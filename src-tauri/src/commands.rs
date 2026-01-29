use std::sync::Mutex;
use tauri::State;

pub struct SidecarState {
    pub port: Option<u16>,
}

#[tauri::command]
pub fn get_sidecar_port(state: State<'_, Mutex<SidecarState>>) -> Result<u16, String> {
    let state = state.lock().map_err(|e| e.to_string())?;
    state.port.ok_or_else(|| "Sidecar not ready".to_string())
}
