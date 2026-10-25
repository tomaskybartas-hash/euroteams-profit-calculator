"""Truthful daily worker metrics: advertisements never count toward the target."""
from datetime import datetime,date,timedelta,timezone,time
from zoneinfo import ZoneInfo
import json
from sqlalchemy import Integer,String,Text,DateTime,ForeignKey
from sqlalchemy.orm import Mapped,mapped_column
from app.db import Base
from app.models import Worker

class DailyAcquisitionReport(Base):
    __tablename__='collector_daily_reports'
    tenant_id:Mapped[int]=mapped_column(ForeignKey('tenants.id'),primary_key=True)
    day:Mapped[str]=mapped_column(String(10),primary_key=True)
    payload:Mapped[str]=mapped_column(Text)
    recorded_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)


def daily_metrics(db,tenant_id,day=None):
    from collector.platform import whatsapp_number,WorkerContact
    from collector.coresignal import SourceProfile
    from collector.intake import CandidateIntake
    zone=ZoneInfo('Europe/Vilnius');today=datetime.now(zone).date();day=day or today
    start=datetime.combine(day,time.min,tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None)
    end=datetime.combine(day+timedelta(days=1),time.min,tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None)
    rows=db.query(Worker).filter(Worker.tenant_id==tenant_id,Worker.created_at>=start,Worker.created_at<end).all()
    profiles={p.worker_id:p.source for p in db.query(SourceProfile).filter(SourceProfile.tenant_id==tenant_id).all()}
    registrations={p.worker_id for p in db.query(CandidateIntake).filter(CandidateIntake.tenant_id==tenant_id,CandidateIntake.status=='CREATED').all()}
    by_source={}
    for worker in rows:
        name=profiles.get(worker.id,'Candidate registration' if worker.id in registrations else 'Manual / import')
        by_source[name]=by_source.get(name,0)+1
    elapsed=max(1,(min(datetime.utcnow(),end)-start).total_seconds())
    return {'day':day.isoformat(),'timezone':'Europe/Vilnius','target':300,'unique_added':len(rows),'new_whatsapp':sum(bool(whatsapp_number(w,db.get(WorkerContact,w.id))) for w in rows),'new_email':sum(bool(w.email) for w in rows),'by_source':by_source,'unique_per_elapsed_hour':round(len(rows)/(elapsed/3600),2),'target_reason':'Target reached' if len(rows)>=300 else 'Insufficient source coverage','ads_included':False,'invalid':None,'errors':None,'limitations':'Invalid and error counts are not aggregated across all acquisition channels.'}


def save_previous_day(db,tenant_id):
    day=datetime.now(ZoneInfo('Europe/Vilnius')).date()-timedelta(days=1)
    key=(tenant_id,day.isoformat())
    if not db.get(DailyAcquisitionReport,key):
        payload=daily_metrics(db,tenant_id,day)
        db.add(DailyAcquisitionReport(tenant_id=tenant_id,day=day.isoformat(),payload=json.dumps(payload,ensure_ascii=False)))
        db.commit()


def install(app,current_user,require_roles):
    from fastapi import Request,Depends
    from fastapi.responses import RedirectResponse
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session
    from pathlib import Path
    from app.db import get_db
    from collector.localization import translate,language
    from collector.platform import asset_version,csrf
    views=Jinja2Templates(directory=[str(Path(__file__).parent/'templates'),str(Path(__file__).parents[1]/'app'/'templates')])
    @app.get('/acquisition-reports')
    def reports(request:Request,db:Session=Depends(get_db)):
        user=current_user(request,db)
        if not user:return RedirectResponse('/login',303)
        require_roles(user,'admin','recruiter')
        save_previous_day(db,user.tenant_id)
        rows=db.query(DailyAcquisitionReport).filter(DailyAcquisitionReport.tenant_id==user.tenant_id).order_by(DailyAcquisitionReport.day.desc()).limit(90).all()
        return views.TemplateResponse(request,'platform_reports.html',dict(request=request,user=user,lang=language(request),t=lambda s:translate(s,language(request)),asset_version=asset_version(),csrf_token=csrf(request),reports=[json.loads(row.payload) for row in rows]))
