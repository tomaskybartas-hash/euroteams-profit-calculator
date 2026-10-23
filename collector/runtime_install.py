"""Install Worker Collector UI/routes into the extracted Workforce Live app at build time."""
from pathlib import Path


def install(app_dir: Path, repo_root: Path) -> bool:
    main_path=app_dir/"main.py";templates=app_dir/"templates";base=templates/"base.html"
    routes=repo_root/"collector"/"runtime_routes.pyfrag";template=repo_root/"collector"/"collector.html"
    if not main_path.exists() or not routes.exists() or not template.exists():return False
    main=main_path.read_text()
    marker="# WORKFORCE_COLLECTOR_ROUTES_V1"
    if marker not in main:
        frag=routes.read_text()
        anchor='@app.get("/api/health")\n'
        if anchor in main:main=main.replace(anchor,frag+"\n"+anchor)
        else:main += "\n"+frag+"\n"
        # UploadFile/File are needed by the import route. Extend the common FastAPI import when possible.
        main=main.replace("from fastapi import FastAPI, Request, Form, Depends, HTTPException", "from fastapi import FastAPI, Request, Form, Depends, HTTPException, UploadFile, File")
        main_path.write_text(main)
    templates.mkdir(parents=True,exist_ok=True)
    (templates/"collector.html").write_text(template.read_text())
    if base.exists():
        text=base.read_text()
        if 'href="/collector"' not in text:
            for needle in ['<a href="/projects"','<a href="/workers"']:
                pos=text.find(needle)
                if pos!=-1:
                    text=text[:pos]+'<a href="/collector">Worker Collector</a>'+text[pos:];break
            base.write_text(text)
    return True
