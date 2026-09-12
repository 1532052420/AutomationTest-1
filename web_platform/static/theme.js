/* 测试平台 · 日间/夜间模式切换（悬浮按钮，宫崎骏风日/月图标，所有页面通用）
   默认夜间（黑色居多，即原深色主题）；日间模式白色居多（html.day 变量覆盖，见 style.css）
   选择存 localStorage['platform_theme']，刷新/重开保持
   按钮图标：日间显示月亮图（点击切夜间），夜间显示太阳图（点击切日间） */
(function () {
  const KEY = 'platform_theme';
  const ICON_MOON = '/static/theme_moon.png';
  const ICON_SUN = '/static/theme_sun.png';

  function apply(mode) {
    document.documentElement.classList.toggle('day', mode === 'day');
    const fab = document.getElementById('theme-fab');
    if (fab) {
      fab.innerHTML = '<img src="' + (mode === 'day' ? ICON_MOON : ICON_SUN) + '" alt="切换主题">';
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
