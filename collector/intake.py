"""First-party candidate acquisition. Public input never updates an existing worker."""
from datetime import date, datetime, timedelta
from pathlib import Path
import math
import os
import re
import secrets
from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer, BadData
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, Session
from app.db import Base, get_db
from app.models import Tenant, Worker, Project, ProjectCandidate, Consent, AuditLog
from .worker_collector import CandidateRecord, canonical_country, canonical_role, normalize_phone, SUPPORTED_COUNTRIES
from .workforce_bridge import create_project_candidates

PRIVACY_VERSION = 'candidate-intake-v1'
ROLES = {'welder', 'pipefitter', 'metal fitter', 'mechanic', 'carpenter', 'mason', 'electrician', 'scaffolder', 'general labour', 'other'}

class CandidateIntake(Base):
    __tablename__ = 'collector_intakes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id'), index=True)
    worker_id: Mapped[int | None] = mapped_column(ForeignKey('workers.id'), nullable=True, index=True)
    nonce: Mapped[str] = mapped_column(String(80), unique=True)
    request_key: Mapped[str] = mapped_column(String(80), default='', index=True)
    source: Mapped[str] = mapped_column(String(80), default='euroteams-portal', index=True)
    source_url: Mapped[str] = mapped_column(String(200), default='/join')
    status: Mapped[str] = mapped_column(String(40), index=True)
    privacy_version: Mapped[str] = mapped_column(String(60), default=PRIVACY_VERSION)
    permission_basis: Mapped[str] = mapped_column(Text, default='Candidate request to be considered for recruitment')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


def signer():
    secret = os.getenv('INTAKE_FORM_SECRET', '')
    if len(secret) < 32:
        raise HTTPException(503, 'Candidate registration is not configured yet')
    return URLSafeTimedSerializer(secret, salt='euroteams-candidate-intake-v1')


def validate_input(form):
    def value(key, limit=200):
        text = str(form.get(key, '')).strip()
        if len(text) > limit:
            raise ValueError(f'{key}: value is too long')
        return text
    name = value('full_name', 160)
    email = value('email', 160).lower()
    phone = normalize_phone(value('phone', 60))
    country = canonical_country(value('country', 80))
    role = canonical_role(value('profession', 120))
    if len(name) < 3 or country not in SUPPORTED_COUNTRIES or role not in ROLES:
        raise ValueError('Enter your full name, country and profession')
    if not email and not phone:
        raise ValueError('Enter an email address or phone number')
    if email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise ValueError('Enter a valid email address')
    if phone and not re.fullmatch(r'\+?[0-9]{8,15}', phone):
        raise ValueError('Enter a valid phone number including country code')
    if value('privacy') != 'yes':
        raise ValueError('Please acknowledge the privacy notice')
    years = int(value('years_experience') or '0')
    salary = float(value('salary').replace(',', '.') or '0')
    if not 0 <= years <= 70 or not math.isfinite(salary) or not 0 <= salary <= 300:
        raise ValueError('Check experience and expected hourly pay')
    availability = value('availability')
    if availability not in {'AVAILABLE NOW', 'AVAILABLE FROM DATE', 'OPEN TO OFFERS'}:
        raise ValueError('Select your availability')
    available_from = date.fromisoformat(value('available_from')) if value('available_from') else None
    if availability == 'AVAILABLE FROM DATE' and not available_from:
        raise ValueError('Select the date you can start')
    return dict(full_name=name, email=email, phone=phone, country=country,
                profession=role, years_experience=years, expected_salary_net_hour=salary,
                availability_status=availability, available_from=available_from,
                eu_citizen=value('eu_citizen') == 'yes',
                certificates=value('certificates', 2000), languages=value('languages', 500),
                preferred_countries=value('preferred_countries', 500),
                preferred_rotation=value('rotation', 80), city=value('city', 120))


def collect(db, values, nonce, tenant_id, offer_permission=False, request_key="", whatsapp_permission=False):
    """One atomic acquisition transaction, including provenance and consent."""
    email, phone = values['email'], values['phone']
    checks = []
    if email:
        checks.append(func.lower(Worker.email) == email)
    if phone:
        stored_phone = Worker.phone
        for char in (' ', '-', '(', ')', '.'):
            stored_phone = func.replace(stored_phone, char, '')
        checks.append(stored_phone == phone)
    if whatsapp_permission and not re.fullmatch(r'\+[1-9][0-9]{7,14}',phone):
        raise ValueError('Enter a valid WhatsApp number including country code')
    # Serialize concurrent submissions for one contact on PostgreSQL.
    if db.get_bind().dialect.name == 'postgresql':
        from sqlalchemy import text
        import hashlib
        identifiers = ([f'email:{email}'] if email else []) + ([f'phone:{phone}'] if phone else [])
        for identifier in sorted(identifiers):
            key = int.from_bytes(hashlib.sha256(f'{tenant_id}:{identifier}'.encode()).digest()[:8], 'big', signed=True)
            db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': key})
    existing = db.query(Worker).filter(Worker.tenant_id == tenant_id, or_(*checks)).first()
    if existing:
        # Never reveal an existing private portal token or overwrite verified data.
        row = CandidateIntake(tenant_id=tenant_id, worker_id=existing.id, nonce=nonce, status='DUPLICATE', request_key=request_key)
        db.add(row)
        db.commit()
        return {'created': False, 'worker_id': existing.id}
    worker = Worker(tenant_id=tenant_id, **values,
                    self_service_token=secrets.token_urlsafe(32),
                    last_availability_confirmed=date.today(),
                    identity_verified=False, documents_verified=False,
                    skills_verified=False, ready_to_deploy=False,
                    work_permit_notes='Self-declared application; recruiter verification required',
                    preferred_channel='WhatsApp' if whatsapp_permission else 'Email' if email else 'WhatsApp')
    db.add(worker)
    db.flush()
    db.add(CandidateIntake(tenant_id=tenant_id, worker_id=worker.id, nonce=nonce, status='CREATED', request_key=request_key))
    if offer_permission and email:
        db.add(Consent(tenant_id=tenant_id, worker_id=worker.id, channel='Email',
                       purpose='job_offers', granted=True, source='worker_self_registration', text_version=PRIVACY_VERSION))
    if whatsapp_permission:
        db.add(Consent(tenant_id=tenant_id,worker_id=worker.id,channel='WhatsApp',purpose='job_offers',granted=True,source='worker_self_registration',text_version='whatsapp-optin-v1'))
    db.add(AuditLog(tenant_id=tenant_id, actor='candidate-portal', action='CANDIDATE_SELF_REGISTERED',
                    entity_type='worker', entity_id=str(worker.id), details='source=euroteams-portal; verification=self-declared'))
    db.commit()
    return {'created': True, 'worker_id': worker.id}


def intake_stats(db, tenant_id):
    rows = db.query(CandidateIntake.status, func.count(CandidateIntake.id)).filter(
        CandidateIntake.tenant_id == tenant_id).group_by(CandidateIntake.status).all()
    result = dict(rows)
    last = db.query(func.max(CandidateIntake.created_at)).filter(CandidateIntake.tenant_id == tenant_id).scalar()
    return {'created': result.get('CREATED', 0), 'duplicates': result.get('DUPLICATE', 0),
            'last': last, 'state': 'READY_FOR_APPLICATIONS' if not last else 'RECEIVING_APPLICATIONS'}


def install(app):
    views = Jinja2Templates(directory=Path(__file__).parent / 'templates')
    def tenant(db):
        tid = int(os.getenv('WORKFORCE_ADMIN_TENANT_ID', '1'))
        if not db.get(Tenant, tid):
            raise HTTPException(503, 'Recruitment workspace is not available')
        return tid

    def render(request, error=None, status=200, values=None):
        token = signer().dumps({'nonce': secrets.token_urlsafe(24)})
        response = views.TemplateResponse(request, 'join.html', {'request': request, 'token': token, 'error': error, 'values': values or {}}, status_code=status)
        response.set_cookie('intake_form', token, httponly=True, secure=request.url.scheme == 'https', samesite='lax', max_age=3600, path='/join')
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/join', response_class=HTMLResponse)
    def join_form(request: Request, db: Session = Depends(get_db)):
        tenant(db)
        return render(request)

    @app.get('/join/privacy', response_class=HTMLResponse)
    def privacy(request: Request):
        return views.TemplateResponse(request, 'intake_privacy.html', {'request': request})

    @app.get('/join/received', response_class=HTMLResponse)
    def received(request: Request):
        return views.TemplateResponse(request, 'intake_received.html', {'request': request})

    @app.post('/join', response_class=HTMLResponse)
    async def join_submit(request: Request, db: Session = Depends(get_db)):
        tid = tenant(db)
        from urllib.parse import parse_qs
        import hashlib, hmac
        if not request.headers.get('content-type', '').startswith('application/x-www-form-urlencoded'):
            raise HTTPException(415, 'Use the registration form')
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 32_000:
                raise HTTPException(413, 'Application is too large')
        try:
            form = {key: value[-1] for key, value in parse_qs(body.decode('utf-8'), max_num_fields=30).items()}
        except (ValueError, UnicodeError):
            raise HTTPException(400, 'Invalid form')
        token = form.get('token', '')
        if not token or not secrets.compare_digest(token, request.cookies.get('intake_form', '')):
            raise HTTPException(403, 'Open the registration form and try again')
        try:
            payload = signer().loads(token, max_age=3600)
            nonce = payload['nonce']
        except (BadData, KeyError, TypeError):
            raise HTTPException(403, 'Registration form expired; reload and try again')
        if form.get('website'):
            return RedirectResponse('/join/received', 303)
        if db.query(CandidateIntake).filter(CandidateIntake.nonce == nonce).first():
            return RedirectResponse('/join/received', 303)
        ip = request.client.host if request.client else 'unknown'
        key = hmac.new(os.environ['INTAKE_FORM_SECRET'].encode(), ip.encode(), hashlib.sha256).hexdigest()
        recent = db.query(CandidateIntake).filter(CandidateIntake.request_key == key,
                    CandidateIntake.created_at >= datetime.utcnow() - timedelta(hours=1)).count()
        if recent >= 10:
            raise HTTPException(429, 'Too many applications; please try again later')
        try:
            values = validate_input(form)
        except (ValueError, OverflowError) as exc:
            return render(request, str(exc), 422, form)
        try:
            whatsapp_permission=form.get('whatsapp_offers')=='yes'
            if whatsapp_permission and not re.fullmatch(r'\+[1-9][0-9]{7,14}',values['phone']):
                return render(request,'Enter a valid WhatsApp number including country code',422,form)
            result = collect(db, values, nonce, tid, form.get('offers') == 'yes', key,whatsapp_permission)
        except IntegrityError:
            db.rollback()
            return RedirectResponse('/join/received', 303)
        if result['created']:
            worker = db.get(Worker, result['worker_id'])
            record = CandidateRecord(full_name=worker.full_name, country=worker.country,
                      role=worker.profession, source='euroteams-portal', email=worker.email,
                      phone=worker.phone, years_experience=worker.years_experience,
                      certificates=[x.strip() for x in worker.certificates.split(',') if x.strip()],
                      languages=[x.strip() for x in worker.languages.split(',') if x.strip()],
                      eu_citizen=worker.eu_citizen, availability_status=worker.availability_status,
                      available_from=worker.available_from, desired_net_hourly=worker.expected_salary_net_hour)
            projects = db.query(Project).filter(Project.tenant_id == tid,
                       Project.status.in_(['DRAFT', 'RECRUITING', 'ACTIVE'])).limit(100).all()
            try:
                for project in projects:
                    create_project_candidates(db, ProjectCandidate, project, {record.fingerprint: worker}, [record], tid)
            except Exception:
                db.rollback()
                db.add(AuditLog(tenant_id=tid, actor='candidate-portal', action='PORTAL_MATCH_FAILED',
                               entity_type='worker', entity_id=str(worker.id), details='Retry matching from Worker Collector'))
                db.commit()
        response = RedirectResponse('/join/received', 303)
        response.delete_cookie('intake_form', path='/join')
        return response
