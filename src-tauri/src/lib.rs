pub mod state;
pub mod sidecar;
pub mod commands;
pub mod config;

use std::sync::{Arc, Mutex};
use std::collections::HashMap;
use tokio::sync::Semaphore;
use tauri::{Manager, TitleBarStyle};
use state::AppState;

pub fn run() {
    let config = config::AppConfig::load();
    let limit = config.ocr_concurrency_limit;

    let state = AppState {
        semaphore: Arc::new(Semaphore::new(limit)),
        active_tasks: Mutex::new(HashMap::new()),
        config,
    };

    tauri::Builder::default()
        .manage(state)
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .invoke_handler(tauri::generate_handler![
            commands::scan_files,
            commands::process_task,
            commands::abort_task
        ])
        .setup(|app| {
            // 获取主窗口
            let main_window = app.get_webview_window("main").unwrap();

            // 针对 macOS 的底层强制设置
            #[cfg(target_os = "macos")]
            {
                main_window.set_title_bar_style(TitleBarStyle::Overlay).ok();
                main_window.set_title("").ok();
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_concurrency_semaphore() {
        let semaphore = Arc::new(Semaphore::new(2));
        let p1 = semaphore.clone().acquire_owned().await.unwrap();
        let _p2 = semaphore.clone().acquire_owned().await.unwrap();
        
        let p3_try = tokio::time::timeout(
            std::time::Duration::from_millis(50),
            semaphore.clone().acquire_owned()
        ).await;
        assert!(p3_try.is_err());
        
        drop(p1);
        let p3 = tokio::time::timeout(
            std::time::Duration::from_millis(50),
            semaphore.clone().acquire_owned()
        ).await;
        assert!(p3.is_ok());
    }
}
