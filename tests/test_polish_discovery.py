from datetime import datetime,timedelta
import httpx,pytest
from sqlalchemy.orm import Session
from test_platform_flow import setup
from collector import polish_discovery as source
from collector.coresignal import SourceProfile
from app.models import Worker,Consent
URL=source.BASE+'/ogloszenia/praca/praca/praca-szukam/test-jobseeker'


def listing(body='Szukam pracy fizycznej jako pomocnik',phone='600 000 009',email='worker@example.test',days=0):
    date=(datetime.utcnow()-timedelta(days=days)).strftime('%Y-%m-%d')
    return '<div class="ogloszenie-select-TYP1 item"><div><h5><a href="'+URL+'">'+body+'</a></h5></div><div>'+body+'</div><span>Telefon: '+phone+'</span><span>Mail: '+email+'</span><span> '+date+'</span></div>'


def test_public_listing_requires_recent_jobseeker_intent_and_unique_contact():
    rows=source.parse_listing(listing());assert len(rows)==1
    row=rows[0]
    assert row['phone']=='+48600000009' and row['email']=='worker@example.test'
    assert row['profession']=='general labour' and row['preferred_countries']==''
    assert source.parse_listing(listing(days=32))==[]
    assert source.parse_listing(listing('Szukam pracownika na budowe'))==[]
    assert source.parse_listing(listing('Szukam pracy, odpada budowlanka'))==[]
    assert source.parse_listing(listing(phone='600000009, 600000010'))==[]
    assert source.parse_listing(listing(phone='60xxxx009'))==[]
    assert source.parse_listing(listing('Szukam pracy fizycznej w Suwałkach dorywczo'))[0]['preferred_countries']=='PL'
    assert not source.valid_url(URL+'?reveal=1')
    with pytest.raises(ValueError):source.parse_listing('<h1>Blocked</h1>')


def test_robots_block_stops_before_reading_ads():
    calls=[]
    def handler(request):
        calls.append(str(request.url));return httpx.Response(200,text='User-agent: *\nDisallow: /ogloszenia/')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError,match='robots_disallowed'):source.discover(client)
    assert calls==[source.BASE+'/robots.txt']


def test_polish_contact_saved_once_and_email_dedupes_changed_phone(setup,monkeypatch):
    _,engine=setup
    row=source.parse_listing(listing())[0]
    monkeypatch.setattr(source,'discover',lambda c:([row],0))
    with Session(engine) as db:
        result=source.refresh(db,1,client=object());assert result['added']==1
        profile=db.query(SourceProfile).filter_by(source=source.SOURCE).one()
        worker=db.get(Worker,profile.worker_id)
        assert worker.email=='worker@example.test' and worker.country=='PL'
        assert worker.availability_status=='UNKNOWN' and not worker.ready_to_deploy
        assert db.query(Consent).filter_by(worker_id=worker.id).count()==0
        from collector.coresignal import SourceRun
        run=db.query(SourceRun).filter(SourceRun.run_key.like(source.SOURCE+':%')).one()
        run.created_at-=timedelta(hours=7);db.commit()
        row.update(source_id='second',source_url=URL+'-second',phone='+48600000010')
        assert source.refresh(db,1,client=object())['duplicates']==1
        assert db.query(SourceProfile).filter_by(source=source.SOURCE).count()==1


def test_second_page_failure_keeps_first_page_candidates(monkeypatch):
    monkeypatch.setattr(source.time,'sleep',lambda delay:None)
    def handler(request):
        if request.url.path=='/robots.txt':return httpx.Response(200,text='User-agent: *\nAllow: /')
        if request.url.query:return httpx.Response(503,text='temporary error')
        return httpx.Response(200,text=listing())
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows,failed=source.discover(client)
    assert len(rows)==1 and failed==1


def test_helper_and_domestic_plumber_do_not_become_industrial_specialists():
    row=source.parse_listing(listing('Szukam pracy dorywczej jako pomocnik mechanika tylko Suwałki'))[0]
    assert row['profession']=='general labour' and row['preferred_countries']=='PL'
    row=source.parse_listing(listing('Szukam pracy jako hydraulik'))[0]
    assert row['profession']=='plumber'
