"""Install Worker Collector UI/routes into the extracted Workforce Live app at build time."""
from pathlib import Path
import shutil


def _ensure_fastapi_upload_imports(main: str) -> str:
    """Add UploadFile/File without assuming one exact import ordering."""
    if "UploadFile" in main and "File" in main:
        return main
    lines=main.splitlines()
    for i,line in enumerate(lines):
        if line.startswith("from fastapi import "):
            names=[x.strip() for x in line.split(" import ",1)[1].split(",")]
            for required in ("UploadFile","File"):
                if required not in names:names.append(required)
            lines[i]="from fastapi import "+", ".join(names)
            return "\n".join(lines)+("\n" if main.endswith("\n") else "")
    return "from fastapi import UploadFile, File\n"+main


def install(app_dir: Path, repo_root: Path) -> bool:
    main_path=app_dir/"main.py";templates=app_dir/"templates";base=templates/"base.html"
    source_package=repo_root/"collector"
    routes=source_package/"runtime_routes.pyfrag";template=source_package/"collector.html"
    if not main_path.exists() or not routes.exists() or not template.exists():return False
    main=main_path.read_text()
    marker="# WORKFORCE_COLLECTOR_ROUTES_V1"
    if marker not in main:
        frag=routes.read_text()
        anchor='@app.get("/api/health")\n'
        if anchor in main:main=main.replace(anchor,frag+"\n"+anchor)
        else:main += "\n"+frag+"\n"
        main=_ensure_fastapi_upload_imports(main)
        main_path.write_text(main)
    templates.mkdir(parents=True,exist_ok=True)
    (templates/"collector.html").write_text(template.read_text())
    runtime_root=app_dir.parent
    runtime_package=runtime_root/"collector"
    if source_package.resolve()!=runtime_package.resolve():
        shutil.copytree(source_package,runtime_package,dirs_exist_ok=True,ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    if base.exists():
        text=base.read_text()
        if 'href="/collector"' not in text:
            for needle in ['<a href="/projects"','<a href="/workers"']:
                pos=text.find(needle)
                if pos!=-1:
                    text=text[:pos]+'<a href="/collector">Worker Collector</a>'+text[pos:];break
            base.write_text(text)
    return True
