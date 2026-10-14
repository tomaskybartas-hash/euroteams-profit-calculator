(() => {
  const STORE = 'euroteams-payroll-2026-v1';
  const MMA = 1153;
  const MIN_HOURLY = 7.05;
  const PERDIEM_MONTH_LIMIT = MMA * 1.65;
  const PERDIEM_HOUR_LIMIT = MIN_HOURLY * 1.65;
  const EMPLOYEE_SOC_RATE = 0.195;
  const PENSION2_RATE = 0.03;
  const DEFAULT_EMPLOYER_RATE = 1.77;
  const ANNUAL_36VDU = 83237.40;
  const ANNUAL_60VDU = 138729;

  const COUNTRIES = [
    ['nl','Nyderlandai','Netherlands',64],['fi','Suomija','Finland',69],['ee','Estija','Estonia',47],['se','Švedija','Sweden',70],
    ['es','Ispanija','Spain',58],['pt','Portugalija','Portugal',56],['de','Vokietija','Germany',62],['fr','Prancūzija','France',69],
    ['dk','Danija','Denmark',80],['no','Norvegija','Norway',70],['be','Belgija','Belgium',61],['pl','Lenkija','Poland',48],
    ['lv','Latvija','Latvia',44],['at','Austrija','Austria',69],['ie','Airija','Ireland',69],['it','Italija','Italy',63],
    ['cz','Čekija','Czechia',50],['sk','Slovakija','Slovakia',53],['si','Slovėnija','Slovenia',52],['hr','Kroatija','Croatia',45],
    ['gr','Graikija','Greece',55],['hu','Vengrija','Hungary',48],['ro','Rumunija','Romania',35],['bg','Bulgarija','Bulgaria',39],
    ['cy','Kipras','Cyprus',62],['mt','Malta','Malta',63],['lu','Liuksemburgas','Luxembourg',61],['is','Islandija','Iceland',70],
    ['ch','Šveicarija','Switzerland',80],['li','Lichtenšteinas','Liechtenstein',80],['gb','Didžioji Britanija','United Kingdom',67],
    ['al','Albanija','Albania',33],['ad','Andora','Andorra',46],['ba','Bosnija ir Hercegovina','Bosnia and Herzegovina',43],
    ['me','Juodkalnija','Montenegro',53],['rs','Serbija','Serbia',53],['mk','Šiaurės Makedonija','North Macedonia',40],['xk','Kosovas','Kosovo',40],
    ['md','Moldova','Moldova',53],['ua','Ukraina','Ukraine',53],['tr','Turkija','Turkey',37],['ge','Sakartvelas','Georgia',53],
    ['am','Armėnija','Armenia',47],['az','Azerbaidžanas','Azerbaijan',47],['by','Baltarusija','Belarus',60],['mc','Monakas','Monaco',49],
    ['sm','San Marinas','San Marino',63],['va','Vatikanas','Vatican City',63],['lt','Lietuva','Lithuania',28],
    ['ae','Jungtiniai Arabų Emyratai','United Arab Emirates',60],['cd','Kongo Demokratinė Respublika','Democratic Republic of the Congo',70],
    ['other','Kitos valstybės','Other countries',33]
  ];

  const defaults = () => ({
    gross: 3100,
    contractualHourly: 0,
    a1: 'yes',
    pension2: 'no',
    npd: 'no',
    gpmMode: 'lt',
    employerRate: DEFAULT_EMPLOYER_RATE,
    country: 'nl',
    days: 30,
    accommodation: 0,
    travel: 0,
    localTransport: 0,
    workwear: 0,
    other: 0
  });

  const money = (v, lang) => new Intl.NumberFormat(lang === 'lt' ? 'lt-LT' : 'en-GB', {style:'currency',currency:'EUR',minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(v)||0);
  const pct = v => `${(Number(v)||0).toFixed(2)} %`;
  const n = v => Math.max(0, Number(v) || 0);

  function isEN(){ return document.getElementById('enBtn')?.classList.contains('active'); }
  function lang(){ return isEN() ? 'en' : 'lt'; }
  function tr(lt,en){ return isEN() ? en : lt; }

  function activeIndex(){
    const tabs = [...(document.getElementById('scenarioTabs')?.children || [])];
    const idx = tabs.findIndex(el => {
      const c = el.style.borderColor || '';
      return c.includes('var(--gold)') || c.includes('178, 138, 72');
    });
    return idx >= 0 ? idx : 0;
  }

  function loadStore(){
    try { const x = JSON.parse(localStorage.getItem(STORE)||'null'); return Array.isArray(x) ? x : []; }
    catch { return []; }
  }
  function saveStore(arr){ localStorage.setItem(STORE, JSON.stringify(arr)); }
  function getData(){
    const arr = loadStore(), i = activeIndex();
    if (!arr[i]) { arr[i] = defaults(); saveStore(arr); }
    return {...defaults(), ...arr[i]};
  }
  function setData(data){ const arr = loadStore(), i = activeIndex(); arr[i] = data; saveStore(arr); }

  function countryInfo(code){ return COUNTRIES.find(x=>x[0]===code) || COUNTRIES[0]; }
  function npdFor(income, enabled){
    if (!enabled) return 0;
    if (income <= MMA) return 747;
    return Math.max(0, 747 - 0.49 * (income - MMA));
  }
  function annualRate(annual){ return annual <= ANNUAL_36VDU ? 20 : annual <= ANNUAL_60VDU ? 25 : 32; }
  function annualTax(annual){
    const a = Math.max(0, annual);
    return Math.min(a, ANNUAL_36VDU)*0.20 + Math.min(Math.max(a-ANNUAL_36VDU,0), ANNUAL_60VDU-ANNUAL_36VDU)*0.25 + Math.max(a-ANNUAL_60VDU,0)*0.32;
  }

  function calculate(d){
    const gross = n(d.gross), hourly = n(d.contractualHourly), ci = countryInfo(d.country), perDiem = ci[3] * n(d.days);
    const fullExempt = gross >= PERDIEM_MONTH_LIMIT || hourly >= PERDIEM_HOUR_LIMIT;
    const exemptPerDiem = fullExempt ? perDiem : Math.min(perDiem, gross * 0.5);
    const taxablePerDiem = Math.max(0, perDiem - exemptPerDiem);
    const taxableIncome = gross + taxablePerDiem;
    const socialBase = d.a1 === 'yes' ? taxableIncome : 0;
    const employeeSocial = socialBase * EMPLOYEE_SOC_RATE;
    const pension2 = d.a1 === 'yes' && d.pension2 === 'yes' ? taxableIncome * PENSION2_RATE : 0;
    const npd = npdFor(taxableIncome, d.npd === 'yes');
    const gpmBase = Math.max(0, taxableIncome - npd);
    const gpm = d.gpmMode === 'lt' ? gpmBase * 0.20 : 0;
    const employerSocial = d.a1 === 'yes' ? taxableIncome * (n(d.employerRate)/100) : 0;
    const netSalary = gross - employeeSocial - pension2 - gpm;
    const wageCost = gross + employerSocial;
    const employeePayout = netSalary + exemptPerDiem;
    const extras = n(d.accommodation)+n(d.travel)+n(d.localTransport)+n(d.workwear)+n(d.other);
    const finalCost = wageCost + perDiem + extras;
    const clientRate = n(document.getElementById('clientRate')?.value);
    const hours = n(document.getElementById('hours')?.value);
    const revenue = clientRate * hours;
    const profit = revenue - finalCost;
    const margin = revenue ? profit/revenue*100 : 0;
    const annualized = taxableIncome * 12;
    return {ci,gross,hourly,perDiem,fullExempt,exemptPerDiem,taxablePerDiem,taxableIncome,employeeSocial,pension2,npd,gpmBase,gpm,employerSocial,netSalary,wageCost,employeePayout,extras,finalCost,revenue,profit,margin,annualized,annualRate:annualRate(annualized),annualTax:annualTax(annualized)};
  }

  function setCore(id, value){
    const el = document.getElementById(id); if (!el) return;
    const s = String(value);
    if (el.value !== s) { el.value = s; el.dispatchEvent(new Event('input',{bubbles:true})); }
  }

  function syncCore(d, c){
    const monthlyActive = document.getElementById('modeMonthly')?.classList.contains('active');
    if (!monthlyActive) return;
    setCore('monthlyPay', c.employeePayout);
    setCore('monthlyEmployer', c.wageCost + c.perDiem);
    setCore('housing', n(d.accommodation));
    if (!document.getElementById('travelMonthlyBtn')?.classList.contains('active')) document.getElementById('travelMonthlyBtn')?.click();
    setCore('travelMonthly', n(d.travel));
    setCore('other', n(d.localTransport)+n(d.workwear)+n(d.other));
  }

  function field(id,label,value,type='number',extra=''){
    return `<div class="field"><label for="${id}">${label}</label><input id="${id}" type="${type}" value="${value}" ${type==='number'?'step="0.01" min="0"':''} ${extra}></div>`;
  }
  function yesNo(id,label,val){
    return `<div class="field"><label for="${id}">${label}</label><select id="${id}"><option value="yes" ${val==='yes'?'selected':''}>${tr('TAIP','YES')}</option><option value="no" ${val==='no'?'selected':''}>${tr('NE','NO')}</option></select></div>`;
  }

  function resultRow(label,value,cls='') { return `<div class="p26-row"><span>${label}</span><strong class="${cls}">${value}</strong></div>`; }

  function render(){
    const host = document.getElementById('monthlyFields');
    if (!host) return;
    let wrap = document.getElementById('p26-module');
    const d = getData(), c = calculate(d), L = lang();
    const original = host.querySelector(':scope > .two'); if (original) original.style.display='none';
    if (!wrap) { wrap = document.createElement('div'); wrap.id='p26-module'; host.appendChild(wrap); }

    const countryOptions = COUNTRIES.map(([code,lt,en,rate]) => `<option value="${code}" ${d.country===code?'selected':''}>${isEN()?en:lt} — ${rate.toFixed(2)} €/day</option>`).join('');
    const gpmWarn = d.gpmMode === 'lt' ? '' : `<div class="p26-alert warn">${tr('Pasirinktas ne Lietuvos GPM režimas. Lietuvos GPM šiame mėnesio skaičiavime neskaičiuojamas – būtina patikrinti priimančios valstybės taisykles.','A non-Lithuanian PIT regime is selected. Lithuanian PIT is not calculated in this monthly estimate — host-country rules must be checked.')}</div>`;
    const a1Warn = d.a1 === 'yes' ? '' : `<div class="p26-alert warn">${tr('A1 = NE. Lietuvos socialinio draudimo tarifai šiame skaičiavime netaikomi. Reikia nustatyti, kurios valstybės socialinio draudimo sistema taikoma.','A1 = NO. Lithuanian social insurance rates are not applied in this calculation. The applicable social-security system must be determined.')}</div>`;

    wrap.innerHTML = `
      <style>
        #p26-module{margin-top:16px;border-top:1px solid #e0e6ec;padding-top:18px}
        #p26-module .p26-title{font-size:20px;font-weight:800;color:#17263a;margin:0 0 6px}
        #p26-module .p26-sub{font-size:13px;color:#718296;margin:0 0 16px;line-height:1.45}
        #p26-module .p26-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px 16px}
        #p26-module .p26-wide{grid-column:1/-1}
        #p26-module .p26-rate{padding:10px 12px;border:1px solid #dbe3ea;border-radius:10px;background:#f7f9fb;font-size:13px;color:#42546a}
        #p26-module .p26-results{margin-top:18px;border:1px solid #dbe3ea;border-radius:14px;overflow:hidden;background:#fff}
        #p26-module .p26-results h3{margin:0;padding:14px 16px;background:#f6f8fa;font-size:15px}
        #p26-module .p26-row{display:flex;justify-content:space-between;gap:18px;padding:10px 16px;border-top:1px solid #edf1f4;font-size:13px;align-items:center}
        #p26-module .p26-row strong{font-size:14px;color:#152438;text-align:right}
        #p26-module .p26-row strong.green{color:#16845f}
        #p26-module .p26-row strong.red{color:#b45b55}
        #p26-module .p26-alert{padding:11px 13px;border-radius:10px;margin-top:12px;font-size:12px;line-height:1.45}
        #p26-module .p26-alert.warn{background:#fff7e8;border:1px solid #eed49b;color:#76551c}
        #p26-module .p26-alert.info{background:#eef5fb;border:1px solid #cfdeec;color:#40566e}
        @media(max-width:650px){#p26-module .p26-grid{grid-template-columns:1fr}}
      </style>
      <div class="p26-title">${tr('2026 m. Lietuvos DU, mokesčių ir komandiruočių modulis','2026 Lithuanian payroll, tax & business-trip module')}</div>
      <p class="p26-sub">${tr('Skirta Lietuvos įmonėje įdarbintam darbuotojui, komandiruojamam į užsienį. Skaičiavimas centų tikslumu; tarpiniai dydžiai neapvalinami.','For an employee hired by a Lithuanian company and posted abroad. Results are shown to cents; intermediate values are not rounded early.')}</p>
      <div class="p26-grid">
        ${field('p26-gross',tr('Bruto atlyginimas EUR / mėn.','Gross salary EUR / month'),d.gross)}
        ${field('p26-hourly',tr('Darbo sutartyje nustatytas valandinis atlygis EUR','Contractual hourly wage EUR'),d.contractualHourly)}
        ${yesNo('p26-a1',tr('A1','A1'),d.a1)}
        ${yesNo('p26-pension2',tr('II pakopos pensijų kaupimas','Pillar II pension saving'),d.pension2)}
        ${yesNo('p26-npd',tr('Taikyti NPD','Apply monthly tax-free allowance (NPD)'),d.npd)}
        <div class="field"><label for="p26-gpm">${tr('GPM režimas','PIT regime')}</label><select id="p26-gpm"><option value="lt" ${d.gpmMode==='lt'?'selected':''}>${tr('Lietuva','Lithuania')}</option><option value="host" ${d.gpmMode==='host'?'selected':''}>${tr('Priimanti valstybė','Host country')}</option><option value="check" ${d.gpmMode==='check'?'selected':''}>${tr('Tikrinti','Check')}</option></select></div>
        ${field('p26-employer-rate',tr('Darbdavio įmokų tarifas %','Employer contribution rate %'),d.employerRate)}
        <div class="field"><label for="p26-country">${tr('Komandiruotės šalis','Posting country')}</label><select id="p26-country">${countryOptions}</select></div>
        ${field('p26-days',tr('Komandiruotės kalendorinių dienų skaičius','Calendar days on business trip'),d.days)}
        <div class="p26-rate"><strong>${tr('Maksimali dienpinigių norma','Maximum daily allowance')}:</strong> ${money(c.ci[3],L)} / ${tr('dieną','day')}<br><span>${tr('LRV nutarimas Nr. 526','Government Resolution No. 526')}</span></div>
        ${field('p26-accommodation',tr('Apgyvendinimas EUR / mėn.','Accommodation EUR / month'),d.accommodation)}
        ${field('p26-travel',tr('Kelionės EUR / mėn.','Travel EUR / month'),d.travel)}
        ${field('p26-local',tr('Vietinis transportas EUR / mėn.','Local transport EUR / month'),d.localTransport)}
        ${field('p26-workwear',tr('Darbo rūbai / įrankiai EUR / mėn.','Workwear / tools EUR / month'),d.workwear)}
        ${field('p26-other',tr('Kitos sąnaudos EUR / mėn.','Other costs EUR / month'),d.other)}
        <div class="p26-wide p26-alert info">${tr(`2026 ribos: MMA ${money(MMA,L)}, MVA ${money(MIN_HOURLY,L)}/val.; pilnam neapmokestinamų užsienio dienpinigių taikymui ${money(PERDIEM_MONTH_LIMIT,L)}/mėn. arba ${money(PERDIEM_HOUR_LIMIT,L)}/val.`,`2026 thresholds: MMA ${money(MMA,L)}, minimum hourly wage ${money(MIN_HOURLY,L)}/h; full tax-free foreign per diem threshold ${money(PERDIEM_MONTH_LIMIT,L)}/month or ${money(PERDIEM_HOUR_LIMIT,L)}/h.`)}</div>
      </div>
      ${a1Warn}${gpmWarn}
      <div class="p26-alert warn">${tr('Būtina patikrinti priimančios valstybės komandiruojamų darbuotojų minimalaus atlygio / remuneration reikalavimus.','The host country’s minimum pay / remuneration requirements for posted workers must be checked.')}</div>
      <div class="p26-results">
        <h3>${tr('Darbuotojo atlyginimas ir mokesčiai','Employee pay and taxes')}</h3>
        ${resultRow(tr('Bruto atlyginimas','Gross salary'),money(c.gross,L))}
        ${resultRow(tr('Apmokestinama dienpinigių dalis','Taxable per diem'),money(c.taxablePerDiem,L),c.taxablePerDiem?'red':'')}
        ${resultRow(tr('Apmokestinamos su darbo santykiais susijusios pajamos','Taxable employment income'),money(c.taxableIncome,L))}
        ${resultRow(tr('Darbuotojo socialinio draudimo įmokos (19,50 %)','Employee social insurance contributions (19.50%)'),money(c.employeeSocial,L))}
        ${resultRow(tr('Papildoma II pakopos pensijų įmoka (3 %)','Additional Pillar II pension contribution (3%)'),money(c.pension2,L))}
        ${resultRow(tr('Taikomas NPD','Applied NPD'),money(c.npd,L))}
        ${resultRow(tr('GPM','PIT'),money(c.gpm,L))}
        ${resultRow(tr('Neto atlyginimas','Net salary'),money(c.netSalary,L),'green')}
        <h3>${tr('Darbdavio savikaina ir dienpinigiai','Employer cost and per diem')}</h3>
        ${resultRow(tr('Darbdavio socialinio draudimo įmokos','Employer social insurance contributions'),money(c.employerSocial,L))}
        ${resultRow(tr('Darbo užmokesčio savikaina įmonei','Payroll cost to company'),money(c.wageCost,L))}
        ${resultRow(tr('Dienpinigiai iš viso','Total per diem'),money(c.perDiem,L))}
        ${resultRow(tr('Neapmokestinama dienpinigių dalis','Tax-free per diem'),money(c.exemptPerDiem,L),'green')}
        ${resultRow(tr('Apmokestinama dienpinigių dalis','Taxable per diem'),money(c.taxablePerDiem,L),c.taxablePerDiem?'red':'')}
        ${resultRow(tr('Darbuotojui išmokama suma (NETO DU + neapmokestinami dienpinigiai)','Employee payout (net salary + tax-free per diem)'),money(c.employeePayout,L),'green')}
        ${resultRow(tr('Galutinė darbuotojo savikaina įmonei','Final employee cost to company'),money(c.finalCost,L))}
        <h3>${tr('Projekto marža','Project margin')}</h3>
        ${resultRow(tr('Pajamos iš kliento','Client revenue'),money(c.revenue,L))}
        ${resultRow(tr('Pelnas EUR','Profit EUR'),money(c.profit,L),c.profit>=0?'green':'red')}
        ${resultRow(tr('Pelno marža %','Profit margin %'),pct(c.margin),c.margin>=0?'green':'red')}
        <h3>${tr('Metinių GPM ribų informacija','Annual PIT thresholds')}</h3>
        ${resultRow(tr('Metinės apmokestinamos pajamos (mėnesio sumos × 12)','Annualized taxable income (monthly amount × 12)'),money(c.annualized,L))}
        ${resultRow(tr('Informacinis metinis tarifas pagal ribą','Indicative annual bracket'),pct(c.annualRate))}
        ${resultRow(tr('Informacinis progresinis GPM be metinio NPD korekcijų','Indicative progressive annual PIT before annual NPD adjustments'),money(c.annualTax,L))}
      </div>`;

    const ids = ['gross','hourly','a1','pension2','npd','gpm','employer-rate','country','days','accommodation','travel','local','workwear','other'];
    const map = {gross:'gross',hourly:'contractualHourly',a1:'a1',pension2:'pension2',npd:'npd',gpm:'gpmMode','employer-rate':'employerRate',country:'country',days:'days',accommodation:'accommodation',travel:'travel',local:'localTransport',workwear:'workwear',other:'other'};
    ids.forEach(k => {
      const el = document.getElementById(`p26-${k}`); if (!el) return;
      el.addEventListener('input', () => {
        const x = getData(); const prop = map[k];
        x[prop] = ['a1','pension2','npd','gpm','country'].includes(k) ? el.value : n(el.value);
        setData(x); const cc = calculate(x); syncCore(x,cc); render();
      });
      el.addEventListener('change', () => el.dispatchEvent(new Event('input')));
    });
    syncCore(d,c);
  }

  function visibility(){
    const host = document.getElementById('monthlyFields');
    if (!host) return;
    const active = document.getElementById('modeMonthly')?.classList.contains('active');
    const module = document.getElementById('p26-module');
    if (module) module.style.display = active ? '' : 'none';
  }

  let timer;
  function schedule(ms=30){ clearTimeout(timer); timer=setTimeout(()=>{ render(); visibility(); },ms); }

  document.addEventListener('click', e => {
    if (e.target.closest('#deleteBtn')) {
      const idx = activeIndex(); const arr = loadStore(); if (arr.length) { arr.splice(idx,1); saveStore(arr); }
      schedule(80); return;
    }
    if (e.target.closest('#addBtn')) { setTimeout(()=>{ const arr=loadStore(); while(arr.length <= activeIndex()) arr.push(defaults()); saveStore(arr); schedule(); },70); return; }
    if (e.target.closest('#scenarioTabs') || e.target.closest('#modeMonthly') || e.target.closest('#modeHourly') || e.target.closest('#ltBtn') || e.target.closest('#enBtn') || e.target.closest('#resetBtn')) schedule(80);
  }, true);

  ['clientRate','hours','workers'].forEach(id => document.getElementById(id)?.addEventListener('input',()=>schedule(10)));
  window.addEventListener('load',()=>schedule(50));
  schedule(100);
})();