(() => {
  function activeProjectIndex() {
    const tabs = document.getElementById('scenarioTabs');
    if (!tabs || !tabs.children.length) return 0;
    const items = [...tabs.children];
    const idx = items.findIndex(el => {
      const c = el.style.borderColor || '';
      return c.includes('var(--gold)') || c.includes('rgb(178, 138, 72)');
    });
    return idx >= 0 ? idx : 0;
  }

  function ensureScenarioCount() {
    const header = document.querySelector('.scen-head > div:first-child');
    if (!header) return;

    let count = document.getElementById('scenarioCount');
    const en = document.getElementById('enBtn')?.classList.contains('active');
    const number = String(activeProjectIndex() + 1);

    if (!count) {
      header.textContent = '';
      header.appendChild(document.createTextNode(`${en ? 'Project' : 'Projektas'} `));
      count = document.createElement('strong');
      count.id = 'scenarioCount';
      count.textContent = number;
      header.appendChild(count);
      return;
    }

    const textNode = [...header.childNodes].find(n => n.nodeType === Node.TEXT_NODE);
    const prefix = `${en ? 'Project' : 'Projektas'} `;
    if (textNode) {
      if (textNode.nodeValue !== prefix) textNode.nodeValue = prefix;
    } else {
      header.insertBefore(document.createTextNode(prefix), count);
    }
  }

  const header = document.querySelector('.scen-head > div:first-child');
  if (header) {
    new MutationObserver(() => {
      if (!document.getElementById('scenarioCount')) ensureScenarioCount();
    }).observe(header, { childList: true, subtree: true });
  }

  document.addEventListener('click', e => {
    if (e.target.closest('#ltBtn') || e.target.closest('#enBtn') || e.target.closest('#scenarioTabs') || e.target.closest('#addBtn') || e.target.closest('#deleteBtn') || e.target.closest('#resetBtn')) {
      queueMicrotask(ensureScenarioCount);
      requestAnimationFrame(ensureScenarioCount);
    }
  });

  window.addEventListener('load', ensureScenarioCount);
  ensureScenarioCount();
})();