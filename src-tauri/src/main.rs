// droidB GUI — native Rust (Tauri v2) backend. Drives droidB-native as a subprocess and
// parses its --json output, the same pattern arxctl already uses for `arx` (see
// `arx updates-json` alongside `arx update`): the CLI is the single source of truth and the
// GUI never re-implements device/USB/flashing logic, it only presents what the CLI already
// does. Nothing here is mocked — every command below runs the real binary.
//
// Binary is deliberately `droidB-gui-native`, not `droidB-gui` — that name is the existing
// Python/GTK app's. This is additive during development; the cutover to replace it is a
// later, deliberate step once this GUI covers the same ground.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};

/// Holds the currently-running logcat child's PID, if any, so a Stop button can end an
/// otherwise-unbounded stream (droidB-native logcat runs until Ctrl+C by design — a GUI
/// with no equivalent stop control would be a real usability gap, not a minor omission).
/// The Arc is what actually makes this shareable: `tauri::State` only hands out a reference
/// into Tauri-managed state, which cannot be moved into the spawned worker thread below —
/// cloning the Arc gives the thread its own owned handle to the SAME underlying Mutex.
#[derive(Clone)]
struct LogcatHandle(Arc<Mutex<Option<u32>>>);

// ---------- resolve the droidB-native CLI binary ----------

fn droidb_bin() -> PathBuf {
    // Installed system-wide (repos/droidB/install-native.sh) — the normal case once shipped.
    if let Ok(path) = std::env::var("PATH") {
        for dir in path.split(':') {
            let p = PathBuf::from(dir).join("droidB-native");
            if p.is_file() { return p; }
        }
    }
    // Dev fallback: this crate is workspace member src-tauri/, so the CLI binary lands in
    // the shared workspace target/ one level up. Release preferred if both exist.
    for profile in ["release", "debug"] {
        let p = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("target").join(profile).join("droidB-native");
        if p.is_file() { return p; }
    }
    PathBuf::from("droidB-native") // last resort: let Command::output's own error name it missing
}

fn run(args: &[&str]) -> Result<String, String> {
    let out = Command::new(droidb_bin()).args(args).output().map_err(|e| format!("failed to run droidB-native: {e}"))?;
    if !out.status.success() {
        let err = String::from_utf8_lossy(&out.stderr);
        let err = if err.trim().is_empty() { String::from_utf8_lossy(&out.stdout).trim().to_string() } else { err.trim().to_string() };
        return Err(if err.is_empty() { format!("droidB-native exited {}", out.status) } else { err });
    }
    Ok(String::from_utf8_lossy(&out.stdout).into_owned())
}

fn run_json<T: serde::de::DeserializeOwned>(args: &[&str]) -> Result<T, String> {
    let out = run(args)?;
    serde_json::from_str(&out).map_err(|e| format!("bad JSON from droidB-native: {e} (raw: {out})"))
}

#[derive(Serialize)]
struct ActionResult { ok: bool, exit_code: i32, output: String }

/// Every subcommand allowed through the generic runner below. droidB-native validates its
/// own inputs internally regardless of caller (package names, paths, IPs — see adb.rs's
/// safe_token/device.rs's valid_package, already unit-tested), and Command::args never
/// invokes a shell so there is no injection surface either way; this allowlist is defense in
/// depth against the GUI accidentally constructing an unintended top-level command, not a
/// security boundary by itself.
const ALLOWED_SUBCOMMANDS: &[&str] = &[
    "install", "uninstall", "clear-data", "stop", "push", "pull", "screenshot", "record",
    "reboot", "debloat", "wifi", "backup", "restore", "extract", "proxy", "cert", "avd",
    "harden", "engines", "deeplinks", "mtk",
];

/// Runs any allowlisted droidB-native subcommand and returns its exit status + combined
/// output. Used for every action that is not a structured list — the frontend renders the
/// output verbatim in a console pane, same as the Samsung check-only flow already shipped.
#[tauri::command]
fn run_action(args: Vec<String>) -> Result<ActionResult, String> {
    let Some(first) = args.first() else { return Err("no subcommand given".into()) };
    if !ALLOWED_SUBCOMMANDS.contains(&first.as_str()) {
        return Err(format!("'{first}' is not a GUI-allowed subcommand"));
    }
    let out = Command::new(droidb_bin()).args(&args).output().map_err(|e| format!("failed to run droidB-native: {e}"))?;
    Ok(ActionResult {
        ok: out.status.success(),
        exit_code: out.status.code().unwrap_or(-1),
        output: format!("{}{}", String::from_utf8_lossy(&out.stdout), String::from_utf8_lossy(&out.stderr)).trim().to_string(),
    })
}

// ---------- device state ----------

#[tauri::command]
fn devices_list() -> Result<serde_json::Value, String> {
    run_json(&["devices", "--json"])
}

#[tauri::command]
fn probe_devices(all: bool) -> Result<serde_json::Value, String> {
    if all { run_json(&["probe", "--all", "--json"]) } else { run_json(&["probe", "--json"]) }
}

#[tauri::command]
fn device_battery() -> Result<String, String> {
    run_json(&["battery", "--json"])
}

#[tauri::command]
fn device_props() -> Result<String, String> {
    run_json(&["props", "--json"])
}

#[tauri::command]
fn fastboot_info() -> Result<serde_json::Value, String> {
    run_json(&["bootloader", "--json"])
}

// ---------- samsung (odin/thor) ----------

#[tauri::command]
fn samsung_version() -> Result<String, String> {
    run_json(&["samsung", "version", "--json"])
}

#[tauri::command]
fn samsung_devices() -> Result<Vec<String>, String> {
    run_json(&["samsung", "devices", "--json"])
}

/// Odin/Thor's own --check-only pass: reads the device's PIT and validates the given
/// firmware slots without writing anything. This GUI does not expose a real, irreversible
/// flash button yet on purpose — that needs an explicit confirmation flow, not a first pass.
#[tauri::command]
fn samsung_flash_check(bootloader: Option<String>, ap: Option<String>, cp: Option<String>, csc: Option<String>, ums: Option<String>) -> Result<ActionResult, String> {
    let mut args: Vec<String> = vec!["samsung".into(), "flash".into(), "--check-only".into()];
    let mut slot = |flag: &str, v: &Option<String>| if let Some(p) = v { args.push(flag.into()); args.push(p.clone()); };
    slot("-b", &bootloader);
    slot("-a", &ap);
    slot("-c", &cp);
    slot("-s", &csc);
    slot("-u", &ums);
    let out = Command::new(droidb_bin()).args(&args).output().map_err(|e| format!("failed to run droidB-native: {e}"))?;
    Ok(ActionResult {
        ok: out.status.success(),
        exit_code: out.status.code().unwrap_or(-1),
        output: format!("{}{}", String::from_utf8_lossy(&out.stdout), String::from_utf8_lossy(&out.stderr)).trim().to_string(),
    })
}

// ---------- apps ----------

#[tauri::command]
fn apps_list(filter: String) -> Result<Vec<String>, String> {
    let f = match filter.as_str() { "system" => "system", "user" => "user", _ => "all" };
    run_json(&["apps", f, "--json"])
}

// ---------- files ----------

#[tauri::command]
fn files_ls(path: String) -> Result<String, String> {
    run(&["ls", &path])
}

// ---------- MediaTek BROM (read-only chip id) ----------

#[tauri::command]
fn mtk_info() -> Result<String, String> {
    run(&["mtk"])
}

// ---------- engines (mtkclient / edl survey) ----------

#[tauri::command]
fn engines_survey() -> Result<String, String> {
    run(&["engines"])
}

// ---------- harden ----------

#[tauri::command]
fn harden_list() -> Result<String, String> {
    run(&["harden", "list"])
}

// ---------- logcat (streamed — a live tail, not a one-shot JSON return) ----------

/// Streams `droidB-native logcat <pkg> [--launch]` line by line via the `logcat-line` event,
/// same pattern as arxctl's anond_action_streamed: a worker thread reads the child's
/// stdout/stderr and forwards each line through an mpsc channel, the async command function
/// drains that channel into app.emit() so the frontend sees output as it happens rather than
/// waiting for the whole (potentially unbounded) stream to finish. `args` is built as owned
/// Strings up front specifically so it can move into the spawned thread — a borrowed &str
/// slice into `pkg` would not outlive this function returning.
#[tauri::command]
async fn logcat_stream(app: tauri::AppHandle, state: tauri::State<'_, LogcatHandle>, pkg: String, launch: bool) -> Result<i32, String> {
    use tauri::Emitter;
    if pkg.trim().is_empty() { return Err("package name required".into()); }
    let mut args: Vec<String> = vec!["logcat".into(), pkg.clone()];
    if launch { args.push("--launch".into()); }
    let bin = droidb_bin();
    let (tx, rx) = std::sync::mpsc::channel::<String>();
    let pid_slot = state.0.clone();
    let handle = std::thread::spawn(move || -> i32 {
        use std::io::{BufRead, BufReader};
        let mut cmd = Command::new(bin);
        cmd.args(&args).stdout(Stdio::piped()).stderr(Stdio::piped());
        let mut child = match cmd.spawn() { Ok(c) => c, Err(e) => { let _ = tx.send(format!("could not start droidB-native: {e}")); return -1; } };
        *pid_slot.lock().unwrap() = Some(child.id());
        if let Some(out) = child.stdout.take() {
            for line in BufReader::new(out).lines().map_while(Result::ok) { let _ = tx.send(line); }
        }
        if let Some(err) = child.stderr.take() {
            for line in BufReader::new(err).lines().map_while(Result::ok) { let _ = tx.send(line); }
        }
        let code = child.wait().ok().and_then(|s| s.code()).unwrap_or(-1);
        *pid_slot.lock().unwrap() = None;
        code
    });
    for line in rx { let _ = app.emit("logcat-line", line); }
    handle.join().map_err(|_| "logcat worker panicked".to_string())
}

#[tauri::command]
fn logcat_stop(state: tauri::State<'_, LogcatHandle>) -> Result<(), String> {
    if let Some(pid) = *state.0.lock().unwrap() {
        // plain `kill`, not a new process-signaling crate, for one PID this process itself spawned.
        let _ = Command::new("kill").arg(pid.to_string()).status();
    }
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .manage(LogcatHandle(Arc::new(Mutex::new(None))))
        .invoke_handler(tauri::generate_handler![
            run_action,
            devices_list, probe_devices, device_battery, device_props, fastboot_info,
            samsung_version, samsung_devices, samsung_flash_check,
            apps_list, files_ls, mtk_info, engines_survey, harden_list,
            logcat_stream, logcat_stop,
        ])
        .run(tauri::generate_context!())
        .expect("error while running droidB");
}
