import { ref, computed, Ref, onUnmounted } from 'vue';
import { open } from '@tauri-apps/plugin-dialog';
import { listen } from '@tauri-apps/api/event';
import { Task, SaveMode, ConflictPolicy } from '../types/task';
import { scanFilesApi, processTaskApi, abortTaskApi } from '../services/api';

export function useTaskProcessor(
  saveMode: Ref<SaveMode>,
  customOutputDir: Ref<string>,
  conflictPolicy: Ref<ConflictPolicy>,
  resolvedQuality: Ref<{ dpi: number; quality: number }>
) {
  const tasks = ref<Task[]>([]);
  const isGlobalProcessing = ref(false);
  const error = ref('');
  const filterStatus = ref<string[]>([]);

  // Registry to match taskId to its promise resolver function
  const taskResolvers = new Map<string, (val: boolean) => void>();

  // Register single global listener for progress updates
  let unlistenFn: (() => void) | null = null;
  const unlistenPromise = listen('ocr-progress', (event: any) => {
    const data = event.payload;
    const task = tasks.value.find(t => t.task_id === data.task_id);
    if (!task) return;

    task.status = data.status;
    task.message = data.message;
    task.current_page = data.current_page;
    task.total_pages = data.total_pages;

    if (data.status === 'completed' || data.status === 'error') {
      const resolve = taskResolvers.get(data.task_id);
      if (resolve) {
        resolve(data.status === 'completed');
        taskResolvers.delete(data.task_id);
      }
    }
  });

  unlistenPromise.then(fn => {
    unlistenFn = fn;
  });

  onUnmounted(() => {
    if (unlistenFn) unlistenFn();
  });

  const filteredTasks = computed(() => {
    if (filterStatus.value.length === 0) return tasks.value;

    return tasks.value.filter(t => {
      if (filterStatus.value.includes('processing') && t.status === 'processing') return true;
      if (filterStatus.value.includes('pending') && (t.status === 'idle' || t.status === 'scanning')) return true;
      return false;
    });
  });

  const totalSelectedTaskCount = computed(() => {
    return tasks.value.filter(t => t.selected).length;
  });

  const completedTaskCount = computed(() => {
    return tasks.value.filter(t => t.selected && t.status === 'completed').length;
  });

  const globalProgress = computed(() => {
    if (totalSelectedTaskCount.value === 0) return 0;
    return Math.round((completedTaskCount.value / totalSelectedTaskCount.value) * 100);
  });

  const hasSelectedTasks = computed(() => {
    return tasks.value.some(t => t.selected && t.status !== 'completed');
  });

  function toggleFilter(status: string) {
    const index = filterStatus.value.indexOf(status);
    if (index === -1) {
      filterStatus.value.push(status);
    } else {
      filterStatus.value.splice(index, 1);
    }
  }

  async function addTasksFromPaths(paths: string[]) {
    const newTasks = paths.map(path => ({
      path,
      name: path.split(/[/\\]/).pop() || path,
      selected: true,
      category: 'UNKNOWN',
      status: 'idle' as const,
      message: '等待扫描',
      current_page: 0,
      total_pages: 0
    }));

    const existingPaths = new Set(tasks.value.map(t => t.path));
    const filteredNewTasks = newTasks.filter(t => !existingPaths.has(t.path));

    tasks.value = [...tasks.value, ...filteredNewTasks];
    if (filteredNewTasks.length > 0) {
      await scanFiles(filteredNewTasks);
    }
  }

  async function selectFiles() {
    try {
      const selected = await open({
        filters: [{ name: 'PDF', extensions: ['pdf'] }],
        multiple: true,
      });

      if (selected && Array.isArray(selected)) {
        await addTasksFromPaths(selected);
      }
    } catch (err) {
      error.value = '选择文件失败';
    }
  }

  async function scanFiles(targetTasks: Task[]) {
    const paths = targetTasks.map(t => t.path);

    tasks.value.forEach(t => {
      if (paths.includes(t.path)) {
        t.status = 'scanning';
      }
    });

    try {
      const results = await scanFilesApi(paths);

      tasks.value.forEach(t => {
        if (paths.includes(t.path)) {
          t.category = results[t.path] || 'UNKNOWN';
          t.status = 'idle';
          t.message = '准备就绪';
          t.selected = (t.category === 'TYPE_2' || t.category === 'TYPE_4');
        }
      });
    } catch (err: any) {
      tasks.value.forEach(t => {
        if (paths.includes(t.path)) {
          t.status = 'error';
          t.message = '分析失败: ' + err.message;
        }
      });
    }
  }

  async function startBatchProcessing() {
    if (saveMode.value === 'custom-dir' && !customOutputDir.value) {
      error.value = '请选择自定义保存目录';
      return;
    }

    const pendingTasks = tasks.value.filter(t => t.selected && t.status !== 'completed');
    if (pendingTasks.length === 0) return;

    isGlobalProcessing.value = true;
    error.value = '';

    const concurrencyLimit = 2;
    const executing: Promise<void>[] = [];

    for (const task of pendingTasks) {
      const p = processSingleTask(task).then(() => {
        // Remove promise from execution pool when completed
        const index = executing.indexOf(p);
        if (index > -1) {
          executing.splice(index, 1);
        }
      });
      executing.push(p);

      // If we reached the concurrency limit, wait for at least one task to finish
      if (executing.length >= concurrencyLimit) {
        await Promise.race(executing);
      }
    }

    // Wait for all remaining active tasks to finish
    await Promise.all(executing);

    isGlobalProcessing.value = false;
  }

  async function processSingleTask(task: Task) {
    task.status = 'processing';
    task.message = '连接后端...';

    try {
      let outputDir = '';
      if (saveMode.value === 'custom-dir' && customOutputDir.value) {
        outputDir = customOutputDir.value;
      } else {
        const lastSlash = Math.max(task.path.lastIndexOf('/'), task.path.lastIndexOf('\\'));
        if (lastSlash === 0) {
          outputDir = task.path.substring(0, 1);
        } else if (lastSlash > 0) {
          outputDir = task.path.substring(0, lastSlash);
          if (outputDir.endsWith(':')) {
            outputDir += task.path.charAt(lastSlash);
          }
        } else {
          outputDir = '.';
        }
      }

      const taskId = crypto.randomUUID();
      task.task_id = taskId;

      await new Promise<boolean>((resolve) => {
        taskResolvers.set(taskId, resolve);

        processTaskApi({
          input_path: task.path,
          output_dir: outputDir,
          conflict_policy: conflictPolicy.value,
          task_id: taskId,
          dpi: resolvedQuality.value.dpi,
          quality: resolvedQuality.value.quality
        }).catch((err: any) => {
          task.status = 'error';
          task.message = '启动失败: ' + err.message;
          taskResolvers.delete(taskId);
          resolve(false);
        });
      });
    } catch (err: any) {
      task.status = 'error';
      task.message = err.message;
    }
  }

  async function abortTask(path: string) {
    const task = tasks.value.find(t => t.path === path);
    if (!task || !task.task_id || task.status !== 'processing') return;
    try {
      await abortTaskApi(task.task_id);
    } catch (err: any) {
      console.error('Failed to abort task:', err);
    }
  }

  function removeTask(path: string) {
    tasks.value = tasks.value.filter(t => t.path !== path || t.status === 'processing');
  }

  function clearAll() {
    if (isGlobalProcessing.value) return;
    tasks.value = [];
  }

  function toggleAll() {
    const target = !tasks.value.every(t => t.selected);
    tasks.value.forEach(t => {
      if (t.status !== 'processing' && t.status !== 'completed') {
        t.selected = target;
      }
    });
  }

  return {
    tasks,
    isGlobalProcessing,
    error,
    filterStatus,
    filteredTasks,
    totalSelectedTaskCount,
    completedTaskCount,
    globalProgress,
    hasSelectedTasks,
    addTasksFromPaths,
    selectFiles,
    startBatchProcessing,
    removeTask,
    clearAll,
    toggleAll,
    toggleFilter,
    abortTask
  };
}
