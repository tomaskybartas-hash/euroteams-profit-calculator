(() => {
  const files = ['safe-storage.js','app-core.js','full-language.js','payroll-controls.js','tax-rules-2026.js','canonical-results.js','text-translation.js'];
  function next(){
    const src = files.shift();
    if(!src){ window.renderEuroteamsCore(); return; }
    const script = document.createElement('script');
    script.src = src + '?v=20261016-texttranslation1';
    script.onload = next;
    script.onerror = () => { document.getElementById('savedMsg').textContent = 'Nepavyko įkelti skaičiuoklės / Calculator could not load'; };
    document.head.appendChild(script);
  }
  next();
})();
