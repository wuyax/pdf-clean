# 2026-07-05 App.vue 重构设计方案 (App.vue Refactoring Design)

## 1. 背景与现状分析 (Background)

目前 `src/App.vue` 已经超过 600 行。该组件承担了过多相互耦合的职责，包括：
- **布局与页面结构 (UI Structure)**: 自定义标题栏、侧边栏、空状态引导、拖拽遮罩、底部状态栏。
- **配置持久化 (Local Settings)**: 包括保存路径设置、覆盖策略等，并同步至 `localStorage`。
- **拖拽与系统事件 (Drag & Drop Events)**: 对 Tauri 文件拖拽状态进行计数与逻辑监听。
- **异步任务处理器 (Task Queue Processing)**: 后端 API 请求 (`/scan`, `/process`) 以及复杂的 SSE `EventSource` 重连流状态机逻辑。

为了提升代码可维护性、测试性及扩展性，我们计划遵循 **Vue 3 组合式 API (Composition API)** 的最佳实践，对组件进行彻底的关注点分离重构。

---

## 2. 架构设计与职责分离 (Architecture)

我们将应用划分为以下核心层级：
1. **类型层 (`src/types/task.ts`)**: 统一维护数据实体定义。
2. **服务接口层 (`src/services/api.ts`)**: 抽象网络交互 API，对外暴露 Promise 风格或 URL 构造器。
3. **逻辑控制层 (Composables)**: 抽离通用或复杂的业务逻辑状态机，暴露响应式 Refs 和具体操作方法。
4. **展示组件层 (Presentational Components)**: 实现完全依靠 Props 接收数据、Emit 触发操作的纯净 UI 组件。
5. **容器层 (`src/App.vue`)**: 作为编排器，通过组合 Composables 和展示组件，声明式构建整体布局。

---

## 3. 详细设计 (Detailed Specifications)

### 3.1 类型定义 (Types)

新建 [src/types/task.ts](file:///Users/wuyax/Downloads/workcopy/pdf-clean/src/types/task.ts)：

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

### 3.2 接口层设计 (Services)

新建 [src/services/api.ts](file:///Users/wuyax/Downloads/workcopy/pdf-clean/src/services/api.ts)：

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

### 3.3 逻辑控制器设计 (Composables)

#### 3.3.1 `useSettings.ts`
负责持久化状态（保存方式、保存路径和同名替换策略），集成本地存储。

- **返回值**:
  - `saveMode`: `Ref<SaveMode>`
  - `customOutputDir`: `Ref<string>`
  - `conflictPolicy`: `Ref<ConflictPolicy>`
  - `selectCustomOutputDir`: `() => Promise<void>`
  - `error`: `Ref<string>` (用于存储选择文件夹错误等临时异常)

#### 3.3.2 `useFileDrop.ts`
负责 Tauri 原生文件拖拽交互事件的处理。

- **返回值**:
  - `isDragging`: `Ref<boolean>`
  - `setupTauriDropListeners`: `(onFilesDropped: (paths: string[]) => void) => () => void` (返回一个用于注销事件监听的 cleanup 函数)

#### 3.3.3 `useTaskProcessor.ts`
负责批量任务流逻辑和重试机制（通过 fetch API 和 Server-Sent Events 连接）。

- **参数**: 
  - `saveMode`: `Ref<SaveMode>`
  - `customOutputDir`: `Ref<string>`
  - `conflictPolicy`: `Ref<ConflictPolicy>`
- **返回值**:
  - `tasks`: `Ref<Task[]>`
  - `isGlobalProcessing`: `Ref<boolean>`
  - `error`: `Ref<string>`
  - `filterStatus`: `Ref<string[]>`
  - `filteredTasks`: `ComputedRef<Task[]>`
  - `totalSelectedTaskCount`: `ComputedRef<number>`
  - `completedTaskCount`: `ComputedRef<number>`
  - `globalProgress`: `ComputedRef<number>`
  - `hasSelectedTasks`: `ComputedRef<boolean>`
  - `addTasksFromPaths`: `(paths: string[]) => Promise<void>`
  - `selectFiles`: `() => Promise<void>`
  - `startBatchProcessing`: `() => Promise<void>`
  - `removeTask`: `(path: string) => void`
  - `clearAll`: `() => void`
  - `toggleAll`: `() => void`
  - `toggleFilter`: `(status: string) => void`

### 3.4 展示组件设计 (Components)

我们将提取以下 UI 展示型组件：

- [src/components/Titlebar.vue](file:///Users/wuyax/Downloads/workcopy/pdf-clean/src/components/Titlebar.vue): 标题栏展示。
- [src/components/EmptyState.vue](file:///Users/wuyax/Downloads/workcopy/pdf-clean/src/components/EmptyState.vue): 拖拽空白引导图。
- [src/components/Footer.vue](file:///Users/wuyax/Downloads/workcopy/pdf-clean/src/components/Footer.vue): 底部统计与错误展示栏。
  - **Props**: `tasksCount: number`, `error: string`
- [src/components/Sidebar.vue](file:///Users/wuyax/Downloads/workcopy/pdf-clean/src/components/Sidebar.vue): 侧边设置和操作区。
  - **Props**:
    - `isGlobalProcessing`: `boolean`
    - `hasSelectedTasks`: `boolean`
    - `saveMode`: `SaveMode`
    - `customOutputDir`: `string`
    - `conflictPolicy`: `ConflictPolicy`
    - `filterStatus`: `string[]`
    - `tasksCount`: `number`
    - `processingCount`: `number`
    - `pendingCount`: `number`
    - `completedTaskCount`: `number`
    - `totalSelectedTaskCount`: `number`
    - `globalProgress`: `number`
  - **Emits**:
    - `update:saveMode`: `(val: SaveMode) => void`
    - `update:customOutputDir`: `(val: string) => void`
    - `update:conflictPolicy`: `(val: ConflictPolicy) => void`
    - `start-processing`
    - `select-files`
    - `clear-all`
    - `select-custom-dir`
    - `toggle-filter`: `(status: string) => void`

---

## 4. 迁移与测试策略 (Migration & Verification)

### 4.1 实施路径
1. 创建 `src/types/task.ts`。
2. 创建 `src/services/api.ts`。
3. 实现 Composables 并运行 TypeScript 检查确保参数类型匹配。
4. 实现展示组件并运行编译检查。
5. 精简 `src/App.vue`。
6. 运行类型检查与生成构建文件确认无 Regression。

### 4.2 验证指标 (Success Criteria)
- `vue-tsc --noEmit && vite build` 编译成功。
- 新组件和 Composable 符合 TypeScript 强类型。
- 原有的所有业务流程保持不变：
  - 支持本地配置从 localStorage 正确读取并写入。
  - 支持通过拖拽或文件选择对话框导入 PDF。
  - 导入后自动发起 scan（扫描分类）。
  - 开始清理能按队列批处理，显示进度，建立 EventSource连接获取进度 stream。
  - 支持发生中断时，使用 status 接口回退查询与最多 5 次连接自动恢复逻辑。
