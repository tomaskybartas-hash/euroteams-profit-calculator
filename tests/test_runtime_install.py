from pathlib import Path
from collector.runtime_install import install


def test_runtime_install_adds_routes_template_nav_and_is_idempotent(tmp_path: Path):
    app=tmp_path/"app";templates=app/"templates";templates.mkdir(parents=True)
    (app/"main.py").write_text('from fastapi import FastAPI, Request, Form, Depends, HTTPException\napp=FastAPI()\n@app.get("/api/health")\ndef health(): return {"ok": True}\n')
    (templates/"base.html").write_text('<nav><a href="/projects">Projects</a></nav>')
    collector=tmp_path/"collector";collector.mkdir()
    source_root=Path(__file__).resolve().parents[1]/"collector"
    (collector/"runtime_routes.pyfrag").write_text((source_root/"runtime_routes.pyfrag").read_text())
    (collector/"collector.html").write_text((source_root/"collector.html").read_text())

    assert install(app,tmp_path) is True
    first=(app/"main.py").read_text()
    assert "UploadFile" in first and "File" in first
    assert first.count("# WORKFORCE_COLLECTOR_ROUTES_V1")==1
    assert 'href="/collector"' in (templates/"base.html").read_text()
    assert (templates/"collector.html").exists()

    assert install(app,tmp_path) is True
    second=(app/"main.py").read_text()
    assert second.count("# WORKFORCE_COLLECTOR_ROUTES_V1")==1
    assert (templates/"base.html").read_text().count('href="/collector"')==1
