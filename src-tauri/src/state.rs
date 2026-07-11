use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use tokio::sync::Semaphore;
use tauri::AppHandle;
use tauri::Manager;

pub struct AppState {
    pub semaphore: Arc<Semaphore>,
    pub active_tasks: Mutex<HashMap<String, tokio::sync::oneshot::Sender<()>>>,
    pub config: crate::config::AppConfig,
    pub daemon: tokio::sync::Mutex<Option<(crate::sidecar::SidecarSession, tokio::sync::mpsc::Receiver<crate::sidecar::SidecarOutputEvent>)>>,
}

pub struct TaskCleanupGuard {
    pub app: AppHandle,
    pub task_id: String,
}

impl Drop for TaskCleanupGuard {
    fn drop(&mut self) {
        if let Ok(mut tasks) = self.app.state::<AppState>().active_tasks.lock() {
            tasks.remove(&self.task_id);
        } else {
            eprintln!("Failed to acquire active_tasks lock during cleanup (poisoned)");
        }
    }
}
