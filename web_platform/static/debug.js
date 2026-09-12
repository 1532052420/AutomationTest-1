/* 代码审查页 · 前端逻辑（独立文件，复用 app.js 公共工具与侧边栏）
   - 按模块文件夹分组（common/pojo/base/init/page_objects/cases/平台接口/全框架体检）
   - 体检状态行：通过/失败/跳过汇总（对齐「代码审查 P0 方案」第 15 节展示）
   - 统计卡 = 筛选器；失败项可展开看完整错误与堆栈
   - 交互调试：HTTP 请求 / 文本断言 / 元素构造 / 新增 PO（生成+保存）
   - 审查记录：每次「全部验证」自动存快照，10 条/页分页，可查看/删除 */
'use strict';

let DBG_ITEMS = [];      // 检查项规格 [{id,file,title}]
let DBG_FUNCS = [];      // 框架文件自动识别目录 [{file, module, error, entries}]
let DBG_RESULTS = {};    // id -> result（实时为空对象；查看历史快照时填充）
let DBG_FILTER = '';     // '' | 'PASS' | 'FAIL' | 'SKIP'
let DBG_RECORD = null;   // 正在查看的历史记录
let DBG_RUNNING = false;
let REC_PAGE = 1;
let DBG_VIEW = 'overview';

/* ---------------- 模块（文件夹）元数据 ---------------- */
const MODULE_META = {
  common: {name: 'common 工具库', icon: '🧰', desc: '时间 / 文件 / 字符串 / 断言 / 网络 / 进程池 / HTTP 客户端 / Java / 验证码 / hamcrest'},
  pojo: {name: 'pojo 数据模型', icon: '📦', desc: '配置对象与数据结构'},
  base: {name: 'base 配置与客户端', icon: '🏗️', desc: '配置读取器、接口 / APP 客户端链路'},
  init: {name: 'init 初始化链路', icon: '🚀', desc: 'maven / httpserver / mitmproxy / 项目初始化'},
  page_objects: {name: 'page_objects 页面对象', icon: '📄', desc: '定位 / 等待 / 元素构造 / 页面方法接线'},
  cases: {name: 'cases 测试用例', icon: '🧪', desc: '用例收集与执行入口'},
  platform: {name: '平台与设备接口', icon: '🌐', desc: '元素定位器 / 执行平台 / Appium 探测'},
  sweep: {name: '全框架体检', icon: '🔍', desc: '全部模块逐一 import 扫描'},
  other: {name: '其他', icon: '📁', desc: ''},
};
const MODULE_ORDER = ['common', 'pojo', 'base', 'init', 'page_objects', 'cases', 'platform', 'sweep', 'other'];

const FILE_DISP_MAX = 20;
function dbgFileCell(file) {
  const disp = file.length > FILE_DISP_MAX ? file.slice(0, FILE_DISP_MAX) + '…' : file;
  return '<span class="file-cell" title="点击复制完整路径：' + esc(file) + '" data-copy="' + esc(file) + '">' + esc(disp) + '</span>';
}

function dbgModuleOf(file) {
  if (file.startsWith('平台接口') || file.startsWith('环境探测')) return 'platform';
  if (file.startsWith('全框架')) return 'sweep';
  const seg = file.split('/')[0];
  return MODULE_ORDER.includes(seg) ? seg : 'other';
}

const DBG_ST_KEY = {PASS: 'passed', FAIL: 'failed', SKIP: 'skipped'};

function dbgBadge(status) {
  const map = {PASS: 'PASSED', FAIL: 'FAILED', SKIP: 'SKIPPED'};
  return statusBadge(map[status] || status).replace('class="status', 'data-st="' + status + '" class="status');
}

function dbgStatusOf(id) {
  const r = DBG_RESULTS[id];
  return r ? r.status : '';
}

/* ================= 视图切换 ================= */
function dbgShowView(view) {
  DBG_VIEW = view;
  ['overview', 'records'].forEach(v => {
    const sec = $('#view-' + v);
    if (sec) sec.style.display = (v === view) ? '' : 'none';
  });
  document.querySelectorAll('.ttab').forEach(b => b.classList.toggle('on', b.dataset.view === view));
  if (view === 'records') dbgLoadRecords();
}

/* ================= 模块总览 ================= */
function dbgRender() {
  const byModule = {};
  DBG_ITEMS.forEach(it => {
    const m = dbgModuleOf(it.file);
    (byModule[m] = byModule[m] || []).push(it);
  });

  // 体检状态行
  const counts = {PASS: 0, FAIL: 0, SKIP: 0};
  let done = 0;
  DBG_ITEMS.forEach(it => {
    const s = dbgStatusOf(it.id);
    if (s) { counts[s]++; done++; }
  });
  const total = DBG_ITEMS.length;
  let health;
  if (!done) health = '<span class="hl-icon">⏳</span> <b>待验证</b><span class="muted">共 ' + total + ' 项，点右上角「▶ 全部验证」开始</span>';
  else if (counts.FAIL > 0) health = '<span class="hl-icon">❌</span> <b>体检未通过</b><span class="muted">失败 <b class="num-bad">' + counts.FAIL + '</b> · 跳过 ' + counts.SKIP + ' · 通过 ' + counts.PASS + '（' + done + '/' + total + '）</span>';
  else if (done < total) health = '<span class="hl-icon">⏳</span> <b>进行中</b><span class="muted">通过 ' + counts.PASS + ' · 跳过 ' + counts.SKIP + '（' + done + '/' + total + '）</span>';
  else health = '<span class="hl-icon">✅</span> <b>框架体检通过</b><span class="muted">通过 ' + counts.PASS + ' · 跳过 ' + counts.SKIP + '（共 ' + total + ' 项）</span>';
  if (DBG_RECORD) {
    const s = DBG_RECORD.summary;
    health = '<span class="hl-icon">🗂</span> <b>历史快照 ' + esc(DBG_RECORD.id) + '</b><span class="muted">' +
      esc(DBG_RECORD.time) + ' · 通过 ' + s.passed + ' · 失败 ' + s.failed + ' · 跳过 ' + s.skipped + '</span>';
  }
  $('#healthLine').innerHTML = health;

  // 模块锚点
  const modules = MODULE_ORDER.filter(m => byModule[m]);
  $('#fileChips').innerHTML = modules.map(m => {
    const items = byModule[m];
    const dn = items.filter(it => dbgStatusOf(it.id)).length;
    const fl = items.filter(it => dbgStatusOf(it.id) === 'FAIL').length;
    return '<button class="chip" data-anchor="mod-' + m + '" title="' + esc(MODULE_META[m].desc) + '">' +
      MODULE_META[m].icon + ' ' + esc(MODULE_META[m].name) + ' <span class="muted">' +
      (fl ? '<b class="num-bad">' + fl + '✗</b> ' : '') + dn + '/' + items.length + '</span></button>';
  }).join('');

  // 模块分组卡片
  $('#dbgList').innerHTML = modules.map(m => {
    const meta = MODULE_META[m];
    const items = byModule[m];
    const st = {PASS: 0, FAIL: 0, SKIP: 0}, dn = items.filter(it => dbgStatusOf(it.id)).length;
    items.forEach(it => { const s = dbgStatusOf(it.id); if (s) st[s]++; });
    const pill = !dn ? '<span class="status st-PENDING">待验证</span>'
      : st.FAIL ? '<span class="status st-FAILED">' + st.FAIL + ' 失败</span>'
      : st.PASS === items.length ? '<span class="status st-PASSED">全部通过</span>'
      : '<span class="status st-PASSED">' + st.PASS + ' 过</span>' + (st.SKIP ? ' <span class="status st-PENDING">' + st.SKIP + ' 跳过</span>' : '');
    const rows = items.map(it => {
      const stt = dbgStatusOf(it.id);
      const r = DBG_RESULTS[it.id];
      const stHtml = stt ? dbgBadge(stt) : '<span class="status st-PENDING">待验证</span>';
      return '<tr class="dbg-row" data-id="' + esc(it.id) + '" data-status="' + stt + '">' +
        '<td style="width:40%"><b>' + esc(it.title) + '</b>' +
        '<div class="muted" style="font-size:12px">' + esc(it.id) + '</div></td>' +
        '<td class="muted" style="font-size:12px">' + dbgFileCell(it.file) + '</td>' +
        '<td class="cell-status">' + stHtml + '</td>' +
        '<td class="cell-dur muted">' + (r ? r.duration_ms + 'ms' : '-') + '</td>' +
        '<td style="width:150px"><button class="ghost mini dbg-run" data-id="' + esc(it.id) + '">▶ 调试</button>' +
        (r ? ' <button class="ghost mini dbg-expand" data-id="' + esc(it.id) + '">详情</button>' : '') + '</td></tr>' +
        (r ? '<tr class="detail-row" data-for="' + esc(it.id) + '" style="display:none"><td colspan="5">' +
          '<pre class="detail-pre">' + esc((r.error ? '❌ ' + r.error + '\n' : '') + (r.detail || '-')) + '</pre></td></tr>' : '');
    }).join('');
    // 自动识别：该模块下没有专项检查的框架文件，随文件增减自动出现/消失
    const checked = new Set(items.map(it => it.file.split(' + ')[0]));
    const autoFiles = DBG_FUNCS.filter(f => dbgModuleOf(f.file) === m && !checked.has(f.file));
    const autoRows = autoFiles.map(f => {
      const ok = !f.error;
      const st = ok ? '<span class="status st-PASSED">可导入</span>' : '<span class="status st-FAILED">导入失败</span>';
      return '<tr class="dbg-row auto-row" data-status="' + (ok ? 'PASS' : 'FAIL') + '">' +
        '<td><span class="auto-tag">🤖 自动识别</span></td>' +
        '<td class="muted" style="font-size:12px">' + dbgFileCell(f.file) + '</td>' +
        '<td class="cell-status">' + st + '</td>' +
        '<td class="cell-dur muted">' + f.entries.length + ' 方法</td>' +
        '<td>' + (f.error ? '<span class="num-bad" style="font-size:12px">' + esc(f.error) + '</span>' : '<span class="muted" style="font-size:12px">导入验证覆盖</span>') + '</td></tr>';
    }).join('');
    const autoSection = autoRows ? '<tr class="auto-head"><td colspan="5" class="muted" style="font-size:12px">🤖 自动识别文件（' + autoFiles.length + '）· 无专项检查，由全框架导入验证覆盖 · 交互调试可调用其方法</td></tr>' + autoRows : '';
    return '<div class="card dbg-group" id="mod-' + m + '">' +
      '<h3>' + meta.icon + ' ' + esc(meta.name) + ' <span class="muted" style="font-size:12px">' + esc(meta.desc) + '（' + items.length + ' 项检查' + (autoFiles.length ? ' + ' + autoFiles.length + ' 自动识别' : '') + '）</span>' +
      '<span style="float:right">' + pill + '</span></h3>' +
      '<div class="tblwrap"><table><thead><tr><th>调试项</th><th>归属文件</th><th>结果</th><th>耗时</th><th>操作</th></tr></thead>' +
      '<tbody>' + rows + autoSection + '</tbody></table></div></div>';
  }).join('');
  dbgApplyFilter();
  dbgUpdateStats();
}

function dbgApplyFilter() {
  const visible = {};
  document.querySelectorAll('#dbgList tbody tr.dbg-row').forEach(tr => {
    const st = tr.dataset.status || '';
    const show = !DBG_FILTER || st === DBG_FILTER;
    tr.style.display = show ? '' : 'none';
    const det = tr.nextElementSibling;
    if (det && det.classList.contains('detail-row')) det.style.display = (show && det.style.display !== 'none' && tr.dataset.status) ? det.style.display : 'none';
    const mod = tr.closest('.dbg-group').id.replace('mod-', '');
    if (show) visible[mod] = true;
  });
  document.querySelectorAll('#dbgList .dbg-group').forEach(card => {
    card.style.display = visible[card.id.replace('mod-', '')] ? '' : 'none';
  });
  $('#filterTip').style.display = DBG_FILTER ? '' : 'none';
  $('#filterTipText').textContent = {PASS: '通过', FAIL: '失败 / 异常', SKIP: '跳过'}[DBG_FILTER] || '';
}

function dbgUpdateStats() {
  const c = {PASS: 0, FAIL: 0, SKIP: 0};
  DBG_ITEMS.forEach(it => { const s = dbgStatusOf(it.id); if (s) c[s]++; });
  $('#stTotal').textContent = DBG_ITEMS.length + ' / ' + new Set(DBG_ITEMS.map(i => dbgModuleOf(i.file))).size;
  $('#stPass').textContent = c.PASS;
  $('#stFail').textContent = c.FAIL;
  $('#stSkip').textContent = c.SKIP;
  [['stPass', 'PASS'], ['stFail', 'FAIL'], ['stSkip', 'SKIP']].forEach(([sid, key]) => {
    const el = $('#' + sid).closest('.stat');
    if (el) el.classList.toggle('filter-on', DBG_FILTER === key);
  });
}

function dbgToggleFilter(key) {
  DBG_FILTER = (DBG_FILTER === key) ? '' : key;
  dbgApplyFilter();
  dbgUpdateStats();
}

/* ================= 单项调试 / 全部验证 ================= */
async function dbgRunOne(id) {
  const btn = document.querySelector('#dbgList button.dbg-run[data-id="' + CSS.escape(id) + '"]');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ 执行中'; }
  try {
    const d = await postJson('/api/debug/run', {id: id});
    if (d.ok) {
      DBG_RESULTS[id] = d.result;
      dbgRender();
    } else toast('执行失败: ' + (d.msg || ''), false);
  } catch (e) {
    toast('请求异常: ' + e, false);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '▶ 调试'; }
  }
}

async function dbgRunAll() {
  if (DBG_RUNNING) return;
  DBG_RUNNING = true;
  $('#btnRunAll').disabled = true;
  const sub = $('#subTitle');
  const t0 = Date.now();
  let completed = 0;
  try {
    DBG_RESULTS = {}; DBG_RECORD = null; dbgShowBanner(null); dbgRender();
    for (const it of DBG_ITEMS) {
      completed++;
      sub.textContent = '全部验证中… ' + completed + '/' + DBG_ITEMS.length + '（' + it.id + '）';
      await dbgRunOne(it.id);
    }
    sub.textContent = '全部验证完成 ✓';
    const results = DBG_ITEMS.map(it => DBG_RESULTS[it.id]).filter(Boolean);
    const d = await postJson('/api/debug/records', {results: results, duration_ms: Date.now() - t0});
    if (d.ok) {
      toast('全部验证完成，审查记录 ' + d.record_id + ' 已保存（通过 ' + d.summary.passed +
        ' / 失败 ' + d.summary.failed + ' / 跳过 ' + d.summary.skipped + '）', d.summary.failed === 0);
      REC_PAGE = 1;
    } else toast('验证完成，但记录保存失败: ' + (d.msg || ''), false);
  } finally {
    DBG_RUNNING = false;
    $('#btnRunAll').disabled = false;
  }
}

/* ================= 历史记录 ================= */
async function dbgLoadRecords() {
  const d = await api('/api/debug/records?page=' + REC_PAGE);
  const tb = $('#recList');
  if (!d.ok) { tb.innerHTML = '<tr><td colspan="5">记录加载失败</td></tr>'; return; }
  $('#recCount').textContent = '· 共 ' + d.total + ' 条';
  if (!d.records.length) {
    tb.innerHTML = '<tr><td colspan="5"><div class="empty">暂无审查记录，点右上角「▶ 全部验证」生成第一份</div></td></tr>';
    $('#recPager').innerHTML = '';
    return;
  }
  tb.innerHTML = d.records.map(r =>
    '<tr><td><b>' + esc(r.id) + '</b></td>' +
    '<td class="muted">' + esc(r.time) + '</td>' +
    '<td>' + runStatsHtml({total: r.summary.total, passed: r.summary.passed, failed: r.summary.failed, error: 0}) +
    ' <span class="muted">跳过 ' + r.summary.skipped + '</span></td>' +
    '<td class="muted">' + (r.duration_ms ? (r.duration_ms / 1000).toFixed(1) + 's' : '-') + '</td>' +
    '<td><div class="ops">' +
    '<button class="ghost mini dbg-view" data-id="' + esc(r.id) + '">查看</button>' +
    '<button class="mini danger-ghost dbg-del" data-id="' + esc(r.id) + '">删除</button>' +
    '</div></td></tr>').join('');
  renderPager('#recPager', d.page, d.pages, (p) => { REC_PAGE = p; dbgLoadRecords(); }, d.total);
}

async function dbgViewRecord(id) {
  const d = await api('/api/debug/records/' + encodeURIComponent(id));
  if (!d.ok) return toast(d.msg || '记录读取失败', false);
  DBG_RECORD = d.record;
  DBG_RESULTS = {};
  (d.record.results || []).forEach(r => { DBG_RESULTS[r.id] = r; });
  DBG_FILTER = '';
  dbgRender();
  dbgShowBanner(d.record);
  dbgShowView('overview');
  toast('正在查看历史记录 ' + id);
}

function dbgBackToLive() {
  DBG_RECORD = null; DBG_RESULTS = {}; DBG_FILTER = '';
  dbgRender(); dbgShowBanner(null);
  toast('已返回实时模式');
}

function dbgShowBanner(record) {
  const el = $('#viewBanner');
  if (!record) { el.style.display = 'none'; return; }
  el.style.display = '';
  el.innerHTML = '🗂 正在查看历史记录 <b>' + esc(record.id) + '</b>（' + esc(record.time) + '）' +
    ' <button class="ghost mini" id="btnBackLive">返回实时</button>';
  $('#btnBackLive').addEventListener('click', dbgBackToLive);
}

/* ---------------- 初始化 ---------------- */
async function dbgInit() {
  renderSidebar('/debug');
  const d = await api('/api/debug/items');
  if (!d.ok) { toast('清单加载失败: ' + (d.msg || ''), false); return; }
  DBG_ITEMS = d.items || [];
  if ((d.load_errors || []).length) {
    toast('有 ' + d.load_errors.length + ' 个检查模块自身加载失败，将在执行时呈现', false);
  }
  try {
    const f = await api('/api/debug/functions');
    if (f.ok) DBG_FUNCS = f.files || [];
  } catch (e) { /* 目录加载失败不影响检查项 */ }
  dbgRender();

  $('#btnRunAll').addEventListener('click', dbgRunAll);
  $('#btnReload').addEventListener('click', () => location.reload());
  $('#stPass').closest('.stat').addEventListener('click', () => dbgToggleFilter('PASS'));
  $('#stFail').closest('.stat').addEventListener('click', () => dbgToggleFilter('FAIL'));
  $('#stSkip').closest('.stat').addEventListener('click', () => dbgToggleFilter('SKIP'));
  $('#fileChips').addEventListener('click', (e) => {
    const chip = e.target.closest('.chip');
    if (!chip) return;
    const el = document.getElementById(chip.dataset.anchor);
    if (el) el.scrollIntoView({behavior: 'smooth', block: 'start'});
  });
  $('#dbgList').addEventListener('click', (e) => {
    const run = e.target.closest('button.dbg-run');
    if (run) return dbgRunOne(run.dataset.id);
    const ex = e.target.closest('button.dbg-expand');
    if (ex) {
      const tr = document.querySelector('#dbgList .detail-row[data-for="' + CSS.escape(ex.dataset.id) + '"]');
      if (tr) tr.style.display = tr.style.display === 'none' ? '' : 'none';
    }
  });
  document.querySelectorAll('.ttab').forEach(b =>
    b.addEventListener('click', () => dbgShowView(b.dataset.view)));
  document.querySelector('main').addEventListener('click', (e) => {
    const cell = e.target.closest('.file-cell');
    if (!cell) return;
    const text = cell.dataset.copy;
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(
      () => toast('已复制：' + text),
      () => {
        const ta = document.createElement('textarea');
        ta.value = text; document.body.appendChild(ta); ta.select();
        document.execCommand('copy'); ta.remove();
        toast('已复制：' + text);
      });
  });
  dbgRender();

  $('#btnRunAll').addEventListener('click', dbgRunAll);  $('#recList').addEventListener('click', (e) => {
    const v = e.target.closest('button.dbg-view');
    if (v) return dbgViewRecord(v.dataset.id);
    const del2 = e.target.closest('button.dbg-del');
    if (del2) dbgDeleteRecord(del2.dataset.id);
  });
}

async function dbgDeleteRecord(id) {
  const yes = await confirmModal('删除审查记录', '将删除记录 ' + id + '，不可恢复。', true);
  if (!yes) return;
  const d = await del('/api/debug/records/' + encodeURIComponent(id));
  toast(d.msg || (d.ok ? '已删除' : '删除失败'), d.ok);
  if (DBG_RECORD && DBG_RECORD.id === id) dbgBackToLive();
  await dbgLoadRecords();
}

document.addEventListener('DOMContentLoaded', dbgInit);
