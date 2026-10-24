"""Euroteams Workforce Collector v1: normalization, dedupe and job matching."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
import hashlib, re, unicodedata
from typing import Iterable, Optional

SUPPORTED_COUNTRIES={"LT","LV","PL","RO","BG","ES","IT"}
COUNTRY_ALIASES={
 "LT":{"lt","lithuania","lietuva"},"LV":{"lv","latvia","latvija"},
 "PL":{"pl","poland","polska","lenkija"},"RO":{"ro","romania","romania","rumunija"},
 "BG":{"bg","bulgaria","bulgarija"},"ES":{"es","spain","espana","ispanija"},
 "IT":{"it","italy","italia","italija"},
}
ROLE_ALIASES={
 "general labour":{"general labour","general labor","unskilled","helper","nekvalifikuota","pagalbinis"},
 "mason":{"mason","bricklayer","murininkas","mūrininkas"},
 "scaffolder":{"scaffolder","pastolininkas"},
 "other":{"other","kita"},
 "welder":{"welder","welding","suvirintojas","spawacz","sudor","saldatore"},
 "pipefitter":{"pipefitter","pipe fitter","rigger tubero","monter rurociagow","monter rurociągów"},
 "metal fitter":{"metal fitter","assembly fitter","mechanical fitter","steel fitter","monter konstrukcji"},
 "mechanic":{"mechanic","mechanical mechanic","mechanik","mecanico","meccanico"},
 "carpenter":{"carpenter","stolarz","dailide","carpintero","falegname"},
 "electrician":{"electrician","elektryk","elektrikas","electricista","elettricista"},
}
AVAILABILITY_ALIASES={
 "AVAILABLE NOW":{"available now","available","immediately","asap","now","laisvas dabar"},
 "OPEN TO OFFERS":{"open to offers","open for offers","looking","seeking work"},
 "AVAILABLE FROM DATE":{"available from date","available from","from date"},
 "CURRENTLY WORKING":{"currently working","working","employed"},
 "NOT AVAILABLE":{"not available","unavailable"},
}
LANGUAGE_ALIASES={"EN":{"en","english","anglu","anglų"},"LT":{"lt","lithuanian","lietuviu","lietuvių"},"PL":{"pl","polish","polski"},"ES":{"es","spanish","espanol","español"},"IT":{"it","italian","italiano"},"RO":{"ro","romanian"},"BG":{"bg","bulgarian"}}

def clean(v:Optional[str])->str:return re.sub(r"\s+"," ",(v or "").strip())
def fold(v:Optional[str])->str:
 v=unicodedata.normalize("NFKD",clean(v)).encode("ascii","ignore").decode().lower()
 return re.sub(r"[^a-z0-9+.# ]+"," ",v).strip()
def normalize_phone(v:Optional[str])->str:
 raw=clean(v)
 if not raw:return ""
 digits=re.sub(r"\D","",raw)
 return ("+" if raw.startswith("+") else "")+digits
def canonical_country(v:Optional[str])->str:
 x=fold(v)
 for code,aliases in COUNTRY_ALIASES.items():
  if x in {fold(a) for a in aliases}:return code
 return clean(v).upper()
def canonical_role(v:Optional[str])->str:
 x=fold(v)
 for role,aliases in ROLE_ALIASES.items():
  if any(fold(a) in x for a in aliases):return role
 return x
def canonical_availability(v:Optional[str])->str:
 x=fold(v)
 for status,aliases in AVAILABILITY_ALIASES.items():
  if x in {fold(a) for a in aliases}:return status
 return clean(v).upper() or "UNKNOWN"
def canonical_language(v:str)->str:
 x=fold(v).split()[0] if fold(v) else ""
 for code,aliases in LANGUAGE_ALIASES.items():
  if x in {fold(a) for a in aliases}:return code
 return clean(v).upper()
def certificate_tokens(values:Iterable[str])->set[str]:
 out=set()
 for value in values:
  text=clean(value).upper()
  if text:out.add(text)
  out.update(re.findall(r"\b(?:111|135|136|138|141|VCA|SCC|ISO\s*9606(?:-1)?)\b",text))
 return out
def stable_fingerprint(email="",phone="",name="",country="")->str:
 email=clean(email).lower();phone=normalize_phone(phone);country=canonical_country(country)
 raw="email:"+email if email else ("phone:"+phone if phone else f"person:{fold(name)}:{country}")
 return hashlib.sha256(raw.encode()).hexdigest()

@dataclass
class CandidateRecord:
 full_name:str;country:str;role:str;source:str;source_url:str="";email:str="";phone:str="";years_experience:float=0
 certificates:list[str]=field(default_factory=list);languages:list[str]=field(default_factory=list);eu_citizen:Optional[bool]=None
 availability_status:str="UNKNOWN";available_from:Optional[date]=None;desired_net_hourly:Optional[float]=None
 consent_basis:str="SOURCE_PERMITTED";collected_at:datetime=field(default_factory=datetime.utcnow)
 def normalized(self):
  self.full_name=clean(self.full_name);self.country=canonical_country(self.country);self.role=canonical_role(self.role)
  self.email=clean(self.email).lower();self.phone=normalize_phone(self.phone)
  self.certificates=sorted(certificate_tokens(self.certificates));self.languages=sorted({canonical_language(x) for x in self.languages if clean(x)})
  self.availability_status=canonical_availability(self.availability_status);return self
 @property
 def fingerprint(self):return stable_fingerprint(self.email,self.phone,self.full_name,self.country)

@dataclass
class ProjectNeed:
 role:str;country:str;workers_needed:int;required_certificates:list[str]=field(default_factory=list);required_languages:list[str]=field(default_factory=list)
 eu_only:bool=False;start_date:Optional[date]=None;offered_net_hourly:Optional[float]=None;min_experience_years:float=0
@dataclass
class MatchResult:
 fingerprint:str;score:int;eligible:bool;reasons:list[str];blockers:list[str];candidate:CandidateRecord

def deduplicate(records:Iterable[CandidateRecord])->list[CandidateRecord]:
 merged={}
 for incoming in records:
  incoming.normalized();key=incoming.fingerprint;current=merged.get(key)
  if current is None:merged[key]=incoming;continue
  primary,secondary=(incoming,current) if incoming.collected_at>=current.collected_at else (current,incoming)
  primary.certificates=sorted(set(primary.certificates)|set(secondary.certificates));primary.languages=sorted(set(primary.languages)|set(secondary.languages))
  for attr in ("email","phone","source_url"):
   if not getattr(primary,attr):setattr(primary,attr,getattr(secondary,attr))
  primary.years_experience=max(primary.years_experience,secondary.years_experience)
  if primary.eu_citizen is None:primary.eu_citizen=secondary.eu_citizen
  if primary.availability_status in {"","UNKNOWN"}:primary.availability_status=secondary.availability_status
  if primary.available_from is None:primary.available_from=secondary.available_from
  if primary.desired_net_hourly is None:primary.desired_net_hourly=secondary.desired_net_hourly
  merged[key]=primary
 return list(merged.values())

def score_candidate(candidate:CandidateRecord,project:ProjectNeed)->MatchResult:
 c=candidate.normalized();role=canonical_role(project.role);blockers=[];reasons=[];score=0
 if c.country not in SUPPORTED_COUNTRIES:blockers.append("unsupported source country")
 if c.role==role:score+=35;reasons.append("exact role")
 else:blockers.append("role mismatch")
 if project.eu_only and c.eu_citizen is not True:blockers.append("EU citizenship not confirmed")
 elif c.eu_citizen is True:score+=10;reasons.append("EU citizen")
 required=certificate_tokens(project.required_certificates);have=certificate_tokens(c.certificates);missing=required-have
 if missing:blockers.append("missing certificates: "+", ".join(sorted(missing)))
 elif required:score+=15;reasons.append("certificates match")
 required_langs={canonical_language(x) for x in project.required_languages if clean(x)}
 if required_langs:
  if required_langs & set(c.languages):score+=10;reasons.append("language match")
  else:blockers.append("required language not confirmed")
 if c.years_experience>=project.min_experience_years:score+=min(15,int(c.years_experience*2));reasons.append("experience")
 else:blockers.append("insufficient confirmed experience")
 if c.availability_status in {"AVAILABLE NOW","OPEN TO OFFERS"}:score+=15;reasons.append("available")
 elif c.availability_status=="AVAILABLE FROM DATE" and c.available_from:
  if not project.start_date or c.available_from<=project.start_date:score+=12;reasons.append("available by start")
  else:blockers.append("available after project start")
 else:blockers.append("availability not confirmed")
 if project.offered_net_hourly is not None and c.desired_net_hourly is not None:
  if c.desired_net_hourly<=project.offered_net_hourly:score+=10;reasons.append("rate accepted range")
  else:blockers.append("rate above offer")
 score=max(0,min(100,score));return MatchResult(c.fingerprint,score,not blockers,reasons,blockers,c)
def shortlist(records:Iterable[CandidateRecord],project:ProjectNeed,limit:int=100)->list[MatchResult]:
 return sorted((score_candidate(c,project) for c in deduplicate(records)),key=lambda x:(x.eligible,x.score),reverse=True)[:limit]
def serialize_result(result:MatchResult)->dict:
 data=asdict(result);data["candidate"]["collected_at"]=result.candidate.collected_at.isoformat()
 if result.candidate.available_from:data["candidate"]["available_from"]=result.candidate.available_from.isoformat()
 return data
