/* User-authored text translation. Originals never leave scenario storage except
   after explicit opt-in; amounts and payroll data are never sent. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id), store=window.EuroteamsStorage;
  const CONSENT='euroteams-text-translation-enabled-v1', CACHE='euroteams-text-translations-v1';
  let cache={};try{cache=JSON.parse(store.getItem(CACHE)||'{}')||{}}catch{}
  const pending=new Map(), failed=new Set();let editing=false, queue=Promise.resolve();
  const state=()=>window.EuroteamsTextContext.getState();
  const english=()=>state().lang==='en';
  const enabled=()=>store.getItem(CONSENT)==='yes';
  const key=text=>JSON.stringify(['lt','en',text]);
  const display=text=>english()&&enabled()&&typeof cache[key(text)]==='string'?cache[key(text)]:text;
  function chunks(text){
    const parts=[];let part='',bytes=0;
    for(const ch of text){const size=new TextEncoder().encode(ch).length;if(bytes+size>450){parts.push(part);part='';bytes=0}part+=ch;bytes+=size}
    if(part)parts.push(part);return parts;
  }
  async function translate(text){
    const result=[];
    // Preserve paragraph boundaries and avoid oversized UTF-8 requests.
    for(const line of text.split(/(\n+)/)){
      if(!line.trim()){result.push(line);continue}
      const translated=[];
      for(const chunk of chunks(line)){
        const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
        try{
          const url=new URL('https://api.mymemory.translated.net/get');url.searchParams.set('q',chunk);url.searchParams.set('langpair','lt|en');
          const response=await fetch(url,{signal:controller.signal,credentials:'omit',referrerPolicy:'no-referrer'});
          const data=await response.json();
          if(!response.ok||Number(data.responseStatus)!==200||data.quotaFinished||typeof data.responseData?.translatedText!=='string')throw Error('Translation unavailable');
          // Decode entities as text, never insert remote HTML into the document.
          const decoder=document.createElement('textarea');decoder.innerHTML=data.responseData.translatedText;
          translated.push(decoder.value);
        }finally{clearTimeout(timer)}
      }
      result.push(translated.join(' '));
    }
    return result.join('');
  }
  function request(text){
    if(!text?.trim()||cache[key(text)]!==undefined||pending.has(key(text))||failed.has(key(text)))return;
    const k=key(text);
    const job=queue.then(()=>enabled()?translate(text):Promise.reject(Error('Disabled')));
    pending.set(k,job);queue=job.catch(()=>{});
    job.then(value=>{if(enabled()){cache[k]=value;store.setItem(CACHE,JSON.stringify(cache))}},()=>{failed.add(k)}).finally(()=>{
      pending.delete(k);
      // Resolve by original text, never by mutable project index or stale DOM node.
      if(english()&&enabled())window.renderEuroteamsCore();
    });
  }
  function ensure(){
    if($('textTranslationPanel'))return;
    const panel=document.createElement('section');panel.id='textTranslationPanel';panel.className='text-translation-panel';
    panel.innerHTML='<strong id="textTranslationTitle"></strong><p id="textTranslationHelp" class="help"></p><div class="saved-example-actions"><button type="button" class="btn" id="enableTextTranslation"></button><button type="button" class="btn" id="editTranslationOriginal"></button><button type="button" class="btn" id="retryTextTranslation"></button></div><div id="textTranslationStatus" role="status" aria-live="polite" class="help"></div>';
    $('nameInput').closest('.field').before(panel);
    $('enableTextTranslation').onclick=()=>{const next=!enabled();store.setItem(CONSENT,next?'yes':'no');editing=false;if(!next)failed.clear();window.renderEuroteamsCore(true)};
    $('editTranslationOriginal').onclick=()=>{editing=!editing;window.renderEuroteamsCore(true)};
    $('retryTextTranslation').onclick=()=>{failed.clear();window.renderEuroteamsCore()};
  }
  function render(){
    ensure();const en=english(),on=enabled(),st=state(),s=window.EuroteamsTextContext.current();
    $('textTranslationPanel').hidden=!en&&!on;
    $('textTranslationTitle').textContent=en?'Automatic text translation':'Automatinis tekstų vertimas';
    $('textTranslationHelp').textContent=en?'Translate project names and notes from Lithuanian to English using MyMemory (Translated). Only these texts are sent to the provider. Lithuanian originals stay saved. Machine translation may need review; service limits apply.':'Projektų pavadinimai ir pastabos verčiami iš lietuvių į anglų kalbą per „MyMemory“ (Translated). Paslaugai siunčiami tik šie tekstai. Lietuviški originalai išsaugomi. Automatinį vertimą verta peržiūrėti; taikomi paslaugos limitai.';
    $('enableTextTranslation').textContent=on?(en?'Disable automatic translation':'Išjungti automatinį vertimą'):'Enable MyMemory translation';
    $('editTranslationOriginal').hidden=!en||!on;
    $('editTranslationOriginal').textContent=editing?'Save original and translate':'Edit Lithuanian originals';
    $('retryTextTranslation').hidden=!en||!on||!failed.size;
    $('retryTextTranslation').textContent='Retry translation';
    const texts=[...st.scenarios.map(x=>x.name),s.notes].filter(x=>x?.trim());
    if(en&&on&&!editing)for(const text of texts)request(text);
    const waiting=en&&on&&texts.some(x=>pending.has(key(x))),error=en&&on&&texts.some(x=>failed.has(key(x)));
    $('textTranslationStatus').textContent=!on?'':!en?'Originalūs lietuviški tekstai. Anglų režime vertimas įjungtas.':editing?'Editing Lithuanian originals. Save to refresh English translations.':error?'Translation unavailable or service limit reached. Original text is shown where no translation is saved.':waiting?'Translating… Original text is shown until the translation is ready.':'English translations are saved in this browser. Lithuanian originals are preserved.';
    for(const [id,value] of [['nameInput',s.name],['notes',s.notes]]){
      const input=$(id);input.readOnly=en&&on&&!editing;
      if(!editing||!en||!on)input.value=display(value);
      else if(document.activeElement!==input)input.value=value;
    }
    document.querySelectorAll('.scenario-title').forEach((el,i)=>el.textContent=display(st.scenarios[i].name));
    $('resultTitle').textContent=display(s.name);
    // A saved example keeps its own original name; translation is display-only.
    for(const option of $('presetSelect').options)if(option.value&&!['factory','partner'].includes(option.value)){
      const original=window.EuroteamsTextContext.examples().items.find(x=>x.id===option.value)?.name;
      if(original){option.textContent=display(original);if(en&&on&&!editing)request(original)}
    }
  }
  window.EuroteamsTextTranslation=Object.freeze({render,display,chunks});
})();
