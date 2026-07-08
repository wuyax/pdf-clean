use serde::{Deserialize, Serialize};
use std::io::{BufRead, BufReader};
use tauri::{AppHandle, Emitter, Manager, TitleBarStyle};

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

// Cross-platform helper to spawn the sidecar in dev (venv python) or release (Tauri sidecar)
fn spawn_process(app: &AppHandle, args: Vec<String>) -> Result<std::process::Child, String> {
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
           .stderr(std::process::Stdio::piped());
        
        #[cfg(target_os = "windows")]
        {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
        }

        cmd.spawn().map_err(|e| format!("Failed to spawn python venv: {}", e))
    }

    #[cfg(not(debug_assertions))]
    {
        let ocr_models_dir = app.path()
            .resolve("resources/ocr_models", tauri::path::BaseDirectory::Resource)
            .map_err(|e| e.to_string())?;
        let ocr_models_str = ocr_models_dir.to_string_lossy().to_string();

        // Spawn sidecar via OS Command to get standard stdout reader
        let sidecar_path = app.path()
            .resolve("binaries/python-sidecar", tauri::path::BaseDirectory::Resource)
            .map_err(|e| e.to_string())?;
        
        let platform_sidecar_name = if cfg!(target_os = "windows") {
            "python-sidecar.exe"
        } else {
            "python-sidecar"
        };
        let sidecar_bin = sidecar_path.join(platform_sidecar_name);

        let mut cmd = std::process::Command::new(sidecar_bin);
        cmd.args(args)
           .env("MODEL_DIR", &ocr_models_str)
           .stdout(std::process::Stdio::piped())
           .stderr(std::process::Stdio::piped());

        #[cfg(target_os = "windows")]
        {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
        }

        cmd.spawn().map_err(|e| format!("Failed to spawn release sidecar: {}", e))
    }
}

#[tauri::command]
async fn scan_files(paths: Vec<String>, app: AppHandle) -> Result<serde_json::Value, String> {
    let mut args = vec!["scan".to_string()];
    args.extend(paths);

    let mut child = spawn_process(&app, args)?;
    let stdout = child.stdout.take().ok_or("Failed to open sidecar stdout")?;
    let reader = BufReader::new(stdout);

    for line in reader.lines() {
        if let Ok(line_str) = line {
            if let Ok(val) = serde_json::from_str::<serde_json::Value>(&line_str) {
                if val["type"] == "scan_result" {
                    return Ok(val["results"].clone());
                }
            }
        }
    }
    Err("Failed to get scan results from sidecar".to_string())
}

#[tauri::command]
async fn process_task(
    input_path: String,
    output_dir: String,
    conflict_policy: String,
    task_id: String,
    app: AppHandle,
) -> Result<(), String> {
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

    // Spawn in blocking/separate thread to stream events
    std::thread::spawn(move || {
        let mut child = match spawn_process(&app, args) {
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

        let stdout = child.stdout.take().expect("Failed to open sidecar stdout");
        let reader = BufReader::new(stdout);

        for line in reader.lines() {
            if let Ok(line_str) = line {
                if let Ok(val) = serde_json::from_str::<serde_json::Value>(&line_str) {
                    let type_str = val["type"].as_str().unwrap_or("");
                    let status = match type_str {
                        "progress" => "processing",
                        "completed" => "completed",
                        _ => "error",
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
    });

    Ok(())
}

pub fn run() {
    tauri::Builder::default()
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
