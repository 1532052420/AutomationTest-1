/* 代码审查页 · 前端逻辑（独立文件，仅复用 app.js 的公共工具与侧边栏） */
'use strict';

let DBG_ITEMS = [];
let DBG_RUNNING = false;

function dbgBadge(status) {
  const map = { PASS: 'PASSED', FAIL: 'FAILED', SKIP: 'SKIPPED' };
  return statusBadge(map[status] || status).replace('class="status', 'data-st="' + status + '" class="status');
}

function dbgRender() {
  const byFile = {};
  DBG_ITEMS.forEach(it => {
    (byFile[it.file] = byFile[it.file] || []).push(it);
  });
  const files = Object.keys(byFile).sort();
  const host = $('#dbgList');
  host.innerHTML = files.map(f => {
    const rows = byFile[f].map(it =>
      '<tr id="row-' + esc(it.id) + '">' +
      '<td style="width:44%"><b>' + esc(it.title) + '</b><div class="muted" style="font-size:12px">' + esc(it.id) + '</div></td>' +
      '<td class="cell-status"><span class="status st-PENDING">待验证</span></td>' +
      '<td class="cell-dur muted">-</td>' +
      '<td class="cell-detail muted">-</td>' +
      '<td style="width:90px"><button class="ghost mini" onclick="dbgRunOne(\'' + esc(it.id) + '\')">▶ 调试</button></td>' +
      '</tr>'
    ).join('');
    return '<div class="card"><h3>📄 ' + esc(f) + ' <span class="muted" style="font-size:12px">(' + byFile[f].length + ' 项)</span></h3>' +
      '<div class="tblwrap"><table><thead><tr><th>调试项</th><th>结果</th><th>耗时</th><th>详情</th><th>操作</th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table></div></div>';
  }).join('');
  DBG_ST.updateTotal();
}

const DBG_ST = {
  updateTotal() {
    $('#stTotal').textContent = DBG_ITEMS.length + ' / ' + new Set(DBG_ITEMS.map(i => i.file)).size;
  },
  apply(r) {
    const tr = $('#row-' + CSS.escape(r.id));
    if (!tr) return;
    tr.querySelector('.cell-status').innerHTML = dbgBadge(r.status);
    tr.querySelector('.cell-dur').textContent = r.duration_ms + 'ms';
    const detail = (r.error ? ('❌ ' + r.error + '\n') : '') + (r.detail || '-');
    const cell = tr.querySelector('.cell-detail');
    cell.textContent = detail.length > 90 ? detail.slice(0, 90) + '…' : detail;
    cell.title = detail;
    cell.style.whiteSpace = 'pre-wrap';
    this.counts();
  },
  counts() {
    const c = { PASS: 0, FAIL: 0, SKIP: 0 };
    DBG_ITEMS.forEach(it => {
      const tr = $('#row-' + CSS.escape(it.id));
      if (!tr) return;
      const s = tr.querySelector('.cell-status .status');
      if (s) c[s.dataset.st || ''] = (c[s.dataset.st || ''] || 0) + 1;
    });
    $('#stPass').textContent = c.PASS || 0;
    $('#stFail').textContent = c.FAIL || 0;
    $('#stSkip').textContent = c.SKIP || 0;
  }
};

/* 状态徽章已带 data-st（dbgBadge 内注入），供 DBG_ST.counts 统计 */

async function dbgRunOne(id) {
  const tr = $('#row-' + CSS.escape(id));
  const btn = tr ? tr.querySelector('button') : null;
  if (btn) { btn.disabled = true; btn.textContent = '⏳ 执行中'; }
  try {
    const d = await postJson('/api/debug/run', { id: id });
    if (d.ok) DBG_ST.apply(d.result);
    else toast('执行失败: ' + (d.msg || ''), false);
  } catch (e) {
    toast('请求异常: ' + e, false);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '▶ 调试'; }
  }
}
window.dbgRunOne = dbgRunOne;

async function dbgRunAll() {
  if (DBG_RUNNING) return;
  DBG_RUNNING = true;
  $('#btnRunAll').disabled = true;
  const sub = $('#subTitle');
  try {
    for (let i = 0; i < DBG_ITEMS.length; i++) {
      const it = DBG_ITEMS[i];
      sub.textContent = '全部验证中… ' + (i + 1) + '/' + DBG_ITEMS.length + '（' + it.id + '）';
      await dbgRunOne(it.id);
    }
    sub.textContent = '全部验证完成 ✓（结果已保留在列表中）';
    toast('全部验证完成');
  } finally {
    DBG_RUNNING = false;
    $('#btnRunAll').disabled = false;
  }
}

async function dbgInit() {
  renderSidebar('/debug');
  const d = await api('/api/debug/items');
  if (!d.ok) { toast('清单加载失败: ' + (d.msg || ''), false); return; }
  DBG_ITEMS = d.items || [];
  if ((d.load_errors || []).length) {
    toast('有 ' + d.load_errors.length + ' 个检查模块自身加载失败，将在执行时呈现', false);
  }
  dbgRender();
  $('#btnRunAll').addEventListener('click', dbgRunAll);
  $('#btnReload').addEventListener('click', () => location.reload());
}

document.addEventListener('DOMContentLoaded', dbgInit);
