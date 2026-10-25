from datetime import datetime,timedelta,timezone
from email.utils import format_datetime
import httpx
import pytest
from sqlalchemy.orm import Session
from test_platform_flow import setup
from collector.free_sources import refresh,FreeLead,FreeCollectionRun,FreeSourceState,STATE_ID,fresh_leads,parse_feed


def feed():
    posted=format_datetime(datetime.now(timezone.utc))
    return f'<rss><channel><item><title>Ищу работу сварщика</title><link>https://www.ss.com/msg/ru/work/i-search-for-work/welder/abc.html</link><pubDate>{posted}</pubDate></item></channel></rss>'.encode()


def test_real_runs_have_history_but_cached_checks_do_not(setup):
    _,engine=setup
    with Session(engine) as db,httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=feed()))) as client:
        first=refresh(db,1,client)
        assert first['status']=='COMPLETED' and first['added']==1
        run=db.query(FreeCollectionRun).one()
        assert run.finished_at>=run.started_at and run.seconds>=0
        assert run.found==1 and run.added==1 and run.successful_sources==4
        assert refresh(db,1,client)['cached'] is True
        assert db.query(FreeCollectionRun).count()==1
        state=db.get(FreeSourceState,STATE_ID);state.checked_at-=timedelta(hours=5);db.commit()
        assert refresh(db,1,client)['duplicates']==1
        assert db.query(FreeCollectionRun).count()==2
        assert db.query(FreeLead).count()==1


def test_partial_feed_failure_is_audited_without_stopping_healthy_feeds(setup):
    _,engine=setup
    def handler(request):
        return httpx.Response(503) if '/mason/' in str(request.url) else httpx.Response(200,content=feed())
    with Session(engine) as db,httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result=refresh(db,1,client)
        assert result['status']=='DEGRADED' and result['active_sources']==3
        row=db.query(FreeCollectionRun).one()
        assert row.error=='mason:503' and row.added==1


def test_interrupted_run_is_recovered_and_preserved_in_history(setup):
    _,engine=setup
    old=datetime.utcnow()-timedelta(minutes=20)
    with Session(engine) as db,httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=feed()))) as client:
        db.add(FreeSourceState(id=STATE_ID,status='RUNNING',checked_at=old))
        db.add(FreeCollectionRun(tenant_id=1,started_at=old,status='RUNNING'));db.commit()
        assert refresh(db,1,client)['status']=='COMPLETED'
        rows=db.query(FreeCollectionRun).order_by(FreeCollectionRun.id).all()
        assert len(rows)==2 and rows[0].status=='FAILED' and rows[0].error=='INTERRUPTED'
        assert rows[1].status=='COMPLETED'


def test_old_and_unseen_ads_are_hidden_without_deleting_source_evidence(setup):
    _,engine=setup;now=datetime.utcnow()
    with Session(engine) as db:
        for i,(published,seen) in enumerate([(now,now),(now-timedelta(days=31),now),(now,now-timedelta(days=31)),(None,now)]):
            db.add(FreeLead(tenant_id=1,source_url=f'https://www.ss.com/test/{i}',title=f'QA {i}',profession='welder',published_at=published,last_seen_at=seen))
        db.commit()
        assert fresh_leads(db,1).count()==2
        assert db.query(FreeLead).count()==4
        assert fresh_leads(db,2).count()==0


def test_sources_history_is_tenant_scoped_and_eures_is_not_claimed_connected(setup):
    client,engine=setup
    with Session(engine) as db:
        db.add(FreeCollectionRun(tenant_id=2,status='FAILED',error='PRIVATE_OTHER_TENANT_ERROR'));db.commit()
    page=client.get('/sources')
    assert page.status_code==200
    assert 'Collection history' in page.text and 'PRIVATE_OTHER_TENANT_ERROR' not in page.text
    assert 'Employer registration required' in page.text
    assert 'Automatic export or API access has not been confirmed.' in page.text
    client.get('/language/lt?next=/sources')
    assert 'Rinkimo istorija' in client.get('/sources').text


def test_html_cannot_be_mistaken_for_a_healthy_rss_feed():
    with pytest.raises(ValueError):parse_feed(b'<html><body>Not an RSS feed</body></html>')

def test_manual_refresh_keeps_rate_limit_and_reuses_existing_ads(setup):
    _,engine=setup;calls=[]
    def handler(request):
        calls.append(str(request.url));return httpx.Response(200,content=feed())
    with Session(engine) as db,httpx.Client(transport=httpx.MockTransport(handler)) as client:
        refresh(db,1,client)
        assert refresh(db,1,client,force=True)['cached'] is True
        assert len(calls)==4
        state=db.get(FreeSourceState,STATE_ID);state.checked_at-=timedelta(hours=1);db.commit()
        assert refresh(db,1,client)['cached'] is True
        assert refresh(db,1,client,force=True)['duplicates']==1
        assert len(calls)==8 and db.query(FreeCollectionRun).count()==2


def test_manual_refresh_requires_admin_and_csrf(setup,monkeypatch):
    client,engine=setup
    from test_platform_flow import hidden
    from app.models import AppUser
    import collector.free_sources as source
    calls=[]
    monkeypatch.setattr(source,'refresh',lambda db,tenant_id,force=False:calls.append((tenant_id,force)))
    assert client.post('/collector/free-source/run',data={}).status_code==403
    token=hidden(client.get('/sources').text,'csrf')
    assert client.post('/collector/free-source/run',data={'csrf':token},follow_redirects=False).status_code==303
    assert calls==[(1,True)]
    with Session(engine) as db:
        db.get(AppUser,1).role='viewer';db.commit()
    assert client.post('/collector/free-source/run',data={'csrf':token}).status_code==403
    assert calls==[(1,True)]
