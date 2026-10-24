"""Bridge collected candidates into existing Workforce Live models.

Kept isolated so the collector remains testable without the production app package.
The bridge uses conservative field assignment because Workforce Live models evolve.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from .worker_collector import CandidateRecord, ProjectNeed, shortlist
import secrets


def _set_if_present(obj, name, value):
    if hasattr(obj, name) and value is not None:
        setattr(obj, name, value)


def _set_first_present(obj, names, value):
    for name in names:
        if hasattr(obj, name):
            setattr(obj, name, value)
            return name
    return None


def _find_worker(db, Worker, candidate: CandidateRecord, tenant_id: int):
    q = db.query(Worker).filter(Worker.tenant_id == tenant_id)
    if candidate.email and hasattr(Worker, "email"):
        found = q.filter(Worker.email == candidate.email).first()
        if found:
            return found
    if candidate.phone and hasattr(Worker, "phone"):
        found = q.filter(Worker.phone == candidate.phone).first()
        if found:
            return found
    return None


def upsert_workers(db, Worker, records: Iterable[CandidateRecord], tenant_id: int) -> dict:
    """Create/update Worker rows and preserve match-critical collector data."""
    created = updated = 0
    persisted = []
    for candidate in records:
        candidate.normalized()
        worker = _find_worker(db, Worker, candidate, tenant_id)
        if worker is None:
            worker = Worker(tenant_id=tenant_id)
            # Unknown citizenship must not inherit the legacy EU=True default.
            _set_if_present(worker, "eu_citizen", candidate.eu_citizen is True)
            _set_if_present(worker, "self_service_token", secrets.token_urlsafe(32))
            db.add(worker)
            created += 1
        else:
            updated += 1
        _set_if_present(worker, "full_name", candidate.full_name)
        _set_if_present(worker, "country", candidate.country)
        _set_if_present(worker, "profession", candidate.role)
        _set_if_present(worker, "role", candidate.role)
        _set_if_present(worker, "email", candidate.email or None)
        _set_if_present(worker, "phone", candidate.phone or None)
        _set_if_present(worker, "eu_citizen", candidate.eu_citizen)
        _set_if_present(worker, "availability_status", candidate.availability_status)
        _set_if_present(worker, "available_from", candidate.available_from)
        if candidate.desired_net_hourly is not None:
            _set_first_present(worker, ("expected_salary_net_hour", "desired_net_hourly"), candidate.desired_net_hourly)
        _set_if_present(worker, "years_experience", candidate.years_experience)
        _set_first_present(worker, ("certificates", "certifications", "certs"), ", ".join(candidate.certificates))
        _set_first_present(worker, ("languages", "language_skills"), ", ".join(candidate.languages))
        _set_if_present(worker, "source", candidate.source)
        _set_if_present(worker, "source_url", candidate.source_url)
        _set_if_present(worker, "collector_fingerprint", candidate.fingerprint)
        _set_if_present(worker, "consent_basis", candidate.consent_basis)
        _set_if_present(worker, "updated_at", datetime.now(timezone.utc))
        persisted.append(worker)
    db.commit()
    for worker in persisted:
        try:
            db.refresh(worker)
        except Exception:
            pass
    return {"created": created, "updated": updated, "workers": persisted}


def project_need_from_model(project) -> ProjectNeed:
    certs = getattr(project, "required_certificates", None) or []
    if isinstance(certs, str):
        certs = [x.strip() for x in certs.replace(";", ",").split(",") if x.strip()]
    langs = getattr(project, "required_languages", None) or getattr(project, "required_language", None) or []
    if isinstance(langs, str):
        langs = [x.strip() for x in langs.replace(";", ",").split(",") if x.strip()]
    citizenship = str(getattr(project, "citizenship_requirement", "") or "").upper()
    return ProjectNeed(
        role=getattr(project, "profession", None) or getattr(project, "role", None) or getattr(project, "trade", ""),
        country=getattr(project, "country", ""),
        workers_needed=int(getattr(project, "workers_needed", 1) or 1),
        required_certificates=certs,
        required_languages=langs,
        eu_only=citizenship == "EU",
        start_date=getattr(project, "start_date", None),
        offered_net_hourly=getattr(project, "salary_net_hour", None) or getattr(project, "net_hourly", None) or getattr(project, "offered_net_hourly", None),
        min_experience_years=float(getattr(project, "min_experience_years", 0) or 0),
    )


def create_project_candidates(db, ProjectCandidate, project, worker_by_fingerprint: dict, records, tenant_id: int) -> dict:
    """Rank candidates and create or refresh ProjectCandidate rows."""
    results = shortlist(records, project_need_from_model(project), limit=500)
    created = existing = refreshed = blocked = 0
    for result in results:
        worker = worker_by_fingerprint.get(result.fingerprint)
        if worker is None or not getattr(worker, "id", None):
            continue
        row = db.query(ProjectCandidate).filter(
            ProjectCandidate.project_id == project.id,
            ProjectCandidate.worker_id == worker.id,
        ).first()
        is_new = row is None
        if is_new:
            row = ProjectCandidate(project_id=project.id, worker_id=worker.id)
            _set_if_present(row, "tenant_id", tenant_id)
            db.add(row)
            created += 1
        else:
            existing += 1
            refreshed += 1
        _set_if_present(row, "match_score", result.score)
        _set_if_present(row, "eligibility", "PASS" if result.eligible else "BLOCKED")
        current_stage = str(getattr(row, "stage", "") or "").upper()
        if is_new or current_stage in {"", "MATCHED", "BLOCKED"}:
            _set_if_present(row, "stage", "MATCHED" if result.eligible else "BLOCKED")
        _set_if_present(row, "notes", "COLLECTOR_REASONS=" + " | ".join(result.reasons) + "\nCOLLECTOR_BLOCKERS=" + (" | ".join(result.blockers) or "NONE"))
        if not result.eligible:
            blocked += 1
    db.commit()
    return {"created": created, "existing": existing, "refreshed": refreshed, "blocked": blocked, "ranked": len(results)}
