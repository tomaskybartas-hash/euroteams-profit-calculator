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

let w=boot();const el=id=>w.document.getElementById(id);const input=(id,value)=>{el(id).value=value;el(id).dispatchEvent(new w.Event('input',{bubbles:true}))};
input('nameInput','My saved project');input('clientRate',44);el('modeMonthly').click();el('a1Enabled').checked=true;el('a1Enabled').dispatchEvent(new w.Event('change',{bubbles:true}));input('postingRate',70);input('exampleName','Custom <example>');el('saveExampleBtn').click();const id=el('presetSelect').value;assert.ok(id.startsWith('saved-'));
input('clientRate',99);input('postingRate',20);el('presetSelect').value=id;el('presetSelect').dispatchEvent(new w.Event('change',{bubbles:true}));assert.equal(el('clientRate').value,'44');assert.equal(el('postingRate').value,'70');assert.equal(el('a1Enabled').checked,true);
el('enBtn').click();assert.equal(el('saveExampleBtn').textContent,'+ Save as example');assert.equal(el('presetSelect').selectedOptions[0].textContent,'Custom <example>');
const saved=Object.fromEntries(Object.keys(w.localStorage).map(k=>[k,w.localStorage.getItem(k)]));w.close();w=boot(saved);assert.ok([...el('presetSelect').options].some(o=>o.value===id));el('presetSelect').value=id;el('presetSelect').dispatchEvent(new w.Event('change',{bubbles:true}));el('deleteExampleBtn').click();assert.ok(![...el('presetSelect').options].some(o=>o.value===id));assert.equal(el('clientRate').value,'44');
for(const value of ['factory','partner']){el('presetSelect').value=value;el('presetSelect').dispatchEvent(new w.Event('change',{bubbles:true}));el('deleteExampleBtn').click()};assert.equal(el('presetSelect').options.length,1);el('resetBtn').click();assert.equal(el('presetSelect').options.length,1);el('saveExampleBtn').click();assert.equal(el('presetSelect').options.length,2);console.log('Saved examples: add/load payroll/independence/reload/translation/delete/empty list/reset checks passed');w.close();
