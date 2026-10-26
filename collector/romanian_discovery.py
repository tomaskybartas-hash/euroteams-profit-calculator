"""Low-frequency public jobseeker reader; only visible ad facts, no reveal calls."""
from datetime import datetime,timedelta
from html.parser import HTMLParser
from urllib.parse import urljoin,urlparse
from urllib.robotparser import RobotFileParser
import re,time,unicodedata
import httpx
from collector.public_discovery import Document,read,AGENT

BASE='https://www.anunturi66.ro'
INDEX=BASE+'/afaceri-industrie-joburi/locuri-de-munca/cereri/'
SOURCE='anunturi66-public'
POLICY=BASE+'/termeni-si-conditii'
MONTHS='ianuarie februarie martie aprilie mai iunie iulie august septembrie octombrie noiembrie decembrie'.split()


def fold(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value.casefold()) if not unicodedata.combining(c))


def valid_url(url):
    p=urlparse(url)
    return p.scheme=='https' and p.netloc=='www.anunturi66.ro' and not p.query and not p.fragment and bool(re.fullmatch(r'/[a-z0-9-]+-\d{4,9}',p.path))


class Ad(Document):
    def __init__(self,raw):
        self.description=[];self.depth=0;self.in_description=False
        super().__init__(raw)
    def handle_starttag(self,tag,attrs):
        super().handle_starttag(tag,attrs)
        if self.hidden:return
        attrs=dict(attrs)
        if tag=='div':
            if self.in_description:self.depth+=1
            elif attrs.get('itemprop')=='description':self.in_description=True;self.depth=1
    def handle_data(self,data):
        super().handle_data(data)
        if self.in_description and not self.hidden:self.description.append(data)
    def handle_endtag(self,tag):
        if tag=='div' and self.in_description:
            self.depth-=1
            if self.depth==0:self.in_description=False
        super().handle_endtag(tag)


def listing_urls(raw):
    doc=Document(raw)
    if 'Anunțuri cereri de muncă' not in doc.text:raise ValueError('unexpected_listing')
    urls=[]
    for href in doc.links:
        url=urljoin(INDEX,href)
        if valid_url(url) and url not in urls:urls.append(url)
    return urls[:12]


def parse_ad(raw,url,now=None):
    if not valid_url(url):raise ValueError('outside_source')
    doc=Ad(raw);body=' '.join(' '.join(doc.description).split());plain=fold(body)
    if not re.search(r'caut\s+(?:un\s+)?(?:loc\s+de\s+munca|de\s+(?:munca|lucru))|doresc\s+angajarea',plain):return None
    if re.search(r'angajam|cautam\s+(?:sudor|muncitor|electrician)|agentie\s+de\s+recrutare',plain):return None
    roles=[('welder',r'sudor|sudura'),('pipefitter',r'instalator|conducte'),('electrician',r'electrician'),('carpenter',r'dulgher|tamplar'),('mason',r'zidar'),('mechanic',r'mecanic'),('general labour',r'muncitor|constructii|constructi|necalificat|manipulant')]
    role=next((r for r,p in roles if re.search(p,plain)),None)
    if not role:return None
    match=re.search(r'actualizat\s+(\d{1,2})\s+('+'|'.join(MONTHS)+r')\s+(\d{4})',fold(doc.text))
    if not match:raise ValueError('missing_publication_date')
    published=datetime(int(match[3]),MONTHS.index(match[2])+1,int(match[1]))
    now=now or datetime.utcnow()
    if not now-timedelta(days=30)<=published<=now+timedelta(hours=1):return None
    # Only numbers explicitly present in the ad description; not publisher/sidebar data.
    phones=set()
    for value in re.findall(r'(?<!\d)(?:(?:\+40[ .()-]*|0)[ .()-]*7(?:[ .()-]*\d){8})(?!\d)',body):
        digits=re.sub(r'\D','',value)
        if digits.startswith('0'):digits='40'+digits[1:]
        if len(digits)==11 and digits.startswith('407'):phones.add('+'+digits)
    if len(phones)!=1:return None
    sid=url.rsplit('-',1)[1]
    local=bool(re.search(r'doar\s+(?:in\s+)?(?:tara|romania)',plain))
    return {'source_id':sid,'source_url':url,'phone':phones.pop(),'profession':role,'published_at':published,
        'full_name':'Vardas nepateiktas · RO-'+sid,'preferred_countries':'RO' if local else '',
        'notes':'Only work in Romania is requested in the ad.' if local else 'Destination preference not confirmed.'}


def discover(client):
    robot=RobotFileParser()
    try:raw=read(client,BASE+'/robots.txt',100000)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code!=404:raise ValueError('robots_unavailable') from exc
        raw='User-agent: *\nAllow: /'
    robot.parse(raw.splitlines())
    if not robot.can_fetch(AGENT,INDEX):raise ValueError('robots_disallowed')
    delay=max(1,robot.crawl_delay(AGENT) or robot.crawl_delay('*') or 1)
    if delay>5:raise ValueError('source_rate_limit')
    rows=[];failed=0
    for url in listing_urls(read(client,INDEX)):
        if not robot.can_fetch(AGENT,url):continue
        time.sleep(delay)
        try:
            row=parse_ad(read(client,url),url)
            if row:rows.append(row)
        except (httpx.HTTPError,ValueError):failed+=1
    return rows,failed


def refresh(db,tenant_id=1,client=None):
    from collector.public_discovery import refresh as run
    return run(db,tenant_id,client,source_key=SOURCE,country='RO',discoverer=discover,policy=POLICY)
