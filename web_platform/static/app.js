/* App UI 自动化测试平台 v1.2 · 前端逻辑 */
'use strict';

/* ---------------- 基础工具 ---------------- */
async function api(url, opts) {
  const res = await fetch(url, Object.assign({ headers: { 'Content-Type': 'application/json' } }, opts));
  const data = await res.json().catch(() => ({ ok: false, msg: '响应解析失败(' + res.status + ')' }));
  if (!res.ok && !data.msg) data.msg = 'HTTP ' + res.status;
  return data;
}
const postJson = (url, body) => api(url, { method: 'POST', body: JSON.stringify(body || {}) });
const del = (url) => api(url, { method: 'DELETE' });
const $ = (sel) => document.querySelector(sel);

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
/* 失败录屏缩略图：点击放大播放（全局委托） */
document.addEventListener('click', (e) => {
  const v = e.target.closest('video.video-thumb');
  if (v && v.dataset.video) { e.preventDefault(); openLightbox(v.dataset.video + '#t=1.5', '录屏'); }
});

/* 状态徽章：run 状态为大写（PASSED…），用例/步骤状态来自 allure 为小写（passed…），
   统一转大写复用同一套 .st-* 样式；broken→ERROR、skipped/unknown→PENDING */
function statusBadge(st) {
  const s = String(st == null ? '' : st).toUpperCase();
  const cls = { BROKEN: 'ERROR', SKIPPED: 'PENDING', UNKNOWN: 'PENDING' }[s] || s;
  return '<span class="status st-' + esc(cls) + '">' + esc(s) + '</span>';
}
/* run 统计：带标签的 通过/失败/异常 三个数值 */
function runStatsHtml(t) {
  return '<span>共 <b>' + (t.total || 0) + '</b> 条</span>' +
    '<span>通过 <b class="num-ok">' + (t.passed || 0) + '</b></span>' +
    '<span>失败 <b class="num-bad">' + (t.failed || 0) + '</b></span>' +
    '<span>异常 <b class="num-err">' + (t.error || 0) + '</b></span>';
}
function fmtTime(s) { return s ? String(s).replace('T', ' ').slice(0, 19) : '-'; }

/* 执行编号显示格式化：20260913_002 → 09-13 · 第2次；cli- 任务显示「CLI · 设备」。
   存储层 id 不变（目录名/外键），仅显示层转换；title 悬停可看原始 id。 */
function formatRunId(id) {
  const s = String(id || '');
  const m = s.match(/^(\d{4})(\d{2})(\d{2})_(\d+)$/);
  if (m) return m[2] + '-' + m[3] + ' · 第' + parseInt(m[4], 10) + '次';
  if (s.startsWith('cli-')) {
    const rest = s.slice(4);
    const i = rest.lastIndexOf('-');
    return i > 0 ? 'CLI · ' + rest.slice(0, i) : s;
  }
  return s;
}

let _toastTimer = null;
function toast(msg, ok = true) {
  const el = $('#toast');
  el.textContent = msg;
  el.className = ok ? 'ok' : 'bad';
  el.classList.add('show');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
}

/* 自绘确认模态（替代原生 confirm） */
function confirmModal(title, msg, danger) {
  return new Promise((resolve) => {
    const mask = $('#mask'), mTitle = $('#mTitle'), mMsg = $('#mMsg'),
          btnOk = $('#mOk'), btnCancel = $('#mCancel');
    mTitle.textContent = title;
    mMsg.textContent = msg;
    btnOk.className = danger ? 'danger' : '';
    btnOk.textContent = danger ? '删除' : '确定';
    mask.classList.add('show');
    const done = (v) => { mask.classList.remove('show'); btnOk.onclick = btnCancel.onclick = null; resolve(v); };
    btnOk.onclick = () => done(true);
    btnCancel.onclick = () => done(false);
    mask.onclick = (e) => { if (e.target === mask) done(false); };
  });
}

/* ---------------- 侧边栏（全局） ---------------- */
function renderSidebar(active) {
  const sb = $('#sidebar');
  if (!sb) return;
  const items = [
    ['/', '📊', '首页'],
    ['/run', '🚀', '执行'],
    ['/report', '📈', '测试报告'],
    ['/debug', '🧪', '代码审查'],
    ['/admin', '🗂', '管理后台'],
    ['/locator', '🎯', '元素定位器'],
  ];
  sb.innerHTML =
    '<div class="brand"><div class="logo">🤖</div><div>AppUI 自动化<br><small>测试平台 v1.2</small></div></div>' +
    '<nav>' + items.map(([href, ico, name]) =>
      '<a href="' + href + '" class="' + (href === active ? 'on' : '') + '"><span class="ico">' + ico + '</span>' + name + '</a>'
    ).join('') + '</nav>' +
    '<div class="foot">' +
    '<span><i class="dot ok" id="dotDevice"></i>设备 <span id="footDevice">…</span></span>' +
    '<span><i class="dot ok" id="dotAppium"></i>Appium <span id="footAppium">…</span></span>' +
    '</div>';
  pollFootStatus();
  setInterval(pollFootStatus, 10000);
  /* 元素定位器入口：/locator 已是平台内嵌页（iframe 加载，无整页白闪），普通跳转即可；
     服务未启动时由 /locator 页面自己调用 /api/locator/start 拉起 */
}

async function pollFootStatus() {
  try {
    const st = await api('/api/status');
    const d = $('#dotDevice'), f = $('#footDevice');
    if (d) {
      const on = st.device_online > 0;
      d.className = 'dot ' + (on ? 'ok' : 'bad');
      // 在线数量 + 首台设备序列号（长序列号截断，悬停看全）
      let txt = on ? '在线×' + st.device_online : '离线';
      if (on && st.devices && st.devices[0] && st.devices[0].udid) {
        const udid = st.devices[0].udid;
        txt += ' · ' + (udid.length > 14 ? udid.slice(0, 13) + '…' : udid);
        f.title = '设备序列号: ' + udid;
      }
      f.textContent = txt;
    }
    const d2 = $('#dotAppium'), f2 = $('#footAppium');
    if (d2) {
      d2.className = 'dot ' + (st.appium.ok ? 'ok' : 'bad');
      f2.textContent = st.appium.ok ? '正常' : '不可用';
    }
  } catch (e) {}
}

/* ---------------- 首页 ---------------- */
async function initIndex() {
  renderSidebar('/');
  const refresh = async () => { await refreshStats(); await loadRunsTable('#recentList', true, 10); };
  $('#btnClearAll').addEventListener('click', clearAllRuns);
  await refresh();
  setInterval(refresh, 8000);
}

async function refreshStats() {
  try {
    const d = await api('/api/runs');
    const runs = d.runs || [];
    const pass = runs.filter(r => r.status === 'PASSED').length;
    const fail = runs.filter(r => r.status === 'FAILED' || r.status === 'ERROR').length;
    $('#cardRuns').textContent = runs.length;
    $('#cardPass').textContent = pass;
    $('#cardFail').textContent = fail;
    $('#cardRate').textContent = runs.length ? Math.round(pass / runs.length * 100) + '%' : '—';
  } catch (e) {}
}

/* ---------------- 执行记录渲染（首页/执行页共用） ----------------
   设备列显示真实型号（runner 启动时从 adb 取，如 FGD AL00=华为）；
   旧历史记录无 device_model 时回退显示 conf 别名 device_desc */
function runRowHtml(r, withOps) {
  const dev = r.device_model || r.device_desc || '-';
  return '<tr>' +
    '<td><a class="runlink" href="/runs/' + esc(r.run_id) + '" title="原始编号: ' + esc(r.run_id) + '">' + esc(formatRunId(r.run_id)) + '</a></td>' +
    '<td>' + fmtTime(r.start_time) + '</td>' +
    '<td title="' + esc(dev) + ' · ' + esc(r.udid || '') + '">' + esc(dev) + '</td>' +
    '<td title="' + esc(r.app_package) + '">' + esc((r.app_package || '-').split('.').pop()) + '</td>' +
    '<td><b>' + r.total + '</b> / <span style="color:#4ade80">' + r.passed + '</span> / <span style="color:#ff8787">' + r.failed + '</span></td>' +
    '<td>' + statusBadge(r.status) + '</td>' +
    (withOps ? '<td><div class="ops">' +
      '<a class="btn ghost mini" style="text-decoration:none" href="/runs/' + esc(r.run_id) + '">详情</a>' +
      '<button class="ghost mini" onclick="openReportFor(\'' + esc(r.run_id) + '\', this)">报告</button>' +
      '<button class="mini danger-ghost" onclick="deleteRunFor(\'' + esc(r.run_id) + '\')">删除</button>' +
      '</div></td>' : '') +
    '</tr>';
}

function renderRunRows(sel, runs, withOps) {
  const tbody = $(sel);
  if (!tbody) return;
  if (!runs.length) {
    tbody.innerHTML = '<tr><td colspan="7"><div class="empty"><span class="eico">🗂️</span>暂无执行记录<br>' +
      '<a class="runlink" href="/run">去执行页开始第一次测试 →</a></div></td></tr>';
    return;
  }
  tbody.innerHTML = runs.map(r => runRowHtml(r, withOps)).join('');
}

/* 首页：只取最近 N 条，无分页 */
async function loadRunsTable(sel, withOps, limit) {
  const d = await api('/api/runs');
  renderRunRows(sel, (d.runs || []).slice(0, limit || 100), withOps);
}

/* ---------------- 分页（每页 10 条） ---------------- */
const PAGE_SIZE = 10;
let _runsPage = 1, _reportPage = 1;

function renderPager(sel, page, pages, onPage, total) {
  const el = $(sel);
  if (!el) return;
  if (!total) { el.innerHTML = ''; return; }
  const totalHtml = '<span class="muted" style="align-self:center;margin-left:8px">共 ' + total + ' 条</span>';
  // 单页时不显示页码按钮，但保留「共 N 条」让分页始终可见
  if (pages <= 1) { el.innerHTML = totalHtml; return; }
  const btn = (p, label, cur, dis) =>
    '<button class="' + (cur ? 'mini' : 'ghost mini') + '"' + (dis ? ' disabled' : '') +
    ' data-p="' + p + '">' + label + '</button>';
  let html = btn(page - 1, '‹', false, page <= 1);
  const s = Math.max(1, Math.min(page - 2, pages - 4));
  const e = Math.min(pages, s + 4);
  if (s > 1) html += '<span class="muted" style="align-self:center">…</span>';
  for (let p = s; p <= e; p++) html += btn(p, p, p === page, false);
  if (e < pages) html += '<span class="muted" style="align-self:center">…</span>';
  html += btn(page + 1, '›', false, page >= pages);
  html += totalHtml;
  el.innerHTML = html;
  el.querySelectorAll('button[data-p]').forEach(b =>
    b.addEventListener('click', () => onPage(parseInt(b.dataset.p, 10))));
}

/* 执行页：执行记录已并入测试报告页，这里不再需要分页版加载；
   保留 renderPager/分页状态供报告页使用 */
async function loadRunsPaged() {}

async function deleteRunFor(runId) {
  const yes = await confirmModal('删除执行记录', '将删除 ' + runId + ' 的全部数据（Allure 结果、日志），不可恢复。', true);
  if (!yes) return;
  const d = await del('/api/runs/' + runId);
  toast(d.msg || (d.ok ? '已删除' : '删除失败'), d.ok);
  if (d.ok && _activeDetailRun === runId) {
    clearInterval(_detailTimer); _detailTimer = null;
    _activeDetailRun = null;
    const box = $('#runDetail');
    if (box) box.innerHTML = '<div class="empty"><span class="eico">👈</span>从上方列表选择一条执行记录查看详情</div>';
    // run_detail 独立页：删完回到报告页（当前 run 已不存在）
    if (document.body.dataset.page === 'detail') { location.href = '/report'; return; }
  }
  refreshAfterOps();
}

async function clearAllRuns() {
  const yes = await confirmModal('清空全部执行记录', '将删除所有已结束执行记录的全部数据（正在运行的保留），不可恢复。', true);
  if (!yes) return;
  const d = await postJson('/api/runs/clear', {});
  toast(d.msg || '已清空', d.ok);
  if (d.ok && _activeDetailRun) {
    clearInterval(_detailTimer); _detailTimer = null;
    _activeDetailRun = null;
    const box = $('#runDetail');
    if (box) box.innerHTML = '<div class="empty"><span class="eico">👈</span>从上方列表选择一条执行记录查看详情</div>';
  }
  refreshAfterOps();
}

function refreshAfterOps() {
  const page = document.body.dataset.page;
  if (page === 'index') { refreshStats(); loadRunsTable('#recentList', true, 10); }
  else if (page === 'report') { loadReportList(); }
}

/* ---------------- 执行页（配置+设备+用例+记录 合并） ---------------- */
/* Appium 状态徽标 + 启动按钮（执行配置区） */
async function refreshAppiumBadge() {
  const badge = $('#appiumBadge'), btn = $('#btnAppium');
  if (!badge || !btn) return;
  const d = await api('/api/status');
  if (d.appium && d.appium.ok) {
    badge.textContent = 'Appium 已就绪'; badge.className = 'pill ok';
    btn.disabled = true; btn.textContent = '✓ 已启动';
  } else {
    badge.textContent = 'Appium 未启动'; badge.className = 'pill';
    btn.disabled = false; btn.textContent = '🟢 启动 Appium';
  }
}
/* 执行配置参数帮助：悬停问号显示获取途径命令；移出延迟 0.3s 消失，
   期间移入气泡则保持可见，气泡内「复制」按钮可复制全文 */
function bindParamHelp() {
  let tip = document.getElementById('paramHelpTip');
  if (!tip) {
    tip = document.createElement('div');
    tip.id = 'paramHelpTip';
    tip.className = 'help-tip';
    tip.style.display = 'none';
    document.body.appendChild(tip);
    tip.addEventListener('mouseenter', () => clearTimeout(tip._hideTimer));   // 移入气泡：取消隐藏
    tip.addEventListener('mouseleave', () => {
      tip._hideTimer = setTimeout(() => { tip.style.display = 'none'; }, 300);
    });
    tip.addEventListener('click', async (e) => {
      const btn = e.target.closest('.tip-copy');
      if (!btn) return;
      const text = (tip.getAttribute('data-cmd') || tip.getAttribute('data-text') || '');
      try { await navigator.clipboard.writeText(text); }
      catch (err) {
        const ta = document.createElement('textarea');
        ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); } catch (e2) {}
        document.body.removeChild(ta);
      }
      btn.textContent = '✓ 已复制'; btn.classList.add('copied');
      setTimeout(() => { btn.textContent = '复制'; btn.classList.remove('copied'); }, 1500);
    });
  }
  document.querySelectorAll('.field .help-icon').forEach(icon => {
    if (icon.dataset.bound) return;
    icon.dataset.bound = '1';
    icon.addEventListener('mouseenter', () => {
      clearTimeout(tip._hideTimer);
      const text = icon.getAttribute('data-help') || '';
      tip.setAttribute('data-text', text);
      // 文案 + 右上角复制按钮（复制全文，不含按钮字样）
      tip.innerHTML = '<button class="tip-copy">复制</button>' + esc(text);
      tip.style.display = 'block';
      const r = icon.getBoundingClientRect();
      const left = Math.min(r.left - 40, window.innerWidth - 400);
      tip.style.left = Math.max(10, left) + 'px';
      const top = r.bottom + 6;
      const estH = text.length > 90 ? 150 : 90;
      tip.style.top = (top + estH > window.innerHeight - 10 ? Math.max(10, r.top - estH - 10) : top) + 'px';
    });
    icon.addEventListener('mouseleave', () => {
      clearTimeout(tip._hideTimer);
      tip._hideTimer = setTimeout(() => { tip.style.display = 'none'; }, 300);   // 延迟 0.3s
    });
  });
}

/* 启动 Appium：后端立即拉起并返回（异步），前端轮询状态直到就绪（上限 45s）。
   冷启动可能超过 20s，同步等待会让请求超时且状态不明确 */
async function startAppium() {
  const btn = $('#btnAppium');
  btn.disabled = true; btn.textContent = '⏳ 启动中…';
  const d = await postJson('/api/appium/start', {});
  if (!d.ok) {
    btn.disabled = false; btn.textContent = '🟢 启动 Appium';
    toast(d.msg || '启动失败', false);
    return;
  }
  toast(d.already ? 'Appium 已在运行' : 'Appium 启动中，请稍候…', true);
  const deadline = Date.now() + 45000;
  const poll = async () => {
    const s = await api('/api/status');
    if (s.appium && s.appium.ok) {
      toast('Appium 已就绪');
      refreshAppiumBadge();
      return;
    }
    if (Date.now() > deadline) {
      toast('Appium 启动超时（45s），请查看 logs/appium.log', false);
      refreshAppiumBadge();
      return;
    }
    btn.textContent = '⏳ 启动中… ' + Math.ceil((deadline - Date.now()) / 1000) + 's';
    setTimeout(poll, 1000);
  };
  poll();
}

async function initRun() {
  renderSidebar('/run');
  await loadExecDefaults();
  await loadCaseTree();
  $('#btnStart').addEventListener('click', startRun);
  $('#btnAppium').addEventListener('click', startAppium);
  refreshAppiumBadge();
  setInterval(refreshAppiumBadge, 10000);
  bindParamHelp();
  $('#btnStop').addEventListener('click', stopRun);
  $('#btnSelectAll').addEventListener('click', () => setAllChecked(true));
  $('#btnSelectNone').addEventListener('click', () => setAllChecked(false));
  $('#confSel').addEventListener('change', () => loadExecDefaults($('#confSel').value));
}

async function loadExecDefaults(conf) {
  const url = '/api/exec_defaults' + (conf ? '?conf=' + encodeURIComponent(conf) : '');
  const d = await api(url);
  if (!d.ok) return toast(d.msg || '加载执行配置失败', false);
  const sel = $('#confSel');
  sel.innerHTML = (d.confs || []).map(f =>
    '<option value="' + esc(f) + '"' + (f === d.defaults.conf_file ? ' selected' : '') + '>' +
    esc(f.split('/').pop()) + '</option>').join('');
  // 默认值填充：当前在线设备 + conf 默认
  $('#inUdid').value = d.defaults.udid || '';
  $('#inPackage').value = d.defaults.app_package || '';
  $('#inActivity').value = d.defaults.app_activity || '';
  // 设备状态卡：在线状态以 adb 实测为准（device_online），conf 里的 udid 仅作预填
  const online = !!d.defaults.device_online;
  $('#devState').innerHTML =
    '<span class="pill ' + (online ? 'ok' : 'bad') + '">' + (online ? '● 设备在线' : '● 未检测到在线设备') + '</span>' +
    '<span>设备 <b>' + esc(d.defaults.udid || '-') + '</b>' +
    (!online && d.defaults.udid ? ' <span class="muted" style="font-size:12px">(conf 预填，未连接)</span>' : '') + '</span>' +
    '<span>型号 <b>' + esc(d.defaults.model || '-') + '</b></span>' +
    '<span>Appium <b>' + (d.defaults.appium_ok ? '<span style="color:#4ade80">正常</span>' : '<span style="color:#ff8787">不可用</span>') + '</b></span>' +
    '<span>服务 <b>' + esc(d.defaults.server || '-') + '</b></span>' +
    (d.defaults.occupied ? '<span class="pill bad">有任务执行中</span>' : '');
}

async function loadCaseTree() {
  const d = await api('/api/cases');
  const box = $('#caseTree');
  if (!d.ok || !(d.tree || []).length) {
    box.innerHTML = '<div class="empty"><span class="eico">📂</span>cases/app_ui 下没有可执行用例</div>';
    return;
  }
  let html = '<ul>';
  d.tree.forEach(f => {
    html += '<li><label class="chk"><input type="checkbox" data-file="' + esc(f.file) + '" class="ck-file">' +
      '<span class="file">' + esc(f.file.split('/').pop()) + '</span> <span class="muted">' + esc(f.file) + '</span></label><ul>';
    f.methods.forEach(m => {
      const node = f.file + '::' + f.class_name + '::' + m;
      html += '<li><label class="chk"><input type="checkbox" data-node="' + esc(node) + '" class="ck-node">' +
        '<span class="cls">' + esc(f.class_name) + '::' + esc(m) + '</span></label></li>';
    });
    html += '</ul></li>';
  });
  html += '</ul>';
  box.innerHTML = html;
  box.addEventListener('change', (e) => {
    if (e.target.classList.contains('ck-file')) {
      Array.from(box.querySelectorAll('input[data-node]')).forEach(n => {
        if (n.dataset.node.startsWith(e.target.dataset.file + '::')) n.checked = e.target.checked;
      });
    }
  });
}

function setAllChecked(v) { document.querySelectorAll('#caseTree input[type=checkbox]').forEach(n => n.checked = v); }
function selectedCases() { return Array.from(document.querySelectorAll('#caseTree .ck-node:checked')).map(n => n.dataset.node); }

async function startRun() {
  const conf = $('#confSel').value;
  const cases = selectedCases();
  if (!conf) return toast('请选择默认配置来源(conf)', false);
  if (!cases.length) return toast('请至少勾选一个用例', false);
  const btn = $('#btnStart');
  btn.disabled = true; btn.textContent = '启动中…';
  const body = {
    conf_file: conf,
    case_nodes: cases,
    overrides: {
      udid: $('#inUdid').value.trim(),
      appPackage: $('#inPackage').value.trim(),
      appActivity: $('#inActivity').value.trim(),
    },
  };
  const d = await postJson('/api/run', body);
  btn.disabled = false; btn.textContent = '🚀 开始执行';
  if (!d.ok) return toast(d.msg || '启动失败', false);
  $('#execArea').style.display = 'block';
  $('#execArea').scrollIntoView({ behavior: 'smooth', block: 'start' });
  toast('任务 ' + d.run_id + ' 已启动');
  pollTask(d.run_id);
}

let _pollTimer = null, _logOffset = 0;
function pollTask(runId) {
  clearInterval(_pollTimer); _logOffset = 0;
  const box = $('#logBox'); box.innerHTML = '';
  _pollTimer = setInterval(async () => {
    const d = await api('/api/run/' + runId);
    if (!d.ok) { clearInterval(_pollTimer); return; }
    const t = d.task;
    $('#runIdNow').textContent = t.run_id;
    $('#runStatusNow').innerHTML = statusBadge(t.status);
    $('#runStatsNow').textContent = '共 ' + t.total + ' · 通过 ' + t.passed + ' · 失败 ' + t.failed + ' · 异常 ' + (t.error || 0);
    const done = t.passed + t.failed + t.error + t.skipped;
    $('#runProgress').style.width = (t.total ? Math.min(100, Math.round(done / t.total * 100)) : 0) + '%';
    $('#btnStop').disabled = !(t.status === 'RUNNING' || t.status === 'PENDING');
    $('#btnGoDetail').onclick = () => location.href = '/runs/' + runId;
    const lg = await api('/api/run/' + runId + '/log?offset=' + _logOffset);
    if (lg.ok) { _logOffset = lg.offset; renderLog(lg.lines); }
    if (t.status !== 'RUNNING') {
      clearInterval(_pollTimer);
      if (t.error_msg) toast('任务异常: ' + t.error_msg, false);
      else toast('任务结束: ' + t.status + ' → 去「测试报告」查看用例明细与截图', t.status === 'PASSED');
    }
  }, 1500);
}

/* 日志降噪：按「对定位问题有没有用」过滤展示（原始日志文件不动）。
   1) selenium 内部包装栈（errorhandler/check_response 的实现行）——只保留最终错误消息与 Appium 端 Stacktrace；
   2) DeprecationWarning 兼容警告块——与业务失败无关；
   3) live log 的分节头与无关空行——纯噪声 */
function _logNoise(l) {
  if (/^-{10,} live log (setup|call|teardown) -{10,}$/.test(l)) return true;
  if (/^INFO     video_evidence:conftest\.py:85 录屏已开始/.test(l)) return false;  // 证据链保留
  if (/DeprecationWarning: |warnings\.warn\(|appium_connection\.py:\d+|webdriver\.py:245/.test(l)) return true;
  if (/super\(\)\.__init__\(remote_server_addr|pool_manager_init_args|setting remote_server_addr|get_timeout\(\) in RemoteConnection|desired_capabilities argument is deprecated/.test(l)) return true;
  if (/^\s*-- Docs: https:\/\/docs\.pytest\.org.*warnings\.html\s*$/.test(l)) return true;
  if (/^cases\/\S+::\S+$/.test(l) && !/PASSED|FAILED|ERROR|SKIPPED/.test(l)) return true; // warnings summary 的裸用例名行
  if (/^\s*(:Args:|:Raises:|:Returns:|screen: str|status = response|value = None|value_json|exception_class|error_codes|if isinstance\(status|if isinstance\(value|if not value|if message == |screen = None|stacktrace = None|st_value = value|for error_code|error_info = |if not status|try:|except ValueError|if len\(value\) == 1|else:|pass$)/.test(l)) return true;
  if (l.includes('errorhandler.py:')) return true;
  if (/^\s*"screen" in value|^\s*"data" in value|^\s*"alert" in value/.test(l)) return true;
  if (/^Captured log setup$|^Captured stdout setup$|^Captured log call$/.test(l)) return false; // 分节头保留
  return false;
}
function renderLog(lines, boxSel) {
  const box = boxSel ? $(boxSel) : $('#logBox');
  if (!box || !lines.length) return;
  const nearBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 60;
  lines.filter(l => !_logNoise(l)).forEach(l => {
    let cls = '';
    if (/断言「.+」失败|FAILED|ERROR|TimeoutException|AssertionError/.test(l)) cls = 'fail';
    else if (/断言「.+」通过|PASSED/.test(l)) cls = 'pass';
    else if (/toast「.+」未出现|WARNING/.test(l)) cls = 'warn';
    else if (/^[-=]+$|^platform darwin|^cachedir|^rootdir|^plugins/.test(l)) cls = 'dim';
    const div = document.createElement('div');
    if (cls) div.className = cls;
    div.textContent = l;
    box.appendChild(div);
  });
  if (nearBottom) box.scrollTop = box.scrollHeight;
}

async function stopRun() {
  const runId = $('#runIdNow').textContent;
  if (!runId || runId === '-') return;
  const d = await postJson('/api/run/' + runId + '/stop', {});
  toast(d.msg || '停止信号已发送', d.ok);
}

/* ---------------- 执行详情页 ---------------- */
let _detailTimer = null;

async function initRunDetail() {
  renderSidebar('/run');
  const runId = document.body.dataset.runId;
  await renderRunDetail('#detailBody', runId);
}

/* ---------------- 详情组件：run 概要 + 用例执行记录 + 断言截图 + 执行日志 ----------------
   自建视图，直接解析 allure-results；报告页「详情」与 run_detail 页共用 */
let _activeDetailRun = null, _activeSel = null;

function shotHtml(runId, shot) {
  const src = '/api/runs/' + encodeURIComponent(runId) + '/res/' + encodeURIComponent(shot.source);
  return '<img class="thumb" src="' + src + '" title="' + esc(shot.name || shot.source) + '"' +
    ' onclick="openLightbox(\'' + src + '\', \'' + esc(shot.name || shot.source) + '\')">';
}

function caseRowHtml(runId, c, idx) {
  const dur = c.duration_ms ? (c.duration_ms / 1000).toFixed(1) + 's' : '-';
  const steps = c.steps || [];
  const shots = c.screenshots || [];
  const stepHtml = steps.length ? '<ul class="steps">' + steps.map(s => {
    const ss = s.attachments || [];
    return '<li class="st-' + esc(s.status) + '"><span class="sico">' +
      (s.status === 'passed' ? '✓' : s.status === 'failed' ? '✗' : '○') + '</span>' +
      esc(s.name) +
      (ss.length ? '<span class="shots">' + ss.map(a => shotHtml(runId, a)).join('') + '</span>' : '') +
      '</li>';
  }).join('') + '</ul>' : '';
  const errHtml = c.error_message ? '<div class="err">' + esc(c.error_message) + '</div>' : '';
  const oldShots = (!steps.length && shots.length)
    ? '<div class="shots">' + shots.map(a => shotHtml(runId, a)).join('') + '</div>' : '';
  const none = (!steps.length && !shots.length)
    ? '<p class="muted">该用例无步骤/截图数据（旧版执行记录，仅保留统计）</p>' : '';
  return '<tr class="case-row"><td class="xpand"><button class="ghost mini" data-t="' + idx + '">展开</button></td>' +
    '<td>' + esc(c.name) + '</td><td>' + statusBadge(c.status) + '</td>' +
    '<td class="muted">' + dur + '</td><td>' + shots.length + ' 图</td></tr>' +
    '<tr class="detail-row" data-t="' + idx + '" style="display:none"><td colspan="5">' +
    stepHtml + errHtml + oldShots + none + '</td></tr>';
}

async function renderRunDetail(sel, runId) {
  _activeDetailRun = runId; _activeSel = sel;
  clearInterval(_detailTimer); _detailTimer = null;
  const box = $(sel);
  if (!box) return;
  box.innerHTML = '<div class="card"><div class="empty">加载中…</div></div>';
  const [d, c] = await Promise.all([
    api('/api/run/' + runId),
    api('/api/run/' + runId + '/cases'),
  ]);
  if (!d.ok) {
    box.innerHTML = '<div class="card"><div class="empty"><span class="eico">🫥</span>' + esc(d.msg || '任务不存在') + '</div></div>';
    return;
  }
  const t = d.task;
  const cases = c.ok ? c.cases : [];
  const running = t.status === 'RUNNING' || t.status === 'PENDING';
  const isCli = t.source === 'cli';   // 命令行执行导入：无平台实时日志，不能生成报告/删除
  // 按用例文件维度分组（用例文件 = 一个项目的用例集合，执行也按文件为单位）
  const groups = [];
  const byFile = {};
  cases.forEach((c2, i) => {
    const file = (c2.full_name || c2.name).split('::')[0] || '（未知文件）';
    if (!byFile[file]) { byFile[file] = []; groups.push(file); }
    byFile[file].push({ c: c2, i: i });
  });
  const groupRows = groups.map(f => {
    const list = byFile[f];
    const p = list.filter(x => x.c.status === 'passed').length;
    const fl = list.filter(x => x.c.status === 'failed').length;
    const br = list.filter(x => x.c.status === 'broken').length;
    const sk = list.filter(x => x.c.status === 'skipped').length;
    const stat = [p + ' 过', fl + ' 失败', br + ' 异常', sk + ' 跳过'].filter((s, k) => [p, fl, br, sk][k] > 0).join(' · ');
    const fileName = f.split('/').pop();
    return '<tr class="file-group-row"><td colspan="5">📁 <b>' + esc(fileName) + '</b>' +
      '<span class="muted" style="margin-left:8px">' + esc(f) + '</span>' +
      '<span class="muted" style="margin-left:auto">' + list.length + ' 条' + (stat ? ' · ' + stat : '') + '</span></td></tr>' +
      list.map(x => caseRowHtml(runId, x.c, x.i)).join('');
  }).join('');
  const emptyText = running ? '执行进行中，用例数据产生后在此展示'
    : (t.status === 'STOPPED' ? '执行被停止，未产生用例结果数据（停止过早，用例尚未执行完任何一条）'
    : '该 run 没有用例数据（allure-results 缺失或已删除）');
  const casesHtml = cases.length ? '<div class="tblwrap mt"><table><thead><tr><th></th><th>用例</th><th>结果</th><th>耗时</th><th>截图</th></tr></thead><tbody>' +
      groupRows + '</tbody></table></div>' :
      '<div class="empty mt"><span class="eico">📄</span>' + esc(emptyText) + '</div>';
  box.innerHTML =
    '<div class="card">' +
    '<div class="cardhead"><h3>用例执行记录 <span class="muted">· ' + esc(runId) + '</span>' +
    (isCli ? ' <span class="pill">命令行执行导入</span>' : '') + '</h3>' +
    '<div class="ops">' +
    '<button class="ghost mini" onclick="openReportFor(\'' + esc(runId) + '\', this)">打开报告</button>' +
    (isCli ? '' : '<button class="mini danger-ghost" onclick="deleteRunFor(\'' + esc(runId) + '\')">删除本记录</button>') +
    '</div></div>' +
    '<div class="meta"><span>状态 ' + statusBadge(t.status) + '</span>' +
    '<span>设备 <b>' + esc(t.device_model || t.device_desc) + ' / ' + esc(t.udid) + '</b></span>' +
    '<span>App <b>' + esc(t.app_package) + '</b></span>' +
    '<span>开始 <b>' + fmtTime(t.start_time) + '</b></span>' +
    runStatsHtml(t) +
    (running ? '<span class="pill ok">执行中</span>' : '') + '</div>' +
    (t.error_msg ? '<p class="mt" style="color:#ff8787">' + esc(t.error_msg) + '</p>' : '') +
    casesHtml +
    '</div>' +
    '<div class="card"><div class="cardhead"><h3>执行日志 <span class="muted" id="logCount"></span>' +
    '<button class="ghost mini" id="btnCopyLog" style="margin-left:10px">📋 复制日志</button></h3></div>' +
    '<div class="logbox" id="detailLogBox"></div></div>' +
    '<details class="adv-info"><summary>高级信息（原始数据路径，研发排障用）</summary>' +
    '<div class="kv"><span>Allure 数据路径</span>' +
    '<code>' + esc(t.allure_dir || '-') + '</code>' +
    '<button class="ghost mini" data-copy="' + esc(t.allure_dir || '') + '">复制</button></div>' +
    '<div class="kv"><span>报告目录</span>' +
    '<code>' + esc(t.report_dir || (t.source === 'cli' ? '（打开报告时生成到 allure 数据同目录）' : 'output/runs/' + esc(runId) + '/report')) + '</code>' +
    '<button class="ghost mini" data-copy="' + esc(t.report_dir || '') + '">复制</button></div>' +
    '</details>';
  // 高级信息路径复制
  box.addEventListener('click', async (e) => {
    const cp = e.target.closest('[data-copy]');
    if (cp && cp.dataset.copy) {
      try { await navigator.clipboard.writeText(cp.dataset.copy); }
      catch (err) {
        const ta = document.createElement('textarea');
        ta.value = cp.dataset.copy; ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); } catch (e2) {}
        document.body.removeChild(ta);
      }
      const orig = cp.textContent; cp.textContent = '✓ 已复制';
      setTimeout(() => { cp.textContent = orig; }, 1500);
    }
  });
  // 复制日志（过滤后的展示内容）
  box.addEventListener('click', async (e) => {
    if (e.target.closest('#btnCopyLog')) {
      const lb = document.getElementById('detailLogBox');
      const text = lb ? lb.innerText : '';
      const n = text.split('\n').length;
      try {
        await navigator.clipboard.writeText(text);
        toast('日志已复制（' + n + ' 行）');
      } catch (err) {
        // 兜底：页面未聚焦等场景 Clipboard API 不可用，用隐藏 textarea + execCommand
        const ta = document.createElement('textarea');
        ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); toast('日志已复制（' + n + ' 行）'); }
        catch (e2) { toast('复制失败：' + e2, false); }
        document.body.removeChild(ta);
      }
    }
  });
  // 用例行展开/收起（事件委托，避免 8s 轮询重建后按钮失效）
  box.addEventListener('click', (e) => {
    const b = e.target.closest('button[data-t]');
    if (b) {
      const tr = box.querySelector('tr.detail-row[data-t="' + b.dataset.t + '"]');
      if (tr) tr.style.display = tr.style.display === 'none' ? '' : 'none';
    }
  });
  // 日志：全量加载；RUNNING 时增量轮询
  const lg0 = await api('/api/run/' + runId + '/log?offset=0');
  if (lg0.ok) { $('#logCount').textContent = '共 ' + lg0.lines.length + ' 行'; renderLog(lg0.lines, '#detailLogBox'); }
  if (running) {
    let off = lg0.ok ? lg0.offset : 0;
    _detailTimer = setInterval(async () => {
      const lg = await api('/api/run/' + runId + '/log?offset=' + off);
      if (lg.ok) { off = lg.offset; $('#logCount').textContent = '共 ' + off + ' 行'; renderLog(lg.lines, '#detailLogBox'); }
      const st = await api('/api/run/' + runId);
      if (st.ok && st.task.status !== 'RUNNING' && st.task.status !== 'PENDING') {
        clearInterval(_detailTimer); _detailTimer = null;
        renderRunDetail(_activeSel, runId); // 收尾：刷新最终状态与用例
      } else if (st.ok) {
        const tb = box.querySelector('.meta');
        if (tb) {
          const t2 = st.task;
          tb.innerHTML = '<span>状态 ' + statusBadge(t2.status) + '</span>' +
            '<span>设备 <b>' + esc(t2.device_model || t2.device_desc) + ' / ' + esc(t2.udid) + '</b></span>' +
            '<span>App <b>' + esc(t2.app_package) + '</b></span>' +
            runStatsHtml(t2) +
            '<span class="pill ok">执行中</span>';
        }
      }
    }, 3000);
  }
}

async function showRunDetail(runId) {
  const box = $('#runDetail');
  if (!box) return;
  box.scrollIntoView({ behavior: 'smooth', block: 'start' });
  await renderRunDetail('#runDetail', runId);
}

/* 截图 lightbox（点击缩略图放大） */
function openLightbox(src, name) {
  let lb = $('#lightbox');
  if (!lb) { lb = document.createElement('div'); lb.id = 'lightbox'; document.body.appendChild(lb); }
  const isVideo = /\.(mp4|webm|mov)(\?|#|$)/.test(src) || src.includes('#t=');
  lb.innerHTML = (isVideo
    ? '<video src="' + src + '" controls autoplay style="max-width:90vw;max-height:86vh;border-radius:8px;box-shadow:0 20px 60px rgba(0,0,0,.5)"></video>'
    : '<img src="' + src + '" alt="">') + '<button class="lb-close">✕</button>';
  lb.classList.add('show');
  lb.onclick = (e) => { if (e.target === lb || e.target.closest('.lb-close')) lb.classList.remove('show'); };
}

/* ---------------- 测试报告页 ---------------- */
async function initReport() {
  renderSidebar('/report');
  $('#btnClearAll3').addEventListener('click', clearAllRuns);
  await loadReportList();
  setInterval(loadReportList, 8000);
}

/* 报告页：列表分页 */
async function loadReportList() {
  const d = await api('/api/runs');
  const tb = $('#reportList');
  const runs = d.runs || [];
  if (!runs.length) {
    tb.innerHTML = '<tr><td colspan="6"><div class="empty"><span class="eico">📈</span>暂无执行记录，先生成一次执行</div></td></tr>';
    const pg = $('#reportPager'); if (pg) pg.innerHTML = '';
    return;
  }
  const pages = Math.max(1, Math.ceil(runs.length / PAGE_SIZE));
  if (_reportPage > pages) _reportPage = pages;
  if (_reportPage < 1) _reportPage = 1;
  const slice = runs.slice((_reportPage - 1) * PAGE_SIZE, _reportPage * PAGE_SIZE);
  tb.innerHTML = slice.map(r => {
    const files = (r.evidence && r.evidence.files) || [];
    const fileTxt = files.length
      ? files.slice(0, 2).join('、') + (files.length > 2 ? ' 等' + files.length + '个文件' : '')
      : '';
    return '<tr>' +
    '<td><a class="runlink" href="/runs/' + esc(r.run_id) + '" title="原始编号: ' + esc(r.run_id) + '">' + esc(formatRunId(r.run_id)) + '</a>' +
    (fileTxt ? '<div class="muted" style="font-size:11.5px;margin-top:2px">' + esc(fileTxt) + '</div>' : '') + '</td>' +
    '<td>' + fmtTime(r.start_time) + '</td>' +
    '<td>' + statusBadge(r.status) + '</td>' +
    '<td class="attach-cell" data-run="' + esc(r.run_id) + '"><span class="muted">…</span></td>' +
    '<td><button class="ghost mini" onclick="openReportFor(\'' + esc(r.run_id) + '\', this)">打开报告</button></td>' +
    '<td><div class="ops">' +
    '<button class="ghost mini" onclick="showRunDetail(\'' + esc(r.run_id) + '\')">详情</button>' +
    '<button class="mini danger-ghost" onclick="deleteRunFor(\'' + esc(r.run_id) + '\')">删除数据</button>' +
    '</div></td></tr>';
  }).join('');
  // 附件列异步填充：失败录屏首帧缩略图（点击放大播放）；无视频显示 —
  slice.forEach(r => loadVideoThumbs(r.run_id));
  renderPager('#reportPager', _reportPage, pages, (p) => { _reportPage = p; loadReportList(); }, runs.length);
}

/* 附件列：拉取失败录屏首帧缩略图并填充；点击 lightbox 放大播放 */
async function loadVideoThumbs(runId) {
  const cell = document.querySelector('.attach-cell[data-run="' + CSS.escape(runId) + '"]');
  if (!cell) return;
  const d = await api('/api/run/' + encodeURIComponent(runId) + '/video_thumbs');
  if (!cell.isConnected) return;
  const thumbs = (d && d.thumbs) || [];
  if (!thumbs.length) { cell.innerHTML = '<span class="muted">—</span>'; return; }
  cell.innerHTML = thumbs.map(t =>
    '<video class="video-thumb" src="/api/runs/' + encodeURIComponent(runId) + '/res/' + encodeURIComponent(t.video) + '#t=1.5" ' +
    'preload="metadata" data-video="/api/runs/' + encodeURIComponent(runId) + '/res/' + encodeURIComponent(t.video) + '" title="点击放大播放失败录屏"></video>'
  ).join('');
}

/* 打开报告（统一入口）：按钮 loading + 5 秒冷却防重复点击。
   冷却用全局时间锁而非按钮状态——报告页每 8s 轮询会重建表格 DOM，
   按钮级的 disabled 挡不住重建出来的新按钮。
   后端等报告服务就绪才返回，返回后只 window.open 一次（不会双开） */
let _openReportLockUntil = 0;
async function openReportFor(runId, btn) {
  if (Date.now() < _openReportLockUntil) return;
  _openReportLockUntil = Date.now() + 5000;
  const orig = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.textContent = '⏳ 打开中…'; }
  const started = Date.now();
  try {
    toast('正在生成/打开 ' + runId + ' 的报告…');
    const d = await postJson('/api/run/' + runId + '/report/open', {});
    if (d.ok) { toast(d.reused ? '报告服务已就绪: ' + d.url : '报告已生成并打开: ' + d.url); window.open(d.url, '_blank'); }
    else toast('打开失败: ' + (d.msg || ''), false);
  } finally {
    // 5 秒冷却：即使请求已返回，也要等满 5 秒才恢复按钮可点
    const remain = 5000 - (Date.now() - started);
    setTimeout(() => {
      _openReportLockUntil = 0;
      if (btn) { btn.disabled = false; btn.textContent = orig; }
    }, Math.max(0, remain));
  }
}

/* ---------------- 页面分发 ---------------- */
document.addEventListener('DOMContentLoaded', () => {
  const page = document.body.dataset.page;
  if (page === 'index') initIndex();
  else if (page === 'run') initRun();
  else if (page === 'detail') initRunDetail();
  else if (page === 'report') initReport();
});