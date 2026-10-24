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
