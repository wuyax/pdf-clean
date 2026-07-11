use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use tokio::sync::Semaphore;

pub struct AppState {
    pub semaphore: Arc<Semaphore>,
    pub active_tasks: Mutex<HashMap<String, tokio::sync::oneshot::Sender<()>>>,
}
