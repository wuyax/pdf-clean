# Task 2 Report: Implement Rust Tauri Commands and Sidecar Manager

## Summary
Task 2 has been completed and fully corrected according to the review findings. We implemented robust, on-demand sidecar spawning and Tauri commands (`scan_files` and `process_task`) in `src-tauri/src/lib.rs`.

## Changes and Fixes Made
1. **Official Tauri Sidecar Integration (Critical Fix)**:
   - In release mode (`#[cfg(not(debug_assertions))]`), replaced manual path resolution (`resolve("binaries/python-sidecar")`) with Tauri's official sidecar manager: `app.shell().sidecar("python-sidecar")?`.
   - This ensures the application can locate and spawn the sidecar correctly across platforms (macOS, Windows, Linux) in bundled production releases.

2. **Deadlock Prevention on Stderr (Critical Fix)**:
   - In dev mode (`#[cfg(debug_assertions)]`), set `.stderr(std::process::Stdio::inherit())` to forward stderr to the parent terminal, ensuring OS pipe buffers (typically 64KB) never block.
   - In release mode, the sidecar is spawned via the Tauri shell plugin which drains stdout and stderr internally. We handle `CommandEvent::Stderr` to print sidecar logs (`eprintln!`) to assist debugging.

3. **Zombie Process Prevention & Resource Leak Cleanup (Important Fix)**:
   - In dev mode, standard Rust child processes are now explicitly terminated using `child.kill()` and reaped via `child.wait()` at the end of execution blocks or on early breaks.
   - In release mode, the Tauri shell child process is killed and cleaned up using `child.kill()` upon task completion or termination.

4. **Crash Detection & Frontend Safety (Important Fix)**:
   - Enhanced both commands to track whether a final completed/error status has been emitted.
   - If the sidecar process crashes, exits early, or terminates without writing the expected final JSON message, the Rust backend detects the early exit and emits a `"进程意外终止"` (Process terminated unexpectedly) error progress event to the frontend, preventing the UI from hanging.

5. **Validation and Verification**:
   - Ran `cargo check` and `cargo check --release` in `src-tauri`.
   - Ensured zero compile warnings and errors.
