/* 测试平台 · 日间/夜间模式切换（悬浮按钮，Mac/iPhone 简约风日/月图标，所有页面通用）
   默认夜间（黑色居多，即原深色主题）；日间模式白色居多（html.day 变量覆盖，见 style.css）
   选择存 localStorage['platform_theme']，刷新/重开保持
   按钮图标：日间显示月亮（点击切夜间），夜间显示太阳（点击切日间）；图标颜色随主题自适应 */
(function () {
  const KEY = 'platform_theme';
  /* SF Symbols 风格：细线太阳 / 实心月牙 */
  const ICON_SUN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">'
    + '<circle cx="12" cy="12" r="4.1"/>'
    + '<path d="M12 2.8v2M12 19.2v2M2.8 12h2M19.2 12h2M5.2 5.2l1.5 1.5M17.3 17.3l1.5 1.5M18.8 5.2l-1.5 1.5M6.7 17.3l-1.5 1.5"/></svg>';
  const ICON_MOON = '<svg viewBox="0 0 24 24" fill="currentColor">'
    + '<path d="M20.6 14.4A8.6 8.6 0 0 1 9.6 3.4 8.6 8.6 0 1 0 20.6 14.4Z"/></svg>';

  function apply(mode) {
    document.documentElement.classList.toggle('day', mode === 'day');
    const fab = document.getElementById('theme-fab');
    if (fab) {
      fab.innerHTML = mode === 'day' ? ICON_MOON : ICON_SUN;
      fab.title = mode === 'day' ? '切换到夜间模式（黑色）' : '切换到日间模式（白色）';
    }
  }

  function current() {
    try { if (localStorage.getItem(KEY) === 'day') return 'day'; } catch (e) { /* 忽略 */ }
    return 'night';
  }

  function toggle() {
    const m = current() === 'day' ? 'night' : 'day';
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
