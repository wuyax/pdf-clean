# Lucide 图标集成实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用 `lucide-vue-next` 图标库替换现有的硬编码 SVG，增强 UI 的语义化引导和交互感。

**Architecture:** 采用按需引入（named imports）的方式集成 Lucide 图标，确保打包体积优化。通过在 Vue 组件中声明式使用图标组件，提升代码可读性。

**Tech Stack:** Vue 3, Tailwind CSS, lucide-vue-next, Vite

---

### Task 1: 基础设施配置

**Files:**
- Modify: `package.json`

- [ ] **Step 1: 安装依赖**

执行命令安装 `lucide-vue-next`:
```bash
npm install lucide-vue-next
```

- [ ] **Step 2: 验证安装**

确认 `package.json` 中已包含 `lucide-vue-next`。

- [ ] **Step 3: 提交**

```bash
git add package.json package-lock.json
git commit -m "chore: install lucide-vue-next"
```

---

### Task 2: 优化 App.vue 侧边栏与状态栏

**Files:**
- Modify: `src/App.vue`

- [ ] **Step 1: 引入图标组件**

在 `<script setup>` 中引入所需图标：
```typescript
import { 
  Zap, 
  FilePlus, 
  Trash2, 
  Loader2, 
  Clock, 
  AlertCircle 
} from 'lucide-vue-next';
```

- [ ] **Step 2: 替换“开始清理”按钮图标**

将原有的 `<svg>` 替换为 `<Zap class="w-4 h-4" :stroke-width="2.5" />`。

- [ ] **Step 3: 为“添加文件”和“清空列表”增加图标**

- 添加文件：增加 `<FilePlus class="w-3.5 h-3.5" />`
- 清空列表：增加 `<Trash2 class="w-3.5 h-3.5" />`

- [ ] **Step 4: 替换过滤器状态图标**

- 处理中：使用 `<Loader2 class="w-3.5 h-3.5 animate-spin" />`
- 待处理：使用 `<Clock class="w-3.5 h-3.5" />`

- [ ] **Step 5: 替换状态栏错误图标**

使用 `<AlertCircle class="w-3 h-3" />`。

- [ ] **Step 6: 提交**

```bash
git add src/App.vue
git commit -m "ui: integrate lucide icons in App.vue"
```

---

### Task 3: 优化 TaskTable.vue 任务列表

**Files:**
- Modify: `src/components/TaskTable.vue`

- [ ] **Step 1: 引入图标组件**

在 `<script setup>` 中引入所需图标：
```typescript
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
  X,
  Trash2
} from 'lucide-vue-next';
```

- [ ] **Step 2: 替换表头图标**

在“文件名”旁增加 `<Files class="w-3.5 h-3.5 inline-block mr-1 opacity-60" />`。

- [ ] **Step 3: 动态渲染分类图标**

根据 `task.category` 渲染对应图标。

- [ ] **Step 4: 替换处理状态图标**

- 已完成：`<CheckCircle2 class="w-3.5 h-3.5" />`
- 错误：`<AlertCircle class="w-3.5 h-3.5" />`
- 扫描中：`<RefreshCw class="w-3 h-3 animate-spin" />`

- [ ] **Step 5: 替换删除按钮图标**

使用 `<Trash2 class="w-4 h-4" />`。

- [ ] **Step 6: 提交**

```bash
git add src/components/TaskTable.vue
git commit -m "ui: integrate lucide icons in TaskTable.vue"
```

---

### Task 4: 最终验证

- [ ] **Step 1: 运行开发服务器**

```bash
npm run dev
```

- [ ] **Step 2: 手动检查 UI**

1. 检查侧边栏按钮和过滤器图标是否正常显示。
2. 检查任务列表表头、分类图标、状态图标是否正常显示。
3. 检查动画（旋转）是否生效。
