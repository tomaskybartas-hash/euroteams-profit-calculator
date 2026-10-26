"""Public Polish jobseeker listing reader, bounded to two current listing pages."""
from datetime import datetime,timedelta
from html import escape
from html.parser import HTMLParser
from urllib.parse import urljoin,urlparse
from urllib.robotparser import RobotFileParser
import hashlib,re,unicodedata,time
import httpx
from collector.public_discovery import Document,read,AGENT
BASE='https://www.suwalki.info'
INDEX=BASE+'/ogloszenia/praca/praca-szukam'
SOURCE='suwalki-public'
POLICY=BASE+'/index.php/regulamin-ogloszenia'


def fold(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value.casefold().replace('ł','l')) if not unicodedata.combining(c))


class Cards(HTMLParser):
    def __init__(self,raw):
        super().__init__(convert_charrefs=True)
        self.cards=[];self.current=[];self.depth=0
        self.feed(raw)
    def handle_starttag(self,tag,attrs):
        if tag=='div':
            if self.depth:self.depth+=1
            elif 'item' in dict(attrs).get('class','').split() and 'ogloszenie-select-' in dict(attrs).get('class',''):self.depth=1
        if self.depth:self.current.append(self.get_starttag_text())
    def handle_endtag(self,tag):
        if not self.depth:return
        self.current.append('</'+tag+'>')
        if tag=='div':
            self.depth-=1
            if not self.depth:self.cards.append(''.join(self.current));self.current=[]
    def handle_data(self,data):
        if self.depth:self.current.append(escape(data))


def valid_url(url):
    p=urlparse(url)
    return p.scheme=='https' and p.netloc=='www.suwalki.info' and not p.query and not p.fragment and bool(re.fullmatch(r'/ogloszenia/praca/praca/praca-szukam/[a-z0-9-]+',p.path))


def parse_listing(raw,now=None):
    cards=Cards(raw).cards
    if not cards:raise ValueError('unexpected_listing')
    now=now or datetime.utcnow();rows=[]
    for card in cards[:40]:
        doc=Document(card);body=doc.text;plain=fold(body)
        urls=[urljoin(INDEX,x) for x in doc.links if valid_url(urljoin(INDEX,x))]
        if not urls:continue
        if not re.search(r'szukam|poszukuje|podejme',plain) or re.search(r'szukam\s+pracownik|zatrudni|poszukuje\s+pracownik',plain):continue
        if re.search(r'odpada[^.]*budow|procz\s+budow|bez\s+budowl',plain):continue
        roles=[('welder',r'spawacz|spawani'),('pipefitter',r'monter\s+rur|rurociag'),('plumber',r'hydraulik'),('electrician',r'elektryk'),('carpenter',r'ciesla|stolarz|stolarni'),('mason',r'murarz'),('mechanic',r'mechanik'),('general labour',r'budow|fizyczn|pomocnik|magazyn|produkcj')]
        role=next((r for r,p in roles if re.search(p,plain)),None)
        if not role:continue
        if re.search(r'pomocnik(?:a)?\s+mechanik',plain):role='general labour'
        dates=re.findall(r'(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)',body)
        if not dates:continue
        try:published=datetime.strptime(dates[-1],'%Y-%m-%d')
        except ValueError:continue
        if not now-timedelta(days=30)<=published<=now+timedelta(hours=1):continue
        found=re.search(r'Telefon:\s*(.*?)\s*Mail:',body,re.S)
        if not found:continue
        # Multiple phone numbers are ambiguous: never invent which is personal.
        digits=re.sub(r'\D','',found[1])
        if len(digits)==9:digits='48'+digits
        if len(digits)!=11 or not digits.startswith('48'):continue
        emails=set(x.lower() for x in re.findall(r'(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])',body))
        if len(emails)>1:continue
        url=urls[0];sid=hashlib.sha256(url.encode()).hexdigest()[:20]
        local=bool(re.search(r'w suwalkach|tylko suwalki|na terenie miasta|suwalki i okolice',plain))
        short=bool(re.search(r'dorywcz|weekend|na\s+\d+\s+dni|dwa tygodnie|popoludni',plain))
        notes=('Local work requested; destination PL only. ' if local else 'Destination preference not confirmed. ')+('Short-term or part-time work requested. ' if short else '')+'Profession is inferred from the public listing excerpt; exact skills and current availability require confirmation.'
        rows.append(dict(source_id=sid,source_url=url,phone='+'+digits,email=next(iter(emails),''),profession=role,published_at=published,full_name='Vardas nepateiktas · PL-'+sid[:8],preferred_countries='PL' if local else '',notes=notes))
    return rows


def discover(client):
    robot=RobotFileParser()
    try:raw=read(client,BASE+'/robots.txt',100000)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code!=404:raise ValueError('robots_unavailable') from exc
        raw='User-agent: *\nAllow: /'
    robot.parse(raw.splitlines())
    if not robot.can_fetch(AGENT,INDEX):raise ValueError('robots_disallowed')
    if (robot.crawl_delay(AGENT) or robot.crawl_delay('*') or 1)>5:raise ValueError('source_rate_limit')
    rows=parse_listing(read(client,INDEX));failed=0
    second=INDEX+'?keys=&page=1'
    if robot.can_fetch(AGENT,second):
        time.sleep(max(1,robot.crawl_delay(AGENT) or robot.crawl_delay('*') or 1))
        try:rows.extend(parse_listing(read(client,second)))
        except (httpx.HTTPError,ValueError):failed+=1
    return rows,failed


def refresh(db,tenant_id=1,client=None):
    from collector.public_discovery import refresh as run
    return run(db,tenant_id,client,source_key=SOURCE,country='PL',discoverer=discover,policy=POLICY)
