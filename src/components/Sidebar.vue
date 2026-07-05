<template>
  <aside class="w-[260px] border-r border-slate-200/60 bg-slate-50/50 flex flex-col shrink-0">
    <div class="flex-1 p-4 space-y-6 overflow-y-auto">
      <!-- Main Actions -->
      <div class="space-y-2">
        <button
          @click="$emit('start-processing')"
          :disabled="isGlobalProcessing || !hasSelectedTasks || (saveMode === 'custom-dir' && !customOutputDir)"
          class="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-200 text-white rounded-lg text-[13px] font-semibold transition-all shadow-sm active:scale-[0.98]"
        >
          <Zap v-if="!isGlobalProcessing" class="w-4 h-4" :stroke-width="2.5" />
          <Loader2 v-else class="w-4 h-4 animate-spin" />
          {{ isGlobalProcessing ? '正在处理...' : '开始清理' }}
        </button>

        <div class="grid grid-cols-2 gap-2">
          <button
            @click="$emit('select-files')"
            :disabled="isGlobalProcessing"
            class="flex items-center justify-center gap-1.5 px-3 py-2 bg-white border border-slate-200 hover:border-slate-300 rounded-lg text-[12px] font-medium text-slate-700 transition-all active:scale-[0.98]"
          >
            <FilePlus class="w-3.5 h-3.5" />
            添加文件
          </button>
          <button
            @click="$emit('clear-all')"
            :disabled="isGlobalProcessing || tasksCount === 0"
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
            @click="$emit('toggle-filter', 'processing')"
            class="flex items-center justify-between px-3 py-2 rounded-lg text-[12px] font-medium transition-all"
            :class="filterStatus.includes('processing') ? 'bg-blue-50 text-blue-600 shadow-sm' : 'text-slate-500 hover:bg-slate-100'"
          >
            <div class="flex items-center gap-2">
              <Loader2 v-if="filterStatus.includes('processing')" class="w-3.5 h-3.5 animate-spin" />
              <div v-else class="w-1.5 h-1.5 rounded-full bg-slate-300 mx-1"></div>
              处理中
            </div>
            <span class="text-[10px] font-bold opacity-60">{{ processingCount }}</span>
          </button>

          <button
            @click="$emit('toggle-filter', 'pending')"
            class="flex items-center justify-between px-3 py-2 rounded-lg text-[12px] font-medium transition-all"
            :class="filterStatus.includes('pending') ? 'bg-slate-100 text-slate-900 shadow-sm' : 'text-slate-500 hover:bg-slate-100'"
          >
            <div class="flex items-center gap-2">
              <Clock v-if="filterStatus.includes('pending')" class="w-3.5 h-3.5" />
              <div v-else class="w-1.5 h-1.5 rounded-full bg-slate-300 mx-1"></div>
              待处理
            </div>
            <span class="text-[10px] font-bold opacity-60">{{ pendingCount }}</span>
          </button>
        </div>
      </div>

      <!-- Save Settings Card -->
      <div class="space-y-4 bg-white/50 border border-slate-200/60 rounded-xl p-3">
        <div class="text-[11px] font-bold text-slate-500 uppercase tracking-tight">保存设置</div>
        
        <!-- Save Mode Options -->
        <div class="space-y-2">
          <label class="flex items-center gap-2 cursor-pointer">
            <input 
              type="radio" 
              :value="'same-dir'" 
              :checked="saveMode === 'same-dir'"
              @change="$emit('update:saveMode', 'same-dir')"
              class="w-3.5 h-3.5 text-blue-600 border-slate-300 focus:ring-blue-500" 
            />
            <span class="text-xs font-medium text-slate-700">保存在原文件目录</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input 
              type="radio" 
              :value="'custom-dir'" 
              :checked="saveMode === 'custom-dir'"
              @change="$emit('update:saveMode', 'custom-dir')"
              class="w-3.5 h-3.5 text-blue-600 border-slate-300 focus:ring-blue-500" 
            />
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
              @click="$emit('select-custom-dir')" 
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
              <input 
                type="radio" 
                :value="'overwrite'" 
                :checked="conflictPolicy === 'overwrite'"
                @change="$emit('update:conflictPolicy', 'overwrite')"
                class="w-3 h-3 text-blue-600 border-slate-300 focus:ring-blue-500" 
              />
              <span class="text-[11px] font-medium text-slate-600">自动覆盖</span>
            </label>
            <label class="flex items-center gap-1.5 cursor-pointer">
              <input 
                type="radio" 
                :value="'rename'" 
                :checked="conflictPolicy === 'rename'"
                @change="$emit('update:conflictPolicy', 'rename')"
                class="w-3 h-3 text-blue-600 border-slate-300 focus:ring-blue-500" 
              />
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
          <p class="text-[10px] text-slate-400 font-medium">RapidOCR (ONNX)</p>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { Zap, Loader2, FilePlus, Trash2, Clock } from '@lucide/vue';
import { SaveMode, ConflictPolicy } from '../types/task';

defineProps<{
  isGlobalProcessing: boolean;
  hasSelectedTasks: boolean;
  saveMode: SaveMode;
  customOutputDir: string;
  conflictPolicy: ConflictPolicy;
  filterStatus: string[];
  tasksCount: number;
  processingCount: number;
  pendingCount: number;
  completedTaskCount: number;
  totalSelectedTaskCount: number;
  globalProgress: number;
}>();

defineEmits<{
  (e: 'update:saveMode', val: SaveMode): void;
  (e: 'update:customOutputDir', val: string): void;
  (e: 'update:conflictPolicy', val: ConflictPolicy): void;
  (e: 'start-processing'): void;
  (e: 'select-files'): void;
  (e: 'clear-all'): void;
  (e: 'select-custom-dir'): void;
  (e: 'toggle-filter', status: string): void;
}>();
</script>
