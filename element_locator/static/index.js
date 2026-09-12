/* App 元素定位器前端逻辑（原生 JS，无外部依赖） */
'use strict';

const state = {
  width: 0, height: 0,
  tree: null, all: [],
  shot: null,
  selUid: null, selNode: null,
  hitCands: null,
  // 用例工作台
  currentCase: null,      // 当前用例草稿（统一步骤结构 steps 数组）
  pages: [],              // 现有页面文件
  eleFiles: [],           // 现有元素文件
  elementsAll: {},        // { 元素文件: [元素名...] }
  defaultEleFile: 'locator_gui_elements.py',
  caseFiles: [],          // 现有用例文件 [{file, class, methods:[...]}]（「保存并添加到用例」目标下拉用）
};
// 右侧教学：搜索时展开所有分类，否则默认收起（点分类标题展开）
var tutExpandAll = false;

const $ = (id) => document.getElementById(id);

/* 步骤类型（与后端 case_generator.STEP_TYPES 一致）：值 -> 中文名 + 是否需要元素 + 是否需要参数 */
const STEP_TYPES = [
  { v: 'click', n: '点击', el: true, param: false, ph: '' },
  { v: 'input', n: '输入', el: true, param: true, ph: '输入内容' },
  { v: 'long_press', n: '长按', el: true, param: false, ph: '' },
  { v: 'assert_visible', n: '断言存在', el: true, param: false, ph: '' },
  { v: 'assert_text', n: '断言文本', el: true, param: true, ph: '期望文本' },
  { v: 'assert_toast', n: '断言Toast', el: false, param: true, ph: 'toast文本' },
  { v: 'screenshot', n: '截图', el: false, param: true, ph: '截图名' },
  { v: 'tap', n: '坐标点击', el: false, param: true, ph: 'x,y' },
  { v: 'sleep', n: '等待', el: false, param: true, ph: '秒数' },
  { v: 'custom', n: '自定义代码', el: false, param: true, ph: '代码行' },
];
const stepTypeInfo = (v) => STEP_TYPES.find(t => t.v === v) || STEP_TYPES[0];

function genStepDesc(s) {
  const t = stepTypeInfo(s.type);
  if (s.desc && s.desc.trim()) return s.desc.trim();
  const p = s.param || '';
  switch (s.type) {
    case 'click': return '点击' + s.element;
    case 'input': return '在' + s.element + '输入「' + p + '」';
    case 'long_press': return '长按' + s.element;
    case 'assert_visible': return '断言' + s.element + '出现';
    case 'assert_text': return '断言' + s.element + '文本为「' + p + '」';
    case 'assert_toast': return '断言toast「' + p + '」';
    case 'screenshot': return '截图：' + p;
    case 'tap': return '点击坐标(' + p + ')';
    case 'sleep': return '等待' + p + '秒';
    case 'custom': return (p || '自定义代码').split('\n')[0];
    default: return '未定义步骤';
  }
}

/* ---------- 工具 ---------- */
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function copyText(text, btn) {
  const done = () => {
    if (!btn) return;
    btn.textContent = '已复制 ✓'; btn.classList.add('copied');
    setTimeout(() => { btn.textContent = '复制'; btn.classList.remove('copied'); }, 1500);
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done));
  } else { fallbackCopy(text, done); }
}
function fallbackCopy(text, done) {
  const ta = document.createElement('textarea');
  ta.value = text; document.body.appendChild(ta); ta.select();
  try { document.execCommand('copy'); } catch (e) {}
  document.body.removeChild(ta); done();
}

/* ---------- 初始化 ---------- */
async function init() {
  const st = await fetch('/api/status').then(r => r.json()).catch(() => null);
  const devInfo = $('dev-info');
  // 版本号以服务端为准（页面缓存旧版本时也能纠正显示）
  if (st && st.version) $('app-version').textContent = st.version;
  if (st && st.ok) {
    devInfo.textContent = '📱 ' + st.device.model + ' | ' + st.device.serial + ' | Android ' + st.device.platformVersion;
    devInfo.className = 'dev-info ok';
  } else {
    devInfo.textContent = st ? st.msg : '连接失败';
    devInfo.className = 'dev-info bad';
  }
  loadLibraryFiles();
  loadPages();
  renderTutorials();
  if (st && st.ok) refresh();
  $('btn-refresh').addEventListener('click', refresh);
  $('btn-case').addEventListener('click', openCaseModal);
  $('shot').addEventListener('click', onShotClick);
  $('shot').addEventListener('dblclick', onShotDblClick);   // 双击执行器：设备真实点击
  // 截图显示尺寸：机型预设切换 + 记住上次选择
  // （判空防御：浏览器缓存了旧版 index.html 时该下拉不存在，避免 init 中断）
  const sizeSel = document.getElementById('shot-size-sel');
  if (sizeSel) {
    sizeSel.addEventListener('change', applyShotSize);
    try { sizeSel.value = localStorage.getItem('locator_shot_size') || 'default'; } catch (e) {}
    applyShotSize();
  }
  $('btn-tap').addEventListener('click', onTapElement);      // ▶ 设备上点击
  $('tree-search').addEventListener('input', onTreeSearch);
  $('tut-search').addEventListener('input', onTutSearch);
  $('btn-add').addEventListener('click', openModal);
  $('btn-modal-cancel').addEventListener('click', () => {
    if (state.continuousAdd) { state.continuousAdd = false; updateContChip(); }
    $('modal-mask').style.display = 'none';
  });
  $('btn-modal-save').addEventListener('click', () => onSaveElement(false));
  $('btn-modal-save-continue').addEventListener('click', () => onSaveElement(true));
  // 连续添加：退出悬浮条；已有元素复用面板三按钮
  $('cont-add-chip').addEventListener('click', () => { state.continuousAdd = false; updateContChip(); });
  $('btn-dup-reuse').addEventListener('click', () => { const r = dupResolver; closeDupPanel(); if (r) r('reuse'); });
  $('btn-dup-update').addEventListener('click', () => { const r = dupResolver; closeDupPanel(); if (r) r('update'); });
  $('btn-dup-cancel').addEventListener('click', () => { const r = dupResolver; closeDupPanel(); if (r) r('cancel'); });
  document.querySelectorAll('input[name="el-purpose"]').forEach(r => r.addEventListener('change', onPurposeChange));
  $('el-op-type').addEventListener('change', onOpTypeChange);
  $('el-op-param').addEventListener('input', updatePreview);
  $('el-case-file').addEventListener('change', onCaseFileChange);
  $('el-case-method').addEventListener('change', updatePreview);
  // 三栏字段变动 → 三个示例代码区实时刷新
  ['el-name', 'el-value', 'el-comment', 'el-case-comment', 'el-op-comment'].forEach(id => $(id).addEventListener('input', updatePreview));
  ['el-type', 'el-wait'].forEach(id => $(id).addEventListener('change', updatePreview));
  $('el-wait-sec').addEventListener('input', updatePreview);
  $('el-insert-pos').addEventListener('change', () => { renderStepsList(currentSteps()); updatePreview(); });
  $('btn-case-cancel').addEventListener('click', () => $('case-mask').style.display = 'none');
  $('btn-case-save').addEventListener('click', onSaveCase);
  $('btn-step-add').addEventListener('click', () => addStepRow('click'));
  $('btn-step-custom').addEventListener('click', () => addStepRow('custom'));
  // 用例字段联动：文件名 → 自动填充类名/方法名/页面类名
  ['case-file', 'case-page-file'].forEach(id => {
    $(id).addEventListener('change', syncCaseNames);
    $(id).addEventListener('input', syncCaseNames);
  });
  $('case-ele-file').addEventListener('change', () => {
    if (state.currentCase) state.currentCase.elementsFile = $('case-ele-file').value;
  });
  // 顶部快速打开：用例 / 元素文件 / 页面操作 下拉打开编辑
  loadHeaderOpeners();
  $('open-case-sel').addEventListener('change', (e) => { onOpenHdrFile('case', e.target.value); e.target.value = ''; });
  $('open-ele-sel').addEventListener('change', (e) => { onOpenHdrFile('element', e.target.value); e.target.value = ''; });
  $('open-page-sel').addEventListener('change', (e) => { onOpenHdrFile('page', e.target.value); e.target.value = ''; });
  $('btn-view-close').addEventListener('click', () => { $('view-mask').style.display = 'none'; });
  $('btn-view-save').addEventListener('click', onSaveHdrFile);
  bindHelpIcons();
}

/* ---------- 顶部快速打开：用例 / 元素定位 / 页面操作 文件编辑 ---------- */
async function loadHeaderOpeners() {
  const cs = await fetch('/api/cases').then(r => r.json()).catch(() => null);
  const caseSel = $('open-case-sel');
  if (cs && cs.ok && caseSel) {
    caseSel.innerHTML = '<option value="">📂 打开用例…</option>' +
      (cs.case_info || []).map(c => '<option value="' + esc(c.file) + '">' + esc(c.file) + '</option>').join('');
  }
  const lib = await fetch('/api/library').then(r => r.json()).catch(() => null);
  const eleSel = $('open-ele-sel');
  if (lib && lib.ok && eleSel) {
    eleSel.innerHTML = '<option value="">🗂 打开元素文件…</option>' +
      (lib.files || []).map(f => '<option value="' + esc(f) + '">' + esc(f) + '</option>').join('');
  }
  const pg = await fetch('/api/pages').then(r => r.json()).catch(() => null);
  const pageSel = $('open-page-sel');
  if (pg && pg.ok && pageSel) {
    pageSel.innerHTML = '<option value="">🧩 打开页面操作…</option>' +
      (pg.pages || []).map(f => '<option value="' + esc(f) + '">' + esc(f) + '</option>').join('');
  }
}

// 当前打开的文件（{kind, filename}），保存时用
let viewFile = null;

async function onOpenHdrFile(kind, filename) {
  if (!filename) return;
  const q = { case: 'case=', element: 'element=', page: 'page=' }[kind];
  const r = await fetch('/api/file_content?' + q + encodeURIComponent(filename)).then(r => r.json()).catch(() => null);
  if (!r || !r.ok) { alert((r && r.msg) || '读取失败'); return; }
  viewFile = { kind: kind, filename: filename };
  $('view-title').textContent = '📄 ' + r.title;
  $('view-content').value = r.content;
  setViewStatus('可直接修改，点「💾 保存修改」写回文件（保存前自动做语法检查）', '');
  $('view-mask').style.display = 'flex';
}

function setViewStatus(msg, cls) {
  const el = $('view-status');
  el.textContent = msg;
  el.className = 'hint' + (cls ? ' ' + cls : '');
}

async function onSaveHdrFile() {
  if (!viewFile) return;
  const btn = $('btn-view-save');
  btn.disabled = true; btn.textContent = '保存中…';
  setViewStatus('正在保存…', '');
  const r = await fetch('/api/save_file', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kind: viewFile.kind, filename: viewFile.filename, content: $('view-content').value }),
  }).then(r => r.json()).catch(() => null);
  btn.disabled = false; btn.textContent = '💾 保存修改';
  if (!r || !r.ok) {
    setViewStatus((r && r.msg) || '保存失败：服务异常', 'bad');
    alert((r && r.msg) || '保存失败：服务异常');
    return;
  }
  setViewStatus('✓ ' + r.msg, 'ok');
  // 元素/用例/页面文件可能被手改，刷新相关下拉与状态
  loadHeaderOpeners(); loadLibraryFiles(); loadCaseFiles(); loadPages();
}

/* ---------- 字段帮助：鼠标移到「?」即显示该字段有什么用 ---------- */
const HELP_TIP_W = 330;
function bindHelpIcons() {
  const tip = $('help-tip');
  let showTimer = null, hideTimer = null, tipOn = false;
  function showTip(icon) {
    clearTimeout(hideTimer);
    const text = icon.getAttribute('data-help') || '';
    tip.textContent = text;
    tip.style.display = '';
    const r = icon.getBoundingClientRect();
    let left = r.left;
    if (left + HELP_TIP_W > window.innerWidth - 10) left = Math.max(10, window.innerWidth - HELP_TIP_W - 10);
    let top = r.bottom + 6;
    const estH = text.length > 90 ? 260 : 160;
    if (top + estH > window.innerHeight - 10) top = Math.max(10, r.top - estH - 6);
    tip.style.left = left + 'px';
    tip.style.top = top + 'px';
    tipOn = true;
  }
  function hideTip() {
    // 鼠标移出问号后延迟关闭；若已移入气泡则保持
    if (tipOn) {
      clearTimeout(hideTimer);
      hideTimer = setTimeout(() => { tip.style.display = 'none'; tipOn = false; }, 180);
    }
  }
  document.addEventListener('mouseover', (e) => {
    const icon = e.target.closest('.help-icon');
    if (icon) { showTip(icon); return; }
  });
  document.addEventListener('mouseout', (e) => {
    const icon = e.target.closest && e.target.closest('.help-icon');
    if (icon) return;
    const to = e.relatedTarget;
    if (to && to.closest && to.closest('.help-tip')) return;  // 移入气泡 → 保持显示
    hideTip();
  });
  // 气泡本身：移入保持、移出关闭
  tip.addEventListener('mouseenter', () => { clearTimeout(hideTimer); });
  tip.addEventListener('mouseleave', () => { tip.style.display = 'none'; tipOn = false; });
}

/* ---------- 刷新：截图 + 元素树 ---------- */
async function refresh() {
  $('btn-refresh').textContent = '刷新中…'; $('btn-refresh').disabled = true;
  try {
    const r = await fetch('/api/refresh', { method: 'POST' }).then(r => r.json()).catch(() => null);
    if (!r || !r.ok) {
      alert(r && r.msg ? r.msg : '刷新失败');
      return;
    }
    state.width = r.width; state.height = r.height;
    state.tree = r.tree; state.all = r.all || [];
    // 统一分配 uid（DFS 先父后子，tree 与 all 顺序一致）
    let seq = 1;
    (function assign(node) { node.uid = seq++; node.children.forEach(assign); })(state.tree);
    let k = 0;
    (function assignAll(node) { state.all[k++].uid = node.uid; node.children.forEach(assignAll); })(state.tree);
    state.selUid = null; state.selNode = null;
    state.hitCands = null;
    $('detail').style.display = 'none';
    $('shot-empty').style.display = 'none';
    const img = $('shot');
    img.src = r.screenshot; img.style.display = 'block';
    renderTree(state.tree);
  } catch (err) {
    console.error('[locator] refresh error:', err);
    // 把错误直接显示在页面上，避免 try/finally 静默吞掉异常导致"点了没反应"
    $('shot-empty').textContent = '刷新出错: ' + (err && err.message ? err.message : String(err));
    $('shot-empty').style.display = 'block';
  } finally {
    $('btn-refresh').textContent = '🔄 刷新'; $('btn-refresh').disabled = false;
  }
}

/* ---------- 截图点击命中 ---------- */
// 由点击事件算出命中的最内层元素 + 所有包含该点的候选（按面积升序）
function hitFromEvent(e) {
  if (!state.all.length) return null;
  const img = $('shot');
  const rect = img.getBoundingClientRect();
  if (rect.width <= 0) return null;
  // 点击换算：先按截图(PNG)实际像素定位，再映射到 uiautomator XML 坐标。
  // 关键：PNG 尺寸(如720x1600)与 XML 尺寸(如720x1536)可能不一致——
  // 华为机的 PNG 底部多了虚拟导航条(64px)，XML 是顶部对齐的内容区坐标。
  // 所以宽度同值，高度用 PNG 像素点亮的 y，超过 XML 高度部分按导航条处理。
  const natW = img.naturalWidth || state.width;
  const natH = img.naturalHeight || state.height;
  const pngX = (e.clientX - rect.left) / rect.width * natW;
  const pngY = (e.clientY - rect.top) / rect.height * natH;
  const px = pngX;                          // 宽同值
  const py = Math.min(pngY, state.height);  // 顶部对齐同值，多余的底部是导航条
  // 收集所有包含该点的元素，按面积升序（越小越内层），作为候选列表
  const cands = [];
  for (const n of state.all) {
    const b = n.bounds_num;
    if (!b || b.length !== 4) continue;
    const [x1, y1, x2, y2] = b;
    if (x1 <= px && px <= x2 && y1 <= py && py <= y2) {
      const area = (x2 - x1) * (y2 - y1);
      if (area > 0) cands.push({ node: n, area });
    }
  }
  cands.sort((a, b) => a.area - b.area);
  if (!cands.length) return null;
  return { hit: cands[0].node, cands: cands.map(c => c.node) };
}
function onShotClick(e) {
  const r = hitFromEvent(e);
  if (!r) return;
  state.hitCands = r.cands;
  selectNode(r.hit.uid);
}
// 双击执行器：双击截图 = 在设备上真实点击该元素（验证定位是否准确）
function onShotDblClick(e) {
  const r = hitFromEvent(e);
  if (!r) return;
  state.hitCands = r.cands;
  selectNode(r.hit.uid);
  tapOnDevice(r.hit.center, r.hit.text || r.hit['resource-id'] || '双击元素');
}
// 「▶ 设备上点击」按钮：点击选中的元素
async function onTapElement() {
  const n = state.selNode;
  if (!n) { alert('请先选中一个元素'); return; }
  if (!n.center) { alert('该元素没有坐标，无法点击'); return; }
  tapOnDevice(n.center, n.text || n['resource-id'] || '选中元素');
}
async function tapOnDevice(center, label) {
  if (!center || center.length < 2) return;
  const x = center[0], y = center[1];
  const r = await fetch('/api/tap', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ x: x, y: y }) })
    .then(r => r.json()).catch(() => null);
  const tip = $('tap-tip');
  if (r && r.ok) {
    tip.textContent = '✓ 已点击设备（' + label + '）(' + x + ',' + y + ')，刷新中…';
    tip.className = 'tap-tip ok';
    refresh();
  } else {
    tip.textContent = (r && r.msg ? r.msg : '点击失败');
    tip.className = 'tap-tip err';
  }
}

/* ---------- 树渲染 ---------- */
function renderTree(tree) {
  const box = $('tree');
  box.innerHTML = '';
  box.appendChild(buildTreeUl(tree));
}
function buildTreeUl(node) {
  const ul = document.createElement('ul');
  appendNode(ul, node);
  return ul;
}
// 把节点 n 渲染成一个 li 追加到 ul；有子节点时嵌套可折叠层（递归子节点，而不是重复渲染 n 自己）
function appendNode(ul, n) {
  const li = document.createElement('li');
  const row = document.createElement('div');
  row.className = 'tnode' + (state.selUid === n.uid ? ' sel' : '');
  row.dataset.uid = n.uid;
  const hasKids = n.children && n.children.length > 0;
  const arrow = document.createElement('span');
  arrow.className = 'arrow';
  arrow.textContent = hasKids ? '▾' : '';
  const text = document.createElement('span');
  text.className = 't-text';
  text.textContent = (n.text && n.text.trim()) ? truncate(n.text, 18) : (n['resource-id'] ? truncate(n['resource-id'].split('/').pop(), 22) : (n['content-desc'] || n.class || 'node'));
  if (!n.text && !n['resource-id']) { text.style.color = '#9ca3af'; }
  row.appendChild(arrow);
  row.appendChild(text);
  if (n['resource-id']) {
    const rid = document.createElement('span');
    rid.className = 't-rid'; rid.textContent = truncate(n['resource-id'], 24);
    row.appendChild(rid);
  }
  if (n.clickable) {
    const badge = document.createElement('span');
    badge.className = 'clickable-badge'; badge.textContent = '可点';
    row.appendChild(badge);
  }
  row.addEventListener('click', (ev) => { ev.stopPropagation(); selectNode(n.uid); });
  li.appendChild(row);
  if (hasKids) {
    const sub = document.createElement('div');
    const childUl = document.createElement('ul');
    n.children.forEach(c => appendNode(childUl, c));
    sub.appendChild(childUl);
    const toggle = () => { sub.style.display = sub.style.display === 'none' ? '' : 'none'; arrow.textContent = sub.style.display === 'none' ? '▸' : '▾'; };
    row.addEventListener('dblclick', toggle);
    // 保留展开
    li.appendChild(sub);
  }
  ul.appendChild(li);
}
function truncate(s, n) { s = String(s || ''); return s.length > n ? s.slice(0, n) + '…' : s; }

/* 树搜索：按 text / resource-id / class 过滤（命中节点保留，父链保留） */
function onTreeSearch(e) {
  if (!state.tree) return;
  const kw = e.target.value.trim().toLowerCase();
  if (!kw) { renderTree(state.tree); return; }
  const filtered = filterTree(state.tree, kw);
  $('tree').innerHTML = '';
  $('tree').appendChild(buildTreeUl(filtered));
}
function filterTree(node, kw) {
  const children = (node.children || [])
    .map(c => filterTree(c, kw))
    .filter(Boolean);
  const selfHit = [node.text, node['resource-id'], node.class].some(v => String(v || '').toLowerCase().includes(kw));
  if (selfHit || children.length) {
    return Object.assign({}, node, { children });
  }
  return null;
}

/* ---------- 选中元素 ---------- */
function findByUid(node, uid) {
  if (node.uid === uid) return node;
  for (const c of node.children || []) { const r = findByUid(c, uid); if (r) return r; }
  return null;
}
function selectNode(uid) {
  if (!state.tree) return;
  const node = findByUid(state.tree, uid);
  if (!node) return;
  state.selUid = uid; state.selNode = node;
  // 树高亮
  document.querySelectorAll('.tree .tnode').forEach(el => {
    el.classList.toggle('sel', +el.dataset.uid === uid);
  });
  renderDetail(node);
  highlightShot(node);
  // 连续添加模式：选中元素即自动弹出「添加到元素库」——点一个录一步，直到退出
  if (state.continuousAdd) openModal();
}
function highlightShot(node) {
  const ov = $('shot-overlay');
  const img = $('shot');
  if (!node.bounds_num || img.style.display === 'none') { ov.style.display = 'none'; return; }
  const scale = img.clientWidth / state.width;
  const [x1, y1, x2, y2] = node.bounds_num;
  ov.style.display = 'block';
  // 截图选了机型预设时居中显示，高亮框要加上图片在栏内的偏移
  ov.style.left = (img.offsetLeft + x1 * scale) + 'px';
  ov.style.top = (img.offsetTop + y1 * scale) + 'px';
  ov.style.width = ((x2 - x1) * scale) + 'px';
  ov.style.height = ((y2 - y1) * scale) + 'px';
}

/* ---------- 截图显示尺寸（默认铺满栏宽；机型预设按其逻辑屏幕尺寸居中显示） ---------- */
// iPhone15Pro 逻辑分辨率 393×852；iQOO15 为 2K(1440×3168) 按 560dpi 换算约 411×905
const SHOT_SIZES = { iphone15pro: 393, iqoo15: 411 };
function applyShotSize() {
  const sel = $('shot-size-sel');
  const img = $('shot');
  const v = sel ? sel.value : 'default';
  try { localStorage.setItem('locator_shot_size', v); } catch (e) { /* 隐私模式忽略 */ }
  const w = SHOT_SIZES[v];
  if (w) {
    img.classList.add('centered');
    img.style.width = w + 'px';
    img.style.height = 'auto';
  } else {
    img.classList.remove('centered');
    img.style.width = '';
    img.style.height = '';
  }
  if (state.selNode) highlightShot(state.selNode);
}
function renderDetail(node) {
  $('detail').style.display = 'block';
  // 候选元素：截图同一点可能命中多层（容器/文字/按钮），点选更精确的
  const candBox = $('hit-cands');
  if (state.hitCands && state.hitCands.length > 1) {
    candBox.style.display = '';
    candBox.innerHTML = '<span class="cand-label">命中 ' + state.hitCands.length + ' 层，选一个：</span>' +
      state.hitCands.map(n =>
        '<button class="cand-chip' + (n.uid === node.uid ? ' sel' : '') + '" data-uid="' + n.uid + '">'
        + esc(candName(n)) + '</button>').join('');
    candBox.querySelectorAll('.cand-chip').forEach(btn => {
      btn.addEventListener('click', () => selectNode(+btn.dataset.uid));
    });
  } else {
    candBox.style.display = 'none';
  }
  const ATTRS = ['text', 'resource-id', 'class', 'content-desc', 'bounds', 'clickable', 'focusable', 'scrollable', 'selected', 'enabled', 'package', 'index'];
  const rows = ATTRS.filter(k => node[k] !== undefined && node[k] !== '' && node[k] !== false)
    .map(k => '<tr><td>' + esc(k) + '</td><td>' + esc(node[k]) + '</td></tr>')
    .join('');
  // 重复 resource-id 提示
  const rid = node['resource-id'];
  const sameCount = rid ? state.all.filter(n => n['resource-id'] === rid).length : 0;
  const dupTip = sameCount > 1
    ? '<div class="dup-tip">⚠ 该 resource-id 页面有 <b>' + sameCount + '</b> 个相同的，定位会不准。' +
      '用例里用 <code>appOperator.getElements(元素)[i]</code> 按下标取第 i 个（0 开始），' +
      '或用下面带 <code>instance</code> / 下标 的写法。</div>' : '';
  $('detail-attrs').innerHTML = rows + '<tr><td>中心坐标</td><td>' + (node.center ? node.center.join(', ') : '-') + '</td></tr>';
  $('dup-tip').innerHTML = dupTip;
  // 定位写法
  const locs = node.locators || [];
  const box = $('locators');
  box.innerHTML = '';
  if (!locs.length) { box.innerHTML = '<div class="loc-item">该元素无合适定位表达式</div>'; return; }
  locs.forEach((loc, i) => {
    const div = document.createElement('div');
    div.className = 'loc-item';
    div.innerHTML = '<label><input type="radio" name="loc" data-lt="' + esc(loc.locator_type) + '" data-val="' + esc(loc.value) + '"' + (i === 0 ? ' checked' : '') + '> <span class="loc-kind">' + esc(loc.kind) + '</span> <span class="loc-desc">' + esc(loc.desc || '') + '</span></label>'
      + '<code>' + esc(loc.value) + '</code>';
    box.appendChild(div);
  });
}
function candName(n) {
  if (n.text && n.text.trim()) return n.text.trim().slice(0, 12);
  const r = (n['resource-id'] || '').split('/').pop();
  if (r) return r;
  if (n['content-desc']) return n['content-desc'].slice(0, 12);
  return (n.class || 'node').split('.').pop();
}
function selectedLocator() {
  const radio = document.querySelector('input[name="loc"]:checked');
  return radio ? { type: radio.dataset.lt, value: radio.dataset.val } : null;
}

/* ---------- 添加到元素库 ---------- */
async function loadLibraryFiles() {
  const r = await fetch('/api/library').then(r => r.json()).catch(() => null);
  if (!r || !r.ok) return;
  state.eleFiles = r.files || [];
  state.defaultEleFile = r.default || 'locator_gui_elements.py';
  $('el-file').innerHTML = r.files.map(f => '<option value="' + esc(f) + '">' + esc(f) + '</option>').join('');
  $('case-ele-file').innerHTML = r.files.map(f => '<option value="' + esc(f) + '">' + esc(f) + '</option>').join('');
}
async function loadPages() {
  const r = await fetch('/api/pages').then(r => r.json()).catch(() => null);
  if (!r || !r.ok) return;
  state.pages = r.pages || [];
  state.elementsAll = r.elements || {};
  $('case-page-file').innerHTML = [''].concat(state.pages.map(f => f))
    .map(f => '<option value="' + esc(f) + '">' + (f || '─ 自动新建页面文件（默认，与用例同名） ─') + '</option>').join('');
  $('case-ele-file').innerHTML = state.eleFiles.map(f => '<option value="' + esc(f) + '">' + esc(f) + '</option>').join('');
}
function allElementNames() {
  const seen = [];
  Object.keys(state.elementsAll).forEach(f => {
    (state.elementsAll[f] || []).forEach(n => { if (seen.indexOf(n) < 0) seen.push(n); });
  });
  return seen;
}
async function openModal() {
  if (!state.selNode) { alert('请先在截图或元素树里选中一个元素'); return; }
  const node = state.selNode;
  // 自动名称：优先 resource-id 末段，其次 text 截断
  let auto = '';
  const rid = node['resource-id'] || '';
  if (rid && rid.includes('/')) auto = rid.split('/').pop();
  else if (node.text && node.text.trim()) auto = node.text.trim().replace(/\s+/g, '_').slice(0, 20);
  else auto = 'element_' + state.selUid;
  $('el-name').value = auto;
  const loc = selectedLocator() || { type: 'ID', value: node['resource-id'] || '' };
  // 定位方式下拉：框架 Locator_Type
  $('el-type').innerHTML = ['ID', 'XPATH', 'ACCESSIBILITY_ID', 'ANDROID_UIAUTOMATOR', 'CLASS_NAME', 'NAME']
    .map(t => '<option value="' + t + '"' + (t === loc.type ? ' selected' : '') + '>' + t + '</option>').join('');
  $('el-value').value = loc.value;
  // 等待时间：每次打开弹窗恢复框架默认 30（上一个元素的设置不串扰）
  $('el-wait-sec').value = 30;
  $('el-result').className = 'el-result'; $('el-result').textContent = '';
  $('el-content').textContent = '';
  // 写入文件默认定位器自己的元素库文件（避免误写进框架自带文件；③ 会在选目标用例后自动对齐）
  $('el-file').value = state.defaultEleFile || 'locator_gui_elements.py';
  // 用途默认：已有可追加的用例方法 → 直接选③（三件套一次完成），否则退回①
  document.querySelector('input[name="el-purpose"][value="only"]').checked = true;
  $('el-op-type').innerHTML = STEP_TYPES.map(t => '<option value="' + t.v + '">' + t.n + '</option>').join('');
  $('el-op-type').value = 'click';
  $('el-op-param').value = '';
  // 步骤描述自动预填：优先元素文本（报告更友好），无文本则留空由后端按元素名生成
  $('el-op-comment').value = (node.text && node.text.trim()) ? '点击「' + node.text.trim() + '」' : '';
  $('el-comment').value = '';
  $('el-case-comment').value = '';
  $('el-page-file').value = '';
  closeDupPanel();
  setElLinkNote('');
  onOpTypeChange();
  await loadCaseFiles();
  const usable = (state.caseFiles || []).some(c =>
    (c.methods || []).some(m => m !== 'setup_class' && m !== 'teardown_class'));
  if (usable) document.querySelector('input[name="el-purpose"][value="all"]').checked = true;
  onPurposeChange();
  $('modal-mask').style.display = 'flex';
}
/* 用途（①仅元素 / ②+用例 / ③+操作 三件套）：决定流程走到哪一栏 */
function purposeValue() {
  const r = document.querySelector('input[name="el-purpose"]:checked');
  return r ? r.value : 'only';
}
function setElLinkNote(msg) {
  const el = $('el-link-note');
  if (el) { el.textContent = msg || ''; el.style.display = msg ? '' : 'none'; }
}
/* ---- 已有元素复用面板：命中相同定位时弹出，默认「直接复用」防元素库膨胀 ---- */
let dupResolver = null;
function askDuplicatePanel(dup) {
  const used = dup.used_in || [];
  const usedTxt = used.length
    ? '已被用例使用：' + used.map(u => u.file + '（' + u.count + ' 处）').join('、')
    : '暂无用例使用';
  $('el-dup-info').textContent = '已有元素「' + dup.name + '」（' + dup.filename + '）· ' + usedTxt
    + '。直接复用不在元素库新增条目，且不阻止你继续添加「用例 + 操作」；'
    + '「更新元素定义」才会用当前定位/等待覆盖它。';
  $('el-dup-panel').style.display = '';
  return new Promise(resolve => { dupResolver = resolve; });
}
function closeDupPanel() {
  $('el-dup-panel').style.display = 'none';
  dupResolver = null;
}
/* ---- 连续添加模式：保存并继续后开启；点截图/元素树选中新元素自动弹出添加窗口 ---- */
function updateContChip() {
  const chip = $('cont-add-chip');
  if (chip) chip.style.display = state.continuousAdd ? '' : 'none';
}
/* ---- 目标方法已有步骤 + 插入位置（②栏） ---- */
function currentSteps() {
  const f = $('el-case-file').value;
  const method = $('el-case-method').value;
  if (!f || !method) return [];
  const info = (state.caseFiles || []).find(c => c.file === f && (c.method_steps || {})[method]);
  return info ? (info.method_steps[method] || []) : [];
}
function insertPos() { return parseInt($('el-insert-pos').value, 10) || 0; }
function newStepNo() { const p = insertPos(); return p > 0 ? p + 1 : currentSteps().length + 1; }
function renderStepsList(steps) {
  const box = $('el-steps-list');
  if (!box) return;
  if (purposeValue() === 'only' || !$('el-case-method').value) { box.innerHTML = ''; box.style.display = 'none'; return; }
  box.style.display = '';
  const pos = insertPos();
  const newNo = pos > 0 ? pos + 1 : steps.length + 1;
  const step = { type: $('el-op-type').value, element: $('el-name').value.trim() || '<元素名>', param: $('el-op-param').value.trim() };
  const desc = $('el-op-comment').value.trim() || genStepDesc(step);
  let html = steps.length
    ? '<div class="sl-title">当前用例已有 ' + steps.length + ' 步：</div>'
    : '<div class="sl-title">当前方法还没有步骤，这一步将是第 1 步：</div>';
  steps.forEach((s, i) => {
    html += '<div class="sl-row"><span class="sl-idx">' + (i + 1) + '</span><span>' + esc(s) + '</span></div>';
  });
  html += '<div class="sl-row new"><span class="sl-idx">' + newNo + '</span><span>➕ 本步：'
    + esc(desc) + (pos > 0 ? '（插到第 ' + pos + ' 步之后）' : '') + '</span></div>';
  box.innerHTML = html;
}
/* 组装添加元素请求；checkDup=true 时后端先做重复检测（命中返回 duplicate 不落盘） */
async function saveElement(checkDup) {
  const waitSec = parseInt($('el-wait-sec').value, 10);
  const payload = {
    filename: $('el-file').value,
    name: $('el-name').value.trim(),
    locator_type: $('el-type').value,
    value: $('el-value').value.trim(),
    wait_type: $('el-wait').value,
    wait_seconds: (isNaN(waitSec) || waitSec < 1) ? '' : waitSec,  // 空 = 沿用框架默认 30
    comment: $('el-comment').value.trim(),                          // 元素备注 → 元素行行尾注释
    check_dup: checkDup ? 1 : 0,
  };
  if (!payload.name || !payload.value) { showElResult('元素名称和定位值不能为空', false); return null; }
  const r = await fetch('/api/add_element', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    .then(r => r.json()).catch(() => null);
  if (!r) { showElResult('保存失败：服务异常', false); return null; }
  return r;
}
/* 用途单选：① 仅元素 → ②③栏熄灭；② 元素+用例 → ③栏只生成用例行；③ 三件套全联动 */
function onPurposeChange() {
  const p = purposeValue();
  $('col-case').classList.toggle('dim', p === 'only');
  $('col-op').classList.toggle('dim', p === 'only');
  $('op-note').textContent = p === 'all'
    ? '🔗 保存时将自动生成/更新页面操作方法（三件套一次完成）'
    : (p === 'case' ? '⚠ 不会生成页面方法——目标页面须已存在同名方法，否则执行报错' : '');
  if (p !== 'only') { onOpTypeChange(); onCaseFileChange(); }
  else { renderStepsList([]); }
  updatePreview();
}
/* 操作类型切换：参数框按需显隐 + 刷新预览 */
function onOpTypeChange() {
  const t = stepTypeInfo($('el-op-type').value);
  $('el-op-param-wrap').style.display = t.param ? '' : 'none';
  $('el-op-param').placeholder = t.ph || '参数';
  updatePreview();
}
/* ---- 代码预览：与后端 case_step_line 保持一致（所见即所得） ---- */
function escQ(s) { return String(s == null ? '' : s).replace(/\\/g, '\\\\').replace(/'/g, "\\'"); }
function previewLine(step) {
  const t = step.type, el = step.element || '<元素名>', p = step.param || '';
  switch (t) {
    case 'click': return 'page.click_' + el + '()';
    case 'input': return 'page.input_' + el + "('" + escQ(p) + "')";
    case 'long_press': return 'page.long_press_' + el + '()';
    case 'assert_visible': return 'page.assert_' + el + '()';
    case 'assert_text': return 'page.assert_' + el + "_text('" + escQ(p) + "')";
    case 'assert_toast': return "page.assert_toast('" + escQ(p) + "')";
    case 'screenshot': return "page.wait_and_shot('" + escQ(p) + "')";
    case 'tap': {
      const parts = p.split(',').map(x => x.trim()).filter(Boolean);
      return parts.length >= 2 ? 'page.tap_xy(' + parts[0] + ', ' + parts[1] + ')'
        : 'page.tap_xy(' + (parts[0] || '0') + ')';
    }
    case 'sleep': {
      const n = parseFloat(p);
      return 'time.sleep(' + (isNaN(n) ? (p || '1') : n) + ')';
    }
    case 'custom': return p || 'page.xxx()';
    default: return '';
  }
}
/* 页面方法名预览：与后端 method_name 派生规则一致（sleep/custom 无页面方法） */
function pageMethodName(step) {
  const t = step.type, el = step.element || '<元素名>';
  return {
    click: 'click_' + el, input: 'input_' + el, long_press: 'long_press_' + el,
    assert_visible: 'assert_' + el, assert_text: 'assert_' + el + '_text',
    assert_toast: 'assert_toast', screenshot: 'wait_and_shot', tap: 'tap_xy',
  }[t] || '';
}
/* 目标用例的页面文件（来自 /api/cases 的三件套归属信息） */
function targetPageInfo() {
  const f = $('el-case-file').value;
  const info = (state.caseFiles || []).find(c => c.file === f && c.page_file);
  return info || null;
}
/* ---- 三个实时预览：元素代码 / 用例代码 / 页面方法代码（与后端生成规则保持一致） ---- */
/* 元素栏：将写入元素库的那一行 */
function elementLinePreview() {
  const name = $('el-name').value.trim() || '<元素名>';
  const val = $('el-value').value.trim();
  const sec = parseInt($('el-wait-sec').value, 10);
  let line = "self." + name + " = CreateElement.create(Locator_Type." + $('el-type').value
    + ", '" + escQ(val) + "', wait_type=Wait_By." + $('el-wait').value;
  if (!isNaN(sec) && sec >= 1) line += ", wait_seconds=" + sec;
  line += ')';
  const c = $('el-comment').value.trim();
  if (c) line += '  # ' + c;
  return line;
}
/* 用例栏：将插入到目标方法的注释行 + 代码行（注释=步骤描述，留空后端自动生成） */
function caseLinesPreview(step) {
  const c = $('el-case-comment').value.trim();
  const desc = c || genStepDesc(step);
  return '# ' + desc + '\n' + previewLine(step);
}
/* 操作栏：选③时将生成到页面文件的页面方法（镜像后端 page_method_code） */
function pageMethodPreview(step) {
  const pm = pageMethodName(step);
  if (!pm) return '（该操作类型无需页面方法）';
  const el = step.element || '<元素名>';
  const doc = $('el-op-comment').value.trim() || genStepDesc(step);
  const t = step.type;
  let sig = pm, body = '';
  if (t === 'click') body = 'self.appOperator.click(self._elements.' + el + ')';
  else if (t === 'input') { sig += '(self, text)'; body = 'self.appOperator.sendText(self._elements.' + el + ', text)'; }
  else if (t === 'long_press') body = 'self.appOperator.touch_long_press(self._elements.' + el + ', duration_sconds=2)';
  else if (t === 'assert_visible') body = 'self.appOperator.getElement(self._elements.' + el + ')';
  else if (t === 'assert_text') { sig += '(self, expected)'; body = "assert self.appOperator.getText(self._elements." + el + ") == expected, '" + escQ(doc) + "'"; }
  else if (t === 'assert_toast') { sig += '(self, text)'; body = "assert self.appOperator.is_toast_visible(text, wait_seconds=5), '" + escQ(doc) + "'"; }
  else if (t === 'screenshot') { sig += '(self, tag)'; body = 'import time\ntime.sleep(1)\nself.appOperator.get_screenshot(tag)'; }
  else if (t === 'tap') { sig += '(self, x, y)'; body = 'self.appOperator.tap(x, y)'; }
  return 'def ' + sig + ':\n    """' + doc + '"""\n    ' + body.replace(/\n/g, '\n    ');
}
function updatePreview() {
  // 元素代码：任何用途都实时显示（元素栏是必走的第一步）
  $('el-code-element').textContent = elementLinePreview();
  const p = purposeValue();
  const step = {
    type: $('el-op-type').value,
    element: $('el-name').value.trim() || '<元素名>',
    param: $('el-op-param').value.trim(),
  };
  // 用例代码 / 页面方法：按用途显示
  if (p === 'only') {
    $('el-code-case').textContent = '';
    $('el-code-preview').textContent = '';
    return;
  }
  $('el-code-case').textContent = caseLinesPreview(step);
  if (p === 'all') $('el-code-preview').textContent = pageMethodPreview(step);
  else $('el-code-preview').textContent = '（② 不生成页面方法；目标页面须已存在同名方法）';
}
/* ---- 目标用例文件 + 方法（两级联动；③ 时元素文件自动对齐页面引用的元素文件） ---- */
async function loadCaseFiles() {
  const r = await fetch('/api/cases').then(r => r.json()).catch(() => null);
  if (!r || !r.ok) return;
  state.caseFiles = r.case_info || [];
  const sel = $('el-case-file');
  const cur = sel.value;
  const files = [];
  (state.caseFiles || []).forEach(c => { if (files.indexOf(c.file) < 0) files.push(c.file); });
  sel.innerHTML = files.map(f => '<option value="' + esc(f) + '">' + esc(f) + '</option>').join('');
  if (cur && files.indexOf(cur) >= 0) sel.value = cur;
  else if (files.length) sel.value = files[0];
  onCaseFileChange();
}
function onCaseFileChange() {
  const f = $('el-case-file').value;
  const infos = (state.caseFiles || []).filter(c => c.file === f);
  const methods = [];
  infos.forEach(c => (c.methods || []).forEach(m => { if (methods.indexOf(m) < 0) methods.push(m); }));
  const usable = methods.filter(m => m !== 'setup_class' && m !== 'teardown_class');
  const mSel = $('el-case-method');
  mSel.innerHTML = usable.length
    ? usable.map(m => '<option value="' + esc(m) + '">' + esc(m) + '</option>').join('')
    : '<option value="">（该文件暂无可用方法）</option>';
  // 已有步骤 + 插入位置（漏步骤可插中间；步骤来自方法体的 # 注释，后端 method_steps 解析）
  const selMethod = mSel.value;
  const stepsInfo = infos.find(c => (c.method_steps || {})[selMethod]);
  const steps = (stepsInfo && stepsInfo.method_steps[selMethod]) || [];
  const posSel = $('el-insert-pos');
  const curPos = posSel.value;
  let posOpts = '<option value="0">末尾（成为第 ' + (steps.length + 1) + ' 步）</option>';
  for (let i = 1; i <= steps.length; i++) {
    posOpts += '<option value="' + i + '">第 ' + i + ' 步之后 · ' + esc(String(steps[i - 1]).slice(0, 12)) + '</option>';
  }
  posSel.innerHTML = posOpts;
  posSel.value = (curPos !== '' && curPos !== null && parseInt(curPos, 10) <= steps.length) ? curPos : '0';
  renderStepsList(steps);
  // 三件套联动：写入元素文件 ← 目标用例页面实际引用的元素文件（必须一致）
  // 写入页面文件 = 目标用例的 self.page 所在文件（只读展示，跟随用例）
  const p = purposeValue();
  const info = infos.find(c => c.page_file);
  $('el-page-file').value = info ? info.page_file : '';
  if (p !== 'only' && !info) {
    setElLinkNote('⚠ 该用例没有页面对象（self.page），③ 无法生成操作——先到「📝 用例工作台」生成');
  } else if (p === 'all' && info && info.elements_file) {
    if ($('el-file').value !== info.elements_file) {
      $('el-file').value = info.elements_file;
      setElLinkNote('🔗 页面 ' + info.page_file + ' 引用元素文件 ' + info.elements_file + '，「写入元素文件」已自动对齐');
    } else {
      setElLinkNote('🔗 三件套去向：页面 ' + info.page_file + ' ← 元素文件 ' + info.elements_file);
    }
  } else if (info) {
    setElLinkNote('该用例的页面: ' + info.page_file + (info.elements_file ? '（元素: ' + info.elements_file + '）' : ''));
  } else {
    setElLinkNote('');
  }
  updatePreview();
}
/* 保存：按「用途」单选分流 —— ① 仅保存到元素库 / ② 保存并追加到目标用例方法 */
/* 保存：按「保存到哪一步」分流 ① 仅元素 / ② +用例 / ③ +操作；
 * continueMode=true（保存并继续）= 保存后回到定位器，开启连续添加（点下一个元素自动弹本窗） */
async function onSaveElement(continueMode) {
  const purpose = purposeValue();
  if (!purpose) return;
  const name = $('el-name').value.trim();
  // 选②/③：前置校验用例栏（保存元素前就拦住，避免元素入库了代码却追加不了）
  let caseFile = '', methodName = '';
  if (purpose !== 'only') {
    caseFile = $('el-case-file').value;
    methodName = $('el-case-method').value;
    if (!(state.caseFiles || []).some(c => c.file === caseFile)) {
      showElResult('请选择目标用例文件（没有？先到「📝 用例工作台」创建）', false); return;
    }
    if (!methodName) { showElResult('请选择目标方法', false); return; }
  }
  // 同名（同文件）覆盖确认：防止误覆盖已有元素
  const fname = $('el-file').value;
  if (name && (state.elementsAll[fname] || []).indexOf(name) >= 0) {
    if (!confirm('元素库文件 ' + fname + ' 里已有同名元素「' + name + '」，保存将覆盖更新原定义。\n\n' +
      '点「确定」= 覆盖更新\n点「取消」= 不保存')) return;
  }
  let r = await saveElement(true);
  if (!r) return;
  let savedName = name;
  let dupHandled = false;   // 已处理「相同定位重复」：复用=使用已有元素 / 更新=覆盖定义 / 取消
  if (r.duplicate) {
    dupHandled = true;
    const choice = await askDuplicatePanel(r.duplicate);
    if (choice === 'cancel') { showElResult('已取消，元素未保存（可改用途或直接关闭）', false); return; }
    if (choice === 'reuse') {
      savedName = r.duplicate.name;        // 直接复用：不新建，防元素库膨胀；用例+操作继续
    } else {
      r = await saveElement(false);        // 更新元素定义：用当前定位/等待覆盖
      if (!r || !r.ok) { if (r) showElResult(r.msg, false); return; }
      savedName = $('el-name').value.trim();
    }
  }
  // 非重复场景失败 → 报错返回；重复但已「使用已有元素」→ 继续后续流程
  if (!r || (!r.ok && !dupHandled)) { if (r) showElResult(r.msg, false); return; }

  const finishContinue = () => {
    loadPages(); loadLibraryFiles(); loadCaseFiles();
    state.continuousAdd = true;
    updateContChip();
    $('modal-mask').style.display = 'none';
  };

  if (purpose === 'only') {
    if (dupHandled && r.duplicate) {
      showElResult('已复用已有元素「' + savedName + '」（未新建，避免元素库重复）', true);
    } else {
      if (r.ok && r.content) $('el-content').textContent = r.content;
      showElResult(r.msg + ' —— 已保存到元素库', true);
    }
    if (continueMode) finishContinue();
    else setTimeout(() => { $('modal-mask').style.display = 'none'; }, 600);
    return;
  }
  // purpose ②/③：追加一步代码到目标用例方法体末尾（③ 同时生成/更新页面方法）
  const step = {
    type: $('el-op-type').value,
    element: savedName,
    param: $('el-op-param').value.trim(),
    desc: '',
    comment: $('el-op-comment').value.trim(),        // 操作备注 → 页面方法 docstring
    case_comment: $('el-case-comment').value.trim(), // 用例备注 → 追加行上方注释
  };
  const res = $('el-result');
  res.className = 'el-result'; res.textContent = purpose === 'all'
    ? '元素已保存，正在追加用例代码 + 生成页面操作…'
    : '元素已保存，正在追加用例代码…';
  const cr = await fetch('/api/add_code', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ case_file: caseFile, method_name: methodName, step: step,
                           gen_page_method: purpose === 'all' ? 1 : 0,
                           insert_after_step: insertPos() }),
  }).then(r => r.json()).catch(() => null);
  if (!cr || !cr.ok) {
    showElResult((cr && cr.msg ? cr.msg : '追加用例代码失败：服务异常') + '（元素已保存到元素库）', false);
    return;
  }
  res.className = 'el-result ok';
  res.textContent = (dupHandled ? '已使用已有元素「' + savedName + '」' : r.msg)
    + '；' + cr.msg + '（三件套已联动完成）';
  // 展示追加后的目标方法片段 + ③ 生成的页面方法片段（方便确认写入位置）
  let snippets = [];
  if (cr.content) {
    const lines = cr.content.split('\n');
    const idx = lines.findIndex(l => l.indexOf('def ' + methodName) >= 0);
    if (idx >= 0) {
      let end = lines.length;
      for (let i = idx + 1; i < lines.length; i++) {
        if (lines[i] && !/^\s/.test(lines[i])) { end = i; break; }
      }
      snippets.push('# ' + caseFile + ' :: ' + methodName + '\n' + lines.slice(Math.max(0, idx - 2), end).join('\n'));
    }
  }
  if (purpose === 'all' && cr.page_content && cr.page_method) {
    const plines = cr.page_content.split('\n');
    const pidx = plines.findIndex(l => l.indexOf('def ' + cr.page_method) >= 0);
    if (pidx >= 0) {
      let pend = plines.length;
      for (let i = pidx + 1; i < plines.length; i++) {
        // 方法体结束：下一个类级 class 或同级 def
        if (/^(class |    def )/.test(plines[i])) { pend = i; break; }
      }
      snippets.push('\n# ' + cr.page_file + ' :: ' + cr.page_method + '\n' + plines.slice(pidx, pend).join('\n').replace(/^\n+/, ''));
    }
  }
  if (snippets.length) $('el-content').textContent = snippets.join('\n\n');
  // 刷新页面/元素/用例列表（可能有新元素、新页面对象/新方法）；保存并继续 → 连续添加模式
  if (continueMode) { finishContinue(); return; }
  loadPages(); loadLibraryFiles(); loadCaseFiles();
}

function showElResult(msg, ok) {
  const box = $('el-result');
  box.className = 'el-result ' + (ok ? 'ok' : 'err');
  box.textContent = msg;
}

/* ---------- 用例工作台（用例 = 步骤列表；每步 = 元素 + 操作） ---------- */
function defaultCurrentCase() {
  return {
    caseFile: 'test_login.py', methodName: 'test_login',
    desc: '', pkg: 'com.recordlife.kuaige', activity: 'com.recordlife.kuaige.feature.main.MainActivity',
    pageFile: '',
    elementsFile: state.defaultEleFile || 'locator_gui_elements.py',
    genTeardown: true, steps: [],
  };
}
function ensureCurrentCase() {
  if (!state.currentCase) state.currentCase = defaultCurrentCase();
  return state.currentCase;
}
/* 两个入口共用：往当前用例草稿追加一个步骤（统一步骤结构） */
function pushStep(step) {
  const c = ensureCurrentCase();
  c.steps.push(Object.assign({ type: 'click', element: '', param: '', desc: '' }, step));
  renderCaseSteps();
  return c;
}
function openCaseModal() {
  const c = ensureCurrentCase();
  // 同步下拉数据（页面文件/元素文件）
  if (!state.pages.length) loadPages();
  if (!state.eleFiles.length) loadLibraryFiles();
  // 表单回填（类名、页面类名、是否生成页面均自动处理，无需表单字段）
  $('case-file').value = c.caseFile;
  $('case-method').value = c.methodName;
  $('case-desc').value = c.desc;
  $('case-pkg').value = c.pkg;
  $('case-activity').value = c.activity;
  $('case-page-file').value = c.pageFile || '';
  $('case-ele-file').value = c.elementsFile || state.defaultEleFile;
  $('case-gen-teardown').checked = c.genTeardown;
  $('case-result').className = 'el-result'; $('case-result').textContent = '';
  $('case-preview-content').textContent = '';
  renderCaseSteps();
  $('case-mask').style.display = 'flex';
}
/* 文件名变化 → 自动补方法名（半自动命名） */
function syncCaseNames() {
  const c = ensureCurrentCase();
  const file = $('case-file').value.trim();
  if (file) {
    const base = file.replace(/^test_/, '').replace(/\.py$/, '').split(/[_\s]+/).filter(Boolean).join('_');
    if (!$('case-method').dataset.touched) $('case-method').value = 'test_' + base;
  }
  c.caseFile = file;
  c.methodName = $('case-method').value.trim();
  c.pageFile = $('case-page-file').value;
}
/* 步骤列表：增删 / 排序 / 行内编辑 */
function addStepRow(type) {
  const step = { type: type || 'click', element: '', param: '', desc: '' };
  if (type === 'custom') step.param = 'page.xxx()  # 自定义';
  pushStep(step);
}
/* ---- 元素名绑定：用例步骤的元素名 ↔ 元素库 self.元素名 必须一致 ---- */
/* 元素名 → 所在元素文件列表（state.elementsAll = {文件: [元素名...]}） */
function filesOfElement(name) {
  return Object.keys(state.elementsAll || {}).filter(f => (state.elementsAll[f] || []).indexOf(name) >= 0);
}
/* 元素名变动 → 校验 + 联动：不在库 = 红框警示；在别的文件 = 自动切换「引用元素文件」 */
function syncEleBinding(s, input) {
  const name = (s.element || '').trim();
  if (!name) {
    input.classList.remove('missing');
    input.title = '从元素库选或手输元素名';
    return;
  }
  const files = filesOfElement(name);
  if (!files.length) {
    input.classList.add('missing');
    input.title = '元素库里没有「' + name + '」——用例和元素库的元素名必须完全一致才能执行，请从下拉选择或先添加该元素';
    return;
  }
  input.classList.remove('missing');
  input.title = '元素在: ' + files.join('、');
  const cur = $('case-ele-file').value;
  if (files.indexOf(cur) < 0) {
    $('case-ele-file').value = files[0];
    if (state.currentCase) state.currentCase.elementsFile = files[0];
    setBindNote('🔗 元素「' + name + '」在 ' + files[0] + '，「引用元素文件」已自动切换保持一致');
  }
}
function setBindNote(msg) {
  const el = $('case-bind-note');
  if (el) { el.textContent = msg || ''; el.style.display = msg ? '' : 'none'; }
}
/* 生成预览：随步骤实时更新（元素名 → 页面方法名 → 用例代码行 的派生关系所见即所得） */
function updateCasePreview() {
  const c = state.currentCase;
  if (!c || !c.steps.length) { $('case-preview-content').textContent = ''; return; }
  const lines = [];
  c.steps.forEach((s, i) => {
    const line = previewLine({ type: s.type, element: s.element, param: s.param });
    if (!line) return;
    lines.push('# ' + (i + 1) + '. ' + (s.desc || genStepDesc(s)));
    const t = stepTypeInfo(s.type);
    let mark = '';
    if (t.el && s.element && !filesOfElement(s.element).length) mark = '   # ⚠ 元素库中未找到 ' + s.element;
    lines.push(line + mark);
  });
  $('case-preview-content').textContent = lines.join('\n');
}
function renderCaseSteps() {
  const box = $('case-steps');
  if (!box) return;
  const c = state.currentCase;
  const names = allElementNames();
  const eleOpts = names.map(n => '<option value="' + esc(n) + '">' + esc(n) + '</option>').join('');
  box.innerHTML = '<datalist id="ele-list">' + eleOpts + '</datalist>';
  // 列头：与步骤行的列对齐（序号/做什么/哪个元素/参数/备注/排序删除）
  if (c && c.steps.length) {
    box.insertAdjacentHTML('beforeend',
      '<div class="step-cols"><span class="step-idx">#</span><span class="st-type">做什么</span>' +
      '<span class="st-ele">哪个元素</span><span class="st-param">参数</span>' +
      '<span class="st-desc">备注</span><span class="step-btns"></span></div>');
  }
  (c ? c.steps : []).forEach((s, i) => {
    const row = document.createElement('div');
    row.className = 'step-row';
    const t = stepTypeInfo(s.type);
    row.innerHTML =
      '<span class="step-idx">' + (i + 1) + '</span>' +
      '<select class="st-type">' + STEP_TYPES.map(x =>
        '<option value="' + x.v + '"' + (x.v === s.type ? ' selected' : '') + '>' + x.n + '</option>').join('') + '</select>' +
      '<input class="st-ele" list="ele-list" value="' + esc(s.element || '') + '" placeholder="元素名" title="从元素库选或手输元素名">' +
      '<input class="st-param" value="' + esc(s.param || '') + '" placeholder="' + esc(t.ph || '参数') + '">' +
      '<input class="st-desc" value="' + esc(s.desc || '') + '" placeholder="描述（自动生成可改）">' +
      '<span class="step-btns">' +
        '<button class="btn mini" data-act="up" title="上移">↑</button>' +
        '<button class="btn mini" data-act="down" title="下移">↓</button>' +
        '<button class="btn mini del" data-act="del" title="删除">✕</button>' +
      '</span>';
    const qType = row.querySelector('.st-type');
    const qEle = row.querySelector('.st-ele');
    const qParam = row.querySelector('.st-param');
    const qDesc = row.querySelector('.st-desc');
    // 类型切换：元素/参数显隐 + 描述自动生成
    qType.addEventListener('change', () => {
      const nt = stepTypeInfo(qType.value);
      s.type = qType.value;
      s.element = nt.el ? s.element : '';
      qEle.style.display = nt.el ? '' : 'none';
      qParam.style.display = nt.param ? '' : 'none';
      qParam.placeholder = nt.ph || '参数';
      s.desc = genStepDesc(s);
      qDesc.value = s.desc;
      syncEleBinding(s, qEle);
      updateCasePreview();
    });
    qEle.addEventListener('input', () => { s.element = qEle.value.trim(); s.desc = genStepDesc(s); qDesc.value = s.desc; syncEleBinding(s, qEle); updateCasePreview(); });
    qParam.addEventListener('input', () => { s.param = qParam.value.trim(); s.desc = genStepDesc(s); qDesc.value = s.desc; updateCasePreview(); });
    qDesc.addEventListener('input', () => { s.desc = qDesc.value.trim(); });
    row.querySelector('[data-act=up]').addEventListener('click', () => { if (i > 0) { c.steps.splice(i - 1, 0, c.steps.splice(i, 1)[0]); renderCaseSteps(); } });
    row.querySelector('[data-act=down]').addEventListener('click', () => { if (i < c.steps.length - 1) { c.steps.splice(i + 1, 0, c.steps.splice(i, 1)[0]); renderCaseSteps(); } });
    row.querySelector('[data-act=del]').addEventListener('click', () => { c.steps.splice(i, 1); renderCaseSteps(); });
    // 按类型初始化显隐
    qEle.style.display = t.el ? '' : 'none';
    qParam.style.display = t.param ? '' : 'none';
    qParam.placeholder = t.ph || '参数';
    box.appendChild(row);
  });
  // 渲染后统一刷新绑定状态（红框警示/文件归属）与实时预览
  box.querySelectorAll('.step-row').forEach((row, i) => {
    const s = c.steps[i];
    if (s) syncEleBinding(s, row.querySelector('.st-ele'));
  });
  updateCasePreview();
  if (!c || !c.steps.length) {
    box.insertAdjacentHTML('beforeend', '<div class="empty steps-empty">还没有步骤。<br>① 点下方「从元素库添加步骤」，选元素 + 操作类型逐条拼；<br>② 或「自定义代码步骤」写任意代码行兜底（高级）。<br><span class="hint">（「添加到元素库」→「② 保存并添加到用例」会把一步代码直接追加到已有用例文件，不进这里）</span></div>');
  }
}
/* 收集表单 → 生成用例（操作自动写入页面文件；类名由后端按文件名自动派生） */
async function onSaveCase() {
  const c = ensureCurrentCase();
  c.caseFile = $('case-file').value.trim();
  c.methodName = $('case-method').value.trim();
  c.desc = $('case-desc').value.trim();
  c.pkg = $('case-pkg').value.trim();
  c.activity = $('case-activity').value.trim();
  c.pageFile = $('case-page-file').value;
  c.elementsFile = $('case-ele-file').value;
  c.genTeardown = $('case-gen-teardown').checked;
  const res = $('case-result');
  if (!c.caseFile || !c.methodName) { res.className = 'el-result err'; res.textContent = '用例文件名和测试方法名不能为空'; return; }
  if (!c.steps.length) { res.className = 'el-result err'; res.textContent = '还没有任何步骤，请先添加步骤（或用定位器快捷添加）'; return; }
  // 元素名绑定校验：用例引用的元素必须真实存在于元素库，且都能由「引用元素文件」提供
  // （一个页面文件只能引用一个元素文件，元素名对不上执行时就会找不到元素）
  const missing = [];
  const outside = [];
  c.steps.forEach(s => {
    const t = stepTypeInfo(s.type);
    if (!t.el || !s.element) return;
    const files = filesOfElement(s.element);
    if (!files.length) { missing.push(s.element); return; }
    if (files.indexOf(c.elementsFile) < 0) outside.push(s.element + '（在 ' + files.join('、') + '）');
  });
  if (missing.length) {
    res.className = 'el-result err';
    res.textContent = '元素库里找不到：' + missing.join('、') + ' —— 用例和元素库的元素名必须完全一致才能执行，请从元素下拉重新选择或先添加元素';
    return;
  }
  if (outside.length) {
    res.className = 'el-result err';
    res.textContent = '以下元素不在「引用元素文件」' + c.elementsFile + ' 里：' + outside.join('；')
      + '。一个页面文件只能引用一个元素文件，请把元素移到同一文件，或改选元素实际所在的文件';
    return;
  }
  // 页面文件为空时自动生成默认名（如 login → loginPage.py）
  const pageFile = c.pageFile || (c.caseFile.replace(/^test_/, '').replace(/\.py$/, '') + 'Page.py');
  c.pageFile = pageFile;
  const payload = {
    case_file: c.caseFile, method_name: c.methodName, desc: c.desc,
    pkg: c.pkg, activity: c.activity,
    page_file: pageFile,
    elements_file: c.elementsFile, gen_page: 1, gen_teardown: c.genTeardown ? 1 : 0,
    steps: c.steps,
  };
  res.className = 'el-result'; res.textContent = '生成中…';
  const r = await fetch('/api/add_case', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    .then(r => r.json()).catch(() => null);
  if (!r) { res.className = 'el-result err'; res.textContent = '生成失败：服务异常'; return; }
  res.className = 'el-result ' + (r.ok ? 'ok' : 'err');
  res.textContent = r.msg;
  if (r.ok) {
    let preview = '';
    if (r.case) preview += '# ========== 用例文件：' + r.case.filename + ' ==========\n' + r.case.content;
    if (r.page) preview += '\n\n# ========== 页面文件：' + r.page.filename + ' ==========\n' + r.page.content;
    $('case-preview-content').textContent = preview;
    // 刷新页面/元素列表下拉（新增了文件）
    loadPages(); loadLibraryFiles();
  }
}

/* ---------- 右侧教学 ---------- */
var tutSearchTimer = null;
function onTutSearch(e) {
  clearTimeout(tutSearchTimer);
  tutSearchTimer = setTimeout(() => renderTutorials(e.target.value.trim()), 250);
}
async function renderTutorials(q) {
  tutExpandAll = !!(q && q.trim());
  const url = '/api/tutorials' + (q ? '?q=' + encodeURIComponent(q) : '');
  const r = await fetch(url).then(r => r.json()).catch(() => null);
  if (!r || !r.ok) return;
  const box = $('tutorials');
  box.innerHTML = '';
  const items = r.tutorials;
  if (!items.length) { box.innerHTML = '<div class="empty">没有匹配的教程，换个词试试<br>如：点击 / 滑动 / toast / 断言 / 输入</div>'; return; }
  items.forEach(item => box.appendChild(buildTutItem(item)));
}
function buildTutItem(item) {
  const isCat = item.length === 2 && Array.isArray(item[1]);
  if (isCat) {
    const wrap = document.createElement('div');
    const head = document.createElement('div');
    head.className = 'cat-head';
    const arrow = document.createElement('span');
    arrow.textContent = '▾';
    head.innerHTML = '<span>📁 ' + esc(item[0]) + '</span>';
    head.appendChild(arrow);
    const body = document.createElement('div');
    (item[1] || []).forEach(x => body.appendChild(buildTutItem(x)));
    let open = tutExpandAll;  // 默认收起；搜索命中时展开
    if (!open) body.style.display = 'none';
    arrow.textContent = open ? '▾' : '▸';
    head.appendChild(arrow);
    head.addEventListener('click', () => {
      open = !open;
      body.style.display = open ? '' : 'none';
      arrow.textContent = open ? '▾' : '▸';
    });
    wrap.appendChild(head); wrap.appendChild(body);
    return wrap;
  }
  const [title, sig, desc, code] = item;
  const leaf = document.createElement('div');
  leaf.className = 'tut-leaf';
  leaf.innerHTML = '<div class="tut-title"><span>' + esc(title) + '</span></div>'
    + (sig ? '<div class="tut-sig">' + esc(sig) + '</div>' : '')
    + (desc ? '<div class="tut-desc">' + esc(desc) + '</div>' : '');
  if (code) {
    const c = document.createElement('div');
    c.className = 'tut-code';
    const pre = document.createElement('span');
    pre.textContent = code;
    const btn = document.createElement('button');
    btn.className = 'copy-btn'; btn.textContent = '复制';
    btn.addEventListener('click', () => copyText(code, btn));
    c.appendChild(pre); c.appendChild(btn);
    leaf.appendChild(c);
  }
  return leaf;
}

document.addEventListener('DOMContentLoaded', init);
/* ---------- 日间/夜间模式切换（悬浮按钮，宫崎骏风日/月图标；默认日间=白色居多） ----------
   按钮图标：日间显示月亮图（点击切夜间），夜间显示太阳图（点击切日间） */
(function () {
  const KEY = 'locator_theme';
  const ICON_MOON = '/static/theme_icons/theme_moon.png';
  const ICON_SUN = '/static/theme_icons/theme_sun.png';

  function apply(mode) {
    document.documentElement.classList.toggle('night', mode === 'night');
    const fab = document.getElementById('theme-fab');
    if (fab) {
      fab.innerHTML = '<img src="' + (mode === 'night' ? ICON_SUN : ICON_MOON) + '" alt="切换主题">';
      fab.title = mode === 'night' ? '切换到日间模式（白色）' : '切换到夜间模式（黑色）';
    }
  }

  function current() {
    try { if (localStorage.getItem(KEY) === 'night') return 'night'; } catch (e) { /* 忽略 */ }
    return 'day';
  }

  function toggle() {
    const m = current() === 'night' ? 'day' : 'night';
    try { localStorage.setItem(KEY, m); } catch (e) { /* 忽略 */ }
    apply(m);
  }

  function init() {
    const fab = document.createElement('button');
    fab.id = 'theme-fab';
    fab.className = 'theme-fab';
    fab.addEventListener('click', toggle);
    document.body.appendChild(fab);
    apply(current());
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
