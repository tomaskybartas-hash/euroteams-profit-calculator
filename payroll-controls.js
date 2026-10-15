(() => {
  'use strict';
  const KEY='euroteams-payroll-2026-v4', MAIN='euroteams-profit-calculator-v3';
  const $=id=>document.getElementById(id);
  const en=()=>$('enBtn').classList.contains('active'), t=(lt,eng)=>en()?eng:lt;
  const defaults={pension2:false,applyNpd:false,employerRate:1.77,localTransport:0,workwearTools:0,a1:false,includePerDiemInNet:true,country:'NL',days:30,perDiemRate:64,taxMode:'monthly',taxResident:true,otherAnnualIncome:0,priorSocialIncome:0,floorBase:1153,wageBasis:'monthly',contractWage:0,shortDays:0,customCountryLimit:0};
  const countries={NL:['Nyderlandai','Netherlands',64],DE:['Vokietija','Germany',62],FR:['Prancūzija','France',69],FI:['Suomija','Finland',69],SE:['Švedija','Sweden',70],DK:['Danija','Denmark',80],NO:['Norvegija','Norway',70],EE:['Estija','Estonia',47],ES:['Ispanija','Spain',58],PT:['Portugalija','Portugal',56],BE:['Belgija','Belgium',61],AT:['Austrija','Austria',69],OTHER:['Kita','Other',0]};
  window.EuroteamsDailyRates=countries;
  function read(key,fallback){try{return JSON.parse(window.EuroteamsStorage.getItem(key))||fallback}catch{return fallback}}
  function context(){const state=read(MAIN,{selected:0,scenarios:[]});return {state,index:state.selected,scenario:state.scenarios[state.selected]||{}}}
  function config(){return {...defaults,...read(KEY,{})[context().index]}}
  function save(patch){const all=read(KEY,{}),i=context().index;all[i]={...config(),...patch};window.EuroteamsStorage.setItem(KEY,JSON.stringify(all));window.renderEuroteamsCore()}
  const field=(id,label,type='number')=>`<div class="field"><label for="${id}" id="${id}Label">${label}</label><input id="${id}" type="${type}" min="0" step="0.01"></div>`;
  const select=(id)=>`<div class="field"><label for="${id}" id="${id}Label"></label><select id="${id}"><option value="no"></option><option value="yes"></option></select></div>`;
  const toggle=(id)=>`<div class="field check-field"><label for="${id}"><input id="${id}" type="checkbox"><span id="${id}Label"></span></label></div>`;
  function ensure(){
    if($('payrollControls'))return;
    const box=document.createElement('section');box.id='payrollControls';
    box.innerHTML=toggle('a1Enabled')+`<div id="payrollParameters"><div class="two">${select('pension2')}${select('applyNpd')}</div>${field('employerRate2026','')}<div class="help" id="payrollRateHelp"></div></div><div id="a1Details">${toggle('includePerDiemInNet')}<p class="help" id="includePerDiemHelp"></p><div class="field"><label for="postingCountry" id="postingCountryLabel"></label><select id="postingCountry"></select></div><div class="two">${field('postingDays','')}${field('postingRate','')}</div><p class="help" id="rateHint"></p><p class="help" id="a1Note"></p><div id="a1Status" role="status"></div></div><details id="payrollDetail"><summary id="payrollBreakdownTitle"></summary><div id="payrollBreakdown" class="metrics"></div></details><div class="subhead" id="extraProjectCostsTitle"></div><div class="two">${field('localTransport2026','')}${field('workwearTools2026','')}</div>`;
    $('monthlyFields').insertAdjacentElement('afterend',box);
    const advanced=document.createElement('details');advanced.className='tax-advanced';advanced.id='taxAdvanced';
    advanced.innerHTML=`<summary id="taxAdvancedTitle"></summary><div class="two"><div class="field"><label id="taxModeLabel" for="taxMode"></label><select id="taxMode"><option value="monthly"></option><option value="annualAverage"></option></select></div>${select('taxResident')}</div><div class="two">${field('priorSocialIncome','')}${field('otherAnnualIncome','')}</div>${field('floorBase','')}<p class="help" id="taxAdvancedHelp"></p>`;
    $('payrollRateHelp').insertAdjacentElement('afterend',advanced);
    const postingExtra=document.createElement('div');postingExtra.className='tax-advanced';postingExtra.innerHTML=`<div class="two"><div class="field"><label for="wageBasis" id="wageBasisLabel"></label><select id="wageBasis"><option value="monthly"></option><option value="hourly"></option></select></div>${field('contractWage','')}</div><div class="two">${field('shortDays','')}${field('customCountryLimit','')}</div><p class="help" id="contractHelp"></p>`;
    $('rateHint').insertAdjacentElement('beforebegin',postingExtra);
    for(const [id,key] of [['taxMode','taxMode'],['wageBasis','wageBasis']])$(id).addEventListener('change',e=>save({[key]:e.target.value}));
    $('taxResident').addEventListener('change',e=>save({taxResident:e.target.value==='yes'}));
    for(const id of ['priorSocialIncome','otherAnnualIncome','floorBase','contractWage','shortDays','customCountryLimit'])$(id).addEventListener('input',e=>{const value=Number(e.target.value);save({[id]:id==='shortDays'?Math.min(2,Math.trunc(Math.max(0,value||0)),Math.trunc(config().days||0)):Number.isFinite(value)?Math.max(0,value):0})});

    Object.keys(countries).forEach(code=>{const opt=document.createElement('option');opt.value=code;$('postingCountry').appendChild(opt)});
    [['a1Enabled','a1'],['includePerDiemInNet','includePerDiemInNet']].forEach(([id,key])=>$(id).addEventListener('change',e=>save({[key]:e.target.checked})));
    [['pension2','pension2'],['applyNpd','applyNpd']].forEach(([id,key])=>$(id).addEventListener('change',e=>save({[key]:e.target.value==='yes'})));
    [['employerRate2026','employerRate'],['postingDays','days'],['postingRate','perDiemRate'],['localTransport2026','localTransport'],['workwearTools2026','workwearTools']].forEach(([id,key])=>{
      $(id).addEventListener('input',e=>{const v=Number(e.target.value);let normalized=Number.isFinite(v)?Math.max(0,v):0;if(key==='days')normalized=Math.min(31,Math.trunc(normalized));save(key==='days'?{days:normalized,shortDays:Math.min(config().shortDays||0,normalized)}:{[key]:normalized})});
      $(id).addEventListener('blur',e=>{if(e.target.value!=='')e.target.value=String(config()[key])});
    });
    $('postingDays').step='1';$('postingDays').max='31';$('shortDays').max='2';
    $('postingCountry').addEventListener('change',e=>save({country:e.target.value,perDiemRate:countries[e.target.value][2]}));
    document.querySelectorAll('input[type=number]').forEach(el=>{el.min=['workers','workWeeks'].includes(el.id)?'1':'0';if(!['workers','workWeeks','homeWeeks','postingDays','shortDays'].includes(el.id))el.step='0.01';el.addEventListener('blur',()=>{const min=Number(el.min)||0;if((el.value!==''&&Number(el.value)<min)||(el.value===''&&min>0)){el.value=String(min);el.dispatchEvent(new Event('input',{bubbles:true}));}});});
    document.querySelectorAll('.field').forEach(el=>{const input=el.querySelector('input,select,textarea'),label=el.querySelector('label');if(input&&label&&!label.htmlFor)label.htmlFor=input.id});
  }
  function render(){
    ensure();const c=config(),s=context().scenario,payroll=s.costMode==='monthly'||c.a1;
    $('payrollParameters').hidden=!payroll;$('a1Details').hidden=!c.a1;$('payrollDetail').hidden=!payroll;
    $('monthlyEmployer').readOnly=true;$('monthlyEmployer').setAttribute('aria-readonly','true');
    const put=(id,text)=>$(id).textContent=text;
    put('a1EnabledLabel',t('Skaičiuoti su A1 komandiruote','Calculate with A1 posting'));
    put('includePerDiemInNetLabel',t('Skaičiuoti su įtrauktais dienpinigiais','Include daily allowance in net payout'));
    put('includePerDiemHelp',t('Pažymėta: įvesta NETO suma jau apima dienpinigius. Nepažymėta: dienpinigiai pridedami prie NETO atlyginimo.','Checked: the entered net amount includes the daily allowance. Unchecked: the daily allowance is added to net salary.'));
    put('pension2Label',t('II pakopos pensijų kaupimas','Pillar II pension contribution'));put('applyNpdLabel',t('Taikyti NPD','Apply tax-free income allowance (NPD)'));
    for(const id of ['pension2','applyNpd']){$(id).options[0].textContent=t('NE','NO');$(id).options[1].textContent=t('TAIP','YES')+(id==='pension2'?' (+3 %)':'');}
    put('employerRate2026Label',t('Darbdavio socialinių įmokų tarifas (%)','Employer social security rate (%)'));
    put('payrollRateHelp',c.taxMode==='annualAverage'?t('Metinis vidurkis: 12 vienodų mėnesių, progresinis GPM ir VSD lubos.','Annual average: 12 identical months, progressive income tax and VSD cap.'):t('2026 m. mėnesio DU modelis: GPM 20 %. Metines prielaidas rasite žemiau.','2026 monthly payroll: 20% income tax. Annual assumptions are available below.'));
    put('taxAdvancedTitle',t('Mokestiniai parametrai · 2026','Tax assumptions · 2026'));
    put('taxModeLabel',t('Skaičiavimo laikotarpis','Calculation period'));
    $('taxMode').options[0].textContent=t('Mėnesio išmoka (GPM 20 %)','Monthly payout (20% income tax)');$('taxMode').options[1].textContent=t('Metinis NETO vidurkis','Annual-average net income');
    put('taxResidentLabel',t('Lietuvos mokesčių rezidentas','Lithuanian tax resident'));
    $('taxResident').options[0].textContent=t('NE','NO');$('taxResident').options[1].textContent=t('TAIP','YES');
    put('priorSocialIncomeLabel',t('Draudžiamosios pajamos iki šio mėnesio, EUR','Insured income before this month, EUR'));
    put('otherAnnualIncomeLabel',t('Kitos metinės pajamos 20/25/32 % režime, EUR','Other annual income in 20/25/32% regime, EUR'));
    put('floorBaseLabel',t('Įmokų grindų mėnesio bazė, EUR','Monthly minimum contribution base, EUR'));
    put('taxAdvancedHelp',t('Grindų bazė: 1153 EUR už visą mėnesį; tik esant teisėtai išimčiai – 0 arba proporcinga bazė. Nenuolatiniam gyventojui mėnesio NPD netaikomas. Metinis vidurkis daro 12 vienodų mėnesių ir vieno darbdavio prielaidą; neapima specialių NPD ir individualios veiklos mokesčių kredito.','Minimum base: EUR 1153 for a full month; use 0 or a prorated base only for a statutory exception. Monthly NPD is unavailable to non-residents. Annual average assumes 12 identical months and one employer; special NPD and self-employment tax credits are excluded.'));
    put('wageBasisLabel',t('Sutartinio atlygio rūšis','Contractual pay basis'));$('wageBasis').options[0].textContent=t('Mėnesinis','Monthly');$('wageBasis').options[1].textContent=t('Valandinis','Hourly');
    put('contractWageLabel',t('Sutartinis BRUTO (0 = apskaičiuotas)','Contractual gross pay (0 = calculated)'));
    put('shortDaysLabel',t('Pirma / paskutinė diena iki 4 val. (0–2)','First / last days under 4 hours (0–2)'));
    put('customCountryLimitLabel',t('Kitos šalies patikrinta dienos riba, EUR','Verified daily limit for Other country, EUR'));
    put('contractHelp',t('Taikoma tik pasirinkto sutartinio atlygio riba: 1902,45 EUR/mėn. arba 11,6325 EUR/val. 0 naudoja apskaičiuotą DU kaip prielaidą. Trumpa diena nuo 2026-10-01 skaičiuojama kaip 20 % dienos. Kelių šalių maršrutai vertinami atskirai.','Only the selected contractual pay threshold applies: EUR 1902.45/month or EUR 11.6325/hour. Zero uses calculated pay as an assumption. From 2026-10-01, a short day counts as 20% of a day. Multi-country itineraries need separate assessment.'));
    $('taxMode').value=c.taxMode;$('taxResident').value=c.taxResident?'yes':'no';$('wageBasis').value=c.wageBasis;
    $('applyNpd').disabled=!c.taxResident;
    $('priorSocialIncome').closest('.field').hidden=c.taxMode==='annualAverage';$('otherAnnualIncome').closest('.field').hidden=c.taxMode!=='annualAverage';
    $('customCountryLimit').closest('.field').hidden=c.country!=='OTHER';
    for(const key of ['priorSocialIncome','otherAnnualIncome','floorBase','contractWage','shortDays','customCountryLimit'])if(document.activeElement!==$(key))$(key).value=c[key];
    put('postingCountryLabel',t('Komandiruotės šalis','Posting country'));put('postingDaysLabel',t('Komandiruotės dienos / mėn.','Posting days / month'));put('postingRateLabel',t('Dienpinigių norma EUR / dieną','Daily allowance EUR / day'));
    put('rateHint',t('Šalis parenka dienos normą; ją galite koreguoti. Kitai šaliai įveskite patikrintą normą. Įveskite kalendorines dienas ir atskirai trumpas pirmą / paskutinę dienas.','Country selects the daily rate; you can edit it. For Other, enter a verified rate. Enter calendar days and separately count short first / last days.'));
    put('a1Note',t('A1 patvirtina taikomą socialinio draudimo valstybę. Dienpinigių lengvata čia vertinama pagal apskaičiuotą DU; būtina sutikrinti su sutartiniu atlygiu ir šalies norma.','A1 confirms the applicable social security system. This estimate uses calculated pay for allowance relief; verify contractual pay and the country limit.'));
    put('payrollBreakdownTitle',t('Darbo užmokesčio ir dienpinigių išklotinė','Payroll and daily allowance breakdown'));
    put('extraProjectCostsTitle',t('Atskiros projekto sąnaudos','Additional project costs'));put('localTransport2026Label',t('Vietinis transportas / mėn.','Local transport / month'));put('workwearTools2026Label',t('Darbo rūbai / įrankiai / mėn.','Workwear / tools / month'));
    const label=id=>$(id).closest('.field').querySelector('label');
    label('netRate').textContent=c.a1&&c.includePerDiemInNet?t('Bendra NETO išmoka / val. (su dienpinigiais)','Total net payout / hour (including allowance)'):t('Darbuotojo NETO atlyginimas / val.','Employee net salary / hour');
    label('monthlyPay').textContent=c.a1&&c.includePerDiemInNet?t('Bendra NETO išmoka / mėn. (su dienpinigiais)','Total net payout / month (including allowance)'):t('Darbuotojo NETO atlyginimas / mėn.','Employee net salary / month');
    label('monthlyEmployer').textContent=t('DU savikaina įmonei / mėn.','Total payroll cost / month');
    if(c.taxMode==='annualAverage'&&c.a1)label('netRate').textContent=t('Metinis NETO išmokos vidurkis / val.','Annual-average net payout / hour');
    if(c.taxMode==='annualAverage'){label('monthlyPay').textContent=c.a1&&c.includePerDiemInNet?t('Metinis NETO išmokos vidurkis / mėn. (su dienpinigiais)','Annual-average net payout / month (including allowance)'):t('Metinis NETO atlyginimo vidurkis / mėn.','Annual-average net salary / month');}
    document.querySelector('.badge').textContent=payroll&&c.taxMode==='annualAverage'?t('Metinis vidurkis','Annual average'):t('Numatomas pelnas','Projected profit');
    $('uplift').closest('.field').hidden=!!c.a1;$('upliftHelp').hidden=!!c.a1;
    $('modeMonthly').textContent=t('NETO → BRUTO / mėnesio DU','Net to gross / monthly payroll');
    $('a1Enabled').checked=!!c.a1;$('includePerDiemInNet').checked=!!c.includePerDiemInNet;
    $('pension2').value=c.pension2?'yes':'no';$('applyNpd').value=c.taxResident&&c.applyNpd?'yes':'no';$('postingCountry').value=c.country;
    [...$('postingCountry').options].forEach(o=>o.textContent=countries[o.value][en()?1:0]);
    [['employerRate2026','employerRate'],['postingDays','days'],['postingRate','perDiemRate'],['localTransport2026','localTransport'],['workwearTools2026','workwearTools']].forEach(([id,key])=>{if(document.activeElement!==$(id))$(id).value=c[key]});
    // Preserve user names and notes verbatim during translation.
    document.querySelectorAll('.scenario-title').forEach((el,i)=>el.textContent=context().state.scenarios[i].name);
    document.querySelector('.navitem').textContent=t('▣ Maržos skaičiuoklė','▣ Margin calculator');
    document.querySelector('.scen-head > div:first-child').innerHTML=`${t('Projektas','Project')} <strong id="scenarioCount">${context().index+1}</strong> / ${context().state.scenarios.length}`;
    $('deleteBtn').disabled=context().state.scenarios.length<=1;
    $('resultTitle').textContent=s.name;
    $('savedMsg').textContent=window.EuroteamsStorage.hasPending()?t('Neišsaugota: naršyklės saugykla nepasiekiama arba pilna. Neuždarykite šio skirtuko.','Not saved: browser storage is unavailable or full. Keep this tab open.'):t('Išsaugota šioje naršyklėje','Saved in this browser');$('savedMsg').classList.toggle('calculation-warning',window.EuroteamsStorage.hasPending());
    const w=Math.max(1,Math.round(Number(s.workers)||1));
    const plural=w%100>=11&&w%100<=19?'darbuotojų':w%10===1?'darbuotojas':w%10>=2&&w%10<=9?'darbuotojai':'darbuotojų';
    $('teamTitle').textContent=t(`${w} ${plural} · mėnesio sumos`,`${w} ${w===1?'worker':'workers'} · monthly totals`);
    $('teamHours').textContent=t(`${w} ${plural} × ${s.hours} val. = ${w*s.hours} klientui pateikiamų valandų / mėn.`,`${w} × ${s.hours} h = ${w*s.hours} billed hours / month`);
    document.querySelectorAll('.scenario-meta').forEach((el,i)=>{const x=context().state.scenarios[i];el.textContent=`${x.clientRate} EUR / ${t('val.','h')} · ${x.hours} ${t('val.','h')} · ${x.workers} ${t(x.workers===1?'darbuotojas':(x.workers%100>=11&&x.workers%100<=19)||x.workers%10===0?'darbuotojų':x.workers%10===1?'darbuotojas':'darbuotojai',x.workers===1?'worker':'workers')}`});
  }
  window.renderPayrollControls=render;
})();
