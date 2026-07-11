use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, Manager};
use crate::state::AppState;
use crate::sidecar::SidecarOutputEvent;

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

// Enable Tauri commands to serialize this error to an object with a message field for the frontend
impl serde::Serialize for CommandError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        use serde::ser::SerializeStruct;
        let mut state = serializer.serialize_struct("CommandError", 1)?;
        state.serialize_field("message", &self.to_string())?;
        state.end()
    }
}

async fn get_or_start_daemon<'a>(
    app: &tauri::AppHandle,
    daemon_guard: &'a mut Option<(crate::sidecar::SidecarSession, tokio::sync::mpsc::Receiver<crate::sidecar::SidecarOutputEvent>)>,
) -> Result<&'a mut (crate::sidecar::SidecarSession, tokio::sync::mpsc::Receiver<crate::sidecar::SidecarOutputEvent>), CommandError> {
    if daemon_guard.is_none() {
        let (session, rx) = crate::sidecar::spawn_sidecar(app, vec!["daemon".to_string()])
            .map_err(|e| CommandError::SidecarError(format!("Failed to spawn daemon sidecar: {}", e)))?;
        *daemon_guard = Some((session, rx));
    }
    Ok(daemon_guard.as_mut().unwrap())
}

#[tauri::command]
pub async fn scan_files(paths: Vec<String>, app: AppHandle) -> Result<serde_json::Value, CommandError> {
    let state = app.state::<AppState>();
    let scan_timeout = state.config.scan_timeout_secs;

    let mut daemon_guard = state.daemon.lock().await;
    get_or_start_daemon(&app, &mut *daemon_guard).await?;

    let (mut session, mut rx) = daemon_guard.take().unwrap();

    let req = serde_json::json!({
        "action": "scan",
        "paths": paths,
    });
    let req_str = serde_json::to_string(&req).map_err(|e| CommandError::Internal(e.to_string()))?;
    
    if let Err(e) = session.write_line(&req_str).await {
        session.kill();
        return Err(CommandError::SidecarError(format!("Failed to write to daemon: {}", e)));
    }

    let run_fut = async {
        while let Some(event) = rx.recv().await {
            match event {
                SidecarOutputEvent::Stdout(line_str) => {
                    if let Ok(val) = serde_json::from_str::<serde_json::Value>(&line_str) {
                        if val["type"] == "scan_result" {
                            return Ok(val["results"].clone());
                        }
                    }
                }
                SidecarOutputEvent::Stderr(line_str) => {
                    eprintln!("[Daemon Scan Stderr] {}", line_str);
                }
                SidecarOutputEvent::Terminated(_) => {
                    return Err(CommandError::SidecarError("Daemon terminated during scan".to_string()));
                }
            }
        }
        Err(CommandError::SidecarError("Daemon connection closed".to_string()))
    };

    match tokio::time::timeout(std::time::Duration::from_secs(scan_timeout), run_fut).await {
        Ok(res) => {
            match res {
                Ok(results) => {
                    *daemon_guard = Some((session, rx));
                    Ok(results)
                }
                Err(e) => {
                    session.kill();
                    Err(e)
                }
            }
        }
        Err(_) => {
            session.kill();
            Err(CommandError::Timeout(format!("Scan timeout after {} seconds", scan_timeout)))
        }
    }
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
        let mut active_tasks = state.active_tasks.lock()
            .map_err(|e| CommandError::LockError(e.to_string()))?;
        active_tasks.insert(task_id.clone(), abort_tx);
    }

    #[allow(clippy::redundant_clone)]
    let app_clone = app.clone();
    tauri::async_runtime::spawn(async move {
        let _cleanup_guard = crate::state::TaskCleanupGuard {
            app: app_clone.clone(),
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
                        let _ = app_clone.emit("ocr-progress", payload);
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
                let _ = app_clone.emit("ocr-progress", payload);
                return;
            }
        };
        let _permit_holder = permit;

        let state = app_clone.state::<AppState>();
        let mut daemon_guard = state.daemon.lock().await;
        
        let (mut session, mut rx) = match get_or_start_daemon(&app_clone, &mut *daemon_guard).await {
            Ok(_) => daemon_guard.take().unwrap(),
            Err(e) => {
                let payload = ProgressPayload {
                    r#type: "progress".to_string(),
                    task_id: task_id.clone(),
                    status: "error".to_string(),
                    message: format!("启动守护进程失败: {}", e),
                    current_page: 0,
                    total_pages: 0,
                    output_path: None,
                };
                let _ = app_clone.emit("ocr-progress", payload);
                return;
            }
        };

        let req = serde_json::json!({
            "action": "process",
            "input_path": input_path,
            "output_dir": output_dir,
            "conflict": conflict_policy,
            "task_id": task_id.clone(),
            "dpi": dpi,
            "quality": quality,
        });
        let req_str = match serde_json::to_string(&req) {
            Ok(s) => s,
            Err(e) => {
                let payload = ProgressPayload {
                    r#type: "progress".to_string(),
                    task_id: task_id.clone(),
                    status: "error".to_string(),
                    message: format!("序列化请求失败: {}", e),
                    current_page: 0,
                    total_pages: 0,
                    output_path: None,
                };
                let _ = app_clone.emit("ocr-progress", payload);
                *daemon_guard = Some((session, rx));
                return;
            }
        };

        if let Err(e) = session.write_line(&req_str).await {
            let payload = ProgressPayload {
                r#type: "progress".to_string(),
                task_id: task_id.clone(),
                status: "error".to_string(),
                message: format!("向守护进程写入失败: {}", e),
                current_page: 0,
                total_pages: 0,
                output_path: None,
            };
            let _ = app_clone.emit("ocr-progress", payload);
            session.kill();
            return;
        }

        let mut status_emitted = false;
        let mut stderr_buffer = Vec::<String>::new();
        let mut exit_code = None;
        let mut put_back = false;

        let process_timeout = app_clone.state::<AppState>().config.process_timeout_secs;

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
                                let _ = app_clone.emit("ocr-progress", payload);
                                status_emitted = true;
                            }
                            session.kill();
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
                                        put_back = true;
                                        "completed"
                                    }
                                    "error" => {
                                        status_emitted = true;
                                        put_back = true;
                                        "error"
                                    }
                                    _ => {
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
                                let _ = app_clone.emit("ocr-progress", payload);
                                if status == "completed" || status == "error" {
                                    break;
                                }
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
                            exit_code = Some(code);
                            break;
                        }
                    }
                }
                _ = &mut abort_rx => {
                    if let Some((mut session, _)) = daemon_guard.take() {
                        session.kill();
                    }
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
                    let _ = app_clone.emit("ocr-progress", payload);
                    status_emitted = true;
                    break;
                }
            }
        }

        if !status_emitted {
            let mut msg = match exit_code {
                Some(Some(c)) => format!("进程意外终止，退出码: {}", c),
                _ => "进程意外终止".to_string(),
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
            let _ = app_clone.emit("ocr-progress", payload);
            session.kill();
        } else if put_back {
            *daemon_guard = Some((session, rx));
        }
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
