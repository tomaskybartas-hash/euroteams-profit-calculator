from datetime import datetime,timedelta
import httpx
import pytest
from sqlalchemy.orm import Session
from test_platform_flow import setup
from collector import public_discovery as source
from collector.coresignal import SourceRun,SourceProfile
from app.models import Worker,Consent

URL=source.INDEX+'test-ad-a/'

def ad(body='Meklēju darbu celtniecībā. 20000001',days=0):
    day=(datetime.utcnow()-timedelta(days=days)).strftime('%d.%m.%Y')
    return f'<html><script>fake</script><h1>mekleju darbu</h1><p>{body}</p><div>Datums: {day} 00:01</div><footer>Publisher phone 29999999</footer></html>'

def test_only_relevant_recent_ads_and_unambiguous_public_contacts():
    row=source.parse_ad(ad(),URL)
    assert row['phone']=='+37120000001' and row['profession']=='general labour'
    assert row['full_name'].startswith('Public jobseeker LV')
    assert source.parse_ad(ad(days=31),URL) is None
    assert source.parse_ad(ad('Meklējam darbiniekus celtniecībā 20000001'),URL) is None
    assert source.parse_ad(ad('Veicu elektro darbus 20000001'),URL) is None
    assert source.parse_ad(ad('Meklēju darbu celtniecībā 20000001, 20000002'),URL) is None
    assert source.parse_ad(ad('Meklēju darbu celtniecībā 20****01'),URL) is None
    with pytest.raises(ValueError):source.parse_ad(ad(),'https://example.test/private')

def test_discovery_respects_robots_and_does_not_follow_arbitrary_links(monkeypatch):
    calls=[]
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200,text='User-agent: *\nDisallow: /sludinajumi/')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError,match='robots_disallowed'):source.discover(client)
    assert calls==[source.BASE+'/robots.txt']
    listing='<h1>Meklēju darbu</h1><a href="'+URL+'">ad</a><a href="https://evil.test/ad">no</a><a href="/sludinajumi/darbs/mekleju-darbu/page/2/">page</a>'
    assert source.listing_urls(listing)==[URL]

def test_public_profile_dedupe_preserves_registered_data_and_no_optin(setup,monkeypatch):
    _,engine=setup
    row=source.parse_ad(ad(),URL)
    monkeypatch.setattr(source,'discover',lambda client:([row],0))
    with Session(engine) as db:
        first=source.refresh(db,1,client=object())
        assert first['state']=='COMPLETED' and first['added']==1
        profile=db.query(SourceProfile).filter_by(source=source.SOURCE).one()
        worker=db.get(Worker,profile.worker_id)
        assert worker.availability_status=='UNKNOWN' and not worker.eu_citizen
        assert not worker.identity_verified and not worker.ready_to_deploy
        assert worker.last_availability_confirmed is None
        assert not db.query(Consent).filter_by(worker_id=worker.id).count()
        assert source.refresh(db,1,client=object())['cached']
        assert db.query(SourceRun).filter(SourceRun.run_key.like(source.SOURCE+':%')).count()==1
        previous=db.query(SourceRun).first();previous.created_at-=timedelta(hours=7);db.commit()
        assert source.refresh(db,1,client=object())['duplicates']==1
        assert db.query(SourceProfile).count()==1
        # Same phone, different advertisement must not create another person.
        row['source_id']='other-ad';row['source_url']=source.INDEX+'other/'
        for run in db.query(SourceRun):run.created_at-=timedelta(hours=7)
        db.commit()
        assert source.refresh(db,1,client=object())['duplicates']==1
        assert db.query(SourceProfile).count()==1

def test_source_failure_is_audited_and_contains_no_contact_data(setup,monkeypatch):
    _,engine=setup
    def fail(client):raise ValueError('robots_unavailable')
    monkeypatch.setattr(source,'discover',fail)
    with Session(engine) as db:
        result=source.refresh(db,1,client=object())
        assert result['state']=='FAILED' and result['error']=='robots_unavailable'
        assert result['added']==0 and 'phone' not in str(result)
        assert db.query(SourceProfile).count()==0
