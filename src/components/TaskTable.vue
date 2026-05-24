<template>
  <div class="w-full h-full overflow-auto">
    <table class="min-w-full border-collapse text-sm">
      <thead class="bg-[#f5f5f7] text-gray-500 sticky top-0 z-10 border-b border-gray-200">
        <tr>
          <th class="py-2 px-4 text-left w-10">
            <input 
              type="checkbox" 
              :checked="allSelected" 
              @change="$emit('toggle-all')"
              class="w-3.5 h-3.5 rounded border-gray-300 text-blue-500 focus:ring-blue-500/30"
            />
          </th>
          <th class="py-2 px-4 text-left font-medium w-1/2">文件名</th>
          <th class="py-2 px-4 text-left font-medium w-32">类型</th>
          <th class="py-2 px-4 text-left font-medium">状态 / 进度</th>
        </tr>
      </thead>
      <tbody class="bg-white">
        <tr 
          v-for="(task, index) in tasks" 
          :key="task.path" 
          class="border-b border-gray-100 last:border-b-0 hover:bg-blue-50/50 transition-colors"
          :class="{'bg-gray-50/30': index % 2 === 0}"
        >
          <td class="py-2.5 px-4">
            <input 
              type="checkbox" 
              v-model="task.selected"
              :disabled="task.status === 'processing' || task.status === 'completed'"
              class="w-3.5 h-3.5 rounded border-gray-300 text-blue-500 focus:ring-blue-500/30"
            />
          </td>
          <td class="py-2.5 px-4 text-gray-800 truncate max-w-xs" :title="task.path">
            {{ task.name }}
          </td>
          <td class="py-2.5 px-4">
            <span 
              :class="categoryClass(task.category)"
              class="px-2 py-0.5 rounded text-[11px] font-medium tracking-wide inline-block"
            >
              {{ categoryLabel(task.category) }}
            </span>
          </td>
          <td class="py-2.5 px-4">
            <div v-if="task.status === 'processing'" class="w-full flex items-center gap-3">
              <div class="w-full max-w-[120px] bg-gray-200 rounded-full h-1.5 overflow-hidden">
                <div 
                  class="bg-blue-500 h-full transition-all duration-300 ease-out" 
                  :style="{ width: `${(task.current_page / task.total_pages) * 100 || 0}%` }"
                ></div>
              </div>
              <span class="text-[11px] text-gray-500 w-24 truncate">{{ task.message }}</span>
            </div>
            <span v-else-if="task.status === 'completed'" class="text-[11px] text-emerald-600 flex items-center gap-1">
              <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
              已优化
            </span>
            <span v-else-if="task.status === 'error'" class="text-[11px] text-red-500 truncate block max-w-[200px]" :title="task.message">
              {{ task.message }}
            </span>
            <span v-else-if="task.status === 'scanning'" class="text-[11px] text-gray-400 flex items-center gap-1.5">
              <svg class="animate-spin h-3 w-3 text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
              扫描中...
            </span>
            <span v-else class="text-[11px] text-gray-400">
              等待中
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  tasks: any[];
}>();

const emit = defineEmits(['toggle-all']);

const allSelected = computed(() => {
  return props.tasks.length > 0 && props.tasks.every(t => t.selected);
});

function categoryLabel(cat: string) {
  switch (cat) {
    case 'TYPE_1': return '正常文本';
    case 'TYPE_2': return '干扰层';
    case 'TYPE_3': return '已有OCR';
    case 'TYPE_4': return '纯图片';
    case 'NOT_FOUND': return '找不到文件';
    default: return '未知';
  }
}

function categoryClass(cat: string) {
  switch (cat) {
    case 'TYPE_2':
    case 'TYPE_4': return 'bg-amber-100/50 text-amber-700 border border-amber-200/50';
    case 'TYPE_1':
    case 'TYPE_3': return 'bg-emerald-50 text-emerald-600 border border-emerald-100/50';
    default: return 'bg-gray-100 text-gray-500 border border-gray-200';
  }
}
</script>
