from datetime import date
from collector.worker_collector import CandidateRecord, ProjectNeed, deduplicate, shortlist


def test_deduplicates_by_email_and_merges_certificates():
    rows = [
        CandidateRecord("Jan Kowalski", "PL", "Welder", "import", email="JAN@example.com", certificates=["135"]),
        CandidateRecord("Jan Kowalski", "PL", "welding", "portal", email="jan@example.com", certificates=["136"]),
    ]
    unique = deduplicate(rows)
    assert len(unique) == 1
    assert set(unique[0].certificates) == {"135", "136"}


def test_shortlist_prefers_deployable_exact_match():
    project = ProjectNeed(
        role="welder", country="NL", workers_needed=2,
        required_certificates=["135"], required_languages=["EN"], eu_only=True,
        start_date=date(2026, 11, 1), offered_net_hourly=21, min_experience_years=3,
    )
    good = CandidateRecord(
        "Piotr Nowak", "PL", "Welder", "approved-source", email="p@example.com",
        years_experience=7, certificates=["135"], languages=["EN"], eu_citizen=True,
        availability_status="AVAILABLE NOW", desired_net_hourly=20,
    )
    weak = CandidateRecord(
        "Mario Rossi", "IT", "Carpenter", "approved-source", email="m@example.com",
        years_experience=8, languages=["IT"], eu_citizen=True, availability_status="UNKNOWN",
    )
    results = shortlist([weak, good], project)
    assert results[0].candidate.full_name == "Piotr Nowak"
    assert results[0].eligible is True
    assert results[0].score >= 80
    assert results[1].eligible is False
