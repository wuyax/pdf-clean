import { invoke } from '@tauri-apps/api/core';

export async function scanFilesApi(paths: string[]): Promise<Record<string, string>> {
  return await invoke('scan_files', { paths });
}

export async function processTaskApi(payload: {
  input_path: string;
  output_dir: string;
  conflict_policy: string;
  task_id: string;
}): Promise<void> {
  await invoke('process_task', {
    inputPath: payload.input_path,
    outputDir: payload.output_dir,
    conflictPolicy: payload.conflict_policy,
    taskId: payload.task_id
  });
}

