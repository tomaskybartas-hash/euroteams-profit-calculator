(() => {
  const core = document.createElement('script');
  core.src = 'app-core.js?v=20261013-1';
  core.onload = () => {
    const fix = document.createElement('script');
    fix.src = 'name-save-fix.js?v=20261013-1';
    fix.onload = () => {
      const projectCounter = document.createElement('script');
      projectCounter.src = 'project-counter-safe.js?v=20261014-2';
      projectCounter.onload = () => {
        const language = document.createElement('script');
        language.src = 'full-language.js?v=20261014-2';
        language.onload = () => {
          const patch = document.createElement('script');
          patch.src = 'language-patch.js?v=20261014-1';
          document.head.appendChild(patch);
        };
        document.head.appendChild(language);
      };
      document.head.appendChild(projectCounter);
    };
    document.head.appendChild(fix);
  };
  document.head.appendChild(core);
})();