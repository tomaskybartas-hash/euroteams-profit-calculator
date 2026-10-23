"""Collector preview runtime hook.

Python imports usercustomize after sitecustomize. This lets the collector layer install
without rewriting the large production sitecustomize patch and keeps the integration
isolated to the development branch.
"""
from pathlib import Path

root=Path.cwd()
app_dir=root/"app"
if not app_dir.exists():
    candidate=root/"workforce_live_prod_clean"/"app"
    if candidate.exists():app_dir=candidate

try:
    from collector.runtime_install import install
    ok=install(app_dir,root)
    print(f"WORKFORCE_COLLECTOR_INSTALLED={ok}")
except Exception as exc:
    print(f"WORKFORCE_COLLECTOR_INSTALL_ERROR={type(exc).__name__}: {exc}")
