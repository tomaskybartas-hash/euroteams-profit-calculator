(() => {
  const MAIN_KEY='euroteams-profit-calculator-v3';
  const PAYROLL_KEY='euroteams-payroll-2026-v4';
  const $=id=>document.getElementById(id);
  const n=v=>Math.max(0,Number(v)||0);
  const isEn=()=>$('enBtn')?.classList.contains('active');
  const money=v=>new Intl.NumberFormat(isEn()?'en-GB':'lt-LT',{style:'currency',currency:'EUR',minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(v)||0);
  const pct=v=>new Intl.NumberFormat(isEn()?'en-GB':'lt-LT',{minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(v)||0)+' %';
  const DEF={pension2:false,applyNpd:false,employerRate:1.77,localTransport:0,workwearTools:0,a1:false,includePerDiemInNet:true,country:'NL',days:30,perDiemRate:64};
  let queued=false;

  function main(){try{return JSON.parse(localStorage.getItem(MAIN_KEY)||'null')}catch(e){return null}}
  function payrollAll(){try{return JSON.parse(localStorage.getItem(PAYROLL_KEY)||'{}')||{}}catch(e){return {}}}
  function cfg(i){return {...DEF,...(payrollAll()[String(i)]||{})}}
  function npd(g,c){if(!c.applyNpd)return 0;if(g<=1153)return 747;return Math.max(0,747-.49*(g-1153))}
  function payroll(g,c){g=n(g);const sodra=g*.195,pension=c.pension2?g*.03:0,N=npd(g,c),gpm=Math.max(0,g-N)*.20,net=g-sodra-pension-gpm,employerTaxes=g*(n(c.employerRate)/100);return{gross:g,sodra,pension,gpm,net,employerTaxes,payrollCost:g+employerTaxes}}
  function grossFromNet(target,c){target=n(target);if(!target)return payroll(0,c);if(!c.applyNpd){const d=1-.195-(c.pension2?.03:0)-.20;return payroll(target/d,c)}let lo=0,hi=Math.max(2000,target*3+1000);while(payroll(hi,c).net<target)hi*=2;for(let i=0;i<120;i++){const m=(lo+hi)/2;payroll(m,c).net<target?lo=m:hi=m}return payroll((lo+hi)/2,c)}
  function post(base,c,hours){if(!c.a1)return{totalPerDiem:0,taxableEmployerTaxes:0,paidToEmployee:base.net,payrollPostingCost:base.payrollCost};const total=n(c.perDiemRate)*n(c.days),hourly=hours?base.gross/hours:0,full=base.gross>=1902.45||hourly>=11.6325,exempt=Math.min(total,full?total:base.gross*.5),taxable=Math.max(0,total-exempt),combined=payroll(base.gross+taxable,c),extraS=Math.max(0,combined.sodra-base.sodra),extraP=Math.max(0,combined.pension-base.pension),extraG=Math.max(0,combined.gpm-base.gpm),taxNet=Math.max(0,taxable-extraS-extraP-extraG),taxEmpl=taxable*(n(c.employerRate)/100);return{totalPerDiem:total,taxableEmployerTaxes:taxEmpl,paidToEmployee:base.net+exempt+taxNet,payrollPostingCost:base.payrollCost+total+taxEmpl}}
  function solve(target,c,hours){target=n(target);const ev=g=>{const base=payroll(g,c);return{base,post:post(base,c,hours)}};if(!target)return ev(0);let lo=0,hi=Math.max(3000,target*3+n(c.perDiemRate)*n(c.days)+1000);while(ev(hi).post.paidToEmployee<target)hi*=2;for(let i=0;i<140;i++){const m=(lo+hi)/2;ev(m).post.paidToEmployee<target?lo=m:hi=m}const a=ev(lo),b=ev(hi);return Math.abs(a.post.paidToEmployee-target)<=Math.abs(b.post.paidToEmployee-target)?a:b}
  function travel(s){if((s.travelMode||'monthly')!=='rotation')return n(s.travelMonthly);let w=6,h=2;if(s.rotation==='custom'){w=Math.max(1,n(s.workWeeks));h=n(s.homeWeeks)}else{const p=String(s.rotation||'6/2').split('/').map(Number);w=p[0]||6;h=p[1]||2}return n(s.travelRotation)*(4.345/Math.max(1,w+h))}
  function calc(s,i){const workers=Math.max(1,Math.round(n(s.workers)||1)),hours=n(s.hours),revenue=n(s.clientRate)*hours,c=cfg(i);let workerTotal,employeeShown;
    if((s.costMode||'hourly')==='monthly'){
      const target=n(s.monthlyPay),x=c.a1&&c.includePerDiemInNet?solve(target,c,hours):(()=>{const base=grossFromNet(target,c);return{base,post:post(base,c,hours)}})();
      workerTotal=(c.a1?x.post.payrollPostingCost:x.base.payrollCost)+n(s.housing)+travel(s)+n(s.other)+n(c.localTransport)+n(c.workwearTools);
      employeeShown=c.a1&&c.includePerDiemInNet?x.post.paidToEmployee:x.base.net;
    }else if(c.a1){
      const target=n(s.netRate)*hours,x=c.includePerDiemInNet?solve(target,c,hours):(()=>{const base=grossFromNet(target,c);return{base,post:post(base,c,hours)}})();
      workerTotal=x.post.payrollPostingCost+n(s.housing)+travel(s)+n(s.other)+n(c.localTransport)+n(c.workwearTools);
      employeeShown=c.includePerDiemInNet?x.post.paidToEmployee:x.base.net;
    }else{
      const salary=n(s.netRate)*hours,employer=salary*(1+n(s.uplift)/100);workerTotal=employer+n(s.housing)+travel(s)+n(s.other);employeeShown=salary;
    }
    const profit=revenue-workerTotal,margin=revenue?profit/revenue*100:0;return{workers,revenue,workerTotal,profit,margin,teamRevenue:revenue*workers,teamCost:workerTotal*workers,teamProfit:profit*workers,employeeShown};
  }
  function tone(el,v){if(!el)return;el.classList.remove('audit-positive','audit-negative','audit-neutral');el.classList.add(v>0.005?'audit-positive':v<-0.005?'audit-negative':'audit-neutral')}
  function sync(){queued=false;const st=main();if(!st||!Array.isArray(st.scenarios)||!st.scenarios.length)return;const tabs=[...($('scenarioTabs')?.querySelectorAll('.scenario-tab')||[])];let allRev=0,allCost=0,allProfit=0;st.scenarios.forEach((s,i)=>{const c=calc(s,i);allRev+=c.teamRevenue;allCost+=c.teamCost;allProfit+=c.teamProfit;const p=tabs[i]?.querySelector('.scenario-profit strong');if(p){p.textContent=money(c.teamProfit);tone(p,c.teamProfit)}});const i=Math.max(0,Math.min(Number(st.selected)||0,st.scenarios.length-1)),c=calc(st.scenarios[i],i);if($('profitValue')){$('profitValue').textContent=money(c.profit);tone($('profitValue'),c.profit)}if($('teamProfit')){$('teamProfit').textContent=money(c.teamProfit);tone($('teamProfit'),c.teamProfit)}if($('marginValue'))$('marginValue').textContent=pct(c.margin);if($('teamRevenue'))$('teamRevenue').textContent=money(c.teamRevenue);if($('teamCosts'))$('teamCosts').textContent=money(c.teamCost);if($('totalCostValue'))$('totalCostValue').textContent=money(c.workerTotal);if($('salaryValue'))$('salaryValue').textContent=money(c.employeeShown);const box=$('allProjectsAudit');if(box){const m=allRev?allProfit/allRev*100:0;box.innerHTML=`<div><span>${isEn()?'All Projects Revenue':'Visų projektų pajamos'}</span><strong>${money(allRev)}</strong></div><div><span>${isEn()?'All Projects Cost':'Visų projektų savikaina'}</span><strong>${money(allCost)}</strong></div><div><span>${isEn()?'All Projects Profit':'Visų projektų pelnas'}</span><strong id="allProfitAudit">${money(allProfit)}</strong></div><div><span>${isEn()?'Overall Margin':'Bendra marža'}</span><strong>${pct(m)}</strong></div>`;tone($('allProfitAudit'),allProfit)}}
  function schedule(){if(queued)return;queued=true;setTimeout(sync,0)}
  document.addEventListener('input',e=>{if(e.target.matches('input,textarea'))schedule()},true);
  document.addEventListener('change',e=>{if(e.target.matches('select,input[type=checkbox]'))schedule()},true);
  document.addEventListener('click',e=>{if(e.target.closest('#scenarioTabs')||e.target.closest('#modeMonthly')||e.target.closest('#modeHourly')||e.target.closest('#addBtn')||e.target.closest('#deleteBtn')||e.target.closest('#resetBtn')||e.target.closest('#ltBtn')||e.target.closest('#enBtn'))schedule()},true);
  window.addEventListener('load',()=>setTimeout(sync,300));setTimeout(sync,450);
})();