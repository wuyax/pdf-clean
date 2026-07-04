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
    <header
      data-tauri-drag-region
      class="h-[30px] flex items-center px-4 border-b border-slate-200/60 bg-white z-50 shrink-0"
    >
      <div class="flex items-center gap-2 pointer-events-none ml-[72px]" data-tauri-drag-region>
        <span class="text-[11px] font-semibold text-slate-700">PDF OCR Cleaner</span>
        <span class="text-[10px] text-slate-400 font-medium tracking-wide">v1.0</span>
      </div>
    </header>

    <div class="flex-1 flex overflow-hidden">
      <!-- Sidebar / Control Center -->
      <aside class="w-[260px] border-r border-slate-200/60 bg-slate-50/50 flex flex-col shrink-0">
        <div class="flex-1 p-4 space-y-6 overflow-y-auto">
          <!-- Main Actions -->
          <div class="space-y-2">
            <button
              @click="startBatchProcessing"
              :disabled="isGlobalProcessing || !hasSelectedTasks || (saveMode === 'custom-dir' && !customOutputDir)"
              class="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-200 text-white rounded-lg text-[13px] font-semibold transition-all shadow-sm active:scale-[0.98]"
            >
              <Zap v-if="!isGlobalProcessing" class="w-4 h-4" :stroke-width="2.5" />
              <Loader2 v-else class="w-4 h-4 animate-spin" />
              {{ isGlobalProcessing ? '正在处理...' : '开始清理' }}
            </button>

            <div class="grid grid-cols-2 gap-2">
              <button
                @click="selectFiles"
                :disabled="isGlobalProcessing"
                class="flex items-center justify-center gap-1.5 px-3 py-2 bg-white border border-slate-200 hover:border-slate-300 rounded-lg text-[12px] font-medium text-slate-700 transition-all active:scale-[0.98]"
              >
                <FilePlus class="w-3.5 h-3.5" />
                添加文件
              </button>
              <button
                @click="clearAll"
                :disabled="isGlobalProcessing || tasks.length === 0"
                class="flex items-center justify-center gap-1.5 px-3 py-2 bg-white border border-slate-200 hover:border-rose-200 hover:text-rose-600 rounded-lg text-[12px] font-medium text-slate-700 transition-all active:scale-[0.98]"
              >
                <Trash2 class="w-3.5 h-3.5" />
                清空列表
              </button>
            </div>
          </div>

          <!-- Filter Section with Divider -->
          <div class="space-y-4">
            <div class="border-t border-slate-200/60 mx-1"></div>

            <div class="flex flex-col gap-2 px-1">
              <button
                @click="toggleFilter('processing')"
                class="flex items-center justify-between px-3 py-2 rounded-lg text-[12px] font-medium transition-all"
                :class="filterStatus.includes('processing') ? 'bg-blue-50 text-blue-600 shadow-sm' : 'text-slate-500 hover:bg-slate-100'"
              >
                <div class="flex items-center gap-2">
                  <Loader2 v-if="filterStatus.includes('processing')" class="w-3.5 h-3.5 animate-spin" />
                  <div v-else class="w-1.5 h-1.5 rounded-full bg-slate-300 mx-1"></div>
                  处理中
                </div>
                <span class="text-[10px] font-bold opacity-60">{{ tasks.filter(t => t.status === 'processing').length }}</span>
              </button>

              <button
                @click="toggleFilter('pending')"
                class="flex items-center justify-between px-3 py-2 rounded-lg text-[12px] font-medium transition-all"
                :class="filterStatus.includes('pending') ? 'bg-slate-100 text-slate-900 shadow-sm' : 'text-slate-500 hover:bg-slate-100'"
              >
                <div class="flex items-center gap-2">
                  <Clock v-if="filterStatus.includes('pending')" class="w-3.5 h-3.5" />
                  <div v-else class="w-1.5 h-1.5 rounded-full bg-slate-300 mx-1"></div>
                  待处理
                </div>
                <span class="text-[10px] font-bold opacity-60">{{ tasks.filter(t => t.status === 'idle' || t.status === 'scanning').length }}</span>
              </button>
            </div>
          </div>

          <!-- Save Settings Card -->
          <div class="space-y-4 bg-white/50 border border-slate-200/60 rounded-xl p-3">
            <div class="text-[11px] font-bold text-slate-500 uppercase tracking-tight">保存设置</div>
            
            <!-- Save Mode Options -->
            <div class="space-y-2">
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="radio" v-model="saveMode" value="same-dir" class="w-3.5 h-3.5 text-blue-600 border-slate-300 focus:ring-blue-500" />
                <span class="text-xs font-medium text-slate-700">保存在原文件目录</span>
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="radio" v-model="saveMode" value="custom-dir" class="w-3.5 h-3.5 text-blue-600 border-slate-300 focus:ring-blue-500" />
                <span class="text-xs font-medium text-slate-700">保存在自定义目录</span>
              </label>
            </div>
            
            <!-- Custom Dir Chooser (shown only when custom-dir selected) -->
            <div v-if="saveMode === 'custom-dir'" class="space-y-1.5 pt-1">
              <div class="flex items-center gap-1">
                <input 
                  type="text" 
                  readonly 
                  :value="customOutputDir || '未选择文件夹'" 
                  class="flex-1 min-w-0 px-2 py-1 bg-white border border-slate-200 rounded text-[11px] font-medium text-slate-600 truncate focus:outline-none"
                />
                <button 
                  @click="selectCustomOutputDir" 
                  class="px-2 py-1 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded text-[11px] font-semibold transition-colors shrink-0"
                >
                  选择
                </button>
              </div>
            </div>

            <!-- Divider -->
            <div class="border-t border-slate-200/60 my-2"></div>

            <!-- Conflict Policy -->
            <div class="space-y-2">
              <div class="text-[10px] font-semibold text-slate-400">同名文件处理</div>
              <div class="flex items-center gap-4">
                <label class="flex items-center gap-1.5 cursor-pointer">
                  <input type="radio" v-model="conflictPolicy" value="overwrite" class="w-3 h-3 text-blue-600 border-slate-300 focus:ring-blue-500" />
                  <span class="text-[11px] font-medium text-slate-600">自动覆盖</span>
                </label>
                <label class="flex items-center gap-1.5 cursor-pointer">
                  <input type="radio" v-model="conflictPolicy" value="rename" class="w-3 h-3 text-blue-600 border-slate-300 focus:ring-blue-500" />
                  <span class="text-[11px] font-medium text-slate-600">自动重命名</span>
                </label>
              </div>
            </div>
          </div>

          <!-- Global Progress (Visible during processing) -->
          <div v-if="isGlobalProcessing || completedTaskCount > 0" class="space-y-3 bg-white/50 border border-slate-200/60 rounded-xl p-3">
            <div class="flex items-center justify-between text-[11px] font-bold text-slate-500 uppercase tracking-tight">
              <span>总体进度</span>
              <span>{{ completedTaskCount }}/{{ totalSelectedTaskCount }}</span>
            </div>
            <div class="h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                class="h-full bg-blue-500 transition-all duration-500"
                :style="{ width: `${globalProgress}%` }"
              ></div>
            </div>
          </div>
        </div>

        <!-- Sidebar Footer -->
        <div class="p-4 border-t border-slate-200/60 bg-slate-50/80">
          <div class="flex flex-col gap-1.5">
            <div class="flex items-center gap-2">
              <span class="text-[10px] font-semibold text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded">Active</span>
              <p class="text-[10px] text-slate-400 font-medium">PaddleOCR 3.5.0</p>
            </div>
          </div>
        </div>
      </aside>

      <!-- Main Content Area -->
      <main class="flex-1 overflow-hidden relative flex flex-col bg-white">
        <!-- Empty State -->
        <div v-if="tasks.length === 0" class="flex-1 flex flex-col items-center justify-center pointer-events-none animate-in fade-in zoom-in duration-700">
          <div class="relative mb-6">
            <div class="absolute inset-0 bg-blue-100 rounded-full blur-3xl opacity-30 animate-pulse"></div>
            <div class="relative w-20 h-20 bg-slate-50 rounded-2xl border border-slate-100 flex items-center justify-center shadow-sm">
              <svg class="w-10 h-10 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
              </svg>
            </div>
          </div>
          <p class="text-[15px] font-semibold text-slate-700 tracking-tight">准备好处理您的文档</p>
          <p class="text-xs text-slate-400 mt-2 font-medium">将 PDF 文件拖放到此处或点击“添加文件”</p>
        </div>

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
    <footer class="h-8 border-t border-slate-200/60 bg-white flex items-center px-6 justify-between text-[10px] font-bold uppercase tracking-widest text-slate-400 select-none shrink-0">
      <div class="flex gap-6">
        <div v-if="tasks.length > 0" class="flex items-center gap-2">
          <div class="w-1.5 h-1.5 rounded-full bg-blue-400"></div>
          <span>{{ tasks.length }} 个文件已载入</span>
        </div>
        <div v-if="error" class="flex items-center gap-1.5 text-rose-500">
          <AlertCircle class="w-3 h-3" />
          <span>{{ error }}</span>
        </div>
      </div>
      <div class="flex items-center gap-4">
        <span class="hover:text-slate-600 transition-colors cursor-default tracking-normal lowercase font-medium italic">Powered by Impeccable Design</span>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { open } from '@tauri-apps/plugin-dialog';
import { listen } from '@tauri-apps/api/event';
import {
  Zap,
  FilePlus,
  Trash2,
  Loader2,
  Clock,
  AlertCircle
} from 'lucide-vue-next';
import TaskTable from './components/TaskTable.vue';

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
        const eventSource = new EventSource(`${API_URL}/stream/${task.task_id}`);

        eventSource.onmessage = (event) => {
          const data = JSON.parse(event.data);
          task.status = data.status;
          task.message = data.message;
          task.current_page = data.current_page;
          task.total_pages = data.total_pages;

          if (data.status === 'completed' || data.status === 'error') {
            eventSource.close();
            resolve(true);
          }
        };

        eventSource.onerror = (_e) => {
          // Defer checking status to allow pending onmessage events to execute first
          setTimeout(() => {
            if (task.status !== 'completed' && task.status !== 'error') {
              task.status = 'error';
              task.message = '流中断';
              eventSource.close();
              resolve(false);
            }
          }, 100);
        };
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
