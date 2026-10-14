(() => {
  const isEn = () => document.getElementById('enBtn')?.classList.contains('active');

  const LT = new Map([
    ['Dienpinigiai','Bendra apskaičiuota dienpinigių suma'],
    ['Neapmokestinami dienpinigiai','Iš jų neapmokestinami dienpinigiai'],
    ['Apmokestinami dienpinigiai','Iš jų apmokestinami dienpinigiai'],
    ['NETO darbo užmokestis','NETO darbo užmokestis (be dienpinigių)']
  ]);
  const EN = new Map([
    ['Per diem','Total calculated per diem'],
    ['Tax-exempt per diem','Of which tax-exempt per diem'],
    ['Taxable per diem','Of which taxable per diem'],
    ['NET salary','NET salary (excluding per diem)']
  ]);

  function patchText(root) {
    if (!root) return;
    const map = isEn() ? EN : LT;
    const nodes = root.querySelectorAll('th, span');
    for (const el of nodes) {
      const key = (el.textContent || '').trim();
      const next = map.get(key);
      if (next && key !== next) el.textContent = next;
    }
  }

  function apply() {
    const cfgRaw = localStorage.getItem('euroteams-payroll-2026-v4');
    let include = false, a1 = false;
    try {
      const all = JSON.parse(cfgRaw || '{}') || {};
      const main = JSON.parse(localStorage.getItem('euroteams-profit-calculator-v3') || 'null');
      const idx = main && Array.isArray(main.scenarios) ? Math.max(0, Math.min(Number(main.selected) || 0, main.scenarios.length - 1)) : 0;
      const cfg = all[String(idx)] || {};
      include = cfg.includePerDiemInNet !== false;
      a1 = !!cfg.a1;
    } catch (e) {}

    patchText(document.getElementById('resultTableBody'));
    patchText(document.getElementById('postingSummary'));
    patchText(document.getElementById('payrollBreakdown'));

    const label = document.getElementById('monthlyPay')?.closest('.field')?.querySelector('label');
    if (label && a1 && include) {
      label.textContent = isEn()
        ? 'Total NET amount paid to employee / month (including per diem)'
        : 'Bendra darbuotojui išmokama NETO suma / mėn. (įskaitant dienpinigius)';
    }
  }

  let queued = false;
  function schedule() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      apply();
    });
  }

  document.addEventListener('input', schedule, true);
  document.addEventListener('change', schedule, true);
  document.addEventListener('click', () => requestAnimationFrame(schedule), true);

  const observer = new MutationObserver(schedule);
  const start = () => {
    const roots = ['resultTableBody','postingSummary','payrollBreakdown'].map(id => document.getElementById(id)).filter(Boolean);
    roots.forEach(r => observer.observe(r, {childList:true, subtree:true}));
    apply();
  };
  window.addEventListener('load', () => setTimeout(start, 120));
  setTimeout(start, 220);
})();