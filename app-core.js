const PASSWORD_HASH='341a26f1252120f6705cd9ecfb5d502fe10b188f20ab6a99a73af5dc14b10159';const KEY='euroteams-profit-calculator-v3';const base={name:'Alano Gamykla su nekvalifikuotais darb.',clientRate:27,hours:200,workers:1,costMode:'hourly',netRate:12.5,uplift:59,monthlyPay:2500,monthlyEmployer:3975,housing:0,travelMode:'monthly',travelMonthly:0,travelRotation:0,other:0,rotation:'6/2',workWeeks:6,homeWeeks:2,notes:''};const partner={name:'Partneris · mėnesinės pasiūlymo sumos',clientRate:27,hours:180,workers:1,costMode:'monthly',netRate:13.5,uplift:30,monthlyPay:2120,monthlyEmployer:3275,housing:0,travelMode:'monthly',travelMonthly:0,travelRotation:0,other:0,rotation:'6/2',workWeeks:6,homeWeeks:2,notes:'NETO: 2 120 EUR / month.'};let st;try{st=JSON.parse(window.EuroteamsStorage.getItem(KEY)||'null')}catch(e){}if(!st||!Array.isArray(st.scenarios))st={lang:'lt',selected:0,scenarios:[structuredClone(base)]};st.scenarios=st.scenarios.length?st.scenarios.map(s=>({...structuredClone(base),...s})): [structuredClone(base)];st.scenarios.forEach(s=>{for(const k of Object.keys(base))if(typeof base[k]==='number')s[k]=window.EuroteamsInput.normalize(s[k],['workers','workWeeks'].includes(k)?1:0);});st.selected=Math.max(0,Math.min(Math.trunc(Number(st.selected)||0),st.scenarios.length-1));const $=id=>document.getElementById(id),num=v=>window.EuroteamsInput.normalize(v),cur=()=>st.scenarios[st.selected];function money(v){return new Intl.NumberFormat(st.lang==='lt'?'lt-LT':'en-GB',{style:'currency',currency:'EUR',minimumFractionDigits:2}).format(v||0)}function pct(v){return new Intl.NumberFormat(st.lang==='lt'?'lt-LT':'en-GB',{minimumFractionDigits:2,maximumFractionDigits:2}).format(v||0)+' %'}function rot(s){if(s.rotation==='custom')return[Math.max(1,num(s.workWeeks)),num(s.homeWeeks)];return s.rotation.split('/').map(Number)}function save(){window.EuroteamsStorage.setItem(KEY,JSON.stringify(st));if($('savedMsg'))$('savedMsg').textContent=st.lang==='lt'?'Išsaugota šioje naršyklėje':'Saved in this browser'}function esc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}function t(lt,en){return st.lang==='lt'?lt:en}function renderTabs(){const b=$('scenarioTabs');b.innerHTML='';st.scenarios.forEach((s,i)=>{const c=window.EuroteamsCalculator.calculateScenario(s,i),x=document.createElement('button');x.className='scenario-tab';x.style.borderColor=i===st.selected?'var(--gold)':'#d9dee3';x.innerHTML=`<div><div class="scenario-title">${esc(s.name)}</div><div class="scenario-meta">${money(s.clientRate)} / val. · ${s.hours} val. · ${c.workers} ${t(c.workers===1?'darbuotojas':'darbuotojų',c.workers===1?'worker':'workers')}</div></div><div class="scenario-profit"><strong>${money(c.teamProfit)}</strong><span>${t('komanda / mėn.','team / month')}</span></div>`;x.onclick=()=>{st.selected=i;render(true)};x.setAttribute('aria-pressed',String(i===st.selected));b.appendChild(x)})}function render(forceInputs=false){
  const s=cur();
  $('ltBtn').classList.toggle('active',st.lang==='lt');
  $('enBtn').classList.toggle('active',st.lang==='en');
  renderTabs();
  ['nameInput','clientRate','hours','workers','netRate','uplift','monthlyPay','housing','travelMonthly','travelRotation','other','rotation','workWeeks','homeWeeks','notes'].forEach(id=>{
    if(forceInputs||document.activeElement!==$(id))$(id).value=s[id==='nameInput'?'name':id]??'';
  });
  for(const [id,active] of [['modeHourly',s.costMode==='hourly'],['modeMonthly',s.costMode==='monthly'],['travelMonthlyBtn',s.travelMode==='monthly'],['travelRotationBtn',s.travelMode==='rotation']])$(id).classList.toggle('active',active);
  for(const [id,hidden] of [['hourlyFields',s.costMode!=='hourly'],['monthlyFields',s.costMode!=='monthly'],['travelMonthlyField',s.travelMode!=='monthly'],['travelRotationField',s.travelMode!=='rotation'],['customRotation',s.rotation!=='custom']])$(id).classList.toggle('hidden',hidden);
  const [w,h]=rot(s);
  $('rotationHelp').textContent=t(`${w}/${h} · ${w} sav. komandiruotėje / ${h} sav. namuose. Visas ciklas: ${w+h} sav. Mėnesio valandos lieka įvestos; poilsis namuose jų automatiškai nesumažina.`,`${w} weeks work / ${h} weeks home. Total cycle ${w+h} weeks. Monthly hours remain as entered.`);
  $('upliftHelp').textContent=t(`Papildomos darbdavio išlaidos pridedamos kaip atlyginimo į rankas procentas. Pavyzdys: ${money(s.netRate)} į rankas + ${money(num(s.netRate)*num(s.uplift)/100)} papildomų išlaidų (${s.uplift} %) = ${money(num(s.netRate)*(1+num(s.uplift)/100))} už valandą. Tai prielaida, o ne patvirtintas mokesčių tarifas.`,`Additional employer costs are added as a percentage of net pay. This is an assumption, not a verified tax rate.`);
  save();
  window.applyEuroteamsLanguage(st.lang);
  window.renderPayrollControls();
  window.applyEuroteamsResults();
  renderSavedExamples();
}
const fields=['nameInput','clientRate','hours','workers','netRate','uplift','monthlyPay','monthlyEmployer','housing','travelMonthly','travelRotation','other','rotation','workWeeks','homeWeeks','notes'];fields.forEach(id=>$(id).addEventListener('input',e=>{const s=cur(),k=id==='nameInput'?'name':id;if(['name','rotation','notes'].includes(k))s[k]=e.target.value;else if(k==='workers')s[k]=Math.max(1,Math.round(num(e.target.value)));else s[k]=num(e.target.value);render()}));$('modeHourly').onclick=()=>{cur().costMode='hourly';render()};$('modeMonthly').onclick=()=>{cur().costMode='monthly';render()};$('travelMonthlyBtn').onclick=()=>{cur().travelMode='monthly';render()};$('travelRotationBtn').onclick=()=>{cur().travelMode='rotation';render()};$('presetSelect').onchange=loadSavedExample;$('addBtn').onclick=()=>{const a=readPayrollSettings();delete a[String(st.scenarios.length)];window.EuroteamsStorage.setItem('euroteams-payroll-2026-v4',JSON.stringify(a));st.scenarios.push({...structuredClone(base),name:t('Naujas scenarijus ','New scenario ')+(st.scenarios.length+1)});st.selected=st.scenarios.length-1;render()};$('deleteBtn').onclick=()=>{if(st.scenarios.length<=1)return;const a=readPayrollSettings(),next={};st.scenarios.forEach((_,i)=>{if(i!==st.selected&&a[i])next[i>st.selected?i-1:i]=a[i]});window.EuroteamsStorage.setItem('euroteams-payroll-2026-v4',JSON.stringify(next));st.scenarios.splice(st.selected,1);st.selected=Math.max(0,st.selected-1);render()};$('resetBtn').onclick=()=>{window.EuroteamsStorage.removeItem('euroteams-payroll-2026-v4');st.scenarios=[structuredClone(base)];st.selected=0;render()};function setLang(l){st.lang=l;if($('exampleStatus'))$('exampleStatus').textContent='';$('ltBtn').classList.toggle('active',l==='lt');$('enBtn').classList.toggle('active',l==='en');render()}$('ltBtn').onclick=()=>setLang('lt');$('enBtn').onclick=()=>setLang('en');$('loginLt').onclick=()=>{st.lang='lt';$('loginTitle').textContent='Euroteams prisijungimas';$('loginText').textContent='Prisijunkite bendru įmonės slaptažodžiu, kad atidarytumėte skaičiuoklę.'};$('loginEn').onclick=()=>{st.lang='en';$('loginTitle').textContent='Euroteams login';$('loginText').textContent='Sign in with the shared company password to open the calculator.'};$('logoutBtn').onclick=()=>{sessionStorage.removeItem('et-auth');$('app').classList.add('hidden');$('login').classList.remove('hidden')};async function sha(s){const b=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s));return[...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,'0')).join('')}async function login(){if(await sha($('password').value)===PASSWORD_HASH){sessionStorage.setItem('et-auth',Date.now());$('login').classList.add('hidden');$('app').classList.remove('hidden');$('loginMsg').textContent='';render()}else $('loginMsg').textContent=t('Neteisingas slaptažodis. Bandykite dar kartą.','Incorrect password. Please try again.')}$('loginBtn').onclick=login;$('password').onkeydown=e=>{if(e.key==='Enter')login()};if(Number(sessionStorage.getItem('et-auth')||0)&&Date.now()-Number(sessionStorage.getItem('et-auth'))<86400000){$('login').classList.add('hidden');$('app').classList.remove('hidden')}
window.renderEuroteamsCore=render;

function readPayrollSettings(){try{return JSON.parse(window.EuroteamsStorage.getItem('euroteams-payroll-2026-v4')||'{}')||{}}catch{return {}}}

window.addEventListener('storage',event=>{
  if(event.key==='euroteams-profit-calculator-v3'){
    try{const next=JSON.parse(event.newValue);if(next?.scenarios?.length){st=next;st.scenarios=st.scenarios.map(s=>({...structuredClone(base),...s}));st.selected=Math.max(0,Math.min(Math.trunc(Number(st.selected)||0),st.scenarios.length-1));render()}}catch{}
  }else if(event.key==='euroteams-payroll-2026-v4'||event.key===EXAMPLES_KEY)render();
});

// Saved examples contain independent copies of every project and payroll assumption.
var EXAMPLES_KEY='euroteams-saved-examples-v1';
function readSavedExamples(){
  try{const data=JSON.parse(window.EuroteamsStorage.getItem('euroteams-saved-examples-v1')||'null');if(data&&Array.isArray(data.items))return data}catch{}
  return {items:[{id:'factory',name:'Gamykla · 12,50 EUR NETO / val. · 200 val.',scenario:structuredClone(base),payroll:{}},{id:'partner',name:'Partneris · mėnesinis NETO atlyginimas',scenario:structuredClone(partner),payroll:{}}]};
}
function renderSavedExamples(){
  const select=$('presetSelect');if(!select)return;
  if(!$('saveExampleBtn')){
    const controls=document.createElement('div');controls.className='saved-example-controls';
    controls.innerHTML='<label for="exampleName" id="exampleNameLabel"></label><input id="exampleName" maxlength="120"><div class="saved-example-actions"><button type="button" class="btn" id="saveExampleBtn"></button><button type="button" class="btn danger" id="deleteExampleBtn"></button></div><div class="help" id="examplesHelp"></div><div role="status" aria-live="polite" id="exampleStatus"></div>';
    select.after(controls);
    $('saveExampleBtn').onclick=()=>{
      const name=$('exampleName').value.trim()||cur().name.trim();if(!name){$('exampleName').focus();return}
      const data=readSavedExamples(),id='saved-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
      data.items.push({id,name,scenario:structuredClone(cur()),payroll:structuredClone(readPayrollSettings()[st.selected]||{})});
      window.EuroteamsStorage.setItem('euroteams-saved-examples-v1',JSON.stringify(data));
      renderSavedExamples();select.value=id;$('exampleName').value='';$('deleteExampleBtn').disabled=false;
      $('exampleStatus').textContent=window.EuroteamsStorage.hasPending()?t('Nepavyko išsaugoti naršyklėje. Pavyzdys liko tik šiame lange.','Browser storage failed. Example is kept only in this window.'):t('Pavyzdys išsaugotas.','Example saved.');
    };
    $('deleteExampleBtn').onclick=()=>{
      const data=readSavedExamples(),id=select.value;if(!data.items.some(x=>x.id===id))return;
      data.items=data.items.filter(x=>x.id!==id);window.EuroteamsStorage.setItem('euroteams-saved-examples-v1',JSON.stringify(data));renderSavedExamples();
      $('exampleStatus').textContent=window.EuroteamsStorage.hasPending()?t('Ištrinta tik šiame lange: naršyklės saugykla nepasiekiama.','Deleted only in this window: browser storage unavailable.'):t('Pavyzdys ištrintas. Projekto duomenys palikti.','Example deleted. Project data retained.');
    };
  }
  const selected=select.value;select.replaceChildren(new Option(t('Pasirinkite pavyzdį…','Choose an example…'),''));
  for(const item of readSavedExamples().items)select.add(new Option(item.id==='factory'?t('Gamykla · 12,50 EUR NETO / val. · 200 val.','Factory · EUR 12.50 net / hour · 200 h'):item.id==='partner'?t('Partneris · mėnesinis NETO atlyginimas','Partner · monthly net salary'):item.name,item.id));
  select.value=selected;if(select.selectedIndex<0)select.value='';
  $('deleteExampleBtn').disabled=!select.value;
  $('saveExampleBtn').textContent=t('+ Išsaugoti kaip pavyzdį','+ Save as example');
  $('deleteExampleBtn').textContent=t('Ištrinti pasirinktą pavyzdį','Delete selected example');
  $('exampleNameLabel').textContent=t('Naujo pavyzdžio pavadinimas','New example name');
  $('exampleName').placeholder=t('Neįvedus naudojamas projekto pavadinimas','Defaults to the project name');
  $('examplesHelp').textContent=t('Išsaugomi visi šio projekto laukai, A1, dienpinigiai ir mokesčių nustatymai šioje naršyklėje.','Saves all current project fields, A1, per diem and tax settings in this browser.');
}
function loadSavedExample(event){
  const item=readSavedExamples().items.find(x=>x.id===event.target.value);if(!item)return;
  const a=readPayrollSettings();a[st.selected]=structuredClone(item.payroll||{});window.EuroteamsStorage.setItem('euroteams-payroll-2026-v4',JSON.stringify(a));
  st.scenarios[st.selected]={...structuredClone(base),...structuredClone(item.scenario)};
  $('exampleStatus').textContent='';render(true);
}
