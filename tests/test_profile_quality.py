from datetime import date,timedelta
from sqlalchemy.orm import Session
from test_platform_flow import setup,hidden
from app.models import Worker,Consent,AuditLog
from collector.profile_quality import profile_ready,missing_fields
from collector.acquisition_metrics import daily_metrics


def data(name='Real Candidate'):
    return dict(full_name=name,phone='+37060012345',email='qa-worker@example.test',country='LT',profession='welder',skills='135 welding',languages='English',certificates='',preferred_countries='NL',preferred_rotation='6/2',years_experience='5',availability_status='AVAILABLE NOW',available_from='',confirmed='yes')


def test_incomplete_records_separate_from_candidates_and_daily_target(setup):
    client,engine=setup
    assert 'QA Welder' not in client.get('/workers').text
    assert 'QA Welder' in client.get('/workers?stage=prospects').text
    assert 'QA Welder' in client.get('/workers?stage=all').text
    with Session(engine) as db:
        assert not profile_ready(db.get(Worker,1))
        assert daily_metrics(db,1)['unique_added']==0
    assert client.get('/workers?stage=invalid').status_code==400


def test_recruiter_completion_is_scoped_csrf_protected_and_does_not_verify_identity(setup):
    client,engine=setup
    assert client.get('/workers/2/profile').status_code==404
    assert client.post('/workers/1/profile',data=data()).status_code==403
    page=client.get('/workers/1/profile').text
    result=client.post('/workers/1/profile',data=dict(data(),csrf=hidden(page,'csrf')),follow_redirects=False)
    assert result.status_code==303,result.text
    with Session(engine) as db:
        worker=db.get(Worker,1)
        assert profile_ready(worker)
        assert not worker.identity_verified and not worker.documents_verified and not worker.skills_verified and not worker.ready_to_deploy
        assert db.query(AuditLog).filter_by(action='PROFILE_COMPLETED').count()==1
        assert daily_metrics(db,1)['unique_added']==1
    assert 'Real Candidate' in client.get('/workers').text
    assert 'Real Candidate' not in client.get('/workers?stage=prospects').text


def test_private_form_rejects_missing_or_wrong_csrf_and_only_saves_explicit_consent(setup):
    client,engine=setup
    token='private-profile-key-abcdefghijklmnopqrstuvwxyz12345'
    with Session(engine) as db:
        db.get(Worker,1).self_service_token=token;db.commit()
        before=db.query(Consent).count()
    url='/worker/'+token+'/profile'
    assert client.post(url,data=data()).status_code==403
    page=client.get(url)
    assert page.headers['cache-control']=='no-store, private'
    payload=dict(data(),csrf=hidden(page.text,'csrf'))
    result=client.post(url,data=payload)
    assert result.status_code==200,result.text
    with Session(engine) as db:
        assert db.query(Consent).count()==before
        assert profile_ready(db.get(Worker,1))
    page=client.get(url)
    assert client.post(url,data=dict(payload,csrf=hidden(page.text,'csrf'),email_offers='yes')).status_code==200
    with Session(engine) as db:
        assert db.query(Consent).filter_by(worker_id=1,channel='Email',source='worker_profile_completion',granted=True).count()==1
        worker=db.get(Worker,1);worker.identity_verified=True;db.commit()
    assert client.get(url).status_code==403


def test_aliases_stale_availability_and_missing_preferences_are_not_ready(setup):
    _,engine=setup
    with Session(engine) as db:
        w=db.get(Worker,1)
        for key,val in data().items():
            if hasattr(w,key):setattr(w,key,int(val) if key=='years_experience' else val if key!='available_from' else None)
        w.last_availability_confirmed=date.today()
        assert profile_ready(w)
        w.full_name='Vardas nepateiktas · PL-123';assert 'Full name' in missing_fields(w)
        w.full_name='Real Candidate';w.last_availability_confirmed=date.today()-timedelta(days=31)
        assert 'Recent availability confirmation' in missing_fields(w)


def test_first_qualification_counts_today_even_for_older_contacts_and_never_counts_twice(setup):
    from datetime import datetime
    client,engine=setup
    with Session(engine) as db:
        db.get(Worker,1).created_at=datetime.utcnow()-timedelta(days=5);db.commit()
    page=client.get('/workers/1/profile').text
    payload=dict(data(),csrf=hidden(page,'csrf'))
    assert client.post('/workers/1/profile',data=payload).status_code==200
    page=client.get('/workers/1/profile').text
    assert client.post('/workers/1/profile',data=dict(data(),csrf=hidden(page,'csrf'))).status_code==200
    with Session(engine) as db:
        assert daily_metrics(db,1)['unique_added']==1
        assert db.query(AuditLog).filter_by(action='PROFILE_QUALIFIED').count()==1
        from app.models import ProjectCandidate
        assert db.query(ProjectCandidate).filter_by(worker_id=1,project_id=1).count()==1
