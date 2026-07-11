use std::env;
use std::fs;

#[derive(Clone, Debug)]
pub struct AppConfig {
    pub ocr_concurrency_limit: usize,
    pub scan_timeout_secs: u64,
    pub process_timeout_secs: u64,
    pub python_interpreter_path: String,
    pub python_script_path: String,
}

impl AppConfig {
    pub fn load() -> Self {
        // Simple .env file manual line-by-line parsing to avoid external dependencies
        if let Ok(content) = fs::read_to_string(".env") {
            for line in content.lines() {
                let line = line.trim();
                if line.is_empty() || line.starts_with('#') {
                    continue;
                }
                if let Some((key, value)) = line.split_once('=') {
                    let key = key.trim();
                    let value = value.trim().trim_matches('"').trim_matches('\'');
                    env::set_var(key, value);
                }
            }
        }

        let ocr_concurrency_limit = env::var("OCR_CONCURRENCY_LIMIT")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(1);

        let scan_timeout_secs = env::var("SCAN_TIMEOUT_SECS")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(180);

        let process_timeout_secs = env::var("PROCESS_TIMEOUT_SECS")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(300);

        let python_interpreter_path = env::var("PYTHON_INTERPRETER_PATH")
            .unwrap_or_else(|_| {
                if cfg!(target_os = "windows") {
                    "../python-sidecar/venv/Scripts/python.exe".to_string()
                } else {
                    "../python-sidecar/venv/bin/python".to_string()
                }
            });

        let python_script_path = env::var("PYTHON_SCRIPT_PATH")
            .unwrap_or_else(|_| "../python-sidecar/src/main.py".to_string());

        Self {
            ocr_concurrency_limit,
            scan_timeout_secs,
            process_timeout_secs,
            python_interpreter_path,
            python_script_path,
        }
    }
}
