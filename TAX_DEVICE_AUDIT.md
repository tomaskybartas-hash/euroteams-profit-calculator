# Euroteams mokestinio ir įrenginių audito ataskaita

Data: 2026-10-15. Tikrintas Lietuvos 2026 m. standartinis darbo užmokesčio ir užsienio komandiruotės planavimo modelis.

## Aprėptis ir rezultatas

Tai skaičiavimo modelio, programos ir pateiktų prielaidų auditas. Tai nėra kiekvieno darbuotojo mokestinės rezidencijos, A1 dokumento, sutarties ar užsienio valstybės prievolių patvirtinimas. Tikri telefonai ir papildomos naršyklės nebuvo prieinami; jų testai neatlikti.

## Mokestinės taisyklės

| Sritis | Patikrinimas ir pakeitimas |
|---|---|
| Mėnesio GPM | Standartinis išskaičiavimas 20 %. Atskirtas nuo metinio perskaičiavimo. |
| Metinis GPM | Naujas pasirenkamas metinio vidurkio režimas: 12 vienodų mėnesių; 20 % iki 83 237,40 EUR, 25 % iki 138 729 EUR, 32 % virš šios ribos. Kitų metinių pajamų įvedimas taikomas tik bendram 20/25/32 % režimui. |
| NPD | 747 EUR, MMA 1 153 EUR, mažėjimo koeficientas 0,49. Nenuolatiniam Lietuvos gyventojui mėnesio NPD išjungtas. Specialūs NPD neįtraukti. |
| Darbuotojo įmokos | VSD 12,52 %, PSD 6,98 %, pasirinktas II pakopos kaupimas 3 %. |
| Metinės lubos | 138 729 EUR VSD bazė. PSD nelimituojamas. Mėnesio režime įvedamos ankstesnės draudžiamosios pajamos; metinio vidurkio režimas remiasi 12 vienodų mėnesių ir vieno darbdavio prielaida. |
| Darbdavio įmokos | Redaguojamas tarifas; numatytasis 1,77 %. VSD dalis atskirta nuo GF ir ILDF (po 0,16 %). Darbdavio tarifas ir rizikos grupė turi atitikti įmonės duomenis. |
| Įmokų grindys | Numatyta viso mėnesio 1 153 EUR bazė. Darbdavio primoka įtraukta į savikainą; bazę galima keisti tik esant proporcingam perskaičiavimui ar teisėtai išimčiai. GF remiasi faktiniu DU. |
| Dienpinigių riba | Atskirai pasirenkamas mėnesinis arba valandinis sutartinis atlygis; ribos 1 902,45 EUR/mėn. arba 11,6325 EUR/val. Nebetaikomas klaidinantis abiejų ribų OR pagal faktines mėnesio valandas. |
| Sutartinis atlygis | Galima įvesti faktinį sutartinį BRUTO. Reikšmė 0 naudoja iš NETO išvestą atlyginimą kaip aiškiai pažymėtą prielaidą. |
| Dienpinigių apmokestinimas | Atskirtos neapmokestinama ir apmokestinama dalys. Apmokestinama dalis perskaičiuoja NPD, įmokas ir grindų primoką vieną kartą. |
| Trumpos dienos | Nuo 2026-10-01 pirma ir (arba) paskutinė diena iki 4 val. įskaitoma po 20 % dienos normos. Kalendorinės dienos ir trumpos dienos įvedamos atskirai. |
| Sumažinta norma | Rodomas reikalavimas patikrinti dokumentinį pagrindą: 50 % kolektyvinė sutartis arba 65 % vidaus tvarka ir bent 7 dienų trukmė. Programa netvirtina dokumentų buvimo. |

## Programoje esančios normos

Sutikrintos su Vyriausybės nutarimo Nr. 526 normų sąrašu. Sąrašo pakeitimas Nr. 504 yra 2023-06-28; 2026 m. tvarkos pakeitimai vertinti atskirai.

| Šalis | EUR / dieną |
|---|---:|
| Nyderlandai | 64 |
| Vokietija | 62 |
| Prancūzija | 69 |
| Suomija | 69 |
| Švedija | 70 |
| Danija | 80 |
| Norvegija | 70 |
| Estija | 47 |
| Ispanija | 58 |
| Portugalija | 56 |
| Belgija | 61 |
| Austrija | 69 |

„Kita“ reiškia programoje neįtrauktą pasirinktą šalį, o ne teisės akto kategoriją „Kitos valstybės“. Reikalinga konkrečiai šaliai patikrinta dienos riba. Kol ji neįvesta, lengvata savavališkai netaikoma.

## Automatiniai bandymai

- 189 mokestinių patikrinimų: skaitiniai etalonai, NPD, rezidencija, įmokų grindys, progresinis GPM, VSD/PSD, lubos, sutartinio atlygio rūšis, trumpų dienų ir ribų logika, NETO/BRUTO inversija.
- 64 programos ir DOM patikrinimas: pradiniai pavyzdžiai, A1 įtraukimas/pridėjimas, scenarijų nepriklausomumas, šalinimas, vertimas, redagavimas ir perkrovimas.
- 10 saugojimo ir apimties patikrinimų: 500 scenarijų, kito skirtuko įvykis, structuredClone atsarginis variantas, pilna saugykla, atkūrimas po saugojimo klaidos.
- 500 scenarijų DOM bandymas apie 1,5–1,7 s šioje aplinkoje; tai nėra telefono spartos matavimas.

## Įrenginiai ir naršyklės

| Aplinka | Būsena |
|---|---|
| Pateikta Chrome naršyklė | Gyvas funkcinis QA |
| Mobile / tablet / laptop / desktop dydžiai | Gyvai emuliuota: 320, 375, 390, 430, 768, 1024, 1280, 1600 px ir 844 × 390 landscape. Visais atvejais horizontalus turinys telpa. Tai iframe pločio emuliacija, ne tikras mobilus įrenginys. |
| Fiziniai iPhone / iPad, iOS Safari | Neatlikta: nėra prieigos |
| Fiziniai Android telefonai, Samsung Internet | Neatlikta: nėra prieigos |
| Firefox, macOS Safari, tikras Microsoft Edge | Neatlikta: nėra prieigos |
| Mobili klaviatūra, lietimas, ekrano skaitytuvai, OS šrifto didinimas | Neatlikta tikruose įrenginiuose |

Gyvai patikrinti ir nauji laukai: metinis vidurkis (8 000 ir 15 000 EUR BRUTO etalonai), mažo atlyginimo grindys, NPD išjungimas nerezidentui, dvi trumpos dienos, visi 12 šalių pasirinkimai, A1 klaviatūra ir LT/EN vertimai. Įmokų ir GPM šaltinių neatitikimas dėl istorinio darbdavio lubų sakinio pažymėtas žemiau.

Emuliatorius naudoja įprastą 15 px naršyklės slinkties juostą: 320 px rėmo vidinė turinio sritis yra 305 px. Puslapis vis tiek telpa be horizontalaus slinkimo.

## Kas negali būti patvirtinta be konkrečių duomenų

- Kurioje valstybėje konkrečiu atveju privaloma mokėti GPM, socialinį draudimą ir priimančios šalies įmokas.
- Darbuotojo rezidencija, specialus NPD, nerezidento metinis NPD susigrąžinimas, darbas kitur, faktinės metų pajamos, grindų išimtis ir A1 galiojimas.
- Priimančios valstybės minimalus atlygis, kolektyvinės sutartys, viršvalandžiai, atostoginiai, ligos išmokos ir kelių šalių kelionių paskirstymas.
- Vartotojo sutartinis valandinis/mėnesinis atlygis ir teisė mažinti dienpinigius.
- Metinio vidurkio režimas nėra individualios veiklos, kapitalo pajamų, užsienio mokesčio kredito ar metinės deklaracijos skaičiuoklė.

## Oficialūs šaltiniai

- [VMI – NPD taikymas](https://www.vmi.lt/evmi/npd-pnpd-taikymas-20-str.-1)
- [VMI – GPM tarifai nuo 2026 m.](https://www.vmi.lt/evmi/5725?lang=en)
- [VMI – nenuolatinio gyventojo metinė deklaracija ir NPD](https://www.vmi.lt/evmi/web/guest/metin%C4%97-pajam%C5%B3-mokes%C4%8Dio-deklaracija-gpm314)
- [Sodra – 2026 m. tarifai (PDF)](https://www.sodra.lt/wp-content/uploads/2025/12/Aktuali-informacija-draudejams-2026-metais.pdf)
- [Sodra – įmokų grindys ir įmokų rūšys](https://sodra.lt/imokos/idarbinimas-pranesimai-imokos-ir-tarifai)
- [Sodra – II pakopos įmokos](https://sodra.lt/pensijos/papildomai-kaupiama-pensija/pagrindine-informacija)
- [VMI – privačių įmonių komandiruotės](https://www.vmi.lt/evmi/priva%C4%8Di%C5%B3-%C4%AFmoni%C5%B31)
- [VDI – nuo 2026-10-01 galiojanti dienpinigių tvarka](https://vdi.lrv.lt/lt/naujienos/nuo-spalio-1-osios-nauja-komandiruociu-dienpinigiu-tvarka-ka-darbdaviai-turi-pakeisti-jau-dabar-wIM/)
- [TAR – dienpinigių normų sąrašas Nr. 504 (PDF)](https://e-tar.lt/rs/legalact/4824fa10167d11ee9f7ec2ffce8b47bc/format/ISO_PDF)

Pastaba: Sodra bendrame istoriniame puslapyje dar turi sakinį apie nuo 2021 m. darbdaviui netaikytas lubas. 2026 m. skaičiavimui vadovautasi specialiai 2026 metams paskelbta informacija ir PDF, kurie nurodo darbdavio VSD lubas.
