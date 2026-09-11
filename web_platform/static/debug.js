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
let DBG_TOOL = 'methods';
let PO_ROWS = [];        // 新增 PO 的元素行

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
  ['overview', 'tools', 'records'].forEach(v => {
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

const LOCATOR_TYPES = ['ID', 'XPATH', 'CLASS_NAME', 'ACCESSIBILITY_ID', 'ANDROID_UIAUTOMATOR', 'ANDROID_VIEWTAG',
  'ANDROID_DATA_MATCHER', 'CSS_SELECTOR', 'LINK_TEXT', 'PARTIAL_LINK_TEXT', 'TAG_NAME', 'NAME', 'IMAGE',
  'IOS_CLASS_CHAIN', 'IOS_PREDICATE', 'IOS_UIAUTOMATION'];
const WAIT_TYPES = ['', 'VISIBILITY_OF', 'PRESENCE_OF_ELEMENT_LOCATED', 'ELEMENT_TO_BE_CLICKABLE',
  'ELEMENT_LOCATED_TO_BE_SELECTED', 'TITLE_IS', 'TITLE_CONTAINS'];

/* ================= 方法调试（调试对象 = 框架真实方法，目录自动识别） ================= */
let DBG_FUNCS_FLAT = [];   // [{target,file,cls,name,kind,params,ctor_params,instantiable,doc}]
let DBG_CALL_TARGET = null;

function dbgBuildFuncIndex() {
  DBG_FUNCS_FLAT = [];
  (DBG_FUNCS || []).forEach(f => {
    (f.entries || []).forEach(e => DBG_FUNCS_FLAT.push(Object.assign({}, e, {file: f.file})));
  });
}

function dbgRenderToolTabs() {
  const tabs = [
    ['methods', '🔎 方法调试'],
    ['http_request', '🌐 HTTP 请求'],
    ['text_assert', '🔤 文本断言'],
    ['element_build', '🎯 元素调试'],
    ['po', '📄 新增 PO'],
  ];
  $('#toolTabs').innerHTML = tabs.map(([k, label]) =>
    '<button class="ttab2' + (DBG_TOOL === k ? ' on' : '') + '" data-tool="' + k + '">' + label + '</button>').join('');
}

function dbgRenderToolForm() {
  if (DBG_TOOL === 'po') { dbgRenderPoForm(); return; }
  if (DBG_TOOL !== 'methods') { dbgRenderLegacyToolForm(); return; }
  $('#toolForm').innerHTML =
    '<div class="field" style="max-width:420px;margin-bottom:10px"><label>搜索方法（目标 / 文档）</label>' +
    '<input type="text" id="methodSearch" placeholder="strTool / DateTimeTool / toast / doRequest…"></div>' +
    '<div class="mdebug"><div id="methodTree" class="mtree"></div>' +
    '<div id="callPane" style="flex:1;min-width:0"></div></div>';
  $('#methodSearch').addEventListener('input', dbgRenderMethodTree);
  $('#methodTree').addEventListener('click', (e) => {
    const item = e.target.closest('.mtree-item');
    if (!item) return;
    DBG_CALL_TARGET = item.dataset.target;
    dbgRenderMethodTree();
    dbgRenderCallForm();
  });
  dbgRenderMethodTree();
  $('#callPane').innerHTML = '<p class="muted">左侧选择一个框架方法（目录由框架文件自动识别）。</p>';
}

function dbgRenderMethodTree() {
  const q = (($('#methodSearch') || {}).value || '').trim().toLowerCase();
  const byFile = {};
  DBG_FUNCS_FLAT
    .filter(m => !q || m.target.toLowerCase().includes(q) || (m.doc || '').toLowerCase().includes(q))
    .forEach(m => (byFile[m.file] = byFile[m.file] || []).push(m));
  const files = Object.keys(byFile).sort();
  $('#methodTree').innerHTML = files.map(f =>
    '<div class="mtree-file">' + esc(f) + '</div>' +
    byFile[f].map(m =>
      '<div class="mtree-item' + (DBG_CALL_TARGET === m.target ? ' on' : '') + '" data-target="' + esc(m.target) + '" title="' + esc(m.doc) + '">' +
      '<b>' + esc(m.cls ? m.cls + '.' + m.name : m.name) + '</b>' +
      '<span class="muted">' + esc('(' + m.params.map(p => p.name + (p.required ? '' : '?')).join(', ') + ')') + '</span></div>').join('')
  ).join('') || '<p class="muted">无匹配方法</p>';
}

function dbgRenderCallForm() {
  const m = DBG_FUNCS_FLAT.find(x => x.target === DBG_CALL_TARGET);
  const pane = $('#callPane');
  if (!m) { pane.innerHTML = '<p class="muted">方法不存在</p>'; return; }
  const notInstantiable = !m.instantiable && m.ctor_params.length > 0;
  const ctorHtml = (m.ctor_params.length && m.instantiable)
    ? '<h4>构造参数（用于创建实例）</h4><div class="fields">' + m.ctor_params.map(p => dbgParamField('ctor', p)).join('') + '</div>'
    : '';
  const warn = notInstantiable
    ? '<p class="num-bad">⚠ 该类构造需要运行时对象（' + m.ctor_params.map(p => p.name).join(', ') +
      '），无法脱离设备 / 服务调试，运行会得到明确报错</p>'
    : '';
  pane.innerHTML = '<h4 class="muted" style="margin-top:0">' + esc(m.target) + '</h4>' +
    (m.doc ? '<p class="muted">' + esc(m.doc) + '</p>' : '') +
    '<p class="muted" style="font-size:12px">类型: ' + esc(m.kind) + (notInstantiable ? ' · 不可自动实例化' : '') + '</p>' +
    warn + ctorHtml +
    '<h4>方法参数' + (m.params.length ? '' : '（无）') + '</h4>' +
    (m.params.length ? '<div class="fields">' + m.params.map(p => dbgParamField('arg', p)).join('') + '</div>' : '') +
    '<div class="mt"><button id="btnCallRun"' + (notInstantiable ? '' : '') + '>▶ 运行调试</button></div>' +
    '<div id="callResult" class="mt"></div>';
  $('#btnCallRun').addEventListener('click', dbgRunCall);
}

function dbgParamField(prefix, p) {
  const ph = p.required ? '必填' : ('留空 = 默认 ' + (p.default === null ? '无' : p.default));
  return '<div class="field"><label>' + esc(p.name) + (p.required ? ' <b class="num-bad">*</b>' : '') +
    (p.annotation ? ' <span class="muted">(' + esc(p.annotation) + ')</span>' : '') + '</label>' +
    '<input type="text" data-prefix="' + prefix + '" data-name="' + esc(p.name) + '" placeholder="' + esc(ph) + '"></div>';
}

async function dbgRunCall() {
  const ctor_args = {}, args = {};
  document.querySelectorAll('#callPane input[data-name]').forEach(el => {
    const v = el.value.trim();
    if (el.dataset.prefix === 'ctor') ctor_args[el.dataset.name] = v;
    else args[el.dataset.name] = v;
  });
  const btn = $('#btnCallRun');
  btn.disabled = true; btn.textContent = '⏳ 运行中…';
  $('#callResult').innerHTML = '<p class="muted">运行中…</p>';
  try {
    const d = await postJson('/api/debug/tool',
      {tool: '__call__', params: {target: DBG_CALL_TARGET, ctor_args: ctor_args, args: args}});
    if (!d.ok) { $('#callResult').innerHTML = '<div class="err">✗ ' + esc(d.msg || '执行失败') + '</div>'; return; }
    const r = d.result;
    if (!r.ok) {
      $('#callResult').innerHTML = '<div class="err">✗ ' + esc(r.msg || '执行失败') + '</div>' +
        (r.traceback ? '<pre class="codebox">' + esc(r.traceback) + '</pre>' : '');
      return;
    }
    const data = r.data;
    const ret = data.return;
    const valHtml = ret.kind === 'json'
      ? '<pre class="codebox">' + esc(JSON.stringify(ret.value, null, 2)) + '</pre>'
      : '<pre class="codebox">' + esc(ret.value) + '</pre>';
    $('#callResult').innerHTML =
      '<div class="meta"><span>返回类型 <b>' + esc(ret.type) + '</b></span><span>耗时 <b>' + data.duration_ms + 'ms</b></span></div>' +
      '<h4>返回值</h4>' + valHtml +
      (data.stdout ? '<h4>方法内部输出 (stdout)</h4><pre class="codebox">' + esc(data.stdout) + '</pre>' : '');
  } catch (e) {
    $('#callResult').innerHTML = '<div class="err">✗ 请求异常: ' + esc(String(e)) + '</div>';
  } finally {
    btn.disabled = false; btn.textContent = '▶ 运行调试';
  }
}

/* ---------------- 固定字段调试工具（HTTP / 文本断言 / 元素调试） ---------------- */
const DBG_TOOLS = {
  http_request: {name: '🌐 HTTP 请求', fields: [
    {k: 'url', label: '完整 URL', type: 'text', ph: 'https://example.com/api?q=1', required: true},
    {k: 'method', label: '请求方式', type: 'select', options: ['get', 'post_form', 'put'], def: 'get'},
    {k: 'params', label: '参数（JSON 对象，可空）', type: 'textarea', ph: '{"wd": "apitest"}'},
    {k: 'headers', label: '请求头（JSON 对象，可空）', type: 'textarea', ph: '{"X-Debug": "1"}'},
    {k: 'timeout', label: '超时秒数（1-45）', type: 'text', def: '20'},
  ]},
  text_assert: {name: '🔤 文本断言', fields: [
    {k: 'source', label: '被检文本', type: 'textarea', ph: '订单金额：123.45 元', required: true},
    {k: 'pattern', label: '正则表达式', type: 'text', ph: '金额：([0-9.]+)', required: true},
  ]},
  element_build: {name: '🎯 元素调试', fields: [
    {k: 'locator_type', label: '定位方式', type: 'select', options: LOCATOR_TYPES, def: 'ID'},
    {k: 'locator_value', label: '定位值', type: 'text', ph: 'com.app:id/btn', required: true},
    {k: 'expected_value', label: '期望值（可选）', type: 'text'},
    {k: 'wait_type', label: '等待类型（可选）', type: 'select', options: WAIT_TYPES},
    {k: 'wait_seconds', label: '等待秒数（可选）', type: 'text', ph: '10'},
  ]},
};

function dbgRenderLegacyToolForm() {
  const t = DBG_TOOLS[DBG_TOOL];
  $('#toolForm').innerHTML = '<div class="fields">' +
    t.fields.map(f => {
      const ph = f.ph ? ' placeholder="' + esc(f.ph) + '"' : '';
      const def = f.def ? ' value="' + esc(f.def) + '"' : '';
      if (f.type === 'textarea') return '<div class="field" style="grid-column:1/-1"><label>' + esc(f.label) + '</label><textarea id="tf-' + f.k + '" rows="3"' + ph + '></textarea></div>';
      if (f.type === 'select') return '<div class="field"><label>' + esc(f.label) + '</label><select id="tf-' + f.k + '">' +
        f.options.map(o => '<option value="' + esc(o) + '"' + (o === f.def ? ' selected' : '') + '>' + (o || '（不等待）') + '</option>').join('') + '</select></div>';
      return '<div class="field"><label>' + esc(f.label) + '</label><input type="text" id="tf-' + f.k + '"' + ph + def + '></div>';
    }).join('') + '</div>' +
    '<div class="mt"><button id="btnToolRun">▶ 运行调试</button></div>';
  $('#btnToolRun').addEventListener('click', dbgRunTool);
  $('#toolResult').innerHTML = '<p class="muted">填写参数后运行，结果展示在这里。</p>';
}

function dbgCollectToolParams() {
  const t = DBG_TOOLS[DBG_TOOL];
  const params = {};
  t.fields.forEach(f => {
    const el = $('#tf-' + f.k);
    if (!el) return;
    params[f.k] = el.value.trim();
  });
  if (DBG_TOOL === 'http_request') {
    ['params', 'headers'].forEach(k => {
      if (params[k]) {
        try { params[k] = JSON.parse(params[k]); }
        catch (e) { throw new Error(k + ' 不是合法 JSON: ' + e.message); }
      } else delete params[k];
    });
  }
  return params;
}

async function dbgRunTool() {
  const btn = $('#btnToolRun');
  let params;
  try { params = dbgCollectToolParams(); }
  catch (e) { return toast(e.message, false); }
  btn.disabled = true; btn.textContent = '⏳ 运行中…';
  $('#toolResult').innerHTML = '<p class="muted">运行中…</p>';
  try {
    const d = await postJson('/api/debug/tool', {tool: DBG_TOOL, params: params});
    if (!d.ok) { $('#toolResult').innerHTML = '<div class="err">✗ ' + esc(d.msg || '执行失败') + '</div>'; return; }
    const r = d.result;
    if (!r.ok) { $('#toolResult').innerHTML = '<div class="err">✗ ' + esc(r.msg || '执行失败') + '</div>'; return; }
    dbgRenderToolResult(r.data);
  } catch (e) {
    $('#toolResult').innerHTML = '<div class="err">✗ 请求异常: ' + esc(String(e)) + '</div>';
  } finally {
    btn.disabled = false; btn.textContent = '▶ 运行调试';
  }
}

function dbgRenderToolResult(data) {
  if (DBG_TOOL === 'http_request') {
    $('#toolResult').innerHTML =
      '<div class="meta"><span>状态码 <b class="' + (data.status_code === 200 ? 'num-ok' : 'num-bad') + '">' + data.status_code + '</b></span>' +
      '<span>响应长度 <b>' + data.body_length + '</b></span></div>' +
      '<h4>响应体</h4><pre class="codebox">' + esc(data.body) + '</pre>' +
      '<h4 class="mt muted">请求回显</h4><pre class="codebox">' + esc(JSON.stringify(data.request, null, 2)) + '</pre>';
  } else if (DBG_TOOL === 'text_assert') {
    $('#toolResult').innerHTML =
      '<div class="meta"><span>匹配 <b class="' + (data.matched ? 'num-ok' : 'num-bad') + '">' + (data.matched ? '成功' : '失败') + '</b></span>' +
      '<span>匹配到 <b>' + data.match_count + '</b> 处</span>' +
      '<span>AssertTool: <b>' + data.assertTool_isRegularMatch + '</b></span>' +
      '<span>hamcrest: <b>' + data.hamcrest_is_match_by_regexp + '</b></span></div>' +
      '<h4>匹配内容</h4><pre class="codebox">' + esc(JSON.stringify({first: data.match_text, groups: data.groups, all: data.all_matches}, null, 2)) + '</pre>';
  } else if (DBG_TOOL === 'element_build') {
    $('#toolResult').innerHTML =
      '<h4>ElementInfo 数据</h4><pre class="codebox">' + esc(JSON.stringify(data, null, 2)) + '</pre>' +
      '<p class="muted">可直接粘贴到元素仓库文件中的写法：</p><pre class="codebox">' + esc(data.code) + '</pre>';
  }
}

/* ---------------- 新增 PO ---------------- */
function dbgRenderPoForm() {
  const ltOptions = LOCATOR_TYPES.map(t => '<option>' + t + '</option>').join('');
  const wtOptions = ['', 'VISIBILITY_OF', 'PRESENCE_OF_ELEMENT_LOCATED', 'ELEMENT_TO_BE_CLICKABLE',
    'ELEMENT_LOCATED_TO_BE_SELECTED', 'TITLE_IS', 'TITLE_CONTAINS'].map(t => '<option value="' + t + '">' + (t || '（不等待）') + '</option>').join('');
  $('#toolForm').innerHTML =
    '<div class="fields">' +
    '<div class="field"><label>页面类名（大驼峰，建议 Page 结尾）</label><input type="text" id="po-class" placeholder="KuaigeLoginPage"></div>' +
    '<div class="field"><label>页面说明</label><input type="text" id="po-desc" placeholder="快歌 App 登录页"></div>' +
    '</div>' +
    '<div class="mt"><b>元素定义</b> <button class="ghost mini" id="poAdd">＋ 添加元素</button>' +
    '<label class="muted" style="margin-left:12px"><input type="checkbox" id="po-force"> 覆盖已存在文件</label></div>' +
    '<div class="tblwrap mt"><table><thead><tr><th>元素名</th><th>说明</th><th>页面操作</th><th>定位方式</th><th>定位值</th><th>等待</th><th></th></tr></thead><tbody id="poRows"></tbody></table></div>' +
    '<div class="mt"><button id="btnPoGen">⚡ 生成代码预览</button> <button id="btnPoSave" class="ghost">💾 保存到框架</button></div>' +
    '<div id="poResult"></div>';
  $('#poAdd').addEventListener('click', () => { PO_ROWS.push({}); dbgRenderPoRows(); });
  $('#btnPoGen').addEventListener('click', () => dbgPoSubmit('po_generate'));
  $('#btnPoSave').addEventListener('click', () => dbgPoSubmit('po_save'));
  if (!PO_ROWS.length) PO_ROWS.push({});
  dbgRenderPoRows();
  $('#poResult').innerHTML = '';
}

function dbgRenderPoRows() {
  const ltOptions = LOCATOR_TYPES.map(t => '<option value="' + t + '">' + t + '</option>').join('');
  const wtOptions = ['', 'VISIBILITY_OF', 'PRESENCE_OF_ELEMENT_LOCATED', 'ELEMENT_TO_BE_CLICKABLE',
    'ELEMENT_LOCATED_TO_BE_SELECTED', 'TITLE_IS', 'TITLE_CONTAINS']
    .map(t => '<option value="' + t + '">' + (t || '（不等待）') + '</option>').join('');
  $('#poRows').innerHTML = PO_ROWS.map((row, i) =>
    '<tr>' +
    '<td><input type="text" data-pk="name" data-i="' + i + '" placeholder="btn_login" value="' + esc(row.name || '') + '"></td>' +
    '<td><input type="text" data-pk="desc" data-i="' + i + '" placeholder="登录按钮" value="' + esc(row.desc || '') + '"></td>' +
    '<td><select data-pk="action" data-i="' + i + '">' +
    ['click', 'input', 'check', 'read'].map(a => '<option' + (row.action === a ? ' selected' : '') + '>' + a + '</option>').join('') +
    '</select></td>' +
    '<td><select data-pk="locator_type" data-i="' + i + '">' + ltOptions + '</select></td>' +
    '<td><input type="text" data-pk="locator_value" data-i="' + i + '" placeholder="com.app:id/btn" value="' + esc(row.locator_value || '') + '"></td>' +
    '<td><select data-pk="wait_type" data-i="' + i + '">' + wtOptions + '</select></td>' +
    '<td><button class="mini danger-ghost po-del" data-i="' + i + '">✕</button></td></tr>').join('');
  document.querySelectorAll('#poRows [data-pk]').forEach(el => {
    el.addEventListener('change', () => {
      PO_ROWS[+el.dataset.i][el.dataset.pk] = (el.tagName === 'SELECT' ? el.value : el.value.trim());
    });
  });
  document.querySelectorAll('#poRows .po-del').forEach(el => {
    el.addEventListener('click', () => { PO_ROWS.splice(+el.dataset.i, 1); dbgRenderPoRows(); });
  });
  PO_ROWS.forEach((row, i) => {
    ['action', 'locator_type', 'wait_type'].forEach(k => {
      if (row[k]) { const el = document.querySelector('#poRows [data-pk="' + k + '"][data-i="' + i + '"]'); if (el) el.value = row[k]; }
    });
  });
}

function dbgCollectPo() {
  const po = {
    page_class: $('#po-class').value.trim(),
    page_desc: $('#po-desc').value.trim(),
    elements: PO_ROWS.map(r => ({...r})),
    force: $('#po-force') && $('#po-force').checked,
  };
  if (DBG_LAST_PO && DBG_TOOL_LAST_RESULT && po.page_class === DBG_TOOL_LAST_RESULT.page_class) {
    po.page_class = po.page_class || DBG_TOOL_LAST_RESULT.page_class;
  }
  return po;
}

let DBG_TOOL_LAST_RESULT = null, DBG_LAST_PO = null;

async function dbgPoSubmit(mode) {
  const po = {
    page_class: $('#po-class').value.trim(),
    page_desc: $('#po-desc').value.trim(),
    elements: PO_ROWS.map(r => ({...r})),
    force: $('#po-force') && $('#po-force').checked,
  };
  if (mode === 'po_save' && DBG_LAST_PO) {
    po.page_class = po.page_class || DBG_LAST_PO.page_class;
    po.page_desc = po.page_desc || DBG_LAST_PO.page_desc;
    po.elements = po.elements.some(e => e.locator_value) ? po.elements : DBG_LAST_PO.elements;
  }
  const btn = mode === 'po_save' ? $('#btnPoSave') : $('#btnPoGen');
  btn.disabled = true;
  $('#poResult').innerHTML = '<p class="muted">处理中…</p>';
  try {
    const d = await postJson('/api/debug/tool', {tool: mode, params: po});
    if (!d.ok) { $('#poResult').innerHTML = '<div class="err">✗ ' + esc(d.msg || '') + '</div>'; return; }
    const r = d.result;
    if (!r.ok) { $('#poResult').innerHTML = '<div class="err">✗ ' + esc(r.msg || '') + '</div>'; return; }
    if (mode === 'po_generate') {
      DBG_LAST_PO = po;
      const warn = (p, exists) => exists ? '<span class="num-bad">⚠ 文件已存在，保存需勾选覆盖</span>' : '<span class="num-ok">新文件</span>';
      $('#poResult').innerHTML =
        '<p>' + warn('', r.data.elements_exists) + ' → <b>' + esc(r.data.elements_path) + '</b>　' +
        warn('', r.data.page_exists) + ' → <b>' + esc(r.data.page_path) + '</b></p>' +
        '<h4>' + esc(r.data.elements_class) + '（元素仓库）</h4><pre class="codebox">' + esc(r.data.elements_code) + '</pre>' +
        '<h4>' + esc(r.data.page_class) + '（页面对象）</h4><pre class="codebox">' + esc(r.data.page_code) + '</pre>';
    } else {
      $('#poResult').innerHTML = '<div class="meta"><span class="num-ok">✓ ' + esc(r.data.msg || '已保存') + '</span>' +
        '<span>' + esc((r.data.written || []).join('、')) + '</span></div>';
      toast(r.data.msg || '已保存', true);
    }
  } catch (e) {
    $('#poResult').innerHTML = '<div class="err">✗ 请求异常: ' + esc(String(e)) + '</div>';
  } finally {
    btn.disabled = false;
  }
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
  dbgBuildFuncIndex();
  dbgRender();
  dbgRenderToolTabs();
  dbgRenderToolForm();

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
  $('#toolTabs').addEventListener('click', (e) => {
    const b = e.target.closest('.ttab2');
    if (!b) return;
    DBG_TOOL = b.dataset.tool;
    dbgRenderToolTabs();
    dbgRenderToolForm();
  });
  $('#recList').addEventListener('click', (e) => {
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
