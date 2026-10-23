"""Registry for worker acquisition sources.

Only enabled sources with an explicit lawful/contractual basis may enter the automated
pipeline. This gives the future scheduler one place to decide what it may collect.
"""
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class SourceConfig:
    key:str
    name:str
    source_type:str
    enabled:bool=False
    acquisition_method:str="MANUAL_EXPORT"
    permission_basis:str=""
    retention_days:int=365
    country_scope:tuple[str,...]=()
    notes:str=""

class SourceRegistry:
    def __init__(self):self._sources={}
    def register(self,source:SourceConfig):
        if not source.key.strip():raise ValueError("source key required")
        if source.enabled and not source.permission_basis.strip():raise ValueError("enabled source requires permission basis")
        self._sources[source.key]=source;return source
    def get(self,key:str)->Optional[SourceConfig]:return self._sources.get(key)
    def enabled(self):return [s for s in self._sources.values() if s.enabled]
    def assert_ingestion_allowed(self,key:str):
        source=self.get(key)
        if not source:raise ValueError("unknown source")
        if not source.enabled:raise PermissionError("source is disabled")
        if not source.permission_basis.strip():raise PermissionError("permission basis missing")
        return source

def default_registry():
    r=SourceRegistry()
    r.register(SourceConfig("euroteams-existing","Euroteams existing candidate database","FIRST_PARTY",True,"DATABASE_IMPORT","existing Euroteams recruitment relationship",730,("LT","LV","PL","RO","BG","ES","IT")))
    r.register(SourceConfig("euroteams-portal","Euroteams worker self-registration","FIRST_PARTY",True,"API","candidate self-registration / consent",730,("LT","LV","PL","RO","BG","ES","IT")))
    r.register(SourceConfig("licensed-jobboard","Licensed job board feed","PARTNER",False,"API","",365,(),"Enable only after provider/API agreement is configured"))
    return r
