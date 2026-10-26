from datetime import date
from collector.worker_collector import CandidateRecord, ProjectNeed, deduplicate, shortlist, canonical_country, certificate_tokens


def test_deduplicates_by_email_and_merges_certificates():
    rows=[CandidateRecord("Jan Kowalski","Poland","Welder","import",email="JAN@example.com",certificates=["135/136"]),CandidateRecord("Jan Kowalski","PL","welding","portal",email="jan@example.com",certificates=["141"])]
    unique=deduplicate(rows)
    assert len(unique)==1
    assert {"135","136","141"}.issubset(set(unique[0].certificates))
    assert unique[0].country=="PL"


def test_country_names_from_all_target_markets_normalize():
    expected={"Lithuania":"LT","Latvia":"LV","Poland":"PL","Romania":"RO","Bulgaria":"BG","Spain":"ES","Italy":"IT"}
    assert {name:canonical_country(name) for name in expected}==expected


def test_compound_welding_certificate_satisfies_required_process():
    assert "135" in certificate_tokens(["EN ISO 9606-1 MIG/MAG 135/136"])
    project=ProjectNeed(role="MIG/MAG Welder 135/136",country="NL",workers_needed=1,required_certificates=["135"],required_languages=["English"],eu_only=True,start_date=date(2026,11,1),offered_net_hourly=21,min_experience_years=3)
    worker=CandidateRecord("Piotr Nowak","Poland","MIG/MAG Welder 135/136","approved",email="p@example.com",years_experience=7,certificates=["EN ISO 9606-1 135/136"],languages=["English A2"],eu_citizen=True,availability_status="ASAP",desired_net_hourly=20)
    result=shortlist([worker],project)[0]
    assert result.eligible is True
    assert result.score>=80


def test_shortlist_blocks_nonmatching_worker():
    project=ProjectNeed(role="welder",country="NL",workers_needed=2,required_certificates=["135"],required_languages=["EN"],eu_only=True,start_date=date(2026,11,1),offered_net_hourly=21,min_experience_years=3)
    good=CandidateRecord("Piotr Nowak","PL","Welder","approved-source",email="p@example.com",years_experience=7,certificates=["135"],languages=["EN"],eu_citizen=True,availability_status="AVAILABLE NOW",desired_net_hourly=20)
    weak=CandidateRecord("Mario Rossi","IT","Carpenter","approved-source",email="m@example.com",years_experience=8,languages=["IT"],eu_citizen=True,availability_status="UNKNOWN")
    results=shortlist([weak,good],project)
    assert results[0].candidate.full_name=="Piotr Nowak" and results[0].eligible is True
    assert results[1].eligible is False
