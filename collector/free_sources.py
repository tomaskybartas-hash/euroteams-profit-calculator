"""Free, low-frequency RSS discovery. Leads are jobseeker ads, not verified workers."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse
import html
import re
import xml.etree.ElementTree as ET
import httpx
from sqlalchemy import Integer, String, DateTime, ForeignKey, Float, text, or_
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base, SessionLocal

FEED='https://www.ss.com/ru/work/i-search-for-work/welder/rss/'
SOURCE='ss-jobseeker-welder-rss'
FEEDS={'welder':'welder','mason':'mason','mechanics':'mechanic','electrician':'electrician'}
STATE_ID=2

class FreeLead(Base):
    __tablename__='collector_free_leads'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id'),index=True)
    source: Mapped[str]=mapped_column(String(100),default=SOURCE)
    source_url: Mapped[str]=mapped_column(String(500),unique=True)
    title: Mapped[str]=mapped_column(String(180))
    profession: Mapped[str]=mapped_column(String(100),default='welder')
    country: Mapped[str]=mapped_column(String(10),default='LV')
    intent: Mapped[str]=mapped_column(String(60),default='PUBLIC_WORK_SEEKING_AD')
    published_at: Mapped[datetime | None]=mapped_column(DateTime,nullable=True)
    discovered_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)
    last_seen_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class FreeSourceState(Base):
    __tablename__='collector_free_source_state'
    id: Mapped[int]=mapped_column(Integer,primary_key=True,default=1)
    status: Mapped[str]=mapped_column(String(40),default='NOT_RUN')
    checked_at: Mapped[datetime | None]=mapped_column(DateTime,nullable=True)
    found: Mapped[int]=mapped_column(Integer,default=0)
    added: Mapped[int]=mapped_column(Integer,default=0)
    duplicates: Mapped[int]=mapped_column(Integer,default=0)
    error: Mapped[str]=mapped_column(String(80),default='')


def clean(value):
    value=html.unescape(re.sub(r'<[^>]*>',' ',value or ''))
    value=re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}','[contact on source]',value)
    value=re.sub(r'\+?\d[\d ()-]{6,}\d','[contact on source]',value)
    return re.sub(r'\s+',' ',value).strip()



def visible_rss_contacts(value):
    """Read only contacts voluntarily written in the public RSS text, never reveal calls."""
    from collector.public_discovery import Document
    visible=Document(value or '').text
    phones=set()
    patterns=[r'(?<!\w)\+371[ ()-]*2(?:[ ()-]*[0-9]){7}(?![0-9])',
              r'(?:tel(?:efons?|ephone)?|phone|whatsapp|t[aā]lrunis|тел(?:ефон)?)\s*[.:=-]?\s*((?:\+371[ ()-]*)?2(?:[ ()-]*[0-9]){7})(?![0-9])']
    for pattern in patterns:
        for value in re.findall(pattern,visible,re.I):
            digits=re.sub(r'\D','',value)
            if len(digits)==8:digits='371'+digits
            if len(digits)==11 and digits.startswith('3712'):phones.add('+'+digits)
    emails={x.lower() for x in re.findall(r'(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])',visible)}
    if len(phones)>1 or len(emails)>1:return {}
    return {'phone':next(iter(phones),''),'email':next(iter(emails),'')} if phones or emails else {}


def store_rss_contacts(db,tenant_id,entry,contacts):
    """A public contact is an unverified prospect, never a marketing opt-in."""
    from app.models import Worker,AuditLog
    from collector.coresignal import SourceProfile
    from sqlalchemy import func
    import hashlib,secrets
    if not contacts or not entry.get('published_at'):return False
    url=entry['source_url'];source='ss-public-rss'
    sid=hashlib.sha256(url.encode()).hexdigest()[:20]
    if db.query(SourceProfile).filter_by(tenant_id=tenant_id,source_url=url).first():return False
    checks=[]
    phone=contacts.get('phone','');email=contacts.get('email','')
    if phone:
        normalized=Worker.phone
        for char in (' ','-','(',')','.'):normalized=func.replace(normalized,char,'')
        checks.append(normalized==phone)
    if email:checks.append(func.lower(Worker.email)==email)
    if not checks or db.query(Worker).filter(Worker.tenant_id==tenant_id,or_(*checks)).first():return False
    worker=Worker(tenant_id=tenant_id,full_name='Public jobseeker LV · '+sid[:8],country='LV',
        profession=entry['profession'],phone=phone,email=email,availability_status='UNKNOWN',eu_citizen=False,
        ready_to_deploy=False,identity_verified=False,documents_verified=False,skills_verified=False,
        years_experience=0,preferred_channel='Phone' if phone else 'Email',self_service_token=secrets.token_urlsafe(32),
        work_permit_notes='Public RSS work-seeking advertisement. Name, current availability and right to work unverified; no messaging opt-in. Source: '+url)
    db.add(worker);db.flush()
    db.add(SourceProfile(tenant_id=tenant_id,worker_id=worker.id,source=source,source_id=sid,source_url=url,
        reported_title='Public RSS jobseeker advertisement · '+entry['profession'],provider_updated_at=entry['published_at'].isoformat(),
        verification_status='UNCONFIRMED',permission_basis='Minimal public recruitment contact written directly in an official jobseeker RSS feed; source attribution retained; no messaging consent inferred'))
    db.add(AuditLog(tenant_id=tenant_id,actor='public-rss-discovery',action='PUBLIC_JOBSEEKER_COLLECTED',entity_type='worker',entity_id=str(worker.id),details='source='+source+'; no messaging consent inferred'))
    return True


def parse_feed(raw,category="welder"):
    if len(raw)>1_000_000 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('unsupported_feed')
    root=ET.fromstring(raw)
    if root.tag.lower()!='rss' or root.find('channel') is None:raise ValueError('unsupported_feed')
    results=[]
    seen=set()
    for item in root.findall('./channel/item')[:100]:
        title=clean(item.findtext('title'))
        content=title+' '+clean(item.findtext('description'))
        # The RSS category contains service advertisements too; do not count those as jobseekers.
        if not re.search(r'ищ[ую](?:т|м)?\s+(?:работ|подработ)|mekl[eē]j(?:u|am)\s+darbu|looking for (?:a )?(?:job|work)|seeking (?:a )?(?:job|work)',content,re.I):
            continue
        url=(item.findtext('link') or '').strip()
        parsed=urlparse(url)
        if parsed.scheme!='https' or parsed.hostname not in {'www.ss.com','ss.com','m.ss.com'} or parsed.query or parsed.fragment:
            continue
        if category not in FEEDS or not re.fullmatch(r'/msg/ru/work/i-search-for-work/'+re.escape(category)+r'/[a-z]+\.html',parsed.path):
            continue
        if url in seen:continue
        seen.add(url)
        posted=None
        try:
            posted=parsedate_to_datetime(item.findtext('pubDate') or '').astimezone(timezone.utc).replace(tzinfo=None)
        except (ValueError,TypeError,OverflowError):pass
        if posted and (posted<datetime.utcnow()-timedelta(days=30) or posted>datetime.utcnow()+timedelta(days=1)):
            continue
        results.append({'source_url':url,'title':title[:180],'published_at':posted,'profession':FEEDS[category],'source':'ss-jobseeker-'+category+'-rss','public_contacts':visible_rss_contacts(item.findtext('description'))})
    return results


class FreeCollectionRun(Base):
    __tablename__='collector_free_runs'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id'),index=True)
    status: Mapped[str]=mapped_column(String(40),default='RUNNING',index=True)
    started_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)
    finished_at: Mapped[datetime | None]=mapped_column(DateTime,nullable=True)
    seconds: Mapped[float]=mapped_column(Float,default=0)
    successful_sources: Mapped[int]=mapped_column(Integer,default=0)
    found: Mapped[int]=mapped_column(Integer,default=0)
    added: Mapped[int]=mapped_column(Integer,default=0)
    duplicates: Mapped[int]=mapped_column(Integer,default=0)
    error: Mapped[str]=mapped_column(String(200),default='')


def fresh_leads(db,tenant_id,now=None):
    cutoff=(now or datetime.utcnow())-timedelta(days=30)
    return db.query(FreeLead).filter(FreeLead.tenant_id==tenant_id,
        FreeLead.last_seen_at>=cutoff,
        or_(FreeLead.published_at.is_(None),FreeLead.published_at>=cutoff))


def refresh(db, tenant_id=1, client=None, force=False):
    if db.get_bind().dialect.name=='postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(64132972)'))
    state=db.get(FreeSourceState,STATE_ID)
    if state is None:
        state=FreeSourceState(id=STATE_ID);db.add(state);db.flush()
    now=datetime.utcnow()
    # An instance can stop mid-run. A stale RUNNING flag must not block the next run for four hours.
    if state.status=='RUNNING' and state.checked_at and now-state.checked_at>timedelta(minutes=10):
        for interrupted in db.query(FreeCollectionRun).filter(FreeCollectionRun.tenant_id==tenant_id,FreeCollectionRun.status=='RUNNING').all():
            interrupted.status='FAILED';interrupted.error='INTERRUPTED';interrupted.finished_at=now
            interrupted.seconds=max(0,(now-interrupted.started_at).total_seconds())
        state.status='FAILED';state.error='INTERRUPTED'
    cooldown=timedelta(minutes=15) if state.status in ['FAILED','DEGRADED'] else timedelta(hours=4)
    if force:cooldown=timedelta(minutes=15)
    if state.checked_at and now-state.checked_at<cooldown:
        result={'status':state.status,'cached':True,'found':state.found,'added':state.added,'duplicates':state.duplicates,'error':state.error}
        db.commit();return result
    run=FreeCollectionRun(tenant_id=tenant_id,started_at=now)
    db.add(run);state.checked_at=now;state.status='RUNNING';state.error='';db.commit()
    run_id=run.id
    own=client is None
    if own:client=httpx.Client(timeout=20,follow_redirects=False,headers={'User-Agent':'EuroteamsRSSReader/1.0 (recruitment feed reader)'})
    try:
        entries=[];feed_errors=[];successful=0
        for category in FEEDS:
            try:
                url='https://www.ss.com/ru/work/i-search-for-work/'+category+'/rss/'
                with client.stream('GET',url) as response:
                    response.raise_for_status()
                    raw=bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        if len(raw)>1_000_000:raise ValueError('feed_too_large')
                entries.extend(parse_feed(bytes(raw),category));successful+=1
            except (httpx.HTTPError,ValueError,ET.ParseError) as exc:
                feed_errors.append(category+':'+(str(exc.response.status_code) if isinstance(exc,httpx.HTTPStatusError) else type(exc).__name__))
        state.found=len(entries);state.added=0;state.duplicates=0
        if db.get_bind().dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock(64132979)'))
        contact_ads=profiles_added=0
        for entry in entries:
            contacts=entry.pop('public_contacts',{})
            if contacts:
                contact_ads+=1
                profiles_added+=int(store_rss_contacts(db,tenant_id,entry,contacts))
            old=db.query(FreeLead).filter(FreeLead.source_url==entry['source_url']).first()
            if old:
                old.last_seen_at=now;state.duplicates+=1
            else:
                db.add(FreeLead(tenant_id=tenant_id,**entry));state.added+=1
        state.error=','.join(feed_errors)[:80]
        # A healthy empty feed is successful; a failed category is degraded even if no ads match.
        state.status=('DEGRADED' if successful else 'FAILED') if feed_errors else 'COMPLETED'
        run.status=state.status;run.successful_sources=successful;run.found=state.found
        run.added=state.added;run.duplicates=state.duplicates;run.error=','.join(feed_errors)[:200]
        run.finished_at=datetime.utcnow();run.seconds=max(0,(run.finished_at-run.started_at).total_seconds())
        db.commit()
    except Exception as exc:
        db.rollback();state=db.get(FreeSourceState,STATE_ID);state.status='FAILED';state.found=0;state.added=0;state.duplicates=0
        state.error=f'HTTP_{exc.response.status_code}' if isinstance(exc,httpx.HTTPStatusError) else type(exc).__name__
        run=db.get(FreeCollectionRun,run_id);run.status='FAILED';run.error=state.error
        run.finished_at=datetime.utcnow();run.seconds=max(0,(run.finished_at-run.started_at).total_seconds())
        db.commit()
    finally:
        if own:client.close()
    return {'status':state.status,'found':state.found,'added':state.added,'duplicates':state.duplicates,'error':state.error,
            'run_id':run.id,'seconds':round(run.seconds,3),'active_sources':run.successful_sources,'rss_public_contact_ads':locals().get('contact_ads',0),'new_worker_profiles':locals().get('profiles_added',0)}


def install(app,current_user,require_roles,page_ctx):
    import os
    from fastapi import Depends,Request
    from fastapi.responses import RedirectResponse,HTMLResponse
    from fastapi.templating import Jinja2Templates
    from app.db import get_db
    @app.get('/collector/free-source/refresh')
    def refresh_public_cache(db=Depends(get_db)):
        # Fixed public feed only; no arbitrary URLs or submitted candidate data.
        # Durable four-hour cache bounds requests even when this URL is repeatedly visited.
        tid=int(os.getenv('WORKFORCE_ADMIN_TENANT_ID','1'))
        result=refresh(db,tid)
        from collector.public_discovery import refresh as refresh_public_jobseekers
        result["public_jobseekers"]=refresh_public_jobseekers(db,tid)
        from collector.romanian_discovery import refresh as refresh_romanian_jobseekers
        result["romanian_jobseekers"]=refresh_romanian_jobseekers(db,tid)
        from collector.polish_discovery import refresh as refresh_polish_jobseekers
        result["polish_jobseekers"]=refresh_polish_jobseekers(db,tid)
        from collector.acquisition_metrics import save_previous_day
        save_previous_day(db,tid)
        return result

    @app.get('/collector/free-leads',response_class=HTMLResponse)
    def leads(request:Request,page:int=1,db=Depends(get_db)):
        user=current_user(request,db)
        if not user:return RedirectResponse('/login',303)
        require_roles(user,'admin','recruiter')
        page=max(1,min(page,100000))
        rows=fresh_leads(db,user.tenant_id).order_by(FreeLead.id.desc()).offset((page-1)*20).limit(21).all()
        state=db.get(FreeSourceState,STATE_ID)
        views=Jinja2Templates(directory=[str(Path(__file__).parents[1]/'app'/'templates'),str(Path(__file__).parent/'templates')])
        return views.TemplateResponse(request,'free_leads.html',page_ctx(request,user,rows=rows[:20],has_more=len(rows)>20,page=page,state=state))
