import re
from urllib.parse import urlparse,parse_qs,unquote
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from test_platform_flow import setup,hidden
from app.models import Worker,Consent
from collector.platform import ContactHistory


def test_email_fallback_requires_current_permission_and_prepares_correct_message(setup):
    client,engine=setup
    with Session(engine) as db:
        w=db.get(Worker,1);w.phone='';w.preferred_channel='Email';db.commit()
    page=client.get('/workers/1/request?job_id=1').text
    assert 'Email job-offer permission is required' in page
    with Session(engine) as db:db.add(Consent(tenant_id=1,worker_id=1,channel='Email',purpose='job_offers',granted=True));db.commit()
    page=client.get('/workers/1/request?job_id=1').text
    r=client.post('/workers/1/request',data={'csrf':hidden(page,'csrf'),'job_id':'1','nonce':hidden(page,'nonce'),'channel':'Email'})
    link=BeautifulSoup(r.text,'html.parser').find('a',href=re.compile('^mailto:'))['href']
    parts=urlparse(link);payload=parse_qs(parts.query)
    assert parts.path=='qa-worker@example.test'
    assert 'QA shipyard' in payload['subject'][0]
    assert 'Working hours per week: 50' in payload['body'][0] and '/offer/' in payload['body'][0]
    with Session(engine) as db:
        h=db.query(ContactHistory).one();assert h.channel=='Email' and h.status=='DRAFT_PREPARED';cid=h.id
    client.post(f'/contacts/{cid}/confirm',data={'csrf':hidden(page,'csrf')})
    assert 'Already contacted' in client.get('/workers/1/request?job_id=1').text
    with Session(engine) as db:
        db.add(Consent(tenant_id=1,worker_id=1,channel='Email',purpose='job_offers',granted=False));db.commit()
    assert client.post('/workers/1/request',data={'csrf':hidden(page,'csrf'),'job_id':'1','nonce':hidden(page,'nonce'),'channel':'Email'}).status_code==403


def test_daily_target_excludes_demo_ads_and_snapshots_previous_day(setup):
    from collector.acquisition_metrics import daily_metrics,save_previous_day,DailyAcquisitionReport
    client,engine=setup
    with Session(engine) as db:
        daily=daily_metrics(db,1)
        assert daily['unique_added']==0 and daily['search_contacts_added']==1 and daily['target']==300
        assert daily['new_email']==0 and daily['ads_included'] is False
        save_previous_day(db,1);save_previous_day(db,1)
        assert db.query(DailyAcquisitionReport).count()==1
    assert '0 / 300' in client.get('/').text


def test_old_confirmed_offer_blocks_cross_channel_even_with_newer_draft(setup):
    from datetime import datetime,timedelta
    client,engine=setup
    with Session(engine) as db:
        db.add_all([ContactHistory(tenant_id=1,worker_id=1,project_id=1,actor_id=1,nonce='confirmedoldnonce1234567890',channel='Email',status='CONTACTED',created_at=datetime.utcnow()-timedelta(days=7)),ContactHistory(tenant_id=1,worker_id=1,project_id=1,actor_id=1,nonce='newdraftnonce12345678901234',channel='WhatsApp')]);db.commit()
    page=client.get('/workers/1/request?job_id=1').text
    assert 'Already contacted' in page
    csrf=hidden(client.get('/workers/1/contact-history').text,'csrf')
    r=client.post('/workers/1/request',data={'csrf':csrf,'job_id':'1','nonce':'othernonce1234567890123456','channel':'WhatsApp'})
    assert 'Already contacted' in r.text
    assert 'href="https://wa.me/' not in r.text
    with Session(engine) as db:assert db.query(ContactHistory).count()==2
