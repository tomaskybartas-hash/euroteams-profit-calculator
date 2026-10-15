(() => {
  'use strict';
  const KEY='euroteams-payroll-2026-v4', MAIN='euroteams-profit-calculator-v3';
  const $=id=>document.getElementById(id);
  const en=()=>$('enBtn').classList.contains('active'), t=(lt,eng)=>en()?eng:lt;
  const defaults={pension2:false,applyNpd:false,employerRate:1.77,localTransport:0,workwearTools:0,a1:false,includePerDiemInNet:true,country:'NL',days:30,perDiemRate:64};
  const countries={NL:['Nyderlandai','Netherlands',64],DE:['Vokietija','Germany',62],FR:['Prancūzija','France',69],FI:['Suomija','Finland',69],SE:['Švedija','Sweden',70],DK:['Danija','Denmark',80],NO:['Norvegija','Norway',70],EE:['Estija','Estonia',47],ES:['Ispanija','Spain',58],PT:['Portugalija','Portugal',56],BE:['Belgija','Belgium',61],AT:['Austrija','Austria',69],OTHER:['Kita','Other',0]};
  window.EuroteamsDailyRates=countries;
  function read(key,fallback){try{return JSON.parse(localStorage.getItem(key))||fallback}catch{return fallback}}
  function context(){const state=read(MAIN,{selected:0,scenarios:[]});return {state,index:state.selected,scenario:state.scenarios[state.selected]||{}}}
  function config(){return {...defaults,...read(KEY,{})[context().index]}}
  function save(patch){const all=read(KEY,{}),i=context().index;all[i]={...config(),...patch};localStorage.setItem(KEY,JSON.stringify(all));window.renderEuroteamsCore()}
  const field=(id,label,type='number')=>`<div class="field"><label for="${id}" id="${id}Label">${label}</label><input id="${id}" type="${type}" min="0" step="0.01"></div>`;
  const select=(id)=>`<div class="field"><label for="${id}" id="${id}Label"></label><select id="${id}"><option value="no"></option><option value="yes"></option></select></div>`;
  const toggle=(id)=>`<div class="field check-field"><label for="${id}"><input id="${id}" type="checkbox"><span id="${id}Label"></span></label></div>`;
  function ensure(){
    if($('payrollControls'))return;
    const box=document.createElement('section');box.id='payrollControls';
    box.innerHTML=toggle('a1Enabled')+`<div id="payrollParameters"><div class="two">${select('pension2')}${select('applyNpd')}</div>${field('employerRate2026','')}<div class="help" id="payrollRateHelp"></div></div><div id="a1Details">${toggle('includePerDiemInNet')}<p class="help" id="includePerDiemHelp"></p><div class="field"><label for="postingCountry" id="postingCountryLabel"></label><select id="postingCountry"></select></div><div class="two">${field('postingDays','')}${field('postingRate','')}</div><p class="help" id="rateHint"></p><p class="help" id="a1Note"></p><div id="a1Status" role="status"></div></div><details id="payrollDetail"><summary id="payrollBreakdownTitle"></summary><div id="payrollBreakdown" class="metrics"></div></details><div class="subhead" id="extraProjectCostsTitle"></div><div class="two">${field('localTransport2026','')}${field('workwearTools2026','')}</div>`;
    $('monthlyFields').insertAdjacentElement('afterend',box);
    Object.keys(countries).forEach(code=>{const opt=document.createElement('option');opt.value=code;$('postingCountry').appendChild(opt)});
    [['a1Enabled','a1'],['includePerDiemInNet','includePerDiemInNet']].forEach(([id,key])=>$(id).addEventListener('change',e=>save({[key]:e.target.checked})));
    [['pension2','pension2'],['applyNpd','applyNpd']].forEach(([id,key])=>$(id).addEventListener('change',e=>save({[key]:e.target.value==='yes'})));
    [['employerRate2026','employerRate'],['postingDays','days'],['postingRate','perDiemRate'],['localTransport2026','localTransport'],['workwearTools2026','workwearTools']].forEach(([id,key])=>{
      $(id).addEventListener('input',e=>{const v=Number(e.target.value);save({[key]:Number.isFinite(v)?Math.max(0,v):0})});
      $(id).addEventListener('blur',e=>{if(e.target.value!=='')e.target.value=String(config()[key])});
    });
    $('postingDays').step='1';
    $('postingCountry').addEventListener('change',e=>save({country:e.target.value,perDiemRate:countries[e.target.value][2]}));
    document.querySelectorAll('input[type=number]').forEach(el=>{el.min=['workers','workWeeks'].includes(el.id)?'1':'0';if(!['workers','workWeeks','homeWeeks'].includes(el.id))el.step='0.01';el.addEventListener('blur',()=>{const min=Number(el.min)||0;if((el.value!==''&&Number(el.value)<min)||(el.value===''&&min>0)){el.value=String(min);el.dispatchEvent(new Event('input',{bubbles:true}));}});});
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
    put('payrollRateHelp',t('Numatyta 1,77 %. NPD skaičiuojamas pagal 2026 m. mėnesio formulę. GPM 20 %; metinis progresinis GPM ir Sodros lubos nevertinami.','Default employer rate: 1.77%. NPD uses the 2026 monthly formula. Income tax: 20%; annual progressive tax and social security caps are excluded.'));
    put('postingCountryLabel',t('Komandiruotės šalis','Posting country'));put('postingDaysLabel',t('Komandiruotės dienos / mėn.','Posting days / month'));put('postingRateLabel',t('Dienpinigių norma EUR / dieną','Daily allowance EUR / day'));
    put('rateHint',t('Šalis parenka dienos normą; ją galite koreguoti. Kitai šaliai įveskite patikrintą normą. Dienos gali būti perskaičiuotos į visos dienos ekvivalentą.','Country selects the daily rate; you can edit it. For Other, enter a verified rate. Days may be entered as full-day equivalents.'));
    put('a1Note',t('A1 patvirtina taikomą socialinio draudimo valstybę. Dienpinigių lengvata čia vertinama pagal apskaičiuotą DU; būtina sutikrinti su sutartiniu atlygiu ir šalies norma.','A1 confirms the applicable social security system. This estimate uses calculated pay for allowance relief; verify contractual pay and the country limit.'));
    put('payrollBreakdownTitle',t('Darbo užmokesčio ir dienpinigių išklotinė','Payroll and daily allowance breakdown'));
    put('extraProjectCostsTitle',t('Atskiros projekto sąnaudos','Additional project costs'));put('localTransport2026Label',t('Vietinis transportas / mėn.','Local transport / month'));put('workwearTools2026Label',t('Darbo rūbai / įrankiai / mėn.','Workwear / tools / month'));
    const label=id=>$(id).closest('.field').querySelector('label');
    label('netRate').textContent=c.a1&&c.includePerDiemInNet?t('Bendra NETO išmoka / val. (su dienpinigiais)','Total net payout / hour (including allowance)'):t('Darbuotojo NETO atlyginimas / val.','Employee net salary / hour');
    label('monthlyPay').textContent=c.a1&&c.includePerDiemInNet?t('Bendra NETO išmoka / mėn. (su dienpinigiais)','Total net payout / month (including allowance)'):t('Darbuotojo NETO atlyginimas / mėn.','Employee net salary / month');
    label('monthlyEmployer').textContent=t('DU savikaina įmonei / mėn.','Total payroll cost / month');
    $('uplift').closest('.field').hidden=!!c.a1;$('upliftHelp').hidden=!!c.a1;
    $('modeMonthly').textContent=t('NETO → BRUTO / mėnesio DU','Net to gross / monthly payroll');
    $('a1Enabled').checked=!!c.a1;$('includePerDiemInNet').checked=!!c.includePerDiemInNet;
    $('pension2').value=c.pension2?'yes':'no';$('applyNpd').value=c.applyNpd?'yes':'no';$('postingCountry').value=c.country;
    [...$('postingCountry').options].forEach(o=>o.textContent=countries[o.value][en()?1:0]);
    [['employerRate2026','employerRate'],['postingDays','days'],['postingRate','perDiemRate'],['localTransport2026','localTransport'],['workwearTools2026','workwearTools']].forEach(([id,key])=>{if(document.activeElement!==$(id))$(id).value=c[key]});
    // Preserve user names and notes verbatim during translation.
    document.querySelectorAll('.scenario-title').forEach((el,i)=>el.textContent=context().state.scenarios[i].name);
    document.querySelector('.navitem').textContent=t('▣ Maržos skaičiuoklė','▣ Margin calculator');
    document.querySelector('.scen-head > div:first-child').innerHTML=`${t('Projektas','Project')} <strong id="scenarioCount">${context().index+1}</strong> / ${context().state.scenarios.length}`;
    $('deleteBtn').disabled=context().state.scenarios.length<=1;
    $('resultTitle').textContent=s.name;
    $('presetSelect').options[1].textContent=t('Gamykla · 12,50 EUR NETO / val. · 200 val.','Factory · EUR 12.50 net / hour · 200 h');
    $('presetSelect').options[2].textContent=t('Partneris · mėnesinis NETO atlyginimas','Partner · monthly net salary');
    $('savedMsg').textContent=t('Išsaugota šioje naršyklėje','Saved in this browser');
    const w=Math.max(1,Math.round(Number(s.workers)||1));
    const plural=w%100>=11&&w%100<=19?'darbuotojų':w%10===1?'darbuotojas':w%10>=2&&w%10<=9?'darbuotojai':'darbuotojų';
    $('teamTitle').textContent=t(`${w} ${plural} · mėnesio sumos`,`${w} ${w===1?'worker':'workers'} · monthly totals`);
    $('teamHours').textContent=t(`${w} ${plural} × ${s.hours} val. = ${w*s.hours} klientui pateikiamų valandų / mėn.`,`${w} × ${s.hours} h = ${w*s.hours} billed hours / month`);
    document.querySelectorAll('.scenario-meta').forEach((el,i)=>{const x=context().state.scenarios[i];el.textContent=`${x.clientRate} EUR / ${t('val.','h')} · ${x.hours} ${t('val.','h')} · ${x.workers} ${t(x.workers===1?'darbuotojas':(x.workers%100>=11&&x.workers%100<=19)||x.workers%10===0?'darbuotojų':x.workers%10===1?'darbuotojas':'darbuotojai',x.workers===1?'worker':'workers')}`});
  }
  window.renderPayrollControls=render;
})();
