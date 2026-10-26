"""Authenticated recruiter editing and private candidate-owned profile completion."""
from datetime import date
from pathlib import Path
import hashlib,hmac,re,secrets,json
from types import SimpleNamespace
from fastapi import Request,Depends,HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func,or_,text
from app.db import get_db
from app.models import Worker,AuditLog,Consent,Project,ProjectCandidate
from collector.intake import signer
from collector.profile_quality import has_name,missing_fields,profile_ready

FIELDS=['full_name','phone','email','country','profession','skills','languages','certificates','preferred_countries','preferred_rotation','years_experience','availability_status','available_from']


def install(app,current_user,require_roles):
    from collector.platform import csrf,verify_csrf,international_number,asset_version
    from collector.localization import translate,language
    views=Jinja2Templates(directory=str(Path(__file__).parent/'templates'))
    def admin(request,db,wid):
        user=current_user(request,db)
        if not user:raise HTTPException(401,'Login required')
        require_roles(user,'admin','recruiter')
        w=db.query(Worker).filter_by(id=wid,tenant_id=user.tenant_id).first()
        if not w:raise HTTPException(404,'Worker not found')
        return user,w
    def private(db,token):
        if len(token)<32:raise HTTPException(404,'Profile not found')
        w=db.query(Worker).filter_by(self_service_token=token).first()
        if not w:raise HTTPException(404,'Profile not found')
        if w.identity_verified or w.documents_verified or w.skills_verified:raise HTTPException(403,'Contact your recruiter to change a verified profile')
        return w
    def proposal(db,w,application_id):
        if not application_id:return None
        row=db.query(AuditLog).filter_by(id=application_id,tenant_id=w.tenant_id,entity_type='worker',entity_id=str(w.id),action='APPLICATION_REVIEW_REQUESTED').first()
        reviewed=db.query(AuditLog).filter_by(tenant_id=w.tenant_id,action='APPLICATION_REVIEWED',entity_type='application',entity_id=str(application_id)).first()
        if not row or reviewed:raise HTTPException(404,'Application not found or already reviewed')
        return row
    def show(request,w,user=None,token=None,error='',status=200,application=None):
        if application:
            supplied=json.loads(application.details)['values']
            preview={key:getattr(w,key) for key in FIELDS}
            preview.update({key:supplied[key] for key in FIELDS if key in supplied})
            preview.update(id=w.id,last_availability_confirmed=w.last_availability_confirmed)
            w=SimpleNamespace(**preview)
        is_private=token is not None
        signed=signer().dumps({'wid':w.id,'key':hashlib.sha256(token.encode()).hexdigest(),'nonce':secrets.token_urlsafe(20)}) if is_private else csrf(request)
        response=views.TemplateResponse(request,'profile_completion.html',dict(request=request,worker=w,user=user,private=is_private,form_csrf=signed,error=error,missing=missing_fields(w),has_name=has_name(w.full_name),lang=language(request),t=lambda s:translate(s,language(request)),asset_version=asset_version(),application_id=application.id if application else None),status_code=status)
        response.headers['Cache-Control']='no-store, private';response.headers['Referrer-Policy']='no-referrer';response.headers['X-Robots-Tag']='noindex, nofollow'
        if is_private:response.set_cookie('profile_completion',signed,secure=request.url.scheme=='https',httponly=True,samesite='lax',max_age=3600,path=request.url.path)
        return response
    def save(db,w,form,actor,is_private,application=None):
        values={k:str(form.get(k,'')).strip() for k in FIELDS}
        if any(len(v)>(getattr(Worker.__table__.columns[k].type,'length',None) or 2000) for k,v in values.items()):raise ValueError('Profile value is too long')
        if not has_name(values['full_name']):raise ValueError('Enter your full name')
        if not values['country'] or not values['profession']:raise ValueError('Enter your country and profession')
        values['email']=values['email'].lower()
        if values['email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',values['email']):raise ValueError('Enter a valid email address')
        if values['phone']:
            values['phone']=international_number(values['phone'])
            if not values['phone']:raise ValueError('Enter a valid phone number including country code')
        if not values['email'] and not values['phone']:raise ValueError('Enter an email address or phone number')
        values['years_experience']=int(values['years_experience'] or '0')
        if not 0<=values['years_experience']<=70:raise ValueError('Check experience')
        allowed=['AVAILABLE NOW','AVAILABLE FROM DATE','OPEN TO OFFERS','CURRENTLY WORKING','NOT LOOKING','UNKNOWN']
        if values['availability_status'] not in allowed:raise ValueError('Select your availability')
        values['available_from']=date.fromisoformat(values['available_from']) if values['available_from'] else None
        if values['availability_status']=='AVAILABLE FROM DATE' and not values['available_from']:raise ValueError('Select the date you can start')
        if form.get('confirmed')!='yes':raise ValueError('Confirm that these details were supplied by the candidate')
        stored=Worker.phone
        for char in (' ','-','(',')','.'):stored=func.replace(stored,char,'')
        checks=[]
        if values['phone']:checks.append(stored==values['phone'])
        if values['email']:checks.append(func.lower(Worker.email)==values['email'])
        if db.get_bind().dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock(64132979)'))
        if application and db.query(AuditLog).filter_by(tenant_id=w.tenant_id,action='APPLICATION_REVIEWED',entity_type='application',entity_id=str(application.id)).first():raise ValueError('Application already reviewed')
        if db.query(Worker).filter(Worker.tenant_id==w.tenant_id,Worker.id!=w.id,or_(*checks)).first():raise ValueError('Contact details already belong to another profile; contact the recruiter')
        if not is_private and (w.identity_verified or w.skills_verified or w.documents_verified):
            for k in ['full_name','profession','skills','certificates','years_experience']:
                if values[k]!=getattr(w,k):raise ValueError('A verified profile must be updated through the existing verification workflow')
        for key,value in values.items():setattr(w,key,value)
        w.last_availability_confirmed=date.today() if values['availability_status']!='UNKNOWN' else None
        # Completion never grants identity/document verification or readiness to deploy.
        w.ready_to_deploy=False
        if is_private:
            for channel,field in [('Email','email_offers'),('WhatsApp','whatsapp_offers')]:
                if form.get(field)=='yes':
                    if channel=='Email' and not w.email:raise ValueError('Enter a valid email address')
                    if channel=='WhatsApp' and not w.phone:raise ValueError('Enter a valid phone number including country code')
                    db.add(Consent(tenant_id=w.tenant_id,worker_id=w.id,channel=channel,purpose='job_offers',granted=True,source='worker_profile_completion',text_version='profile-completion-v1'))
        db.add(AuditLog(tenant_id=w.tenant_id,actor=actor,action='PROFILE_COMPLETED',entity_type='worker',entity_id=str(w.id),details='Candidate-supplied details; identity and documents not verified by this form'))
        if profile_ready(w):
            if not db.query(AuditLog).filter_by(tenant_id=w.tenant_id,entity_type='worker',entity_id=str(w.id),action='PROFILE_QUALIFIED').first():
                db.add(AuditLog(tenant_id=w.tenant_id,actor=actor,action='PROFILE_QUALIFIED',entity_type='worker',entity_id=str(w.id),details='First complete profile; identity and documents still require separate verification'))
            from collector.matching import sync_worker_matches
            sync_worker_matches(db,w)
        if application:
            db.add(AuditLog(tenant_id=w.tenant_id,actor=actor,action='APPLICATION_REVIEWED',entity_type='application',entity_id=str(application.id),details='Candidate details reviewed and applied to worker '+str(w.id)+'; no messaging permission or verification inferred'))
        db.commit()
    @app.get('/applications')
    def application_queue(request:Request,db=Depends(get_db)):
        user=current_user(request,db)
        if not user:return RedirectResponse('/login',303)
        require_roles(user,'admin','recruiter')
        reviewed={x.entity_id for x in db.query(AuditLog).filter_by(tenant_id=user.tenant_id,action='APPLICATION_REVIEWED',entity_type='application').all()}
        rows=[]
        for row in db.query(AuditLog).filter_by(tenant_id=user.tenant_id,action='APPLICATION_REVIEW_REQUESTED',entity_type='worker').filter(~AuditLog.id.in_([int(value) for value in reviewed if value.isdigit()])).order_by(AuditLog.id.desc()).limit(200).all():
            if str(row.id) in reviewed:continue
            w=db.query(Worker).filter_by(id=int(row.entity_id),tenant_id=user.tenant_id).first()
            if not w:continue
            try:values=json.loads(row.details)['values']
            except (ValueError,KeyError,TypeError):continue
            rows.append(dict(id=row.id,worker_id=w.id,existing_name=w.full_name,submitted_name=values.get('full_name',''),profession=values.get('profession',''),created_at=row.created_at))
        response=views.TemplateResponse(request,'application_queue.html',dict(request=request,user=user,rows=rows,t=lambda s:translate(s,language(request)),lang=language(request),asset_version=asset_version()))
        response.headers['Cache-Control']='no-store, private'
        response.headers['Referrer-Policy']='no-referrer'
        return response
    @app.get('/workers/{worker_id}/profile')
    def recruiter_form(worker_id:int,request:Request,db=Depends(get_db)):
        user,w=admin(request,db,worker_id)
        try:application_id=int(request.query_params.get('application','0'))
        except ValueError:raise HTTPException(400,'Invalid application')
        return show(request,w,user,application=proposal(db,w,application_id))
    @app.post('/workers/{worker_id}/profile')
    async def recruiter_save(worker_id:int,request:Request,db=Depends(get_db)):
        user,w=admin(request,db,worker_id);form=await request.form();verify_csrf(request,form)
        try:application_id=int(form.get('application_id','0'))
        except ValueError:raise HTTPException(400,'Invalid application')
        application=proposal(db,w,application_id)
        try:save(db,w,form,'user:'+str(user.id),False,application)
        except (ValueError,TypeError) as exc:
            db.rollback();return show(request,w,user,error=str(exc),status=422,application=application)
        return RedirectResponse('/workers/'+str(w.id),303)
    @app.get('/worker/{token}/profile')
    def candidate_form(token:str,request:Request,db=Depends(get_db)):
        return show(request,private(db,token),token=token)
    @app.post('/worker/{token}/profile')
    async def candidate_save(token:str,request:Request,db=Depends(get_db)):
        w=private(db,token)
        if not request.headers.get('content-type','').startswith('application/x-www-form-urlencoded'):raise HTTPException(415,'Use the profile form')
        body=bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body)>32000:raise HTTPException(413,'Application is too large')
        from urllib.parse import parse_qs
        try:form={k:v[-1] for k,v in parse_qs(body.decode('utf-8'),max_num_fields=30).items()}
        except (ValueError,UnicodeError):raise HTTPException(400,'Invalid form')
        signed=str(form.get('csrf',''))
        try:
            if not signed or not hmac.compare_digest(signed,request.cookies.get('profile_completion','')):raise ValueError()
            payload=signer().loads(signed,max_age=3600)
            if payload['wid']!=w.id or payload['key']!=hashlib.sha256(token.encode()).hexdigest():raise ValueError()
        except Exception:raise HTTPException(403,'Refresh the page and try again')
        origin=request.headers.get('origin')
        if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):raise HTTPException(403,'Not permitted')
        try:save(db,w,form,'candidate-profile',True)
        except (ValueError,TypeError) as exc:
            db.rollback();return show(request,w,token=token,error=str(exc),status=422)
        return show(request,w,token=token,error='Profile saved. Your recruiter can review the supplied information.')
