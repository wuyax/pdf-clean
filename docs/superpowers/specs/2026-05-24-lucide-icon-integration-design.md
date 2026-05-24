# 2026-05-24 Lucide 图标集成设计方案

## 1. 目标
通过引入 `lucide-vue-next` 图标库，替换现有的硬编码 SVG 代码，提升代码可维护性，并增强 UI 的视觉语义引导。

## 2. 核心变更
### 2.1 基础设施
- 安装 `lucide-vue-next` 依赖。
- 在 Vue 组件中按需引入图标。

### 2.2 侧边栏 (App.vue)
- **主动作 (开始清理):** 使用 `Zap` 图标。
- **添加文件:** 使用 `FilePlus` 图标。
- **清空列表:** 使用 `Trash2` 图标。
- **状态过滤器:**
  - `处理中`: `Loader2` 图标（添加旋转动画）。
  - `待处理`: `Clock` 图标。

### 2.3 任务列表 (TaskTable.vue)
- **表头 (文件名):** 使用 `Files` 图标。
- **分类语义化:**
  - `TYPE_1` (文本): `FileText` (蓝色)
  - `TYPE_2` (干扰): `FileX` (琥珀色)
  - `TYPE_3` (OCR): `ScanText` (蓝色)
  - `TYPE_4` (全图): `FileImage` (琥珀色)
  - `NOT_FOUND`: `FileWarning` (灰色)
- **处理状态:**
  - `已完成`: `CheckCircle2` (绿色)
  - `错误`: `AlertCircle` (红色)
  - `扫描中`: `RefreshCw` (旋转动画)
- **行操作 (删除):** 使用 `X` 或 `Trash` 图标。

### 2.4 状态栏 (App.vue)
- **错误提示:** 使用 `AlertCircle`。

## 3. 技术规范
- **图标尺寸:** 侧边栏按钮使用 `16px` (w-4 h-4)，列表状态使用 `14px` (w-3.5 h-3.5)。
- **描边宽度:** 统一使用 `2.5px` 或 `2px` 以匹配当前精细的 UI 风格。
- **动画:** 
  - `Loader2` 使用 Tailwind `animate-spin`。
  - `RefreshCw` 使用自定义或内置旋转。

## 4. 成功标准
- 所有原生 `<svg>` 标签被 Lucide 组件替换。
- UI 交互感增强，不同 PDF 类型能通过图标快速区分。
- 打包体积保持优化（通过按需引入）。
