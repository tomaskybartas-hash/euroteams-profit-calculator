(() => {
  const core = document.createElement('script');
  core.src = 'app-core.js?v=20261014-1';
  core.onload = () => {
    const fix = document.createElement('script');
    fix.src = 'name-save-fix.js?v=20261014-1';
    fix.onload = () => {
      const projectCounter = document.createElement('script');
      projectCounter.src = 'project-counter-safe.js?v=20261014-3';
      projectCounter.onload = () => {
        const language = document.createElement('script');
        language.src = 'full-language.js?v=20261014-3';
        language.onload = () => {
          const patch = document.createElement('script');
          patch.src = 'language-patch.js?v=20261014-3';
          patch.onload = () => {
            const functionality = document.createElement('script');
            functionality.src = 'functionality-fix.js?v=20261014-1';
            functionality.onload = () => {
              const terminology = document.createElement('script');
              terminology.src = 'terminology-patch.js?v=20261014-1';
              terminology.onload = () => {
                const payroll = document.createElement('script');
                payroll.src = 'payroll-net-module-v4.js?v=20261014-2';
                payroll.onload = () => {
                  const clarity = document.createElement('script');
                  clarity.src = 'payroll-label-clarity.js?v=20261014-1';
                  document.head.appendChild(clarity);
                };
                document.head.appendChild(payroll);
              };
              document.head.appendChild(terminology);
            };
            document.head.appendChild(functionality);
          };
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