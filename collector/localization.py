"""Deterministic LT/EN interface translation; user-entered content is preserved."""
from html.parser import HTMLParser
import html,json,re
from fastapi import Request,Depends,HTTPException
from fastapi.responses import RedirectResponse,Response
from app.db import SessionLocal,get_db

# Translation keys also cover the legacy administration and document templates.
PAIRS='''New unique worker profiles|Nauji unikalūs darbuotojų profiliai
Daily collection reports|Dienos rinkimo ataskaitos
Saved daily totals for new worker profiles. Ads are excluded. Reports start when this feature is enabled; unsupported metrics are not invented.|Išsaugotos naujų darbuotojų profilių dienos suvestinės. Skelbimai neįtraukiami. Ataskaitos kaupiamos nuo funkcijos įjungimo; nematuojami rodikliai neišgalvojami.
No daily reports yet|Dienos ataskaitų dar nėra
Response|Atsakymas
Daily target|Dienos tikslas
New unique worker profiles only. Advertisements are excluded.|Tik nauji unikalūs darbuotojų profiliai. Skelbimai neįskaičiuojami.
Insufficient source coverage|Nepakanka kandidatų surinkimo šaltinių
Target reached|Tikslas pasiektas
New WhatsApp contacts|Nauji WhatsApp kontaktai
New email contacts|Nauji el. pašto kontaktai
Unique profiles per elapsed hour today|Unikalių profilių per praėjusią šios dienos valandą
WhatsApp Contacts|WhatsApp kontaktai
Email Contacts|El. pašto kontaktai
Email job-offer permission is required|Reikalingas leidimas siųsti darbo pasiūlymus el. paštu
Add a valid email address|Įveskite tinkamą el. pašto adresą
Send by Email|Siųsti el. paštu
Prepare email|Paruošti el. laišką
Already contacted|Jau kontaktuota
Nothing has been sent. Open your email app and press Send there.|Laiškas dar neišsiųstas. Atidarykite el. pašto programą ir joje paspauskite Siųsti.
Candidate responses|Kandidatų atsakymai
Job offer|Darbo pasiūlymas
net per hour|į rankas už valandą
Your answer was received|Jūsų atsakymas gautas
INTERESTED|Domina
NOT_INTERESTED|Nedomina
Not interested|Nedomina
Message to recruiter|Žinutė atrankos specialistui
Your answer will be visible to the Euroteams recruiter. You can change it using this link.|Jūsų atsakymą matys Euroteams atrankos specialistas. Atsakymą galite pakeisti naudodami šią nuorodą.
This is a private link. Please do not forward it.|Tai asmeninė nuoroda. Prašome jos nepersiųsti.
This job is closed|Šis darbo pasiūlymas uždarytas
No responses yet|Atsakymų dar nėra
Replies submitted through private offer links. A reply does not verify identity or confirm that a WhatsApp message was sent.|Atsakymai pateikti per asmenines pasiūlymų nuorodas. Atsakymas nepatvirtina tapatybės ar WhatsApp žinutės išsiuntimo.
Data export|Duomenų eksportas
Download recruitment data|Atsisiųsti atrankos duomenis
Download workers, jobs, permissions and contact history as JSON. Credentials and uploaded files are excluded. This is a data export; automatic restore is not available.|Atsisiųskite darbuotojus, darbo vietas, sutikimus ir kontaktavimo istoriją JSON formatu. Prisijungimo duomenys ir įkelti failai neįtraukiami. Tai duomenų eksportas; automatinio atkūrimo nėra.
Choose availability|Pasirinkite, kada galite pradėti
Dashboard|Apžvalga
Workers|Darbuotojai
Jobs|Darbai
Matches|Atitikmenys
Sources|Šaltiniai
Collector|Duomenų rinkimas
Settings|Nustatymai
Projects|Projektai
Project|Projektas
Worker|Darbuotojas
Profession|Profesija
Country|Šalis
City|Miestas
Phone|Telefonas
WhatsApp number|WhatsApp numeris
Email|El. paštas
Skills|Įgūdžiai
Certificates|Sertifikatai
Languages|Kalbos
Availability|Pasirengimas dirbti
Salary|Atlyginimas
Rotation|Rotacija
Start date|Pradžios data
Accommodation|Apgyvendinimas
Transport|Transportas
Travel|Kelionė
Status|Būsena
Source|Šaltinis
Quality score|Profilio išsamumas
Verified|Patikrintas
Unverified|Nepatikrintas
Verification|Patikra
Experience|Patirtis
Preferred country|Pageidaujama šalis
Preferred countries|Pageidaujamos šalys
Last verified|Paskutinė patikra
Match score|Atitikimo balas
Search workers...|Ieškoti darbuotojų...
Search|Ieškoti
Filter|Filtruoti
Reset filters|Išvalyti filtrus
More filters|Daugiau filtrų
All|Visi
All countries|Visos šalys
All availability|Visos būsenos
All segments|Visos profesijos
All sources|Visi šaltiniai
Any|Bet koks
Yes|Taip
No|Ne
YES|TAIP
NO|NE
UNKNOWN|NEŽINOMA
AVAILABLE NOW|GALI DIRBTI DABAR
AVAILABLE FROM DATE|GALI DIRBTI NUO DATOS
OPEN TO OFFERS|LAUKIA PASIŪLYMŲ
CURRENTLY WORKING|ŠIUO METU DIRBA
NOT LOOKING|NEIEŠKO DARBO
General Labour|Nekvalifikuota darbo jėga
Welders|Suvirintojai
Pipefitters|Vamzdynų montuotojai
Fitters|Konstrukcijų montuotojai
Mechanics|Mechanikai
Carpenters|Staliai
Masons|Mūrininkai
Electricians|Elektrikai
Scaffolders|Pastolininkai
Other|Kiti
Send Job Request|Siųsti darbo pasiūlymą
Select Job|Pasirinkti darbo pasiūlymą
Select a job|Pasirinkite darbą
Select an active job|Pasirinkite aktyvų darbą
Prepare WhatsApp message|Paruošti WhatsApp žinutę
Open WhatsApp|Atidaryti WhatsApp
I sent this message|Žinutę išsiunčiau
Message preview|Žinutės peržiūra
Nothing has been sent. Open WhatsApp and press Send there.|Žinutė dar neišsiųsta. Atidarykite WhatsApp ir ten paspauskite siuntimo mygtuką.
A request for this job was prepared in the last 24 hours. Reuse it to avoid duplicate outreach.|Per paskutines 24 valandas šiam darbui jau paruoštas pasiūlymas. Naudokite jį pakartotinai, kad nedubliuotumėte žinučių.
No active jobs. Create a job first.|Nėra aktyvių darbų. Pirmiausia sukurkite darbą.
Add a valid WhatsApp number including country code|Įveskite tinkamą WhatsApp numerį su šalies kodu
WhatsApp job-offer permission is required|Reikalingas leidimas siųsti darbo pasiūlymus per WhatsApp
Contact settings|Kontaktų nustatymai
Contact History|Kontaktų istorija
Profile|Profilis
Open profile|Atidaryti profilį
Save|Išsaugoti
Save changes|Išsaugoti pakeitimus
Date|Data
Channel|Kanalas
Note|Pastaba
No contact history yet.|Kontaktų istorijos dar nėra.
DRAFT_PREPARED|ŽINUTĖ PARUOŠTA
CONTACTED|SUSISIEKTA
New|Naujas
Available|Gali dirbti
Contacted|Susisiekta
Interested|Susidomėjo
Not Interested|Nesusidomėjo
In Process|Vyksta atranka
Hired|Įdarbintas
Unavailable|Negali dirbti
Stale|Duomenys pasenę
Total Workers|Darbuotojų bazėje
Available Workers|Gali dirbti dabar
New Today|Nauji šiandien
New This Week|Nauji šią savaitę
Active Jobs|Aktyvūs darbai
Collector Status|Rinkimo būsena
Last Run|Paskutinis vykdymas
Next Run|Kitas vykdymas
Candidates Found|Rasta skelbimų
New Candidates Added|Pridėta naujų skelbimų
Duplicates|Dublikatai
Errors|Klaidos
Active Sources|Aktyvūs šaltiniai
Records / Hour|Įrašai per valandą
Not measured|Nematuota
Every 6 hours; GitHub may delay scheduled runs.|Kas 6 valandas; GitHub gali atidėti suplanuotą vykdymą.
Free public jobseeker ads|Nemokami darbo ieškančiųjų skelbimai
These are ads, not verified worker profiles. Contact details remain on the original source.|Tai skelbimai, o ne patikrinti darbuotojų profiliai. Kontaktai pateikiami pirminiame šaltinyje.
View ads|Peržiūrėti skelbimus
Candidate registration|Kandidato registracija
Professional profile|Profesinis profilis
Manual / import|Įvesta ranka / importuota
Registration form|Registracijos forma
Open registration form|Atidaryti registracijos formą
Share this link with candidates or group administrators. Posting is not automatic.|Šią nuorodą galite perduoti kandidatams ar grupių administratoriams. Automatinis skelbimas nevykdomas.
Facebook groups|Facebook grupės
Not connected|Neprijungta
No group API or posting permission is configured. No private group data is collected.|Grupių API ir skelbimo leidimai nesukonfigūruoti. Privačių grupių duomenys nerenkami.
Paid acquisition|Mokamas duomenų rinkimas
Disabled|Išjungta
RSS ads|RSS skelbimai
Four official feeds in Latvia: welders, masons, mechanics and electricians.|Keturi oficialūs srautai Latvijoje: suvirintojai, mūrininkai, mechanikai ir elektrikai.
Countries not connected yet|Dar neprijungtos šalys
Lithuania, Poland, Romania, Bulgaria, Spain, Italy|Lietuva, Lenkija, Rumunija, Bulgarija, Ispanija, Italija
No automated source is currently connected for these countries.|Šioms šalims automatiniai šaltiniai kol kas neprijungti.
Language|Kalba
Your language is saved for this account and browser.|Kalba išsaugoma šiai paskyrai ir naršyklei.
Integrations|Integracijos
WhatsApp click-to-chat|WhatsApp žinutės paruošimas
Free. You confirm sending in WhatsApp. Automatic Business API sending is not configured.|Nemokama. Siuntimą patvirtinate WhatsApp. Automatinis siuntimas per Business API nesukonfigūruotas.
Team administration|Komandos administravimas
Consent Center|Leidimų centras
Outbox|Žinučių eilė
Audit log|Veiksmų žurnalas
Log out|Atsijungti
Log in|Prisijungti
Sign in|Prisijungti
Password|Slaptažodis
Email address|El. pašto adresas
Invalid email or password|Neteisingas el. paštas arba slaptažodis
Login required|Reikia prisijungti
Not permitted|Veiksmas neleidžiamas
Refresh the page and try again|Atnaujinkite puslapį ir bandykite dar kartą
Invalid filter|Neteisingas filtras
Worker not found|Darbuotojas nerastas
Contact not found|Kontaktas nerastas
Job not found|Darbas nerastas
Check job fields|Patikrinkite darbo laukus
Edit job|Redaguoti darbą
New job|Naujas darbas
New project|Naujas projektas
Create project|Sukurti projektą
Project name|Projekto pavadinimas
Client|Klientas
Workers needed|Reikia darbuotojų
Duration weeks|Trukmė savaitėmis
Weekly hours|Valandos per savaitę
Net €/h|Į rankas €/val.
Required language|Reikalinga kalba
Citizenship|Pilietybė
Required certificates|Reikalingi sertifikatai
Requirements|Reikalavimai
Description|Aprašymas
DRAFT|JUODRAŠTIS
ACTIVE|AKTYVUS
RECRUITING|VYKSTA ATRANKA
CLOSED|UŽDARYTAS
Provided|Suteikiama
To be agreed|Derinama
Previous|Ankstesnis
Next|Kitas
No workers match these filters.|Pagal šiuos filtrus darbuotojų nerasta.
No workers yet.|Darbuotojų dar nėra.
No jobs yet.|Darbų dar nėra.
+ Add worker|+ Pridėti darbuotoją
+ New project|+ Naujas projektas
Export CSV|Eksportuoti CSV
Bulk import|Masinis importas
Import CSV|Importuoti CSV
Minimum experience|Minimali patirtis
Minimum profile completeness|Minimalus profilio išsamumas
EU citizenship confirmed|ES pilietybė patvirtinta
Welding process|Suvirinimo procesas
Last contacted|Paskutinį kartą susisiekta
Not confirmed|Nepatvirtinta
Not verified|Nepatikrinta
Not available|Nėra duomenų
years|metai
Open worker portal|Atidaryti darbuotojo portalą
Confirm availability|Patvirtinti pasirengimą dirbti
Available from|Gali dirbti nuo
Update availability|Atnaujinti būseną
Communication consent|Leidimas susisiekti
Grant|Suteikti
GRANTED|SUTEIKTA
REVOKED|ATŠAUKTA
Worker Passport documents|Darbuotojo dokumentai
Type|Tipas
Expiry|Galioja iki
File|Failas
Upload|Įkelti
Document|Dokumentas
Verify|Patikrinti
Availability history|Pasirengimo dirbti istorija
No history yet.|Istorijos dar nėra.
Messages|Žinutės
No messages yet.|Žinučių dar nėra.
CONFIDENCE|PATIKIMUMAS
PROFILE|PROFILIS
RELIABILITY|PATIKIMUMO BALAS
READY TO DEPLOY|PASIRENGĘS IŠVYKTI
Expected rate|Pageidaujamas atlygis
Team|Komanda
Crews|Brigados
Operations|Operacijos
Workspace|Darbo aplinka
Control|Valdymas
Worker Collector|Darbuotojų rinkimas
Worker collection|Darbuotojų rinkimas
Back|Atgal
Back to workers|Atgal į darbuotojus
Details|Informacija
Action|Veiksmas
Actor|Vartotojas
Time|Laikas
Name|Vardas ir pavardė
Role|Rolė
Active|Aktyvus
Add user|Pridėti vartotoją
Full name|Vardas ir pavardė
Create|Sukurti
Send|Siųsti
MATCHED|ATRINKTAS
INTERESTED|SUSIDOMĖJO
NOT_INTERESTED|NESUSIDOMĖJO
QUALIFIED|TINKAMAS
READY_TO_DEPLOY|PASIRENGĘS IŠVYKTI
SENT_DEMO|TESTINIS SIUNTIMAS
BLOCKED_NO_CONSENT|NĖRA LEIDIMO SUSISIEKTI
QUEUED|EILĖJE
COMPLETED|BAIGTA
FAILED|KLAIDA
DEGRADED|VEIKIA IŠ DALIES
RUNNING|VYKDOMA
STOPPED|SUSTABDYTA
NOT_RUN|NEVYKDYTA
Fit|TINKAMUMAS
Interest|Susidomėjimas
Arrival|Atvykimas
Why|Priežastys
Eligible|Tinkamas
Review required|Reikia patikrinti
Open original ad|Atidaryti originalų skelbimą
Jobseeker ads|Darbo ieškančiųjų skelbimai
Back to Collector|Atgal į rinkimą
Profession / source market|Profesija / šaltinio šalis
Discovered|Rasta
Published|Paskelbta
welder|suvirintojas
mason|mūrininkas
mechanic|mechanikas
electrician|elektrikas
'''
LT=dict(line.split('|',1) for line in PAIRS.splitlines() if '|' in line)
# Legacy metric labels are capitalized.
for key,value in list(LT.items()):LT.setdefault(key.upper(),value.upper())

def translate(value,lang):
    if lang!='lt':return value
    key=re.sub(r'\s+',' ',str(value)).strip()
    return LT.get(key,value)

def language(request):return getattr(request.state,'language',request.cookies.get('et_language','en'))

class Translator(HTMLParser):
    def __init__(self,lang):super().__init__(convert_charrefs=True);self.lang=lang;self.output=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ['script','style']:self.skip+=1
        new=[]
        for key,val in attrs:
            if tag=='html' and key=='lang':val=self.lang
            elif key in ['placeholder','title','aria-label','alt'] and val:val=translate(val,self.lang)
            new.append(' '+key+('="'+html.escape(val,quote=True)+'"' if val is not None else ''))
        self.output.append('<'+tag+''.join(new)+'>')
    def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs)
    def handle_endtag(self,tag):
        self.output.append('</'+tag+'>')
        if tag in ['script','style']:self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        translated=translate(data,self.lang) if not self.skip else data
        if self.skip:self.output.append(data)
        elif translated==data:self.output.append(html.escape(data,quote=False))
        else:self.output.append(re.match(r'^\s*',data)[0]+html.escape(translated)+re.search(r'\s*$',data)[0])
    def handle_entityref(self,name):self.output.append('&'+name+';')
    def handle_charref(self,name):self.output.append('&#'+name+';')
    def handle_comment(self,data):self.output.append('<!--'+data+'-->')
    def handle_decl(self,decl):self.output.append('<!'+decl+'>')


def install(app,current_user):
    from collector.platform import UserPreference
    @app.middleware('http')
    async def localized(request,call_next):
        lang=request.cookies.get('et_language','en')
        if lang not in ['lt','en']:lang='en'
        # A cookie stores the browser choice; the account preference restores it after sign-in.
        if 'et_language' not in request.cookies and request.cookies.get('wl_session'):
            with SessionLocal() as db:
                user=current_user(request,db)
                pref=db.get(UserPreference,user.id) if user else None
                if pref:lang=pref.language
        request.state.language=lang
        response=await call_next(request)
        content_type=response.headers.get('content-type','')
        if 'text/html' not in content_type and not ('application/json' in content_type and response.status_code>=400):return response
        raw=b''.join([chunk async for chunk in response.body_iterator]);text=raw.decode('utf-8')
        if 'text/html' in content_type:
            # Preserve the original enum values when translating native option labels.
            def option(m):
                if re.search(r'\bvalue\s*=',m[2],re.I):return m[0]
                return m[1]+m[2]+' value="'+html.escape(html.unescape(m[4]),quote=True)+'">'+m[4]+m[5]
            text=re.sub(r'(<option)([^>]*)(>)([^<]*)(</option>)',option,text,flags=re.I)
            parser=Translator(lang);parser.feed(text);text=''.join(parser.output)
        elif lang=='lt':
            try:
                payload=json.loads(text)
                if isinstance(payload.get('detail'),str):payload['detail']=translate(payload['detail'],lang)
                text=json.dumps(payload,ensure_ascii=False)
            except (ValueError,AttributeError):pass
        headers=dict(response.headers);headers.pop('content-length',None)
        out=Response(text,status_code=response.status_code,headers=headers,media_type=None,background=response.background)
        # Preserve multiple Set-Cookie headers (intake CSRF and login session).
        out.raw_headers=[(k,v) for k,v in out.raw_headers if k.lower()!=b'set-cookie']+[(k,v) for k,v in response.raw_headers if k.lower()==b'set-cookie']
        if 'et_language' not in request.cookies and request.cookies.get('wl_session'):out.set_cookie('et_language',lang,max_age=31536000,secure=request.url.scheme=='https',samesite='lax',httponly=True)
        return out

    @app.get('/language/{lang}')
    def set_language(lang:str,request:Request,next:str='/',db=Depends(get_db)):
        if lang not in ['lt','en']:raise HTTPException(400,'Invalid language')
        user=current_user(request,db)
        if user:
            pref=db.get(UserPreference,user.id)
            if not pref:pref=UserPreference(user_id=user.id);db.add(pref)
            pref.language=lang;db.commit()
        target=next if next.startswith('/') and not next.startswith('//') and '\\' not in next and not any(ord(c)<32 for c in next) else '/'
        response=RedirectResponse(target,303);response.set_cookie('et_language',lang,max_age=31536000,secure=request.url.scheme=='https',samesite='lax',httponly=True)
        return response

LT.update(dict(line.split('|',1) for line in '''People ready.|Žmonės pasirengę.
Projects moving.|Projektai vyksta.
A live operating layer for Euroteams workforce, project demand and deployment readiness across Europe.|Euroteams darbuotojų, projektų poreikio ir pasirengimo išvykti valdymas Europoje.
Secure workspace|Saugi darbo aplinka
Welcome back|Sveiki sugrįžę
Sign in to manage Euroteams workforce operations.|Prisijunkite prie Euroteams darbuotojų valdymo sistemos.
Sign in to Workforce Live|Prisijungti prie platformos
Live worker availability|Darbuotojų pasirengimas dirbti
Project matching & recruitment|Projektų atitikimas ir atranka
Ready-to-deploy control|Pasirengimo išvykti valdymas
Workforce Live|Darbuotojų platforma
Candidate stage|Kandidato etapas
Candidate Screening|Kandidato patikra
Candidate pipeline & deployment blockers|Kandidatų eiga ir išvykimo kliūtys
Add team member|Pridėti komandos narį
Add worker|Pridėti darbuotoją
All outbound/inbound recruitment messages and provider states.|Visos siunčiamos ir gaunamos atrankos žinutės bei paslaugų teikėjų būsenos.
All worker availability is current.|Visų darbuotojų būsenos atnaujintos.
Are you available?|Ar galite dirbti?
Auditable communication permissions by worker, purpose and channel.|Atsekami leidimai susisiekti pagal darbuotoją, tikslą ir kanalą.
Availability needs confirmation|Pasirengimą dirbti reikia patvirtinti
Availability:|Pasirengimas dirbti:
Available now|Gali dirbti dabar
AVAILABLE PARTIALLY|DALIS BRIGADOS GALI DIRBTI
AVAILABLE TOGETHER|VISA BRIGADA GALI DIRBTI
Accepted|Priimta
Active projects|Aktyvūs projektai
AI recommends · Human decides|Sistema rekomenduoja · Žmogus nusprendžia
Approved source|Patvirtintas šaltinis
Back to application|Atgal į registraciją
Back to project|Atgal į projektą
Best current supply|Geriausiai tinkami darbuotojai
Blocked|Užblokuota
BLOCKED|UŽBLOKUOTA
Blockers / reservation|Kliūtys / rezervacija
Bulgaria|Bulgarija
By country|Pagal šalį
CSV file|CSV failas
Candidate privacy notice|Kandidato privatumo pranešimas
Candidate registration source|Kandidatų registracijos šaltinis
Carpenter|Stalius
Check All Readiness|Tikrinti visų pasirengimą
Check readiness|Tikrinti pasirengimą
Choose|Pasirinkti
Choose country|Pasirinkite šalį
Choose profession|Pasirinkite profesiją
Communication Outbox|Žinučių eilė
Confidence|Patikimumas
Confirm date|Patvirtinti datą
Consent to job offers via preferred channel|Leidimas siųsti darbo pasiūlymus pasirinktu kanalu
Country of residence *|Gyvenamoji šalis *
Create a project before importing or matching candidates. Worker registration works without a project.|Prieš importuodami ar atrinkdami kandidatus sukurkite projektą. Darbuotojų registracija veikia ir be projekto.
Create crew|Sukurti brigadą
Create user|Sukurti vartotoją
Create worker|Sukurti darbuotoją
Current Euroteams demand and staffing status.|Euroteams darbuotojų poreikis ir projektų užpildymas.
Define demand once. Let the system do the first 80–90%.|Aprašykite darbo poreikį, kad sistema galėtų atrinkti kandidatus.
Demand → matching → recruitment → deployment.|Poreikis → atitikimas → atranka → išvykimas.
Deployment state|Išvykimo būsena
Direction|Kryptis
Document expiry watch|Dokumentų galiojimo stebėjimas
Documents expired or expiring within 30 days.|Dokumentai, kurių galiojimas pasibaigęs arba baigsis per 30 dienų.
Documents verified|Dokumentai patikrinti
Driving licence|Vairuotojo pažymėjimas
Duplicates removed|Pašalinta dublikatų
EU citizen|ES pilietis
EU citizenship *|ES pilietybė *
Electrician|Elektrikas
Entity|Objektas
Existing crews|Esamos brigados
Expected CSV fields|Laukiami CSV laukai
Expected net pay, €/hour|Pageidaujamas atlygis į rankas, €/val.
Expected net €/h|Pageidaujamas atlygis į rankas, €/val.
FULFILLMENT|UŽPILDYMAS
Facebook group reading is not connected. Candidate registration links can be shared in groups with administrator permission.|Facebook grupių duomenų rinkimas neprijungtas. Kandidatų registracijos nuoroda galima dalytis gavus grupės administratoriaus leidimą.
Fill|Užpildyti
Free jobseeker discovery|Nemokama darbo ieškančiųjų paieška
Free public jobseeker discovery|Nemokama viešų darbo ieškančiųjų paieška
From a specific date|Nuo pasirinktos datos
Full name *|Vardas ir pavardė *
Identity & trade|Tapatybė ir profesija
Identity verified|Tapatybė patikrinta
Import & match|Importuoti ir atrinkti
Import candidates|Importuoti kandidatus
Import result|Importo rezultatas
Import approved candidate data, remove duplicates and match workers to a live project.|Importuokite leidžiamus kandidatų duomenis, pašalinkite dublikatus ir atrinkite darbuotojus projektui.
Italy|Italija
Last confirmed|Paskutinį kartą patvirtinta
Latest communication|Paskutinis susirašinėjimas
Latest operational changes across the platform.|Paskutiniai sistemos pakeitimai.
Latvia|Latvija
Leader worker ID|Brigadininko darbuotojo ID
Lithuania|Lietuva
Live data quality, compliance and project fill control.|Duomenų kokybės, atitikties ir projektų užpildymo valdymas.
Live distribution across markets and skills.|Pasiskirstymas pagal šalis ir įgūdžius.
Live matching preview|Atitikimo peržiūra
Live network, availability and deployment readiness.|Darbuotojų tinklas, pasirengimas dirbti ir išvykti.
Location|Vieta
Mason|Mūrininkas
Match|Atitikimas
Match existing Workforce database|Atrinkti iš esamos darbuotojų bazės
Mechanic|Mechanikas
Message|Žinutė
Metal fitter|Konstrukcijų montuotojas
Need|Poreikis
New portal workers|Nauji registruoti darbuotojai
New project matches|Nauji projektų atitikmenys
New workers|Nauji darbuotojai
Next step|Kitas žingsnis
No active projects.|Aktyvių projektų nėra.
No activity yet.|Veiksmų dar nėra.
No consent records.|Leidimų įrašų nėra.
No crews yet.|Brigadų dar nėra.
No expiring documents.|Besibaigiančių dokumentų nėra.
No matching advertisements have been collected yet.|Tinkamų skelbimų kol kas nerasta.
No matching projects right now.|Tinkamų projektų šiuo metu nėra.
No outreach yet.|Susisiekimo įrašų dar nėra.
Not checked yet|Dar netikrinta
Not interested|Nesusidomėjo
Notes|Pastabos
Official RSS source, no paid API. Only explicit work-seeking ads are retained.|Oficialus RSS šaltinis be mokamos API. Saugomi tik aiškūs darbo ieškojimo skelbimai.
Open|Atidaryti
Open free jobseeker leads|Atidaryti nemokamus darbo ieškančiųjų skelbimus
Open to offers|Laukia pasiūlymų
Operations Center|Operacijų centras
Optional — after taxes.|Neprivaloma — po mokesčių.
Own car|Nuosavas automobilis
Phone with country code|Telefonas su šalies kodu
Pipefitter|Vamzdynų montuotojas
Poland|Lenkija
Prefer to discuss with recruiter|Norėčiau aptarti su atrankos specialistu
Preferences|Pageidavimai
Preferred channel|Pageidaujamas kanalas
Preferred language|Pageidaujama kalba
Preferred rotation|Pageidaujama rotacija
Preferred work countries|Pageidaujamos darbo šalys
Privacy notice|Privatumo pranešimas
privacy notice|privatumo pranešimą
Profession *|Profesija *
Project fulfillment|Projekto užpildymas
Project screening|Projekto patikra
Projects for you|Jums tinkami projektai
Purpose|Tikslas
Qualified / ready|Tinkami / pasirengę
Questions & answers|Klausimai ir atsakymai
Queue all stale availability checks|Įtraukti visas pasenusias būsenas į tikrinimo eilę
Queue check|Įtraukti tikrinimą į eilę
Rate|Atlygis
Re-match database|Atnaujinti bazės atitikmenis
Ready|Pasirengęs
Recent activity|Paskutiniai veiksmai
Recent public work-seeking advertisements from an official RSS feed. No paid data API.|Naujausi vieši darbo ieškojimo skelbimai iš oficialaus RSS srauto. Mokama API nenaudojama.
Recorded|Užregistruota
Recruitment activity|Atrankos veiksmai
Refresh is limited to once every four hours. No phone numbers, emails or full advertisement bodies are copied.|Atnaujinama ne dažniau nei kas keturias valandas. Telefonai, el. paštai ir visas skelbimų tekstas nekopijuojami.
Refreshed matches|Atnaujinti atitikmenys
Register for construction, shipyard and industrial opportunities across Europe.|Registruokitės statybų, laivų statybos ir pramonės darbams Europoje.
Registration does not guarantee work.|Registracija darbo negarantuoja.
Rejected rows / errors|Atmestos eilutės / klaidos
Release|Atlaisvinti
Repeat applications|Pakartotinės registracijos
Reported role|Nurodyta profesija
Reserve 48h|Rezervuoti 48 val.
Retention and your choices|Saugojimas ir jūsų teisės
Retrieved|Gauta
Review and matching|Peržiūra ir atranka
Role / access|Rolė / prieiga
Role-based access: admin, recruiter and viewer.|Prieiga pagal rolę: administratorius, atrankos specialistas ir stebėtojas.
Romania|Rumunija
Rows|Eilutės
Run Follow-ups|Paruošti priminimus
Run Recruitment Autopilot|Paleisti automatinę atranką
Save answer|Išsaugoti atsakymą
Scaffolder|Pastolininkas
Screening|Patikra
Screening has not started.|Patikra nepradėta.
Screening status|Patikros būsena
Seed records are not evidence of real acquisition.|Demonstraciniai įrašai neįrodo tikrų kandidatų surinkimo.
Send my application|Pateikti paraišką
Send offer|Paruošti pasiūlymą
Share|Dalis
Skills verified|Įgūdžiai patikrinti
Source evidence|Šaltinio duomenys
Source state:|Šaltinio būsena:
Source status:|Šaltinio būsena:
Source:|Šaltinis:
Sourced professional profiles|Surinkti profesiniai profiliai
Spain|Ispanija
Stage|Etapas
Start|Pradžia
Start structured screening|Pradėti struktūrinę patikrą
Status:|Būsena:
Structured profile — CV is optional, data is primary.|Struktūrinis profilis — CV neprivalomas, svarbiausi duomenys.
Submit screening|Pateikti patikrą
Team & Roles|Komanda ir rolės
Team members|Komandos nariai
Teams that can move together — a key industrial workforce unit.|Kartu galinčios išvykti brigados pramonės projektams.
Temporary password|Laikinas slaptažodis
Thank you for your application.|Dėkojame už registraciją.
Top professions|Populiariausios profesijos
Traceability for automation, compliance and human overrides.|Automatinių veiksmų, atitikties ir darbuotojų pakeitimų atsekamumas.
Trade|Profesija
Updated workers|Atnaujinti darbuotojai
View all →|Peržiūrėti visus →
View sourced profiles and evidence|Peržiūrėti surinktus profilius ir šaltinius
Website|Interneto svetainė
Welder|Suvirintojas
When can you start? *|Kada galite pradėti? *
Work-seeking advertisement|Darbo ieškojimo skelbimas
Workforce command center|Darbuotojų valdymo centras
Workforce intelligence|Darbuotojų apžvalga
YES — AVAILABLE NOW|TAIP — GALIU DIRBTI DABAR
Years experience|Patirties metai
Years of experience|Patirties metai
Your application|Jūsų paraiška
Your skills. Your next project.|Jūsų įgūdžiai. Jūsų kitas projektas.
admin|administratorius
recruiter|atrankos specialistas
viewer|stebėtojas
from|nuo
yrs|m.
NOT_SENT_API_NOT_CONFIGURED|NEIŠSIŲSTA — API NEPRIJUNGTA
NOT_RUN|NEVYKDYTA
'''.splitlines() if '|' in line))

LT.update(dict(line.split('|',1) for line in '''Tell us when you can start and what work you want. Our team will review your details; registration does not guarantee an offer.|Nurodykite, kada galite pradėti ir kokio darbo ieškote. Mūsų komanda peržiūrės informaciją; registracija darbo pasiūlymo negarantuoja.
Please provide at least one contact method. Your experience, certificates and availability are self-declared until reviewed by a recruiter.|Pateikite bent vieną kontaktą. Patirtis, sertifikatai ir pasirengimas dirbti laikomi jūsų nurodytais duomenimis, kol juos patikrins atrankos specialistas.
I have read the|Perskaičiau
and request Euroteams to consider my application. *|ir prašau Euroteams apsvarstyti mano paraišką. *
I also agree to receive relevant job offers by email (or WhatsApp if I provide only a phone number). Optional; I can withdraw at any time.|Taip pat sutinku gauti tinkamus darbo pasiūlymus el. paštu (arba per WhatsApp, jei pateikiau tik telefono numerį). Neprivaloma; leidimą galiu atšaukti bet kada.
Our team will review the information provided. If we have a suitable opportunity, we may contact you using the details you supplied.|Mūsų komanda peržiūrės pateiktą informaciją. Turėdami tinkamą pasiūlymą galime su jumis susisiekti nurodytais kontaktais.
For privacy, repeat applications do not change an existing worker profile. To correct your details, contact|Siekiant apsaugoti privatumą, pakartotinė registracija nekeičia esamo profilio. Norėdami pataisyti duomenis, susisiekite:
Application received · Euroteams|Paraiška gauta · Euroteams
Candidate privacy · Euroteams|Kandidato privatumas · Euroteams
Work in Europe · Euroteams|Darbas Europoje · Euroteams
Controller: UAB Euroteams Group, Lithuania, company code 302411430. Contact:|Duomenų valdytojas: UAB Euroteams Group, Lietuva, įmonės kodas 302411430. Kontaktai:
We collect the contact details, residence country, profession, experience, certificates, languages, availability and work preferences you choose to provide. We process your application to consider you for recruitment at your request. Optional permission for future job offers is recorded separately and may be withdrawn without affecting your current application.|Renkame jūsų pasirinktus pateikti kontaktus, gyvenamąją šalį, profesiją, patirtį, sertifikatus, kalbas, pasirengimą dirbti ir darbo pageidavimus. Jūsų prašymu tvarkome paraišką kandidatūrai apsvarstyti. Neprivalomas leidimas siųsti būsimus pasiūlymus įrašomas atskirai; jo atšaukimas nedaro įtakos dabartinei paraiškai.
Your information is stored in Euroteams' recruitment system hosted on Render and compared with project requirements. Matching supports recruiter review; it does not make a final employment decision. Self-declared qualifications and availability are not independently verified by submitting this form. Your profile is accessible to authorized Euroteams staff. Further sharing with a client requires a separate recruitment step.|Informacija saugoma Render talpinamoje Euroteams atrankos sistemoje ir palyginama su projektų reikalavimais. Atitikimo vertinimas padeda atrankos specialistui, tačiau nepriima galutinio sprendimo dėl įdarbinimo. Šios formos pateikimas nepatvirtina jūsų nurodytos kvalifikacijos ar pasirengimo dirbti. Profilį mato įgalioti Euroteams darbuotojai. Dalijimasis su klientu yra atskiras atrankos žingsnis.
We retain applications for up to 24 months after the last recruitment interaction, unless a shorter period is requested or another justified obligation applies. Contact us to request access, correction, export, deletion, restriction or withdrawal of job-offer permission. Retention review and these requests are currently handled by Euroteams staff, rather than automatically.|Paraiškas saugome iki 24 mėnesių nuo paskutinio atrankos kontakto, nebent prašote trumpesnio laikotarpio arba taikoma kita pagrįsta prievolė. Kreipkitės dėl prieigos, taisymo, eksporto, ištrynimo, apribojimo ar leidimo siųsti pasiūlymus atšaukimo. Saugojimo terminus ir šiuos prašymus šiuo metu tvarko Euroteams darbuotojai.
A form-security cookie lasts up to one hour. A keyed, non-public network identifier limits abusive submissions; no advertising cookies are used by this registration form. You may complain to the Lithuanian State Data Protection Inspectorate.|Formos saugumo slapukas galioja iki vienos valandos. Neviešas apsaugotas tinklo identifikatorius riboja piktnaudžiavimą; reklaminiai slapukai formoje nenaudojami. Skundą galite pateikti Valstybinei duomenų apsaugos inspekcijai.
Version: candidate-intake-v1 · 24 October 2026|Versija: candidate-intake-v1 · 2026 m. spalio 24 d.
Thank you for your application.|Dėkojame už paraišką.
Alternative common column names are recognized automatically. Rows without a contact method or without name, country or profession are rejected.|Įprasti alternatyvūs stulpelių pavadinimai atpažįstami automatiškai. Eilutės be kontakto, vardo, šalies ar profesijos atmetamos.
UTF-8 CSV · maximum 5 MB. Use only candidate exports or feeds that Euroteams is permitted to process for recruitment.|UTF-8 CSV · iki 5 MB. Naudokite tik kandidatų eksportus ar srautus, kuriuos Euroteams gali tvarkyti atrankos tikslais.
No profiles collected yet. Check source status in Worker Collector.|Profilių dar nesurinkta. Šaltinio būseną rasite rinkimo skiltyje.
Profiles retrieved from the provider. Availability and permission for outreach are not confirmed.|Profilius pateikė duomenų tiekėjas. Pasirengimas dirbti ir leidimas susisiekti nepatvirtinti.
These are leads to original advertisements, not verified worker profiles. Availability for Euroteams projects, identity, certificates, language and permission for further contact still require confirmation. Service-only advertisements are filtered out.|Tai nuorodos į originalius skelbimus, o ne patikrinti darbuotojų profiliai. Dar reikia patvirtinti pasirengimą Euroteams projektams, tapatybę, sertifikatus, kalbas ir leidimą toliau susisiekti. Vien paslaugų reklamos skelbimai atmetami.
Re-score workers already stored in Workforce against the latest project requirements. Existing candidate rows are refreshed instead of duplicated.|Darbuotojai iš naujo vertinami pagal naujausius projekto reikalavimus. Esami kandidatų įrašai atnaujinami, o ne dubliuojami.
Recruiters can operate staffing workflows. Viewers are read-only by policy; admin manages users and settings.|Atrankos specialistai valdo atranką. Stebėtojai gali tik peržiūrėti; administratorius valdo vartotojus ir nustatymus.
No active projects yet. Create the first project to start matching workers.|Aktyvių projektų nėra. Sukurkite pirmą projektą, kad pradėtumėte darbuotojų atranką.
Recruitment has not started. Use Recruitment Autopilot to build the pipeline.|Atranka nepradėta. Paleiskite automatinę atranką kandidatų sąrašui sudaryti.
Run Autopilot to expand outreach to the best matches.|Paleiskite automatinę atranką tinkamiausiems kandidatams atrinkti.
Start Recruitment Autopilot to build the pipeline.|Paleiskite automatinę atranką kandidatų sąrašui sudaryti.
Unknown or not confirmed in the last 21 days.|Nežinoma arba nepatvirtinta per paskutines 21 dieną.
Your work profile is private. Keep your availability current to receive relevant projects.|Jūsų darbo profilis privatus. Atnaujinkite pasirengimo dirbti būseną, kad gautumėte tinkamus projektus.
SS.COM · Latvia · welders, masons, mechanics, electricians|SS.COM · Latvija · suvirintojai, mūrininkai, mechanikai, elektrikai
Required CSV columns: full_name, country, profession. Optional: phone, email, skills, certificates, languages, preferred_countries, rotation, expected_salary_net_hour, availability_status, available_from.|Privalomi CSV stulpeliai: full_name, country, profession. Neprivalomi: phone, email, skills, certificates, languages, preferred_countries, rotation, expected_salary_net_hour, availability_status, available_from.
Recruiter confirmed sending the message in WhatsApp|Atrankos specialistas patvirtino siuntimą per WhatsApp
Enter your full name, country and profession|Įveskite vardą, pavardę, šalį ir profesiją
Enter an email address or phone number|Įveskite el. paštą arba telefono numerį
Enter a valid email address|Įveskite tinkamą el. pašto adresą
Enter a valid phone number including country code|Įveskite tinkamą telefono numerį su šalies kodu
Please acknowledge the privacy notice|Patvirtinkite, kad perskaitėte privatumo pranešimą
Check experience and expected hourly pay|Patikrinkite patirtį ir pageidaujamą valandinį atlygį
Select your availability|Pasirinkite pasirengimo dirbti būseną
Select the date you can start|Pasirinkite, kada galite pradėti
English, Polish…|Anglų, lenkų…
Netherlands, Finland…|Nyderlandai, Suomija…
EUROTEAMS GROUP|EUROTEAMS GROUP
New jobs are matched automatically. Review suitability before contacting candidates.|Naujiems darbams darbuotojai atrenkami automatiškai. Prieš susisiekdami patikrinkite tinkamumą.
'''.splitlines() if '|' in line))
for key,value in list(LT.items()):LT.setdefault(key.upper(),value.upper())

LT['Paid automatic collection is disabled. Previously sourced professional profiles require availability, citizenship and contact-permission checks.']='Automatinis mokamas rinkimas išjungtas. Anksčiau gautuose profesiniuose profiliuose reikia patikrinti pasirengimą dirbti, pilietybę ir leidimą susisiekti.'

LT.update({'NL':'Nyderlandai','LT':'Lietuva','LV':'Latvija','PL':'Lenkija','RO':'Rumunija','BG':'Bulgarija','ES':'Ispanija','IT':'Italija','Netherlands':'Nyderlandai','Finland':'Suomija','Sweden':'Švedija','Germany':'Vokietija','English':'Anglų','Polish':'Lenkų','Lithuanian':'Lietuvių','PIPELINE STRENGTH':'ATRANKOS APRĖPTIS','LIVE PIPELINE':'KANDIDATŲ EIGA','PROJECT COMMAND CENTER':'PROJEKTO VALDYMAS','RECOMMENDED NEXT ACTION':'REKOMENDUOJAMAS KITAS VEIKSMAS','REMAINING':'LIKĘ','SECURED':'UŽTIKRINTA','48H RESERVED':'REZERVUOTA 48 VAL.','SCREENING COMPLETE':'PATIKRA BAIGTA','START':'PRADŽIA','WEEKS':'SAVAITĖS','RATE':'ATLYGIS','CALCULATING URGENCY…':'VERTINAMAS SKUBUMAS…','CHECK NOW':'TIKRINTI DABAR','STALE AVAILABILITY':'PASENUSI BŪSENA','EXPIRING / EXPIRED DOCS':'BESIBAIGIANTYS / NEBEGALIOJANTYS DOKUMENTAI'})

LT['Euroteams Group · Internal operations platform']='Euroteams Group · Vidinė darbo platforma'
LT.update({'Matching uses supplied information. Missing data requires verification; scores are not a prediction of interest or arrival.':'Atranka remiasi pateikta informacija. Trūkstamus duomenis reikia patikrinti; balai neprognozuoja susidomėjimo ar atvykimo.','exact role':'Profesija sutampa','EU citizen':'ES pilietis','certificates match':'Sertifikatai sutampa','language match':'Kalba sutampa','experience':'Nurodyta patirtis','available':'Gali dirbti','available by start':'Gali pradėti laiku','rate accepted range':'Atlygio lūkesčiai atitinka','availability not confirmed':'Pasirengimas dirbti nepatvirtintas','availability not verified':'Pasirengimo dirbti data nepatvirtinta','contact not provided':'Kontaktai nepateikti','EU citizenship not confirmed':'ES pilietybė nepatvirtinta','role mismatch':'Profesija neatitinka','required language not confirmed':'Reikalinga kalba nepatvirtinta','rate above offer':'Atlygio lūkesčiai viršija pasiūlymą','available after project start':'Gali pradėti po projekto pradžios','unsupported source country':'Šaltinio šalis nepalaikoma','UAB Euroteams Group · Lithuania ·':'UAB Euroteams Group · Lietuva ·'})

LT['Main navigation']='Pagrindinis meniu'

LT.update({'I agree to receive relevant job offers by email, if provided. Optional; I can withdraw at any time.':'Sutinku gauti tinkamus darbo pasiūlymus el. paštu, jei jį pateikiau. Neprivaloma; leidimą galiu bet kada atšaukti.','I agree to receive relevant job offers on WhatsApp at the phone number above. Optional; I can withdraw at any time.':'Sutinku gauti tinkamus darbo pasiūlymus per WhatsApp aukščiau nurodytu telefonu. Neprivaloma; leidimą galiu bet kada atšaukti.','Enter a valid WhatsApp number including country code':'Įveskite tinkamą WhatsApp numerį su šalies kodu'})

LT.update({'Employer registration required':'Reikalinga darbdavio registracija','A verified employer account is required to access CVs. Automatic export or API access has not been confirmed.':'CV peržiūrai reikalinga patvirtinta darbdavio paskyra. Automatinis eksportas ar API prieiga nepatvirtinti.','Employer registration':'Darbdavio registracija','Collection history':'Rinkimo istorija','Counts refer to public advertisements, not verified workers. Cached checks do not create new runs.':'Skaičiuojami vieši skelbimai, o ne patikrinti darbuotojai. Patikrinimai iš podėlio nesukuria naujų vykdymų.','Duration, seconds':'Trukmė sekundėmis','History starts with the next scheduled collection. Earlier run durations were not recorded.':'Istorija pradedama nuo kito rinkimo. Ankstesnių vykdymų trukmė nebuvo registruojama.','Only advertisements published and seen in the last 30 days are shown. Undated advertisements use their last-seen date.':'Rodomi tik per paskutines 30 dienų paskelbti ir matyti skelbimai. Jei paskelbimo datos nėra, naudojama paskutinio aptikimo data.'})

LT.update({'Check sources now':'Patikrinti šaltinius dabar','Manual checks are limited to once every 15 minutes. Automatic collection continues every 6 hours.':'Rankinė patikra galima ne dažniau nei kas 15 minučių. Automatinis rinkimas tęsiamas kas 6 valandas.'})

LT.update({'Public jobseekers with phone numbers':'Vieši darbo ieškančių žmonių telefonai','Public contact discovery without registration. Names, availability and messaging permission remain unverified.':'Viešų kontaktų paieška be registracijos. Vardai, pasirengimas dirbti ir leidimas siųsti žinutes lieka nepatvirtinti.','New profiles':'Nauji profiliai','View profiles':'Peržiūrėti profilius'})
