(() => {
  const counter = document.getElementById('scenarioCount');
  if (!counter || typeof st === 'undefined') return;

  const updateProjectCounter = () => {
    const parent = counter.parentElement;
    if (!parent) return;
    const label = st.lang === 'en' ? 'Project ' : 'Projektas ';
    if (parent.firstChild && parent.firstChild.nodeType === Node.TEXT_NODE) {
      parent.firstChild.nodeValue = label;
    }
    counter.textContent = String((Number(st.selected) || 0) + 1);
  };

  let correcting = false;
  const observer = new MutationObserver(() => {
    if (correcting) return;
    correcting = true;
    updateProjectCounter();
    correcting = false;
  });

  observer.observe(counter, { childList: true, characterData: true, subtree: true });
  document.getElementById('scenarioTabs')?.addEventListener('click', () => setTimeout(updateProjectCounter, 0));
  document.getElementById('addBtn')?.addEventListener('click', () => setTimeout(updateProjectCounter, 0));
  document.getElementById('deleteBtn')?.addEventListener('click', () => setTimeout(updateProjectCounter, 0));
  document.getElementById('resetBtn')?.addEventListener('click', () => setTimeout(updateProjectCounter, 0));
  document.getElementById('ltBtn')?.addEventListener('click', () => setTimeout(updateProjectCounter, 0));
  document.getElementById('enBtn')?.addEventListener('click', () => setTimeout(updateProjectCounter, 0));
  updateProjectCounter();
})();