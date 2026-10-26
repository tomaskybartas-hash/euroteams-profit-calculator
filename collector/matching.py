"""Evidence-based ranking. Missing fields do not establish a positive match."""
import re
from app.models import Worker
from .worker_collector import CandidateRecord,ProjectNeed,canonical_country,score_candidate


def completeness(worker):
    fields=[worker.full_name,worker.phone or worker.email,worker.country,worker.profession,worker.city,worker.skills,worker.languages,worker.certificates,worker.preferred_countries,worker.preferred_rotation,worker.expected_salary_net_hour,worker.years_experience,worker.last_availability_confirmed,worker.availability_status if worker.availability_status!='UNKNOWN' else '']
    return round(100*sum(bool(x) for x in fields)/len(fields))


def score(worker,project):
    split=lambda value:[x.strip() for x in re.split(r'[,;\n]',value or '') if x.strip()]
    record=CandidateRecord(full_name=worker.full_name,country=worker.country,role=worker.profession,source='workforce',email=worker.email,phone=worker.phone,years_experience=worker.years_experience,certificates=split(worker.certificates),languages=split(worker.languages),eu_citizen=worker.eu_citizen,availability_status=worker.availability_status,available_from=worker.available_from,desired_net_hourly=worker.expected_salary_net_hour or None)
    need=ProjectNeed(role=project.profession,country=project.country,workers_needed=project.workers_needed,required_certificates=split(project.required_certificates),required_languages=split(project.required_language),eu_only=project.citizenship_requirement.upper()=='EU',start_date=project.start_date,offered_net_hourly=project.salary_net_hour or None)
    result=score_candidate(record,need)
    reasons=[x for x in result.reasons if x!='experience' or worker.years_experience>0]
    blockers=list(result.blockers)
    preferred={canonical_country(x) for x in split(worker.preferred_countries)}
    destination=canonical_country(project.country)
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
        result=score(worker,project)
        if include_ineligible or result['eligible']:rows.append((worker,result))
    rows.sort(key=lambda item:(item[1]['eligible'],item[1]['match_score']),reverse=True)
    return rows[:limit]
