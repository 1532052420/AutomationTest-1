/* 管理后台 · 上传与文件管理（口令存 localStorage，随请求头发送） */
'use strict';

function adminToken() { return localStorage.getItem('adminToken') || ''; }

function adminApi(url, opts) {
  opts = opts || {};
  opts.headers = Object.assign({'X-Admin-Token': adminToken()}, opts.headers || {});
  return fetch(url, opts).then(async res => {
    const data = await res.json().catch(() => ({ok: false, msg: '响应解析失败(' + res.status + ')'}));
    if (res.status === 401) data.needToken = true;
    return data;
  });
}

async function adminLoadFiles() {
  const kind = $('#listKind').value;
  const d = await adminApi('/api/admin/files?kind=' + kind);
  if (d.needToken) { $('#authCard').style.display = ''; toast('请先输入访问口令', false); return; }
  if (!d.ok) return toast(d.msg || '加载失败', false);
  if (d.auth === 'off') $('#authCard').style.display = 'none';
  else $('#authCard').style.display = '';
  $('#fileCount').textContent = '· 共 ' + d.files.length + ' 个';
  const tb = $('#fileList');
  if (!d.files.length) {
    tb.innerHTML = '<tr><td colspan="4"><div class="empty">该目录暂无 .py 文件</div></td></tr>';
    return;
  }
  tb.innerHTML = d.files.map(f =>
    '<tr><td><b>' + esc(f.path) + '</b></td>' +
    '<td class="muted">' + (f.size / 1024).toFixed(1) + ' KB</td>' +
    '<td class="muted">' + fmtTime(new Date(f.mtime * 1000).toISOString()) + '</td>' +
    '<td><button class="mini danger-ghost admin-del" data-path="' + esc(f.path) + '">删除</button></td></tr>').join('');
}

async function adminUpload() {
  const fileInput = $('#upFile');
  if (!fileInput.files.length) return toast('请选择 .py 文件', false);
  const fd = new FormData();
  fd.append('kind', $('#upKind').value);
  fd.append('subdir', $('#upSubdir').value.trim());
  fd.append('force', $('#upForce').checked ? 'true' : 'false');
  fd.append('file', fileInput.files[0]);
  const d = await adminApi('/api/admin/upload', {method: 'POST', body: fd});
  if (d.needToken) { $('#authCard').style.display = ''; return toast('请先输入访问口令', false); }
  toast(d.msg || (d.ok ? '上传成功' : '上传失败'), d.ok);
  if (d.ok) { fileInput.value = ''; adminLoadFiles(); }
}

async function adminDelete(path) {
  const yes = await confirmModal('删除文件', '将删除 ' + path + '，不可恢复。', true);
  if (!yes) return;
  const d = await adminApi('/api/admin/file?kind=' + $('#listKind').value + '&path=' + encodeURIComponent(path), {method: 'DELETE'});
  toast(d.msg || (d.ok ? '已删除' : '删除失败'), d.ok);
  adminLoadFiles();
}

function adminInit() {
  renderSidebar('/admin');
  adminLoadFiles();
  $('#btnUpload').addEventListener('click', adminUpload);
  $('#btnToken').addEventListener('click', () => {
    localStorage.setItem('adminToken', $('#inToken').value.trim());
    toast('口令已保存到本机浏览器');
    adminLoadFiles();
  });
  $('#listKind').addEventListener('change', adminLoadFiles);
  $('#fileList').addEventListener('click', (e) => {
    const b = e.target.closest('.admin-del');
    if (b) adminDelete(b.dataset.path);
  });
}

document.addEventListener('DOMContentLoaded', adminInit);
