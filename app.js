(() => {
  const core = document.createElement('script');
  core.src = 'app-core.js?v=20261013-1';
  core.onload = () => {
    const fix = document.createElement('script');
    fix.src = 'name-save-fix.js?v=20261013-1';
    document.head.appendChild(fix);
  };
  document.head.appendChild(core);
})();