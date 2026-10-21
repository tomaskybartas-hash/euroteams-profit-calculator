from pathlib import Path

# Runtime upgrade layer for Workforce Live production preview.
# Render extracts the packaged app during build; this file applies the next-stage
# source upgrade before uvicorn imports app.main.

root = Path.cwd()
app_dir = root / "app"
if not app_dir.exists():
    candidate = root / "workforce_live_prod_clean" / "app"
    if candidate.exists():
        app_dir = candidate

main_path = app_dir / "main.py"
models_path = app_dir / "models.py"
templates_dir = app_dir / "templates"

if main_path.exists() and models_path.exists():
    main = main_path.read_text()
    models = models_path.read_text()

    if "# WORKFORCE_LIVE_STAGE3" not in main:
        if "class ScreeningResponse(Base):" not in models:
            models += '''\n\nclass ScreeningResponse(Base):\n    __tablename__ = "screening_responses"\n    id: Mapped[int] = mapped_column(Integer, primary_key=True)\n    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, default=1)\n    candidate_id: Mapped[int] = mapped_column(ForeignKey("project_candidates.id"), index=True)\n    worker_id: Mapped[int] = mapped_column(ForeignKey("workers.id"), index=True)\n    question_key: Mapped[str] = mapped_column(String(80), index=True)\n    question_text: Mapped[str] = mapped_column(Text)\n    answer: Mapped[str] = mapped_column(Text, default="")\n    status: Mapped[str] = mapped_column(String(30), default="ANSWERED")\n    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)\n'''
            models_path.write_text(models)

        main = main.replace(
            "    AvailabilityEvent, Message, WorkerDocument, AuditLog\n)",
            "    AvailabilityEvent, Message, WorkerDocument, AuditLog, ScreeningResponse\n)"
        )

        old_ctx = 'def page_ctx(request: Request, user=None, **kwargs):\n    return {"request": request, "user": user, **kwargs}\n'
        new_ctx = '''def require_roles(user, *roles):\n    if not user or user.role not in roles:\n        raise HTTPException(status_code=403, detail="Not permitted")\n    return user\n\n\ndef audit_event(db: Session, user, action: str, entity_type: str = "", entity_id: str = "", details: str = ""):\n    db.add(AuditLog(tenant_id=user.tenant_id, actor=user.email, action=action, entity_type=entity_type, entity_id=entity_id, details=details))\n    db.commit()\n\n\ndef page_ctx(request: Request, user=None, **kwargs):\n    return {"request": request, "user": user, **kwargs}\n'''
        main = main.replace(old_ctx, new_ctx)

        old_portal = '''    projects=db.query(ProjectCandidate).join(ProjectCandidate.project).filter(ProjectCandidate.worker_id==w.id,ProjectCandidate.stage.in_(["MATCHED","CONTACTED","INTERESTED"])).order_by(ProjectCandidate.match_score.desc()).limit(10).all()\n    return templates.TemplateResponse(request, "worker_portal.html", page_ctx(request,None,worker=w,candidates=projects,confidence=availability_confidence(w)))'''
        new_portal = '''    projects=db.query(ProjectCandidate).join(ProjectCandidate.project).filter(ProjectCandidate.worker_id==w.id,ProjectCandidate.stage.in_(["MATCHED","CONTACTED","INTERESTED","QUALIFIED"])).order_by(ProjectCandidate.match_score.desc()).limit(10).all()\n    screening={}\n    for c in projects:\n        screening[c.id]=db.query(ScreeningResponse).filter(ScreeningResponse.candidate_id==c.id).order_by(ScreeningResponse.id).all()\n    return templates.TemplateResponse(request, "worker_portal.html", page_ctx(request,None,worker=w,candidates=projects,screening=screening,confidence=availability_confidence(w)))'''
        main = main.replace(old_portal, new_portal)

        extra = r'''
@app.get("/consents", response_class=HTMLResponse)
def consent_center(request: Request, db: Session = Depends(get_db)):
    user=current_user(request,db)
    if not user:return RedirectResponse("/login",303)
    rows=(db.query(Consent, Worker).join(Worker, Consent.worker_id==Worker.id)
          .filter(Consent.tenant_id==user.tenant_id)
          .order_by(Consent.created_at.desc()).limit(300).all())
    return templates.TemplateResponse(request, "consents.html", page_ctx(request,user,rows=rows))

@app.get("/outbox", response_class=HTMLResponse)
def outbox(request: Request, db: Session = Depends(get_db)):
    user=current_user(request,db)
    if not user:return RedirectResponse("/login",303)
    rows=(db.query(Message, Worker, Project)
          .join(Worker, Message.worker_id==Worker.id)
          .outerjoin(Project, Message.project_id==Project.id)
          .filter(Message.tenant_id==user.tenant_id)
          .order_by(Message.created_at.desc()).limit(300).all())
    return templates.TemplateResponse(request, "outbox.html", page_ctx(request,user,rows=rows))

@app.get("/team", response_class=HTMLResponse)
def team(request: Request, db: Session = Depends(get_db)):
    user=current_user(request,db)
    if not user:return RedirectResponse("/login",303)
    require_roles(user,"admin")
    users=db.query(AppUser).filter(AppUser.tenant_id==user.tenant_id).order_by(AppUser.full_name).all()
    return templates.TemplateResponse(request, "team.html", page_ctx(request,user,users=users))

@app.post("/team/new")
def team_new(request: Request, full_name:str=Form(...), email:str=Form(...), password:str=Form(...), role:str=Form("recruiter"), db:Session=Depends(get_db)):
    user=current_user(request,db)
    if not user:return RedirectResponse("/login",303)
    require_roles(user,"admin")
    role=role if role in {"admin","recruiter","viewer"} else "viewer"
    if db.query(AppUser).filter(AppUser.email==email.lower().strip()).first():
        return RedirectResponse("/team?error=exists",303)
    new=AppUser(tenant_id=user.tenant_id,email=email.lower().strip(),full_name=full_name,password_hash=hash_password(password),role=role,active=True)
    db.add(new);db.commit();db.refresh(new)
    audit_event(db,user,"TEAM_USER_CREATED","user",str(new.id),f"{new.email} · {new.role}")
    return RedirectResponse("/team",303)

@app.post("/team/{user_id}/role")
def team_role(user_id:int, request:Request, role:str=Form(...), active:bool=Form(False), db:Session=Depends(get_db)):
    user=current_user(request,db)
    if not user:return RedirectResponse("/login",303)
    require_roles(user,"admin")
    target=db.query(AppUser).filter(AppUser.id==user_id,AppUser.tenant_id==user.tenant_id).first()
    if not target:raise HTTPException(404)
    if role in {"admin","recruiter","viewer"}:target.role=role
    target.active=active
    db.commit();audit_event(db,user,"TEAM_USER_UPDATED","user",str(target.id),f"role={target.role}; active={target.active}")
    return RedirectResponse("/team",303)

SCREENING_QUESTIONS=[
    ("start_date","Can you start on the required project date?"),
    ("rate","Do you accept the offered net hourly rate?"),
    ("rotation","Do you accept the project rotation?"),
    ("experience","Briefly describe your most relevant experience for this work."),
    ("documents","Are your ID, certificates and required work documents currently valid?"),
]

@app.get("/candidates/{candidate_id}/screening", response_class=HTMLResponse)
def candidate_screening(candidate_id:int, request:Request, db:Session=Depends(get_db)):
    user=current_user(request,db)
    if not user:return RedirectResponse("/login",303)
    c=db.get(ProjectCandidate,candidate_id)
    if not c:raise HTTPException(404)
    p=db.get(Project,c.project_id)
    if p.tenant_id!=user.tenant_id:raise HTTPException(403)
    answers=db.query(ScreeningResponse).filter(ScreeningResponse.candidate_id==c.id).order_by(ScreeningResponse.id).all()
    return templates.TemplateResponse(request,"screening.html",page_ctx(request,user,candidate=c,project=p,worker=c.worker,answers=answers,questions=SCREENING_QUESTIONS))

@app.post("/candidates/{candidate_id}/screening/create")
def candidate_screening_create(candidate_id:int, request:Request, db:Session=Depends(get_db)):
    user=current_user(request,db)
    if not user:return RedirectResponse("/login",303)
    require_roles(user,"admin","recruiter")
    c=db.get(ProjectCandidate,candidate_id)
    if not c:raise HTTPException(404)
    p=db.get(Project,c.project_id)
    if p.tenant_id!=user.tenant_id:raise HTTPException(403)
    existing={x.question_key for x in db.query(ScreeningResponse).filter(ScreeningResponse.candidate_id==c.id).all()}
    for key,text in SCREENING_QUESTIONS:
        if key not in existing:
            db.add(ScreeningResponse(tenant_id=user.tenant_id,candidate_id=c.id,worker_id=c.worker_id,question_key=key,question_text=text,status="PENDING"))
    c.screening_status="IN_PROGRESS";db.commit();audit_event(db,user,"SCREENING_STARTED","candidate",str(c.id),p.name)
    return RedirectResponse(f"/candidates/{c.id}/screening",303)

@app.post("/worker/{token}/candidate/{candidate_id}/screening")
async def worker_screening_reply(token:str,candidate_id:int,request:Request,db:Session=Depends(get_db)):
    w=db.query(Worker).filter(Worker.self_service_token==token).first();c=db.get(ProjectCandidate,candidate_id)
    if not w or not c or c.worker_id!=w.id:raise HTTPException(404)
    form=await request.form()
    rows=db.query(ScreeningResponse).filter(ScreeningResponse.candidate_id==c.id).all()
    for r in rows:
        value=str(form.get(f"q_{r.id}","")).strip()
        if value:
            r.answer=value;r.status="ANSWERED"
    db.commit()
    rows=db.query(ScreeningResponse).filter(ScreeningResponse.candidate_id==c.id).all()
    if rows and all(x.status=="ANSWERED" for x in rows):
        c.screening_status="COMPLETE"
        if c.stage in {"MATCHED","CONTACTED","INTERESTED"}:c.stage="QUALIFIED"
        db.add(Message(tenant_id=w.tenant_id,worker_id=w.id,project_id=c.project_id,candidate_id=c.id,direction="IN",channel="Web",body="Structured screening completed",provider_status="RECEIVED"))
        db.commit()
    return RedirectResponse(f"/worker/{token}",303)

@app.post("/candidates/{candidate_id}/screening/answer")
def admin_screening_answer(candidate_id:int,request:Request,question_id:int=Form(...),answer:str=Form(...),db:Session=Depends(get_db)):
    user=current_user(request,db)
    if not user:return RedirectResponse("/login",303)
    require_roles(user,"admin","recruiter")
    c=db.get(ProjectCandidate,candidate_id);r=db.get(ScreeningResponse,question_id)
    if not c or not r or r.candidate_id!=c.id:raise HTTPException(404)
    p=db.get(Project,c.project_id)
    if p.tenant_id!=user.tenant_id:raise HTTPException(403)
    r.answer=answer.strip();r.status="ANSWERED" if r.answer else "PENDING";db.commit()
    all_rows=db.query(ScreeningResponse).filter(ScreeningResponse.candidate_id==c.id).all()
    if all_rows and all(x.status=="ANSWERED" for x in all_rows):
        c.screening_status="COMPLETE"
        if c.stage in {"MATCHED","CONTACTED","INTERESTED"}:c.stage="QUALIFIED"
        db.commit()
    return RedirectResponse(f"/candidates/{c.id}/screening",303)

'''
        main = main.replace('@app.get("/api/health")\n', extra + '@app.get("/api/health")\n')

        for marker, call in [
            ('def worker_create(', 'require_roles(user,"admin","recruiter")'),
            ('def worker_availability(', 'require_roles(user,"admin","recruiter")'),
            ('def worker_consent(', 'require_roles(user,"admin","recruiter")'),
            ('def worker_document_upload(', 'require_roles(user,"admin","recruiter")'),
            ('def document_verify(', 'require_roles(user,"admin","recruiter")'),
            ('def workers_import(', 'require_roles(user,"admin","recruiter")'),
            ('def project_create(', 'require_roles(user,"admin","recruiter")'),
            ('def project_start(', 'require_roles(user,"admin","recruiter")'),
            ('def candidate_send(', 'require_roles(user,"admin","recruiter")'),
            ('def update_candidate_stage(', 'require_roles(user,"admin","recruiter")'),
            ('def crew_create(', 'require_roles(user,"admin","recruiter")'),
        ]:
            idx=main.find(marker)
            if idx < 0: continue
            end=main.find('\n@app.',idx)
            block=main[idx:end if end!=-1 else len(main)]
            if call in block: continue
            target='    if not user:return RedirectResponse("/login",303)\n'
            pos=main.find(target,idx,end if end!=-1 else len(main))
            if pos!=-1:
                pos2=pos+len(target)
                main=main[:pos2]+'    '+call+'\n'+main[pos2:]

        main = '# WORKFORCE_LIVE_STAGE3\n' + main
        main_path.write_text(main)

        base = templates_dir / "base.html"
        if base.exists():
            text=base.read_text()
            if '/consents' not in text:
                text=text.replace('<a href="/audit"', '<a href="/consents">Consent Center</a><a href="/outbox">Outbox</a>{% if user and user.role==\'admin\' %}<a href="/team">Team</a>{% endif %}<a href="/audit"')
                base.write_text(text)

        (templates_dir / "consents.html").write_text('''{% extends 'base.html' %}{% block content %}<div class="topbar"><div><h1>Consent Center</h1><p>Auditable communication permissions by worker, purpose and channel.</p></div></div><section class="card"><table><thead><tr><th>Worker</th><th>Channel</th><th>Purpose</th><th>Status</th><th>Source</th><th>Recorded</th></tr></thead><tbody>{% for c,w in rows %}<tr><td><a href="/workers/{{w.id}}"><strong>{{w.full_name}}</strong></a><small>{{w.country}}</small></td><td>{{c.channel}}</td><td>{{c.purpose}}</td><td><span class="pill {% if c.granted and not c.revoked_at %}good{% endif %}">{{'GRANTED' if c.granted and not c.revoked_at else 'REVOKED'}}</span></td><td>{{c.source}}<small>{{c.text_version}}</small></td><td>{{c.created_at.strftime('%Y-%m-%d %H:%M')}}</td></tr>{% else %}<tr><td colspan="6">No consent records.</td></tr>{% endfor %}</tbody></table></section>{% endblock %}''')
        (templates_dir / "outbox.html").write_text('''{% extends 'base.html' %}{% block content %}<div class="topbar"><div><h1>Communication Outbox</h1><p>All outbound/inbound recruitment messages and provider states.</p></div></div><section class="card"><table><thead><tr><th>Time</th><th>Worker</th><th>Project</th><th>Channel</th><th>Direction</th><th>Status</th><th>Message</th></tr></thead><tbody>{% for m,w,p in rows %}<tr><td>{{m.created_at.strftime('%Y-%m-%d %H:%M')}}</td><td><a href="/workers/{{w.id}}">{{w.full_name}}</a></td><td>{{p.name if p else '—'}}</td><td>{{m.channel}}</td><td>{{m.direction}}</td><td><span class="pill {% if m.provider_status.startswith('SENT') or m.provider_status=='RECEIVED' %}good{% endif %}">{{m.provider_status}}</span></td><td style="max-width:420px">{{m.body}}</td></tr>{% else %}<tr><td colspan="7">No messages yet.</td></tr>{% endfor %}</tbody></table></section>{% endblock %}''')
        (templates_dir / "team.html").write_text('''{% extends 'base.html' %}{% block content %}<div class="topbar"><div><h1>Team & Roles</h1><p>Role-based access: admin, recruiter and viewer.</p></div></div><div class="grid-2"><section class="card"><h2>Team members</h2><table><thead><tr><th>Name</th><th>Email</th><th>Role / access</th></tr></thead><tbody>{% for u in users %}<tr><td>{{u.full_name}}</td><td>{{u.email}}</td><td><form method="post" action="/team/{{u.id}}/role" class="inline-form"><select name="role"><option {% if u.role=='admin' %}selected{% endif %}>admin</option><option {% if u.role=='recruiter' %}selected{% endif %}>recruiter</option><option {% if u.role=='viewer' %}selected{% endif %}>viewer</option></select><label class="check"><input type="checkbox" name="active" {% if u.active %}checked{% endif %}> Active</label><button class="btn tiny">Save</button></form></td></tr>{% endfor %}</tbody></table></section><section class="card"><h2>Add team member</h2><form method="post" action="/team/new"><label>Full name<input name="full_name" required></label><label>Email<input type="email" name="email" required></label><label>Temporary password<input type="password" name="password" minlength="10" required></label><label>Role<select name="role"><option>recruiter</option><option>viewer</option><option>admin</option></select></label><button class="btn primary">Create user</button></form><p><small>Recruiters can operate staffing workflows. Viewers are read-only by policy; admin manages users and settings.</small></p></section></div>{% endblock %}''')
        (templates_dir / "screening.html").write_text('''{% extends 'base.html' %}{% block content %}<div class="topbar"><div><h1>Candidate Screening</h1><p>{{worker.full_name}} · {{project.name}}</p></div><a class="btn" href="/projects/{{project.id}}">Back to project</a></div><div class="grid-2"><section class="card"><h2>Screening status</h2><dl class="facts"><dt>Candidate stage</dt><dd>{{candidate.stage}}</dd><dt>Screening</dt><dd>{{candidate.screening_status}}</dd><dt>Match score</dt><dd>{{candidate.match_score|round(1)}}%</dd><dt>Notes</dt><dd>{{candidate.notes}}</dd></dl>{% if not answers %}<form method="post" action="/candidates/{{candidate.id}}/screening/create"><button class="btn primary">Start structured screening</button></form>{% endif %}</section><section class="card"><h2>Questions & answers</h2>{% for r in answers %}<div class="message"><span>{{r.question_text}}</span><form method="post" action="/candidates/{{candidate.id}}/screening/answer"><input type="hidden" name="question_id" value="{{r.id}}"><textarea name="answer" placeholder="Record candidate answer">{{r.answer}}</textarea><button class="btn tiny">Save answer</button></form></div>{% else %}<div class="empty">Screening has not started.</div>{% endfor %}</section></div>{% endblock %}''')

        project_tpl = templates_dir / "project_detail.html"
        if project_tpl.exists():
            text=project_tpl.read_text()
            if '/screening' not in text:
                text=text.replace('{% endblock %}', '<section class="card mt"><h2>Structured screening</h2>{% for c in candidates[:20] %}<div class="timeline"><strong>{{c.worker.full_name}}</strong><span>{{c.stage}} · {{c.screening_status}}</span><a class="btn tiny" href="/candidates/{{c.id}}/screening">Open screening</a></div>{% else %}<div class="empty">Start recruitment to create candidates.</div>{% endfor %}</section>{% endblock %}')
                project_tpl.write_text(text)

        portal_tpl = templates_dir / "worker_portal.html"
        if portal_tpl.exists():
            text=portal_tpl.read_text()
            needle='<form method="post" action="/worker/{{worker.self_service_token}}/candidate/{{c.id}}/reply"><button name="reply" value="YES" class="btn primary">Interested</button><button name="reply" value="NO" class="btn">Not interested</button></form></div>'
            replacement=needle+'{% if screening.get(c.id) %}<div class="card compact"><h3>Project screening</h3><form method="post" action="/worker/{{worker.self_service_token}}/candidate/{{c.id}}/screening">{% for r in screening.get(c.id) %}<label>{{r.question_text}}<textarea name="q_{{r.id}}" {% if r.status==\'ANSWERED\' %}readonly{% endif %}>{{r.answer}}</textarea></label>{% endfor %}{% if c.screening_status!=\'COMPLETE\' %}<button class="btn primary">Submit screening</button>{% else %}<span class="pill good">SCREENING COMPLETE</span>{% endif %}</form></div>{% endif %}'
            if 'Project screening' not in text:
                portal_tpl.write_text(text.replace(needle,replacement))
