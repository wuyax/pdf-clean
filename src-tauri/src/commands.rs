use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, Manager};
use crate::state::AppState;
use crate::sidecar::{spawn_sidecar, SidecarOutputEvent};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ProgressPayload {
    pub r#type: String,
    pub task_id: String,
    pub status: String,
    pub message: String,
    pub current_page: usize,
    pub total_pages: usize,
    pub output_path: Option<String>,
}

#[derive(thiserror::Error, Debug)]
pub enum CommandError {
    #[error("Sidecar execution failed: {0}")]
    SidecarError(String),
    #[error("Operation timeout: {0}")]
    Timeout(String),
    #[error("Lock acquisition failed: {0}")]
    LockError(String),
    #[error("Internal error: {0}")]
    Internal(String),
}

// Enable Tauri commands to serialize this error to String for the frontend
impl serde::Serialize for CommandError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_str(&self.to_string())
    }
}

#[tauri::command]
pub async fn scan_files(paths: Vec<String>, app: AppHandle) -> Result<serde_json::Value, CommandError> {
    let mut args = vec!["scan".to_string()];
    args.extend(paths);

    let (mut session, mut rx) = spawn_sidecar(&app, args)
        .map_err(|e| CommandError::SidecarError(e))?;
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

    let state = app.state::<AppState>();
    let scan_timeout = state.config.scan_timeout_secs;

    let results = match tokio::time::timeout(std::time::Duration::from_secs(scan_timeout), run_fut).await {
        Ok(res) => res,
        Err(_) => {
            session.kill();
            return Err(CommandError::Timeout(format!("Scan timeout after {} seconds", scan_timeout)));
        }
    };
    session.kill();
    results.ok_or_else(|| CommandError::Internal("Failed to get scan results".to_string()))
}

#[tauri::command]
pub async fn process_task(
    input_path: String,
    output_dir: String,
    conflict_policy: String,
    task_id: String,
    dpi: u32,
    quality: u8,
    app: AppHandle,
) -> Result<(), CommandError> {
    let state = app.state::<AppState>();
    let semaphore = state.semaphore.clone();
    let (abort_tx, mut abort_rx) = tokio::sync::oneshot::channel::<()>();
    
    {
        let mut tasks = state.active_tasks.lock()
            .map_err(|e| CommandError::LockError(e.to_string()))?;
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
        let _cleanup_guard = crate::state::TaskCleanupGuard {
            app: app.clone(),
            task_id: task_id.clone(),
        };

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
                return;
            }
        };

        let mut status_emitted = false;
        let mut stderr_buffer = Vec::<String>::new();

        let process_timeout = app.state::<AppState>().config.process_timeout_secs;

        loop {
            let rx_recv_fut = tokio::time::timeout(std::time::Duration::from_secs(process_timeout), rx.recv());
            
            tokio::select! {
                event_res = rx_recv_fut => {
                    let event_opt = match event_res {
                        Ok(opt) => opt,
                        Err(_) => {
                            if !status_emitted {
                                let mut msg = format!("OCR 进程超时或未响应({}秒)", process_timeout);
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
                                    "error" => {
                                        status_emitted = true;
                                        "error"
                                    }
                                    _ => {
                                        // Unknown JSON message type (e.g. debugging/info logs).
                                        // Log it and continue reading instead of terminating.
                                        eprintln!("[Sidecar Info JSON] {:?}", val);
                                        continue; 
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
pub async fn abort_task(task_id: String, app: AppHandle) -> Result<(), CommandError> {
    let state = app.state::<AppState>();
    let mut active_tasks = state.active_tasks.lock()
        .map_err(|e| CommandError::LockError(e.to_string()))?;
    if let Some(abort_tx) = active_tasks.remove(&task_id) {
        let _ = abort_tx.send(());
    }
    Ok(())
}
