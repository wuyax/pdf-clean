use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Emitter, Manager, TitleBarStyle};
use tokio::sync::Semaphore;

struct AppState {
    semaphore: Arc<Semaphore>,
    active_tasks: Mutex<HashMap<String, tokio::sync::oneshot::Sender<()>>>,
}

#[derive(Debug, Clone)]
enum SidecarOutputEvent {
    Stdout(String),
    Stderr(String),
    Terminated(Option<i32>),
}

struct SidecarSession {
    kill_tx: Option<tokio::sync::oneshot::Sender<()>>,
}

impl SidecarSession {
    pub fn kill(&mut self) {
        if let Some(tx) = self.kill_tx.take() {
            let _ = tx.send(());
        }
    }
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

fn spawn_sidecar(
    app: &AppHandle,
    args: Vec<String>,
) -> Result<(SidecarSession, tokio::sync::mpsc::Receiver<SidecarOutputEvent>), String> {
    let (tx, rx) = tokio::sync::mpsc::channel::<SidecarOutputEvent>(100);
    let (kill_tx, kill_rx) = tokio::sync::oneshot::channel::<()>();

    let ocr_models_dir = app.path()
        .resolve("resources/ocr_models", tauri::path::BaseDirectory::Resource)
        .map_err(|e| e.to_string())?;
    let ocr_models_str = ocr_models_dir.to_string_lossy().to_string();

    #[cfg(debug_assertions)]
    {
        let python_bin = if cfg!(target_os = "windows") {
            "../python-sidecar/venv/Scripts/python.exe"
        } else {
            "../python-sidecar/venv/bin/python"
        };
        let script_path = "../python-sidecar/src/main.py";
        let mut cmd = tokio::process::Command::new(python_bin);
        cmd.arg(script_path)
           .args(args)
           .env("MODEL_DIR", &ocr_models_str)
           .stdout(std::process::Stdio::piped())
           .stderr(std::process::Stdio::piped());
        cmd.kill_on_drop(true);

        #[cfg(target_os = "windows")]
        {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x08000000);
        }

        let mut child = cmd.spawn().map_err(|e| format!("Failed to spawn python venv: {}", e))?;
        let stdout = child.stdout.take().ok_or("Failed to open stdout")?;
        let stderr = child.stderr.take().ok_or("Failed to open stderr")?;

        let tx_out = tx.clone();
        tauri::async_runtime::spawn(async move {
            use tokio::io::AsyncBufReadExt;
            let mut reader = tokio::io::BufReader::new(stdout);
            let mut line = String::new();
            while reader.read_line(&mut line).await.is_ok() {
                if line.is_empty() { break; }
                let _ = tx_out.send(SidecarOutputEvent::Stdout(line.clone())).await;
                line.clear();
            }
        });

        let tx_err = tx.clone();
        tauri::async_runtime::spawn(async move {
            use tokio::io::AsyncBufReadExt;
            let mut reader = tokio::io::BufReader::new(stderr);
            let mut line = String::new();
            while reader.read_line(&mut line).await.is_ok() {
                if line.is_empty() { break; }
                let _ = tx_err.send(SidecarOutputEvent::Stderr(line.trim_end().to_string())).await;
                line.clear();
            }
        });

        tauri::async_runtime::spawn(async move {
            tokio::select! {
                _ = kill_rx => {
                    let _ = child.kill().await;
                    let _ = child.wait().await;
                }
                status = child.wait() => {
                    let code = status.ok().and_then(|s| s.code());
                    let _ = tx.send(SidecarOutputEvent::Terminated(code)).await;
                }
            }
        });
    }

    #[cfg(not(debug_assertions))]
    {
        use tauri_plugin_shell::ShellExt;
        use tauri_plugin_shell::process::CommandEvent;

        let (mut rx_events, child) = app.shell()
            .sidecar("python-sidecar")
            .map_err(|e| e.to_string())?
            .args(args)
            .env("MODEL_DIR", &ocr_models_str)
            .spawn()
            .map_err(|e| e.to_string())?;

        let mut child_opt = Some(child);
        let tx_clone = tx.clone();
        
        tauri::async_runtime::spawn(async move {
            tokio::select! {
                _ = kill_rx => {
                    if let Some(c) = child_opt.take() {
                        let _ = c.kill();
                    }
                }
                _ = async {
                    while let Some(event) = rx_events.recv().await {
                        match event {
                            CommandEvent::Stdout(line) => {
                                let line_str = String::from_utf8_lossy(&line).into_owned();
                                let _ = tx_clone.send(SidecarOutputEvent::Stdout(line_str)).await;
                            }
                            CommandEvent::Stderr(line) => {
                                let line_str = String::from_utf8_lossy(&line).trim_end().to_string();
                                let _ = tx_clone.send(SidecarOutputEvent::Stderr(line_str)).await;
                            }
                            CommandEvent::Terminated(term_payload) => {
                                let _ = tx_clone.send(SidecarOutputEvent::Terminated(term_payload.code)).await;
                                break;
                            }
                            _ => {}
                        }
                    }
                } => {}
            }
            if let Some(c) = child_opt.take() {
                let _ = c.kill();
            }
        });
    }

    Ok((SidecarSession { kill_tx: Some(kill_tx) }, rx))
}

#[tauri::command]
async fn scan_files(paths: Vec<String>, app: AppHandle) -> Result<serde_json::Value, String> {
    let mut args = vec!["scan".to_string()];
    args.extend(paths);

    let (mut session, mut rx) = spawn_sidecar(&app, args)?;
    let run_fut = async {
        let mut results = None;
        while let Some(event) = rx.recv().await {
            match event {
                SidecarOutputEvent::Stdout(line_str) => {
                    if let Ok(val) = serde_json::from_str::<serde_json::Value>(&line_str) {
                        if val["type"] == "scan_result" {
                            results = Some(val["results"].clone());
                            break;
                        }
                    }
                }
                SidecarOutputEvent::Terminated(_) => break,
                _ => {}
            }
        }
        results
    };

    let results = match tokio::time::timeout(std::time::Duration::from_secs(30), run_fut).await {
        Ok(res) => res,
        Err(_) => {
            session.kill();
            return Err("Scan timeout after 30 seconds".to_string());
        }
    };
    session.kill();
    results.ok_or_else(|| "Failed to get scan results".to_string())
}

#[tauri::command]
async fn process_task(
    input_path: String,
    output_dir: String,
    conflict_policy: String,
    task_id: String,
    dpi: u32,
    quality: u8,
    app: AppHandle,
) -> Result<(), String> {
    let state = app.state::<AppState>();
    let semaphore = state.semaphore.clone();
    let (abort_tx, mut abort_rx) = tokio::sync::oneshot::channel::<()>();
    if let Ok(mut tasks) = state.active_tasks.lock() {
        tasks.insert(task_id.clone(), abort_tx);
    }

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
        "--dpi".to_string(),
        dpi.to_string(),
        "--quality".to_string(),
        quality.to_string(),
    ];

    #[allow(clippy::redundant_clone)]
    let app_clone = app.clone();
    tauri::async_runtime::spawn(async move {
        let permit = tokio::select! {
            res = semaphore.acquire_owned() => {
                match res {
                    Ok(p) => p,
                    Err(e) => {
                        let payload = ProgressPayload {
                            r#type: "progress".to_string(),
                            task_id: task_id.clone(),
                            status: "error".to_string(),
                            message: format!("获取并发信号量失败: {}", e),
                            current_page: 0,
                            total_pages: 0,
                            output_path: None,
                        };
                        let _ = app.emit("ocr-progress", payload);
                        if let Ok(mut tasks) = app.state::<AppState>().active_tasks.lock() {
                            tasks.remove(&task_id);
                        }
                        return;
                    }
                }
            }
            _ = &mut abort_rx => {
                let payload = ProgressPayload {
                    r#type: "progress".to_string(),
                    task_id: task_id.clone(),
                    status: "error".to_string(),
                    message: "用户已中止清理".to_string(),
                    current_page: 0,
                    total_pages: 0,
                    output_path: None,
                };
                let _ = app.emit("ocr-progress", payload);
                if let Ok(mut tasks) = app.state::<AppState>().active_tasks.lock() {
                    tasks.remove(&task_id);
                }
                return;
            }
        };
        let _permit_holder = permit;

        // Use spawn_sidecar helper
        let (mut session, mut rx) = match spawn_sidecar(&app_clone, args) {
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
                if let Ok(mut tasks) = app.state::<AppState>().active_tasks.lock() {
                    tasks.remove(&task_id);
                }
                return;
            }
        };

        let mut status_emitted = false;
        let mut stderr_buffer = Vec::<String>::new();

        loop {
            let rx_recv_fut = tokio::time::timeout(std::time::Duration::from_secs(60), rx.recv());
            
            tokio::select! {
                event_res = rx_recv_fut => {
                    let event_opt = match event_res {
                        Ok(opt) => opt,
                        Err(_) => {
                            if !status_emitted {
                                let mut msg = "OCR 进程超时或未响应(60秒)".to_string();
                                if !stderr_buffer.is_empty() {
                                    msg.push_str(&format!("。错误日志: {}", stderr_buffer.join(" | ")));
                                }
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
                    };

                    let event = match event_opt {
                        Some(ev) => ev,
                        None => break,
                    };

                    match event {
                        SidecarOutputEvent::Stdout(line_str) => {
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
                        SidecarOutputEvent::Stderr(line_str) => {
                            eprintln!("[Sidecar Stderr] {}", line_str);
                            if stderr_buffer.len() >= 3 {
                                stderr_buffer.remove(0);
                            }
                            stderr_buffer.push(line_str);
                        }
                        SidecarOutputEvent::Terminated(code) => {
                            if !status_emitted {
                                let mut msg = match code {
                                    Some(c) => format!("进程意外终止，退出码: {}", c),
                                    None => "进程意外终止".to_string(),
                                };
                                if !stderr_buffer.is_empty() {
                                    msg.push_str(&format!("。错误日志: {}", stderr_buffer.join(" | ")));
                                }
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
                    }
                }
                _ = &mut abort_rx => {
                    session.kill();
                    let payload = ProgressPayload {
                        r#type: "progress".to_string(),
                        task_id: task_id.clone(),
                        status: "error".to_string(),
                        message: "用户已中止清理".to_string(),
                        current_page: 0,
                        total_pages: 0,
                        output_path: None,
                    };
                    let _ = app.emit("ocr-progress", payload);
                    status_emitted = true;
                    break;
                }
            }
        }
        
        // Clean up registry
        if let Ok(mut tasks) = app.state::<AppState>().active_tasks.lock() {
            tasks.remove(&task_id);
        }

        if !status_emitted {
            let mut msg = "进程意外终止".to_string();
            if !stderr_buffer.is_empty() {
                msg.push_str(&format!("。错误日志: {}", stderr_buffer.join(" | ")));
            }
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
        }
        session.kill();
    });

    Ok(())
}

#[tauri::command]
async fn abort_task(task_id: String, app: AppHandle) -> Result<(), String> {
    let state = app.state::<AppState>();
    let mut active_tasks = state.active_tasks.lock().map_err(|e| e.to_string())?;
    if let Some(abort_tx) = active_tasks.remove(&task_id) {
        let _ = abort_tx.send(());
    }
    Ok(())
}

pub fn run() {
    let state = AppState {
        semaphore: Arc::new(Semaphore::new(2)), // Limit to max 2 concurrent OCR tasks
        active_tasks: Mutex::new(HashMap::new()),
    };

    tauri::Builder::default()
        .manage(state)
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .invoke_handler(tauri::generate_handler![scan_files, process_task, abort_task])
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

    #[tokio::test]
    async fn test_timeout_mechanism() {
        let mut cmd = if cfg!(target_os = "windows") {
            let mut c = tokio::process::Command::new("ping");
            c.args(["127.0.0.1", "-n", "3"]);
            c
        } else {
            let mut c = tokio::process::Command::new("sleep");
            c.arg("2");
            c
        };
        cmd.stdout(std::process::Stdio::piped());
        
        let mut child = cmd.spawn().unwrap();
        let stdout = child.stdout.take().unwrap();
        let mut reader = tokio::io::BufReader::new(stdout);
        let mut line_str = String::new();
        
        let fut = async {
            use tokio::io::AsyncBufReadExt;
            let _ = reader.read_line(&mut line_str).await;
        };
        
        // Wrap with a 100ms timeout
        let res = tokio::time::timeout(std::time::Duration::from_millis(100), fut).await;
        assert!(res.is_err(), "Expected timeout error");
        
        // Clean up
        let kill_res = child.kill().await;
        assert!(kill_res.is_ok());
    }

    #[tokio::test]
    async fn test_stderr_capture_mechanism() {
        let mut cmd = if cfg!(target_os = "windows") {
            let mut c = tokio::process::Command::new("cmd");
            c.args(["/c", "echo err1>&2 && echo err2>&2 && echo err3>&2 && echo err4>&2"]);
            c
        } else {
            let mut c = tokio::process::Command::new("sh");
            c.args(["-c", "echo err1 >&2 && echo err2 >&2 && echo err3 >&2 && echo err4 >&2"]);
            c
        };
        cmd.stderr(std::process::Stdio::piped());

        let mut child = cmd.spawn().unwrap();
        let stderr = child.stderr.take().unwrap();
        let mut reader_err = tokio::io::BufReader::new(stderr);

        let stderr_buffer = std::sync::Arc::new(std::sync::Mutex::new(Vec::<String>::new()));
        let stderr_task = {
            let buffer = stderr_buffer.clone();
            async move {
                use tokio::io::AsyncBufReadExt;
                let mut err_line = String::new();
                while reader_err.read_line(&mut err_line).await.is_ok() {
                    if err_line.is_empty() { break; }
                    let trimmed = err_line.trim_end().to_string();
                    if let Ok(mut buf) = buffer.lock() {
                        if buf.len() >= 3 {
                            buf.remove(0);
                        }
                        buf.push(trimmed);
                    }
                    err_line.clear();
                }
            }
        };

        let stderr_handle = tokio::spawn(stderr_task);
        let _ = stderr_handle.await;
        let buffer = {
            if let Ok(buf) = stderr_buffer.lock() {
                buf.clone()
            } else {
                Vec::new()
            }
        };
        
        assert_eq!(buffer.len(), 3);
        assert_eq!(buffer[0], "err2");
        assert_eq!(buffer[1], "err3");
        assert_eq!(buffer[2], "err4");

        let _ = child.wait().await;
    }
}

