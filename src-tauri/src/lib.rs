mod commands;

use commands::{get_sidecar_port, SidecarState};
use std::io::{BufRead, BufReader};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            // Focus the existing window when a second instance is launched
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_focus();
            }
        }))
        .manage(Mutex::new(SidecarState { port: None }))
        .manage(Mutex::new(None::<Child>))
        .invoke_handler(tauri::generate_handler![get_sidecar_port])
        .setup(|app| {
            let app_handle = app.handle().clone();

            // In dev mode, resolve the Python venv relative to the project root.
            // Tauri runs from src-tauri/, so parent is the project root.
            let project_root = std::env::current_dir()
                .expect("Failed to get current directory")
                .parent()
                .expect("Failed to get project root")
                .to_path_buf();

            let python_path = project_root
                .join("sidecar")
                .join(".venv")
                .join("bin")
                .join("python3");

            let sidecar_dir = project_root.join("sidecar");

            // Spawn the Python sidecar process
            let mut child = Command::new(&python_path)
                .arg("-u") // unbuffered stdout
                .arg("main.py")
                .current_dir(&sidecar_dir)
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .spawn()
                .expect("Failed to spawn Python sidecar");

            // Read stdout in a background thread to capture the PORT line
            let stdout = child.stdout.take().expect("Failed to capture stdout");

            std::thread::spawn({
                let handle = app_handle.clone();
                move || {
                    let reader = BufReader::new(stdout);
                    for line in reader.lines() {
                        if let Ok(line) = line {
                            if let Some(port_str) = line.strip_prefix("PORT:") {
                                if let Ok(port) = port_str.parse::<u16>() {
                                    let state = handle.state::<Mutex<SidecarState>>();
                                    let mut state = state.lock().unwrap();
                                    state.port = Some(port);
                                    eprintln!("Sidecar started on port {}", port);
                                }
                            }
                        }
                    }
                }
            });

            // Store child process for cleanup on exit
            let child_state = app_handle.state::<Mutex<Option<Child>>>();
            *child_state.lock().unwrap() = Some(child);

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            let state = app_handle.state::<Mutex<Option<Child>>>();
            let mut guard = match state.lock() {
                Ok(g) => g,
                Err(_) => return,
            };
            if let Some(ref mut child) = *guard {
                let _ = child.kill();
                eprintln!("Sidecar process killed");
            }
        }
    });
}
