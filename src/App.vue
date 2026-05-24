<!-- src/App.vue -->
<template>
  <div 
    class="min-h-screen bg-[#f5f5f7] flex flex-col font-system select-none overflow-hidden"
    @dragenter.prevent="onDragEnter"
    @dragleave.prevent="onDragLeave"
    @dragover.prevent
    @drop.prevent="onDrop"
  >
    <!-- Custom Titlebar (Draggable) -->
    <header 
      data-tauri-drag-region
      class="h-12 flex items-center justify-between px-4 bg-[#f5f5f7] border-b border-gray-200/60 sticky top-0 z-50 window-blur"
    >
      <!-- Left side: Traffic lights space on Mac (approx 70px) + Title -->
      <div class="flex items-center pl-[70px] pointer-events-none" data-tauri-drag-region>
        <span class="text-sm font-semibold text-gray-800 tracking-wide">PDF OCR Cleaner</span>
      </div>

      <!-- Right side: Actions -->
      <div class="flex gap-2 items-center z-10">
        <button 
          @click="selectFiles" 
          :disabled="isGlobalProcessing"
          class="px-3 py-1.5 bg-white border border-gray-200 rounded text-xs font-medium text-gray-700 hover:bg-gray-50 active:bg-gray-100 disabled:opacity-50 transition-colors shadow-sm"
        >
          添加文件
        </button>
        <button 
          @click="startBatchProcessing" 
          :disabled="isGlobalProcessing || !hasSelectedTasks"
          class="px-3 py-1.5 bg-blue-500 border border-transparent rounded text-xs font-medium text-white hover:bg-blue-600 active:bg-blue-700 disabled:opacity-50 transition-colors shadow-sm"
        >
          {{ isGlobalProcessing ? '正在处理...' : '开始清理' }}
        </button>
      </div>
    </header>

    <!-- Main Content Area -->
    <main class="flex-1 overflow-y-auto relative">
      <!-- Empty State -->
      <div v-if="tasks.length === 0" class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <svg class="w-16 h-16 text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p class="text-gray-500 font-medium">将 PDF 文件拖放到此处</p>
        <p class="text-xs text-gray-400 mt-1">或者点击右上角添加文件</p>
      </div>

      <!-- Task List -->
      <div v-else class="h-full">
        <TaskTable 
          :tasks="tasks" 
          @toggle-all="toggleAll" 
        />
      </div>

      <!-- Global Drag Overlay -->
      <div 
        v-if="isDragging" 
        class="absolute inset-0 bg-blue-500/10 backdrop-blur-sm border-2 border-blue-400 border-dashed m-2 rounded-lg flex items-center justify-center z-50 pointer-events-none transition-all duration-200"
      >
        <div class="bg-white/90 px-6 py-3 rounded-full shadow-lg backdrop-blur-md border border-white/20">
          <p class="text-blue-600 font-medium tracking-wide">松开鼠标添加文件</p>
        </div>
      </div>
    </main>

    <!-- Status Bar -->
    <footer class="h-8 border-t border-gray-200/60 bg-[#f5f5f7] flex items-center px-4 justify-between text-[11px] text-gray-500 select-none">
      <div class="flex gap-4">
        <span v-if="tasks.length > 0">共 {{ tasks.length }} 个文件</span>
        <span v-if="error" class="text-red-500 flex items-center gap-1">
          <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
          {{ error }}
        </span>
      </div>
      <div>基于 PaddleOCR 驱动</div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { open } from '@tauri-apps/plugin-dialog';
import { listen } from '@tauri-apps/api/event';
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
let dragCounter = 0;

const API_URL = 'http://127.0.0.1:8000';

const hasSelectedTasks = computed(() => {
  return tasks.value.some(t => t.selected && t.status !== 'completed');
});

// Drag and drop handling
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

async function onDrop(e: DragEvent) {
  dragCounter = 0;
  isDragging.value = false;
  
  const files = e.dataTransfer?.files;
  if (!files) return;

  // In a real Tauri app, dropping files needs to be handled via Tauri events 
  // because browser File API doesn't give absolute paths.
  // We setup the listener below.
}

onMounted(async () => {
  // Setup Tauri global file drop listener
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
    const lastSlash = Math.max(task.path.lastIndexOf('/'), task.path.lastIndexOf('\\'));
    const outputDir = task.path.substring(0, lastSlash);
    
    const response = await fetch(`${API_URL}/process`, {
      method: 'POST',
      body: JSON.stringify({ input_path: task.path, output_dir: outputDir }),
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
          if (task.status !== 'completed') {
            task.status = 'error';
            task.message = '流中断';
          }
          eventSource.close();
          resolve(false);
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
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

/* Make custom titlebar blend with OS on Mac */
.window-blur {
  background: rgba(245, 245, 247, 0.8);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

/* Hide scrollbar for a cleaner look but allow scrolling */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.2);
}
</style>
