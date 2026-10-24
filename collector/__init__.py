"""Euroteams Workforce Collector package."""

from .worker_collector import CandidateRecord, ProjectNeed, MatchResult, deduplicate, shortlist
from .import_pipeline import records_from_csv, ImportReport

__all__ = [
    "CandidateRecord", "ProjectNeed", "MatchResult", "deduplicate", "shortlist",
    "records_from_csv", "ImportReport",
]
