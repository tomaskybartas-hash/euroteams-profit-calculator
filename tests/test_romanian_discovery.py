from datetime import datetime,timedelta
import pytest,httpx
from sqlalchemy.orm import Session
from test_platform_flow import setup
from collector import romanian_discovery as source
from collector.coresignal import SourceProfile,SourceRun
from app.models import Worker,Consent
URL=source.BASE+'/caut-loc-de-munca-123456'


def ad(body='Doresc Angajarea. Caut un loc de munca sudor. Doar in Romania. tel: 0700 000 001',days=0):
    date=datetime.utcnow()-timedelta(days=days)
    return '<h1>Logo</h1><h2 itemprop="name">Sudor</h2><div itemprop="description">'+body+'</div><span>Actualizat '+str(date.day)+' '+source.MONTHS[date.month-1]+' '+str(date.year)+'</span><footer>0755 555 555</footer>'


def test_scoped_visible_contacts_local_limits_and_dates():
    row=source.parse_ad(ad(),URL)
    assert row['phone']=='+40700000001' and row['preferred_countries']=='RO'
    assert row['profession']=='welder'
    assert source.parse_ad(ad(days=32),URL) is None
    assert source.parse_ad(ad('Cautam sudor. Angajam. 0700000001'),URL) is None
    assert source.parse_ad(ad('Execut sudura la cerere client. 0700000001'),URL) is None
    assert source.parse_ad(ad('Caut un loc de munca sudor 0700000001 0700000002'),URL) is None
    assert source.parse_ad(ad('Caut un loc de munca sudor 07xxxx0001'),URL) is None
    assert source.parse_ad(ad('Caut un loc de munca sudor <script>0700000001</script>'),URL) is None
    with pytest.raises(ValueError):source.parse_ad(ad(),source.BASE+'/anunturi/autentificare')


def test_bounded_listing_and_robots_fail_closed():
    raw='<h2>Anunțuri cereri de muncă</h2><a href="'+URL+'">ad</a><a href="https://evil.test/ad-12345">bad</a><a href="'+URL+'?reveal=1">bad</a>'
    assert source.listing_urls(raw)==[URL]
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,text='User-agent: *\nDisallow: /'))) as client:
        with pytest.raises(ValueError,match='robots_disallowed'):source.discover(client)


def test_country_runs_are_independent_and_public_contacts_do_not_grant_consent(setup,monkeypatch):
    _,engine=setup
    row=source.parse_ad(ad(),URL)
    monkeypatch.setattr(source,'discover',lambda c:([row],0))
    with Session(engine) as db:
        db.add(SourceRun(tenant_id=1,run_key='liepajniekiem-public:1:qa',state='FAILED'));db.commit()
        result=source.refresh(db,1,client=object())
        assert not result['cached'] and result['added']==1
        profile=db.query(SourceProfile).filter_by(source=source.SOURCE).one()
        worker=db.get(Worker,profile.worker_id)
        assert worker.country=='RO' and worker.preferred_countries=='RO'
        assert worker.availability_status=='UNKNOWN' and not worker.skills_verified
        assert db.query(Consent).filter_by(worker_id=worker.id).count()==0
        assert source.refresh(db,1,client=object())['cached']
