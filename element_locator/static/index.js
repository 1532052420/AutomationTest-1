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
  $('btn-tap').addEventListener('click', onTapElement);      // ▶ 设备上点击
  $('tree-search').addEventListener('input', onTreeSearch);
  $('tut-search').addEventListener('input', onTutSearch);
  $('btn-add').addEventListener('click', openModal);
  $('btn-modal-cancel').addEventListener('click', () => $('modal-mask').style.display = 'none');
  $('btn-modal-save').addEventListener('click', onSaveElement);
  document.querySelectorAll('input[name="el-purpose"]').forEach(r => r.addEventListener('change', onPurposeChange));
  $('el-op-type').addEventListener('change', onOpTypeChange);
  $('el-op-param').addEventListener('input', updatePreview);
  $('el-case-file').addEventListener('change', onCaseFileChange);
  $('el-case-method').addEventListener('change', updatePreview);
  $('el-name').addEventListener('input', updatePreview);
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
  // 顶部快速打开：用例 / 元素文件 下拉查看
  loadHeaderOpeners();
  $('open-case-sel').addEventListener('change', (e) => { onOpenHdrFile('case', e.target.value); e.target.value = ''; });
  $('open-ele-sel').addEventListener('change', (e) => { onOpenHdrFile('element', e.target.value); e.target.value = ''; });
  $('btn-view-close').addEventListener('click', () => { $('view-mask').style.display = 'none'; });
  bindHelpIcons();
}

/* ---------- 顶部快速打开：用例 / 元素定位文件 查看（只读） ---------- */
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
}

async function onOpenHdrFile(kind, filename) {
  if (!filename) return;
  const q = kind === 'case' ? 'case=' : 'element=';
  const r = await fetch('/api/file_content?' + q + encodeURIComponent(filename)).then(r => r.json()).catch(() => null);
  if (!r || !r.ok) { alert((r && r.msg) || '读取失败'); return; }
  $('view-title').textContent = '📄 ' + r.title;
  $('view-content').textContent = r.content;
  $('view-mask').style.display = 'flex';
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
}
function highlightShot(node) {
  const ov = $('shot-overlay');
  const img = $('shot');
  if (!node.bounds_num || img.style.display === 'none') { ov.style.display = 'none'; return; }
  const scale = img.clientWidth / state.width;
  const [x1, y1, x2, y2] = node.bounds_num;
  ov.style.display = 'block';
  ov.style.left = (x1 * scale) + 'px';
  ov.style.top = (y1 * scale) + 'px';
  ov.style.width = ((x2 - x1) * scale) + 'px';
  ov.style.height = ((y2 - y1) * scale) + 'px';
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
  $('case-page-file').innerHTML = ['', '（新建页面）']
    .concat(state.pages.map(f => f))
    .map(f => '<option value="' + esc(f) + '">' + (f || '─ 新建页面（下方类名） ─') + '</option>').join('');
  $('case-ele-file').innerHTML = state.eleFiles.map(f => '<option value="' + esc(f) + '">' + esc(f) + '</option>').join('');
}
function allElementNames() {
  const seen = [];
  Object.keys(state.elementsAll).forEach(f => {
    (state.elementsAll[f] || []).forEach(n => { if (seen.indexOf(n) < 0) seen.push(n); });
  });
  return seen;
}
function openModal() {
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
  $('el-result').className = 'el-result'; $('el-result').textContent = '';
  $('el-content').textContent = '';
  // 写入文件默认定位器自己的元素库文件（避免误写进框架自带文件）
  $('el-file').value = state.defaultEleFile || 'locator_gui_elements.py';
  // 用途默认「仅保存到元素库」；选②时展开用例生成组
  document.querySelector('input[name="el-purpose"][value="only"]').checked = true;
  $('el-op-type').innerHTML = STEP_TYPES.map(t => '<option value="' + t.v + '">' + t.n + '</option>').join('');
  $('el-op-type').value = 'click';
  $('el-op-param').value = '';
  onPurposeChange();
  loadCaseFiles();
  $('modal-mask').style.display = 'flex';
}
/* 组装添加元素请求；checkDup=true 时后端先做重复检测（命中返回 duplicate 不落盘） */
async function saveElement(checkDup) {
  const payload = {
    filename: $('el-file').value,
    name: $('el-name').value.trim(),
    locator_type: $('el-type').value,
    value: $('el-value').value.trim(),
    wait_type: $('el-wait').value,
    check_dup: checkDup ? 1 : 0,
  };
  if (!payload.name || !payload.value) { showElResult('元素名称和定位值不能为空', false); return null; }
  const r = await fetch('/api/add_element', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    .then(r => r.json()).catch(() => null);
  if (!r) { showElResult('保存失败：服务异常', false); return null; }
  return r;
}
/* 重复元素提示：返回 true=使用已有元素，false=强制新建，null=用户取消 */
function askDuplicate(dup) {
  if (!dup) return false;
  const ok = confirm('发现已有元素「' + dup.name + '」在 ' + dup.filename + ' 中使用相同定位。\n\n' +
    '点「确定」= 直接使用已有元素（不新建，避免元素库重复）\n点「取消」= 强制新建该重复元素');
  return ok;
}
/* 用途单选：选② → 展开「用例生成组」 */
function onPurposeChange() {
  const p = document.querySelector('input[name="el-purpose"]:checked').value;
  $('case-gen-group').style.display = (p === 'case') ? '' : 'none';
  if (p === 'case') onOpTypeChange();
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
function updatePreview() {
  if ($('case-gen-group').style.display === 'none') return;
  const name = $('el-name').value.trim() || '<元素名>';
  const step = { type: $('el-op-type').value, element: name, param: $('el-op-param').value.trim() };
  $('el-code-preview').textContent = previewLine(step);
}
/* ---- 目标用例文件 + 方法（两级联动） ---- */
async function loadCaseFiles() {
  const r = await fetch('/api/cases').then(r => r.json()).catch(() => null);
  if (!r || !r.ok) return;
  state.caseFiles = r.case_info || [];
  const sel = $('el-case-file');
  const cur = sel.value;
  sel.innerHTML = (state.caseFiles || []).map(c =>
    '<option value="' + esc(c.file) + '">' + esc(c.file) + '</option>').join('');
  if (cur && (state.caseFiles || []).some(c => c.file === cur)) sel.value = cur;
  else if (state.caseFiles && state.caseFiles.length) sel.value = state.caseFiles[0].file;
  onCaseFileChange();
}
function onCaseFileChange() {
  const f = $('el-case-file').value;
  const info = (state.caseFiles || []).find(c => c.file === f) || { methods: [] };
  const methods = (info.methods || []).filter(m => m !== 'setup_class' && m !== 'teardown_class');
  const mSel = $('el-case-method');
  mSel.innerHTML = methods.length
    ? methods.map(m => '<option value="' + esc(m) + '">' + esc(m) + '</option>').join('')
    : '<option value="">（该文件暂无可用方法）</option>';
  updatePreview();
}
/* 保存：按「用途」单选分流 —— ① 仅保存到元素库 / ② 保存并追加到目标用例方法 */
async function onSaveElement() {
  const purpose = document.querySelector('input[name="el-purpose"]:checked').value;
  if (!purpose) return;
  const name = $('el-name').value.trim();
  // 选②：前置校验用例生成组（保存元素前就拦住，避免元素入库了代码却追加不了）
  let caseFile = '', methodName = '';
  if (purpose === 'case') {
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
  let dupHandled = false;   // 已处理「相同定位重复」：确定=使用已有元素 / 取消=强制新建
  if (r.duplicate) {
    dupHandled = true;
    if (askDuplicate(r.duplicate)) {
      savedName = r.duplicate.name;        // 直接使用已有元素（不新建，避免元素库重复）
    } else {
      r = await saveElement(false);        // 强制新建
      savedName = $('el-name').value.trim();
    }
  }
  // 非重复场景失败 → 报错返回；重复但已「使用已有元素」→ 继续后续流程
  if (!r || (!r.ok && !dupHandled)) { if (r) showElResult(r.msg, false); return; }

  if (purpose === 'only') {
    if (dupHandled && r.duplicate) {
      showElResult('已使用已有元素「' + savedName + '」（未新建，避免元素库重复）', true);
    } else {
      if (r.ok && r.content) $('el-content').textContent = r.content;
      showElResult(r.msg + ' —— 已保存到元素库', true);
    }
    setTimeout(() => { $('modal-mask').style.display = 'none'; }, 600);
    return;
  }
  // purpose === 'case'：追加一步代码到目标用例方法体末尾
  const step = {
    type: $('el-op-type').value,
    element: savedName,
    param: $('el-op-param').value.trim(),
    desc: '',
  };
  const res = $('el-result');
  res.className = 'el-result'; res.textContent = '元素已保存，正在追加用例代码…';
  const cr = await fetch('/api/add_code', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ case_file: caseFile, method_name: methodName, step: step }),
  }).then(r => r.json()).catch(() => null);
  if (!cr || !cr.ok) {
    showElResult((cr && cr.msg ? cr.msg : '追加用例代码失败：服务异常') + '（元素已保存到元素库）', false);
    return;
  }
  res.className = 'el-result ok';
  res.textContent = (dupHandled ? '已使用已有元素「' + savedName + '」' : r.msg)
    + '；' + cr.msg + '（弹窗可关闭后到用例文件里查看）';
  $('el-code-preview').textContent = cr.line;
  // 展示追加后的目标方法片段（方便确认追加位置正确）
  if (cr.content) {
    const lines = cr.content.split('\n');
    const idx = lines.findIndex(l => l.indexOf('def ' + methodName) >= 0);
    if (idx >= 0) {
      let end = lines.length;
      for (let i = idx + 1; i < lines.length; i++) {
        if (lines[i] && !/^\s/.test(lines[i])) { end = i; break; }
      }
      $('el-content').textContent = lines.slice(Math.max(0, idx - 2), end).join('\n');
    }
  }
  // 刷新页面/元素/用例列表（可能有新元素、新页面对象）
  loadPages(); loadLibraryFiles(); loadCaseFiles();
}

function showElResult(msg, ok) {
  const box = $('el-result');
  box.className = 'el-result ' + (ok ? 'ok' : 'err');
  box.textContent = msg;
}

/* ---------- 用例工作台（元素库 → 页面对象 → 用例 三件套联动） ---------- */
function defaultCurrentCase() {
  return {
    caseFile: 'test_login.py', caseClass: 'TestLogin', methodName: 'test_login',
    desc: '', pkg: 'com.recordlife.kuaige', activity: 'com.recordlife.kuaige.feature.main.MainActivity',
    genPage: true, pageFile: '', pageClass: '',
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
  // 表单回填
  $('case-file').value = c.caseFile;
  $('case-class').value = c.caseClass;
  $('case-method').value = c.methodName;
  $('case-desc').value = c.desc;
  $('case-pkg').value = c.pkg;
  $('case-activity').value = c.activity;
  $('case-page-file').value = c.pageFile || '';
  $('case-page-class').value = c.pageClass || '';
  $('case-ele-file').value = c.elementsFile || state.defaultEleFile;
  $('case-gen-page').checked = c.genPage;
  $('case-gen-teardown').checked = c.genTeardown;
  $('case-result').className = 'el-result'; $('case-result').textContent = '';
  $('case-preview-content').textContent = '';
  renderCaseSteps();
  $('case-mask').style.display = 'flex';
}
/* 文件名/页面名变化 → 自动补类名、方法名（半自动命名） */
function toPascalCase(s) {
  return String(s || '').replace(/\.py$/, '').split(/[_\s]+/).filter(Boolean)
    .map(w => w[0].toUpperCase() + w.slice(1)).join('');
}
function syncCaseNames() {
  const c = ensureCurrentCase();
  const file = $('case-file').value.trim();
  if (file) {
    const base = file.replace(/^test_/, '').replace(/\.py$/, '').split(/[_\s]+/).filter(Boolean).join('_');
    if (!$('case-class').dataset.touched) $('case-class').value = 'Test' + toPascalCase(base);
    if (!$('case-method').dataset.touched) $('case-method').value = 'test_' + base;
  }
  c.caseFile = file;
  c.caseClass = $('case-class').value.trim();
  c.methodName = $('case-method').value.trim();
  const pf = $('case-page-file').value;
  c.pageFile = pf;
  if (pf && !$('case-page-class').dataset.touched) $('case-page-class').value = toPascalCase(pf);
  c.pageClass = $('case-page-class').value.trim();
}
/* 步骤列表：增删 / 排序 / 行内编辑 */
function addStepRow(type) {
  const step = { type: type || 'click', element: '', param: '', desc: '' };
  if (type === 'custom') step.param = 'page.xxx()  # 自定义';
  pushStep(step);
}
function renderCaseSteps() {
  const box = $('case-steps');
  if (!box) return;
  const c = state.currentCase;
  const names = allElementNames();
  const eleOpts = names.map(n => '<option value="' + esc(n) + '">' + esc(n) + '</option>').join('');
  box.innerHTML = '<datalist id="ele-list">' + eleOpts + '</datalist>';
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
    });
    qEle.addEventListener('input', () => { s.element = qEle.value.trim(); s.desc = genStepDesc(s); qDesc.value = s.desc; });
    qParam.addEventListener('input', () => { s.param = qParam.value.trim(); s.desc = genStepDesc(s); qDesc.value = s.desc; });
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
  if (!c || !c.steps.length) {
    box.insertAdjacentHTML('beforeend', '<div class="empty steps-empty">还没有步骤。<br>① 点下方「从元素库添加步骤」，选元素 + 操作类型逐条拼；<br>② 或「自定义代码步骤」写任意代码行兜底（高级）。<br><span class="hint">（「添加到元素库」→「② 保存并添加到用例」会把一步代码直接追加到已有用例文件，不进这里）</span></div>');
  }
}
/* 收集表单 → 生成用例（+页面对象） */
async function onSaveCase() {
  const c = ensureCurrentCase();
  c.caseFile = $('case-file').value.trim();
  c.caseClass = $('case-class').value.trim();
  c.methodName = $('case-method').value.trim();
  c.desc = $('case-desc').value.trim();
  c.pkg = $('case-pkg').value.trim();
  c.activity = $('case-activity').value.trim();
  c.pageFile = $('case-page-file').value.trim();
  c.pageClass = $('case-page-class').value.trim();
  c.elementsFile = $('case-ele-file').value;
  c.genPage = $('case-gen-page').checked;
  c.genTeardown = $('case-gen-teardown').checked;
  const res = $('case-result');
  if (!c.caseFile || !c.methodName) { res.className = 'el-result err'; res.textContent = '用例文件名和测试方法名不能为空'; return; }
  if (!c.steps.length) { res.className = 'el-result err'; res.textContent = '还没有任何步骤，请先添加步骤（或用定位器快捷添加）'; return; }
  // 页面文件为空时自动生成默认名（如 login → loginPage.py）
  const pageFile = c.pageFile || (c.caseFile.replace(/^test_/, '').replace(/\.py$/, '') + 'Page.py');
  c.pageFile = pageFile;
  if (!c.pageClass) c.pageClass = toPascalCase(pageFile);
  const payload = {
    case_file: c.caseFile, method_name: c.methodName, desc: c.desc,
    pkg: c.pkg, activity: c.activity,
    case_class: c.caseClass, page_file: pageFile, page_class: c.pageClass,
    elements_file: c.elementsFile, gen_page: c.genPage ? 1 : 0, gen_teardown: c.genTeardown ? 1 : 0,
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