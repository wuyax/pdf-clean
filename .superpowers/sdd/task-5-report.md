# Task 5 Report: Create useTaskProcessor Composable

## Implementation Details
We created the core task processing and backend-communication composable at `src/composables/useTaskProcessor.ts`. It extracts all the batch processing, file selection, scanning, and Server-Sent Events (SSE) streaming logic from `App.vue` into a reusable, stateful composition function:
- **Exposing State**:
  - `tasks`: A reactive ref array of `Task` objects representing loaded files.
  - `isGlobalProcessing`: A boolean ref flag tracking if batch cleaning is currently running.
  - `error`: A string ref storing current global errors.
  - `filterStatus`: An array ref representing selected status filters ('processing', 'pending').
- **Computed Properties**:
  - `filteredTasks`: Returns list of tasks matching the current status filter.
  - `totalSelectedTaskCount`: Count of selected tasks.
  - `completedTaskCount`: Count of completed tasks.
  - `globalProgress`: Calculated percentage progress of completed tasks vs. selected tasks.
  - `hasSelectedTasks`: Checks if any task is selected and not yet completed.
- **Operations & Navigation**:
  - `toggleFilter(status)`: Modifies current status filter state.
  - `addTasksFromPaths(paths)`: Initializes tasks with path and filename, and triggers an initial scan.
  - `selectFiles()`: Opens a Tauri system file dialog to choose `.pdf` files.
  - `scanFiles(targetTasks)`: Sends selected paths to the backend `/scan` API with a 60-second abort timeout, updating categories and selecting TYPE_2 and TYPE_4 categories by default.
  - `startBatchProcessing()`: Sequentially runs `processSingleTask` for each selected pending task.
  - `processSingleTask(task)`: Initiates output directory detection, calls the backend `/process` API, retrieves a `task_id`, and initiates a SSE stream connection via `EventSource`. Resolves only upon completion, error, or fallback checking via `/status/<task_id>` when a stream failure occurs.
  - `removeTask(path)`, `clearAll()`, and `toggleAll()`: Helper utilities for task list control.

## Verification and Testing
We verified the code against static type checking and ran python backend tests:
- **TypeScript Static Verification**:
  - Command: `npx vue-tsc --noEmit`
  - Result: PASS (No compilation errors)
- **Backend Test Suite (python-sidecar)**:
  - Command: `. venv/bin/activate && pytest`
  - Result: PASS (15 passed, 0 failed)

No unit testing framework is currently configured for the frontend codebase. Verify compile checks were clean.

## Files Changed
- [useTaskProcessor.ts](file:///Users/wuyax/Downloads/workcopy/pdf-clean/src/composables/useTaskProcessor.ts) (Modified)
- [api.ts](file:///Users/wuyax/Downloads/workcopy/pdf-clean/src/services/api.ts) (Modified)

## Fixes Applied
- **AbortController Signal Passing**:
  - Updated `scanFilesApi` in [api.ts](file:///Users/wuyax/Downloads/workcopy/pdf-clean/src/services/api.ts) to accept an optional `signal?: AbortSignal` and passed it to the `fetch` options.
  - Passed `controller.signal` to `scanFilesApi` in [useTaskProcessor.ts](file:///Users/wuyax/Downloads/workcopy/pdf-clean/src/composables/useTaskProcessor.ts) to enforce the 60-second scanning timeout.
- **Task Removal Prevention**:
  - Updated `removeTask` in [useTaskProcessor.ts](file:///Users/wuyax/Downloads/workcopy/pdf-clean/src/composables/useTaskProcessor.ts) to prevent removal of tasks currently in `'processing'` status.

## Self-Review Findings
- **Completeness**: Fully implemented the `useTaskProcessor` composable as specified by the brief, and fixed the reviewed issues.
- **Quality**: Verified directory resolution and EventSource onerror retry and fallback status checks are structurally correct and type-safe.
- **Discipline**: Followed exact implementation constraints. App.vue was left untouched because refactoring it is allocated to Task 8.

## Issues or Concerns
None. The code compiled successfully via `npx vue-tsc --noEmit`.
