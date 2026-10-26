"""Recruiter contract tests: locale persistence, permissions, drafts, dedupe and tenant isolation."""
from datetime import date
from urllib.parse import urlparse,parse_qs
import re
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.main import app,get_db
from app.db import Base
from app.models import Tenant,AppUser,Worker,Project,Consent
from app.services.auth import create_session_token
from collector.platform import ContactHistory,WorkerContact,UserPreference,international_number

@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv('INTAKE_FORM_SECRET','test-platform-secret-with-at-least-32-characters')
    engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    def session():
        with Session(engine) as db:yield db
    app.dependency_overrides[get_db]=session
    with Session(engine) as db:
        db.add_all([Tenant(id=1,name='Test'),Tenant(id=2,name='Other')]);db.flush()
        db.add(AppUser(id=1,tenant_id=1,email='qa@example.test',password_hash='no-login',role='admin'))
        db.add_all([Worker(id=1,tenant_id=1,full_name='QA Welder',country='LT',profession='Welder 135',skills='135',phone='+370 600 12345',preferred_channel='WhatsApp',email='qa-worker@example.test'),Worker(id=2,tenant_id=2,full_name='Other Tenant',country='PL',profession='welder'),Worker(id=3,tenant_id=1,full_name='Piotr Kowalski',country='PL',profession='welder',email='piotr@example.com')])
        db.add(Project(id=1,tenant_id=1,name='QA shipyard',country='NL',profession='welder',start_date=date.today(),salary_net_hour=21,rotation='6/2',status='ACTIVE'))
        db.add(Consent(worker_id=1,tenant_id=1,channel='WhatsApp',purpose='job_offers',granted=True));db.commit()
    client=TestClient(app);client.cookies.set('wl_session',create_session_token(1));client.cookies.set('et_language','en')
    yield client,engine
    app.dependency_overrides.pop(get_db,None);engine.dispose()

def hidden(text,key):return re.search(r'name="'+key+r'" value="([^"]+)"',text)[1]

def test_all_workspace_pages_and_segments_hide_demo_and_other_tenant(setup):
    client,engine=setup
    for path in ['/workers/export.csv','/','/workers','/matches','/sources','/settings','/workers/1/request','/workers/1/contact-history','/workers/1','/projects/1/edit']:
        r=client.get(path);assert r.status_code==200,(path,r.text)
        assert 'Other Tenant' not in r.text and 'Piotr Kowalski' not in r.text
    assert 'QA Welder' in client.get('/workers?segment=welder&process=135').text
    assert 'QA Welder' not in client.get('/workers?segment=carpenter').text
    assert 'QA Welder' in client.get('/workers?q=qa-worker%40example.test').text
    assert client.get('/workers/2/request').status_code==404

def test_whatsapp_draft_is_not_a_sent_message_and_deduplicates(setup):
    client,engine=setup
    page=client.get('/workers/1/request?job_id=1').text
    data={'csrf':hidden(page,'csrf'),'job_id':'1','nonce':hidden(page,'nonce')}
    prepared=client.post('/workers/1/request',data=data)
    assert prepared.status_code==200,prepared.text
    url=re.search(r'href="(https://wa.me/[^"]+)"',prepared.text)[1]
    message=parse_qs(urlparse(url).query)['text'][0]
    assert urlparse(url).path=='/37060012345'
    assert 'Hello QA,' in message and '€21.00/h net' in message and 'NL' in message
    assert client.post('/workers/1/request',data=data).status_code==200
    with Session(engine) as db:
        row=db.query(ContactHistory).one();cid=row.id
        assert row.status=='DRAFT_PREPARED'
        assert db.get(WorkerContact,1) is None
    result=client.post(f'/contacts/{cid}/confirm',data={'csrf':data['csrf']})
    assert result.status_code==200
    with Session(engine) as db:
        assert db.query(ContactHistory).one().status=='CONTACTED'
        assert db.get(WorkerContact,1).status=='Contacted'

def test_locales_persist_account_and_preserve_option_values(setup):
    client,engine=setup
    client.get('/language/lt?next=/workers')
    page=client.get('/workers').text
    assert '<html lang="lt">' in page and 'Siųsti darbo pasiūlymą' in page
    assert 'value="AVAILABLE NOW"' in page and 'GALI DIRBTI DABAR' in page
    request=client.get('/workers/1/request?job_id=1').text
    assert 'Sveiki, QA,' in request
    with Session(engine) as db:assert db.get(UserPreference,1).language=='lt'
    client.get('/language/en?next=/workers')
    assert 'Send Job Request' in client.get('/workers').text
    assert client.get('/language/lt?next=//evil.example',follow_redirects=False).headers['location']=='/'

def test_csrf_and_latest_revocation_block_outreach(setup):
    client,engine=setup
    assert client.post('/workers/1/request',data={'job_id':'1'}).status_code==403
    with Session(engine) as db:
        db.add(Consent(worker_id=1,tenant_id=1,channel='WhatsApp',purpose='job_offers',granted=False));db.commit()
    page=client.get('/workers/1/request?job_id=1').text
    assert 'WhatsApp job-offer permission is required' in page
    from collector.platform import csrf
    from starlette.requests import Request
    # Reuse a valid form token from contact settings, since the offer form is blocked.
    token=hidden(client.get('/workers/1/contact-history').text,'csrf')
    assert client.post('/workers/1/request',data={'job_id':'1','csrf':token,'nonce':'testnonce0000000000000000'}).status_code==403

def test_job_edit_persists_and_normalizes_numbers(setup):
    client,engine=setup
    page=client.get('/projects/1/edit').text
    fields={'csrf':hidden(page,'csrf'),'name':'Edited job','country':'FI','profession':'welder','start_date':date.today().isoformat(),'workers_needed':'2','weekly_hours':'50','duration_weeks':'8','salary_net_hour':'22','status':'ACTIVE'}
    r=client.post('/projects/1/edit',data=fields,follow_redirects=False);assert r.status_code==303
    with Session(engine) as db:assert db.get(Project,1).country=='FI'
    assert international_number('00370 600 12345')=='+37060012345'
    assert international_number('60012345')==''

def test_new_job_form_saves_and_matches_without_sending(setup):
    client,engine=setup
    page=client.get('/projects/new').text
    token=hidden(page,'csrf')
    data={'csrf':token,'name':'New matching job','country':'LT','profession':'Welder 135','start_date':date.today().isoformat(),'salary_net_hour':'21','citizenship_requirement':'Any','workers_needed':'1','duration_weeks':'8','weekly_hours':'40'}
    r=client.post('/projects/new',data=data,follow_redirects=False)
    assert r.status_code==303,r.text
    from app.models import ProjectCandidate,Message
    with Session(engine) as db:
        job=db.query(Project).filter(Project.name=='New matching job').one()
        assert db.query(ProjectCandidate).filter(ProjectCandidate.project_id==job.id).count()==1
        assert db.query(Message).count()==0

def test_unconfigured_provider_never_reports_sent():
    from app.services.messaging import DemoMessagingProvider
    result=DemoMessagingProvider().send('WhatsApp','+37060012345','test')
    assert not result.status.startswith('SENT')

def test_draft_scope_and_xss_are_not_loosened_by_translation(setup):
    client,engine=setup
    with Session(engine) as db:
        w=db.get(Worker,1);w.full_name='<img src=x onerror=alert(1)>';db.commit()
    client.get('/language/lt?next=/workers')
    page=client.get('/workers').text
    assert '&lt;img src=x onerror=alert(1)&gt;' in page
    assert '<img src=x onerror=alert(1)>' not in page
    assert client.get('/workers/2/contact-history').status_code==404

def test_mobile_qa_frame_is_admin_only_and_limited(setup):
    client,engine=setup
    r=client.get('/qa/responsive?width=390&surface=workers');assert r.status_code==200
    assert 'width="390"' in r.text and 'src="/workers"' in r.text
    assert client.get('/qa/responsive?surface=//example.test').status_code==400
    with Session(engine) as db:
        user=db.get(AppUser,1);user.role='viewer';db.commit()
    assert client.get('/qa/responsive').status_code==403

def test_multiple_jobs_require_selection_and_use_selected_offer(setup):
    client,engine=setup
    with Session(engine) as db:
        db.add(Project(id=2,tenant_id=1,name='QA Finland',country='FI',profession='mechanic',start_date=date.today(),salary_net_hour=25,status='ACTIVE'));db.commit()
    page=client.get('/workers/1/request').text
    assert 'QA shipyard' in page and 'QA Finland' in page
    assert 'Prepare WhatsApp message' not in page
    selected=client.get('/workers/1/request?job_id=2').text
    result=client.post('/workers/1/request',data={'csrf':hidden(selected,'csrf'),'nonce':hidden(selected,'nonce'),'job_id':'2'})
    url=re.search(r'href="(https://wa.me/[^"]+)"',result.text)[1]
    message=parse_qs(urlparse(url).query)['text'][0]
    assert 'mechanic' in message and 'FI' in message and '€25.00' in message
    assert '€21.00' not in message

def test_account_language_is_restored_in_a_fresh_browser(setup,monkeypatch):
    client,engine=setup
    import collector.localization as localization
    monkeypatch.setattr(localization,'SessionLocal',lambda:Session(engine))
    client.get('/language/lt?next=/settings')
    client.cookies.delete('et_language')
    response=client.get('/settings')
    assert '<html lang="lt">' in response.text
    assert 'Nustatymai' in response.text

def test_unknown_fields_do_not_invent_compatibility_or_interest(setup):
    client,engine=setup
    from collector.matching import score,completeness
    with Session(engine) as db:
        worker=db.get(Worker,1);job=db.get(Project,1)
        result=score(worker,job)
        assert result['eligible'] is False
        assert 'availability not confirmed' in result['hard_failures']
        assert 'Salary compatible' not in result['reasons']
        assert 'Country preference matches' not in result['reasons']
        assert result['interest_probability']==0 and result['arrival_probability']==0
        assert completeness(worker)>0
    page=client.get('/projects/1').text
    assert 'Interest 99' not in page and 'Arrival' not in page
    assert 'Matching uses supplied information' in page

def test_candidate_can_opt_in_to_whatsapp_with_email_present(setup):
    client,engine=setup
    from collector.intake import collect
    from collector.platform import consent_allowed,whatsapp_number
    with Session(engine) as db:
        result=collect(db,dict(full_name='QA explicit WhatsApp applicant',country='LT',profession='welder',phone='+37060056789',email='wa-test@example.test'),nonce='qa-whatsapp-explicit-consent',tenant_id=1,offer_permission=False,whatsapp_permission=True)
        worker=db.get(Worker,result['worker_id'])
        assert worker.preferred_channel=='WhatsApp'
        assert whatsapp_number(worker)=='+37060056789'
        assert consent_allowed(db,worker.id)
        assert db.query(Consent).filter(Consent.worker_id==worker.id,Consent.channel=='Email').count()==0

def test_email_permission_does_not_become_whatsapp_permission(setup):
    client,engine=setup
    from collector.intake import collect
    from collector.platform import consent_allowed
    with Session(engine) as db:
        result=collect(db,dict(full_name='QA email applicant',country='LT',profession='welder',phone='+37060056780',email='email-test@example.test'),nonce='qa-email-only-consent',tenant_id=1,offer_permission=True,whatsapp_permission=False)
        assert not consent_allowed(db,result['worker_id'])


def test_recruitment_export_admin_csrf_and_tenant_isolation(setup):
    client,engine=setup
    assert client.post('/settings/export').status_code==403
    token=hidden(client.get('/settings').text,'csrf')
    r=client.post('/settings/export',data={'csrf':token})
    assert r.status_code==200 and r.headers['cache-control']=='no-store, private'
    data=r.json()
    assert data['counts']['workers']==1
    assert data['data']['workers'][0]['full_name']=='QA Welder'
    assert 'self_service_token' not in data['data']['workers'][0]
    assert 'Other Tenant' not in r.text and 'Piotr Kowalski' not in r.text
    assert 'password_hash' not in r.text
    with Session(engine) as db:
        db.get(AppUser,1).role='recruiter';db.commit()
    assert client.post('/settings/export',data={'csrf':token}).status_code==403
    assert 'Download recruitment data' not in client.get('/settings').text


def test_csv_export_neutralises_formulas_and_preserves_json_original(setup):
    import csv,io
    client,engine=setup
    with Session(engine) as db:
        db.get(Worker,1).full_name='=HYPERLINK("https://invalid.test")';db.commit()
    r=client.get('/workers/export.csv')
    assert r.status_code==200 and r.headers['cache-control']=='no-store, private'
    row=list(csv.DictReader(io.StringIO(r.text)))[0]
    assert row['full_name'].startswith("'=")
    assert row['phone'].startswith("'+")
    token=hidden(client.get('/settings').text,'csrf')
    assert client.post('/settings/export',data={'csrf':token}).json()['data']['workers'][0]['full_name'].startswith('=')


def test_stated_country_limits_block_foreign_jobs_and_notes_are_visible(setup):
    client,engine=setup
    from collector.matching import score
    with Session(engine) as db:
        worker=db.get(Worker,1);job=db.get(Project,1)
        worker.preferred_countries='PL; LT'
        worker.work_permit_notes='Local jobs only <script>alert(1)</script>'
        db.commit()
        result=score(worker,job)
        assert 'project country outside stated preferences' in result['hard_failures']
        assert not result['eligible']
        job.country='LT'
        result=score(worker,job)
        assert 'project country outside stated preferences' not in result['hard_failures']
        assert 'Country preference matches' in result['reasons']
    page=client.get('/workers/1').text
    assert 'tel:+37060012345' in page
    assert 'Local jobs only &lt;script&gt;' in page
    assert '<script>alert(1)</script>' not in page
