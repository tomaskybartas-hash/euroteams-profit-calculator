"""Free, low-frequency RSS discovery. Leads are jobseeker ads, not verified workers."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse
import html
import re
import xml.etree.ElementTree as ET
import httpx
from sqlalchemy import Integer, String, DateTime, ForeignKey, text
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


def parse_feed(raw,category="welder"):
    if len(raw)>1_000_000 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('unsupported_feed')
    root=ET.fromstring(raw)
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
        results.append({'source_url':url,'title':title[:180],'published_at':posted,'profession':FEEDS[category],'source':'ss-jobseeker-'+category+'-rss'})
    return results


def refresh(db, tenant_id=1, client=None):
    if db.get_bind().dialect.name=='postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(64132972)'))
    state=db.get(FreeSourceState,STATE_ID)
    if state is None:
        state=FreeSourceState(id=STATE_ID);db.add(state);db.flush()
    now=datetime.utcnow()
    cooldown=timedelta(minutes=15) if state.status=='FAILED' else timedelta(hours=4)
    if state.checked_at and now-state.checked_at<cooldown:
        result={'status':state.status,'cached':True,'found':state.found,'added':state.added}
        db.commit();return result
    state.checked_at=now;state.status='RUNNING';state.error='';db.commit()
    own=client is None
    if own:client=httpx.Client(timeout=20,follow_redirects=False,headers={'User-Agent':'EuroteamsRSSReader/1.0 (recruitment feed reader)'})
    try:
        entries=[];feed_errors=[]
        for category in FEEDS:
            try:
                url='https://www.ss.com/ru/work/i-search-for-work/'+category+'/rss/'
                with client.stream('GET',url) as response:
                    response.raise_for_status()
                    raw=bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        if len(raw)>1_000_000:raise ValueError('feed_too_large')
                entries.extend(parse_feed(bytes(raw),category))
            except (httpx.HTTPError,ValueError,ET.ParseError) as exc:
                feed_errors.append(category+':'+(str(exc.response.status_code) if isinstance(exc,httpx.HTTPStatusError) else type(exc).__name__))
        state.found=len(entries);state.added=0;state.duplicates=0
        for entry in entries:
            old=db.query(FreeLead).filter(FreeLead.source_url==entry['source_url']).first()
            if old:
                old.last_seen_at=now;state.duplicates+=1
            else:
                db.add(FreeLead(tenant_id=tenant_id,**entry));state.added+=1
        state.error=','.join(feed_errors)[:80]
        state.status=('DEGRADED' if entries else 'FAILED') if feed_errors else 'COMPLETED'
        db.commit()
    except Exception as exc:
        db.rollback();state=db.get(FreeSourceState,STATE_ID);state.status='FAILED'
        state.error=f'HTTP_{exc.response.status_code}' if isinstance(exc,httpx.HTTPStatusError) else type(exc).__name__
        db.commit()
    finally:
        if own:client.close()
    return {'status':state.status,'found':state.found,'added':state.added,'duplicates':state.duplicates,'error':state.error}


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
        return refresh(db,int(os.getenv('WORKFORCE_ADMIN_TENANT_ID','1')))

    @app.get('/collector/free-leads',response_class=HTMLResponse)
    def leads(request:Request,page:int=1,db=Depends(get_db)):
        user=current_user(request,db)
        if not user:return RedirectResponse('/login',303)
        require_roles(user,'admin','recruiter')
        page=max(1,min(page,100000))
        rows=db.query(FreeLead).filter(FreeLead.tenant_id==user.tenant_id).order_by(FreeLead.id.desc()).offset((page-1)*20).limit(21).all()
        state=db.get(FreeSourceState,STATE_ID)
        views=Jinja2Templates(directory=[str(Path(__file__).parents[1]/'app'/'templates'),str(Path(__file__).parent/'templates')])
        return views.TemplateResponse(request,'free_leads.html',page_ctx(request,user,rows=rows[:20],has_more=len(rows)>20,page=page,state=state))
