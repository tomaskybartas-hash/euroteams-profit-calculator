// Run with JSDOM_PATH=/path/to/jsdom node tests/calculator.test.cjs
const {JSDOM}=require(process.env.JSDOM_PATH||'jsdom');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
function boot(saved){
 const d=new JSDOM(fs.readFileSync(path.join(root,'index.html'),'utf8'),{url:'https://calculator.test/',runScripts:'outside-only'}),w=d.window;
 w.structuredClone=structuredClone;
 if(saved)for(const [k,v] of Object.entries(saved))w.localStorage.setItem(k,v);
 for(const f of ['safe-storage.js','app-core.js','full-language.js','payroll-controls.js','tax-rules-2026.js','canonical-results.js'])w.eval(fs.readFileSync(path.join(root,f),'utf8'));
 w.renderEuroteamsCore();return w;
}
let w=boot();let count=0;
const ok=(condition,msg)=>{assert.ok(condition,msg);count++};
const el=id=>w.document.getElementById(id);
function input(id,value){el(id).value=String(value);el(id).dispatchEvent(new w.Event('input',{bubbles:true}));}
function change(id,value){if(el(id).type==='checkbox')el(id).checked=value;else el(id).value=value;el(id).dispatchEvent(new w.Event('change',{bubbles:true}));}
const last=()=>w.__euroteamsCanonicalLast.c;
const near=(a,b)=>Math.abs(a-b)<.011;
ok(w.__euroteamsCanonicalTests.passed,'Original audit payroll reference cases');
ok(near(last().workerTotal,3975),'Legacy hourly calculation preserved');
el('modeMonthly').click();input('monthlyPay',2300);
ok(near(last().base.gross,3801.65289256),'2300 net → gross');ok(near(last().workerTotal,3868.94214876),'Payroll cost excludes duplicate employee tax');
change('pension2','yes');ok(near(last().base.gross,4000)&&near(last().workerTotal,4070.80),'Pension reference example');
change('pension2','no');change('a1Enabled',true);change('includePerDiemInNet',false);
ok(near(last().post.paidToEmployee,4220)&&near(last().workerTotal,5788.94214876),'Allowance added to net reference example');
input('postingRate',80);ok(near(last().post.exemptPerDiem,1920)&&near(last().post.taxablePerDiem,480),'Country maximum caps tax-free allowance');input('postingRate',64);
change('includePerDiemInNet',true);ok(near(last().post.paidToEmployee,2300),'Allowance INCLUDED in net target');
ok(near(Number(el('monthlyEmployer').value),last().base.payrollCost),'Read-only payroll cost agrees');
const before=last().workerTotal;el('enBtn').click();ok(near(last().workerTotal,before),'Language switch preserves amounts');
ok(el('a1EnabledLabel').textContent==='Calculate with A1 posting','A1 translation synchronous');
ok(el('pension2').options[0].textContent==='NO','Options translated');
ok(!/val\.|mėn\./.test(w.document.querySelector('.scenario-meta').textContent),'English units translated');
change('postingCountry','DE');ok(el('postingRate').value==='62','Country updates rate');input('postingDays',20);ok(near(last().post.totalPerDiem,1240),'Days recalculate allowance');
input('postingDays',35);ok(last().cfg.days===31,'Calendar days normalized to maximum 31');input('shortDays',8);ok(last().cfg.shortDays===2,'Short days capped at two');input('postingDays',1);ok(last().cfg.shortDays===1,'Short-day count cannot exceed calendar days');input('postingDays',20);input('shortDays',0);
input('localTransport2026',100);input('workwearTools2026',50);ok(near(last().projectExtras,150),'Extra costs included');
el('tableWorkers').focus();input('tableWorkers',2);ok(w.document.activeElement.id==='tableWorkers','Table editing retains focus');ok(last().workers===2,'Result table worker count recalculates immediately');input('workers',1);
const first=last().workerTotal;el('addBtn').click();ok(!last().cfg.a1,'New scenario does not inherit A1');input('nameInput','QA independent');input('clientRate',40);change('a1Enabled',true);input('postingRate',69);const second=last().workerTotal;
w.document.querySelectorAll('.scenario-tab')[0].click();ok(near(last().workerTotal,first)&&last().cfg.country==='DE','First scenario settings preserved');
el('deleteBtn').click();ok(el('nameInput').value==='QA independent'&&near(last().workerTotal,second)&&last().cfg.perDiemRate===69,'Deletion reindexes payroll settings');
change('a1Enabled',false);ok(near(last().workerTotal,3975),'A1 off excludes allowance');
input('localTransport2026',100);ok(near(last().workerTotal,4075),'Local transport counted in legacy hourly mode');
for(const [id,value] of [['clientRate',-10],['hours',''],['workers',0],['netRate',-1],['housing',-20],['other','']])input(id,value);
ok(Number.isFinite(last().profit)&&last().workers===1&&last().revenue===0,'Invalid and empty inputs remain finite');
el('modeMonthly').click();change('a1Enabled',true);input('monthlyPay',0);
ok(el('a1Status').className==='calculation-warning','Impossible included payout is explained');
el('resetBtn').click();ok(!last().cfg.a1&&last().cfg.localTransport===0,'Reset clears payroll settings');
for(let i=0;i<12;i++)el('addBtn').click();ok(w.document.querySelectorAll('.scenario-tab').length===13,'No artificial scenario limit');
input('nameInput','Saved project');input('clientRate',41);change('a1Enabled',true);input('postingDays',12);const old=last().workerTotal;
let saved={};for(let i=0;i<w.localStorage.length;i++){let k=w.localStorage.key(i);saved[k]=w.localStorage.getItem(k)}w=boot(saved);
ok(el('nameInput').value==='Saved project'&&near(last().workerTotal,old)&&last().cfg.days===12,'Reload restores inputs and payroll settings');
ok(near(w.__euroteamsCanonicalLast.allCost,w.__euroteamsCanonicalLast.allRevenue-w.__euroteamsCanonicalLast.allProfit),'All-scenario totals balance');
for(const row of el('resultTableBody').rows)ok(!/NaN|Infinity|undefined|null/.test(row.textContent),'Finite table row');
w.close();console.log(`${count} assertions passed`);
