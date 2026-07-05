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
