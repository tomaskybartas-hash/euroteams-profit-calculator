(() => {
  const LT_TO_EN = new Map([
    ['Slaptažodis','Password'],
    ['Prisijungti','Sign in'],
    ['Tik Euroteams komandai · prisijungimas galioja 24 val.','Euroteams team only · sign-in remains valid for 24 hours.'],
    ['VERSLO DARBO ERDVĖ','BUSINESS WORKSPACE'],
    ['Maržos skaičiuoklė','Margin calculator'],['▣   Maržos skaičiuoklė','▣   Margin calculator'],
    ['Privati darbo erdvė','Private workspace'],
    ['Euroteams Group komandai','For the Euroteams Group team'],
    ['PROJEKTO VERTINIMAS / NYDERLANDAI','PROJECT EVALUATION / NETHERLANDS'],
    ['Atsijungti','Log out'],
    ['Apsaugota slaptažodžiu','Password protected'],
    ['ŽINOKITE SAVO SKAIČIUS','KNOW YOUR NUMBERS'],
    ['Kiekviena valanda. Kiekvienas euras.','Every hour. Every euro.'],
    ['Įvertinkite subrangos projekto pajamas, išlaidas ir pelną vienam darbuotojui bei visai komandai.','Evaluate subcontracting project revenue, costs and profit per worker and for the entire team.'],
    ['Planavimo skaičiavimas pagal įvestas prielaidas.','Planning calculation based on the assumptions entered.'],
    ['Darbdavio išlaidų procentai ir pasiūlymo sumos yra keičiami planavimo duomenys. Skaičiuoklė netikrina teisinių darbo užmokesčio reikalavimų.','Employer cost percentages and proposal amounts are editable planning inputs. The calculator does not verify legal wage requirements.'],
    ['Atkurti pavyzdžius','Restore examples'],
    ['Ištrinti projektą','Delete project'],
    ['+ Pridėti projektą','+ Add project'],
    ['01 / DUOMENYS','01 / INPUTS'],
    ['Projekto prielaidos','Project assumptions'],
    ['Projekto pavadinimas','Project name'],
    ['Pasirinkti redaguojamą pavyzdį','Choose an editable example'],
    ['Pasirinkite pavyzdį…','Choose an example…'],
    ['Gamykla · 12 € į rankas / 200 val.','Factory · €12 net / 200 h'],
    ['Partneris · mėnesinės pasiūlymo sumos','Partner · monthly proposal amounts'],
    ['Kliento valandinis tarifas','Client hourly rate'],
    ['Valandos per mėnesį','Hours per month'],
    ['Darbuotojui apmokamos ir klientui pateikiamos tos pačios valandos · vienam darbuotojui · be PVM','The same hours are paid to the worker and billed to the client · per worker · excluding VAT'],
    ['Darbuotojų skaičius','Number of workers'],
    ['Visos įvedamos išlaidos skirtos vienam darbuotojui. Komandos sumos dauginamos iš darbuotojų skaičiaus.','All entered costs are per worker. Team totals are multiplied by the number of workers.'],
    ['Darbdavio išlaidų skaičiavimas','Employer cost calculation'],
    ['Atlyginimas į rankas + papildomos išlaidos','Net pay + additional costs'],
    ['Mėnesinės pasiūlymo sumos','Monthly proposal amounts'],
    ['Atlyginimas į rankas / val.','Net pay / hour'],
    ['Papildomos darbdavio išlaidos (%)','Additional employer costs (%)'],
    ['Darbuotojo atlyginimas / mėn.','Worker pay / month'],
    ['Darbuotojo kaina įmonei / mėn.','Employer cost / month'],
    ['Apgyvendinimas ir logistika','Accommodation and logistics'],
    ['Rotacija (darbas / namai)','Rotation (work / home)'],
    ['4/1 — 4 sav. komandiruotėje, 1 sav. namuose','4/1 — 4 weeks on assignment, 1 week home'],
    ['4/2 — 4 sav. komandiruotėje, 2 sav. namuose','4/2 — 4 weeks on assignment, 2 weeks home'],
    ['6/2 — 6 sav. komandiruotėje, 2 sav. namuose','6/2 — 6 weeks on assignment, 2 weeks home'],
    ['7/2 — 7 sav. komandiruotėje, 2 sav. namuose','7/2 — 7 weeks on assignment, 2 weeks home'],
    ['8/2 — 8 sav. komandiruotėje, 2 sav. namuose','8/2 — 8 weeks on assignment, 2 weeks home'],
    ['Kita visa ciklo trukmė','Custom cycle length'],
    ['Darbo savaitės','Work weeks'],
    ['Namų savaitės','Home weeks'],
    ['Apgyvendinimas / mėn.','Accommodation / month'],
    ['Skrydžių ir kelionių skaičiavimas','Flight and travel calculation'],
    ['Mėnesio išlaidos','Monthly costs'],
    ['Vienos rotacijos išlaidos','Cost per rotation'],
    ['Kelionės išlaidos / mėn.','Travel costs / month'],
    ['Vienos rotacijos kelionės išlaidos','Travel cost per rotation'],
    ['Kitos išlaidos / mėn.','Other costs / month'],
    ['Įrankiai, administravimas, draudimas, rezervas ir kitos išlaidos','Tools, administration, insurance, contingency and other costs'],
    ['Projekto pastabos ir pirminės prielaidos','Project notes and initial assumptions'],
    ['Išsaugota šioje naršyklėje','Saved in this browser'],
    ['02 / VIENAM DARBUOTOJUI · PER MĖNESĮ','02 / PER WORKER · PER MONTH'],
    ['Numatomas pelnas','Projected profit'],
    ['Pelnas nuo vieno darbuotojo / mėn.','Profit per worker / month'],
    ['Atėmus įvestas darbdavio, logistikos ir kitas išlaidas','After entered employer, logistics and other costs'],
    ['Marža','Margin'],
    ['Įmonės pelnas už 1 pateiktą val.','Company profit per billed hour'],
    ['Pajamos iš kliento','Client revenue'],
    ['Valandinis tarifas × mėnesio valandos','Hourly rate × monthly hours'],
    ['Darbuotojo atlyginimas','Worker pay'],
    ['Atlyginimas į rankas už valandą × mėnesio valandos','Net pay per hour × monthly hours'],
    ['Numatoma darbuotojo kaina įmonei','Estimated employer cost'],
    ['Logistikos išlaidos','Logistics costs'],
    ['Apgyvendinimas + mėnesio kelionės','Accommodation + monthly travel'],
    ['Papildomos išlaidos virš darbuotojo atlyginimo','Additional employer costs above worker pay'],
    ['Šiam mėnesiui paskirstytos kelionės','Travel allocated to this month'],
    ['Kitos mėnesio išlaidos','Other monthly costs'],
    ['Visos įvestos išlaidos','Total entered costs'],
    ['Kliento tarifas be pelno ir nuostolio','Break-even client rate'],
    ['KOMANDA / PER MĖNESĮ','TEAM / PER MONTH'],
    ['Euroteams Group įmonės pelnas','Euroteams Group company profit'],
    ['Patikrinkite prielaidas','Review assumptions'],
    ['Šios aplinkybės gali pakeisti galutinę maržą.','These factors may affect the final margin.'],
    ['03 / REZULTATAI','03 / RESULTS'],
    ['Pasirinkto projekto rezultatai.','Selected project results.'],
    ['Vienam darbuotojui ir komandai · per mėnesį · EUR','Per worker and team · per month · EUR'],
    ['Pasirinkto projekto mėnesio rezultatai vienam darbuotojui ir komandai bei keičiamas darbuotojų skaičius','Monthly results for the selected project per worker and team, with editable worker count'],
    ['¹ Darbuotojo atlyginimas įtrauktas į bendrą darbuotojo kainą įmonei. Įvedamos išlaidos yra vienam darbuotojui; visiems komandos nariams taikomos tos pačios valandos ir išlaidos.','¹ Worker pay is included in the total employer cost. Entered costs are per worker; the same hours and costs are applied to all team members.'],
    ['Euroteams Group · Projekto Nyderlanduose vertinimas · Projektai saugomi šioje naršyklėje. Jie nesinchronizuoja tarp įrenginių.','Euroteams Group · Netherlands project evaluation · Projects are stored in this browser and do not sync across devices.']
  ]);

  const EN_TO_LT = new Map([...LT_TO_EN.entries()].map(([lt,en]) => [en,lt]));

  function replaceTextNodes(root, map) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let n;
    while ((n = walker.nextNode())) nodes.push(n);
    for (const node of nodes) {
      const raw = node.nodeValue;
      const trimmed = raw.trim();
      if (!trimmed) continue;
      const direct = map.get(trimmed);
      if (direct) {
        const start = raw.match(/^\s*/)?.[0] || '';
        const end = raw.match(/\s*$/)?.[0] || '';
        node.nodeValue = start + direct + end;
      }
    }
  }

  function translateNotice(lang) {
    const notice = document.querySelector('.notice');
    if (!notice) return;
    if (lang === 'en') {
      notice.innerHTML = '<strong>Planning calculation based on the assumptions entered.</strong> Employer cost percentages and proposal amounts are editable planning inputs. The calculator does not verify legal wage requirements.';
    } else {
      notice.innerHTML = '<strong>Planavimo skaičiavimas pagal įvestas prielaidas.</strong> Darbdavio išlaidų procentai ir pasiūlymo sumos yra keičiami planavimo duomenys. Skaičiuoklė netikrina teisinių darbo užmokesčio reikalavimų.';
    }
  }

  function translateBreadcrumb(lang) {
    const el = document.querySelector('.breadcrumb');
    if (el) el.textContent = lang === 'en' ? 'PROJECT EVALUATION / NETHERLANDS' : 'PROJEKTO VERTINIMAS / NYDERLANDAI';
  }

  function translateProtected(lang) {
    const span = document.querySelector('.top-actions > span');
    if (span) span.textContent = lang === 'en' ? '● Password protected' : '● Apsaugota slaptažodžiu';
  }

  function translateScenarioHeader(lang) {
    const header = document.querySelector('.scen-head > div:first-child');
    if (!header) return;
    const m = header.textContent.match(/(\d+)/);
    const num = m ? m[1] : '1';
    header.textContent = `${lang === 'en' ? 'Project' : 'Projektas'} ${num}`;
  }

  function translateLogin(lang) {
    const title = document.getElementById('loginTitle');
    const text = document.getElementById('loginText');
    const input = document.getElementById('password');
    const btn = document.getElementById('loginBtn');
    const foot = document.querySelector('.login-card p:last-child');
    if (title) title.textContent = lang === 'en' ? 'Euroteams sign in' : 'Euroteams prisijungimas';
    if (text) text.textContent = lang === 'en' ? 'Sign in with the shared company password to open the calculator.' : 'Prisijunkite bendru įmonės slaptažodžiu, kad atidarytumėte skaičiuoklę.';
    if (input) input.placeholder = lang === 'en' ? 'Password' : 'Slaptažodis';
    if (btn) btn.textContent = lang === 'en' ? 'Sign in' : 'Prisijungti';
    if (foot) foot.textContent = lang === 'en' ? 'Euroteams team only · sign-in remains valid for 24 hours.' : 'Tik Euroteams komandai · prisijungimas galioja 24 val.';
  }

  function applyLanguage(lang) {
    document.documentElement.lang = lang;
    const map = lang === 'en' ? LT_TO_EN : EN_TO_LT;
    replaceTextNodes(document.body, map);
    translateNotice(lang);
    translateBreadcrumb(lang);
    translateProtected(lang);

    translateLogin(lang);

    const lt = document.getElementById('ltBtn');
    const en = document.getElementById('enBtn');
    if (lt) lt.classList.toggle('active', lang === 'lt');
    if (en) en.classList.toggle('active', lang === 'en');
  }

  function currentLang() {
    return document.getElementById('enBtn')?.classList.contains('active') ? 'en' : 'lt';
  }

  window.applyEuroteamsLanguage = applyLanguage;
  applyLanguage(currentLang());
})();
