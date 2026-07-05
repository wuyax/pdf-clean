<template>
  <footer class="h-8 border-t border-slate-200/60 bg-white flex items-center px-6 justify-between text-[10px] font-bold uppercase tracking-widest text-slate-400 select-none shrink-0">
    <div class="flex gap-6">
      <div v-if="tasksCount > 0" class="flex items-center gap-2">
        <div class="w-1.5 h-1.5 rounded-full bg-blue-400"></div>
        <span>{{ tasksCount }} 个文件已载入</span>
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
</template>

<script setup lang="ts">
import { AlertCircle } from 'lucide-vue-next';

defineProps<{
  tasksCount: number;
  error: string;
}>();
</script>
