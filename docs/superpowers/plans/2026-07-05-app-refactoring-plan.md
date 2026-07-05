# App.vue Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor App.vue to separate UI components (Titlebar, Sidebar, Footer, EmptyState) and business logic (useSettings, useFileDrop, useTaskProcessor composables) to follow Vue 3 best practices and Single Responsibility Principle.

**Architecture:** Split the codebase into:
1. `src/types/task.ts` for interfaces.
2. `src/services/api.ts` for backend HTTP/SSE calls.
3. `src/composables/` for state and event handling logic.
4. `src/components/` for presentational UI components.
5. `src/App.vue` as a thin orchestrator.

**Tech Stack:** Vue 3, Composition API, TypeScript, Vite, Tailwind CSS, Tauri v2.

## Global Constraints

- No features beyond what was asked.
- `vue-tsc --noEmit && vite build` must compile successfully after each task.
- Match existing style and retain existing comments and features (Tauri file drop event listeners, EventSource status checks, etc.).

---

### Task 1: Create Shared Types

**Files:**
- Create: `src/types/task.ts`

**Interfaces:**
- Consumes: None
- Produces: `Task` interface, `SaveMode` and `ConflictPolicy` types.

- [ ] **Step 1: Write type definitions**

Create `src/types/task.ts` with the following content:
```typescript
export interface Task {
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

export type SaveMode = 'same-dir' | 'custom-dir';
export type ConflictPolicy = 'overwrite' | 'rename';
```

- [ ] **Step 2: Run verification**

Run: `npx vue-tsc --noEmit`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/types/task.ts
git commit -m "refactor: create src/types/task.ts"
```

---

### Task 2: Create API Service Layer

**Files:**
- Create: `src/services/api.ts`

**Interfaces:**
- Consumes: `src/types/task.ts`
- Produces: `scanFilesApi`, `processTaskApi`, `getTaskStatusApi` functions and `getEventSourceUrl` helper.

- [ ] **Step 1: Write API client code**

Create `src/services/api.ts` with the following content:
```typescript
import { ConflictPolicy } from '../types/task';

const API_URL = 'http://127.0.0.1:8000';

export async function scanFilesApi(paths: string[]): Promise<Record<string, string>> {
  const response = await fetch(`${API_URL}/scan`, {
    method: 'POST',
    body: JSON.stringify({ file_paths: paths }),
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok) throw new Error(`Scan failed: ${response.status}`);
  return response.json();
}

export async function processTaskApi(payload: {
  input_path: string;
  output_dir: string;
  conflict_policy: ConflictPolicy;
}): Promise<{ task_id: string }> {
  const response = await fetch(`${API_URL}/process`, {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok) throw new Error(`Process start failed: ${response.status}`);
  return response.json();
}

export async function getTaskStatusApi(taskId: string): Promise<{ status: string; message: string }> {
  const response = await fetch(`${API_URL}/status/${taskId}`);
  if (!response.ok) throw new Error(`Get status failed: ${response.status}`);
  return response.json();
}

export function getEventSourceUrl(taskId: string): string {
  return `${API_URL}/stream/${taskId}`;
}
```

- [ ] **Step 2: Run verification**

Run: `npx vue-tsc --noEmit`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/services/api.ts
git commit -m "refactor: create src/services/api.ts"
```

---

### Task 3: Create useSettings Composable

**Files:**
- Create: `src/composables/useSettings.ts`

**Interfaces:**
- Consumes: `src/types/task.ts`
- Produces: `useSettings` composable exposing `saveMode`, `customOutputDir`, `conflictPolicy` refs and `selectCustomOutputDir` method.

- [ ] **Step 1: Write useSettings logic**

Create `src/composables/useSettings.ts` with the following content:
```typescript
import { ref, watch } from 'vue';
import { open } from '@tauri-apps/plugin-dialog';
import { SaveMode, ConflictPolicy } from '../types/task';

export function useSettings() {
  const saveMode = ref<SaveMode>(
    (localStorage.getItem('saveMode') as SaveMode) || 'same-dir'
  );
  const customOutputDir = ref<string>(localStorage.getItem('customOutputDir') || '');
  const conflictPolicy = ref<ConflictPolicy>(
    (localStorage.getItem('conflictPolicy') as ConflictPolicy) || 'overwrite'
  );
  const error = ref('');

  watch(saveMode, (val) => {
    localStorage.setItem('saveMode', val);
  });
  watch(customOutputDir, (val) => {
    localStorage.setItem('customOutputDir', val);
  });
  watch(conflictPolicy, (val) => {
    localStorage.setItem('conflictPolicy', val);
  });

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

  return {
    saveMode,
    customOutputDir,
    conflictPolicy,
    selectCustomOutputDir,
    error,
  };
}
```

- [ ] **Step 2: Run verification**

Run: `npx vue-tsc --noEmit`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/composables/useSettings.ts
git commit -m "refactor: add useSettings composable"
```

---

### Task 4: Create useFileDrop Composable

**Files:**
- Create: `src/composables/useFileDrop.ts`

**Interfaces:**
- Consumes: None
- Produces: `useFileDrop` composable exposing drag states and tauri drag drop event bindings.

- [ ] **Step 1: Write useFileDrop logic**

Create `src/composables/useFileDrop.ts` with the following content:
```typescript
import { ref, onUnmounted } from 'vue';
import { listen } from '@tauri-apps/api/event';

export function useFileDrop() {
  const isDragging = ref(false);
  let dragCounter = 0;
  let unlistenDrop: (() => void) | null = null;
  let unlistenHover: (() => void) | null = null;
  let unlistenCancel: (() => void) | null = null;

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

  function onDrop() {
    dragCounter = 0;
    isDragging.value = false;
  }

  async function setupTauriDropListeners(onFilesDropped: (paths: string[]) => void) {
    try {
      unlistenDrop = await listen('tauri://file-drop', (event: any) => {
        isDragging.value = false;
        dragCounter = 0;

        const droppedPaths = event.payload as string[];
        if (droppedPaths && droppedPaths.length > 0) {
          const pdfPaths = droppedPaths.filter(p => p.toLowerCase().endsWith('.pdf'));
          if (pdfPaths.length > 0) {
            onFilesDropped(pdfPaths);
          }
        }
      });

      unlistenHover = await listen('tauri://file-drop-hover', () => {
        isDragging.value = true;
      });

      unlistenCancel = await listen('tauri://file-drop-cancelled', () => {
        isDragging.value = false;
        dragCounter = 0;
      });
    } catch (e) {
      console.error("Failed to setup drag listeners", e);
    }
  }

  onUnmounted(() => {
    if (unlistenDrop) unlistenDrop();
    if (unlistenHover) unlistenHover();
    if (unlistenCancel) unlistenCancel();
  });

  return {
    isDragging,
    onDragEnter,
    onDragLeave,
    onDrop,
    setupTauriDropListeners,
  };
}
```

- [ ] **Step 2: Run verification**

Run: `npx vue-tsc --noEmit`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/composables/useFileDrop.ts
git commit -m "refactor: add useFileDrop composable"
```

---

### Task 5: Create useTaskProcessor Composable

**Files:**
- Create: `src/composables/useTaskProcessor.ts`

**Interfaces:**
- Consumes: `src/types/task.ts`, `src/services/api.ts`
- Produces: `useTaskProcessor` composable.

- [ ] **Step 1: Write useTaskProcessor logic**

Create `src/composables/useTaskProcessor.ts` with the following content:
```typescript
import { ref, computed, Ref } from 'vue';
import { open } from '@tauri-apps/plugin-dialog';
import { Task, SaveMode, ConflictPolicy } from '../types/task';
import { scanFilesApi, processTaskApi, getTaskStatusApi, getEventSourceUrl } from '../services/api';

export function useTaskProcessor(
  saveMode: Ref<SaveMode>,
  customOutputDir: Ref<string>,
  conflictPolicy: Ref<ConflictPolicy>
) {
  const tasks = ref<Task[]>([]);
  const isGlobalProcessing = ref(false);
  const error = ref('');
  const filterStatus = ref<string[]>([]);

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
        await addTasksFromPaths(selected);
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

      const results = await scanFilesApi(paths);
      clearTimeout(timeoutId);

      tasks.value.forEach(t => {
        if (paths.includes(t.path)) {
          t.category = results[t.path] || 'UNKNOWN';
          t.status = 'idle';
          t.message = '准备就绪';
          t.selected = (t.category === 'TYPE_2' || t.category === 'TYPE_4');
        }
      });
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
            outputDir += task.path.charAt(lastSlash);
          }
        } else {
          outputDir = '.';
        }
      }

      const data = await processTaskApi({
        input_path: task.path,
        output_dir: outputDir,
        conflict_policy: conflictPolicy.value
      });
      task.task_id = data.task_id;

      await new Promise<boolean>((resolve) => {
        let retryCount = 0;
        const maxRetries = 5;

        function connect() {
          const eventSource = new EventSource(getEventSourceUrl(task.task_id!));

          eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.status === 'not_found' && retryCount < maxRetries) {
              return;
            }
            task.status = data.status;
            task.message = data.message;
            task.current_page = data.current_page;
            task.total_pages = data.total_pages;

            if (data.status === 'completed' || data.status === 'error') {
              eventSource.close();
              resolve(data.status === 'completed');
            }
          };

          eventSource.onerror = async () => {
            eventSource.close();

            try {
              const statusData = await getTaskStatusApi(task.task_id!);
              if (statusData.status === 'completed') {
                task.status = 'completed';
                task.message = statusData.message;
                resolve(true);
                return;
              } else if (statusData.status === 'error') {
                task.status = 'error';
                task.message = statusData.message;
                resolve(false);
                return;
              } else if (statusData.status === 'processing') {
                if (retryCount < maxRetries) {
                  retryCount++;
                  task.message = `正在重新连接... (${retryCount}/${maxRetries})`;
                  setTimeout(connect, 1500);
                  return;
                }
              }
            } catch (err) {
              console.error("Error verifying task status during stream failure:", err);
            }

            if (task.status !== 'completed') {
              task.status = 'error';
              task.message = '流中断';
            }
            resolve(false);
          };
        }

        connect();
      });
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

  return {
    tasks,
    isGlobalProcessing,
    error,
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
    toggleFilter
  };
}
```

- [ ] **Step 2: Run verification**

Run: `npx vue-tsc --noEmit`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/composables/useTaskProcessor.ts
git commit -m "refactor: add useTaskProcessor composable"
```

---

### Task 6: Create Presentational Components (Titlebar, EmptyState, Footer)

**Files:**
- Create: `src/components/Titlebar.vue`
- Create: `src/components/EmptyState.vue`
- Create: `src/components/Footer.vue`

**Interfaces:**
- Consumes: None (Titlebar, EmptyState), Vue props/emits (Footer).
- Produces: Rendered Vue components.

- [ ] **Step 1: Write Titlebar.vue**

Create `src/components/Titlebar.vue` with the following content:
```vue
<template>
  <header
    data-tauri-drag-region
    class="h-[30px] flex items-center px-4 border-b border-slate-200/60 bg-white z-50 shrink-0"
  >
    <div class="flex items-center gap-2 pointer-events-none ml-[72px]" data-tauri-drag-region>
      <span class="text-[11px] font-semibold text-slate-700">PDF OCR Cleaner</span>
      <span class="text-[10px] text-slate-400 font-medium tracking-wide">v1.0</span>
    </div>
  </header>
</template>
```

- [ ] **Step 2: Write EmptyState.vue**

Create `src/components/EmptyState.vue` with the following content:
```vue
<template>
  <div class="flex-1 flex flex-col items-center justify-center pointer-events-none animate-in fade-in zoom-in duration-700">
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
</template>
```

- [ ] **Step 3: Write Footer.vue**

Create `src/components/Footer.vue` with the following content:
```vue
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
```

- [ ] **Step 4: Run verification**

Run: `npx vue-tsc --noEmit`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/components/Titlebar.vue src/components/EmptyState.vue src/components/Footer.vue
git commit -m "refactor: add UI components Titlebar, EmptyState, Footer"
```

---

### Task 7: Create Sidebar Component

**Files:**
- Create: `src/components/Sidebar.vue`

**Interfaces:**
- Consumes: `src/types/task.ts`
- Produces: Rendered Vue Sidebar component.

- [ ] **Step 1: Write Sidebar.vue**

Create `src/components/Sidebar.vue` with the following content:
```vue
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
          <p class="text-[10px] text-slate-400 font-medium">PaddleOCR 3.5.0</p>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { Zap, Loader2, FilePlus, Trash2, Clock } from 'lucide-vue-next';
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
```

- [ ] **Step 2: Run verification**

Run: `npx vue-tsc --noEmit`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/components/Sidebar.vue
git commit -m "refactor: add Sidebar component"
```

---

### Task 8: Refactor App.vue & TaskTable.vue Import Path

**Files:**
- Modify: `src/components/TaskTable.vue` (Update Task import)
- Modify: `src/App.vue` (Complete rewrite)

**Interfaces:**
- Consumes: Composables and Components built in Tasks 1-7.
- Produces: Refactored, lean orchestrator app.

- [ ] **Step 1: Update TaskTable.vue imports**

Modify [src/components/TaskTable.vue](file:///Users/wuyax/Downloads/workcopy/pdf-clean/src/components/TaskTable.vue#L116-L133) to import `Task` definition from `../types/task.ts`:
```typescript
import { computed } from 'vue';
import { Task } from '../types/task';
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
  Trash2 
} from 'lucide-vue-next';

const props = defineProps<{
  tasks: Task[];
}>();
```

- [ ] **Step 2: Rewrite App.vue**

Replace the content of `src/App.vue` with the following clean version:
```vue
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
```

- [ ] **Step 3: Run project validation**

Run: `npm run build`
Expected: SUCCESS

- [ ] **Step 4: Commit**

```bash
git add src/App.vue src/components/TaskTable.vue
git commit -m "refactor: simplify App.vue and update TaskTable"
```
