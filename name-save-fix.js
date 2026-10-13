(() => {
  const KEY = 'euroteams-profit-calculator-v3';

  function persistScenarioName() {
    const input = document.getElementById('nameInput');
    if (!input) return;
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return;
      const data = JSON.parse(raw);
      if (!data || !Array.isArray(data.scenarios)) return;
      const selected = Math.max(0, Math.min(Number(data.selected) || 0, data.scenarios.length - 1));
      if (!data.scenarios[selected]) return;
      data.scenarios[selected].name = input.value;
      localStorage.setItem(KEY, JSON.stringify(data));
      const msg = document.getElementById('savedMsg');
      if (msg) msg.textContent = 'Išsaugota šioje naršyklėje';
    } catch (e) {
      console.error('Could not save scenario name', e);
    }
  }

  function attach() {
    const input = document.getElementById('nameInput');
    if (!input || input.dataset.saveFixAttached === '1') return;
    input.dataset.saveFixAttached = '1';
    input.addEventListener('input', persistScenarioName);
    input.addEventListener('change', persistScenarioName);
    input.addEventListener('blur', persistScenarioName);
    window.addEventListener('beforeunload', persistScenarioName);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', attach);
  } else {
    attach();
  }
})();