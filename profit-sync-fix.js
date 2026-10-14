(() => {
  const MAIN_KEY = 'euroteams-profit-calculator-v3';
  const $ = id => document.getElementById(id);

  function activeIndex() {
    try {
      const st = JSON.parse(localStorage.getItem(MAIN_KEY) || 'null');
      if (st && Array.isArray(st.scenarios)) {
        return Math.max(0, Math.min(Number(st.selected) || 0, st.scenarios.length - 1));
      }
    } catch (e) {}
    return 0;
  }

  function syncActiveScenarioProfit() {
    const teamProfit = $('teamProfit');
    const tabs = $('scenarioTabs')?.querySelectorAll('.scenario-tab');
    if (!teamProfit || !tabs?.length) return;
    const tab = tabs[activeIndex()];
    const target = tab?.querySelector('.scenario-profit strong');
    if (target && target.textContent !== teamProfit.textContent) {
      target.textContent = teamProfit.textContent;
    }
  }

  function init() {
    const teamProfit = $('teamProfit');
    if (!teamProfit) {
      setTimeout(init, 100);
      return;
    }
    syncActiveScenarioProfit();
    new MutationObserver(syncActiveScenarioProfit).observe(teamProfit, {
      childList: true,
      subtree: true,
      characterData: true
    });
    document.addEventListener('click', e => {
      if (e.target.closest('#scenarioTabs') || e.target.closest('#addBtn') || e.target.closest('#deleteBtn') || e.target.closest('#resetBtn')) {
        requestAnimationFrame(() => requestAnimationFrame(syncActiveScenarioProfit));
      }
    });
  }

  window.addEventListener('load', () => setTimeout(init, 120));
  setTimeout(init, 180);
})();
