<!-- src/App.vue -->
<template>
  <div
    class="h-screen flex flex-col font-system select-none overflow-hidden text-slate-900 bg-white"
    @dragenter.prevent="onDragEnter"
    @dragleave.prevent="onDragLeave"
    @dragover.prevent
    @drop.prevent="onDrop"
  >
    <!-- Simplified Titlebar -->
    <Titlebar />

    <div class="flex-1 flex overflow-hidden">
      <!-- Sidebar / Control Center -->
      <Sidebar
        v-model:saveMode="saveMode"
        v-model:customOutputDir="customOutputDir"
        v-model:conflictPolicy="conflictPolicy"
        :is-global-processing="isGlobalProcessing"
        :has-selected-tasks="hasSelectedTasks"
        :filter-status="filterStatus"
        :tasks-count="tasks.length"
        :processing-count="processingCount"
        :pending-count="pendingCount"
        :completed-task-count="completedTaskCount"
        :total-selected-task-count="totalSelectedTaskCount"
        :global-progress="globalProgress"
        @start-processing="startBatchProcessing"
        @select-files="selectFiles"
        @clear-all="clearAll"
        @select-custom-dir="selectCustomOutputDir"
        @toggle-filter="toggleFilter"
      />

      <!-- Main Content Area -->
      <main class="flex-1 overflow-hidden relative flex flex-col bg-white">
        <!-- Empty State -->
        <EmptyState v-if="tasks.length === 0" />

        <!-- Task List -->
        <TaskTable
          v-else
          :tasks="filteredTasks"
          @toggle-all="toggleAll"
          @remove-task="removeTask"
        />

        <!-- Global Drag Overlay -->
        <Transition
          enter-active-class="transition duration-300 ease-out"
          enter-from-class="opacity-0 scale-95"
          enter-to-class="opacity-100 scale-100"
          leave-active-class="transition duration-200 ease-in"
          leave-from-class="opacity-100 scale-100"
          leave-to-class="opacity-0 scale-95"
        >
          <div
            v-if="isDragging"
            class="absolute inset-4 bg-blue-600/5 backdrop-blur-[2px] border-2 border-blue-500/30 border-dashed rounded-2xl flex items-center justify-center z-50 pointer-events-none"
          >
            <div class="bg-white px-8 py-4 rounded-2xl shadow-2xl border border-slate-100 flex flex-col items-center gap-3">
              <div class="w-10 h-10 bg-blue-50 rounded-full flex items-center justify-center">
                <svg class="w-5 h-5 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path d="M12 4v16m8-8H4"></path></svg>
              </div>
              <p class="text-sm font-bold text-slate-800 tracking-tight">释放鼠标以添加 PDF</p>
            </div>
          </div>
        </Transition>
      </main>
    </div>

    <!-- Refined Status Bar -->
    <Footer :tasks-count="tasks.length" :error="error" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { open } from '@tauri-apps/plugin-dialog';
import { listen } from '@tauri-apps/api/event';
import Sidebar from './components/Sidebar.vue';
import TaskTable from './components/TaskTable.vue';
import Titlebar from './components/Titlebar.vue';
import EmptyState from './components/EmptyState.vue';
import Footer from './components/Footer.vue';

interface Task {
  path: string;
  name: string;
  selected: boolean;
  category: string;
  status: 'idle' | 'scanning' | 'processing' | 'completed' | 'error';
  message: string;
  current_page: number;
  total_pages: number;
  task_id?: string;
}

const tasks = ref<Task[]>([]);
const isGlobalProcessing = ref(false);
const error = ref('');
const isDragging = ref(false);
const filterStatus = ref<string[]>([]); // 'processing', 'pending'
let dragCounter = 0;

const saveMode = ref<'same-dir' | 'custom-dir'>(
  (localStorage.getItem('saveMode') as 'same-dir' | 'custom-dir') || 'same-dir'
);
const customOutputDir = ref<string>(localStorage.getItem('customOutputDir') || '');
const conflictPolicy = ref<'overwrite' | 'rename'>(
  (localStorage.getItem('conflictPolicy') as 'overwrite' | 'rename') || 'overwrite'
);

watch(saveMode, (val) => {
  localStorage.setItem('saveMode', val);
});
watch(customOutputDir, (val) => {
  localStorage.setItem('customOutputDir', val);
});
watch(conflictPolicy, (val) => {
  localStorage.setItem('conflictPolicy', val);
});

// Directory selection handler
async function selectCustomOutputDir() {
  try {
    const selected = await open({
      directory: true,
      multiple: false,
    });
    if (selected && typeof selected === 'string') {
      customOutputDir.value = selected;
    }
  } catch (err) {
    error.value = '选择文件夹失败';
  }
}

const API_URL = 'http://127.0.0.1:8000';

const filteredTasks = computed(() => {
  if (filterStatus.value.length === 0) return tasks.value;

  return tasks.value.filter(t => {
    if (filterStatus.value.includes('processing') && t.status === 'processing') return true;
    if (filterStatus.value.includes('pending') && (t.status === 'idle' || t.status === 'scanning')) return true;
    return false;
  });
});

const processingCount = computed(() => {
  return tasks.value.filter(t => t.status === 'processing').length;
});

const pendingCount = computed(() => {
  return tasks.value.filter(t => t.status === 'idle' || t.status === 'scanning').length;
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

function onDragEnter(e: DragEvent) {
  dragCounter++;
  if (e.dataTransfer?.types.includes('Files')) {
    isDragging.value = true;
  }
}

function onDragLeave() {
  dragCounter--;
  if (dragCounter === 0) {
    isDragging.value = false;
  }
}

async function onDrop(_e: DragEvent) {
  dragCounter = 0;
  isDragging.value = false;
}

onMounted(async () => {
  try {
    await listen('tauri://file-drop', (event: any) => {
      isDragging.value = false;
      dragCounter = 0;

      const droppedPaths = event.payload as string[];
      if (droppedPaths && droppedPaths.length > 0) {
        const pdfPaths = droppedPaths.filter(p => p.toLowerCase().endsWith('.pdf'));
        if (pdfPaths.length > 0) {
          addTasksFromPaths(pdfPaths);
        }
      }
    });

    await listen('tauri://file-drop-hover', () => {
      isDragging.value = true;
    });

    await listen('tauri://file-drop-cancelled', () => {
      isDragging.value = false;
      dragCounter = 0;
    });
  } catch (e) {
    console.error("Failed to setup drag listeners", e);
  }
});

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
      addTasksFromPaths(selected);
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
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000);

    const response = await fetch(`${API_URL}/scan`, {
      method: 'POST',
      body: JSON.stringify({ file_paths: paths }),
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    if (response.ok) {
      const results = await response.json();
      tasks.value.forEach(t => {
        if (paths.includes(t.path)) {
          t.category = results[t.path] || 'UNKNOWN';
          t.status = 'idle';
          t.message = '准备就绪';
          t.selected = (t.category === 'TYPE_2' || t.category === 'TYPE_4');
        }
      });
    } else {
      throw new Error(`Scan failed: ${response.status}`);
    }
  } catch (err: any) {
    tasks.value.forEach(t => {
      if (paths.includes(t.path)) {
        t.status = 'error';
        if (err.name === 'AbortError') {
          t.message = '分析超时';
        } else {
          t.message = '分析失败: ' + err.message;
        }
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

  for (const task of pendingTasks) {
    await processSingleTask(task);
  }

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
          outputDir += task.path.charAt(lastSlash); // Append the slash to make it C:\ or C:/
        }
      } else {
        outputDir = '.';
      }
    }

    const response = await fetch(`${API_URL}/process`, {
      method: 'POST',
      body: JSON.stringify({ 
        input_path: task.path, 
        output_dir: outputDir,
        conflict_policy: conflictPolicy.value
      }),
      headers: { 'Content-Type': 'application/json' }
    });

    if (response.ok) {
      const data = await response.json();
      task.task_id = data.task_id;

      await new Promise((resolve) => {
        let retryCount = 0;
        const maxRetries = 5;

        function connect() {
          const eventSource = new EventSource(`${API_URL}/stream/${task.task_id}`);

          eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.status === 'not_found' && retryCount < maxRetries) {
              return;
            }
            task.status = data.status;
            task.message = data.message;
            task.current_page = data.current_page;
            task.total_pages = data.total_pages;

            if (data.status === 'completed' || data.status === 'error') {
              eventSource.close();
              resolve(data.status === 'completed');
            }
          };

          eventSource.onerror = async () => {
            eventSource.close();

            try {
              const statusResponse = await fetch(`${API_URL}/status/${task.task_id}`);
              if (statusResponse.ok) {
                const statusData = await statusResponse.json();
                if (statusData.status === 'completed') {
                  task.status = 'completed';
                  task.message = statusData.message;
                  resolve(true);
                  return;
                } else if (statusData.status === 'error') {
                  task.status = 'error';
                  task.message = statusData.message;
                  resolve(false);
                  return;
                } else if (statusData.status === 'processing') {
                  if (retryCount < maxRetries) {
                    retryCount++;
                    task.message = `正在重新连接... (${retryCount}/${maxRetries})`;
                    setTimeout(connect, 1500);
                    return;
                  }
                }
              }
            } catch (err) {
              console.error("Error verifying task status during stream failure:", err);
            }

            if (task.status !== 'completed') {
              task.status = 'error';
              task.message = '流中断';
            }
            resolve(false);
          };
        }

        connect();
      });
    } else {
      task.status = 'error';
      task.message = `HTTP ${response.status}`;
    }
  } catch (err: any) {
    task.status = 'error';
    task.message = err.message;
  }
}

function removeTask(path: string) {
  tasks.value = tasks.value.filter(t => t.path !== path);
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
</script>

<style>
/* Native App Typography & Adjustments */
.font-system {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

.animate-in {
  animation-duration: 0.5s;
  animation-fill-mode: both;
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes zoom-in {
  from { transform: scale(0.98); }
  to { transform: scale(1); }
}

.fade-in { animation-name: fade-in; }
.zoom-in { animation-name: zoom-in; }

/* Scrollbar styling for sidebar */
aside ::-webkit-scrollbar {
  width: 4px;
}

aside ::-webkit-scrollbar-track {
  background: transparent;
}

aside ::-webkit-scrollbar-thumb {
  background: #e2e8f0;
  border-radius: 10px;
}

aside ::-webkit-scrollbar-thumb:hover {
  background: #cbd5e1;
}
</style>
