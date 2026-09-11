/* 代码审查页 · 前端逻辑（独立文件，仅复用 app.js 的公共工具与侧边栏）
   - 按文件分组展示 + 顶部文件锚点（点击滚动定位）
   - 统计卡（通过/失败/跳过）即筛选器：点击筛选对应数据，再点一次取消
   - 审查记录：每次「全部验证」自动保存快照，10 条/页分页，可查看/删除 */
'use strict';

let DBG_ITEMS = [];            // 检查项规格 [{id,file,title}]
let DBG_RESULTS = {};          // id -> result（实时为空对象；查看历史时填充）
let DBG_FILTER = '';           // '' | 'PASS' | 'FAIL' | 'SKIP'
let DBG_RECORD = null;         // 正在查看的历史记录（null=实时模式）
let DBG_RUNNING = false;
let REC_PAGE = 1;

const DBG_ST_KEY = { PASS: 'passed', FAIL: 'failed', SKIP: 'skipped' };

function dbgBadge(status) {
  const map = { PASS: 'PASSED', FAIL: 'FAILED', SKIP: 'SKIPPED' };
  return statusBadge(map[status] || status).replace('class="status', 'data-st="' + status + '" class="status');
}

function dbgStatusOf(id) {
  const r = DBG_RESULTS[id];
  return r ? r.status : '';
}

/* ---------------- 渲染：文件锚点 + 分组卡片 ---------------- */
function dbgFileBase(file) { return file.split('/').pop().split(' + ')[0]; }

function dbgRender() {
  const byFile = {};
  DBG_ITEMS.forEach(it => (byFile[it.file] = byFile[it.file] || []).push(it));
  const files = Object.keys(byFile).sort();

  // 顶部文件锚点（点击滚动到对应分组）
  $('#fileChips').innerHTML = files.map(f => {
    const st = dbgFileStats(byFile[f]);
    const label = esc(dbgFileBase(f));
    return '<button class="chip" data-anchor="grp-' + esc(f) + '" title="' + esc(f) + '">' +
      label + ' <span class="muted">' + st.done + '/' + byFile[f].length + '</span></button>';
  }).join('');

  // 分组卡片（每行标注归属文件，筛选打散后仍可定位）
  $('#dbgList').innerHTML = files.map(f => {
    const rows = byFile[f].map(it => {
      const st = dbgStatusOf(it.id);
      const stHtml = st ? dbgBadge(st) : '<span class="status st-PENDING">待验证</span>';
      const r = DBG_RESULTS[it.id];
      const detail = r ? ((r.error ? '❌ ' + r.error + '\n' : '') + (r.detail || '-')) : '-';
      const dur = r ? r.duration_ms + 'ms' : '-';
      return '<tr data-id="' + esc(it.id) + '" data-status="' + st + '">' +
        '<td style="width:42%"><b>' + esc(it.title) + '</b>' +
        '<div class="muted" style="font-size:12px">' + esc(it.id) + '</div></td>' +
        '<td class="cell-file muted" style="font-size:12px">' + esc(f) + '</td>' +
        '<td class="cell-status">' + stHtml + '</td>' +
        '<td class="cell-dur muted">' + dur + '</td>' +
        '<td class="cell-detail muted" title="' + esc(detail) + '">' + (detail.length > 90 ? esc(detail.slice(0, 90)) + '…' : esc(detail)) + '</td>' +
        '<td style="width:90px"><button class="ghost mini dbg-run" data-id="' + esc(it.id) + '">▶ 调试</button></td>' +
        '</tr>';
    }).join('');
    return '<div class="card dbg-group" id="grp-' + esc(f) + '" data-file="' + esc(f) + '">' +
      '<h3>📄 ' + esc(f) + ' <span class="muted" style="font-size:12px">(' + byFile[f].length + ' 项)</span></h3>' +
      '<div class="tblwrap"><table><thead><tr><th>调试项</th><th>归属文件</th><th>结果</th><th>耗时</th><th>详情</th><th>操作</th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table></div></div>';
  }).join('');
  dbgApplyFilter();
  dbgUpdateStats();
}

function dbgFileStats(items) {
  let done = 0;
  items.forEach(it => { if (dbgStatusOf(it.id)) done++; });
  return { done };
}

/* ---------------- 统计卡 = 筛选器 ---------------- */
function dbgUpdateStats() {
  const c = { PASS: 0, FAIL: 0, SKIP: 0 };
  DBG_ITEMS.forEach(it => { const s = dbgStatusOf(it.id); if (s) c[s]++; });
  $('#stTotal').textContent = DBG_ITEMS.length + ' / ' + new Set(DBG_ITEMS.map(i => i.file)).size;
  $('#stPass').textContent = c.PASS;
  $('#stFail').textContent = c.FAIL;
  $('#stSkip').textContent = c.SKIP;
  // 统计卡选中态跟随筛选
  [['stPass', 'PASS'], ['stFail', 'FAIL'], ['stSkip', 'SKIP']].forEach(([sid, key]) => {
    const el = $('#' + sid).closest('.stat');
    if (el) el.classList.toggle('filter-on', DBG_FILTER === key);
  });
}

function dbgApplyFilter() {
  const visible = {};
  document.querySelectorAll('#dbgList tbody tr[data-id]').forEach(tr => {
    const st = tr.dataset.status || '';
    const show = !DBG_FILTER || st === DBG_FILTER;
    tr.style.display = show ? '' : 'none';
    visible[tr.closest('.dbg-group').dataset.file] = (visible[tr.closest('.dbg-group').dataset.file] || 0) || show;
    if (show) visible[tr.closest('.dbg-group').dataset.file] = true;
  });
  document.querySelectorAll('#dbgList .dbg-group').forEach(card => {
    card.style.display = visible[card.dataset.file] ? '' : 'none';
  });
  $('#filterTip').style.display = DBG_FILTER ? '' : 'none';
  $('#filterTipText').textContent =
    { PASS: '通过', FAIL: '失败 / 异常', SKIP: '跳过' }[DBG_FILTER] || '';
}

function dbgToggleFilter(key) {
  DBG_FILTER = (DBG_FILTER === key) ? '' : key;
  dbgApplyFilter();
  dbgUpdateStats();
}

/* ---------------- 单项调试 / 全部验证 ---------------- */
async function dbgRunOne(id) {
  const btn = document.querySelector('#dbgList button[data-id="' + CSS.escape(id) + '"]');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ 执行中'; }
  try {
    const d = await postJson('/api/debug/run', { id: id });
    if (d.ok) {
      DBG_RESULTS[id] = d.result;
      dbgUpdateRow(id);
    } else toast('执行失败: ' + (d.msg || ''), false);
  } catch (e) {
    toast('请求异常: ' + e, false);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '▶ 调试'; }
  }
}

function dbgUpdateRow(id) {
  const tr = document.querySelector('#dbgList tbody tr[data-id="' + CSS.escape(id) + '"]');
  if (!tr) return;
  const r = DBG_RESULTS[id];
  tr.dataset.status = r.status;
  tr.querySelector('.cell-status').innerHTML = dbgBadge(r.status);
  tr.querySelector('.cell-dur').textContent = r.duration_ms + 'ms';
  const detail = (r.error ? '❌ ' + r.error + '\n' : '') + (r.detail || '-');
  tr.querySelector('.cell-detail').textContent = detail.length > 90 ? detail.slice(0, 90) + '…' : detail;
  tr.querySelector('.cell-detail').title = detail;
  dbgApplyFilter();
  dbgUpdateStats();
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
    // 保存审查记录（快照）
    const results = DBG_ITEMS.map(it => DBG_RESULTS[it.id]).filter(Boolean);
    const d = await postJson('/api/debug/records', { results: results, duration_ms: Date.now() - t0 });
    if (d.ok) {
      toast('全部验证完成，审查记录 ' + d.record_id + ' 已保存（通过 ' + d.summary.passed +
        ' / 失败 ' + d.summary.failed + ' / 跳过 ' + d.summary.skipped + '）', d.summary.failed === 0);
      REC_PAGE = 1;
      await dbgLoadRecords();
    } else {
      toast('验证完成，但记录保存失败: ' + (d.msg || ''), false);
    }
  } finally {
    DBG_RUNNING = false;
    $('#btnRunAll').disabled = false;
  }
}

/* ---------------- 历史记录 ---------------- */
async function dbgLoadRecords() {
  const d = await api('/api/debug/records?page=' + REC_PAGE);
  const tb = $('#recList');
  if (!d.ok) { tb.innerHTML = '<tr><td colspan="6">记录加载失败</td></tr>'; return; }
  $('#recCount').textContent = '· 共 ' + d.total + ' 条';
  if (!d.records.length) {
    tb.innerHTML = '<tr><td colspan="6"><div class="empty">暂无审查记录，点右上角「▶ 全部验证」生成第一份</div></td></tr>';
    $('#recPager').innerHTML = '';
    return;
  }
  tb.innerHTML = d.records.map(r =>
    '<tr><td><b>' + esc(r.id) + '</b></td>' +
    '<td class="muted">' + esc(r.time) + '</td>' +
    '<td>' + runStatsHtml({ total: r.summary.total, passed: r.summary.passed, failed: r.summary.failed, error: 0 }) +
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
  $('#dbgList').scrollIntoView({ behavior: 'smooth', block: 'start' });
  toast('正在查看历史记录 ' + id + '（共 ' + (d.record.results || []).length + ' 项）');
}

function dbgBackToLive() {
  DBG_RECORD = null; DBG_RESULTS = {}; DBG_FILTER = '';
  dbgRender(); dbgShowBanner(null);
  toast('已返回实时模式');
}

async function dbgDeleteRecord(id) {
  const yes = await confirmModal('删除审查记录', '将删除记录 ' + id + '，不可恢复。', true);
  if (!yes) return;
  const d = await del('/api/debug/records/' + encodeURIComponent(id));
  toast(d.msg || (d.ok ? '已删除' : '删除失败'), d.ok);
  if (DBG_RECORD && DBG_RECORD.id === id) dbgBackToLive();
  await dbgLoadRecords();
}

function dbgShowBanner(record) {
  const el = $('#viewBanner');
  if (!record) { el.style.display = 'none'; return; }
  const s = record.summary;
  el.style.display = '';
  el.innerHTML = '🗂 正在查看历史记录 <b>' + esc(record.id) + '</b>（' + esc(record.time) +
    ' · 通过 <b>' + s.passed + '</b> / 失败 <b>' + s.failed + '</b> / 跳过 <b>' + s.skipped + '</b>）' +
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
  dbgRender();
  await dbgLoadRecords();

  $('#btnRunAll').addEventListener('click', dbgRunAll);
  $('#btnReload').addEventListener('click', () => location.reload());
  // 统计卡 = 筛选器（不加新按钮，点击现有字段）
  $('#stPass').closest('.stat').addEventListener('click', () => dbgToggleFilter('PASS'));
  $('#stFail').closest('.stat').addEventListener('click', () => dbgToggleFilter('FAIL'));
  $('#stSkip').closest('.stat').addEventListener('click', () => dbgToggleFilter('SKIP'));
  // 文件锚点跳转（事件委托）
  $('#fileChips').addEventListener('click', (e) => {
    const chip = e.target.closest('.chip');
    if (!chip) return;
    const el = document.getElementById(chip.dataset.anchor);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  // 列表按钮（事件委托，筛选重建后仍有效）
  $('#dbgList').addEventListener('click', (e) => {
    const b = e.target.closest('button.dbg-run');
    if (b) dbgRunOne(b.dataset.id);
  });
  $('#recList').addEventListener('click', (e) => {
    const v = e.target.closest('button.dbg-view');
    if (v) return dbgViewRecord(v.dataset.id);
    const del2 = e.target.closest('button.dbg-del');
    if (del2) dbgDeleteRecord(del2.dataset.id);
  });
}

document.addEventListener('DOMContentLoaded', dbgInit);
