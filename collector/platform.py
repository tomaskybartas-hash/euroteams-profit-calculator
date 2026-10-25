"""Recruiter workspace: provenance, segmented search, honest WhatsApp drafts and contact history."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import hashlib, hmac, os, re, secrets
from urllib.parse import quote, urlencode
from fastapi import Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, event, or_
from sqlalchemy.orm import Mapped, mapped_column, Session, with_loader_criteria
from app.db import Base, get_db
from app.models import Worker, Project, ProjectCandidate, Consent, Message, Tenant, AppUser
from collector.intake import CandidateIntake, signer
from collector.coresignal import SourceProfile
from collector.free_sources import FreeLead, FreeSourceState, FreeCollectionRun, fresh_leads, STATE_ID

SEGMENTS={'general':'General Labour','welder':'Welders','pipefitter':'Pipefitters','fitter':'Fitters','mechanic':'Mechanics','carpenter':'Carpenters','mason':'Masons','electrician':'Electricians','scaffolder':'Scaffolders','other':'Other'}
STATUSES=['New','Available','Contacted','Interested','Not Interested','In Process','Hired','Unavailable','Stale']
SEED_EMAILS=('piotr@example.com','marek@example.com','tomas.p@example.com','andrei@example.com')

class WorkerContact(Base):
    __tablename__='platform_worker_contacts'
    worker_id: Mapped[int]=mapped_column(ForeignKey('workers.id'),primary_key=True)
    whatsapp: Mapped[str]=mapped_column(String(40),default='')
    status: Mapped[str]=mapped_column(String(40),default='New')
    source: Mapped[str]=mapped_column(String(200),default='')
    last_contacted: Mapped[datetime | None]=mapped_column(DateTime,nullable=True)

class ContactHistory(Base):
    __tablename__='platform_contact_history'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id'),index=True)
    worker_id: Mapped[int]=mapped_column(ForeignKey('workers.id'),index=True)
    project_id: Mapped[int | None]=mapped_column(ForeignKey('projects.id'),nullable=True,index=True)
    actor_id: Mapped[int]=mapped_column(ForeignKey('app_users.id'))
    channel: Mapped[str]=mapped_column(String(30),default='WhatsApp')
    status: Mapped[str]=mapped_column(String(40),default='DRAFT_PREPARED')
    body: Mapped[str]=mapped_column(Text,default='')
    note: Mapped[str]=mapped_column(Text,default='')
    nonce: Mapped[str]=mapped_column(String(100),unique=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class UserPreference(Base):
    __tablename__='platform_user_preferences'
    user_id: Mapped[int]=mapped_column(ForeignKey('app_users.id'),primary_key=True)
    language: Mapped[str]=mapped_column(String(5),default='en')

# Original bundle contains four demonstration workers. Keep their records for recovery,
# but exclude them from every Worker SELECT and therefore matching and live statistics.
@event.listens_for(Session,'do_orm_execute')
def hide_demo_workers(state):
    if state.is_select and not state.execution_options.get('include_demo_workers'):
        state.statement=state.statement.options(with_loader_criteria(Worker,lambda w:~w.email.in_(SEED_EMAILS),include_aliases=True))


def asset_version():
    return hashlib.sha256((Path(__file__).parents[1]/'app'/'static'/'styles.css').read_bytes()).hexdigest()[:12]


def segment(worker):
    value=(worker.profession+' '+worker.skills).lower()
    rules=[('welder',r'weld|suvir|свар'),('pipefitter',r'pipefitt|vamzd'),('carpenter',r'carpent|stali|столяр'),('mason',r'mason|mūrin|murini|камен'),('electrician',r'electric|elektr'),('mechanic',r'mechan|mechani'),('scaffolder',r'scaffold|pastolin'),('fitter',r'fitter|montuot|assembl|metal fitter'),('general',r'general|labour|labor|helper|nekval|pagalbin')]
    return next((key for key,pattern in rules if re.search(pattern,value)),'other')


def international_number(value):
    value=str(value or '').strip()
    if value.startswith('00'):value='+'+value[2:]
    value=re.sub(r'[ ()\-.]','',value)
    if not re.fullmatch(r'\+[1-9][0-9]{7,14}',value):return ''
    return value


def whatsapp_number(worker,meta=None):
    if meta and meta.whatsapp:return international_number(meta.whatsapp)
    return international_number(worker.phone) if worker.preferred_channel.lower()=='whatsapp' else ''


def consent_allowed(db,worker_id):
    latest=db.query(Consent).filter(Consent.worker_id==worker_id,Consent.channel=='WhatsApp',Consent.purpose=='job_offers').order_by(Consent.created_at.desc(),Consent.id.desc()).first()
    return bool(latest and latest.granted and latest.revoked_at is None)


def csrf(request):
    session=request.cookies.get('wl_session','')
    return signer().dumps({'session':hashlib.sha256(session.encode()).hexdigest()})


def verify_csrf(request,form):
    try:
        data=signer().loads(str(form.get('csrf','')),max_age=7200)
        if not hmac.compare_digest(data['session'],hashlib.sha256(request.cookies.get('wl_session','').encode()).hexdigest()):raise ValueError()
    except Exception:raise HTTPException(403,'Refresh the page and try again')
    origin=request.headers.get('origin')
    if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):raise HTTPException(403,'Not permitted')


def render_offer(worker,job,lang):
    from collector.localization import translate
    first=worker.full_name.split()[0]
    country=translate(job.country,lang);profession=translate(job.profession,lang)
    accommodation=translate(job.accommodation or '—',lang)
    salary=f'€{job.salary_net_hour:.2f}/h net' if job.salary_net_hour else ('To be agreed' if lang=='en' else 'Derinama')
    values=[job.city+', '+country if job.city else country,salary,job.rotation or '—',str(job.start_date),accommodation]
    if lang=='lt':
        return f'Sveiki, {first},\n\nsusisiekiame iš Euroteams Group.\nŠiuo metu turime darbo pasiūlymą: {profession}, {country}.\n\nPagrindinė informacija:\n• Darbo vieta: {values[0]}\n• Atlyginimas: {values[1].replace("/h net","/val. į rankas")}\n• Rotacija: {values[2]}\n• Pradžia: {values[3]}\n• Apgyvendinimas: {values[4]}\n\nAr šis pasiūlymas jums būtų įdomus?\n\nEuroteams Group'
    return f'Hello {first},\n\nWe are contacting you from Euroteams Group.\nWe currently have a job opportunity for a {profession} position in {country}.\n\nMain information:\n• Location: {values[0]}\n• Salary: {values[1]}\n• Rotation: {values[2]}\n• Start date: {values[3]}\n• Accommodation: {values[4]}\n\nWould you be interested in this opportunity?\n\nEuroteams Group'


def install(app,current_user,require_roles,page_ctx):
    import shutil
    shutil.copyfile(Path(__file__).parent/"templates"/"worker_detail.html",Path(__file__).parents[1]/"app"/"templates"/"worker_detail.html")
    shutil.copyfile(Path(__file__).parent/'assets'/'euroteams-logo.svg',Path(__file__).parents[1]/'app'/'static'/'euroteams-logo.svg')
    form_path=Path(__file__).parents[1]/'app'/'templates'/'project_form.html'
    form_html=form_path.read_text()
    if 'name="csrf"' not in form_html:
        form_html=form_html.replace('class="card form-grid">','class="card form-grid"><input type="hidden" name="csrf" value="{{platform_csrf}}">',1)
        form_path.write_text(form_html)
    from collector.localization import install as locale_install, translate, language
    locale_install(app,current_user)
    views=Jinja2Templates(directory=[str(Path(__file__).parent/'templates'),str(Path(__file__).parents[1]/'app'/'templates')])
    def ctx(request,user,**kw):
        return page_ctx(request,user,asset_version=asset_version(),csrf_token=csrf(request),lang=language(request),t=lambda text:translate(text,language(request)),segments=SEGMENTS,completeness=__import__('collector.matching',fromlist=['completeness']).completeness,**kw)
    def render(request,user,template,**kw):return views.TemplateResponse(request,template,ctx(request,user,**kw))
    def user_for(request,db):
        user=current_user(request,db)
        if not user:raise HTTPException(401,'Login required')
        return user
    def worker_for(db,wid,user):
        w=db.query(Worker).filter(Worker.id==wid,Worker.tenant_id==user.tenant_id).first()
        if not w:raise HTTPException(404,'Worker not found')
        return w
    @app.on_event('startup')
    def production_session_key():
        # The bundled development key must never protect a public production session.
        if len(os.getenv('APP_SECRET',''))<32:
            source=os.getenv('INTAKE_FORM_SECRET','')
            if len(source)<32:raise RuntimeError('A strong application session secret is required')
            import app.services.auth as auth
            from itsdangerous import URLSafeTimedSerializer
            key=hmac.new(source.encode(),b'euroteams-session-key-v1',hashlib.sha256).hexdigest()
            auth.serializer=URLSafeTimedSerializer(key,salt='workforce-live-session')
    from collector.matching import ranked_workers as evidence_ranked
    import app.services.matching as matching
    matching.ranked_workers=evidence_ranked
    import sys
    sys.modules['app.main'].ranked_workers=evidence_ranked
    # A provider must never claim a real send when no external messaging API exists.
    import app.services.messaging as messaging
    class UnconfiguredProvider(messaging.MessagingProvider):
        def send(self,channel,destination,body):
            return messaging.SendResult(status='NOT_SENT_API_NOT_CONFIGURED',provider_id='')
    messaging.DemoMessagingProvider=UnconfiguredProvider
    messaging.has_consent=lambda db,wid,channel: consent_allowed(db,wid) if channel=='WhatsApp' else bool(db.query(Consent).filter(Consent.worker_id==wid,Consent.channel==channel,Consent.granted==True,Consent.revoked_at.is_(None)).first())
    app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path','') in ['/projects/{project_id}','/workers/{worker_id}'] and 'GET' in getattr(r,'methods',set()))]
    # Static export must precede the legacy /workers/{worker_id} matcher.
    exports=[r for r in app.router.routes if getattr(r,'path','')=='/workers/export.csv']
    app.router.routes[:]=exports+[r for r in app.router.routes if r not in exports]
    # Replace only specified pages; retain existing create/import/document workflows.
    app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path','') in ['/','/workers'] and 'GET' in getattr(r,'methods',set()))]

    app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path','')=='/projects/new' and 'POST' in getattr(r,'methods',set()))]
    @app.post('/projects/new')
    async def create_job(request:Request,db:Session=Depends(get_db)):
        user=user_for(request,db);require_roles(user,'admin','recruiter');form=await request.form()
        # Legacy project form receives a signed token below during HTML rendering.
        verify_csrf(request,form)
        try:
            fields={k:str(form.get(k,'')).strip() for k in ['name','client','country','city','profession','rotation','required_language','citizenship_requirement','required_certificates','requirements','accommodation','travel']}
            if not all(fields[k] for k in ['name','country','profession']) or any(len(v)>4000 for v in fields.values()):raise ValueError()
            fields.update(start_date=date.fromisoformat(str(form.get('start_date',''))),workers_needed=int(str(form.get('workers_needed','1'))),duration_weeks=int(str(form.get('duration_weeks','8'))),weekly_hours=int(str(form.get('weekly_hours','50'))),salary_net_hour=float(str(form.get('salary_net_hour','0'))))
            if not (1<=fields['workers_needed']<=10000 and 1<=fields['weekly_hours']<=84 and 1<=fields['duration_weeks']<=520 and 0<=fields['salary_net_hour']<=1000):raise ValueError()
        except (ValueError,TypeError):raise HTTPException(400,'Check job fields')
        job=Project(tenant_id=user.tenant_id,**fields);db.add(job);db.flush()
        from app.services.matching import ranked_workers
        for w,result in ranked_workers(db,job,user.tenant_id,limit=100,include_ineligible=True):
            db.add(ProjectCandidate(project_id=job.id,worker_id=w.id,match_score=result['match_score'],fit_score=result.get('fit_score',0),interest_probability=result.get('interest_probability',0),arrival_probability=result.get('arrival_probability',0),data_confidence=result.get('data_confidence',0),eligibility='PASS' if result['eligible'] else 'REVIEW',stage='MATCHED'))
        db.commit()
        return RedirectResponse(f'/projects/{job.id}',303)

    @app.get('/',response_class=HTMLResponse)
    def home(request:Request,db:Session=Depends(get_db)):
        user=current_user(request,db)
        if not user:return RedirectResponse('/login',303)
        rows=db.query(Worker).filter(Worker.tenant_id==user.tenant_id).all()
        now=datetime.utcnow();local_now=now.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Europe/Vilnius'));counts={k:0 for k in SEGMENTS}
        local_date=lambda value:value.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Europe/Vilnius')).date()
        next_tick=min(now.replace(hour=h,minute=17,second=0,microsecond=0)+timedelta(days=d) for d in [0,1] for h in [0,6,12,18] if now.replace(hour=h,minute=17,second=0,microsecond=0)+timedelta(days=d)>now)
        for w in rows:counts[segment(w)]+=1
        jobs=db.query(Project).filter(Project.tenant_id==user.tenant_id,Project.status!='CLOSED').all()
        contacts=db.query(ContactHistory).filter(ContactHistory.tenant_id==user.tenant_id)
        from collector.offer_responses import OfferResponse
        interested={wid for (wid,) in db.query(WorkerContact.worker_id).join(Worker,Worker.id==WorkerContact.worker_id).filter(Worker.tenant_id==user.tenant_id,WorkerContact.status=='Interested').all()}
        interested.update(wid for (wid,) in db.query(OfferResponse.worker_id).join(Worker,Worker.id==OfferResponse.worker_id).filter(OfferResponse.tenant_id==user.tenant_id,Worker.tenant_id==user.tenant_id,OfferResponse.answer=='INTERESTED').all())
        stats={'Total Workers':len(rows),'Available Workers':sum(w.availability_status=='AVAILABLE NOW' for w in rows),'New Today':sum(local_date(w.created_at)==local_now.date() for w in rows),'New This Week':sum(w.created_at>=now-timedelta(days=7) for w in rows),'Contacted':contacts.filter(ContactHistory.status=='CONTACTED').count(),'Interested':len(interested),'Active Jobs':len(jobs),'Matches':db.query(ProjectCandidate).join(Project).filter(Project.tenant_id==user.tenant_id,Project.status!='CLOSED').count()}
        return render(request,user,'platform_dashboard.html',next_run=next_tick.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Europe/Vilnius')).strftime('%Y-%m-%d %H:%M %Z'),stats=stats,counts=counts,jobs=jobs[:6],state=db.get(FreeSourceState,STATE_ID),leads=fresh_leads(db,user.tenant_id).count())

    @app.get('/workers',response_class=HTMLResponse)
    def workers(request:Request,db:Session=Depends(get_db)):
        user=current_user(request,db)
        if not user:return RedirectResponse('/login',303)
        f=dict(request.query_params);query=db.query(Worker).filter(Worker.tenant_id==user.tenant_id)
        fields={'country':Worker.country,'city':Worker.city,'skills':Worker.skills,'certificates':Worker.certificates,'languages':Worker.languages,'preferred_country':Worker.preferred_countries,'process':Worker.skills,'profession':Worker.profession}
        for key,col in fields.items():
            if f.get(key):
                if key=='process':query=query.filter(or_(Worker.skills.ilike('%'+f[key][:150]+'%'),Worker.profession.ilike('%'+f[key][:150]+'%'),Worker.certificates.ilike('%'+f[key][:150]+'%')))
                else:query=query.filter(col.ilike('%'+f[key][:150]+'%'))
        if f.get('q'):
            like='%'+f['q'][:150]+'%';query=query.filter(or_(*[col.ilike(like) for col in [Worker.full_name,Worker.phone,Worker.email,Worker.profession,Worker.country,Worker.skills,Worker.certificates]]))
        if f.get('availability'):query=query.filter(Worker.availability_status==f['availability'])
        if f.get('verified')=='yes':query=query.filter(Worker.identity_verified==True,Worker.documents_verified==True,Worker.skills_verified==True)
        if f.get('verified')=='no':query=query.filter(or_(Worker.identity_verified==False,Worker.documents_verified==False,Worker.skills_verified==False))
        if f.get('eu')=='yes':query=query.filter(Worker.eu_citizen==True)
        try:
            if f.get('experience'):query=query.filter(Worker.years_experience>=int(f['experience']))
            if f.get('quality'):int(f['quality'])
            page=max(1,int(f.get('page','1')))
        except ValueError:raise HTTPException(400,'Invalid filter')
        sourced={x.worker_id:x.source_url for x in db.query(SourceProfile).filter(SourceProfile.tenant_id==user.tenant_id).all()}
        registered={x.worker_id for x in db.query(CandidateIntake).filter(CandidateIntake.tenant_id==user.tenant_id,CandidateIntake.status=='CREATED').all()}
        rows=query.order_by(Worker.created_at.desc()).all()
        all_rows=db.query(Worker).filter(Worker.tenant_id==user.tenant_id).all();counts={k:0 for k in SEGMENTS}
        for w in all_rows:counts[segment(w)]+=1
        def source(w):return 'Professional profile' if w.id in sourced else 'Candidate registration' if w.id in registered else 'Manual / import'
        if f.get('segment'):rows=[w for w in rows if segment(w)==f['segment']]
        if f.get('source'):rows=[w for w in rows if source(w)==f['source']]
        contacts={c.worker_id:c for c in db.query(WorkerContact).join(Worker,Worker.id==WorkerContact.worker_id).filter(Worker.tenant_id==user.tenant_id).all()}
        from collector.offer_responses import OfferResponse
        interested_ids={wid for (wid,) in db.query(OfferResponse.worker_id).filter(OfferResponse.tenant_id==user.tenant_id,OfferResponse.answer=='INTERESTED').all()}
        if f.get('status')=='Interested':rows=[w for w in rows if w.id in interested_ids or (w.id in contacts and contacts[w.id].status=='Interested')]
        elif f.get('status'):rows=[w for w in rows if (contacts[w.id].status if w.id in contacts else 'New')==f['status']]
        if f.get('quality'):
            from collector.matching import completeness
            rows=[w for w in rows if completeness(w)>=int(f['quality'])]
        total=len(rows);rows=rows[(page-1)*30:page*30]
        return render(request,user,'platform_workers.html',workers=rows,filters=f,counts=counts,total=total,page=page,has_more=total>page*30,source=source,sourced=sourced,contacts=contacts,interested_ids=interested_ids,wa=whatsapp_number,statuses=STATUSES,countries=sorted({w.country for w in all_rows}),page_query=urlencode({k:v for k,v in f.items() if k!='page'}))

    @app.get('/workers/{worker_id}/request',response_class=HTMLResponse)
    def job_request(worker_id:int,request:Request,job_id:int=0,db:Session=Depends(get_db)):
        user=user_for(request,db);require_roles(user,'admin','recruiter');w=worker_for(db,worker_id,user)
        jobs=db.query(Project).filter(Project.tenant_id==user.tenant_id,Project.status!='CLOSED').order_by(Project.created_at.desc()).all()
        job=next((p for p in jobs if p.id==job_id),None)
        if not job_id and len(jobs)==1:job=jobs[0]
        meta=db.get(WorkerContact,w.id);number=whatsapp_number(w,meta)
        recent=db.query(ContactHistory).filter(ContactHistory.worker_id==w.id,ContactHistory.project_id==job.id).order_by(ContactHistory.created_at.desc()).first() if job else None
        return render(request,user,'platform_request.html',worker=w,jobs=jobs,job=job,number=number,allowed=consent_allowed(db,w.id),body=render_offer(w,job,language(request)) if job else '',recent=recent,history=None,nonce=secrets.token_urlsafe(24))

    @app.post('/workers/{worker_id}/request',response_class=HTMLResponse)
    async def prepare_request(worker_id:int,request:Request,db:Session=Depends(get_db)):
        user=user_for(request,db);require_roles(user,'admin','recruiter');form=await request.form();verify_csrf(request,form);w=worker_for(db,worker_id,user)
        try:jid=int(str(form.get('job_id','0')))
        except ValueError:raise HTTPException(400,'Select a job')
        job=db.query(Project).filter(Project.id==jid,Project.tenant_id==user.tenant_id,Project.status!='CLOSED').first()
        if not job:raise HTTPException(400,'Select an active job')
        number=whatsapp_number(w,db.get(WorkerContact,w.id))
        if not number:raise HTTPException(400,'Add a valid WhatsApp number including country code')
        if not consent_allowed(db,w.id):raise HTTPException(403,'WhatsApp job-offer permission is required')
        # Serialize each worker's draft creation across recruiters on PostgreSQL.
        if db.get_bind().dialect.name=='postgresql':db.query(Worker).filter(Worker.id==w.id).with_for_update().first()
        recent=db.query(ContactHistory).filter(ContactHistory.worker_id==w.id,ContactHistory.project_id==job.id,ContactHistory.created_at>datetime.utcnow()-timedelta(hours=24)).order_by(ContactHistory.created_at.desc()).first()
        history=recent
        if not history:
            nonce=str(form.get('nonce',''))
            if not re.fullmatch(r'[A-Za-z0-9_-]{20,100}',nonce):raise HTTPException(400,'Refresh the page and try again')
            existing=db.query(ContactHistory).filter(ContactHistory.nonce==nonce).first()
            if existing:
                if existing.tenant_id!=user.tenant_id or existing.worker_id!=w.id or existing.project_id!=job.id:raise HTTPException(409,'Refresh the page and try again')
                history=existing
            else:
                history=ContactHistory(tenant_id=user.tenant_id,worker_id=w.id,project_id=job.id,actor_id=user.id,body=render_offer(w,job,language(request)),nonce=nonce)
                db.add(history);db.commit();db.refresh(history)
        from collector.offer_responses import offer_link
        if '/offer/' not in history.body:
            history.body+='\n\n'+('Atsakykite „Domina / Nedomina“ čia:' if language(request)=='lt' else 'Reply Interested / Not interested here:')+'\n'+offer_link(request,history)
            db.commit()
        return render(request,user,'platform_request.html',worker=w,jobs=[job],job=job,number=number,allowed=True,body=history.body,history=history,recent=recent,wa_url='https://wa.me/'+number[1:]+'?text='+quote(history.body,safe=''))

    @app.post('/contacts/{contact_id}/confirm')
    async def confirm_contact(contact_id:int,request:Request,db:Session=Depends(get_db)):
        user=user_for(request,db);require_roles(user,'admin','recruiter');form=await request.form();verify_csrf(request,form)
        row=db.query(ContactHistory).filter(ContactHistory.id==contact_id,ContactHistory.tenant_id==user.tenant_id).first()
        if not row:raise HTTPException(404,'Contact not found')
        worker_for(db,row.worker_id,user)
        if row.status!='CONTACTED':
            row.status='CONTACTED';row.note='Recruiter confirmed sending the message in WhatsApp'
            meta=db.get(WorkerContact,row.worker_id)
            if not meta:meta=WorkerContact(worker_id=row.worker_id);db.add(meta)
            if meta.status not in ['Interested','Hired','In Process']:meta.status='Contacted'
            meta.last_contacted=datetime.utcnow()
            candidate=db.query(ProjectCandidate).filter(ProjectCandidate.project_id==row.project_id,ProjectCandidate.worker_id==row.worker_id).first()
            if candidate:
                if candidate.stage=='MATCHED':candidate.stage='CONTACTED'
                candidate.outreach_channel='WhatsApp'
            db.commit()
        return RedirectResponse(f'/workers/{row.worker_id}/contact-history',303)

    @app.get('/workers/{worker_id}/contact-history',response_class=HTMLResponse)
    def contact_history(worker_id:int,request:Request,db:Session=Depends(get_db)):
        user=user_for(request,db);w=worker_for(db,worker_id,user)
        history=db.query(ContactHistory).filter(ContactHistory.worker_id==w.id,ContactHistory.tenant_id==user.tenant_id).order_by(ContactHistory.created_at.desc()).limit(100).all()
        meta=db.get(WorkerContact,w.id)
        return render(request,user,'platform_history.html',worker=w,history=history,meta=meta,number=whatsapp_number(w,meta),statuses=STATUSES,jobs={p.id:p for p in db.query(Project).filter(Project.tenant_id==user.tenant_id).all()})

    @app.post('/workers/{worker_id}/contact-settings')
    async def contact_settings(worker_id:int,request:Request,db:Session=Depends(get_db)):
        user=user_for(request,db);require_roles(user,'admin','recruiter');form=await request.form();verify_csrf(request,form);w=worker_for(db,worker_id,user)
        value=str(form.get('whatsapp',''));number=international_number(value)
        if value and not number:raise HTTPException(400,'Add a valid WhatsApp number including country code')
        status=str(form.get('status','New'))
        if status not in STATUSES:raise HTTPException(400,'Invalid status')
        meta=db.get(WorkerContact,w.id)
        if not meta:meta=WorkerContact(worker_id=w.id);db.add(meta)
        meta.whatsapp=number;meta.status=status;db.commit()
        return RedirectResponse(f'/workers/{w.id}/contact-history',303)

    @app.get('/matches',response_class=HTMLResponse)
    def matches(request:Request,job_id:int=0,db:Session=Depends(get_db)):
        user=user_for(request,db)
        jobs=db.query(Project).filter(Project.tenant_id==user.tenant_id,Project.status!='CLOSED').all()
        job=next((j for j in jobs if j.id==job_id),jobs[0] if jobs else None)
        from app.services.matching import ranked_workers
        rows=ranked_workers(db,job,user.tenant_id,limit=100,include_ineligible=True) if job else []
        return render(request,user,'platform_matches.html',jobs=jobs,job=job,rows=rows)

    @app.get('/sources',response_class=HTMLResponse)
    def sources(request:Request,db:Session=Depends(get_db)):
        user=user_for(request,db)
        return render(request,user,'platform_sources.html',state=db.get(FreeSourceState,STATE_ID),runs=db.query(FreeCollectionRun).filter(FreeCollectionRun.tenant_id==user.tenant_id).order_by(FreeCollectionRun.id.desc()).limit(20).all(),lead_count=fresh_leads(db,user.tenant_id).count(),registrations=db.query(CandidateIntake).filter(CandidateIntake.tenant_id==user.tenant_id,CandidateIntake.status=='CREATED').count())

    # Replace the legacy CSV export to prevent spreadsheet formula execution.
    app.router.routes[:]=[r for r in app.router.routes if getattr(r,'path','')!='/workers/export.csv']
    @app.get('/workers/export.csv')
    def safe_workers_csv(request:Request,db:Session=Depends(get_db)):
        user=user_for(request,db);require_roles(user,'admin','recruiter')
        import csv,io
        from fastapi.responses import Response
        fields=['full_name','phone','email','country','profession','skills','certificates','languages','preferred_countries','preferred_rotation','expected_salary_net_hour','availability_status','available_from','ready_to_deploy']
        output=io.StringIO(newline='');writer=csv.writer(output)
        writer.writerow(['rotation' if key=='preferred_rotation' else key for key in fields])
        def safe(value):
            text=str(value) if value is not None else ''
            return "'"+text if text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n')) else text
        for worker in db.query(Worker).filter(Worker.tenant_id==user.tenant_id).order_by(Worker.id):
            writer.writerow([safe(getattr(worker,key)) for key in fields])
        return Response(output.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="euroteams-workers.csv"','Cache-Control':'no-store, private','X-Content-Type-Options':'nosniff'})
    route=app.router.routes.pop();app.router.routes.insert(0,route)

    @app.post('/settings/export')
    async def export_recruitment_data(request:Request,db:Session=Depends(get_db)):
        user=user_for(request,db);require_roles(user,'admin')
        verify_csrf(request,await request.form())
        from fastapi.encoders import jsonable_encoder
        from fastapi.responses import JSONResponse
        from sqlalchemy import inspect
        from app.models import Crew
        from collector.coresignal import SourceRun
        from collector.offer_responses import OfferResponse
        workers=db.query(Worker).filter(Worker.tenant_id==user.tenant_id).all()
        worker_ids=[w.id for w in workers]
        projects=db.query(Project).filter(Project.tenant_id==user.tenant_id).all()
        project_ids=[j.id for j in projects]
        # Explicit business-data allowlist. Authentication tables and bearer tokens
        # are never exported. Uploaded document files require separate storage.
        groups={'workers':workers,'jobs':projects}
        for model in [Crew,Consent,CandidateIntake,SourceProfile,SourceRun,FreeLead,FreeCollectionRun,ContactHistory,OfferResponse]:
            query=db.query(model).filter(model.tenant_id==user.tenant_id)
            if hasattr(model,'worker_id'):query=query.filter(model.worker_id.in_(worker_ids))
            groups[model.__tablename__]=query.all()
        groups['project_candidates']=db.query(ProjectCandidate).filter(ProjectCandidate.project_id.in_(project_ids),ProjectCandidate.worker_id.in_(worker_ids)).all()
        groups['worker_contacts']=db.query(WorkerContact).filter(WorkerContact.worker_id.in_(worker_ids)).all()
        def serialise(row):
            excluded={'self_service_token','nonce','request_key','run_key','password_hash','file_path','stored_path'}
            return {c.key:getattr(row,c.key) for c in inspect(type(row)).columns if c.key not in excluded and 'token' not in c.key and 'secret' not in c.key}
        data={key:[serialise(row) for row in rows] for key,rows in groups.items()}
        payload={'format':'euroteams-recruitment-export-v1','exported_at':datetime.now(timezone.utc).isoformat(),'tenant_id':user.tenant_id,'counts':{key:len(rows) for key,rows in data.items()},'limitations':['Business data only; account credentials, access links and uploaded files are excluded.','Automatic restore is not supported by this export.'],'data':data}
        return JSONResponse(jsonable_encoder(payload),headers={'Content-Disposition':'attachment; filename="euroteams-recruitment-data.json"','Cache-Control':'no-store, private','X-Content-Type-Options':'nosniff'})

    @app.get('/settings',response_class=HTMLResponse)
    def settings(request:Request,db:Session=Depends(get_db)):
        user=user_for(request,db)
        return render(request,user,'platform_settings.html')

    @app.get('/projects/{project_id}/edit',response_class=HTMLResponse)
    def job_edit(project_id:int,request:Request,db:Session=Depends(get_db)):
        user=user_for(request,db);require_roles(user,'admin','recruiter')
        job=db.query(Project).filter(Project.id==project_id,Project.tenant_id==user.tenant_id).first()
        if not job:raise HTTPException(404,'Job not found')
        return render(request,user,'platform_job_edit.html',job=job)

    @app.post('/projects/{project_id}/edit')
    async def job_update(project_id:int,request:Request,db:Session=Depends(get_db)):
        user=user_for(request,db);require_roles(user,'admin','recruiter');form=await request.form();verify_csrf(request,form)
        job=db.query(Project).filter(Project.id==project_id,Project.tenant_id==user.tenant_id).first()
        if not job:raise HTTPException(404,'Job not found')
        try:
            for key in ['name','client','country','city','profession','rotation','required_language','required_certificates','requirements','accommodation','travel']:
                value=str(form.get(key,'')).strip()
                if len(value)>4000:raise ValueError()
                setattr(job,key,value)
            if not job.name or not job.country or not job.profession:raise ValueError()
            job.start_date=date.fromisoformat(str(form.get('start_date','')))
            job.workers_needed=int(str(form.get('workers_needed','1')));job.weekly_hours=int(str(form.get('weekly_hours','50')));job.duration_weeks=int(str(form.get('duration_weeks','8')));job.salary_net_hour=float(str(form.get('salary_net_hour','0')))
            if not (1<=job.workers_needed<=10000 and 1<=job.weekly_hours<=84 and 1<=job.duration_weeks<=520 and 0<=job.salary_net_hour<=1000):raise ValueError()
            status=str(form.get('status','DRAFT'))
            if status not in ['DRAFT','ACTIVE','RECRUITING','CLOSED']:raise ValueError()
            job.status=status
        except (ValueError,TypeError):db.rollback();raise HTTPException(400,'Check job fields')
        db.flush()
        from app.services.matching import ranked_workers
        for w,result in ranked_workers(db,job,user.tenant_id,limit=100,include_ineligible=True):
            candidate=db.query(ProjectCandidate).filter(ProjectCandidate.project_id==job.id,ProjectCandidate.worker_id==w.id).first()
            if not candidate:candidate=ProjectCandidate(project_id=job.id,worker_id=w.id);db.add(candidate)
            candidate.match_score=result['match_score'];candidate.fit_score=result.get('fit_score',0)
            candidate.interest_probability=result.get('interest_probability',0);candidate.arrival_probability=result.get('arrival_probability',0)
            candidate.data_confidence=result.get('data_confidence',0);candidate.eligibility='PASS' if result['eligible'] else 'REVIEW'
        db.commit()
        return RedirectResponse(f'/projects/{job.id}',303)

    @app.get('/qa/responsive',response_class=HTMLResponse)
    def responsive_qa(request:Request,width:int=390,surface:str='workers',db:Session=Depends(get_db)):
        user=user_for(request,db);require_roles(user,'admin')
        if width not in [360,390,768,1280] or surface not in ['workers','dashboard','jobs','matches','sources','settings']:raise HTTPException(400,'Invalid preview')
        target={'workers':'/workers','dashboard':'/','jobs':'/projects','matches':'/matches','sources':'/sources','settings':'/settings'}[surface]
        return HTMLResponse('<!doctype html><html><head><title>Euroteams responsive QA</title><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0;background:#dce5eb"><p style="font:16px system-ui;padding:10px">Euroteams QA · '+str(width)+'px</p><iframe title="Responsive workspace" src="'+target+'" width="'+str(width)+'" height="1100" style="display:block;border:0;background:white;margin:0 auto;max-width:100%"></iframe></body></html>')

    @app.get('/projects/{project_id}',response_class=HTMLResponse)
    def job_detail(project_id:int,request:Request,db:Session=Depends(get_db)):
        user=user_for(request,db)
        job=db.query(Project).filter(Project.id==project_id,Project.tenant_id==user.tenant_id).first()
        if not job:raise HTTPException(404,'Job not found')
        rows=evidence_ranked(db,job,user.tenant_id,limit=100,include_ineligible=True)
        return render(request,user,'platform_job_detail.html',job=job,rows=rows)

    @app.get('/workers/{worker_id}',response_class=HTMLResponse)
    def worker_detail(worker_id:int,request:Request,db:Session=Depends(get_db)):
        from app.models import WorkerDocument,AvailabilityEvent
        user=user_for(request,db);worker=worker_for(db,worker_id,user)
        evidence=db.query(SourceProfile).filter(SourceProfile.worker_id==worker.id,SourceProfile.tenant_id==user.tenant_id).first()
        return render(request,user,'worker_detail.html',worker=worker,source_url=evidence.source_url if evidence else '',confidence='—' if not worker.last_availability_confirmed else 'Confirmed date: '+str(worker.last_availability_confirmed),documents=db.query(WorkerDocument).filter(WorkerDocument.worker_id==worker.id).all(),messages=db.query(Message).filter(Message.worker_id==worker.id).order_by(Message.created_at.desc()).limit(20).all(),events=db.query(AvailabilityEvent).filter(AvailabilityEvent.worker_id==worker.id).order_by(AvailabilityEvent.created_at.desc()).limit(20).all(),consents=db.query(Consent).filter(Consent.worker_id==worker.id).order_by(Consent.created_at.desc()).all())

    @app.post('/collector/free-source/run')
    async def manual_collection(request:Request,db:Session=Depends(get_db)):
        user=user_for(request,db);require_roles(user,'admin')
        form=await request.form();verify_csrf(request,form)
        from collector.free_sources import refresh
        refresh(db,user.tenant_id,force=True)
        return RedirectResponse('/sources',303)
