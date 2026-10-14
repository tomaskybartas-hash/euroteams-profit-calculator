(() => {
  const MAIN_KEY = 'euroteams-profit-calculator-v3';
  const PAYROLL_KEY = 'euroteams-payroll-2026-v4';
  const $ = id => document.getElementById(id);
  const n = v => Math.max(0, Number(v) || 0);
  const isEn = () => $('enBtn')?.classList.contains('active');
  const tr = (lt,en) => isEn() ? en : lt;
  const money = v => new Intl.NumberFormat(isEn() ? 'en-GB' : 'lt-LT', {style:'currency',currency:'EUR',minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(v)||0);
  const pct = v => new Intl.NumberFormat(isEn() ? 'en-GB' : 'lt-LT', {minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(v)||0) + ' %';
  const DEFAULTS = {pension2:false,applyNpd:false,employerRate:1.77,localTransport:0,workwearTools:0,a1:false,includePerDiemInNet:true,country:'NL',days:30,perDiemRate:64};

  function mainState(){ try{return JSON.parse(localStorage.getItem(MAIN_KEY)||'null')}catch(e){return null} }
  function payrollAll(){ try{return JSON.parse(localStorage.getItem(PAYROLL_KEY)||'{}')||{}}catch(e){return {}} }
  function cfgFor(i){ return {...DEFAULTS,...(payrollAll()[String(i)]||{})}; }
  function npdForGross(gross, apply){ if(!apply)return 0; if(gross<=1153)return 747; return Math.max(0,747-0.49*(gross-1153)); }
  function payrollFromGross(gross,cfg){
    gross=n(gross); const sodra=gross*0.195, pension=cfg.pension2?gross*0.03:0, npd=npdForGross(gross,cfg.applyNpd), gpm=Math.max(0,gross-npd)*0.20;
    const net=gross-sodra-pension-gpm, employerTaxes=gross*(n(cfg.employerRate)/100);
    return {gross,sodra,pension,npd,gpm,net,employerTaxes,payrollCost:gross+employerTaxes};
  }
  function grossFromNet(target,cfg){
    target=n(target); if(!target)return payrollFromGross(0,cfg);
    if(!cfg.applyNpd){ const d=1-0.195-(cfg.pension2?0.03:0)-0.20; return payrollFromGross(target/d,cfg); }
    let lo=0,hi=Math.max(2000,target*3+1000); while(payrollFromGross(hi,cfg).net<target)hi*=2;
    for(let i=0;i<120;i++){const m=(lo+hi)/2; payrollFromGross(m,cfg).net<target?lo=m:hi=m;}
    return payrollFromGross((lo+hi)/2,cfg);
  }
  function posting(base,cfg,hours){
    if(!cfg.a1) return {totalPerDiem:0,exemptPerDiem:0,taxablePerDiem:0,taxablePerDiemNet:0,taxableEmployerTaxes:0,totalSodra:base.sodra,totalPension:base.pension,totalGpm:base.gpm,paidToEmployee:base.net,payrollPostingCost:base.payrollCost,fullyExempt:true};
    const totalPerDiem=n(cfg.perDiemRate)*n(cfg.days), hourlyGross=hours?base.gross/hours:0;
    const fullyExempt=base.gross>=1902.45 || hourlyGross>=11.6325;
    const exemptPerDiem=Math.min(totalPerDiem, fullyExempt?totalPerDiem:base.gross*0.5);
    const taxablePerDiem=Math.max(0,totalPerDiem-exemptPerDiem), combined=payrollFromGross(base.gross+taxablePerDiem,cfg);
    const extraSodra=Math.max(0,combined.sodra-base.sodra), extraPension=Math.max(0,combined.pension-base.pension), extraGpm=Math.max(0,combined.gpm-base.gpm);
    const taxablePerDiemNet=Math.max(0,taxablePerDiem-extraSodra-extraPension-extraGpm), taxableEmployerTaxes=taxablePerDiem*(n(cfg.employerRate)/100);
    return {totalPerDiem,exemptPerDiem,taxablePerDiem,taxablePerDiemNet,taxableEmployerTaxes,totalSodra:combined.sodra,totalPension:combined.pension,totalGpm:combined.gpm,paidToEmployee:base.net+exemptPerDiem+taxablePerDiemNet,payrollPostingCost:base.payrollCost+totalPerDiem+taxableEmployerTaxes,fullyExempt};
  }
  function solveIncluded(target,cfg,hours){
    target=n(target); if(!target){const base=payrollFromGross(0,cfg);return {base,post:posting(base,cfg,hours)}}
    const evalGross=g=>{const base=payrollFromGross(g,cfg);return {base,post:posting(base,cfg,hours)}};
    let lo=0,hi=Math.max(3000,target*3+n(cfg.perDiemRate)*n(cfg.days)+1000); while(evalGross(hi).post.paidToEmployee<target)hi*=2;
    for(let i=0;i<140;i++){const m=(lo+hi)/2; evalGross(m).post.paidToEmployee<target?lo=m:hi=m;}
    const a=evalGross(lo),b=evalGross(hi); return Math.abs(a.post.paidToEmployee-target)<=Math.abs(b.post.paidToEmployee-target)?a:b;
  }
  function travel(s){
    if((s.travelMode||'monthly')!=='rotation')return n(s.travelMonthly);
    let w=6,h=2; if(s.rotation==='custom'){w=Math.max(1,n(s.workWeeks));h=n(s.homeWeeks)} else {const p=String(s.rotation||'6/2').split('/').map(Number);w=p[0]||6;h=p[1]||2}
    return n(s.travelRotation)*(4.345/Math.max(1,w+h));
  }
  function calcScenario(s,i){
    const workers=Math.max(1,Math.round(n(s.workers)||1)),hours=n(s.hours),revenue=n(s.clientRate)*hours,cfg=cfgFor(i);
    let workerTotal, employeeShown, base=null, post=null;
    if((s.costMode||'hourly')==='monthly'){
      const target=n(s.monthlyPay);
      if(cfg.a1&&cfg.includePerDiemInNet){const x=solveIncluded(target,cfg,hours);base=x.base;post=x.post}else{base=grossFromNet(target,cfg);post=posting(base,cfg,hours)}
      workerTotal=(cfg.a1?post.payrollPostingCost:base.payrollCost)+n(s.housing)+travel(s)+n(s.other)+n(cfg.localTransport)+n(cfg.workwearTools);
      employeeShown=cfg.a1&&cfg.includePerDiemInNet?post.paidToEmployee:base.net;
    } else {
      const salary=n(s.netRate)*hours, employer=salary*(1+n(s.uplift)/100);
      workerTotal=employer+n(s.housing)+travel(s)+n(s.other); employeeShown=salary;
    }
    const profit=revenue-workerTotal, margin=revenue?profit/revenue*100:0;
    return {workers,hours,revenue,workerTotal,profit,margin,teamRevenue:revenue*workers,teamCost:workerTotal*workers,teamProfit:profit*workers,employeeShown,base,post,cfg};
  }

  function tone(el,value){ if(!el)return; el.classList.remove('audit-positive','audit-negative','audit-neutral'); el.classList.add(value>0.005?'audit-positive':value<-0.005?'audit-negative':'audit-neutral'); }
  function ensureTotals(){
    if($('allProjectsAudit'))return;
    const tabs=$('scenarioTabs'); if(!tabs)return;
    const box=document.createElement('div'); box.id='allProjectsAudit'; box.className='audit-total-strip'; tabs.insertAdjacentElement('afterend',box);
  }
  function setLabels(){
    const metrics=[...document.querySelectorAll('.metrics .metric > span')];
    const replacements=isEn()?{
      'Worker pay':'Employee Net Salary','Estimated employer cost':'Employment Cost to Company','Total entered costs':'Total Employee Cost','Margin':'Profit Margin'
    }:{
      'Darbuotojo atlyginimas':'Darbuotojo NETO atlyginimas','Numatoma darbuotojo kaina įmonei':'DU savikaina įmonei','Visos įvestos išlaidos':'Bendra darbuotojo savikaina','Marža':'Pelno marža'
    };
    metrics.forEach(el=>{const k=(el.textContent||'').trim(); if(replacements[k])el.textContent=replacements[k]});
    const title=document.querySelector('.results-table-card h2'); if(title) title.textContent=tr('Pasirinkto projekto rezultatai','Selected Project Results');
    const badge=document.querySelector('.badge'); if(badge) badge.textContent=tr('Numatomas pelnas','Projected Profit');
  }
  function validateInputs(){
    ['clientRate','hours','netRate','uplift','monthlyPay','monthlyEmployer','housing','travelMonthly','travelRotation','other','workWeeks','homeWeeks','employerRate2026','postingDays','postingRate','localTransport2026','workwearTools2026'].forEach(id=>{const el=$(id);if(el&&el.type==='number')el.min='0'});
    if($('workers'))$('workers').min='1';
  }
  function syncScenarioTabs(){
    const st=mainState(); if(!st||!Array.isArray(st.scenarios))return;
    const tabs=[...($('scenarioTabs')?.querySelectorAll('.scenario-tab')||[])];
    let allRev=0,allCost=0,allProfit=0;
    st.scenarios.forEach((s,i)=>{
      const c=calcScenario(s,i); allRev+=c.teamRevenue; allCost+=c.teamCost; allProfit+=c.teamProfit;
      const p=tabs[i]?.querySelector('.scenario-profit strong'); if(p){p.textContent=money(c.teamProfit);tone(p,c.teamProfit)}
    });
    ensureTotals(); const box=$('allProjectsAudit'); if(box){
      const m=allRev?allProfit/allRev*100:0;
      box.innerHTML=`<div><span>${tr('Visų projektų pajamos','All Projects Revenue')}</span><strong>${money(allRev)}</strong></div><div><span>${tr('Visų projektų savikaina','All Projects Cost')}</span><strong>${money(allCost)}</strong></div><div><span>${tr('Visų projektų pelnas','All Projects Profit')}</span><strong id="allProfitAudit">${money(allProfit)}</strong></div><div><span>${tr('Bendra marža','Overall Margin')}</span><strong>${pct(m)}</strong></div>`;
      tone($('allProfitAudit'),allProfit);
    }
  }
  function syncActive(){
    const st=mainState(); if(!st||!Array.isArray(st.scenarios))return;
    const i=Math.max(0,Math.min(Number(st.selected)||0,st.scenarios.length-1)),c=calcScenario(st.scenarios[i],i);
    tone($('profitValue'),c.profit); tone($('teamProfit'),c.teamProfit);
    const mainProfit=$('profitValue'),teamProfit=$('teamProfit'); if(mainProfit)mainProfit.textContent=money(c.profit); if(teamProfit)teamProfit.textContent=money(c.teamProfit);
    if($('marginValue'))$('marginValue').textContent=pct(c.margin);
    if($('teamRevenue'))$('teamRevenue').textContent=money(c.teamRevenue);
    if($('teamCosts'))$('teamCosts').textContent=money(c.teamCost);
    if($('totalCostValue'))$('totalCostValue').textContent=money(c.workerTotal);
    if($('salaryValue'))$('salaryValue').textContent=money(c.employeeShown);
  }
  function syncTerminology(){
    const tbody=$('resultTableBody'); if(!tbody)return;
    const map=isEn()?new Map([
      ['NET salary','Employee Net Salary'],['Gross salary','Gross Salary'],['Employee social insurance','Employee Social Security Contributions'],['Employer social contributions','Employer Social Security Contributions'],['Payroll cost to company','Employment Cost to Company'],['Tax-exempt per diem','Tax-Free Daily Allowance'],['Taxable per diem','Taxable Daily Allowance'],['Total employee project cost','Total Employee Cost'],['Profit margin','Profit Margin'],['Per diem','Total Daily Allowance']
    ]):new Map([
      ['NETO darbo užmokestis','Darbuotojo NETO atlyginimas'],['Darbuotojo Sodra','Darbuotojo socialinės įmokos'],['Darbdavio socialinės įmokos','Darbdavio socialinės įmokos'],['Visa darbuotojo savikaina','Bendra darbuotojo savikaina'],['Pelno marža','Pelno marža']
    ]);
    tbody.querySelectorAll('th').forEach(th=>{const k=(th.textContent||'').trim();if(map.has(k))th.textContent=map.get(k)});
  }
  function sync(){ setLabels(); validateInputs(); syncActive(); syncScenarioTabs(); syncTerminology(); }

  let deleteIndex=null;
  document.addEventListener('pointerdown',e=>{if(e.target.closest('#deleteBtn')){const st=mainState();deleteIndex=st?Number(st.selected)||0:null}},true);
  document.addEventListener('click',e=>{
    if(e.target.closest('#deleteBtn')&&deleteIndex!==null){ setTimeout(()=>{const all=payrollAll(),next={};Object.keys(all).forEach(k=>{const idx=Number(k);if(idx<deleteIndex)next[idx]=all[k];else if(idx>deleteIndex)next[idx-1]=all[k]});localStorage.setItem(PAYROLL_KEY,JSON.stringify(next));deleteIndex=null;sync()},0);return; }
    if(e.target.closest('#resetBtn')){setTimeout(()=>{localStorage.removeItem(PAYROLL_KEY);sync()},0);return;}
    if(e.target.closest('#scenarioTabs')||e.target.closest('#addBtn')||e.target.closest('#ltBtn')||e.target.closest('#enBtn')||e.target.closest('#modeMonthly')||e.target.closest('#modeHourly')) requestAnimationFrame(()=>requestAnimationFrame(sync));
  },true);
  document.addEventListener('input',e=>{if(e.target.matches('input,textarea'))requestAnimationFrame(()=>requestAnimationFrame(sync))},true);
  document.addEventListener('change',e=>{if(e.target.matches('select,input[type=checkbox]'))requestAnimationFrame(()=>requestAnimationFrame(sync))},true);

  function approx(a,b,t=0.02){return Math.abs(a-b)<=t}
  function selfTests(){
    const a=grossFromNet(2300,{...DEFAULTS,pension2:false,applyNpd:false,employerRate:1.77});
    const b=grossFromNet(2300,{...DEFAULTS,pension2:true,applyNpd:false,employerRate:1.77});
    const p=posting(a,{...DEFAULTS,a1:true,includePerDiemInNet:false,country:'NL',days:30,perDiemRate:64,pension2:false,applyNpd:false,employerRate:1.77},200);
    const tests=[
      ['net2300 gross',approx(a.gross,3801.65)],['net2300 employee social',approx(a.sodra,741.32)],['net2300 GPM',approx(a.gpm,760.33)],['net2300 employer',approx(a.employerTaxes,67.29)],['net2300 payroll cost',approx(a.payrollCost,3868.94)],
      ['pension gross',approx(b.gross,4000)],['pension social',approx(b.sodra,780)],['pension contribution',approx(b.pension,120)],['pension GPM',approx(b.gpm,800)],['pension cost',approx(b.payrollCost,4070.80)],
      ['NL daily allowance',approx(p.totalPerDiem,1920)],['NL tax-free allowance',approx(p.exemptPerDiem,1920)],['NL paid total',approx(p.paidToEmployee,4220)],['NL payroll+posting cost',approx(p.payrollPostingCost,5788.94)]
    ];
    const passed=tests.every(x=>x[1]); window.__euroteamsAudit={passed,tests,checkedAt:new Date().toISOString()};
    if(!passed) console.warn('Euroteams calculator self-test failed',tests.filter(x=>!x[1]));
    return passed;
  }

  const style=document.createElement('link'); style.rel='stylesheet'; style.href='final-audit.css?v=20261014-1'; document.head.appendChild(style);
  window.addEventListener('load',()=>setTimeout(()=>{selfTests();sync()},180));
  setTimeout(()=>{selfTests();sync()},260);
})();
