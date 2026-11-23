'use strict';

/* CesiumLoader iOS —— 页面侧。所有设备操作都通过 window.pywebview.api 走宿主。 */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

let API = null;
let currentMods = [];
let activeLog = null;
let lastTask = null;
let modalModId = null;

/* ---------------------------------------------------------------- 工具 */

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function card(title, body) {
  return `<div class="card"><h3>${esc(title)}</h3>${body}</div>`;
}

function kv(pairs) {
  const html = pairs
    .filter(Boolean)
    .map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`)
    .join('');
  return `<dl>${html}</dl>`;
}

/* ---------------------------------------------------------------- 底部输出 */

function appendLines(lines) {
  if (!lines || !lines.length) return;
  const box = $('#console');
  const stick = box.scrollHeight - box.scrollTop - box.clientHeight < 48;
  for (const line of lines) {
    const row = document.createElement('div');
    row.textContent = line;
    if (line.includes('[FAIL]')) row.className = 'l-fail';
    else if (line.includes('[warn]')) row.className = 'l-warn';
    else if (line.includes('[ok]')) row.className = 'l-ok';
    else if (line.includes('[task]')) row.className = 'l-task';
    box.appendChild(row);
  }
  while (box.childElementCount > 1200) box.removeChild(box.firstChild);
  if (stick) box.scrollTop = box.scrollHeight;
}

function renderTask(task) {
  const label = $('#task-state');
  if (task.running) label.textContent = `运行中：${task.name}`;
  else if (task.ok === true) label.textContent = `已完成：${task.name}`;
  else if (task.ok === false) label.textContent = `失败：${task.name}`;
  else label.textContent = '空闲';

  const busy = !!task.running;
  for (const id of ['#btn-install', '#btn-restore', '#btn-uninstall', '#btn-refresh']) {
    const el = $(id);
    if (el) el.disabled = busy;
  }
  $('#mod-rows').querySelectorAll('.switch').forEach((btn) => { btn.disabled = busy; });
}

/* ---------------------------------------------------------------- 轮询 */

async function poll() {
  if (!API) return;
  let state;
  try {
    state = await API.drain();
  } catch (error) {
    return; // 窗口正在关闭
  }
  appendLines(state.lines);
  renderTask(state.task);

  const finished = lastTask && lastTask.running && !state.task.running;
  lastTask = state.task;
  if (finished) await afterTask(state.task);
}

async function afterTask(task) {
  if (task.ok) {
    const [report, mods] = await Promise.all([API.get_report(), API.get_mods()]);
    if (report) renderReport(report);
    if (mods) { currentMods = mods; renderMods(); }
    await loadLogs(true);
  }
}

/* ---------------------------------------------------------------- 顶栏 */

async function refreshProbe() {
  const el = $('#device-summary');
  let info;
  try {
    info = await API.probe();
  } catch (error) {
    el.textContent = `探测失败：${error}`;
    return false;
  }
  if (!info.connected) {
    el.textContent = info.error || '未连接设备';
    return false;
  }
  const device = info.device || {};
  const game = info.game || {};
  const parts = [
    device.name, device.model, device.ios ? `iOS ${device.ios}` : null,
    game.name ? `${game.name} ${game.version}` : (info.error || null),
  ].filter(Boolean);
  el.textContent = parts.join(' · ');
  return !!info.game;
}

/* ---------------------------------------------------------------- 总览 */

const PATCH_STATE = {
  patched: ['已注入', 'ok'],
  'patched-external': ['已注入（外部安装）', 'ok'],
  clean: ['未注入', 'warn'],
  unknown: ['未知', 'bad'],
};

function renderReport(report) {
  const loader = report.loader || {};
  const patch = PATCH_STATE[report.patch_state] || ['未知', 'bad'];
  const cards = [];

  cards.push(card('游戏', kv([
    ['包名', `<span class="wrap">${esc(report.bundle_id)}</span>`],
    ['版本', esc(report.app_version || '?')],
    ['catalog', esc(report.catalog || '?')],
  ])));

  cards.push(card('补丁状态', `
    <div class="big"><span class="badge ${patch[1]}">${esc(patch[0])}</span></div>
    <div class="muted" style="margin-top:8px">程序集内注入标记：${report.injected ? '有' : '无'}</div>`));

  cards.push(card('代码包', kv([
    ['哈希', `<span class="wrap">${esc(report.code_bundle_hash || '?')}</span>`],
    ['大小', report.bundle_bytes ? `${report.bundle_bytes} B` : '?'],
    ['sha256', `<span class="wrap">${esc(report.bundle_sha256 || '?')}</span>`],
    ['资产数', esc(report.asset_count ?? '?')],
  ])));

  if (loader.present) {
    cards.push(card('加载器', kv([
      ['根目录', `<span class="wrap">${esc(loader.root)}</span>`],
      ['引导 DLL', loader.has_bootstrap ? '有' : '缺'],
      ['安卓 API', loader.has_api ? '有' : '无'],
      ['模组', `${esc(loader.mod_count ?? 0)} 个`],
    ])));
    const launch = loader.mods_ok != null
      ? `<div class="big">ok=${esc(loader.mods_ok)} <span class="muted">failed=${esc(loader.mods_failed ?? 0)}</span></div>`
      : '<div class="muted">还没有启动记录</div>';
    cards.push(card('上次启动', launch +
      (loader.bootstrap_log ? `<div class="muted" style="margin-top:6px">${esc(loader.bootstrap_log)}</div>` : '')));
    if (loader.bootstrap_tail && loader.bootstrap_tail.length) {
      cards.push(card('引导日志尾部', `<pre class="tail">${esc(loader.bootstrap_tail.join('\n'))}</pre>`));
    }
  } else {
    cards.push(card('加载器', '<span class="badge warn">未安装</span>'));
  }

  if (report.markers && report.markers.length) {
    cards.push(card('注入标记', `<div class="mono wrap muted">${esc(report.markers.join('  '))}</div>`));
  }

  $('#cards').innerHTML = cards.join('');
  $('#issues').innerHTML = (report.issues && report.issues.length)
    ? report.issues.map((item) => `<div>${esc(item)}</div>`).join('')
    : '';
  $('#mod-count').textContent = loader.mod_count ?? currentMods.length ?? 0;
}

/* ---------------------------------------------------------------- 模组 */

function sidecarOf(mod) {
  return mod.sidecar || {};
}

function renderMods() {
  const filter = $('#mod-filter').value.trim().toLowerCase();
  const onlyEnabled = $('#only-enabled').checked;

  const rows = currentMods.filter((mod) => {
    if (onlyEnabled && !mod.enabled) return false;
    if (!filter) return true;
    const s = sidecarOf(mod);
    return `${mod.id} ${s.name || ''} ${s.author || ''}`.toLowerCase().includes(filter);
  });

  $('#mod-count').textContent = currentMods.length;
  $('#mod-hint').textContent = currentMods.length
    ? `${rows.length} / ${currentMods.length} 个模组`
    : '';

  if (!currentMods.length) {
    $('#mod-rows').innerHTML = '<tr><td colspan="6" class="muted">还没读到模组 —— 点右上角「刷新」</td></tr>';
    return;
  }

  $('#mod-rows').innerHTML = rows.map((mod) => {
    const s = sidecarOf(mod);
    const platforms = Array.isArray(s.platforms) ? s.platforms : [];
    const name = s.name || mod.id;
    return `<tr class="${mod.enabled ? '' : 'disabled'}">
      <td><button class="switch ${mod.enabled ? 'on' : ''}" data-act="toggle"
                  data-id="${esc(mod.id)}" data-enabled="${mod.enabled}"
                  title="${mod.enabled ? '点击停用' : '点击启用'}"></button></td>
      <td><div class="mod-name">${esc(name)}</div><div class="mod-id-sub">${esc(mod.id)}</div></td>
      <td>${esc(s.version || '–')}</td>
      <td>${esc(s.author || '–')}</td>
      <td>${platforms.map((p) => `<span class="tag">${esc(p)}</span>`).join('') || '–'}</td>
      <td>${mod.has_config
        ? `<button data-act="config" data-id="${esc(mod.id)}">编辑</button>`
        : '<span class="muted">–</span>'}</td>
    </tr>`;
  }).join('');
}

async function onModRowsClick(event) {
  const btn = event.target.closest('[data-act]');
  if (!btn || btn.disabled) return;
  const id = btn.dataset.id;

  if (btn.dataset.act === 'toggle') {
    const enabled = btn.dataset.enabled === 'true';
    btn.disabled = true;
    const result = await API.set_mod_enabled(id, !enabled);
    if (!result.started) {
      btn.disabled = false;
      alert(result.error || '操作没能启动');
    }
    return;
  }

  if (btn.dataset.act === 'config') await openConfig(id);
}

/* ---------------------------------------------------------------- 配置编辑 */

async function openConfig(modId) {
  const result = await API.read_config(modId);
  if (result.error) { alert(result.error); return; }
  modalModId = modId;
  $('#modal-title').textContent = `${modId}/config.json`;
  $('#modal-text').value = result.exists ? result.text : '{\n  \n}';
  const status = $('#modal-status');
  status.className = 'muted';
  status.textContent = result.exists ? result.path : '该模组还没有 config.json，保存会新建一份';
  $('#modal').classList.remove('hidden');
  $('#modal-text').focus();
}

async function saveConfig() {
  const status = $('#modal-status');
  const text = $('#modal-text').value;

  try {
    const parsed = JSON.parse(text);
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
      status.className = 'bad';
      status.textContent = '顶层必须是 JSON 对象';
      return;
    }
  } catch (error) {
    status.className = 'bad';
    status.textContent = `JSON 解析失败：${error.message}`;
    return;
  }

  const result = await API.write_config(modalModId, text);
  if (result.error) {
    status.className = 'bad';
    status.textContent = result.error;
    return;
  }
  status.className = 'ok';
  status.textContent = `已保存 ${result.bytes} B`;
  setTimeout(() => $('#modal').classList.add('hidden'), 700);
}

/* ---------------------------------------------------------------- 日志 */

async function loadLogs(silent) {
  const items = await API.logs();
  const list = $('#log-list');
  if (!items.length) {
    list.innerHTML = '<li class="muted">没有日志文件</li>';
    $('#log-hint').textContent = '';
    return;
  }
  list.innerHTML = items.map((item) => `<li data-name="${esc(item.name)}"
      class="${item.name === activeLog ? 'active' : ''}">${esc(item.name)}
      ${item.bytes != null ? `<span class="size">${item.bytes} B</span>` : ''}</li>`).join('');
  $('#log-hint').textContent = `${items.length} 个文件`;

  if (!activeLog || !items.some((i) => i.name === activeLog)) {
    const preferred = items.find((i) => i.name.startsWith('bootstrap-')) || items[0];
    if (preferred) await showLog(preferred.name);
  } else if (!silent) {
    await showLog(activeLog);
  }
}

async function showLog(name) {
  activeLog = name;
  $$('#log-list li').forEach((li) => li.classList.toggle('active', li.dataset.name === name));
  const view = $('#log-view');
  view.textContent = '读取中…';
  const result = await API.read_log(name);
  view.textContent = result.error ? `读取失败：${result.error}` : (result.text || '(空)');
  view.scrollTop = 0;
}

/* ---------------------------------------------------------------- 操作 */

async function doInstall() {
  const payload = $('#payload-path').value.trim();
  const patch = $('#opt-patch').checked;
  const deploy = $('#opt-deploy').checked;
  if (!patch && !deploy) { alert('至少勾选一项'); return; }
  const result = await API.install(payload || null, patch, deploy);
  if (!result.started) alert(result.error || '没能启动安装');
}

/* ---------------------------------------------------------------- 启动 */

function bind() {
  $$('.tabs button').forEach((btn) => {
    btn.addEventListener('click', () => {
      $$('.tabs button').forEach((b) => b.classList.toggle('active', b === btn));
      $$('.panel').forEach((p) => p.classList.toggle('active', p.id === `tab-${btn.dataset.tab}`));
      if (btn.dataset.tab === 'logs') loadLogs();
    });
  });

  $('#btn-refresh').addEventListener('click', async () => {
    const result = await API.refresh();
    if (!result.started) alert(result.error || '没能启动检测');
  });

  $('#mod-filter').addEventListener('input', renderMods);
  $('#only-enabled').addEventListener('change', renderMods);
  $('#mod-rows').addEventListener('click', onModRowsClick);

  $('#modal-close').addEventListener('click', () => $('#modal').classList.add('hidden'));
  $('#modal-save').addEventListener('click', saveConfig);
  $('#modal').addEventListener('click', (event) => {
    if (event.target.id === 'modal') $('#modal').classList.add('hidden');
  });

  $('#btn-reload-logs').addEventListener('click', () => loadLogs());
  $('#log-list').addEventListener('click', (event) => {
    const li = event.target.closest('li[data-name]');
    if (li) showLog(li.dataset.name);
  });

  $('#btn-pick').addEventListener('click', async () => {
    const result = await API.pick_folder();
    if (result.path) $('#payload-path').value = result.path;
  });
  $('#btn-install').addEventListener('click', doInstall);
  $('#btn-restore').addEventListener('click', async () => {
    if (!confirm('用备份还原代码包？游戏需要完全退出。')) return;
    const result = await API.restore(false);
    if (!result.started) alert(result.error || '没能启动');
  });
  $('#btn-uninstall').addEventListener('click', async () => {
    if (!confirm('还原代码包并删除 Documents/CesiumLoader 整个目录？')) return;
    const result = await API.restore(true);
    if (!result.started) alert(result.error || '没能启动');
  });

  $('#btn-clear').addEventListener('click', () => { $('#console').innerHTML = ''; });
}

async function boot() {
  API = window.pywebview.api;
  bind();
  $('#payload-path').value = await API.default_payload();
  setInterval(poll, 400);
  if (await refreshProbe()) {
    const result = await API.refresh();
    if (!result.started) appendLines([`[FAIL] ${result.error || '检测没能启动'}`]);
  }
}

(function waitForApi() {
  if (window.pywebview && window.pywebview.api) { boot(); return; }
  setTimeout(waitForApi, 60);
})();
