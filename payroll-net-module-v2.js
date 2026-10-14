(() => {
  const STORE_KEY = 'euroteams-payroll-2026-v1';
  const MAIN_KEY = 'euroteams-profit-calculator-v3';
  const DEFAULTS = {
    pension2: false,
    applyNpd: false,
    employerRate: 1.77,
    perDiem: 0,
    localTransport: 0,
    workwearTools: 0
  };

  const $ = id => document.getElementById(id);
  const n = v => Math.max(0, Number(v) || 0);
  const isEn = () => $('enBtn')?.classList.contains('active');
  const tr = (lt, en) => isEn() ? en : lt;
  const money = v => new Intl.NumberFormat(isEn() ? 'en-GB' : 'lt-LT', {
    style: 'currency', currency: 'EUR', minimumFractionDigits: 2, maximumFractionDigits: 2
  }).format(Number(v) || 0);
  const pct = v => new Intl.NumberFormat(isEn() ? 'en-GB' : 'lt-LT', {
    minimumFractionDigits: 2, maximumFractionDigits: 2
  }).format(Number(v) || 0) + ' %';

  let recalcQueued = false;
  let syncingEmployer = false;

  function getMainState() {
    try { return JSON.parse(localStorage.getItem(MAIN_KEY) || 'null'); }
    catch (e) { return null; }
  }

  function activeIndex() {
    const st = getMainState();
    if (st && Array.isArray(st.scenarios)) {
      return Math.max(0, Math.min(Number(st.selected) || 0, st.scenarios.length - 1));
    }
    const tabs = $('scenarioTabs');
    if (!tabs || !tabs.children.length) return 0;
    const items = [...tabs.children];
    const idx = items.findIndex(el => {
      const c = el.style.borderColor || '';
      return c.includes('var(--gold)') || c.includes('rgb(178, 138, 72)');
    });
    return idx >= 0 ? idx : 0;
  }

  function currentScenario() {
    const st = getMainState();
    if (!st || !Array.isArray(st.scenarios)) return null;
    return st.scenarios[activeIndex()] || null;
  }

  function loadAll() {
    try { return JSON.parse(localStorage.getItem(STORE_KEY) || '{}') || {}; }
    catch (e) { return {}; }
  }

  function getSettings() {
    const all = loadAll();
    return { ...DEFAULTS, ...(all[String(activeIndex())] || {}) };
  }

  function saveSettings(patch) {
    const all = loadAll();
    const key = String(activeIndex());
    all[key] = { ...DEFAULTS, ...(all[key] || {}), ...patch };
    localStorage.setItem(STORE_KEY, JSON.stringify(all));
  }

  function npdForGross(gross, apply) {
    if (!apply) return 0;
    if (gross <= 1153) return 747;
    return Math.max(0, 747 - 0.49 * (gross - 1153));
  }

  function payrollFromGross(gross, cfg) {
    const sodra = gross * 0.195;
    const pension = cfg.pension2 ? gross * 0.03 : 0;
    const npd = npdForGross(gross, cfg.applyNpd);
    const gpmBase = Math.max(0, gross - npd);
    const gpm = gpmBase * 0.20;
    const net = gross - sodra - pension - gpm;
    const employerTaxes = gross * (n(cfg.employerRate) / 100);
    return { gross, sodra, pension, npd, gpmBase, gpm, net, employerTaxes, payrollCost: gross + employerTaxes };
  }

  function grossFromNet(targetNet, cfg) {
    targetNet = n(targetNet);
    if (targetNet === 0) return payrollFromGross(0, cfg);
    if (!cfg.applyNpd) {
      const denom = 1 - 0.195 - (cfg.pension2 ? 0.03 : 0) - 0.20;
      return payrollFromGross(targetNet / denom, cfg);
    }
    let lo = 0;
    let hi = Math.max(2000, targetNet * 2.5 + 1000);
    while (payrollFromGross(hi, cfg).net < targetNet) hi *= 2;
    for (let i = 0; i < 100; i++) {
      const mid = (lo + hi) / 2;
      if (payrollFromGross(mid, cfg).net < targetNet) lo = mid;
      else hi = mid;
    }
    return payrollFromGross((lo + hi) / 2, cfg);
  }

  function ensureUi() {
    const monthly = $('monthlyFields');
    if (!monthly) return false;

    const payLabel = $('monthlyPay')?.closest('.field')?.querySelector('label');
    const costLabel = $('monthlyEmployer')?.closest('.field')?.querySelector('label');
    if (payLabel) payLabel.textContent = tr('Darbuotojo NETO atlyginimas / mėn.', 'Employee NET salary / month');
    if (costLabel) costLabel.textContent = tr('DU savikaina įmonei / mėn.', 'Payroll cost to company / month');

    const employer = $('monthlyEmployer');
    if (employer) {
      employer.readOnly = true;
      employer.setAttribute('aria-readonly', 'true');
      employer.step = '0.01';
    }

    if (!$('payrollCostHelp') && employer) {
      const help = document.createElement('div');
      help.id = 'payrollCostHelp';
      help.className = 'help';
      employer.closest('.field').appendChild(help);
    }

    if (!$('payroll2026Controls')) {
      const box = document.createElement('div');
      box.id = 'payroll2026Controls';
      box.style.marginTop = '16px';
      box.innerHTML = `
        <div class="two">
          <div class="field">
            <label id="pension2Label"></label>
            <select id="pension2"><option value="no">NE</option><option value="yes">TAIP, +3 %</option></select>
          </div>
          <div class="field">
            <label id="npdLabel"></label>
            <select id="applyNpd"><option value="no">NE</option><option value="yes">TAIP</option></select>
          </div>
        </div>
        <div class="field"><label id="employerRateLabel"></label><input id="employerRate2026" type="number" step="0.01" min="0"></div>
        <div id="payrollRateHelp" class="help"></div>
        <div class="subhead" id="payrollBreakdownTitle"></div>
        <div id="payrollBreakdown" class="metrics" style="grid-template-columns:repeat(2,minmax(0,1fr));"></div>
        <div class="subhead" id="extraProjectCostsTitle"></div>
        <div class="field"><label id="perDiemLabel"></label><input id="perDiem2026" type="number" step="0.01" min="0"></div>
        <div class="two">
          <div class="field"><label id="localTransportLabel"></label><input id="localTransport2026" type="number" step="0.01" min="0"></div>
          <div class="field"><label id="workwearToolsLabel"></label><input id="workwearTools2026" type="number" step="0.01" min="0"></div>
        </div>`;
      monthly.appendChild(box);
      bindPayrollControls();
    }

    translateUi();
    return true;
  }

  function bindPayrollControls() {
    const pension2 = $('pension2');
    const applyNpd = $('applyNpd');

    if (pension2 && !pension2.dataset.bound) {
      pension2.dataset.bound = '1';
      pension2.addEventListener('change', () => {
        saveSettings({ pension2: pension2.value === 'yes' });
        setTimeout(recalc, 0);
      });
    }

    if (applyNpd && !applyNpd.dataset.bound) {
      applyNpd.dataset.bound = '1';
      applyNpd.addEventListener('change', () => {
        saveSettings({ applyNpd: applyNpd.value === 'yes' });
        setTimeout(recalc, 0);
      });
    }

    ['employerRate2026', 'perDiem2026', 'localTransport2026', 'workwearTools2026'].forEach(id => {
      const el = $(id);
      if (!el || el.dataset.bound) return;
      el.dataset.bound = '1';
      el.addEventListener('input', () => {
        const patch = {};
        if (id === 'employerRate2026') patch.employerRate = n(el.value);
        if (id === 'perDiem2026') patch.perDiem = n(el.value);
        if (id === 'localTransport2026') patch.localTransport = n(el.value);
        if (id === 'workwearTools2026') patch.workwearTools = n(el.value);
        saveSettings(patch);
        scheduleRecalc();
      });
      el.addEventListener('blur', () => {
        if (el.value !== '') el.value = n(el.value).toFixed(2);
      });
    });
  }

  function translateUi() {
    if ($('pension2Label')) $('pension2Label').textContent = tr('II pakopos pensijų kaupimas', 'Pillar II pension contribution');
    if ($('npdLabel')) $('npdLabel').textContent = tr('Taikyti NPD', 'Apply monthly tax-free allowance (NPD)');
    if ($('employerRateLabel')) $('employerRateLabel').textContent = tr('Darbdavio mokesčių tarifas (%)', 'Employer contribution rate (%)');
    if ($('payrollRateHelp')) $('payrollRateHelp').textContent = tr(
      'Numatyta 1,77 %. Tarifą galima keisti pagal darbo sutarties tipą ir nelaimingų atsitikimų draudimo grupę.',
      'Default 1.77%. The rate can be changed according to the employment contract type and accident insurance group.'
    );
    if ($('payrollBreakdownTitle')) $('payrollBreakdownTitle').textContent = tr('2026 m. darbo užmokesčio išklotinė', '2026 payroll breakdown');
    if ($('extraProjectCostsTitle')) $('extraProjectCostsTitle').textContent = tr('Atskiros projekto sąnaudos', 'Separate project costs');
    if ($('perDiemLabel')) $('perDiemLabel').textContent = tr('Komandiruotpinigiai / mėn.', 'Per diem / month');
    if ($('localTransportLabel')) $('localTransportLabel').textContent = tr('Vietinis transportas / mėn.', 'Local transport / month');
    if ($('workwearToolsLabel')) $('workwearToolsLabel').textContent = tr('Darbo rūbai / įrankiai / mėn.', 'Workwear / tools / month');
    if ($('payrollCostHelp')) $('payrollCostHelp').textContent = tr(
      'Bruto atlyginimas + darbdavio socialinės įmokos. Komandiruotpinigiai, būstas, kelionės ir kitos projekto išlaidos skaičiuojamos atskirai.',
      'Gross salary + employer social contributions. Per diem, accommodation, travel and other project costs are calculated separately.'
    );
    if ($('pension2')) {
      $('pension2').options[0].textContent = tr('NE', 'NO');
      $('pension2').options[1].textContent = tr('TAIP, +3 %', 'YES, +3%');
    }
    if ($('applyNpd')) {
      $('applyNpd').options[0].textContent = tr('NE', 'NO');
      $('applyNpd').options[1].textContent = tr('TAIP', 'YES');
    }
  }

  function hydrateControls(cfg) {
    if ($('pension2')) $('pension2').value = cfg.pension2 ? 'yes' : 'no';
    if ($('applyNpd')) $('applyNpd').value = cfg.applyNpd ? 'yes' : 'no';
    if ($('employerRate2026') && document.activeElement !== $('employerRate2026')) $('employerRate2026').value = n(cfg.employerRate).toFixed(2);
    if ($('perDiem2026') && document.activeElement !== $('perDiem2026')) $('perDiem2026').value = n(cfg.perDiem).toFixed(2);
    if ($('localTransport2026') && document.activeElement !== $('localTransport2026')) $('localTransport2026').value = n(cfg.localTransport).toFixed(2);
    if ($('workwearTools2026') && document.activeElement !== $('workwearTools2026')) $('workwearTools2026').value = n(cfg.workwearTools).toFixed(2);
  }

  function renderBreakdown(p) {
    const b = $('payrollBreakdown');
    if (!b) return;
    const rows = [
      [tr('Darbuotojo NETO', 'Employee NET'), p.net],
      [tr('Bruto atlyginimas', 'Gross salary'), p.gross],
      [tr('Darbuotojo Sodra 19,50 %', 'Employee social insurance 19.50%'), p.sodra],
      [tr('GPM 20 %', 'Personal income tax 20%'), p.gpm],
      [tr('Pensijų kaupimas', 'Pillar II pension'), p.pension],
      [tr('Darbdavio mokesčiai', 'Employer contributions'), p.employerTaxes],
      [tr('DU savikaina įmonei', 'Payroll cost to company'), p.payrollCost]
    ];
    const html = rows.map(([label, val]) => `<div class="metric"><span>${label}</span><strong>${money(val)}</strong></div>`).join('');
    if (b.innerHTML !== html) b.innerHTML = html;
  }

  function syncCoreMonthlyEmployer(p) {
    const input = $('monthlyEmployer');
    if (!input || syncingEmployer) return;
    const shown = p.payrollCost.toFixed(2);
    if (input.value === shown) return;
    syncingEmployer = true;
    input.value = shown;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    syncingEmployer = false;
  }

  function overrideResults(p, cfg) {
    const s = currentScenario();
    if (!s) return;
    const rate = n(s.clientRate);
    const hours = n(s.hours);
    const workers = Math.max(1, Math.round(n(s.workers) || 1));
    const revenue = rate * hours;
    const housing = n(s.housing);
    let travel = n(s.travelMonthly);
    if ((s.travelMode || 'monthly') === 'rotation') {
      let work = 6, home = 2;
      if (s.rotation === 'custom') { work = Math.max(1, n(s.workWeeks)); home = n(s.homeWeeks); }
      else {
        const parts = String(s.rotation || '6/2').split('/').map(Number);
        work = parts[0] || 6;
        home = parts[1] || 2;
      }
      travel = n(s.travelRotation) * (4.345 / Math.max(1, work + home));
    }
    const other = n(s.other);
    const total = p.payrollCost + housing + travel + other + n(cfg.perDiem) + n(cfg.localTransport) + n(cfg.workwearTools);
    const profit = revenue - total;
    const margin = revenue ? profit / revenue * 100 : 0;
    const ph = hours ? profit / hours : 0;
    const be = hours ? total / hours : 0;

    if ($('salaryValue')) $('salaryValue').textContent = money(p.net);
    if ($('employerValue')) $('employerValue').textContent = money(p.payrollCost);
    if ($('extraEmployerValue')) $('extraEmployerValue').textContent = money(p.employerTaxes);
    if ($('totalCostValue')) $('totalCostValue').textContent = money(total);
    if ($('profitValue')) $('profitValue').textContent = money(profit);
    if ($('marginValue')) $('marginValue').textContent = pct(margin);
    if ($('profitHourValue')) $('profitHourValue').textContent = money(ph);
    if ($('breakevenValue')) $('breakevenValue').textContent = money(be) + (isEn() ? ' / h' : ' / val.');
    if ($('teamRevenue')) $('teamRevenue').textContent = money(revenue * workers);
    if ($('teamCosts')) $('teamCosts').textContent = money(total * workers);
    if ($('teamProfit')) $('teamProfit').textContent = money(profit * workers);

    const extraLabel = $('extraEmployerValue')?.closest('.metric')?.querySelector('span');
    if (extraLabel) extraLabel.textContent = tr('Darbdavio mokesčiai', 'Employer contributions');

    const tbody = $('resultTableBody');
    if (tbody) {
      const r = (a, b, cls = '') => `<tr><th>${a}</th><td class="${cls}">${b}</td></tr>`;
      const html = [
        r(tr('Darbuotojų skaičius', 'Number of workers'), `<input id="tableWorkers" type="number" min="1" value="${workers}" style="max-width:120px">`),
        r(tr('Pajamos iš kliento / darbuotojui', 'Client revenue / worker'), money(revenue)),
        r(tr('Darbuotojo NETO', 'Employee NET'), money(p.net)),
        r(tr('Bruto atlyginimas', 'Gross salary'), money(p.gross)),
        r(tr('Darbuotojo Sodra 19,50 %', 'Employee social insurance 19.50%'), money(p.sodra)),
        r(tr('GPM 20 %', 'Personal income tax 20%'), money(p.gpm)),
        r(tr('Pensijų kaupimas', 'Pillar II pension'), money(p.pension)),
        r(tr('Darbdavio mokesčiai', 'Employer contributions'), money(p.employerTaxes)),
        r(tr('DU savikaina įmonei', 'Payroll cost to company'), money(p.payrollCost)),
        r(tr('Komandiruotpinigiai', 'Per diem'), money(cfg.perDiem)),
        r(tr('Apgyvendinimas', 'Accommodation'), money(housing)),
        r(tr('Kelionės', 'Travel'), money(travel)),
        r(tr('Vietinis transportas', 'Local transport'), money(cfg.localTransport)),
        r(tr('Darbo rūbai / įrankiai', 'Workwear / tools'), money(cfg.workwearTools)),
        r(tr('Kitos išlaidos', 'Other costs'), money(other)),
        r(tr('Visa darbuotojo savikaina', 'Total employee project cost'), money(total)),
        r(tr('Pelnas nuo vieno darbuotojo', 'Profit per worker'), money(profit), 'green'),
        r(tr('Pelnas už valandą', 'Profit per hour'), money(ph), 'green'),
        r(tr('Pelno marža', 'Profit margin'), pct(margin), 'green'),
        r(tr('Tarifas be pelno ir nuostolio', 'Break-even rate'), money(be) + (isEn() ? ' / h' : ' / val.')),
        r(tr('Komandos pelnas', 'Team profit'), money(profit * workers), 'green')
      ].join('');
      if (tbody.innerHTML !== html) tbody.innerHTML = html;
    }
  }

  function recalc() {
    recalcQueued = false;
    if (!ensureUi()) return;
    const monthly = $('monthlyFields');
    if (!monthly || monthly.classList.contains('hidden')) return;
    const cfg = getSettings();
    hydrateControls(cfg);
    const p = grossFromNet(n($('monthlyPay')?.value), cfg);
    syncCoreMonthlyEmployer(p);
    renderBreakdown(p);
    overrideResults(p, cfg);
    translateUi();
  }

  function scheduleRecalc() {
    if (recalcQueued) return;
    recalcQueued = true;
    requestAnimationFrame(recalc);
  }

  const baseRealtimeIds = new Set([
    'monthlyPay', 'clientRate', 'hours', 'workers', 'housing', 'travelMonthly', 'travelRotation',
    'other', 'workWeeks', 'homeWeeks'
  ]);

  document.addEventListener('input', e => {
    const id = e.target?.id;
    if (id === 'monthlyEmployer' || syncingEmployer) return;
    if (id === 'tableWorkers') {
      const main = $('workers');
      if (main) {
        main.value = Math.max(1, Math.round(n(e.target.value) || 1));
        main.dispatchEvent(new Event('input', { bubbles: true }));
      }
      return;
    }
    if (baseRealtimeIds.has(id)) scheduleRecalc();
  });

  document.addEventListener('change', e => {
    const id = e.target?.id;
    if (id === 'rotation' || id === 'presetSelect') scheduleRecalc();
  });

  document.addEventListener('click', e => {
    if (e.target.closest('#modeMonthly') || e.target.closest('#ltBtn') || e.target.closest('#enBtn') ||
        e.target.closest('#scenarioTabs') || e.target.closest('#addBtn') || e.target.closest('#deleteBtn') ||
        e.target.closest('#resetBtn') || e.target.closest('#travelMonthlyBtn') || e.target.closest('#travelRotationBtn')) {
      requestAnimationFrame(() => requestAnimationFrame(recalc));
    }
  });

  window.addEventListener('load', () => setTimeout(recalc, 100));
  setTimeout(recalc, 150);
})();