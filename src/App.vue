<!-- src/App.vue -->
<template>
  <div class="min-h-screen bg-gray-50 flex flex-col p-6 font-sans">
    <div class="max-w-4xl mx-auto w-full">
      <header class="flex justify-between items-center mb-8">
        <div>
          <h1 class="text-3xl font-extrabold text-gray-900 tracking-tight">PDF OCR Cleaner</h1>
          <p class="text-gray-500 mt-1">智能清除干扰层，像素级还原清晰 PDF</p>
        </div>
        <div class="flex gap-3">
          <button 
            @click="selectFiles" 
            :disabled="isGlobalProcessing"
            class="px-4 py-2 bg-white border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            添加文件
          </button>
          <button 
            @click="startBatchProcessing" 
            :disabled="isGlobalProcessing || !hasSelectedTasks"
            class="px-4 py-2 bg-blue-600 border border-transparent rounded-md shadow-sm text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {{ isGlobalProcessing ? '正在处理...' : '开始清理' }}
          </button>
        </div>
      </header>

      <div v-if="tasks.length === 0" 
           @click="selectFiles"
           class="border-2 border-dashed border-gray-300 rounded-xl p-20 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-all group">
        <div class="mb-4">
          <svg class="mx-auto h-12 w-12 text-gray-400 group-hover:text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <p class="text-lg font-medium text-gray-900">拖入或选择 PDF 文件</p>
        <p class="text-sm text-gray-500 mt-1">支持批量选择，智能识别干扰层模式</p>
      </div>

      <TaskTable 
        v-else 
        :tasks="tasks" 
        @toggle-all="toggleAll" 
      />

      <div v-if="error" class="mt-6 p-4 bg-red-50 border-l-4 border-red-400 text-red-700 text-sm">
        {{ error }}
      </div>

      <footer class="mt-12 pt-8 border-t border-gray-200 text-center text-xs text-gray-400">
        <p>基于 PaddleOCR 3.5.0 & PyMuPDF 驱动</p>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { open } from '@tauri-apps/plugin-dialog';
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

const API_URL = 'http://127.0.0.1:8000';

const hasSelectedTasks = computed(() => {
  return tasks.value.some(t => t.selected && t.status !== 'completed');
});

async function selectFiles() {
  try {
    const selected = await open({
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
      multiple: true,
    });
    
    if (selected && Array.isArray(selected)) {
      const newTasks = selected.map(path => ({
        path,
        name: path.split(/[/\\]/).pop() || path,
        selected: true,
        category: 'UNKNOWN',
        status: 'idle' as const,
        message: '等待扫描',
        current_page: 0,
        total_pages: 0
      }));
      
      // Filter out already added paths
      const existingPaths = new Set(tasks.value.map(t => t.path));
      const filteredNewTasks = newTasks.filter(t => !existingPaths.has(t.path));
      
      tasks.value = [...tasks.value, ...filteredNewTasks];
      if (filteredNewTasks.length > 0) {
        await scanFiles(filteredNewTasks);
      }
    }
  } catch (err) {
    error.value = '选择文件失败';
  }
}

async function scanFiles(targetTasks: Task[]) {
  const paths = targetTasks.map(t => t.path);
  targetTasks.forEach(t => t.status = 'scanning');
  
  try {
    const response = await fetch(`${API_URL}/scan`, {
      method: 'POST',
      body: JSON.stringify({ file_paths: paths }),
      headers: { 'Content-Type': 'application/json' }
    });
    
    if (response.ok) {
      const results = await response.json();
      targetTasks.forEach(t => {
        t.category = results[t.path] || 'UNKNOWN';
        t.status = 'idle';
        t.message = '准备就绪';
        // Auto-select TYPE_2 and TYPE_4
        t.selected = (t.category === 'TYPE_2' || t.category === 'TYPE_4');
      });
    } else {
      throw new Error(`Scan failed: ${response.status}`);
    }
  } catch (err: any) {
    targetTasks.forEach(t => {
      t.status = 'error';
      t.message = '分析失败: ' + err.message;
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
      
      // Setup SSE
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
        
        eventSource.onerror = (e) => {
          console.error('SSE Error:', e);
          // Only error out if we haven't finished
          if (task.status !== 'completed') {
            task.status = 'error';
            task.message = '进度流中断';
          }
          eventSource.close();
          resolve(false);
        };
      });
    } else {
      task.status = 'error';
      task.message = `后端错误: ${response.status}`;
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
/* Ensure smooth transitions for progress bars */
.transition-all {
  transition-property: all;
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  transition-duration: 300ms;
}
</style>
