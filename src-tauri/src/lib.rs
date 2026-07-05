 use tauri::{Manager, TitleBarStyle};

 pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .setup(|app| {
            // 获取主窗口
            let main_window = app.get_webview_window("main").unwrap();

            // 针对 macOS 的底层强制设置
            #[cfg(target_os = "macos")]
            {
                use tauri::Runtime;
                // 强制设置沉浸式样式
                main_window.set_title_bar_style(TitleBarStyle::Overlay).ok();
                // 强制隐藏标题文本
                main_window.set_title("").ok();
            }

            #[cfg(not(debug_assertions))]
            {
                use tauri_plugin_shell::ShellExt;
                use tauri::path::BaseDirectory;

                let ocr_models_dir = app.path()
                    .resolve("resources/ocr_models", BaseDirectory::Resource)?;
                let ocr_models_str = ocr_models_dir.to_string_lossy().to_string();

                let (mut rx, _child) = app.shell()
                    .sidecar("python-sidecar")?
                    .env("MODEL_DIR", &ocr_models_str)
                    .spawn()?;

                tauri::async_runtime::spawn(async move {
                    while let Some(_event) = rx.recv().await {
                        // Drain output to prevent buffer blocking
                    }
                });
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
