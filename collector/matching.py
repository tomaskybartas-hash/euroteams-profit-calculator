"""Evidence-based ranking. Missing fields do not establish a positive match."""
import re
from app.models import Worker
from collector.profile_quality import profile_ready,missing_fields,has_name,country_code
from .worker_collector import CandidateRecord,ProjectNeed,canonical_country,score_candidate


def completeness(worker):
    fields=[worker.full_name if has_name(worker.full_name) else '',worker.phone or worker.email,worker.country,worker.profession,worker.city,worker.skills,worker.languages,worker.certificates,worker.preferred_countries,worker.preferred_rotation,worker.expected_salary_net_hour,worker.years_experience,worker.last_availability_confirmed,worker.availability_status if worker.availability_status!='UNKNOWN' else '']
    return round(100*sum(bool(x) for x in fields)/len(fields))


def score(worker,project):
    split=lambda value:[x.strip() for x in re.split(r'[,;\n]',value or '') if x.strip()]
    record=CandidateRecord(full_name=worker.full_name,country=worker.country,role=worker.profession,source='workforce',email=worker.email,phone=worker.phone,years_experience=worker.years_experience,certificates=split(worker.certificates),languages=split(worker.languages),eu_citizen=worker.eu_citizen,availability_status=worker.availability_status,available_from=worker.available_from,desired_net_hourly=worker.expected_salary_net_hour or None)
    need=ProjectNeed(role=project.profession,country=project.country,workers_needed=project.workers_needed,required_certificates=split(project.required_certificates),required_languages=split(project.required_language),eu_only=project.citizenship_requirement.upper()=='EU',start_date=project.start_date,offered_net_hourly=project.salary_net_hour or None)
    result=score_candidate(record,need)
    reasons=[x for x in result.reasons if x!='experience' or worker.years_experience>0]
    blockers=list(result.blockers)
    if not profile_ready(worker):blockers.append('Profile incomplete')
    preferred={country_code(x) for x in split(worker.preferred_countries)}
    destination=country_code(project.country)
    if preferred and destination not in preferred:
        blockers.append('project country outside stated preferences')
    elif preferred and destination in preferred:
        reasons.append('Country preference matches')
    if not worker.phone and not worker.email:blockers.append('contact not provided')
    if worker.availability_status in ['AVAILABLE NOW','AVAILABLE FROM DATE','OPEN TO OFFERS'] and not worker.last_availability_confirmed:blockers.append('availability not verified')
    return {'eligible':not blockers,'match_score':result.score,'fit_score':result.score,'interest_probability':0,'arrival_probability':0,'data_confidence':completeness(worker),'reasons':reasons+blockers,'hard_failures':blockers}


def ranked_workers(db,project,tenant_id=1,limit=100,include_ineligible=False):
    rows=[]
    for worker in db.query(Worker).filter(Worker.tenant_id==tenant_id).all():
        if not profile_ready(worker):continue
        result=score(worker,project)
        if include_ineligible or result['eligible']:rows.append((worker,result))
    rows.sort(key=lambda item:(item[1]['eligible'],item[1]['match_score']),reverse=True)
    return rows[:limit]


def sync_worker_matches(db,worker):
    """Use the same live scoring for registration, profile completion and rematching.

    Caller owns the transaction; existing recruiter stages and notes are retained.
    """
    from app.models import Project,ProjectCandidate
    if not profile_ready(worker):return 0
    count=0
    for job in db.query(Project).filter(Project.tenant_id==worker.tenant_id,Project.status.in_(['DRAFT','RECRUITING','ACTIVE'])).limit(100).all():
        result=score(worker,job)
        candidate=db.query(ProjectCandidate).filter_by(project_id=job.id,worker_id=worker.id).first()
        if not candidate:
            candidate=ProjectCandidate(project_id=job.id,worker_id=worker.id)
            db.add(candidate)
        candidate.match_score=result['match_score'];candidate.fit_score=result['fit_score']
        candidate.data_confidence=result['data_confidence']
        candidate.eligibility='PASS' if result['eligible'] else 'REVIEW'
        count+=1
    return count
