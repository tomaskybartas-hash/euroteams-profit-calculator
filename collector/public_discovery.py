"""Bounded public jobseeker discovery. No accounts, contact reveals or outreach.

Liepaja and Romanian jobseeker readers use bounded requests and retain source
attribution. Other sources remain in the research catalogue until checked.
"""
from datetime import datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import hashlib
import re
import unicodedata
import httpx

BASE = 'https://www.liepajniekiem.lv'
INDEX = BASE + '/sludinajumi/darbs/mekleju-darbu/'
POLICY = BASE + '/autortiesibas/'
AGENT = 'EuroteamsPublicJobReader'
SOURCE = 'liepajniekiem-public'

class Document(HTMLParser):
    def __init__(self, raw):
        super().__init__(convert_charrefs=True)
        self.parts=[]; self.links=[]; self.hidden=0
        self.feed(raw)
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','noscript'): self.hidden+=1
        if self.hidden: return
        attrs=dict(attrs)
        if tag=='a' and attrs.get('href'): self.links.append(attrs['href'])
        if tag=='h1': self.parts.append('\n__H1__\n')
        elif tag in ('p','div','br','li','h2','h3','article','section','time'): self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script','style','noscript'): self.hidden=max(0,self.hidden-1)
        if not self.hidden and tag in ('p','div','li','h1','h2','article','section'): self.parts.append('\n')
    def handle_data(self, data):
        if not self.hidden:self.parts.append(data)
    @property
    def text(self): return '\n'.join(' '.join(x.split()) for x in ''.join(self.parts).splitlines() if x.strip())

def valid_url(url):
    p=urlparse(url)
    return (p.scheme=='https' and p.netloc=='www.liepajniekiem.lv' and
            not p.query and not p.fragment and not p.username and
            p.path.startswith('/sludinajumi/darbs/mekleju-darbu/'))

def listing_urls(raw):
    doc=Document(raw)
    if '__H1__' not in doc.text or 'Meklēju darbu'.casefold() not in doc.text.casefold():
        raise ValueError('unexpected_listing')
    out=[]
    for href in doc.links:
        url=urljoin(INDEX,href)
        path=urlparse(url).path
        if valid_url(url) and path!=urlparse(INDEX).path and not re.search(r'/page/|/feed/',path) and url not in out:
            out.append(url)
    return out[:8]

def parse_ad(raw, url, now=None):
    if not valid_url(url): raise ValueError('outside_source')
    doc=Document(raw)
    if '__H1__' not in doc.text: raise ValueError('missing_ad')
    body=doc.text.split('__H1__',1)[1]
    match=re.search(r'Datums:\s*(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})',body)
    if not match: raise ValueError('missing_publication_date')
    published=datetime.strptime(match.group(1)+' '+match.group(2),'%d.%m.%Y %H:%M')
    from zoneinfo import ZoneInfo
    published=published.replace(tzinfo=ZoneInfo('Europe/Riga')).astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
    now=now or datetime.utcnow()
    if not now-timedelta(days=30)<=published<=now+timedelta(hours=1): return None
    body=body[:match.start()]
    folded=''.join(c for c in unicodedata.normalize('NFKD',body.casefold()) if not unicodedata.combining(c))
    if not re.search(r'mekle(?:ju|jam)?\s+(?:pastavigu\s+|patstavigu\s+)?darbu|mekle\s+darbu|ищу\s+работ',folded): return None
    if re.search(r'meklejam\s+(?:darbiniek|stradniek)|aicinam\s+pievienoties',folded): return None
    roles=[('welder',r'metina|сварщик'),('pipefitter',r'caurul|santehnik'),('electrician',r'elektrik'),('carpenter',r'galdnie|koka karkas'),('mason',r'murniek'),('mechanic',r'mehanik'),('general labour',r'celtniec|paligstrad|kra[uv]ej|fizisk|haltur|demont')]
    role=next((role for role,pattern in roles if re.search(pattern,folded)),None)
    if not role: return None
    numbers=[]
    for item in re.findall(r'(?<!\d)(?:\+371[ ()-]*)?[2][0-9 ()-]{6,16}[0-9](?!\d)',body):
        digits=re.sub(r'\D','',item)
        if digits.startswith('371') and len(digits)==11:digits=digits[3:]
        if len(digits)==8 and digits.startswith('2') and '+371'+digits not in numbers:numbers.append('+371'+digits)
    if len(numbers)!=1: return None  # Reject ambiguous/shared-contact advertisements.
    ident=hashlib.sha256(url.encode()).hexdigest()[:20]
    return dict(source_id=ident,source_url=url,phone=numbers[0],profession=role,
                published_at=published,full_name='Public jobseeker LV · '+ident[:8])

def read(client,url,limit=1000000):
    with client.stream('GET',url) as response:
        response.raise_for_status()
        raw=bytearray()
        for chunk in response.iter_bytes():
            raw.extend(chunk)
            if len(raw)>limit: raise ValueError('response_too_large')
        return bytes(raw).decode('utf-8',errors='replace')

def discover(client):
    robot=RobotFileParser()
    try: raw=read(client,BASE+'/robots.txt',100000)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code!=404: raise ValueError('robots_unavailable') from exc
        raw='User-agent: *\nAllow: /'
    robot.parse(raw.splitlines())
    if not robot.can_fetch(AGENT,INDEX):raise ValueError('robots_disallowed')
    urls=listing_urls(read(client,INDEX))
    rows=[]; failed=0
    import time
    delay=max(1,robot.crawl_delay(AGENT) or robot.crawl_delay("*") or 1)
    if delay>5:raise ValueError("source_rate_limit")
    for url in urls:
        if not robot.can_fetch(AGENT,url):continue
        try:
            time.sleep(delay)
            row=parse_ad(read(client,url),url)
            if row:rows.append(row)
        except (httpx.HTTPError,ValueError):failed+=1
    return rows,failed


def refresh(db,tenant_id=1,client=None,*,source_key=SOURCE,country="LV",discoverer=None,policy=POLICY):
    from contextlib import nullcontext
    from app.models import Worker,AuditLog
    from collector.coresignal import SourceRun,SourceProfile
    from sqlalchemy import text,func
    import secrets
    now=datetime.utcnow()
    if db.get_bind().dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock(64132979)'))
    previous=db.query(SourceRun).filter(SourceRun.tenant_id==tenant_id,SourceRun.run_key.like(source_key+':%')).order_by(SourceRun.id.desc()).first()
    if previous and previous.state=='RUNNING' and now-previous.created_at>timedelta(minutes=10):
        previous.state='FAILED';previous.error_code='INTERRUPTED';previous.finished_at=now
        db.commit()
        previous=None
    if previous and now-previous.created_at<timedelta(hours=6):
        result={'state':previous.state,'added':previous.added,'found':previous.found,'duplicates':previous.duplicates,'error':previous.error_code,'cached':True}
        db.commit();return result
    run=SourceRun(tenant_id=tenant_id,run_key=source_key+':'+str(tenant_id)+':'+now.isoformat())
    db.add(run);db.commit();run_id=run.id
    try:
        with (httpx.Client(timeout=6,follow_redirects=False,headers={'User-Agent':AGENT+'/1.0 (public jobseeker discovery; source attribution retained)'}) if client is None else nullcontext(client)) as http:
            rows,failed=(discoverer or discover)(http)
        if db.get_bind().dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock(64132979)'))
        run.found=len(rows);run.errors=failed
        for row in rows:
            old=db.query(SourceProfile).filter_by(tenant_id=tenant_id,source_url=row['source_url']).first()
            if old:run.duplicates+=1;continue
            normalized=Worker.phone
            for char in (' ','-','(',')','.'):normalized=func.replace(normalized,char,'')
            existing=db.query(Worker).filter(Worker.tenant_id==tenant_id,normalized==row['phone']).first()
            if existing:run.duplicates+=1;continue  # Never overwrite first-party profiles or revive consent.
            worker=Worker(tenant_id=tenant_id,full_name=row['full_name'],country=country,profession=row['profession'],
                phone=row['phone'],email='',availability_status='UNKNOWN',eu_citizen=False,
                ready_to_deploy=False,identity_verified=False,documents_verified=False,skills_verified=False,
                years_experience=0,preferred_channel='Phone',self_service_token=secrets.token_urlsafe(32),
                preferred_countries=row.get('preferred_countries',''),
                work_permit_notes=row.get('notes','')+' Public jobseeker advertisement; name, current availability and right to work unverified. No Email/WhatsApp opt-in. Source: '+row['source_url'])
            db.add(worker);db.flush()
            db.add(SourceProfile(tenant_id=tenant_id,worker_id=worker.id,source=source_key,source_id=row['source_id'],
                source_url=row['source_url'],reported_title='Public jobseeker advertisement · '+row['profession'],
                provider_updated_at=row['published_at'].isoformat(),verification_status='UNCONFIRMED',
                permission_basis='Public work-seeking advertisement; minimal recruitment review facts; source attribution: '+policy+'; no communication opt-in inferred'))
            db.add(AuditLog(tenant_id=tenant_id,actor='public-jobseeker-discovery',action='PUBLIC_JOBSEEKER_COLLECTED',entity_type='worker',entity_id=str(worker.id),details='source='+source_key+'; no messaging consent inferred'))
            run.added+=1
        run.state='DEGRADED' if failed else 'COMPLETED'
        db.commit()
    except Exception as exc:
        db.rollback();run=db.get(SourceRun,run_id);run.state='FAILED';run.errors+=1
        run.error_code=(str(exc) if isinstance(exc,ValueError) and str(exc) in {'robots_unavailable','robots_disallowed','unexpected_listing','response_too_large','source_rate_limit'} else 'HTTP_'+str(exc.response.status_code) if isinstance(exc,httpx.HTTPStatusError) else type(exc).__name__)
    run.finished_at=datetime.utcnow();db.commit()
    return {'state':run.state,'added':run.added,'found':run.found,'duplicates':run.duplicates,'error':run.error_code,'cached':False}
