"""Recruitment stages based on supplied facts, independently of identity verification."""
from datetime import date,timedelta
import re


def has_name(value):
    text=(value or '').strip()
    if re.search(r'vardas nepateiktas|public jobseeker|unknown|unconfirmed|not provided',text,re.I):return False
    return len([p for p in text.split() if any(c.isalpha() for c in p)])>=2


def missing_fields(worker):
    missing=[]
    if not has_name(worker.full_name):missing.append('Full name')
    phone=re.sub(r'[ ().-]','',worker.phone or '')
    valid_phone=bool(re.fullmatch(r'(?:\+|00)[1-9][0-9]{7,14}',phone))
    valid_email=bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',worker.email or ''))
    if not valid_phone and not valid_email:missing.append('Contact details')
    if not worker.country:missing.append('Country')
    if not worker.profession or worker.profession.lower() in ['unknown','unconfirmed','other']:missing.append('Profession')
    if not worker.skills and not worker.years_experience:missing.append('Experience or skills')
    if not worker.preferred_countries:missing.append('Preferred countries')
    confirmed=worker.last_availability_confirmed
    if worker.availability_status not in ['AVAILABLE NOW','AVAILABLE FROM DATE','OPEN TO OFFERS'] or not confirmed or not date.today()-timedelta(days=30)<=confirmed<=date.today():missing.append('Recent availability confirmation')
    if worker.availability_status=='AVAILABLE FROM DATE' and not worker.available_from:missing.append('Available from')
    return missing


def profile_ready(worker):return not missing_fields(worker)


DESTINATIONS={'NL':('Netherlands','Nyderlandai','Holandija'),'NO':('Norway','Norvegija'),'SE':('Sweden','Švedija'),'FI':('Finland','Suomija'),'DK':('Denmark','Danija'),'DE':('Germany','Vokietija'),'BE':('Belgium','Belgija'),'FR':('France','Prancūzija'),'AT':('Austria','Austrija'),'CH':('Switzerland','Šveicarija'),'CZ':('Czechia','Čekija'),'PT':('Portugal','Portugalija'),'EE':('Estonia','Estija'),'GB':('United Kingdom','UK','Jungtinė Karalystė')}


def country_code(value):
    from collector.worker_collector import canonical_country,fold
    for code,names in DESTINATIONS.items():
        if fold(value) in {fold(x) for x in (code,)+names}:return code
    return canonical_country(value)


def country_label(value):
    code=country_code(value)
    return DESTINATIONS[code][0] if code in DESTINATIONS else value
