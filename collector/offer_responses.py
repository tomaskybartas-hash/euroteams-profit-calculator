"""Private job-offer links: viewing never records interest or confirms a send."""
from datetime import datetime
from pathlib import Path
import hashlib,secrets
from fastapi import Request,Depends,HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import BadData
from sqlalchemy import Integer,ForeignKey,String,Text,DateTime
from sqlalchemy.orm import Mapped,mapped_column,Session
from app.db import Base,get_db
from app.models import Worker,Project,ProjectCandidate
from collector.intake import signer

class OfferResponse(Base):
    __tablename__='platform_offer_responses'
    contact_id:Mapped[int]=mapped_column(ForeignKey('platform_contact_history.id'),primary_key=True)
    tenant_id:Mapped[int]=mapped_column(Integer,index=True)
    worker_id:Mapped[int]=mapped_column(ForeignKey('workers.id'),index=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    answer:Mapped[str]=mapped_column(String(30))
    note:Mapped[str]=mapped_column(Text,default='')
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)


def offer_link(request,history):
    token=signer().dumps({'purpose':'offer-view','contact':history.id,'key':hashlib.sha256(history.nonce.encode()).hexdigest()})
    return str(request.base_url).rstrip('/')+'/offer/'+token


def install(app,current_user,require_roles):
    from collector.platform import ContactHistory,csrf
    from collector.localization import language,translate
    views=Jinja2Templates(directory=[str(Path(__file__).parent/'templates'),str(Path(__file__).parents[1]/'app'/'templates')])
    def record(token,db):
        try:
            data=signer().loads(token,max_age=30*86400)
            if data.get('purpose')!='offer-view':raise ValueError()
            row=db.get(ContactHistory,int(data['contact']))
            if not row or not secrets.compare_digest(data['key'],hashlib.sha256(row.nonce.encode()).hexdigest()):raise ValueError()
            job=db.get(Project,row.project_id)
            worker=db.get(Worker,row.worker_id)
            if not job or not worker or job.tenant_id!=row.tenant_id or worker.tenant_id!=row.tenant_id:raise ValueError()
            return row,job
        except (BadData,ValueError,KeyError,TypeError):raise HTTPException(404,'Offer link is invalid or expired')
    def context(request,**values):
        lang=language(request)
        return dict(request=request,lang=lang,t=lambda s:translate(s,lang),**values)

    @app.get('/offer/{token}')
    def show_offer(token:str,request:Request,db:Session=Depends(get_db)):
        row,job=record(token,db)
        form_token=signer().dumps({'purpose':'offer-form','contact':row.id,'nonce':secrets.token_urlsafe(24)})
        response=views.TemplateResponse(request,'offer_response.html',context(request,job=job,token=token,form_token=form_token,reply=db.get(OfferResponse,row.id)))
        response.set_cookie('offer_form',form_token,httponly=True,secure=request.url.scheme=='https',samesite='strict',path='/offer/',max_age=3600)
        response.headers.update({'Cache-Control':'no-store, private','Referrer-Policy':'no-referrer','X-Robots-Tag':'noindex, nofollow','X-Frame-Options':'DENY'})
        return response

    @app.post('/offer/{token}')
    async def reply_offer(token:str,request:Request,db:Session=Depends(get_db)):
        row,job=record(token,db)
        form=await request.form()
        value=str(form.get('form_token',''))
        try:
            if not value or not secrets.compare_digest(value,request.cookies.get('offer_form','')):raise ValueError()
            verified=signer().loads(value,max_age=3600)
            if verified.get('purpose')!='offer-form' or verified.get('contact')!=row.id:raise ValueError()
        except (BadData,ValueError):raise HTTPException(403,'Reload the offer and try again')
        if job.status=='CLOSED':raise HTTPException(409,'This job is closed')
        answer=str(form.get('answer',''));note=str(form.get('note','')).strip()
        if answer not in ['INTERESTED','NOT_INTERESTED'] or len(note)>1000:raise HTTPException(400,'Check your answer')
        # A shared link does not establish identity. Only a reviewer makes hiring decisions.
        db.query(ContactHistory).filter(ContactHistory.id==row.id).with_for_update().first()
        reply=db.get(OfferResponse,row.id)
        if not reply:
            reply=OfferResponse(contact_id=row.id,tenant_id=row.tenant_id,worker_id=row.worker_id,project_id=row.project_id,answer=answer,note=note);db.add(reply)
        else:reply.answer=answer;reply.note=note
        candidate=db.query(ProjectCandidate).filter(ProjectCandidate.worker_id==row.worker_id,ProjectCandidate.project_id==row.project_id).first()
        if candidate and candidate.stage in ['MATCHED','CONTACTED','INTERESTED','NOT_INTERESTED']:candidate.stage=answer
        db.commit()
        return RedirectResponse('/offer/'+token,303)

    @app.get('/responses')
    def response_inbox(request:Request,db:Session=Depends(get_db)):
        user=current_user(request,db)
        if not user:return RedirectResponse('/login',303)
        require_roles(user,'admin','recruiter')
        rows=db.query(OfferResponse,Worker,Project).join(Worker,Worker.id==OfferResponse.worker_id).join(Project,Project.id==OfferResponse.project_id).filter(OfferResponse.tenant_id==user.tenant_id,Worker.tenant_id==user.tenant_id,Project.tenant_id==user.tenant_id).order_by(OfferResponse.updated_at.desc()).limit(200).all()
        return views.TemplateResponse(request,'platform_responses.html',context(request,user=user,rows=rows,csrf_token=csrf(request),asset_version=__import__('collector.platform',fromlist=['asset_version']).asset_version()))
