(() => {
  const core = document.createElement('script');
  core.src = 'app-core.js?v=20261013-1';
  core.onload = () => {
    const fix = document.createElement('script');
    fix.src = 'name-save-fix.js?v=20261013-1';
    fix.onload = () => {
      const projectCounter = document.createElement('script');
      projectCounter.src = 'project-counter-safe.js?v=20261013-2';
      document.head.appendChild(projectCounter);
    };
    document.head.appendChild(fix);
  };
  document.head.appendChild(core);
})();