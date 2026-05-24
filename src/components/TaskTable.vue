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
      <div class="flex-1 px-4">文件名</div>
      <div class="w-24 px-4">类型</div>
      <div class="w-40 px-4 text-right">状态 / 进度</div>
      <div class="w-10"></div> <!-- Actions column space -->
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
        <div class="w-24 px-4">
          <span 
            :class="categoryClass(task.category)"
            class="px-2 py-0.5 rounded-full text-[10px] font-semibold border"
          >
            {{ categoryLabel(task.category) }}
          </span>
        </div>

        <!-- Progress / Status -->
        <div class="w-40 px-4 flex flex-col items-end gap-1.5">
          <div v-if="task.status === 'processing'" class="w-full">
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

          <div v-else-if="task.status === 'completed'" class="flex items-center gap-1.5 text-emerald-600">
            <span class="text-[11px] font-semibold tracking-tight">已清洗 & 压缩</span>
            <div class="w-4 h-4 rounded-full bg-emerald-100 flex items-center justify-center">
              <svg class="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3"><path d="M5 13l4 4L19 7"></path></svg>
            </div>
          </div>

          <div v-else-if="task.status === 'error'" class="flex items-center gap-1.5 text-rose-500 group-hover:text-rose-600 transition-colors">
            <span class="text-[10px] font-medium truncate max-w-[140px]" :title="task.message">{{ task.message }}</span>
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
          </div>

          <div v-else-if="task.status === 'scanning'" class="flex items-center gap-2">
            <span class="text-[11px] text-slate-400 font-medium">结构分析中</span>
            <div class="flex gap-0.5">
              <div class="w-1 h-1 bg-slate-300 rounded-full animate-bounce" style="animation-delay: 0s"></div>
              <div class="w-1 h-1 bg-slate-300 rounded-full animate-bounce" style="animation-delay: 0.1s"></div>
              <div class="w-1 h-1 bg-slate-300 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
            </div>
          </div>

          <span v-else class="text-[11px] text-slate-300 font-medium tracking-tight group-hover:text-slate-400 transition-colors">
            等待队列
          </span>
        </div>

        <!-- Per-row Action: Remove -->
        <div class="w-10 flex justify-center opacity-0 group-hover:opacity-100 transition-all duration-200">
          <button 
            @click="$emit('remove-task', task.path)"
            :disabled="task.status === 'processing'"
            class="p-1.5 text-slate-300 hover:text-rose-500 hover:bg-rose-50 rounded-md transition-all active:scale-90 disabled:opacity-0"
            title="移除文件"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  tasks: any[];
}>();

const emit = defineEmits(['toggle-all', 'remove-task']);

const allSelected = computed(() => {
  return props.tasks.length > 0 && props.tasks.every(t => t.selected);
});

function categoryLabel(cat: string) {
  switch (cat) {
    case 'TYPE_1': return '文本';
    case 'TYPE_2': return '干扰';
    case 'TYPE_3': return 'OCR';
    case 'TYPE_4': return '全图';
    case 'NOT_FOUND': return '错误';
    default: return '待分析';
  }
}

function categoryClass(cat: string) {
  switch (cat) {
    case 'TYPE_2':
    case 'TYPE_4': return 'bg-amber-50 text-amber-600 border-amber-200/60';
    case 'TYPE_1':
    case 'TYPE_3': return 'bg-blue-50 text-blue-600 border-blue-200/60';
    default: return 'bg-slate-50 text-slate-400 border-slate-200/60';
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
