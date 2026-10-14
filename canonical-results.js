(() => {
  'use strict';

  const MAIN_KEY = 'euroteams-profit-calculator-v3';
  const PAYROLL_KEY = 'euroteams-payroll-2026-v4';
  const DEFAULTS = Object.freeze({
    pension2:false,
    applyNpd:false,
    employerRate:1.77,
    localTransport:0,
    workwearTools:0,
    a1:false,
    includePerDiemInNet:true,
    country:'NL',
    days:30,
    perDiemRate:64
  });

  const $ = id => document.getElementById(id);
  const n = value => Math.max(0, Number(value) || 0);
  const isEn = () => $('enBtn')?.classList.contains('active');
  const tr = (lt,en) => isEn() ? en : lt;
  const money = value => new Intl.NumberFormat(isEn() ? 'en-GB' : 'lt-LT', {
    style:'currency', currency:'EUR', minimumFractionDigits:2, maximumFractionDigits:2
  }).format(Number(value) || 0);
  const pct = value => new Intl.NumberFormat(isEn() ? 'en-GB' : 'lt-LT', {
    minimumFractionDigits:2, maximumFractionDigits:2
  }).format(Number(value) || 0) + ' %';

  function mainState(){
    try { return JSON.parse(localStorage.getItem(MAIN_KEY) || 'null'); }
    catch { return null; }
  }
  function payrollState(){
    try { return JSON.parse(localStorage.getItem(PAYROLL_KEY) || '{}') || {}; }
    catch { return {}; }
  }
  function settingsFor(index, override){
    return {...DEFAULTS, ...(payrollState()[String(index)] || {}), ...(override || {})};
  }
  function npdForGross(gross, enabled){
    if(!enabled) return 0;
    if(gross <= 1153) return 747;
    return Math.max(0, 747 - 0.49 * (gross - 1153));
  }
  function payrollFromGross(gross, cfg){
    gross = n(gross);
    const sodra = gross * 0.195;
    const pension = cfg.pension2 ? gross * 0.03 : 0;
    const npd = npdForGross(gross, cfg.applyNpd);
    const gpm = Math.max(0, gross - npd) * 0.20;
    const net = gross - sodra - pension - gpm;
    const employerTaxes = gross * (n(cfg.employerRate) / 100);
    return {gross,sodra,pension,npd,gpm,net,employerTaxes,payrollCost:gross + employerTaxes};
  }
  function grossFromNet(target, cfg){
    target = n(target);
    if(!target) return payrollFromGross(0,cfg);
    if(!cfg.applyNpd){
      const denominator = 1 - 0.195 - (cfg.pension2 ? 0.03 : 0) - 0.20;
      return payrollFromGross(target / denominator, cfg);
    }
    let lo = 0, hi = Math.max(2000, target * 3 + 1000);
    while(payrollFromGross(hi,cfg).net < target) hi *= 2;
    for(let i=0;i<120;i++){
      const mid = (lo + hi) / 2;
      if(payrollFromGross(mid,cfg).net < target) lo = mid; else hi = mid;
    }
    return payrollFromGross((lo + hi) / 2, cfg);
  }
  function posting(base, cfg, hours){
    if(!cfg.a1){
      return {
        totalPerDiem:0, exemptPerDiem:0, taxablePerDiem:0, taxablePerDiemNet:0,
        taxableEmployerTaxes:0, totalSodra:base.sodra, totalPension:base.pension,
        totalGpm:base.gpm, paidToEmployee:base.net, payrollPostingCost:base.payrollCost,
        fullyExempt:true
      };
    }
    const totalPerDiem = n(cfg.perDiemRate) * n(cfg.days);
    const hourlyGross = hours ? base.gross / hours : 0;
    const fullyExempt = base.gross >= 1902.45 || hourlyGross >= 11.6325;
    const exemptPerDiem = Math.min(totalPerDiem, fullyExempt ? totalPerDiem : base.gross * 0.50);
    const taxablePerDiem = Math.max(0, totalPerDiem - exemptPerDiem);
    const combined = payrollFromGross(base.gross + taxablePerDiem, cfg);
    const extraSodra = Math.max(0, combined.sodra - base.sodra);
    const extraPension = Math.max(0, combined.pension - base.pension);
    const extraGpm = Math.max(0, combined.gpm - base.gpm);
    const taxablePerDiemNet = Math.max(0, taxablePerDiem - extraSodra - extraPension - extraGpm);
    const taxableEmployerTaxes = taxablePerDiem * (n(cfg.employerRate) / 100);
    return {
      totalPerDiem, exemptPerDiem, taxablePerDiem, taxablePerDiemNet, taxableEmployerTaxes,
      totalSodra:combined.sodra, totalPension:combined.pension, totalGpm:combined.gpm,
      paidToEmployee:base.net + exemptPerDiem + taxablePerDiemNet,
      payrollPostingCost:base.payrollCost + totalPerDiem + taxableEmployerTaxes,
      fullyExempt
    };
  }
  function solveIncluded(target, cfg, hours){
    target = n(target);
    const evaluate = gross => {
      const base = payrollFromGross(gross,cfg);
      return {base,post:posting(base,cfg,hours)};
    };
    if(!target) return evaluate(0);
    let lo = 0, hi = Math.max(3000, target * 3 + n(cfg.perDiemRate) * n(cfg.days) + 1000);
    while(evaluate(hi).post.paidToEmployee < target) hi *= 2;
    for(let i=0;i<140;i++){
      const mid = (lo + hi) / 2;
      if(evaluate(mid).post.paidToEmployee < target) lo = mid; else hi = mid;
    }
    const a = evaluate(lo), b = evaluate(hi);
    return Math.abs(a.post.paidToEmployee-target) <= Math.abs(b.post.paidToEmployee-target) ? a : b;
  }
  function travel(s){
    if((s.travelMode || 'monthly') !== 'rotation') return n(s.travelMonthly);
    let work = 6, home = 2;
    if(s.rotation === 'custom'){
      work = Math.max(1,n(s.workWeeks)); home = n(s.homeWeeks);
    } else {
      const parts = String(s.rotation || '6/2').split('/').map(Number);
      work = parts[0] || 6; home = parts[1] || 2;
    }
    return n(s.travelRotation) * (4.345 / Math.max(1, work + home));
  }

  function calculateScenario(s, index, cfgOverride){
    const cfg = settingsFor(index, cfgOverride);
    const workers = Math.max(1, Math.round(n(s.workers) || 1));
    const hours = n(s.hours);
    const revenue = n(s.clientRate) * hours;
    let workerTotal = 0, employeeShown = 0, base = null, post = null;

    if((s.costMode || 'hourly') === 'monthly'){
      const target = n(s.monthlyPay);
      if(cfg.a1 && cfg.includePerDiemInNet){
        const solved = solveIncluded(target,cfg,hours); base = solved.base; post = solved.post;
      } else {
        base = grossFromNet(target,cfg); post = posting(base,cfg,hours);
      }
      workerTotal = (cfg.a1 ? post.payrollPostingCost : base.payrollCost)
        + n(s.housing) + travel(s) + n(s.other) + n(cfg.localTransport) + n(cfg.workwearTools);
      employeeShown = cfg.a1 && cfg.includePerDiemInNet ? post.paidToEmployee : base.net;
    } else if(cfg.a1){
      const target = n(s.netRate) * hours;
      if(cfg.includePerDiemInNet){
        const solved = solveIncluded(target,cfg,hours); base = solved.base; post = solved.post;
      } else {
        base = grossFromNet(target,cfg); post = posting(base,cfg,hours);
      }
      workerTotal = post.payrollPostingCost
        + n(s.housing) + travel(s) + n(s.other) + n(cfg.localTransport) + n(cfg.workwearTools);
      employeeShown = cfg.includePerDiemInNet ? post.paidToEmployee : base.net;
    } else {
      const salary = n(s.netRate) * hours;
      const employer = salary * (1 + n(s.uplift) / 100);
      workerTotal = employer + n(s.housing) + travel(s) + n(s.other);
      employeeShown = salary;
    }

    const profit = revenue - workerTotal;
    const margin = revenue ? profit / revenue * 100 : 0;
    return {
      workers,hours,revenue,workerTotal,profit,margin,
      profitHour:hours ? profit / hours : 0,
      breakEven:hours ? workerTotal / hours : 0,
      teamRevenue:revenue * workers,
      teamCost:workerTotal * workers,
      teamProfit:profit * workers,
      employeeShown,base,post,cfg
    };
  }

  window.EuroteamsCalculator = Object.freeze({
    calculateScenario,
    payrollFromGross,
    grossFromNet,
    posting,
    solveIncluded
  });

  function tone(el,value){
    if(!el) return;
    el.classList.remove('audit-positive','audit-negative','audit-neutral','green','red');
    el.classList.add(value > 0.005 ? 'audit-positive' : value < -0.005 ? 'audit-negative' : 'audit-neutral');
  }
  function setText(el,text){ if(el && el.textContent !== text) el.textContent = text; }
  function ensureTotals(){
    if($('allProjectsAudit')) return $('allProjectsAudit');
    const tabs = $('scenarioTabs'); if(!tabs) return null;
    const box = document.createElement('div');
    box.id = 'allProjectsAudit'; box.className = 'audit-total-strip';
    tabs.insertAdjacentElement('afterend',box);
    return box;
  }
  function updateProfitRows(c){
    const tbody = $('resultTableBody'); if(!tbody) return;
    tbody.querySelectorAll('tr').forEach(row => {
      const th = row.querySelector('th'), td = row.querySelector('td');
      if(!th || !td) return;
      const label = (th.textContent || '').trim().toLowerCase();
      if(label.includes('pelnas nuo vieno darbuotojo') || label.includes('profit per worker')){
        setText(td,money(c.profit)); tone(td,c.profit);
      } else if(label === 'pelno marža' || label === 'profit margin' || label === 'marža' || label === 'margin'){
        setText(td,pct(c.margin)); tone(td,c.margin);
      } else if(label.includes('euroteams group įmonės pelnas') || label.includes('euroteams group company profit') || label === 'komandos pelnas' || label === 'team profit'){
        setText(td,money(c.teamProfit)); tone(td,c.teamProfit);
      }
    });
  }

  let applying = false;
  function applyCanonicalResults(){
    if(applying) return;
    const st = mainState();
    if(!st || !Array.isArray(st.scenarios) || !st.scenarios.length) return;
    applying = true;
    try {
      const tabs = [...($('scenarioTabs')?.querySelectorAll('.scenario-tab') || [])];
      let allRevenue = 0, allCost = 0, allProfit = 0;
      st.scenarios.forEach((scenario,index) => {
        const result = calculateScenario(scenario,index);
        allRevenue += result.teamRevenue; allCost += result.teamCost; allProfit += result.teamProfit;
        const p = tabs[index]?.querySelector('.scenario-profit strong');
        if(p){ setText(p,money(result.teamProfit)); tone(p,result.teamProfit); }
      });

      const active = Math.max(0,Math.min(Number(st.selected)||0,st.scenarios.length-1));
      const c = calculateScenario(st.scenarios[active],active);
      setText($('profitValue'),money(c.profit)); tone($('profitValue'),c.profit);
      setText($('teamProfit'),money(c.teamProfit)); tone($('teamProfit'),c.teamProfit);
      setText($('teamRevenue'),money(c.teamRevenue));
      setText($('teamCosts'),money(c.teamCost));
      setText($('marginValue'),pct(c.margin));
      setText($('totalCostValue'),money(c.workerTotal));
      setText($('salaryValue'),money(c.employeeShown));
      setText($('profitHourValue'),money(c.profitHour));
      setText($('breakevenValue'),money(c.breakEven) + (isEn() ? ' / h' : ' / val.'));
      updateProfitRows(c);

      const box = ensureTotals();
      if(box){
        const overallMargin = allRevenue ? allProfit / allRevenue * 100 : 0;
        const html = `<div><span>${tr('Visų projektų pajamos','All Projects Revenue')}</span><strong>${money(allRevenue)}</strong></div>`+
          `<div><span>${tr('Visų projektų savikaina','All Projects Cost')}</span><strong>${money(allCost)}</strong></div>`+
          `<div><span>${tr('Visų projektų pelnas','All Projects Profit')}</span><strong id="allProfitAudit">${money(allProfit)}</strong></div>`+
          `<div><span>${tr('Bendra marža','Overall Margin')}</span><strong>${pct(overallMargin)}</strong></div>`;
        if(box.innerHTML !== html) box.innerHTML = html;
        tone($('allProfitAudit'),allProfit);
      }
      window.__euroteamsCanonicalLast = {active,c,allRevenue,allCost,allProfit,at:new Date().toISOString()};
    } finally {
      applying = false;
    }
  }

  let scheduled = false;
  function scheduleCanonical(){
    if(scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(() => {
      scheduled = false;
      applyCanonicalResults();
    },0)));
  }

  document.addEventListener('input',scheduleCanonical,false);
  document.addEventListener('change',scheduleCanonical,false);
  document.addEventListener('click',e => {
    if(e.target.closest('#scenarioTabs,#modeHourly,#modeMonthly,#addBtn,#deleteBtn,#resetBtn,#ltBtn,#enBtn,#travelMonthlyBtn,#travelRotationBtn')) scheduleCanonical();
  },false);

  function observe(id){
    const el=$(id); if(!el) return;
    new MutationObserver(() => { if(!applying) scheduleCanonical(); }).observe(el,{subtree:true,childList:true,characterData:true});
  }
  ['profitValue','teamProfit','teamRevenue','teamCosts','marginValue','scenarioTabs','resultTableBody'].forEach(observe);

  function approx(a,b,t=0.02){ return Math.abs(a-b) <= t; }
  function regressionTests(){
    const baseScenario = {clientRate:27,hours:200,workers:1,costMode:'hourly',netRate:12.5,uplift:59,housing:0,travelMode:'monthly',travelMonthly:0,travelRotation:0,other:0,rotation:'6/2',workWeeks:6,homeWeeks:2};
    const noA1 = calculateScenario(baseScenario,999,{a1:false});
    const a1Included30 = calculateScenario(baseScenario,999,{a1:true,includePerDiemInNet:true,days:30,perDiemRate:64,pension2:false,applyNpd:false,employerRate:1.77});
    const a1Included20 = calculateScenario(baseScenario,999,{a1:true,includePerDiemInNet:true,days:20,perDiemRate:64,pension2:false,applyNpd:false,employerRate:1.77});
    const five = calculateScenario({...baseScenario,workers:5},999,{a1:true,includePerDiemInNet:true,days:30,perDiemRate:64,pension2:false,applyNpd:false,employerRate:1.77});
    const offAgain = calculateScenario(baseScenario,999,{a1:false});
    const secondScenario = calculateScenario({...baseScenario,clientRate:31},998,{a1:false});
    const serialized = JSON.parse(JSON.stringify(baseScenario));
    const reloaded = calculateScenario(serialized,999,{a1:false});
    const tests = [
      ['A: A1 off produces finite profit',Number.isFinite(noA1.profit)],
      ['B: A1 included changes profit',!approx(a1Included30.profit,noA1.profit)],
      ['C: changing posting days changes profit',!approx(a1Included30.profit,a1Included20.profit)],
      ['D1: workers do not change per-worker profit',approx(five.profit,a1Included30.profit)],
      ['D2: team profit scales by workers',approx(five.teamProfit,a1Included30.profit*5)],
      ['E: switching A1 off restores baseline',approx(offAgain.profit,noA1.profit)],
      ['F: separate scenario stays independent',!approx(secondScenario.profit,noA1.profit)],
      ['G: serialized/reloaded state stays stable',approx(reloaded.profit,noA1.profit)]
    ];
    window.__euroteamsCanonicalTests = {passed:tests.every(x=>x[1]),tests,checkedAt:new Date().toISOString()};
    if(!window.__euroteamsCanonicalTests.passed) console.warn('Euroteams canonical regression test failed',tests.filter(x=>!x[1]));
  }

  if(!document.querySelector('link[data-euroteams-audit-css]')){
    const link=document.createElement('link'); link.rel='stylesheet'; link.href='final-audit.css?v=20261014-3'; link.dataset.euroteamsAuditCss='1'; document.head.appendChild(link);
  }
  window.addEventListener('load',() => setTimeout(() => { regressionTests(); applyCanonicalResults(); },350));
  setTimeout(() => { regressionTests(); applyCanonicalResults(); },550);
})();
