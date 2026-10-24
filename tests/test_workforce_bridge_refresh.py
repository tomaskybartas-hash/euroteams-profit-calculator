from collector.worker_collector import CandidateRecord
from collector.workforce_bridge import upsert_workers, create_project_candidates

class Field:
    def __eq__(self, other): return (self, other)
class Worker:
    tenant_id=Field(); email=Field(); phone=Field()
    def __init__(self, tenant_id=None):
        self.tenant_id=tenant_id; self.id=None; self.email=''; self.phone=''; self.full_name=''; self.country=''; self.profession=''; self.certificates=''; self.languages=''; self.availability_status=''; self.years_experience=0; self.eu_citizen=None
class ProjectCandidate:
    project_id=Field(); worker_id=Field()
    def __init__(self, project_id=None, worker_id=None): self.project_id=project_id; self.worker_id=worker_id; self.match_score=0; self.eligibility=''; self.stage=''; self.notes=''
class Query:
    def __init__(self, rows): self.rows=rows
    def filter(self,*args): return self
    def first(self): return self.rows[0] if self.rows else None
class DB:
    def __init__(self): self.workers=[]; self.candidates=[]
    def query(self, cls): return Query(self.workers if cls is Worker else self.candidates)
    def add(self,obj):
        if isinstance(obj,Worker): obj.id=len(self.workers)+1; self.workers.append(obj)
        else: self.candidates.append(obj)
    def commit(self): pass
    def refresh(self,obj): pass
class Project:
    id=7; profession='welder'; country='NL'; workers_needed=2; required_certificates='135'; required_languages='EN'; citizenship_requirement='EU'; start_date=None; net_hourly=21; min_experience_years=2

def test_upsert_preserves_match_critical_fields_and_refreshes_candidate():
    db=DB(); record=CandidateRecord('Jan Kowalski','Poland','MIG/MAG welder','test',email='jan@example.com',years_experience=6,certificates=['ISO 9606-1 135'],languages=['English'],eu_citizen=True,availability_status='ASAP',desired_net_hourly=20)
    persisted=upsert_workers(db,Worker,[record],1)
    worker=persisted['workers'][0]
    assert '135' in worker.certificates
    assert 'EN' in worker.languages
    mapping={record.fingerprint:worker}
    first=create_project_candidates(db,ProjectCandidate,Project(),mapping,[record],1)
    assert first['created']==1 and first['blocked']==0
    record.availability_status='NOT AVAILABLE'
    second=create_project_candidates(db,ProjectCandidate,Project(),mapping,[record],1)
    assert second['created']==0 and second['refreshed']==1 and second['blocked']==1
    assert db.candidates[0].eligibility=='BLOCKED'
