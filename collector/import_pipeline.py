"""Safe ingestion pipeline for Workforce Collector.

Turns approved CSV/export data into normalized CandidateRecord objects and produces
an import report. This deliberately does not scrape or bypass third-party controls.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, asdict
from datetime import date
from typing import Iterable

from .worker_collector import CandidateRecord, deduplicate

TRUE_VALUES = {"1", "true", "yes", "y", "taip", "eu"}
FALSE_VALUES = {"0", "false", "no", "n", "ne"}


def split_values(value: str) -> list[str]:
    if not value:
        return []
    normalized = value.replace(";", ",").replace("|", ",")
    return [x.strip() for x in normalized.split(",") if x.strip()]


def parse_bool(value: str):
    v = (value or "").strip().lower()
    if v in TRUE_VALUES:
        return True
    if v in FALSE_VALUES:
        return False
    return None


def parse_date(value: str):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            from datetime import datetime
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def parse_float(value: str):
    try:
        return float((value or "").strip().replace(",", "."))
    except ValueError:
        return None


FIELD_ALIASES = {
    "full_name": ["full_name", "name", "candidate", "worker", "vardas_pavarde"],
    "country": ["country", "country_code", "salis"],
    "role": ["role", "profession", "trade", "job_title", "specialybe"],
    "email": ["email", "e-mail", "mail"],
    "phone": ["phone", "mobile", "telephone", "tel"],
    "years_experience": ["years_experience", "experience_years", "experience"],
    "certificates": ["certificates", "certs", "licenses"],
    "languages": ["languages", "language"],
    "eu_citizen": ["eu_citizen", "eu", "eu_citizenship"],
    "availability_status": ["availability_status", "availability", "status"],
    "available_from": ["available_from", "start_date"],
    "desired_net_hourly": ["desired_net_hourly", "net_hourly", "rate", "salary"],
    "source_url": ["source_url", "profile_url", "url"],
}


def _value(row: dict, field: str) -> str:
    lowered = {str(k).strip().lower(): (v or "") for k, v in row.items()}
    for alias in FIELD_ALIASES[field]:
        if alias in lowered:
            return str(lowered[alias]).strip()
    return ""


@dataclass
class ImportReport:
    source: str
    total_rows: int = 0
    accepted_rows: int = 0
    rejected_rows: int = 0
    duplicates_removed: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def to_dict(self):
        return asdict(self)


def records_from_csv(text: str, source: str, consent_basis: str = "SOURCE_PERMITTED") -> tuple[list[CandidateRecord], ImportReport]:
    report = ImportReport(source=source)
    accepted: list[CandidateRecord] = []
    reader = csv.DictReader(io.StringIO(text))
    for line_no, row in enumerate(reader, start=2):
        report.total_rows += 1
        name, country, role = _value(row, "full_name"), _value(row, "country"), _value(row, "role")
        email, phone = _value(row, "email"), _value(row, "phone")
        if not name or not country or not role:
            report.rejected_rows += 1
            report.errors.append(f"line {line_no}: missing name/country/role")
            continue
        if not email and not phone:
            report.rejected_rows += 1
            report.errors.append(f"line {line_no}: missing contact method")
            continue
        years = parse_float(_value(row, "years_experience"))
        rate = parse_float(_value(row, "desired_net_hourly"))
        record = CandidateRecord(
            full_name=name,
            country=country,
            role=role,
            source=source,
            source_url=_value(row, "source_url"),
            email=email,
            phone=phone,
            years_experience=years or 0,
            certificates=split_values(_value(row, "certificates")),
            languages=split_values(_value(row, "languages")),
            eu_citizen=parse_bool(_value(row, "eu_citizen")),
            availability_status=_value(row, "availability_status") or "UNKNOWN",
            available_from=parse_date(_value(row, "available_from")),
            desired_net_hourly=rate,
            consent_basis=consent_basis,
        )
        accepted.append(record)
        report.accepted_rows += 1
    unique = deduplicate(accepted)
    report.duplicates_removed = len(accepted) - len(unique)
    return unique, report
