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
    perDiemRate:64, taxMode:'monthly',taxResident:true,otherAnnualIncome:0,priorSocialIncome:0,floorBase:1153,wageBasis:'monthly',contractWage:0,shortDays:0,customCountryLimit:0
  });

  const $ = id => document.getElementById(id);
  const n = value => Number.isFinite(Number(value)) ? Math.max(0, Number(value)) : 0;
  const isEn = () => $('enBtn')?.classList.contains('active');
  const tr = (lt,en) => isEn() ? en : lt;
  const money = value => new Intl.NumberFormat(isEn() ? 'en-GB' : 'lt-LT', {
    style:'currency', currency:'EUR', minimumFractionDigits:2, maximumFractionDigits:2
  }).format(Number(Number(value).toPrecision(14)) || 0);
  const pct = value => new Intl.NumberFormat(isEn() ? 'en-GB' : 'lt-LT', {
    minimumFractionDigits:2, maximumFractionDigits:2
  }).format(Number(Number(value).toPrecision(14)) || 0) + ' %';

  function mainState(){
    try { return JSON.parse(window.EuroteamsStorage.getItem(MAIN_KEY) || 'null'); }
    catch { return null; }
  }
  function payrollState(){
    try { return JSON.parse(window.EuroteamsStorage.getItem(PAYROLL_KEY) || '{}') || {}; }
    catch { return {}; }
  }
  function settingsFor(index, override){
    return {...DEFAULTS, ...(payrollState()[String(index)] || {}), ...(override || {})};
  }

  const payrollFromGross=(gross,cfg)=>window.EuroteamsTax2026.payroll(gross,cfg);
  const grossFromNet=(target,cfg)=>window.EuroteamsTax2026.fromNet(target,cfg);
  const posting=(base,cfg,hours)=>window.EuroteamsTax2026.posting(base,cfg,hours);

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
      workerTotal = legacyEmployerCost + housing + travelCost + other + localTransport + workwearTools;
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
    setText(metricLabel('employerValue'),c.base
      ? tr('DU savikaina įmonei','Employment Cost to Company')
      : tr('Darbuotojo savikaina prieš logistiką','Employee Cost Before Logistics'));
    setText(metricLabel('logisticsValue'),tr('Logistikos išlaidos','Logistics Costs'));
    setText(metricLabel('extraEmployerValue'),c.base
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

  function detailRows(c){
    const b=c.base,p=c.post, rows=[];
    if(b){
      rows.push([tr('Darbuotojo NETO atlyginimas (be dienpinigių)','Employee net salary (excluding allowance)'),b.net],
        [tr('Bruto atlyginimas','Gross salary'),b.gross],
        [tr('Darbuotojo socialinės įmokos nuo DU','Employee social security on salary'),b.sodra],
        [tr('GPM nuo DU','Income tax on salary'),b.gpm],
        [tr('Pensijų kaupimas nuo DU','Pension contribution on salary'),b.pension],
        [tr('Darbdavio socialinės įmokos nuo DU','Employer social security on salary'),b.employerTaxes],
        [tr('Darbdavio primoka iki įmokų grindų','Employer-funded minimum contribution top-up'),b.floorCost],[tr('DU savikaina įmonei','Total payroll cost'),b.payrollCost]);
      if(c.cfg.a1) rows.push(
        [tr('Bendra dienpinigių suma','Total daily allowance'),p.totalPerDiem],
        [tr('Neapmokestinami dienpinigiai','Tax-free daily allowance'),p.exemptPerDiem],
        [tr('Apmokestinami dienpinigiai (bruto)','Taxable daily allowance (gross)'),p.taxablePerDiem],
        [tr('Darbuotojo mokesčiai nuo dienpinigių','Employee taxes on daily allowance'),p.taxablePerDiem-p.taxablePerDiemNet],
        [tr('Darbdavio įmokos nuo dienpinigių','Employer contributions on daily allowance'),p.taxableEmployerTaxes],
        [tr('Įmokų grindų primokos pokytis dėl dienpinigių','Minimum contribution top-up adjustment'),p.floorAdjustment],[tr('Apmokestintų dienpinigių NETO dalis','Taxable daily allowance after tax'),p.taxablePerDiemNet],
        [tr('Bendra darbuotojui išmokama suma','Total paid to employee'),p.paidToEmployee],
        [tr('DU ir dienpinigių savikaina','Payroll and daily allowance cost'),p.payrollPostingCost]);
    }else rows.push([tr('Darbuotojo NETO atlyginimas','Employee net salary'),c.employeeShown],[tr('Darbuotojo savikaina prieš logistiką','Employee cost before logistics'),c.payrollCostShown]);
    return rows;
  }
  function updateProfitRows(c){
    const tbody=$('resultTableBody');if(!tbody)return;
    const focusedWorker=document.activeElement===$('tableWorkers')?$('tableWorkers'):null;
    const row=(label,value)=>`<tr><th scope="row">${label}</th><td>${money(value)}</td></tr>`;
    tbody.innerHTML=`<tr><th scope="row">${tr('Darbuotojų skaičius','Number of workers')}</th><td><input id="tableWorkers" aria-label="${tr('Darbuotojų skaičius','Number of workers')}" type="number" min="1" step="1" value="${c.workers}" style="max-width:120px"></td></tr>`+
      [[tr('Kliento pajamos / darbuotojui','Client revenue per worker'),c.revenue],...detailRows(c),
      [tr('Apgyvendinimas','Accommodation'),c.housing],[tr('Kelionės','Travel'),c.travelCost],
      [tr('Vietinis transportas','Local transport'),c.localTransport],[tr('Darbo rūbai / įrankiai','Workwear / tools'),c.workwearTools],
      [tr('Kitos išlaidos','Other costs'),c.other],[tr('Bendra darbuotojo savikaina','Total employee cost'),c.workerTotal],
      [tr('Pelnas nuo vieno darbuotojo','Profit per worker'),c.profit],[tr('Pelnas už valandą','Profit per hour'),c.profitHour],
      [tr('Tarifas be pelno ir nuostolio','Break-even client rate'),c.breakEven],
      [tr('Komandos pajamos','Team revenue'),c.teamRevenue],[tr('Komandos savikaina','Team cost'),c.teamCost],
      [tr('Komandos pelnas','Team profit'),c.teamProfit]].map(([label,value])=>row(label,value)).join('')+
      `<tr><th scope="row">${tr('Pelno marža','Profit margin')}</th><td>${pct(c.margin)}</td></tr>`;
    if(focusedWorker){$('tableWorkers').replaceWith(focusedWorker);focusedWorker.focus();}
    $('tableWorkers').oninput=e=>{ $('workers').value=e.target.value;$('workers').dispatchEvent(new Event('input',{bubbles:true})); };
    for(const row of tbody.rows){const label=row.cells[0].textContent;if(/Pelnas|pelnas|profit|margin|marža/i.test(label)&&!/Tarifas|rate/.test(label))tone(row.cells[1],/margin|marža/i.test(label)?c.margin:/valandą|per hour/i.test(label)?c.profitHour:c.profit);}
    const detail=$('payrollBreakdown');if(detail)detail.innerHTML=detailRows(c).map(([label,value])=>`<div class="metric"><span>${label}</span><strong>${money(value)}</strong></div>`).join('');
    if(c.base&&$('monthlyEmployer'))$('monthlyEmployer').value=c.base.payrollCost.toFixed(2);
    const status=$('a1Status');
    if(status){
      const target=(mainState().scenarios[mainState().selected].costMode==='monthly'?n($('monthlyPay').value):n($('netRate').value)*c.hours);
      const difference=c.cfg.a1&&c.cfg.includePerDiemInNet?c.post.paidToEmployee-target:0;
      status.textContent=Math.abs(difference)>.01
        ? tr('Įvestos NETO sumos su šiais dienpinigiais tiksliai pasiekti negalima. Apskaičiuota išmoka: ','The entered net payout cannot be reached exactly with these allowances. Calculated payout: ')+money(c.post.paidToEmployee)
        : c.cfg.a1?tr('Neapmokestinami dienpinigiai: ','Tax-free daily allowance: ')+money(c.post.exemptPerDiem)+tr(' · Apmokestinami: ',' · Taxable: ')+money(c.post.taxablePerDiem):'';
      status.className=Math.abs(difference)>.01?'calculation-warning':'help';
    }
    setText($('employerHelp'),c.base?tr('Bruto DU + darbdavio įmokos ir grindų primoka; dienpinigiai atskirai.','Gross salary + employer contributions and minimum top-up; allowance is separate.'):tr('NETO atlyginimas + įvestas papildomų išlaidų procentas.','Net salary + entered additional cost percentage.'));
    const salaryHelp=$('salaryValue')?.closest('.metric')?.querySelector('small');
    setText(salaryHelp,c.cfg.a1&&c.cfg.includePerDiemInNet?tr('NETO DU + neapmokestinami ir apmokestinti dienpinigiai.','Net salary + tax-free and after-tax daily allowance.'):tr('Darbuotojo NETO atlyginimas be dienpinigių.','Employee net salary excluding daily allowance.'));
    const warnings=$('scenarioWarning');
    if(warnings)warnings.innerHTML='<ul>'+[
      !c.housing?tr('Apgyvendinimo išlaidos neįtrauktos arba jas apmoka klientas.','Accommodation costs are excluded or paid by the client.'):null,
      !c.travelCost?tr('Kelionės išlaidos neįtrauktos arba jas apmoka klientas.','Travel costs are excluded or paid by the client.'):null,
      tr('Pelnas prieš pelno mokestį ir neįvestas išlaidas.','Profit before corporate tax and costs not entered.'),
      c.cfg.a1&&!n(c.cfg.contractWage)?tr('Dienpinigių lengvatai naudojamas apskaičiuotas DU. Sutikrinkite sutartinį atlyginimą, A1 galiojimą ir GPM apmokestinimo valstybę.','Allowance relief uses calculated pay. Verify contractual pay, A1 validity and the country entitled to tax wages.'):null,
      c.cfg.a1&&c.post.maximum>0&&n(c.cfg.perDiemRate)<c.post.maximum?tr('Sumažinta dienpinigių norma turi būti pagrįsta: kolektyvinėje sutartyje bent 50 %, vidaus tvarkoje bent 65 % ir komandiruotė bent 7 dienų.','A reduced daily rate needs a valid basis: at least 50% under a collective agreement, or 65% under internal rules for trips lasting at least 7 days.'):null,
      c.cfg.a1&&c.cfg.country==='OTHER'&&!n(c.cfg.customCountryLimit)?tr('Kitai šaliai neįvesta patikrinta neapmokestinama dienos riba: dienpinigiai laikomi apmokestinamais.','No verified tax-free daily limit for Other country: allowances are treated as taxable.'):null,
      c.base?(c.cfg.taxMode==='annualAverage'?tr('Metinis vidurkis: 12 vienodų mėnesių, 20/25/32 % GPM ir VSD lubos. Tai ne faktinio mėnesio algalapis.','Annual average: 12 identical months, progressive tax and VSD cap. This is not an actual monthly payslip.'):tr('Mėnesio modelis: GPM 20 %. Metų pradžios draudžiamosios pajamos ir įmokų grindų bazė yra įvedamos prielaidos.','Monthly model: 20% income tax. Prior insured income and minimum contribution base are entered assumptions.')):tr('Darbdavio išlaidų procentas yra planavimo prielaida.','The employer cost percentage is a planning assumption.')
    ].filter(Boolean).map(x=>'<li>'+x+'</li>').join('')+'</ul>';
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

  window.applyEuroteamsResults=applyCanonicalResults;
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
    link.href = 'final-audit.css?v=20261015-examples1';
    link.dataset.euroteamsAuditCss = '1';
    document.head.appendChild(link);
  }

  regressionTests();
  applyCanonicalResults();
})();
