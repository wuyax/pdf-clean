use tauri::{AppHandle, Manager};

#[derive(Debug, Clone)]
pub enum SidecarOutputEvent {
    Stdout(String),
    Stderr(String),
    Terminated(Option<i32>),
}

pub struct SidecarSession {
    pub kill_tx: Option<tokio::sync::oneshot::Sender<()>>,
}

impl SidecarSession {
    pub fn kill(&mut self) {
        if let Some(tx) = self.kill_tx.take() {
            let _ = tx.send(());
        }
    }
}

pub fn spawn_sidecar(
    app: &AppHandle,
    args: Vec<String>,
) -> Result<(SidecarSession, tokio::sync::mpsc::Receiver<SidecarOutputEvent>), String> {
    let (tx, rx) = tokio::sync::mpsc::channel::<SidecarOutputEvent>(100);
    let (kill_tx, kill_rx) = tokio::sync::oneshot::channel::<()>();

    let state = app.try_state::<crate::state::AppState>().ok_or("AppState not registered")?;
    let config = &state.config;

    let ocr_models_dir = app.path()
        .resolve("resources/ocr_models", tauri::path::BaseDirectory::Resource)
        .map_err(|e| e.to_string())?;
    let ocr_models_str = ocr_models_dir.to_string_lossy().to_string();

    #[cfg(debug_assertions)]
    {
        let python_bin = &config.python_interpreter_path;
        let script_path = &config.python_script_path;
        let mut cmd = tokio::process::Command::new(python_bin);
        cmd.arg(script_path)
           .args(args)
           .env("MODEL_DIR", &ocr_models_str)
           .stdin(std::process::Stdio::piped()) // Pipe stdin to monitor parent death
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

#[cfg(test)]
mod tests {
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
