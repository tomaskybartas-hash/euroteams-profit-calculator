from fastapi.testclient import TestClient
from app.main import app


def test_collector_health_and_login_surface():
    client=TestClient(app)
    health=client.get('/collector/health')
    assert health.status_code==200
    payload=health.json()
    assert payload['ok'] is True
    assert payload['module']=='worker-collector-v1'
    assert 'euroteams-existing' in payload['enabled_sources']
    login=client.get('/login')
    assert login.status_code==200
    assert 'Euroteams' in login.text
    protected=client.get('/collector',follow_redirects=False)
    assert protected.status_code in (302,303,307)
    assert '/login' in protected.headers.get('location','')


def test_collector_uses_real_salary_language_and_worker_portal_fields():
    from datetime import date
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.db import Base
    from app.models import Tenant, Worker, Project, ProjectCandidate
    from collector.worker_collector import CandidateRecord
    from collector.workforce_bridge import upsert_workers, create_project_candidates

    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        tenant = Tenant(name='Collector integration test')
        db.add(tenant)
        db.flush()
        project = Project(tenant_id=tenant.id, name='Welder test', country='NL',
                          profession='welder', start_date=date.today(),
                          salary_net_hour=20, required_language='English',
                          citizenship_requirement='EU')
        db.add(project)
        db.commit()
        record = CandidateRecord('Test Worker', 'LT', 'welder', 'test',
                                 email='collector-test@example.com', eu_citizen=True,
                                 availability_status='ASAP', languages=['Polish'],
                                 desired_net_hourly=25)
        worker = upsert_workers(db, Worker, [record], tenant.id)['workers'][0]
        assert worker.expected_salary_net_hour == 25
        assert len(worker.self_service_token) >= 32
        result = create_project_candidates(db, ProjectCandidate, project,
                                          {record.fingerprint: worker}, [record], tenant.id)
        assert result['blocked'] == 1
        candidate = db.query(ProjectCandidate).one()
        assert 'rate above offer' in candidate.notes
        assert 'required language not confirmed' in candidate.notes
        # The same persisted values are used on a later rematch.
        assert worker.expected_salary_net_hour > project.salary_net_hour


def test_unknown_citizenship_does_not_become_confirmed_eu_on_import():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.db import Base
    from app.models import Tenant, Worker
    from collector.worker_collector import CandidateRecord
    from collector.workforce_bridge import upsert_workers

    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        tenant = Tenant(name='Unknown citizenship test')
        db.add(tenant)
        db.commit()
        record = CandidateRecord('Test Unknown', 'LT', 'welder', 'test',
                                 phone='+37060000000', eu_citizen=None)
        worker = upsert_workers(db, Worker, [record], tenant.id)['workers'][0]
        assert worker.eu_citizen is False
        assert worker.email == ''


def test_readiness_rejects_temporary_database():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool
    from app.main import get_db
    engine = create_engine('sqlite:///:memory:', poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    def temporary_db():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = temporary_db
    try:
        response = TestClient(app).get('/collector/ready')
        assert response.status_code == 503
        assert response.json() == {"ok": False, "database": "connected", "persistent": False}
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_readiness_does_not_expose_database_connection_errors():
    from app.main import get_db
    class FailedDatabase:
        def execute(self, statement):
            raise RuntimeError("private database connection details")
        def rollback(self):
            pass
    def unavailable_db():
        yield FailedDatabase()
    app.dependency_overrides[get_db] = unavailable_db
    try:
        response = TestClient(app).get('/collector/ready')
        assert response.status_code == 503
        assert response.json()["database"] == "unavailable"
        assert "private" not in response.text
    finally:
        app.dependency_overrides.pop(get_db, None)

import pytest

@pytest.fixture
def intake_client(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool
    from app.db import Base
    from app.main import get_db
    from app.models import Tenant, Project
    from datetime import date
    monkeypatch.setenv('INTAKE_FORM_SECRET', 'local-test-secret-only-' * 3)
    monkeypatch.setenv('WORKFORCE_ADMIN_TENANT_ID', '1')
    engine = create_engine('sqlite:///:memory:', poolclass=StaticPool, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Tenant(id=1, name='Euroteams test'))
        db.add(Project(tenant_id=1, name='QA welder job', country='NL', profession='welder', start_date=date.today(), salary_net_hour=22, required_language='English', required_certificates='VCA', citizenship_requirement='EU', status='ACTIVE'))
        db.commit()
    def isolated_db():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = isolated_db
    try:
        yield TestClient(app, base_url='https://testserver'), engine
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def registration_form(client, **changes):
    import re
    page = client.get('/join')
    assert page.status_code == 200
    token = re.search(r'name="token" value="([^"]+)"', page.text).group(1)
    values = {'token': token, 'full_name': 'QA Test Applicant', 'country': 'LT', 'profession': 'welder', 'email': 'qa-applicant@example.com', 'phone': '+37060000001', 'privacy': 'yes', 'eu_citizen': 'yes', 'availability': 'AVAILABLE NOW', 'years_experience': '6', 'certificates': 'VCA', 'languages': 'English', 'salary': '21'}
    values.update(changes)
    return values


def test_registration_persists_provenance_and_automatically_matches(intake_client):
    from sqlalchemy.orm import Session
    from app.models import Worker, ProjectCandidate, Consent
    from collector.intake import CandidateIntake
    client, engine = intake_client
    response = client.post('/join', data=registration_form(client, offers='yes'), follow_redirects=False)
    assert response.status_code == 303
    with Session(engine) as db:
        worker = db.query(Worker).one()
        assert worker.ready_to_deploy is False and worker.identity_verified is False
        assert len(worker.self_service_token) >= 32
        intake = db.query(CandidateIntake).one()
        assert intake.source == 'euroteams-portal' and intake.worker_id == worker.id
        assert intake.privacy_version == 'candidate-intake-v1'
        assert db.query(Consent).one().granted is True
        assert db.query(ProjectCandidate).one().eligibility == 'PASS'
        assert worker.self_service_token not in response.text


def test_repeat_application_cannot_overwrite_existing_profile(intake_client):
    from sqlalchemy.orm import Session
    from app.models import Worker
    from collector.intake import CandidateIntake
    client, engine = intake_client
    client.post('/join', data=registration_form(client))
    response = client.post('/join', data=registration_form(client, full_name='Changed Name', salary='1'))
    assert response.status_code == 200
    with Session(engine) as db:
        assert db.query(Worker).count() == 1
        worker = db.query(Worker).one()
        assert worker.full_name == 'QA Test Applicant' and worker.expected_salary_net_hour == 21
        assert db.query(CandidateIntake).filter_by(status='DUPLICATE').count() == 1
        assert worker.self_service_token not in response.text


def test_registration_requires_csrf_privacy_and_contact(intake_client):
    from sqlalchemy.orm import Session
    from app.models import Worker
    client, engine = intake_client
    assert client.post('/join', data={'full_name': 'forged'}).status_code == 403
    for changes in [{'privacy': ''}, {'email': '', 'phone': ''}, {'salary': 'nan'}, {'email': 'invalid'}]:
        assert client.post('/join', data=registration_form(client, **changes)).status_code == 422
    with Session(engine) as db:
        assert db.query(Worker).count() == 0


def test_registration_outreach_is_opt_in(intake_client):
    from sqlalchemy.orm import Session
    from app.models import Consent, Worker
    client, engine = intake_client
    client.post('/join', data=registration_form(client, eu_citizen='unknown'))
    with Session(engine) as db:
        assert db.query(Consent).count() == 0
        assert db.query(Worker).one().eu_citizen is False


def test_registration_limits_body_size_and_honeypot(intake_client):
    from sqlalchemy.orm import Session
    from app.models import Worker
    client, engine = intake_client
    response = client.post('/join', content='a=' + 'x' * 32_001, headers={'content-type': 'application/x-www-form-urlencoded'})
    assert response.status_code == 413
    assert client.post('/join', data=registration_form(client, website='bot.invalid')).status_code == 200
    with Session(engine) as db:
        assert db.query(Worker).count() == 0
