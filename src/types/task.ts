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
  outputPath?: string;
}

export type SaveMode = 'same-dir' | 'custom-dir';
export type ConflictPolicy = 'overwrite' | 'rename';
