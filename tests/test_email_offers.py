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
        assert daily['unique_added']==1 and daily['target']==300
        assert daily['new_email']==1 and daily['ads_included'] is False
        save_previous_day(db,1);save_previous_day(db,1)
        assert db.query(DailyAcquisitionReport).count()==1
    assert '1 / 300' in client.get('/').text
