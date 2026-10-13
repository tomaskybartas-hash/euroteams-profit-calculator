(() => {
  const getHeader = () => document.querySelector('.scen-head > div:first-child');
  const getTabs = () => document.getElementById('scenarioTabs');
  const isEnglish = () => document.getElementById('enBtn')?.classList.contains('active');

  function getActiveIndex() {
    const tabs = getTabs();
    if (!tabs || !tabs.children.length) return 0;
    const items = [...tabs.children];
    const idx = items.findIndex(el => {
      const c = el.style.borderColor || '';
      return c.includes('var(--gold)') || c.includes('rgb(178, 138, 72)');
    });
    return idx >= 0 ? idx : 0;
  }

  function updateProjectLabel() {
    const header = getHeader();
    if (!header) return;
    const number = getActiveIndex() + 1;
    header.textContent = `${isEnglish() ? 'Project' : 'Projektas'} ${number}`;
  }

  const schedule = () => requestAnimationFrame(() => requestAnimationFrame(updateProjectLabel));

  window.addEventListener('load', schedule);
  document.addEventListener('click', e => {
    if (
      e.target.closest('#scenarioTabs') ||
      e.target.closest('#addBtn') ||
      e.target.closest('#deleteBtn') ||
      e.target.closest('#resetBtn') ||
      e.target.closest('#ltBtn') ||
      e.target.closest('#enBtn')
    ) schedule();
  });

  const tabs = getTabs();
  if (tabs) {
    new MutationObserver(schedule).observe(tabs, { childList: true });
  }

  schedule();
})();