"""Bounded Coresignal acquisition; source profiles never imply availability or consent."""
from datetime import datetime
import os
import secrets
import threading
import time
from urllib.parse import urlparse
import httpx
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base, SessionLocal
from app.models import Worker, Tenant, AuditLog
from .worker_collector import canonical_country, canonical_role, SUPPORTED_COUNTRIES

API = 'https://api.coresignal.com/cdapi/v2/employee_multi_source'
TRADES = {'welder', 'pipefitter', 'metal fitter', 'mechanic', 'carpenter', 'mason', 'electrician', 'scaffolder'}
COUNTRIES = ['Lithuania', 'Latvia', 'Poland', 'Romania', 'Bulgaria', 'Spain', 'Italy']

class SourceRun(Base):
    __tablename__ = 'collector_source_runs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_key: Mapped[str] = mapped_column(String(120), unique=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id'), index=True)
    state: Mapped[str] = mapped_column(String(40), default='RUNNING')
    found: Mapped[int] = mapped_column(Integer, default=0)
    added: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    attempted: Mapped[int] = mapped_column(Integer, default=0)
    workers_before: Mapped[int] = mapped_column(Integer, default=0)
    workers_after: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str] = mapped_column(String(80), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class SourceProfile(Base):
    __tablename__ = 'collector_source_profiles'
    __table_args__ = (UniqueConstraint('tenant_id', 'source', 'source_id', name='uq_source_profile_identity'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id'), index=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey('workers.id'), index=True)
    source: Mapped[str] = mapped_column(String(60), default='coresignal')
    source_id: Mapped[str] = mapped_column(String(100))
    source_url: Mapped[str] = mapped_column(String(500), index=True)
    reported_title: Mapped[str] = mapped_column(String(200), default='')
    provider_updated_at: Mapped[str] = mapped_column(String(80), default='')
    verification_status: Mapped[str] = mapped_column(String(40), default='UNCONFIRMED')
    permission_basis: Mapped[str] = mapped_column(Text, default='Licensed professional data; recruitment review only; no outreach permission inferred')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


def query():
    words = ['welder', 'suvirintojas', 'spawacz', 'sudor', 'saldatore', 'soldador', 'pipefitter']
    return {'query': {'bool': {'filter': [{'terms': {'location_country': COUNTRIES}}],
              'must': [{'bool': {'should': [{'match_phrase': {'active_experience_title': word}} for word in words],
                                 'minimum_should_match': 1}}]}}}


def professional_values(profile):
    if not isinstance(profile, dict):
        raise ValueError('invalid_profile')
    name = str(profile.get('full_name') or '').strip()
    country = canonical_country(profile.get('location_country_iso2') or profile.get('location_country') or '')
    title = str(profile.get('active_experience_title') or profile.get('headline') or '').strip()
    role = canonical_role(title)
    url = str(profile.get('professional_network_url') or '').strip()
    parsed = urlparse(url)
    if not name or len(name) > 160 or country not in SUPPORTED_COUNTRIES or role not in TRADES:
        raise ValueError('profile_outside_scope')
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or len(url) > 500:
        raise ValueError('missing_source_url')
    languages = [str(x.get('language', '')) for x in profile.get('languages', []) if isinstance(x, dict)]
    certs = [str(x.get('title', '')) for x in profile.get('certifications', []) if isinstance(x, dict)]
    return {'full_name': name, 'country': country, 'profession': role,
            'city': str(profile.get('location_city') or '')[:120],
            'languages': ', '.join(languages)[:1000], 'certificates': ', '.join(certs)[:2000],
            # No contact details, citizenship, availability or consent inferred from a profile.
            'availability_status': 'UNKNOWN', 'eu_citizen': False,
            'years_experience': 0, 'ready_to_deploy': False,
            'identity_verified': False, 'documents_verified': False, 'skills_verified': False,
            'work_permit_notes': 'Sourced prospect; availability, citizenship, experience and contact permission unconfirmed. Source: ' + url}, url, title[:200]


def request(client, method, url, **kwargs):
    # Retrying a paid collection after an ambiguous timeout might spend credits twice.
    attempts = 3 if method == 'POST' else 1
    for attempt in range(attempts):
        response = client.request(method, url, **kwargs)
        if response.status_code not in (429, 502, 503, 504) or attempt == attempts - 1:
            response.raise_for_status()
            return response.json()
        time.sleep(2 ** attempt)


def acquire(db, tenant_id, run_key, limit=3, client=None):
    key = os.getenv('CORESIGNAL_API_KEY', '').strip()
    if not key:
        return {'state': 'NOT_CONFIGURED'}
    if db.get_bind().dialect.name == 'postgresql':
        # Commit the unique run reservation before any external paid call.
        db.execute(text('SELECT pg_advisory_xact_lock(64132971)'))
    if db.query(SourceRun).filter(SourceRun.run_key == run_key).first():
        db.rollback()
        return {'state': 'ALREADY_RUN'}
    if not db.get(Tenant, tenant_id):
        raise ValueError('workspace_not_found')
    limit = max(1, min(int(limit), 3))
    run = SourceRun(run_key=run_key, tenant_id=tenant_id,
                    workers_before=db.query(Worker).filter(Worker.tenant_id == tenant_id).count())
    db.add(run); db.commit(); db.refresh(run)
    run_id = run.id
    owned_client = client is None
    if owned_client:
        client = httpx.Client(headers={'apikey': key, 'accept': 'application/json'}, timeout=25, follow_redirects=False)
    try:
        ids = request(client, 'POST', API + '/search/es_dsl', params={'items_per_page': 20}, json=query())
        if not isinstance(ids, list) or any(not isinstance(x, int) or isinstance(x, bool) for x in ids):
            raise ValueError('unexpected_search_response')
        run.found = len(ids); db.commit()
        for source_id in ids:
            if run.attempted >= limit:
                break
            previous = db.query(SourceProfile).filter_by(tenant_id=tenant_id, source='coresignal', source_id=str(source_id)).first()
            if previous:
                run.duplicates += 1
                db.commit()
                continue
            run.attempted += 1; db.commit()
            try:
                data = request(client, 'GET', API + '/collect/' + str(source_id))
                values, url, title = professional_values(data)
                # Same source URL means same person; do not overwrite a registered profile.
                previous = db.query(SourceProfile).filter_by(tenant_id=tenant_id, source_url=url).first()
                if previous:
                    run.duplicates += 1; db.commit(); continue
                worker = Worker(tenant_id=tenant_id, **values, self_service_token=secrets.token_urlsafe(32))
                db.add(worker); db.flush()
                db.add(SourceProfile(tenant_id=tenant_id, worker_id=worker.id, source_id=str(source_id),
                                     source_url=url, reported_title=title, provider_updated_at=str(data.get('updated_at') or '')[:80]))
                db.add(AuditLog(tenant_id=tenant_id, actor='coresignal-collector', action='SOURCE_PROFILE_COLLECTED',
                               entity_type='worker', entity_id=str(worker.id), details=f'source=coresignal; source_id={source_id}; verification=UNCONFIRMED'))
                run.added += 1; db.commit()
            except (httpx.HTTPError, ValueError) as exc:
                db.rollback(); run = db.get(SourceRun, run_id)
                run.errors += 1
                code = f'HTTP_{exc.response.status_code}' if isinstance(exc, httpx.HTTPStatusError) else type(exc).__name__
                run.error_code = code; db.commit()
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (401, 402, 403, 429):
                    break
        run.state = 'COMPLETED' if not run.errors else ('DEGRADED' if run.added else 'FAILED')
    except Exception as exc:
        db.rollback(); run = db.get(SourceRun, run_id)
        run.state = 'FAILED'; run.errors += 1
        run.error_code = f'HTTP_{exc.response.status_code}' if isinstance(exc, httpx.HTTPStatusError) else type(exc).__name__
    finally:
        run.finished_at = datetime.utcnow()
        run.workers_after = db.query(Worker).filter(Worker.tenant_id == tenant_id).count()
        db.commit()
        if owned_client:
            client.close()
    return {'state': run.state, 'added': run.added, 'errors': run.errors}


def source_status(db, tenant_id):
    run = db.query(SourceRun).filter_by(tenant_id=tenant_id).order_by(SourceRun.id.desc()).first()
    if not run:
        return {'state': 'READY' if os.getenv('CORESIGNAL_API_KEY') else 'NOT_CONFIGURED', 'added': 0}
    duration = ((run.finished_at or datetime.utcnow()) - run.created_at).total_seconds()
    return {key: getattr(run, key) for key in ('state', 'found', 'added', 'duplicates', 'errors', 'attempted', 'workers_before', 'workers_after', 'error_code')} | {'seconds': round(duration, 2)}


def install(app):
    from app.db import get_db
    from fastapi import Depends
    @app.get('/collector/coresignal/status')
    def status(db=Depends(get_db)):
        # Operational totals only. No names, profile URLs, tokens or credentials.
        return source_status(db, int(os.getenv('WORKFORCE_ADMIN_TENANT_ID', '1')))

    @app.on_event('startup')
    def launch_trial():
        if not os.getenv('CORESIGNAL_API_KEY'):
            return
        def execute():
            with SessionLocal() as db:
                try:
                    acquire(db, int(os.getenv('WORKFORCE_ADMIN_TENANT_ID', '1')), 'initial-coresignal-trial-v1', 3)
                except Exception as exc:
                    print('CORESIGNAL_BOOTSTRAP_ERROR=' + type(exc).__name__)
        threading.Thread(target=execute, name='coresignal-initial-trial', daemon=True).start()
