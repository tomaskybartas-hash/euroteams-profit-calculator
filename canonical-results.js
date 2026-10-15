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
    const gpmBase = Math.max(0, gross - npd);
    const gpm = gpmBase * 0.20;
    const net = gross - sodra - pension - gpm;
    const employerTaxes = gross * (n(cfg.employerRate) / 100);
    return {gross,sodra,pension,npd,gpmBase,gpm,net,employerTaxes,payrollCost:gross + employerTaxes};
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
        fullyExempt:true, hourlyGross:hours ? base.gross / hours : 0
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
      fullyExempt, hourlyGross
    };
  }

  function solveIncluded(target, cfg, hours){
    target = n(target);
    const evaluate = gross => {
      const base = payrollFromGross(gross,cfg);
      return {base,post:posting(base,cfg,hours)};
    };
    if(!target) return evaluate(0);

    let lo = 0;
    let hi = Math.max(3000, target * 3 + n(cfg.perDiemRate) * n(cfg.days) + 1000);
    while(evaluate(hi).post.paidToEmployee < target) hi *= 2;
    for(let i=0;i<140;i++){
      const mid = (lo + hi) / 2;
      if(evaluate(mid).post.paidToEmployee < target) lo = mid; else hi = mid;
    }
    const a = evaluate(lo), b = evaluate(hi);
    const solved = Math.abs(a.post.paidToEmployee-target) <= Math.abs(b.post.paidToEmployee-target) ? a : b;
    solved.targetPayout = target;
    solved.payoutDifference = solved.post.paidToEmployee - target;
    return solved;
  }

  function travel(s){
    if((s.travelMode || 'monthly') !== 'rotation') return n(s.travelMonthly);
    let work = 6, home = 2;
    if(s.rotation === 'custom'){
      work = Math.max(1,n(s.workWeeks));
      home = n(s.homeWeeks);
    } else {
      const parts = String(s.rotation || '6/2').split('/').map(Number);
      work = parts[0] || 6;
      home = parts[1] || 2;
    }
    return n(s.travelRotation) * (4.345 / Math.max(1, work + home));
  }

  function calculateScenario(s, index, cfgOverride){
    const cfg = settingsFor(index, cfgOverride);
    const workers = Math.max(1, Math.round(n(s.workers) || 1));
    const hours = n(s.hours);
    const clientRate = n(s.clientRate);
    const revenue = clientRate * hours;
    const housing = n(s.housing);
    const travelCost = travel(s);
    const other = n(s.other);
    const localTransport = n(cfg.localTransport);
    const workwearTools = n(cfg.workwearTools);

    let workerTotal = 0;
    let employeeShown = 0;
    let base = null;
    let post = null;
    let payrollCostShown = 0;
    let employerContributionShown = 0;
    let legacyEmployerCost = 0;

    if((s.costMode || 'hourly') === 'monthly'){
      const target = n(s.monthlyPay);
      if(cfg.a1 && cfg.includePerDiemInNet){
        const solved = solveIncluded(target,cfg,hours);
        base = solved.base; post = solved.post;
      } else {
        base = grossFromNet(target,cfg);
        post = posting(base,cfg,hours);
      }
      payrollCostShown = base.payrollCost;
      employerContributionShown = base.employerTaxes + (cfg.a1 ? post.taxableEmployerTaxes : 0);
      workerTotal = (cfg.a1 ? post.payrollPostingCost : base.payrollCost)
        + housing + travelCost + other + localTransport + workwearTools;
      employeeShown = cfg.a1 && cfg.includePerDiemInNet ? post.paidToEmployee : base.net;
    } else if(cfg.a1){
      const target = n(s.netRate) * hours;
      if(cfg.includePerDiemInNet){
        const solved = solveIncluded(target,cfg,hours);
        base = solved.base; post = solved.post;
      } else {
        base = grossFromNet(target,cfg);
        post = posting(base,cfg,hours);
      }
      payrollCostShown = base.payrollCost;
      employerContributionShown = base.employerTaxes + post.taxableEmployerTaxes;
      workerTotal = post.payrollPostingCost + housing + travelCost + other + localTransport + workwearTools;
      employeeShown = cfg.includePerDiemInNet ? post.paidToEmployee : base.net;
    } else {
      const salary = n(s.netRate) * hours;
      legacyEmployerCost = salary * (1 + n(s.uplift) / 100);
      payrollCostShown = legacyEmployerCost;
      employerContributionShown = Math.max(0,legacyEmployerCost - salary);
      workerTotal = legacyEmployerCost + housing + travelCost + other;
      employeeShown = salary;
    }

    const logistics = housing + travelCost;
    const projectExtras = other + localTransport + workwearTools;
    const profit = revenue - workerTotal;
    const margin = revenue ? profit / revenue * 100 : 0;

    return {
      workers,hours,clientRate,revenue,workerTotal,profit,margin,
      profitHour:hours ? profit / hours : 0,
      breakEven:hours ? workerTotal / hours : 0,
      teamRevenue:revenue * workers,
      teamCost:workerTotal * workers,
      teamProfit:profit * workers,
      employeeShown,payrollCostShown,employerContributionShown,
      housing,travelCost,logistics,other,localTransport,workwearTools,projectExtras,
      legacyEmployerCost,base,post,cfg
    };
  }

  window.EuroteamsCalculator = Object.freeze({
    calculateScenario,
    payrollFromGross,
    grossFromNet,
    posting,
    solveIncluded,
    travel
  });

  function tone(el,value){
    if(!el) return;
    el.classList.remove('audit-positive','audit-negative','audit-neutral','green','red');
    el.classList.add(value > 0.005 ? 'audit-positive' : value < -0.005 ? 'audit-negative' : 'audit-neutral');
  }
  function setText(el,text){
    if(el && el.textContent !== text) el.textContent = text;
  }
  function metricLabel(valueId){
    return $(valueId)?.closest('.metric')?.querySelector('span') || null;
  }
  function ensureTotals(){
    if($('allProjectsAudit')) return $('allProjectsAudit');
    const tabs = $('scenarioTabs');
    if(!tabs) return null;
    const box = document.createElement('div');
    box.id = 'allProjectsAudit';
    box.className = 'audit-total-strip';
    tabs.insertAdjacentElement('afterend',box);
    return box;
  }

  function updateTopLabels(c){
    setText(metricLabel('revenueValue'),tr('Kliento pajamos','Client Revenue'));
    setText(metricLabel('salaryValue'),c.cfg.a1 && c.cfg.includePerDiemInNet
      ? tr('Bendra darbuotojui išmokama suma','Total Paid to Employee')
      : tr('Darbuotojo NETO atlyginimas','Employee Net Salary'));
    setText(metricLabel('employerValue'),c.cfg.a1
      ? tr('DU savikaina įmonei','Employment Cost to Company')
      : tr('Darbuotojo savikaina prieš logistiką','Employee Cost Before Logistics'));
    setText(metricLabel('logisticsValue'),tr('Logistikos išlaidos','Logistics Costs'));
    setText(metricLabel('extraEmployerValue'),c.cfg.a1
      ? tr('Darbdavio socialinės įmokos','Employer Social Security Contributions')
      : tr('Papildomos darbdavio išlaidos','Additional Employer Costs'));
    setText(metricLabel('allocatedTravelValue'),tr('Kelionės / mėn.','Travel / Month'));
    setText(metricLabel('otherValue'),tr('Kitos projekto išlaidos','Other Project Costs'));
    setText(metricLabel('totalCostValue'),tr('Bendra darbuotojo savikaina','Total Employee Cost'));
    setText(metricLabel('breakevenValue'),tr('Kliento tarifas be pelno ir nuostolio','Break-Even Client Rate'));

    const bigLabel = document.querySelector('.big-label');
    if(bigLabel) setText(bigLabel,tr('Pelnas nuo vieno darbuotojo / mėn.','Profit per Worker / Month'));
    const teamProfitLabel = $('teamProfit')?.closest('.team-cell')?.querySelector('span');
    if(teamProfitLabel) setText(teamProfitLabel,tr('Euroteams Group įmonės pelnas','Euroteams Group Company Profit'));
  }

  function updateProfitRows(c){
    const tbody = $('resultTableBody');
    if(!tbody) return;
    tbody.querySelectorAll('tr').forEach(row => {
      const th = row.querySelector('th');
      const td = row.querySelector('td');
      if(!th || !td) return;
      const label = (th.textContent || '').trim().toLowerCase();
      if(label.includes('pelnas nuo vieno darbuotojo') || label.includes('profit per worker')){
        setText(td,money(c.profit)); tone(td,c.profit);
      } else if(label === 'pelno marža' || label === 'profit margin' || label === 'marža' || label === 'margin'){
        setText(td,pct(c.margin)); tone(td,c.margin);
      } else if(label.includes('euroteams group įmonės pelnas') || label.includes('euroteams group company profit') || label === 'komandos pelnas' || label === 'team profit'){
        setText(td,money(c.teamProfit)); tone(td,c.teamProfit);
      } else if(label.includes('bendra darbuotojo savikaina') || label.includes('total employee cost') || label.includes('visos išlaidos / darbuotojui') || label.includes('total costs / worker')){
        setText(td,money(c.workerTotal));
      } else if(label.includes('pajamos iš kliento / nuo darbuotojo') || label.includes('client revenue / worker')){
        setText(td,money(c.revenue));
      }
    });
  }

  function applyCanonicalResults(){
    const st = mainState();
    if(!st || !Array.isArray(st.scenarios) || !st.scenarios.length) return;

    const tabs = [...($('scenarioTabs')?.querySelectorAll('.scenario-tab') || [])];
    let allRevenue = 0;
    let allCost = 0;
    let allProfit = 0;

    st.scenarios.forEach((scenario,index) => {
      const result = calculateScenario(scenario,index);
      allRevenue += result.teamRevenue;
      allCost += result.teamCost;
      allProfit += result.teamProfit;
      const p = tabs[index]?.querySelector('.scenario-profit strong');
      if(p){ setText(p,money(result.teamProfit)); tone(p,result.teamProfit); }
    });

    const active = Math.max(0,Math.min(Number(st.selected)||0,st.scenarios.length-1));
    const c = calculateScenario(st.scenarios[active],active);

    updateTopLabels(c);
    setText($('revenueValue'),money(c.revenue));
    setText($('salaryValue'),money(c.employeeShown));
    setText($('employerValue'),money(c.payrollCostShown));
    setText($('logisticsValue'),money(c.logistics));
    setText($('extraEmployerValue'),money(c.employerContributionShown));
    setText($('allocatedTravelValue'),money(c.travelCost));
    setText($('otherValue'),money(c.projectExtras));
    setText($('totalCostValue'),money(c.workerTotal));
    setText($('profitValue'),money(c.profit)); tone($('profitValue'),c.profit);
    setText($('marginValue'),pct(c.margin)); tone($('marginValue'),c.margin);
    setText($('profitHourValue'),money(c.profitHour)); tone($('profitHourValue'),c.profitHour);
    setText($('breakevenValue'),money(c.breakEven) + (isEn() ? ' / h' : ' / val.'));
    setText($('teamRevenue'),money(c.teamRevenue));
    setText($('teamCosts'),money(c.teamCost));
    setText($('teamProfit'),money(c.teamProfit)); tone($('teamProfit'),c.teamProfit);
    updateProfitRows(c);

    const box = ensureTotals();
    if(box){
      const overallMargin = allRevenue ? allProfit / allRevenue * 100 : 0;
      box.innerHTML =
        `<div><span>${tr('Visų projektų pajamos','All Projects Revenue')}</span><strong>${money(allRevenue)}</strong></div>`+
        `<div><span>${tr('Visų projektų savikaina','All Projects Cost')}</span><strong>${money(allCost)}</strong></div>`+
        `<div><span>${tr('Visų projektų pelnas','All Projects Profit')}</span><strong id="allProfitAudit">${money(allProfit)}</strong></div>`+
        `<div><span>${tr('Bendra marža','Overall Margin')}</span><strong>${pct(overallMargin)}</strong></div>`;
      tone($('allProfitAudit'),allProfit);
    }

    window.__euroteamsCanonicalLast = {active,c,allRevenue,allCost,allProfit,at:new Date().toISOString()};
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
  window.addEventListener('storage',scheduleCanonical);
  window.addEventListener('euroteams:recalculate',scheduleCanonical);

  function approx(a,b,t=0.02){ return Math.abs(a-b) <= t; }
  function regressionTests(){
    const cfgBase = {...DEFAULTS,pension2:false,applyNpd:false,employerRate:1.77};
    const p1 = grossFromNet(2300,cfgBase);
    const p2 = grossFromNet(2300,{...cfgBase,pension2:true});
    const p3post = posting(p1,{...cfgBase,a1:true,includePerDiemInNet:false,days:30,perDiemRate:64},200);

    const baseScenario = {
      clientRate:27,hours:200,workers:1,costMode:'hourly',netRate:12.5,uplift:59,
      housing:0,travelMode:'monthly',travelMonthly:0,travelRotation:0,other:0,
      rotation:'6/2',workWeeks:6,homeWeeks:2
    };
    const noA1 = calculateScenario(baseScenario,999,{a1:false});
    const a1Included30 = calculateScenario(baseScenario,999,{...cfgBase,a1:true,includePerDiemInNet:true,days:30,perDiemRate:64});
    const a1Included20 = calculateScenario(baseScenario,999,{...cfgBase,a1:true,includePerDiemInNet:true,days:20,perDiemRate:64});
    const five = calculateScenario({...baseScenario,workers:5},999,{...cfgBase,a1:true,includePerDiemInNet:true,days:30,perDiemRate:64});
    const secondScenario = calculateScenario({...baseScenario,clientRate:31},998,{a1:false});
    const reloaded = calculateScenario(JSON.parse(JSON.stringify(baseScenario)),999,{a1:false});

    const tests = [
      ['Payroll 1 gross',approx(p1.gross,3801.65)],
      ['Payroll 1 employee social',approx(p1.sodra,741.32)],
      ['Payroll 1 GPM',approx(p1.gpm,760.33)],
      ['Payroll 1 NET',approx(p1.net,2300)],
      ['Payroll 1 employer social',approx(p1.employerTaxes,67.29)],
      ['Payroll 1 employment cost',approx(p1.payrollCost,3868.94)],
      ['Payroll 2 gross',approx(p2.gross,4000)],
      ['Payroll 2 employee social',approx(p2.sodra,780)],
      ['Payroll 2 pension',approx(p2.pension,120)],
      ['Payroll 2 GPM',approx(p2.gpm,800)],
      ['Payroll 2 employment cost',approx(p2.payrollCost,4070.80)],
      ['Payroll 3 total per diem',approx(p3post.totalPerDiem,1920)],
      ['Payroll 3 tax-free per diem',approx(p3post.exemptPerDiem,1920)],
      ['Payroll 3 total paid',approx(p3post.paidToEmployee,4220)],
      ['Payroll 3 payroll + per diem cost',approx(p3post.payrollPostingCost,5788.94)],
      ['A: A1 off finite profit',Number.isFinite(noA1.profit)],
      ['B: A1 included changes profit',!approx(a1Included30.profit,noA1.profit)],
      ['C: posting days 30→20 changes profit',!approx(a1Included30.profit,a1Included20.profit)],
      ['D1: worker count does not change per-worker profit',approx(five.profit,a1Included30.profit)],
      ['D2: team profit scales ×5',approx(five.teamProfit,a1Included30.profit*5)],
      ['E: A1 off returns baseline',approx(calculateScenario(baseScenario,999,{a1:false}).profit,noA1.profit)],
      ['F: scenarios stay independent',!approx(secondScenario.profit,noA1.profit)],
      ['G: serialized state stays stable',approx(reloaded.profit,noA1.profit)]
    ];

    window.__euroteamsCanonicalTests = {
      passed:tests.every(x=>x[1]),
      tests,
      checkedAt:new Date().toISOString()
    };
    if(!window.__euroteamsCanonicalTests.passed){
      console.warn('Euroteams canonical regression test failed',tests.filter(x=>!x[1]));
    }
    return window.__euroteamsCanonicalTests.passed;
  }

  if(!document.querySelector('link[data-euroteams-audit-css]')){
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'final-audit.css?v=20261015-1';
    link.dataset.euroteamsAuditCss = '1';
    document.head.appendChild(link);
  }

  window.addEventListener('load',() => setTimeout(() => {
    regressionTests();
    applyCanonicalResults();
  },350));
  setTimeout(() => {
    regressionTests();
    applyCanonicalResults();
  },550);
})();
