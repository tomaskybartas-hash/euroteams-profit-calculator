"""Euroteams Workforce Collector v1.

Provider-agnostic ingestion core. It accepts candidate records from approved sources,
normalizes them, deduplicates them and scores them against a project. Collection
adapters should only ingest data that the source permits Euroteams to process.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
import hashlib
import re
import unicodedata
from typing import Iterable, Optional

SUPPORTED_COUNTRIES = {"LT", "LV", "PL", "RO", "BG", "ES", "IT"}
ROLE_ALIASES = {
    "welder": {"welder", "welding", "suvirintojas", "spawacz", "sudor", "saldatore"},
    "pipefitter": {"pipefitter", "pipe fitter", "rigger tubero", "monter rurociagow"},
    "metal fitter": {"metal fitter", "fitter", "monter", "assembly fitter", "mechanical fitter"},
    "mechanic": {"mechanic", "mechanical", "mechanik", "mecanico", "meccanico"},
    "carpenter": {"carpenter", "stolarz", "dailide", "carpintero", "falegname"},
    "electrician": {"electrician", "elektryk", "elektrikas", "electricista", "elettricista"},
}


def clean(value: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def fold(value: Optional[str]) -> str:
    value = unicodedata.normalize("NFKD", clean(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9+.# ]+", " ", value).strip()


def normalize_phone(value: Optional[str]) -> str:
    raw = clean(value)
    if not raw:
        return ""
    plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    return ("+" if plus else "") + digits


def canonical_role(value: Optional[str]) -> str:
    v = fold(value)
    for canonical, aliases in ROLE_ALIASES.items():
        if any(alias in v for alias in aliases):
            return canonical
    return v


def stable_fingerprint(email: str = "", phone: str = "", name: str = "", country: str = "") -> str:
    email = clean(email).lower()
    phone = normalize_phone(phone)
    if email:
        raw = "email:" + email
    elif phone:
        raw = "phone:" + phone
    else:
        raw = f"person:{fold(name)}:{country.upper()}"
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class CandidateRecord:
    full_name: str
    country: str
    role: str
    source: str
    source_url: str = ""
    email: str = ""
    phone: str = ""
    years_experience: float = 0
    certificates: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    eu_citizen: Optional[bool] = None
    availability_status: str = "UNKNOWN"
    available_from: Optional[date] = None
    desired_net_hourly: Optional[float] = None
    consent_basis: str = "SOURCE_PERMITTED"
    collected_at: datetime = field(default_factory=datetime.utcnow)

    def normalized(self) -> "CandidateRecord":
        self.full_name = clean(self.full_name)
        self.country = clean(self.country).upper()
        self.role = canonical_role(self.role)
        self.email = clean(self.email).lower()
        self.phone = normalize_phone(self.phone)
        self.certificates = sorted({clean(x).upper() for x in self.certificates if clean(x)})
        self.languages = sorted({clean(x).upper() for x in self.languages if clean(x)})
        self.availability_status = clean(self.availability_status).upper() or "UNKNOWN"
        return self

    @property
    def fingerprint(self) -> str:
        return stable_fingerprint(self.email, self.phone, self.full_name, self.country)


@dataclass
class ProjectNeed:
    role: str
    country: str
    workers_needed: int
    required_certificates: list[str] = field(default_factory=list)
    required_languages: list[str] = field(default_factory=list)
    eu_only: bool = False
    start_date: Optional[date] = None
    offered_net_hourly: Optional[float] = None
    min_experience_years: float = 0


@dataclass
class MatchResult:
    fingerprint: str
    score: int
    eligible: bool
    reasons: list[str]
    blockers: list[str]
    candidate: CandidateRecord


def deduplicate(records: Iterable[CandidateRecord]) -> list[CandidateRecord]:
    """Merge repeated records, preferring richer/newer data without inventing fields."""
    merged: dict[str, CandidateRecord] = {}
    for incoming in records:
        incoming.normalized()
        key = incoming.fingerprint
        current = merged.get(key)
        if current is None:
            merged[key] = incoming
            continue
        if incoming.collected_at >= current.collected_at:
            primary, secondary = incoming, current
        else:
            primary, secondary = current, incoming
        primary.certificates = sorted(set(primary.certificates) | set(secondary.certificates))
        primary.languages = sorted(set(primary.languages) | set(secondary.languages))
        for attr in ("email", "phone", "source_url"):
            if not getattr(primary, attr):
                setattr(primary, attr, getattr(secondary, attr))
        primary.years_experience = max(primary.years_experience, secondary.years_experience)
        merged[key] = primary
    return list(merged.values())


def score_candidate(candidate: CandidateRecord, project: ProjectNeed) -> MatchResult:
    c = candidate.normalized()
    role = canonical_role(project.role)
    blockers: list[str] = []
    reasons: list[str] = []
    score = 0

    if c.country not in SUPPORTED_COUNTRIES:
        blockers.append("unsupported source country")
    if c.role == role:
        score += 35; reasons.append("exact role")
    else:
        blockers.append("role mismatch")
    if project.eu_only and c.eu_citizen is not True:
        blockers.append("EU citizenship not confirmed")
    elif c.eu_citizen is True:
        score += 10; reasons.append("EU citizen")

    required_certs = {clean(x).upper() for x in project.required_certificates}
    candidate_certs = set(c.certificates)
    missing_certs = required_certs - candidate_certs
    if missing_certs:
        blockers.append("missing certificates: " + ", ".join(sorted(missing_certs)))
    elif required_certs:
        score += 15; reasons.append("certificates match")

    required_langs = {clean(x).upper() for x in project.required_languages}
    if required_langs:
        overlap = required_langs & set(c.languages)
        if overlap:
            score += 10; reasons.append("language match")
        else:
            blockers.append("required language not confirmed")

    if c.years_experience >= project.min_experience_years:
        score += min(15, int(c.years_experience * 2)); reasons.append("experience")
    else:
        blockers.append("insufficient confirmed experience")

    if c.availability_status in {"AVAILABLE NOW", "OPEN TO OFFERS"}:
        score += 15; reasons.append("available")
    elif c.availability_status == "AVAILABLE FROM DATE" and c.available_from:
        if not project.start_date or c.available_from <= project.start_date:
            score += 12; reasons.append("available by start")
        else:
            blockers.append("available after project start")
    else:
        blockers.append("availability not confirmed")

    if project.offered_net_hourly is not None and c.desired_net_hourly is not None:
        if c.desired_net_hourly <= project.offered_net_hourly:
            score += 10; reasons.append("rate accepted range")
        else:
            blockers.append("rate above offer")

    score = max(0, min(100, score))
    eligible = not blockers
    return MatchResult(c.fingerprint, score, eligible, reasons, blockers, c)


def shortlist(records: Iterable[CandidateRecord], project: ProjectNeed, limit: int = 100) -> list[MatchResult]:
    unique = deduplicate(records)
    results = [score_candidate(c, project) for c in unique]
    return sorted(results, key=lambda x: (x.eligible, x.score), reverse=True)[:limit]


def serialize_result(result: MatchResult) -> dict:
    data = asdict(result)
    data["candidate"]["collected_at"] = result.candidate.collected_at.isoformat()
    if result.candidate.available_from:
        data["candidate"]["available_from"] = result.candidate.available_from.isoformat()
    return data
