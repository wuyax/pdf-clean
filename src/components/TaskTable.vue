<template>
  <div class="overflow-x-auto w-full mt-6">
    <table class="min-w-full bg-white rounded-lg overflow-hidden shadow">
      <thead class="bg-gray-200 text-gray-700">
        <tr>
          <th class="py-3 px-4 text-left w-12">
            <input 
              type="checkbox" 
              :checked="allSelected" 
              @change="$emit('toggle-all')"
              class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
          </th>
          <th class="py-3 px-4 text-left">文件名</th>
          <th class="py-3 px-4 text-left">类型</th>
          <th class="py-3 px-4 text-left">状态/进度</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-100">
        <tr v-for="task in tasks" :key="task.path" class="hover:bg-gray-50 transition">
          <td class="py-3 px-4">
            <input 
              type="checkbox" 
              v-model="task.selected"
              :disabled="task.status === 'processing' || task.status === 'completed'"
              class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
          </td>
          <td class="py-3 px-4 text-sm font-medium text-gray-800 truncate max-w-xs" :title="task.path">
            {{ task.name }}
          </td>
          <td class="py-3 px-4">
            <span 
              :class="categoryClass(task.category)"
              class="px-2 py-1 rounded-full text-xs font-semibold"
            >
              {{ categoryLabel(task.category) }}
            </span>
          </td>
          <td class="py-3 px-4">
            <div v-if="task.status === 'processing'" class="w-full">
              <div class="flex justify-between mb-1">
                <span class="text-xs text-blue-600">{{ task.message }}</span>
                <span class="text-xs text-blue-600">{{ Math.round((task.current_page / task.total_pages) * 100) || 0 }}%</span>
              </div>
              <div class="w-full bg-gray-200 rounded-full h-1.5">
                <div 
                  class="bg-blue-600 h-1.5 rounded-full transition-all duration-300" 
                  :style="{ width: `${(task.current_page / task.total_pages) * 100 || 0}%` }"
                ></div>
              </div>
            </div>
            <span v-else-if="task.status === 'completed'" class="text-xs text-green-600 font-medium">
              完成 (体积已优化)
            </span>
            <span v-else-if="task.status === 'error'" class="text-xs text-red-600 font-medium">
              失败: {{ task.message }}
            </span>
            <span v-else-if="task.status === 'scanning'" class="text-xs text-gray-500 italic">
              正在分析...
            </span>
            <span v-else class="text-xs text-gray-400">
              等待处理
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
    case 'TYPE_2': return '干扰层/欺骗';
    case 'TYPE_3': return '已有正确OCR';
    case 'TYPE_4': return '纯图片';
    case 'NOT_FOUND': return '找不到文件';
    default: return '未知/未扫描';
  }
}

function categoryClass(cat: string) {
  switch (cat) {
    case 'TYPE_2':
    case 'TYPE_4': return 'bg-yellow-100 text-yellow-800 border border-yellow-200';
    case 'TYPE_1':
    case 'TYPE_3': return 'bg-green-50 text-green-700 border border-green-100';
    default: return 'bg-gray-100 text-gray-600';
  }
}
</script>
