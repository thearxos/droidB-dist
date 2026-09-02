// droidB GUI — frontend logic. Talks to the Rust backend via the global Tauri API; the
// backend itself just runs droidB-native --json (or plain, for text-console panels) and
// hands the result straight through, so this file never invents device/USB state, only
// renders what the CLI reports.
const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// droidB-native's human-readable output (title(), println! with BOLD/DIM/RST) emits raw
// ANSI escape codes unconditionally — it is written for a terminal, not TTY-gated. Every
// panel that shows that output verbatim must strip these first, or the text shows through
// however the renderer happens to treat control bytes rather than cleanly. Applied by
// showConsole() below so every caller gets this for free, not re-implemented per panel.
function stripAnsi(s) {
  return String(s).replace(/\x1b\[[0-9;]*m/g, '');
}

// Shared result renderer for the run_action-driven panels (Screen, Debloat, Backup, Wi-Fi,
// Security, Harden, Deep links, Low-Level, Emulator): shows the (ANSI-stripped) output plus
// a clear pass/fail marker, matching the pattern already proven on the Samsung panel.
// Errors from a failed Tauri command can come straight from droidB-native's own top-level
// error handler (main.rs: eprintln!("{ORANGE}✖{RST} {e:#}")), which is ANSI-wrapped exactly
// like its success output — the same stripAnsi() applies here, not just to showResult()'s
// `output` field. Centralizing it as errText() so every error-rendering call site gets this
// for free instead of relying on each one to remember it individually (a real bug: this was
// missed on several call sites the first time and showed raw escape codes in the UI).
function errText(e) {
  return stripAnsi(String(e));
}
function showResult(el, r) {
  const body = stripAnsi(r.output || '(no output)');
  const done = r.ok ? '<div class="done good">Done</div>' : `<div class="done fail">Failed (exit ${r.exit_code})</div>`;
  el.innerHTML = `<div>${esc(body)}</div>${done}`;
}
function showError(el, e) {
  el.innerHTML = `<div class="done fail">${esc(errText(e))}</div>`;
}
function showBusy(el, msg) {
  el.innerHTML = `<div class="con-empty">${esc(msg)}</div>`;
}

// Runs an allowlisted droidB-native subcommand through the generic backend dispatcher and
// renders the result into `el`, disabling `btn` for the duration so a slow action (a real
// device operation, not a local computation) cannot be double-fired by an impatient click.
async function runInto(el, btn, args, busyMsg) {
  if (btn) btn.disabled = true;
  showBusy(el, busyMsg || 'Working…');
  try {
    const r = await invoke('run_action', { args });
    showResult(el, r);
  } catch (e) {
    showError(el, e);
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ---- navigation ----
const loaders = {};
$$('.nav-item').forEach(b => b.addEventListener('click', () => {
  $$('.nav-item').forEach(x => x.classList.remove('active'));
  $$('.panel').forEach(x => x.classList.remove('active'));
  b.classList.add('active');
  const p = b.dataset.panel;
  $('#p-' + p).classList.add('active');
  loaders[p]?.();
}));

// ---- devices ----
const STATE_LABELS = {
  Device: 'authorised', Unauthorized: 'debugging not accepted yet', Offline: 'offline',
  Recovery: 'recovery', Sideload: 'sideload', Bootloader: 'bootloader', None: 'none',
};
const MODE_LABELS = {
  Adb: 'ADB', AdbSideload: 'ADB sideload', Fastboot: 'Fastboot', Mtp: 'MTP', Ptp: 'PTP',
  Modem: 'Modem (CDC ACM)', MassStorage: 'Mass storage', Rndis: 'USB tethering', Midi: 'MIDI',
  SamsungDownload: 'Samsung Download Mode', QualcommEdl: 'Qualcomm EDL',
  MediatekPreloader: 'MediaTek Preloader', Unknown: 'unrecognised',
};

function renderAdb(devices) {
  const node = $('#adb-devices');
  if (!devices.length) { node.hidden = true; return; }
  node.hidden = false;
  $('#adb-list').innerHTML = devices.map(d => {
    const label = d.model ? `${d.model} (${d.serial})` : d.serial;
    const state = STATE_LABELS[d.state] || d.state;
    const android = d.android ? ` · Android ${d.android} (API ${d.sdk})` : '';
    return `<div class="dev-row"><span class="status-dot ${d.state === 'Device' ? 'ok' : 'bad'}"></span>` +
      `<span class="name">${esc(label)}</span><span class="dim mono">${esc(state)}${esc(android)}</span></div>`;
  }).join('');
  // per-device quick actions (battery / props / reboot) for the first authorised device —
  // full multi-device targeting isn't wired yet, so this covers the common single-phone case.
  const authed = devices.find(d => d.state === 'Device');
  $('#adb-detail-actions').innerHTML = authed ? `
    <button class="btn-g sm" id="btn-dev-battery">Battery</button>
    <button class="btn-g sm" id="btn-dev-props">Properties</button>
    <button class="btn-g sm" id="btn-dev-reboot">Reboot</button>
    <button class="btn-g sm" id="btn-dev-reboot-recovery">Reboot to recovery</button>
    <button class="btn-g sm" id="btn-dev-reboot-bootloader">Reboot to bootloader</button>` : '';
  if (authed) {
    $('#btn-dev-battery')?.addEventListener('click', async () => {
      try { alert(stripAnsi(await invoke('device_battery'))); } catch (e) { alert(errText(e)); }
    });
    $('#btn-dev-props')?.addEventListener('click', async () => {
      try {
        const w = window.open('', '_blank', 'width=640,height=480');
        if (w) w.document.write(`<pre style="white-space:pre-wrap;font-family:monospace;padding:16px">${esc(stripAnsi(await invoke('device_props')))}</pre>`);
      } catch (e) { alert(errText(e)); }
    });
    $('#btn-dev-reboot')?.addEventListener('click', () => invoke('run_action', { args: ['reboot'] }).catch(e => alert(errText(e))));
    $('#btn-dev-reboot-recovery')?.addEventListener('click', () => invoke('run_action', { args: ['reboot', 'recovery'] }).catch(e => alert(errText(e))));
    $('#btn-dev-reboot-bootloader')?.addEventListener('click', () => invoke('run_action', { args: ['reboot', 'bootloader'] }).catch(e => alert(errText(e))));
  }
}

function renderProbe(devices) {
  const grid = $('#probe-list'), empty = $('#probe-empty');
  if (!devices.length) { grid.innerHTML = ''; empty.hidden = false; return; }
  empty.hidden = true;
  grid.innerHTML = devices.map(d => {
    const name = [d.vendor_name, d.product_name].filter(Boolean).join(' ') || 'unknown device';
    const modes = [...new Set((d.interfaces || []).map(i => i.mode))];
    const modesHtml = modes.length
      ? modes.map(m => `<div class="mode-row"><span class="mode-dot ${m === 'Adb' ? 'adb' : 'other'}"></span>${esc(MODE_LABELS[m] || m)}</div>`).join('')
      : '<div class="mode-row dim">none recognised</div>';
    const warn = d.accessible ? '' : `<div class="warn">! ${esc(d.access_error)}</div>`;
    const ids = `${d.vendor_id.toString(16).padStart(4, '0')}:${d.product_id.toString(16).padStart(4, '0')}`;
    return `<div class="card dev-card">
      <b class="name">${esc(name)}</b>
      <span class="dim ids mono">${ids} · bus ${d.bus} device ${d.address}</span>
      ${d.serial ? `<div class="dim mono" style="margin-top:6px;font-size:.78rem">serial ${esc(d.serial)}</div>` : ''}
      <div class="modes">${modesHtml}</div>
      ${warn}
    </div>`;
  }).join('');
}

let probeAll = false;
async function loadDevices() {
  $('#deck-status').textContent = 'checking…';
  // Three real states, not two: a green "connected" dot must mean an actual device is on the
  // bus, not merely "the backend process answered" — those are different facts, and showing
  // green for the latter would misrepresent hardware state that isn't there.
  let adb = [], probe = [], backendOk = true;
  try { adb = await invoke('devices_list'); } catch { backendOk = false; }
  try { probe = await invoke('probe_devices', { all: probeAll }); } catch { backendOk = false; }
  renderAdb(adb || []);
  renderProbe(probe || []);
  const anyDevice = (adb && adb.length) || (probe && probe.length);
  if (!backendOk) {
    $('#deck-status').innerHTML = '<span class="status-dot bad"></span>backend unreachable';
  } else if (anyDevice) {
    $('#deck-status').innerHTML = '<span class="status-dot ok"></span>device connected';
  } else {
    $('#deck-status').innerHTML = '<span class="status-dot neutral"></span>no device';
  }
  $('#deck-backend').textContent = 'droidB-native';
}
loaders.devices = loadDevices;
$('#btn-refresh-devices').addEventListener('click', loadDevices);
$('#btn-probe-all').addEventListener('click', () => {
  probeAll = !probeAll;
  $('#btn-probe-all').textContent = probeAll ? 'Show Android devices only' : 'Show every USB device';
  loadDevices();
});

// ---- apps ----
let appsFilter = 'all';
async function loadApps() {
  const box = $('#apps-list');
  box.innerHTML = '<div class="con-empty">Loading…</div>';
  try {
    const list = await invoke('apps_list', { filter: appsFilter });
    $('#apps-count').textContent = list.length;
    box.innerHTML = list.length ? list.map(p =>
      `<div class="list-row"><span class="name mono">${esc(p)}</span><button class="subtle fill-pkg" data-pkg="${esc(p)}">use</button></div>`
    ).join('') : '<div class="con-empty">No apps found (or no device connected).</div>';
    $$('.fill-pkg', box).forEach(b => b.addEventListener('click', () => { $('#app-pkg').value = b.dataset.pkg; }));
  } catch (e) {
    $('#apps-count').textContent = '0';
    box.innerHTML = `<div class="con-empty">${esc(errText(e))}</div>`;
  }
}
loaders.apps = loadApps;
$$('#p-apps .tab').forEach(t => t.addEventListener('click', () => {
  $$('#p-apps .tab').forEach(x => x.classList.remove('on'));
  t.classList.add('on');
  appsFilter = t.dataset.filter;
  loadApps();
}));
function pkgOrAlert() {
  const v = $('#app-pkg').value.trim();
  if (!v) { alert('enter a package name first'); return null; }
  return v;
}
$('#btn-app-uninstall').addEventListener('click', () => { const p = pkgOrAlert(); if (p) runInto($('#apps-console'), null, ['uninstall', p]); });
$('#btn-app-cleardata').addEventListener('click', () => { const p = pkgOrAlert(); if (p) runInto($('#apps-console'), null, ['clear-data', p]); });
$('#btn-app-stop').addEventListener('click', () => { const p = pkgOrAlert(); if (p) runInto($('#apps-console'), null, ['stop', p]); });
$('#btn-app-install').addEventListener('click', () => {
  const path = $('#app-apk-path').value.trim();
  if (!path) return alert('enter an APK path first');
  runInto($('#apps-console'), $('#btn-app-install'), ['install', path], 'Installing…');
});

// ---- files ----
$('#btn-files-ls').addEventListener('click', async () => {
  const el = $('#files-console'), path = $('#files-path').value.trim() || '/sdcard/';
  showBusy(el, 'Listing…');
  try { el.innerHTML = `<pre style="margin:0;font:inherit">${esc(await invoke('files_ls', { path }))}</pre>`; }
  catch (e) { showError(el, e); }
});
$('#btn-push').addEventListener('click', () => {
  const local = $('#push-local').value.trim(), remote = $('#push-remote').value.trim() || '/sdcard/';
  if (!local) return alert('enter a local file path first');
  runInto($('#filexfer-console'), $('#btn-push'), ['push', local, remote], 'Pushing…');
});
$('#btn-pull').addEventListener('click', () => {
  const remote = $('#pull-remote').value.trim(), local = $('#pull-local').value.trim() || '.';
  if (!remote) return alert('enter a remote path first');
  runInto($('#filexfer-console'), $('#btn-pull'), ['pull', remote, local], 'Pulling…');
});

// ---- screen ----
$('#btn-screenshot').addEventListener('click', () => {
  const dir = $('#scr-dir').value.trim() || '.';
  runInto($('#screen-console'), $('#btn-screenshot'), ['screenshot', dir], 'Capturing…');
});
$('#btn-record').addEventListener('click', () => {
  const secs = $('#scr-secs').value.trim() || '10';
  runInto($('#screen-console'), $('#btn-record'), ['record', secs], `Recording ${secs}s…`);
});

// ---- logcat (streamed) ----
let logRunning = false;
listen('logcat-line', e => {
  const out = $('#log-out');
  if (out.querySelector('.con-empty')) out.innerHTML = '';
  const line = document.createElement('div');
  line.textContent = stripAnsi(String(e.payload));
  out.appendChild(line);
  out.scrollTop = out.scrollHeight;
});
$('#btn-log-start').addEventListener('click', async () => {
  const pkg = $('#log-pkg').value.trim();
  if (!pkg) return alert('enter a package name first');
  if (logRunning) return;
  logRunning = true;
  $('#btn-log-start').disabled = true;
  $('#btn-log-stop').disabled = false;
  $('#log-out').innerHTML = '';
  try {
    await invoke('logcat_stream', { pkg, launch: $('#log-launch').checked });
  } catch (e) {
    const out = $('#log-out');
    const line = document.createElement('div');
    line.className = 'done fail';
    line.textContent = errText(e);
    out.appendChild(line);
  } finally {
    logRunning = false;
    $('#btn-log-start').disabled = false;
    $('#btn-log-stop').disabled = true;
  }
});
$('#btn-log-stop').addEventListener('click', () => invoke('logcat_stop').catch(() => {}));

// ---- fastboot ----
async function loadFastboot() {
  const grid = $('#fastboot-list'), empty = $('#fastboot-empty');
  try {
    const devs = await invoke('fastboot_info');
    if (!devs.length) { grid.innerHTML = ''; empty.hidden = false; return; }
    empty.hidden = true;
    grid.innerHTML = devs.map(d => {
      const rows = (d.vars || []).map(([k, v]) => `<div class="mode-row"><span class="mode-dot other"></span><span class="mono">${esc(k)}</span>&nbsp;${esc(v)}</div>`).join('')
        || '<div class="mode-row dim">no variables answered (some are locked until unlocked)</div>';
      return `<div class="card dev-card"><b class="name mono">${esc(d.serial || '(unknown serial)')}</b><div class="modes">${rows}</div></div>`;
    }).join('');
  } catch (e) {
    grid.innerHTML = '';
    empty.hidden = false;
    empty.querySelector('.con-empty').textContent = errText(e);
  }
}
loaders.fastboot = loadFastboot;
$('#btn-fastboot-refresh').addEventListener('click', loadFastboot);

// ---- debloat ----
$('#btn-debloat-scan').addEventListener('click', () => runInto($('#debloat-console'), $('#btn-debloat-scan'), ['debloat', 'scan'], 'Scanning…'));
$('#btn-debloat-apply').addEventListener('click', () => {
  if (!confirm('Remove every curated bloat package that is installed? This is reversible via Restore.')) return;
  runInto($('#debloat-console'), $('#btn-debloat-apply'), ['debloat', 'apply'], 'Applying…');
});
$('#btn-debloat-restore').addEventListener('click', () => runInto($('#debloat-console'), $('#btn-debloat-restore'), ['debloat', 'restore'], 'Restoring…'));
$('#btn-debloat-backup').addEventListener('click', () => runInto($('#debloat-console'), $('#btn-debloat-backup'), ['debloat', 'backup'], 'Backing up list…'));

// ---- backup ----
$('#btn-backup-run').addEventListener('click', () => {
  const pkg = $('#bk-pkg').value.trim();
  runInto($('#backup-console'), $('#btn-backup-run'), pkg ? ['backup', pkg] : ['backup'], 'Backing up…');
});
$('#btn-backup-restore').addEventListener('click', () => {
  const path = $('#rs-path').value.trim();
  if (!path) return alert('enter a .ab path first');
  runInto($('#backup-console'), $('#btn-backup-restore'), ['restore', path], 'Restoring…');
});
$('#btn-backup-extract').addEventListener('click', () => {
  const path = $('#ex-path').value.trim(), pw = $('#ex-pw').value.trim();
  if (!path) return alert('enter a .ab path first');
  const args = pw ? ['extract', path, pw] : ['extract', path];
  runInto($('#backup-console'), $('#btn-backup-extract'), args, 'Extracting…');
});

// ---- wifi adb ----
$('#btn-wifi-enable').addEventListener('click', () => runInto($('#wifi-console'), $('#btn-wifi-enable'), ['wifi', 'enable'], 'Enabling…'));
$('#btn-wifi-connect').addEventListener('click', () => {
  const ip = $('#wifi-ip').value.trim();
  if (!ip) return alert('enter the device IP first (shown after Enable)');
  runInto($('#wifi-console'), $('#btn-wifi-connect'), ['wifi', 'connect', ip], 'Connecting…');
});
$('#btn-wifi-disconnect').addEventListener('click', () => runInto($('#wifi-console'), $('#btn-wifi-disconnect'), ['wifi', 'disconnect'], 'Disconnecting…'));

// ---- security (proxy + cert) ----
$('#btn-prx-set').addEventListener('click', () => {
  const addr = $('#prx-addr').value.trim();
  runInto($('#security-console'), $('#btn-prx-set'), addr ? ['proxy', 'set', addr] : ['proxy', 'set'], 'Setting proxy…');
});
$('#btn-prx-show').addEventListener('click', () => runInto($('#security-console'), $('#btn-prx-show'), ['proxy', 'show'], 'Checking…'));
$('#btn-prx-remove').addEventListener('click', () => runInto($('#security-console'), $('#btn-prx-remove'), ['proxy', 'remove'], 'Removing…'));
$('#btn-cert-install').addEventListener('click', () => {
  const tool = $('#cert-tool').value, addr = $('#cert-addr').value.trim();
  if (!addr) return alert('enter host:port first');
  runInto($('#security-console'), $('#btn-cert-install'), ['cert', tool, addr], 'Installing certificate…');
});
$('#btn-cert-list').addEventListener('click', () => runInto($('#security-console'), $('#btn-cert-list'), ['cert', 'list'], 'Listing…'));

// ---- harden ----
$('#btn-hd-apply').addEventListener('click', () => {
  const set = $('#hd-set').value, dry = $('#hd-dry').checked;
  const args = ['harden', set]; if (dry) args.push('--dry-run');
  runInto($('#harden-console'), $('#btn-hd-apply'), args, dry ? 'Checking (dry run)…' : 'Applying…');
});
$('#btn-hd-list').addEventListener('click', () => runInto($('#harden-console'), $('#btn-hd-list'), ['harden', 'list'], 'Loading…'));
$('#btn-hd-restore').addEventListener('click', () => {
  if (!confirm('Restore every hardened setting back to its recorded original value?')) return;
  runInto($('#harden-console'), $('#btn-hd-restore'), ['harden', 'restore'], 'Restoring…');
});

// ---- deep links ----
$('#btn-dl-apk').addEventListener('click', () => {
  const apk = $('#dl-apk').value.trim();
  if (!apk) return alert('enter an APK path first');
  runInto($('#deeplinks-console'), $('#btn-dl-apk'), ['deeplinks', 'apk', apk], 'Extracting…');
});
$('#btn-dl-device').addEventListener('click', () => {
  const pkg = $('#dl-pkg').value.trim();
  if (!pkg) return alert('enter a package name first');
  runInto($('#deeplinks-console'), $('#btn-dl-device'), ['deeplinks', 'device', pkg], 'Extracting…');
});
$('#btn-dl-test').addEventListener('click', () => {
  const url = $('#dl-test').value.trim();
  if (!url) return alert('enter a link to test first');
  runInto($('#deeplinks-console'), $('#btn-dl-test'), ['deeplinks', 'test', url], 'Sending…');
});

// ---- low-level (mtk + engines) ----
$('#btn-mtk-scan').addEventListener('click', () => runInto($('#mtk-console'), $('#btn-mtk-scan'), ['mtk'], 'Scanning for MediaTek BROM/preloader…'));
$('#btn-eng-survey').addEventListener('click', () => runInto($('#engines-console'), $('#btn-eng-survey'), ['engines'], 'Checking…'));
$('#btn-eng-mtk').addEventListener('click', () => runInto($('#engines-console'), $('#btn-eng-mtk'), ['engines', 'install', 'mtk'], 'Installing mtkclient…'));
$('#btn-eng-edl').addEventListener('click', () => runInto($('#engines-console'), $('#btn-eng-edl'), ['engines', 'install', 'edl'], 'Installing edl…'));

// ---- emulator (avd) ----
$('#btn-avd-list').addEventListener('click', () => runInto($('#avd-console'), $('#btn-avd-list'), ['avd', 'list'], 'Loading…'));
$('#btn-avd-create').addEventListener('click', () => {
  const name = $('#avd-name').value.trim(), pkg = $('#avd-pkg').value.trim();
  if (!name || !pkg) return alert('enter both a name and a system image package');
  runInto($('#avd-console'), $('#btn-avd-create'), ['avd', 'create', name, pkg], 'Creating (this can take a while)…');
});
$('#btn-avd-launch').addEventListener('click', () => {
  const name = $('#avd-name').value.trim();
  if (!name) return alert('enter a name first');
  runInto($('#avd-console'), $('#btn-avd-launch'), ['avd', 'launch', name], 'Launching…');
});
$('#btn-avd-delete').addEventListener('click', () => {
  const name = $('#avd-name').value.trim();
  if (!name) return alert('enter a name first');
  if (!confirm(`Delete AVD "${name}"?`)) return;
  runInto($('#avd-console'), $('#btn-avd-delete'), ['avd', 'delete', name], 'Deleting…');
});

// ---- samsung ----
async function loadSamsung() {
  try { $('#sam-engine').textContent = await invoke('samsung_version'); }
  catch { $('#sam-engine').textContent = 'unavailable'; }
  try {
    const devices = await invoke('samsung_devices');
    $('#sam-count').textContent = devices.length;
    $('#sam-devices').innerHTML = devices.length
      ? devices.map(d => `<div class="dev-row mono">${esc(d)}</div>`).join('')
      : '<div class="con-empty">Boot the device into Download Mode (Volume Down + Volume Up + power on most models), then Refresh.</div>';
  } catch (e) {
    // distinct from "0 devices": a real backend failure must not render identically to an
    // honest empty result, or the panel silently lies about which case actually happened.
    $('#sam-count').textContent = '—';
    $('#sam-devices').innerHTML = `<div class="con-empty">Could not check: ${esc(errText(e))}</div>`;
  }
}
loaders.samsung = loadSamsung;
$('#btn-sam-refresh').addEventListener('click', loadSamsung);

$('#btn-sam-check').addEventListener('click', async () => {
  const btn = $('#btn-sam-check'), out = $('#sam-console');
  const val = id => $(id).value.trim() || null;
  btn.disabled = true;
  showBusy(out, 'Running --check-only (writes nothing to the device)…');
  try {
    const r = await invoke('samsung_flash_check', {
      bootloader: val('#sam-bl'), ap: val('#sam-ap'), cp: val('#sam-cp'), csc: val('#sam-csc'), ums: null,
    });
    showResult(out, r);
  } catch (e) {
    showError(out, e);
  } finally {
    btn.disabled = false;
  }
});

// ---- boot ----
loadDevices();
