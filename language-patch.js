(() => {
  const knownNames = new Map([
    ['Olandijos Gamykla su nekvalifikuotais darb.','Netherlands Factory with Unskilled Workers'],
    ['Olandijos gamykla su nekvalifikuotais darb.','Netherlands Factory with Unskilled Workers'],
    ['Alano Gamykla su nekvalifikuotais darb.','Alan’s Factory with Unskilled Workers'],
    ['Alano gamykla su nekvalifikuotais darb.','Alan’s Factory with Unskilled Workers'],
    ['Partneris · mėnesinės pasiūlymo sumos','Partner · Monthly Proposal Amounts']
  ]);
  const reverseNames = new Map([...knownNames.entries()].map(([lt,en]) => [en,lt]));

  const fragmentPairs = [
    ['Maržos skaičiuoklė','Margin calculator'],
    ['Mėnesio rezultatas','Monthly result'],
    ['Pajamos iš kliento / nuo darbuotojo','Client revenue / worker'],
    ['Atlyginimas¹ / darbuotojui','Pay¹ / worker'],
    ['Darbuotojo kaina įmonei','Employer cost / worker'],
    ['Apgyvendinimas / darbuotojui','Accommodation / worker'],
    ['Mėnesio kelionės / darbuotojui','Monthly travel / worker'],
    ['Logistika / darbuotojui','Logistics / worker'],
    ['Kitos išlaidos / darbuotojui','Other costs / worker'],
    ['Visos išlaidos / darbuotojui','Total costs / worker'],
    ['Pelnas nuo vieno darbuotojo','Profit per worker'],
    ['Pelnas už valandą','Profit per hour'],
    ['Tarifas be pelno ir nuostolio','Break-even rate'],
    ['Kliento tarifas','Client rate'],
    ['Rotacija','Rotation'],
    ['Kelionių prielaida','Travel assumption'],
    ['Apgyvendinimas — 0 €: suteikia klientas arba išlaidos neįtrauktos.','Accommodation — €0: provided by the client or not included.'],
    ['Kelionės — 0 €: apmoka klientas arba išlaidos neįtrauktos.','Travel — €0: paid by the client or not included.'],
    ['Kitos išlaidos — 0 €. Prireikus įtraukite įrankius, draudimą, administravimą ir rezervą.','Other costs — €0. Add tools, insurance, administration and contingency if required.'],
    ['Pelnas yra planavimo įvertis prieš neįvestas išlaidas ir pelno mokestį. A1, dienpinigių ir komandiravimo taisyklės netikrinamos.','Profit is a planning estimate before unentered costs and corporate tax. A1, per diem and posting rules are not verified.'],
    ['Pagal įvestą mėnesinę pasiūlymo sumą','Based on the entered monthly proposal amount']
  ];

  function isEnglish() {
    return document.getElementById('enBtn')?.classList.contains('active');
  }

  function replaceFragments(root, toEnglish) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let n;
    while ((n = walker.nextNode())) nodes.push(n);
    for (const node of nodes) {
      const original = node.nodeValue || '';
      let value = original;
      for (const [lt,en] of fragmentPairs) {
        const from = toEnglish ? lt : en;
        const to = toEnglish ? en : lt;
        if (value.includes(from)) value = value.split(from).join(to);
      }
      if (value !== original) node.nodeValue = value;
    }
  }

  function translateKnownProjectNames(toEnglish) {
    const map = toEnglish ? knownNames : reverseNames;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const original = node.nodeValue || '';
      let value = original;
      for (const [from,to] of map) {
        if (value.includes(from)) value = value.split(from).join(to);
      }
      if (value !== original) node.nodeValue = value;
    }
    const input = document.getElementById('nameInput');
    if (input) {
      const translated = map.get(input.value);
      if (translated && input.value !== translated) input.value = translated;
    }
  }

  function translateDynamic(toEnglish) {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const original = node.nodeValue || '';
      let v = original;
      if (toEnglish) {
        v = v.replace(/(\d+) darbuotojas · mėnesio sumos/g, '$1 worker · monthly totals');
        v = v.replace(/(\d+) darbuotojų · mėnesio sumos/g, '$1 workers · monthly totals');
        v = v.replace(/(\d+) darbuotojas × (\d+) val\. = (\d+) klientui pateikiamų valandų \/ mėn\./g, '$1 worker × $2 h = $3 billed hours / month');
        v = v.replace(/(\d+) darbuotojų × (\d+) val\. = (\d+) klientui pateikiamų valandų \/ mėn\./g, '$1 workers × $2 h = $3 billed hours / month');
        v = v.replace(/Darbuotojo atlyginimas \+ ([\d.,]+) % papildomų darbdavio išlaidų/g, 'Worker pay + $1% additional employer costs');
        v = v.replace(/(\d+\/\d+) · (\d+) sav\. komandiruotėje \/ (\d+) sav\. namuose\. Visas ciklas: (\d+) sav\. Mėnesio valandos lieka įvestos; poilsis namuose jų automatiškai nesumažina\./g, '$1 · $2 weeks on assignment / $3 weeks home. Total cycle: $4 weeks. Monthly hours remain as entered; home leave does not reduce them automatically.');
      }
      if (v !== original) node.nodeValue = v;
    }
  }

  function apply() {
    const en = isEnglish();
    replaceFragments(document.body, en);
    translateKnownProjectNames(en);
    translateDynamic(en);
  }

  document.addEventListener('click', e => {
    if (e.target.closest('#enBtn') || e.target.closest('#ltBtn') || e.target.closest('#scenarioTabs') || e.target.closest('#addBtn') || e.target.closest('#deleteBtn') || e.target.closest('#resetBtn')) {
      requestAnimationFrame(() => requestAnimationFrame(apply));
    }
  });

  const obs = new MutationObserver(() => {
    clearTimeout(window.__etLangPatchTimer);
    window.__etLangPatchTimer = setTimeout(apply, 25);
  });
  obs.observe(document.body, {childList:true, subtree:true});

  window.addEventListener('load', apply);
  setTimeout(apply, 100);
})();