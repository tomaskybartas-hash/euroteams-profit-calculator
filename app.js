(() => {
  const load = (src, done) => {
    const s = document.createElement('script');
    s.src = src;
    if (done) s.onload = done;
    document.head.appendChild(s);
  };

  load('app-core.js?v=20261014-1', () => {
    load('name-save-fix.js?v=20261014-1', () => {
      load('project-counter-safe.js?v=20261014-3', () => {
        load('full-language.js?v=20261014-3', () => {
          load('language-patch.js?v=20261014-3', () => {
            load('functionality-fix.js?v=20261014-1', () => {
              load('terminology-patch.js?v=20261014-1', () => {
                load('payroll-net-module-v4.js?v=20261014-3', () => {
                  load('final-audit.js?v=20261014-1', () => {
                    load('hourly-a1-module.js?v=20261014-1', () => {
                      load('a1-profit-sync-fix.js?v=20261014-1');
                    });
                  });
                });
              });
            });
          });
        });
      });
    });
  });
})();
