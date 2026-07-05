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
        v-model:save-mode="saveMode"
        v-model:custom-output-dir="customOutputDir"
        v-model:conflict-policy="conflictPolicy"
        :is-global-processing="isGlobalProcessing"
        :has-selected-tasks="hasSelectedTasks"
        :filter-status="filterStatus"
        :tasks-count="tasks.length"
        :processing-count="tasks.filter(t => t.status === 'processing').length"
        :pending-count="tasks.filter(t => t.status === 'idle' || t.status === 'scanning').length"
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
    <Footer :tasks-count="tasks.length" :error="processorError || settingsError" />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import Titlebar from './components/Titlebar.vue';
import Sidebar from './components/Sidebar.vue';
import EmptyState from './components/EmptyState.vue';
import TaskTable from './components/TaskTable.vue';
import Footer from './components/Footer.vue';

import { useSettings } from './composables/useSettings';
import { useFileDrop } from './composables/useFileDrop';
import { useTaskProcessor } from './composables/useTaskProcessor';

// Initialize Settings Composable
const {
  saveMode,
  customOutputDir,
  conflictPolicy,
  selectCustomOutputDir,
  error: settingsError,
} = useSettings();

// Initialize Task Processor Composable
const {
  tasks,
  isGlobalProcessing,
  error: processorError,
  filterStatus,
  filteredTasks,
  totalSelectedTaskCount,
  completedTaskCount,
  globalProgress,
  hasSelectedTasks,
  addTasksFromPaths,
  selectFiles,
  startBatchProcessing,
  removeTask,
  clearAll,
  toggleAll,
  toggleFilter,
} = useTaskProcessor(saveMode, customOutputDir, conflictPolicy);

// Initialize File Drop Composable
const {
  isDragging,
  onDragEnter,
  onDragLeave,
  onDrop,
  setupTauriDropListeners,
} = useFileDrop();

onMounted(() => {
  setupTauriDropListeners(addTasksFromPaths);
});
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
