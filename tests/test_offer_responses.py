import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from test_platform_flow import setup,hidden
from sqlalchemy.orm import Session
from collector.platform import ContactHistory
from collector.offer_responses import OfferResponse
from app.models import ProjectCandidate,Project


def prepare(client):
    page=client.get('/workers/1/request?job_id=1').text
    r=client.post('/workers/1/request',data={'csrf':hidden(page,'csrf'),'job_id':'1','nonce':hidden(page,'nonce')})
    soup=BeautifulSoup(r.text,'html.parser')
    body=soup.select_one('.offer-preview').text
    return urlparse(re.search(r'https?://[^\s]+/offer/[^\s]+',body)[0]).path


def test_interest_response_is_scoped_private_and_viewing_has_no_side_effect(setup):
    client,engine=setup
    path=prepare(client)
    page=client.get(path)
    assert page.status_code==200 and page.headers['referrer-policy']=='no-referrer'
    assert 'qa-worker@example.test' not in page.text
    with Session(engine) as db:
        assert db.query(OfferResponse).count()==0
        assert db.query(ContactHistory).one().status=='DRAFT_PREPARED'
    assert client.post(path,data={'answer':'INTERESTED'}).status_code==403
    token=hidden(page.text,'form_token')
    r=client.post(path,data={'answer':'INTERESTED','form_token':token,'note':'I can start next week'})
    assert r.status_code==200 and 'Your answer was received' in r.text
    assert 'I can start next week' in client.get('/responses').text
    with Session(engine) as db:
        assert db.query(OfferResponse).one().answer=='INTERESTED'
        assert db.query(ContactHistory).one().status=='DRAFT_PREPARED'
    # The same link updates one response; it never creates duplicate interest.
    token=hidden(r.text,'form_token')
    assert client.post(path,data={'answer':'NOT_INTERESTED','form_token':token}).status_code==200
    with Session(engine) as db:
        assert db.query(OfferResponse).count()==1
        assert db.query(OfferResponse).one().answer=='NOT_INTERESTED'
    assert client.get(path+'tampered').status_code==404
    with Session(engine) as db:db.get(Project,1).status='CLOSED';db.commit()
    page=client.get(path)
    assert 'This job is closed' in page.text
    assert client.post(path,data={'answer':'INTERESTED','form_token':hidden(page.text,'form_token') if 'name="form_token"' in page.text else token}).status_code in (403,409)


def test_reply_inbox_hides_other_tenant_and_late_send_confirmation_keeps_interest(setup):
    from app.models import AppUser
    from app.services.auth import create_session_token
    client,engine=setup
    with Session(engine) as db:
        db.add(ProjectCandidate(project_id=1,worker_id=1));db.commit()
    path=prepare(client);page=client.get(path)
    client.post(path,data={'answer':'INTERESTED','form_token':hidden(page.text,'form_token'),'note':'Reply visible only to my recruiter'})
    csrf=hidden(client.get('/workers/1/contact-history').text,'csrf')
    with Session(engine) as db:cid=db.query(ContactHistory).one().id
    client.post(f'/contacts/{cid}/confirm',data={'csrf':csrf})
    with Session(engine) as db:
        assert db.query(ProjectCandidate).one().stage=='INTERESTED'
        db.add(AppUser(id=2,tenant_id=2,email='other@example.test',password_hash='unused',role='admin'));db.commit()
    assert 'QA Welder' in client.get('/workers?status=Interested').text
    client.cookies.set('wl_session',create_session_token(2))
    assert 'Reply visible only to my recruiter' not in client.get('/responses').text
    client.cookies.clear()
    assert client.get('/responses',follow_redirects=False).status_code==303


def test_registration_to_matching_to_interest_is_one_working_flow(setup):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.models import Worker,Consent,Message,AuditLog
    from test_built_app_smoke import registration_form
    from urllib.parse import parse_qs
    from collector.profile_quality import profile_ready
    recruiter,engine=setup
    applicant=TestClient(app)
    applicant.cookies.set('et_language','en')
    r=applicant.post('/join',data=registration_form(applicant,country='NO',preferred_countries='Germany',email='full-flow@example.test',phone='+4791234567',whatsapp_offers='yes'),follow_redirects=False)
    assert r.status_code==303,r.text
    with Session(engine) as db:
        worker=db.query(Worker).filter_by(email='full-flow@example.test').one();wid=worker.id
        assert profile_ready(worker) and worker.country=='NO'
        assert db.query(ProjectCandidate).filter_by(worker_id=wid,project_id=1).one().eligibility=='REVIEW'
    receipt=applicant.get('/join/received')
    profile=BeautifulSoup(receipt.text,'html.parser').select_one('a[href$="/profile"]')['href']
    page=applicant.get(profile)
    fields={'csrf':hidden(page.text,'csrf'),'full_name':'QA Test Applicant','phone':'+4791234567','email':'full-flow@example.test','country':'NO','profession':'welder','skills':'MIG/MAG','languages':'English','certificates':'','preferred_countries':'NL','preferred_rotation':'6/2','years_experience':'6','availability_status':'AVAILABLE NOW','available_from':'','confirmed':'yes'}
    assert applicant.post(profile,data=fields).status_code==200
    with Session(engine) as db:
        assert db.query(ProjectCandidate).filter_by(worker_id=wid,project_id=1).one().eligibility=='PASS'
        assert db.query(AuditLog).filter_by(entity_type='worker',entity_id=str(wid),action='PROFILE_QUALIFIED').count()==1
        assert db.query(Consent).filter_by(worker_id=wid,channel='Email').count()==0
    page=recruiter.get(f'/workers/{wid}/request?job_id=1').text
    prepared=recruiter.post(f'/workers/{wid}/request',data={'csrf':hidden(page,'csrf'),'nonce':hidden(page,'nonce'),'job_id':'1'})
    assert prepared.status_code==200,prepared.text
    wa=BeautifulSoup(prepared.text,'html.parser').select_one('a[href^="https://wa.me/"]')['href']
    message=parse_qs(urlparse(wa).query)['text'][0]
    offer=urlparse(re.search(r'https?://[^\s]+/offer/[^\s]+',message)[0]).path
    page=applicant.get(offer)
    result=applicant.post(offer,data={'form_token':hidden(page.text,'form_token'),'answer':'INTERESTED','note':'I am interested in this project; please contact me'})
    assert result.status_code==200
    assert 'I am interested in this project; please contact me' in recruiter.get('/responses').text
    with Session(engine) as db:
        assert db.query(OfferResponse).filter_by(worker_id=wid).one().answer=='INTERESTED'
        assert db.query(ProjectCandidate).filter_by(worker_id=wid,project_id=1).one().stage=='INTERESTED'
        assert db.query(ContactHistory).filter_by(worker_id=wid).one().status=='DRAFT_PREPARED'
        assert db.query(Message).count()==0
