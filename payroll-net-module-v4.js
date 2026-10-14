(() => {
  const STORE_KEY = 'euroteams-payroll-2026-v4';
  const MAIN_KEY = 'euroteams-profit-calculator-v3';

  const RATES = Object.freeze({
    NL:{lt:'Nyderlandai',en:'Netherlands',rate:64}, DE:{lt:'Vokietija',en:'Germany',rate:62},
    FR:{lt:'Prancūzija',en:'France',rate:69}, FI:{lt:'Suomija',en:'Finland',rate:69},
    SE:{lt:'Švedija',en:'Sweden',rate:70}, DK:{lt:'Danija',en:'Denmark',rate:80},
    NO:{lt:'Norvegija',en:'Norway',rate:70}, EE:{lt:'Estija',en:'Estonia',rate:47},
    ES:{lt:'Ispanija',en:'Spain',rate:58}, PT:{lt:'Portugalija',en:'Portugal',rate:56},
    BE:{lt:'Belgija',en:'Belgium',rate:61}, AT:{lt:'Austrija',en:'Austria',rate:69},
    OTHER:{lt:'Kita',en:'Other',rate:33}
  });

  const DEFAULTS = {
    pension2:false, applyNpd:false, employerRate:1.77,
    localTransport:0, workwearTools:0,
    a1:false, includePerDiemInNet:true,
    country:'NL', days:30, perDiemRate:64
  };

  const $ = id => document.getElementById(id);
  const n = v => Math.max(0, Number(v) || 0);
  const isEn = () => $('enBtn')?.classList.contains('active');
  const tr = (lt,en) => isEn() ? en : lt;
  const money = v => new Intl.NumberFormat(isEn()?'en-GB':'lt-LT', {
    style:'currency', currency:'EUR', minimumFractionDigits:2, maximumFractionDigits:2
  }).format(Number(v)||0);
  const pct = v => new Intl.NumberFormat(isEn()?'en-GB':'lt-LT', {
    minimumFractionDigits:2, maximumFractionDigits:2
  }).format(Number(v)||0)+' %';

  let syncingEmployer=false;
  let recalcQueued=false;

  function getMainState(){ try{return JSON.parse(localStorage.getItem(MAIN_KEY)||'null')}catch(e){return null} }
  function activeIndex(){
    const st=getMainState();
    if(st&&Array.isArray(st.scenarios)) return Math.max(0,Math.min(Number(st.selected)||0,st.scenarios.length-1));
    return 0;
  }
  function currentScenario(){ const st=getMainState(); return st&&Array.isArray(st.scenarios)?(st.scenarios[activeIndex()]||null):null; }
  function loadAll(){ try{return JSON.parse(localStorage.getItem(STORE_KEY)||'{}')||{}}catch(e){return {}} }
  function getSettings(){
    const raw=loadAll()[String(activeIndex())]||{};
    const cfg={...DEFAULTS,...raw};
    if(!Number.isFinite(Number(cfg.perDiemRate))) cfg.perDiemRate=RATES[cfg.country]?.rate??33;
    return cfg;
  }
  function saveSettings(patch){
    const all=loadAll(), key=String(activeIndex());
    all[key]={...DEFAULTS,...(all[key]||{}),...patch};
    localStorage.setItem(STORE_KEY,JSON.stringify(all));
  }

  function npdForGross(gross,apply){
    if(!apply) return 0;
    if(gross<=1153) return 747;
    return Math.max(0,747-0.49*(gross-1153));
  }

  function payrollFromGross(gross,cfg){
    const sodra=gross*0.195;
    const pension=cfg.pension2?gross*0.03:0;
    const npd=npdForGross(gross,cfg.applyNpd);
    const gpmBase=Math.max(0,gross-npd);
    const gpm=gpmBase*0.20;
    const net=gross-sodra-pension-gpm;
    const employerTaxes=gross*(n(cfg.employerRate)/100);
    return {gross,sodra,pension,npd,gpmBase,gpm,net,employerTaxes,payrollCost:gross+employerTaxes};
  }

  function grossFromNet(targetNet,cfg){
    targetNet=n(targetNet);
    if(targetNet===0) return payrollFromGross(0,cfg);
    if(!cfg.applyNpd){
      const denom=1-0.195-(cfg.pension2?0.03:0)-0.20;
      return payrollFromGross(targetNet/denom,cfg);
    }
    let lo=0,hi=Math.max(2000,targetNet*2.5+1000);
    while(payrollFromGross(hi,cfg).net<targetNet) hi*=2;
    for(let i=0;i<100;i++){
      const mid=(lo+hi)/2;
      if(payrollFromGross(mid,cfg).net<targetNet) lo=mid; else hi=mid;
    }
    return payrollFromGross((lo+hi)/2,cfg);
  }

  function calculatePosting(base,cfg,hours){
    if(!cfg.a1){
      return {enabled:false,totalPerDiem:0,exemptPerDiem:0,taxablePerDiem:0,taxablePerDiemNet:0,
        taxableEmployerTaxes:0,totalSodra:base.sodra,totalPension:base.pension,totalGpm:base.gpm,
        paidToEmployee:base.net,payrollPostingCost:base.payrollCost,fullyExempt:true,hourlyGross:hours?base.gross/hours:0};
    }
    const totalPerDiem=n(cfg.perDiemRate)*n(cfg.days);
    const hourlyGross=hours?base.gross/hours:0;
    const fullyExempt=base.gross>=1902.45 || hourlyGross>=11.6325;
    const exemptLimit=fullyExempt?totalPerDiem:base.gross*0.50;
    const exemptPerDiem=Math.min(totalPerDiem,exemptLimit);
    const taxablePerDiem=Math.max(0,totalPerDiem-exemptPerDiem);
    const combined=payrollFromGross(base.gross+taxablePerDiem,cfg);
    const extraSodra=Math.max(0,combined.sodra-base.sodra);
    const extraPension=Math.max(0,combined.pension-base.pension);
    const extraGpm=Math.max(0,combined.gpm-base.gpm);
    const taxablePerDiemNet=Math.max(0,taxablePerDiem-extraSodra-extraPension-extraGpm);
    const taxableEmployerTaxes=taxablePerDiem*(n(cfg.employerRate)/100);
    return {
      enabled:true,totalPerDiem,exemptPerDiem,taxablePerDiem,taxablePerDiemNet,taxableEmployerTaxes,
      totalSodra:combined.sodra,totalPension:combined.pension,totalGpm:combined.gpm,
      paidToEmployee:base.net+exemptPerDiem+taxablePerDiemNet,
      payrollPostingCost:base.payrollCost+totalPerDiem+taxableEmployerTaxes,
      fullyExempt,hourlyGross
    };
  }

  function solveIncludedTarget(targetPayout,cfg,hours){
    targetPayout=n(targetPayout);
    if(targetPayout===0){
      const base=payrollFromGross(0,cfg);
      return {base,posting:calculatePosting(base,cfg,hours)};
    }
    let lo=0, hi=Math.max(3000,targetPayout*3+n(cfg.perDiemRate)*n(cfg.days)+1000);
    const evalGross=g=>{ const base=payrollFromGross(g,cfg); return {base,posting:calculatePosting(base,cfg,hours)}; };
    while(evalGross(hi).posting.paidToEmployee<targetPayout) hi*=2;
    for(let i=0;i<120;i++){
      const mid=(lo+hi)/2;
      if(evalGross(mid).posting.paidToEmployee<targetPayout) lo=mid; else hi=mid;
    }
    const a=evalGross(lo), b=evalGross(hi);
    return Math.abs(a.posting.paidToEmployee-targetPayout)<=Math.abs(b.posting.paidToEmployee-targetPayout)?a:b;
  }

  function ensureUi(){
    const monthly=$('monthlyFields'); if(!monthly) return false;
    const employer=$('monthlyEmployer');
    if(employer){ employer.readOnly=true; employer.setAttribute('aria-readonly','true'); employer.step='0.01'; }
    if(!$('payrollCostHelp')&&employer){
      const help=document.createElement('div'); help.id='payrollCostHelp'; help.className='help'; employer.closest('.field').appendChild(help);
    }
    if(!$('payroll2026Controls')){
      const box=document.createElement('div'); box.id='payroll2026Controls'; box.style.marginTop='16px';
      box.innerHTML=`
        <div class="two">
          <div class="field"><label id="pension2Label"></label><select id="pension2"><option value="no">NE</option><option value="yes">TAIP, +3 %</option></select></div>
          <div class="field"><label id="npdLabel"></label><select id="applyNpd"><option value="no">NE</option><option value="yes">TAIP</option></select></div>
        </div>
        <div class="field"><label id="employerRateLabel"></label><input id="employerRate2026" type="number" step="0.01" min="0"></div>
        <div id="payrollRateHelp" class="help"></div>
        <div class="field" style="margin-top:18px;padding:14px;border:1px solid #d9dee3;border-radius:12px;background:#fff;">
          <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin:0;">
            <input id="a1Enabled" type="checkbox" style="width:18px;height:18px;margin:0;"><span id="a1Label" style="font-weight:700;"></span>
          </label>
        </div>
        <div id="a1Details" style="display:none;margin-top:12px;padding:16px;border:1px solid #d9dee3;border-radius:12px;background:#f8fafc;">
          <div class="field" style="padding:12px;border:1px solid #d9dee3;border-radius:10px;background:#fff;margin-bottom:14px;">
            <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin:0;">
              <input id="includePerDiemInNet" type="checkbox" style="width:18px;height:18px;margin:0;"><span id="includePerDiemLabel" style="font-weight:700;"></span>
            </label>
            <div id="includePerDiemHelp" class="help" style="margin-top:8px;"></div>
          </div>
          <div class="two">
            <div class="field"><label id="countryLabel"></label><select id="postingCountry"></select></div>
            <div class="field"><label id="daysLabel"></label><input id="postingDays" type="number" min="0" step="1"></div>
          </div>
          <div class="field"><label id="perDiemRateLabel"></label><input id="postingRate" type="number" min="0" step="0.01"></div>
          <div id="rateHint" class="help"></div>
          <div id="a1Status" style="margin-top:12px;padding:12px;border-radius:10px;font-weight:700;"></div>
          <div id="a1TaxNote" class="help" style="margin-top:10px;"></div>
          <div id="hostPayWarning" class="help" style="margin-top:6px;"></div>
          <div id="postingSummary" class="metrics" style="grid-template-columns:repeat(2,minmax(0,1fr));margin-top:14px;"></div>
          <div id="employeePayFlow" style="margin-top:14px;"></div>
          <div id="companyCostFlow" style="margin-top:10px;"></div>
        </div>
        <div class="subhead" id="payrollBreakdownTitle"></div>
        <div id="payrollBreakdown" class="metrics" style="grid-template-columns:repeat(2,minmax(0,1fr));"></div>
        <div id="npdInfo" class="help" style="margin-top:8px;"></div>
        <div class="subhead" id="extraProjectCostsTitle"></div>
        <div class="two">
          <div class="field"><label id="localTransportLabel"></label><input id="localTransport2026" type="number" step="0.01" min="0"></div>
          <div class="field"><label id="workwearToolsLabel"></label><input id="workwearTools2026" type="number" step="0.01" min="0"></div>
        </div>`;
      monthly.appendChild(box); populateCountries(); bindControls();
    }
    translateUi(); return true;
  }

  function populateCountries(){
    const select=$('postingCountry'); if(!select||select.options.length) return;
    Object.entries(RATES).forEach(([code,x])=>{ const o=document.createElement('option'); o.value=code; o.textContent=isEn()?x.en:x.lt; select.appendChild(o); });
  }

  function bindControls(){
    const bindBool=(id,key)=>{ const el=$(id); if(!el||el.dataset.bound) return; el.dataset.bound='1'; el.addEventListener('change',()=>{saveSettings({[key]:el.type==='checkbox'?el.checked:el.value==='yes'});scheduleRecalc();}); };
    bindBool('pension2','pension2'); bindBool('applyNpd','applyNpd'); bindBool('a1Enabled','a1'); bindBool('includePerDiemInNet','includePerDiemInNet');
    const country=$('postingCountry');
    if(country&&!country.dataset.bound){ country.dataset.bound='1'; country.addEventListener('change',()=>{ const code=country.value; saveSettings({country:code,perDiemRate:RATES[code]?.rate??33}); scheduleRecalc(); }); }
    [['employerRate2026','employerRate'],['postingDays','days'],['postingRate','perDiemRate'],['localTransport2026','localTransport'],['workwearTools2026','workwearTools']].forEach(([id,key])=>{
      const el=$(id); if(!el||el.dataset.bound) return; el.dataset.bound='1';
      el.addEventListener('input',()=>{saveSettings({[key]:n(el.value)});scheduleRecalc();});
      el.addEventListener('blur',()=>{ if(id==='postingDays') el.value=String(Math.round(n(el.value))); else if(el.value!=='') el.value=n(el.value).toFixed(2); });
    });
  }

  function translateUi(){
    const cfg=getSettings();
    const payLabel=$('monthlyPay')?.closest('.field')?.querySelector('label');
    if(payLabel) payLabel.textContent=cfg.a1&&cfg.includePerDiemInNet
      ?tr('Bendra darbuotojui išmokama NETO suma / mėn. (su dienpinigiais)','Total NET paid to employee / month (incl. per diem)')
      :tr('Darbuotojo NETO atlyginimas / mėn.','Employee NET salary / month');
    const costLabel=$('monthlyEmployer')?.closest('.field')?.querySelector('label');
    if(costLabel) costLabel.textContent=tr('DU savikaina įmonei / mėn.','Payroll cost to company / month');
    if($('pension2Label')) $('pension2Label').textContent=tr('II pakopos pensijų kaupimas','Pillar II pension contribution');
    if($('npdLabel')) $('npdLabel').textContent=tr('Taikyti NPD','Apply NPD');
    if($('employerRateLabel')) $('employerRateLabel').textContent=tr('Darbdavio mokesčių tarifas (%)','Employer contribution rate (%)');
    if($('payrollRateHelp')) $('payrollRateHelp').textContent=tr('Numatyta 1,77 %. Tarifą galima keisti pagal darbo sutarties tipą ir nelaimingų atsitikimų draudimo grupę.','Default 1.77%. The rate can be changed depending on contract type and accident insurance group.');
    if($('payrollCostHelp')) $('payrollCostHelp').textContent=tr('Bruto atlyginimas + darbdavio socialinės įmokos. Dienpinigiai ir projekto išlaidos skaičiuojami atskirai.','Gross salary + employer social contributions. Per diem and project costs are calculated separately.');
    if($('a1Label')) $('a1Label').textContent=tr('Skaičiuoti su A1 komandiruote','Calculate with A1 posting');
    if($('includePerDiemLabel')) $('includePerDiemLabel').textContent=tr('Skaičiuoti su įtrauktais dienpinigiais','Calculate with per diem included');
    if($('includePerDiemHelp')) $('includePerDiemHelp').textContent=tr('Kai pažymėta, įvesta NETO suma yra visa darbuotojui išmokama suma kartu su dienpinigiais. Skaičiuoklė automatiškai išskaido ją į NETO darbo užmokestį ir dienpinigius.','When enabled, the entered NET amount is the total paid to the employee including per diem. The calculator automatically splits it into NET salary and per diem.');
    if($('countryLabel')) $('countryLabel').textContent=tr('Komandiruotės šalis','Posting country');
    if($('daysLabel')) $('daysLabel').textContent=tr('Komandiruotės dienos / mėn.','Posting calendar days / month');
    if($('perDiemRateLabel')) $('perDiemRateLabel').textContent=tr('Dienpinigių norma EUR / dieną','Per diem rate EUR / day');
    if($('rateHint')) $('rateHint').textContent=tr('Norma automatiškai parenkama pagal šalį, bet ją galima koreguoti rankiniu būdu.','The rate is selected automatically by country but can be adjusted manually.');
    if($('a1TaxNote')) $('a1TaxNote').textContent=tr('A1 taikomas socialiniam draudimui. GPM apmokestinimo valstybė konkrečiu atveju gali priklausyti nuo darbo valstybės ir tarptautinių mokesčių taisyklių.','A1 applies to social security. The country of personal income tax taxation may depend on the work country and international tax rules.');
    if($('hostPayWarning')) $('hostPayWarning').textContent=tr('Būtina patikrinti priimančios valstybės komandiruojamų darbuotojų minimalaus atlygio / remuneration reikalavimus.','Check the host country minimum pay / remuneration requirements for posted workers.');
    if($('payrollBreakdownTitle')) $('payrollBreakdownTitle').textContent=tr('2026 m. darbo užmokesčio išklotinė','2026 payroll breakdown');
    if($('extraProjectCostsTitle')) $('extraProjectCostsTitle').textContent=tr('Atskiros projekto sąnaudos','Separate project costs');
    if($('localTransportLabel')) $('localTransportLabel').textContent=tr('Vietinis transportas / mėn.','Local transport / month');
    if($('workwearToolsLabel')) $('workwearToolsLabel').textContent=tr('Darbo rūbai / įrankiai / mėn.','Workwear / tools / month');
    if($('pension2')){ $('pension2').options[0].textContent=tr('NE','NO'); $('pension2').options[1].textContent=tr('TAIP, +3 %','YES, +3%'); }
    if($('applyNpd')){ $('applyNpd').options[0].textContent=tr('NE','NO'); $('applyNpd').options[1].textContent=tr('TAIP','YES'); }
    const select=$('postingCountry'); if(select) [...select.options].forEach(o=>{const x=RATES[o.value];if(x)o.textContent=isEn()?x.en:x.lt;});
  }

  function hydrateControls(cfg){
    if($('pension2')) $('pension2').value=cfg.pension2?'yes':'no';
    if($('applyNpd')) $('applyNpd').value=cfg.applyNpd?'yes':'no';
    if($('a1Enabled')) $('a1Enabled').checked=!!cfg.a1;
    if($('includePerDiemInNet')) $('includePerDiemInNet').checked=!!cfg.includePerDiemInNet;
    if($('postingCountry')) $('postingCountry').value=cfg.country||'NL';
    if($('a1Details')) $('a1Details').style.display=cfg.a1?'block':'none';
    if($('employerRate2026')&&document.activeElement!==$('employerRate2026')) $('employerRate2026').value=n(cfg.employerRate).toFixed(2);
    if($('postingDays')&&document.activeElement!==$('postingDays')) $('postingDays').value=String(Math.round(n(cfg.days)));
    if($('postingRate')&&document.activeElement!==$('postingRate')) $('postingRate').value=n(cfg.perDiemRate).toFixed(2);
    if($('localTransport2026')&&document.activeElement!==$('localTransport2026')) $('localTransport2026').value=n(cfg.localTransport).toFixed(2);
    if($('workwearTools2026')&&document.activeElement!==$('workwearTools2026')) $('workwearTools2026').value=n(cfg.workwearTools).toFixed(2);
  }

  function renderPayroll(base,posting,cfg,targetInput){
    const b=$('payrollBreakdown'); if(!b) return;
    const rows=[];
    if(cfg.a1&&cfg.includePerDiemInNet) rows.push([tr('Įvesta bendra NETO suma','Entered total NET amount'),targetInput]);
    rows.push([tr('NETO darbo užmokestis','NET salary'),base.net]);
    rows.push([tr('Bruto atlyginimas','Gross salary'),base.gross]);
    rows.push([tr('Darbuotojo Sodra','Employee social insurance'),posting.totalSodra]);
    rows.push([tr('GPM','Personal income tax'),posting.totalGpm]);
    rows.push([tr('Pensijų kaupimas','Pillar II pension'),posting.totalPension]);
    rows.push([tr('Darbdavio socialinės įmokos','Employer social contributions'),base.employerTaxes+posting.taxableEmployerTaxes]);
    rows.push([tr('DU savikaina įmonei','Payroll cost to company'),base.payrollCost]);
    b.innerHTML=rows.map(([label,val])=>`<div class="metric"><span>${label}</span><strong>${money(val)}</strong></div>`).join('');
    const info=$('npdInfo'); if(info) info.textContent=cfg.applyNpd?`${tr('Taikomas NPD','Applied NPD')}: ${money(base.npd)}`:'';
  }

  function renderPosting(cfg,posting,base,targetInput){
    if(!$('postingSummary')) return;
    if(!cfg.a1){ $('postingSummary').innerHTML=''; if($('employeePayFlow'))$('employeePayFlow').innerHTML=''; if($('companyCostFlow'))$('companyCostFlow').innerHTML=''; return; }
    const country=RATES[cfg.country]||RATES.OTHER;
    const rows=[
      [tr('Komandiruotės šalis','Posting country'),isEn()?country.en:country.lt],
      [tr('Dienpinigių norma','Per diem rate'),`${money(cfg.perDiemRate)} / ${tr('dieną','day')}`],
      [tr('Komandiruotės kalendorinės dienos','Posting calendar days'),String(Math.round(n(cfg.days)))],
      [tr('Bendra dienpinigių suma','Total per diem'),money(posting.totalPerDiem)],
      [tr('Neapmokestinami dienpinigiai','Tax-exempt per diem'),money(posting.exemptPerDiem)],
      [tr('Apmokestinami dienpinigiai','Taxable per diem'),money(posting.taxablePerDiem)],
      [tr('Bendra darbuotojui išmokama suma','Total paid to employee'),money(posting.paidToEmployee)],
      [tr('DU + komandiruotės savikaina','Payroll + posting cost'),money(posting.payrollPostingCost)]
    ];
    $('postingSummary').innerHTML=rows.map(([label,val])=>`<div class="metric"><span>${label}</span><strong>${val}</strong></div>`).join('');
    const status=$('a1Status'); if(status){ const ok=posting.taxablePerDiem<=0.000001; status.textContent=ok?tr('Neapmokestinama visa suma','Entire per diem amount is tax-exempt'):tr('Dalis dienpinigių apmokestinama','Part of the per diem is taxable'); status.style.background=ok?'#eef8f1':'#fff4e5'; status.style.color=ok?'#176b35':'#8a4b00'; }
    if($('employeePayFlow')) $('employeePayFlow').innerHTML=`<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;font-weight:700"><span>${tr('NETO darbo užmokestis','NET salary')} ${money(base.net)}</span><span>+</span><span>${tr('Neapmokestinami dienpinigiai','Tax-exempt per diem')} ${money(posting.exemptPerDiem)}</span>${posting.taxablePerDiem>0?`<span>+</span><span>${tr('Apmokestintų dienpinigių NETO dalis','NET taxable per diem')} ${money(posting.taxablePerDiemNet)}</span>`:''}<span>=</span><span>${tr('Darbuotojui išmokama','Paid to employee')} ${money(posting.paidToEmployee)}</span></div>`;
    if($('companyCostFlow')) $('companyCostFlow').innerHTML=`<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;font-weight:700"><span>${tr('DU savikaina','Payroll cost')} ${money(base.payrollCost)}</span><span>+</span><span>${tr('Dienpinigiai','Per diem')} ${money(posting.totalPerDiem)}</span>${posting.taxableEmployerTaxes>0?`<span>+</span><span>${tr('Darbdavio mokesčiai nuo apmokestinamos dalies','Employer tax on taxable part')} ${money(posting.taxableEmployerTaxes)}</span>`:''}<span>=</span><span>${tr('DU + komandiruotė','Payroll + posting')} ${money(posting.payrollPostingCost)}</span></div>`;
  }

  function syncCoreMonthlyEmployer(base){
    const input=$('monthlyEmployer'); if(!input||syncingEmployer) return;
    const shown=base.payrollCost.toFixed(2); if(input.value===shown) return;
    syncingEmployer=true; input.value=shown; input.dispatchEvent(new Event('input',{bubbles:true})); syncingEmployer=false;
  }

  function travelForScenario(s){
    if((s.travelMode||'monthly')!=='rotation') return n(s.travelMonthly);
    let work=6,home=2; if(s.rotation==='custom'){work=Math.max(1,n(s.workWeeks));home=n(s.homeWeeks);} else {const p=String(s.rotation||'6/2').split('/').map(Number);work=p[0]||6;home=p[1]||2;}
    return n(s.travelRotation)*(4.345/Math.max(1,work+home));
  }

  function overrideResults(base,cfg,posting,targetInput){
    const s=currentScenario(); if(!s) return;
    const rate=n(s.clientRate),hours=n(s.hours),workers=Math.max(1,Math.round(n(s.workers)||1));
    const revenue=rate*hours,housing=n(s.housing),travel=travelForScenario(s),other=n(s.other);
    const payrollPosting=cfg.a1?posting.payrollPostingCost:base.payrollCost;
    const total=payrollPosting+housing+travel+other+n(cfg.localTransport)+n(cfg.workwearTools);
    const profit=revenue-total,margin=revenue?profit/revenue*100:0,ph=hours?profit/hours:0,be=hours?total/hours:0;
    const shownEmployee=cfg.a1&&cfg.includePerDiemInNet?posting.paidToEmployee:base.net;
    if($('salaryValue')) $('salaryValue').textContent=money(shownEmployee);
    if($('employerValue')) $('employerValue').textContent=money(base.payrollCost);
    if($('extraEmployerValue')) $('extraEmployerValue').textContent=money(base.employerTaxes+posting.taxableEmployerTaxes);
    if($('totalCostValue')) $('totalCostValue').textContent=money(total);
    if($('profitValue')) $('profitValue').textContent=money(profit);
    if($('marginValue')) $('marginValue').textContent=pct(margin);
    if($('profitHourValue')) $('profitHourValue').textContent=money(ph);
    if($('breakevenValue')) $('breakevenValue').textContent=money(be)+(isEn()?' / h':' / val.');
    if($('teamRevenue')) $('teamRevenue').textContent=money(revenue*workers);
    if($('teamCosts')) $('teamCosts').textContent=money(total*workers);
    if($('teamProfit')) $('teamProfit').textContent=money(profit*workers);
    const tbody=$('resultTableBody'); if(tbody){
      const r=(a,b,cls='')=>`<tr><th>${a}</th><td class="${cls}">${b}</td></tr>`;
      const rows=[r(tr('Darbuotojų skaičius','Number of workers'),workers),r(tr('Pajamos iš kliento / darbuotojui','Client revenue / worker'),money(revenue))];
      if(cfg.a1&&cfg.includePerDiemInNet) rows.push(r(tr('Įvesta bendra NETO suma','Entered total NET amount'),money(targetInput)));
      rows.push(r(tr('NETO darbo užmokestis','NET salary'),money(base.net)));
      rows.push(r(tr('Bruto atlyginimas','Gross salary'),money(base.gross)));
      rows.push(r(tr('Darbuotojo Sodra','Employee social insurance'),money(posting.totalSodra)));
      rows.push(r(tr('GPM','Personal income tax'),money(posting.totalGpm)));
      rows.push(r(tr('Pensijų kaupimas','Pillar II pension'),money(posting.totalPension)));
      rows.push(r(tr('Darbdavio socialinės įmokos','Employer social contributions'),money(base.employerTaxes+posting.taxableEmployerTaxes)));
      rows.push(r(tr('DU savikaina įmonei','Payroll cost to company'),money(base.payrollCost)));
      if(cfg.a1){ rows.push(r(tr('Dienpinigiai','Per diem'),money(posting.totalPerDiem))); rows.push(r(tr('Neapmokestinami dienpinigiai','Tax-exempt per diem'),money(posting.exemptPerDiem))); rows.push(r(tr('Apmokestinami dienpinigiai','Taxable per diem'),money(posting.taxablePerDiem))); rows.push(r(tr('Bendra darbuotojui išmokama suma','Total paid to employee'),money(posting.paidToEmployee))); rows.push(r(tr('DU + komandiruotės savikaina','Payroll + posting cost'),money(posting.payrollPostingCost))); }
      rows.push(r(tr('Apgyvendinimas','Accommodation'),money(housing)),r(tr('Kelionės','Travel'),money(travel)),r(tr('Vietinis transportas','Local transport'),money(cfg.localTransport)),r(tr('Darbo rūbai / įrankiai','Workwear / tools'),money(cfg.workwearTools)),r(tr('Kitos išlaidos','Other costs'),money(other)),r(tr('Visa darbuotojo savikaina','Total employee project cost'),money(total)),r(tr('Pelnas nuo vieno darbuotojo','Profit per worker'),money(profit),'green'),r(tr('Pelnas už valandą','Profit per hour'),money(ph),'green'),r(tr('Pelno marža','Profit margin'),pct(margin),'green'),r(tr('Tarifas be pelno ir nuostolio','Break-even rate'),money(be)+(isEn()?' / h':' / val.')),r(tr('Komandos pelnas','Team profit'),money(profit*workers),'green'));
      tbody.innerHTML=rows.join('');
    }
  }

  function recalc(){
    recalcQueued=false; if(!ensureUi()) return;
    const monthly=$('monthlyFields'); if(!monthly||monthly.classList.contains('hidden')) return;
    const cfg=getSettings(); hydrateControls(cfg); translateUi();
    const targetInput=n($('monthlyPay')?.value);
    const s=currentScenario(); const hours=n(s?.hours||$('hours')?.value);
    let base,posting;
    if(cfg.a1&&cfg.includePerDiemInNet){ const solved=solveIncludedTarget(targetInput,cfg,hours); base=solved.base; posting=solved.posting; }
    else { base=grossFromNet(targetInput,cfg); posting=calculatePosting(base,cfg,hours); }
    syncCoreMonthlyEmployer(base); renderPayroll(base,posting,cfg,targetInput); renderPosting(cfg,posting,base,targetInput); overrideResults(base,cfg,posting,targetInput);
  }

  function scheduleRecalc(){ if(recalcQueued)return; recalcQueued=true; requestAnimationFrame(recalc); }
  const liveIds=new Set(['monthlyPay','clientRate','hours','workers','housing','travelMonthly','travelRotation','other','workWeeks','homeWeeks']);
  document.addEventListener('input',e=>{ if(syncingEmployer||e.target?.id==='monthlyEmployer')return; if(liveIds.has(e.target?.id))scheduleRecalc(); });
  document.addEventListener('change',e=>{ if(['rotation','presetSelect'].includes(e.target?.id))scheduleRecalc(); });
  document.addEventListener('click',e=>{ if(e.target.closest('#modeMonthly')||e.target.closest('#ltBtn')||e.target.closest('#enBtn')||e.target.closest('#scenarioTabs')||e.target.closest('#addBtn')||e.target.closest('#deleteBtn')||e.target.closest('#resetBtn')||e.target.closest('#travelMonthlyBtn')||e.target.closest('#travelRotationBtn')) requestAnimationFrame(()=>requestAnimationFrame(recalc)); });
  window.addEventListener('load',()=>setTimeout(recalc,100)); setTimeout(recalc,150);
})();