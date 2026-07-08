use serde::{Deserialize, Serialize};
#[cfg(debug_assertions)]
use std::io::{BufRead, BufReader};
use std::sync::Arc;
use tauri::{AppHandle, Emitter, Manager, TitleBarStyle};
use tokio::sync::Semaphore;

struct AppState {
    semaphore: Arc<Semaphore>,
}


#[derive(Debug, Serialize, Deserialize, Clone)]
struct ProgressPayload {
    r#type: String,
    task_id: String,
    status: String,
    message: String,
    current_page: usize,
    total_pages: usize,
    output_path: Option<String>,
}

#[tauri::command]
async fn scan_files(paths: Vec<String>, app: AppHandle) -> Result<serde_json::Value, String> {
    let mut args = vec!["scan".to_string()];
    args.extend(paths);

    #[cfg(debug_assertions)]
    {
        let _ = app;
        let python_bin = if cfg!(target_os = "windows") {
            "../python-sidecar/venv/Scripts/python.exe"
        } else {
            "../python-sidecar/venv/bin/python"
        };
        let script_path = "../python-sidecar/src/main.py";
        let mut cmd = std::process::Command::new(python_bin);
        cmd.arg(script_path)
           .args(args)
           .stdout(std::process::Stdio::piped())
           .stderr(std::process::Stdio::inherit());

        #[cfg(target_os = "windows")]
        {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
        }

        let mut child = cmd.spawn().map_err(|e| format!("Failed to spawn python venv: {}", e))?;
        let stdout = child.stdout.take().ok_or("Failed to open stdout")?;
        let reader = BufReader::new(stdout);
        let mut results = None;

        for line in reader.lines() {
            if let Ok(line_str) = line {
                if let Ok(val) = serde_json::from_str::<serde_json::Value>(&line_str) {
                    if val["type"] == "scan_result" {
                        results = Some(val["results"].clone());
                        break;
                    }
                }
            }
        }
        let _ = child.kill();
        let _ = child.wait();
        results.ok_or_else(|| "Failed to get scan results".to_string())
    }

    #[cfg(not(debug_assertions))]
    {
        use tauri_plugin_shell::ShellExt;
        use tauri_plugin_shell::process::CommandEvent;

        let ocr_models_dir = app.path()
            .resolve("resources/ocr_models", tauri::path::BaseDirectory::Resource)
            .map_err(|e| e.to_string())?;
        let ocr_models_str = ocr_models_dir.to_string_lossy().to_string();

        let (mut rx, child) = app.shell()
            .sidecar("python-sidecar")
            .map_err(|e| e.to_string())?
            .args(args)
            .env("MODEL_DIR", &ocr_models_str)
            .spawn()
            .map_err(|e| e.to_string())?;

        let mut results = None;
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    let line_str = String::from_utf8_lossy(&line);
                    if let Ok(val) = serde_json::from_str::<serde_json::Value>(&line_str) {
                        if val["type"] == "scan_result" {
                            results = Some(val["results"].clone());
                            break;
                        }
                    }
                }
                CommandEvent::Stderr(line) => {
                    eprintln!("[Sidecar Stderr] {}", String::from_utf8_lossy(&line).trim_end());
                }
                CommandEvent::Terminated(_) => break,
                _ => {}
            }
        }
        let _ = child.kill();
        results.ok_or_else(|| "Failed to get scan results from sidecar".to_string())
    }
}

#[tauri::command]
async fn process_task(
    input_path: String,
    output_dir: String,
    conflict_policy: String,
    task_id: String,
    app: AppHandle,
) -> Result<(), String> {
    let state = app.state::<AppState>();
    let permit = state.semaphore.clone().acquire_owned().await.map_err(|e| e.to_string())?;

    let args = vec![
        "process".to_string(),
        "--input".to_string(),
        input_path,
        "--output-dir".to_string(),
        output_dir,
        "--conflict".to_string(),
        conflict_policy,
        "--task-id".to_string(),
        task_id.clone(),
    ];

    #[cfg(debug_assertions)]
    {
        let _ = app;
        std::thread::spawn(move || {
            let _permit_holder = permit;
            let python_bin = if cfg!(target_os = "windows") {
                "../python-sidecar/venv/Scripts/python.exe"
            } else {
                "../python-sidecar/venv/bin/python"
            };
            let script_path = "../python-sidecar/src/main.py";
            let mut cmd = std::process::Command::new(python_bin);
            cmd.arg(script_path)
               .args(args)
               .stdout(std::process::Stdio::piped())
               .stderr(std::process::Stdio::inherit());

            #[cfg(target_os = "windows")]
            {
                use std::os::windows::process::CommandExt;
                cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
            }

            let mut child = match cmd.spawn() {
                Ok(c) => c,
                Err(e) => {
                    let payload = ProgressPayload {
                        r#type: "progress".to_string(),
                        task_id: task_id.clone(),
                        status: "error".to_string(),
                        message: format!("启动失败: {}", e),
                        current_page: 0,
                        total_pages: 0,
                        output_path: None,
                    };
                    let _ = app.emit("ocr-progress", payload);
                    return;
                }
            };

            let stdout = child.stdout.take().expect("Failed to open stdout");
            let reader = BufReader::new(stdout);
            let mut status_emitted = false;

            for line in reader.lines() {
                if let Ok(line_str) = line {
                    if let Ok(val) = serde_json::from_str::<serde_json::Value>(&line_str) {
                        let type_str = val["type"].as_str().unwrap_or("");
                        let status = match type_str {
                            "progress" => "processing",
                            "completed" => {
                                status_emitted = true;
                                "completed"
                            }
                            _ => {
                                status_emitted = true;
                                "error"
                            }
                        };
                        
                        let payload = ProgressPayload {
                            r#type: "progress".to_string(),
                            task_id: task_id.clone(),
                            status: status.to_string(),
                            message: val["message"].as_str().unwrap_or("").to_string(),
                            current_page: val["current_page"].as_u64().unwrap_or(0) as usize,
                            total_pages: val["total_pages"].as_u64().unwrap_or(0) as usize,
                            output_path: val["output_path"].as_str().map(|s| s.to_string()),
                        };
                        let _ = app.emit("ocr-progress", payload);
                    }
                }
            }

            if !status_emitted {
                let payload = ProgressPayload {
                    r#type: "progress".to_string(),
                    task_id: task_id.clone(),
                    status: "error".to_string(),
                    message: "进程意外终止".to_string(),
                    current_page: 0,
                    total_pages: 0,
                    output_path: None,
                };
                let _ = app.emit("ocr-progress", payload);
            }

            let _ = child.kill();
            let _ = child.wait();
        });
    }

    #[cfg(not(debug_assertions))]
    {
        tauri::async_runtime::spawn(async move {
            let _permit_holder = permit;
            use tauri_plugin_shell::ShellExt;
            use tauri_plugin_shell::process::CommandEvent;

            let ocr_models_dir = match app.path().resolve("resources/ocr_models", tauri::path::BaseDirectory::Resource) {
                Ok(dir) => dir,
                Err(e) => {
                    let payload = ProgressPayload {
                        r#type: "progress".to_string(),
                        task_id: task_id.clone(),
                        status: "error".to_string(),
                        message: format!("获取模型目录失败: {}", e),
                        current_page: 0,
                        total_pages: 0,
                        output_path: None,
                    };
                    let _ = app.emit("ocr-progress", payload);
                    return;
                }
            };
            let ocr_models_str = ocr_models_dir.to_string_lossy().to_string();

            let sidecar_res = app.shell()
                .sidecar("python-sidecar")
                .map_err(|e| e.to_string());
            
            let command = match sidecar_res {
                Ok(cmd) => cmd,
                Err(e) => {
                    let payload = ProgressPayload {
                        r#type: "progress".to_string(),
                        task_id: task_id.clone(),
                        status: "error".to_string(),
                        message: format!("获取 Sidecar 失败: {}", e),
                        current_page: 0,
                        total_pages: 0,
                        output_path: None,
                    };
                    let _ = app.emit("ocr-progress", payload);
                    return;
                }
            };

            let spawn_res = command
                .args(args)
                .env("MODEL_DIR", &ocr_models_str)
                .spawn();

            let (mut rx, child) = match spawn_res {
                Ok(val) => val,
                Err(e) => {
                    let payload = ProgressPayload {
                        r#type: "progress".to_string(),
                        task_id: task_id.clone(),
                        status: "error".to_string(),
                        message: format!("启动 Sidecar 失败: {}", e),
                        current_page: 0,
                        total_pages: 0,
                        output_path: None,
                    };
                    let _ = app.emit("ocr-progress", payload);
                    return;
                }
            };

            let mut status_emitted = false;

            while let Some(event) = rx.recv().await {
                match event {
                    CommandEvent::Stdout(line) => {
                        let line_str = String::from_utf8_lossy(&line);
                        if let Ok(val) = serde_json::from_str::<serde_json::Value>(&line_str) {
                            let type_str = val["type"].as_str().unwrap_or("");
                            let status = match type_str {
                                "progress" => "processing",
                                "completed" => {
                                    status_emitted = true;
                                    "completed"
                                }
                                _ => {
                                    status_emitted = true;
                                    "error"
                                }
                            };
                            
                            let payload = ProgressPayload {
                                r#type: "progress".to_string(),
                                task_id: task_id.clone(),
                                status: status.to_string(),
                                message: val["message"].as_str().unwrap_or("").to_string(),
                                current_page: val["current_page"].as_u64().unwrap_or(0) as usize,
                                total_pages: val["total_pages"].as_u64().unwrap_or(0) as usize,
                                output_path: val["output_path"].as_str().map(|s| s.to_string()),
                            };
                            let _ = app.emit("ocr-progress", payload);
                        }
                    }
                    CommandEvent::Stderr(line) => {
                        eprintln!("[Sidecar Stderr] {}", String::from_utf8_lossy(&line).trim_end());
                    }
                    CommandEvent::Terminated(term_payload) => {
                        if !status_emitted {
                            let msg = match term_payload.code {
                                Some(code) => format!("进程意外终止，退出码: {}", code),
                                None => "进程意外终止".to_string(),
                            };
                            let payload = ProgressPayload {
                                r#type: "progress".to_string(),
                                task_id: task_id.clone(),
                                status: "error".to_string(),
                                message: msg,
                                current_page: 0,
                                total_pages: 0,
                                output_path: None,
                            };
                            let _ = app.emit("ocr-progress", payload);
                            status_emitted = true;
                        }
                        break;
                    }
                    _ => {}
                }
            }

            if !status_emitted {
                let payload = ProgressPayload {
                    r#type: "progress".to_string(),
                    task_id: task_id.clone(),
                    status: "error".to_string(),
                    message: "进程意外终止".to_string(),
                    current_page: 0,
                    total_pages: 0,
                    output_path: None,
                };
                let _ = app.emit("ocr-progress", payload);
            }
            let _ = child.kill();
        });
    }

    Ok(())
}

pub fn run() {
    let state = AppState {
        semaphore: Arc::new(Semaphore::new(2)), // Limit to max 2 concurrent OCR tasks
    };

    tauri::Builder::default()
        .manage(state)
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .invoke_handler(tauri::generate_handler![scan_files, process_task])
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

