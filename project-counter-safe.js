(() => {
  const getHeader = () => document.querySelector('.scen-head > div:first-child');
  const getTabs = () => document.getElementById('scenarioTabs');
  const getCount = () => document.getElementById('scenarioCount');
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

  function updateProjectHeader() {
    const header = getHeader();
    const count = getCount();
    if (!header || !count) return;

    const prefix = `${isEnglish() ? 'Project' : 'Projektas'} `;
    let textNode = [...header.childNodes].find(n => n.nodeType === Node.TEXT_NODE);
    if (!textNode) {
      textNode = document.createTextNode(prefix);
      header.insertBefore(textNode, count);
    } else if (textNode.nodeValue !== prefix) {
      textNode.nodeValue = prefix;
    }

    const wanted = String(getActiveIndex() + 1);
    if (count.textContent !== wanted) count.textContent = wanted;
  }

  function replaceStaticLabels() {
    const en = isEnglish();
    updateProjectHeader();

    const deleteBtn = document.getElementById('deleteBtn');
    if (deleteBtn) deleteBtn.textContent = en ? 'Delete project' : 'Ištrinti projektą';

    const addBtn = document.getElementById('addBtn');
    if (addBtn) addBtn.textContent = en ? '+ Add project' : '+ Pridėti projektą';

    const nameInput = document.getElementById('nameInput');
    const nameLabel = nameInput?.closest('.field')?.querySelector('label');
    if (nameLabel) nameLabel.textContent = en ? 'Project name' : 'Projekto pavadinimas';

    const notes = document.getElementById('notes');
    const notesLabel = notes?.closest('.field')?.querySelector('label');
    if (notesLabel) notesLabel.textContent = en ? 'Project notes and initial assumptions' : 'Projekto pastabos ir pirminės prielaidos';

    const resultsHeading = document.querySelector('.results-table-card h2');
    if (resultsHeading) resultsHeading.textContent = en ? 'Selected project results.' : 'Pasirinkto projekto rezultatai.';

    const caption = document.querySelector('.results-table caption');
    if (caption) caption.textContent = en
      ? 'Selected project monthly results per worker and team, with editable number of workers'
      : 'Pasirinkto projekto mėnesio rezultatai vienam darbuotojui ir komandai bei keičiamas darbuotojų skaičius';

    const footer = document.querySelector('.content > .footer-note');
    if (footer) footer.textContent = en
      ? 'Euroteams Group · Netherlands project evaluation · Projects are stored in this browser and do not sync between devices.'
      : 'Euroteams Group · Projekto Nyderlanduose vertinimas · Projektai saugomi šioje naršyklėje. Jie nesinchronizuoja tarp įrenginių.';
  }

  function renameNewProjectIfNeeded() {
    const input = document.getElementById('nameInput');
    if (!input) return;
    const oldLt = /^Naujas scenarijus\s+/;
    const oldEn = /^New scenario\s+/;
    let next = input.value;
    if (oldLt.test(next)) next = next.replace(oldLt, 'Naujas projektas ');
    if (oldEn.test(next)) next = next.replace(oldEn, 'New project ');
    if (next !== input.value) {
      input.value = next;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  const schedule = () => requestAnimationFrame(() => requestAnimationFrame(() => {
    replaceStaticLabels();
    renameNewProjectIfNeeded();
  }));

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
  if (tabs) new MutationObserver(schedule).observe(tabs, { childList: true, subtree: true, attributes: true });

  const count = getCount();
  if (count) new MutationObserver(schedule).observe(count, { childList: true, characterData: true, subtree: true });

  schedule();
})();