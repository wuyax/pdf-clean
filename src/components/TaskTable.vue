<template>
  <div class="w-full h-full flex flex-col bg-white overflow-hidden">
    <!-- Header -->
    <div class="flex items-center px-4 py-3 border-b border-slate-100 bg-slate-50/50 text-[11px] font-semibold uppercase tracking-wider text-slate-400 select-none">
      <div class="w-8 flex items-center">
        <input 
          type="checkbox" 
          :checked="allSelected" 
          @change="$emit('toggle-all')"
          class="w-3.5 h-3.5 rounded border-slate-300 text-blue-600 focus:ring-0 focus:ring-offset-0 cursor-pointer"
        />
      </div>
      <div class="flex-1 px-4 flex items-center">
        <Files class="w-3.5 h-3.5 mr-1.5 opacity-60" />
        <span>文件名</span>
      </div>
      <div class="w-24 px-4 text-center">类型</div>
      <div class="w-56 px-4 text-center">状态 / 进度</div>
      <div class="w-20"></div> <!-- Actions column space -->
    </div>

    <!-- Rows -->
    <div class="flex-1 overflow-y-auto scrollbar-hide">
      <div 
        v-for="(task, index) in tasks" 
        :key="task.path" 
        class="group flex items-center px-4 py-2.5 border-b border-slate-50 hover:bg-blue-50/30 transition-all duration-150 ease-out relative"
        :class="{'bg-slate-50/20': index % 2 === 0}"
      >
        <!-- Checkbox -->
        <div class="w-8 flex items-center">
          <input 
            type="checkbox" 
            v-model="task.selected"
            :disabled="task.status === 'processing' || task.status === 'completed'"
            class="w-3.5 h-3.5 rounded border-slate-300 text-blue-600 focus:ring-0 focus:ring-offset-0 cursor-pointer disabled:opacity-30"
          />
        </div>

        <!-- Name -->
        <div class="flex-1 px-4 flex flex-col min-w-0">
          <span class="text-sm font-medium text-slate-700 truncate tracking-tight" :title="task.path">
            {{ task.name }}
          </span>
          <span class="text-[10px] text-slate-400 truncate mt-0.5 tabular-nums">
            {{ task.path }}
          </span>
        </div>

        <!-- Category Tag -->
        <div class="w-24 px-4 flex justify-center items-center">
          <span 
            :class="categoryClass(task.category)"
            class="px-2 py-0.5 rounded-full text-[10px] font-semibold border flex items-center gap-1 justify-center"
          >
            <component :is="getCategoryIcon(task.category)" class="w-3 h-3" />
            {{ categoryLabel(task.category) }}
          </span>
        </div>

        <!-- Progress / Status -->
        <div class="w-56 px-4 flex flex-col items-center gap-1.5">
          <div v-if="task.status === 'processing'" class="w-full flex items-center gap-2">
            <div class="flex-1">
              <div class="flex justify-between items-center mb-1 tabular-nums">
                <span class="text-[10px] font-medium text-blue-600 animate-pulse">{{ task.message }}</span>
                <span class="text-[10px] font-bold text-blue-600">{{ Math.round((task.current_page / task.total_pages) * 100) || 0 }}%</span>
              </div>
              <div class="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden relative shadow-inner">
                <div 
                  class="bg-blue-500 h-full rounded-full transition-all duration-500 ease-in-out relative" 
                  :style="{ width: `${(task.current_page / task.total_pages) * 100 || 0}%` }"
                >
                  <div class="absolute inset-0 shimmer-effect opacity-50"></div>
                </div>
              </div>
            </div>
            <button 
              @click="$emit('abort-task', task.path)"
              class="p-1 text-slate-400 hover:text-rose-500 hover:bg-rose-50 rounded-md transition-all active:scale-90"
              title="中止任务"
            >
              <XCircle class="w-4 h-4" />
            </button>
          </div>

          <div v-else-if="task.status === 'completed'" class="flex items-center gap-1.5 text-emerald-600">
            <span class="text-[11px] font-semibold tracking-tight">已清洗 & 压缩</span>
            <div class="w-4 h-4 rounded-full bg-emerald-100 flex items-center justify-center">
              <CheckCircle2 class="w-3 h-3" />
            </div>
          </div>

          <div v-else-if="task.status === 'error'" class="flex items-center gap-1.5 text-rose-500 group-hover:text-rose-600 transition-colors">
            <span class="text-[10px] font-medium truncate max-w-[204px]" :title="task.message">{{ task.message }}</span>
            <AlertCircle class="w-3.5 h-3.5" />
          </div>

          <div v-else-if="task.status === 'scanning'" class="flex items-center gap-2">
            <span class="text-[11px] text-slate-400 font-medium">结构分析中</span>
            <RefreshCw class="w-3 h-3 animate-spin text-slate-400" />
          </div>

          <span v-else class="text-[11px] text-slate-300 font-medium tracking-tight group-hover:text-slate-400 transition-colors">
            等待队列
          </span>
        </div>

        <!-- Per-row Action: Show Location & Remove -->
        <div class="w-20 flex justify-center items-center gap-1 opacity-0 group-hover:opacity-100 transition-all duration-200">
          <button 
            @click="openFileLocation(task.path)"
            class="p-1.5 text-slate-300 hover:text-blue-500 hover:bg-blue-50 rounded-md transition-all active:scale-90"
            title="打开文件位置"
          >
            <FolderOpen class="w-4 h-4" />
          </button>
          <button 
            @click="$emit('remove-task', task.path)"
            :disabled="task.status === 'processing'"
            class="p-1.5 text-slate-300 hover:text-rose-500 hover:bg-rose-50 rounded-md transition-all active:scale-90 disabled:opacity-0"
            title="移除文件"
          >
            <Trash2 class="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Task } from '../types/task';
import { revealItemInDir } from '@tauri-apps/plugin-opener';
import { 
  Files, 
  FileText, 
  FileX, 
  ScanText, 
  FileImage, 
  FileWarning, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw, 
  Trash2,
  XCircle,
  Lock,
  FolderOpen
} from '@lucide/vue';

const props = defineProps<{
  tasks: Task[];
}>();

const emit = defineEmits(['toggle-all', 'remove-task', 'abort-task']);

async function openFileLocation(path: string) {
  try {
    await revealItemInDir(path);
  } catch (e) {
    console.error('Failed to open file location:', e);
  }
}

const allSelected = computed(() => {
  return props.tasks.length > 0 && props.tasks.every(t => t.selected);
});

function categoryLabel(cat: string) {
  switch (cat) {
    case 'TYPE_1': return '文本';
    case 'TYPE_2': return '干扰';
    case 'TYPE_3': return 'OCR';
    case 'TYPE_4': return '全图';
    case 'TYPE_ENCRYPTED': return '已加密';
    case 'NOT_FOUND': return '错误';
    default: return '待分析';
  }
}

function categoryClass(cat: string) {
  switch (cat) {
    case 'TYPE_2':
    case 'TYPE_4': return 'bg-amber-50 text-amber-600 border-amber-200/60';
    case 'TYPE_ENCRYPTED': return 'bg-rose-50 text-rose-600 border-rose-200/60';
    case 'TYPE_1':
    case 'TYPE_3': return 'bg-blue-50 text-blue-600 border-blue-200/60';
    default: return 'bg-slate-50 text-slate-400 border-slate-200/60';
  }
}

function getCategoryIcon(cat: string) {
  switch (cat) {
    case 'TYPE_1': return FileText;
    case 'TYPE_2': return FileX;
    case 'TYPE_3': return ScanText;
    case 'TYPE_4': return FileImage;
    case 'TYPE_ENCRYPTED': return Lock;
    case 'NOT_FOUND': return FileWarning;
    default: return Files;
  }
}
</script>

<style scoped>
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.shimmer-effect {
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0) 0%,
    rgba(255, 255, 255, 0.4) 50%,
    rgba(255, 255, 255, 0) 100%
  );
  background-size: 200% 100%;
  animation: shimmer 2s infinite;
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
</style>
