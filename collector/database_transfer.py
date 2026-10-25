"""One-time, fail-closed PostgreSQL transfer. Never clears or overwrites data."""
import hashlib
import json
import os
from sqlalchemy import create_engine, select, func, text, inspect


def digest(conn, table):
    rows=conn.execute(select(table).order_by(*table.primary_key.columns)).mappings()
    h=hashlib.sha256();count=0
    for row in rows:
        h.update(json.dumps(dict(row),sort_keys=True,default=str,ensure_ascii=False).encode())
        h.update(b'\n');count+=1
    return count,h.hexdigest()


def transfer(source,target,metadata):
    source_names=set(inspect(source).get_table_names())
    expected=set(metadata.tables)
    if source_names != expected:
        raise RuntimeError('TRANSFER_SCHEMA_MISMATCH')
    metadata.create_all(target)
    with source.connect().execution_options(isolation_level='REPEATABLE READ' if source.dialect.name=='postgresql' else 'SERIALIZABLE') as src:
        with src.begin():
            if source.dialect.name=='postgresql':
                src.execute(text('SET TRANSACTION READ ONLY'))
            before={t.name:digest(src,t) for t in metadata.sorted_tables}
            with target.begin() as dst:
                existing={t.name:digest(dst,t) for t in metadata.sorted_tables}
                if existing==before:return {'status':'ALREADY_VERIFIED','counts':{k:v[0] for k,v in before.items()}}
                if any(v[0] for v in existing.values()):raise RuntimeError('TRANSFER_TARGET_NOT_EMPTY')
                for table in metadata.sorted_tables:
                    result=src.execute(select(table).order_by(*table.primary_key.columns)).mappings()
                    while batch:=result.fetchmany(500):dst.execute(table.insert(),[dict(row) for row in batch])
                after={t.name:digest(dst,t) for t in metadata.sorted_tables}
                if before!=after:raise RuntimeError('TRANSFER_VERIFICATION_FAILED')
                if target.dialect.name=='postgresql':
                    for table in metadata.sorted_tables:
                        for col in table.primary_key.columns:
                            seq=dst.execute(text('SELECT pg_get_serial_sequence(:tbl,:col)'),{'tbl':table.name,'col':col.name}).scalar()
                            if seq:
                                maximum=dst.execute(select(func.max(col))).scalar()
                                dst.execute(text('SELECT setval(CAST(:seq AS regclass),:val,:used)'),{'seq':seq,'val':maximum or 1,'used':maximum is not None})
            return {'status':'VERIFIED','counts':{k:v[0] for k,v in before.items()}}


def run_if_configured():
    value=os.getenv('WORKFORCE_TRANSFER_TARGET','').strip()
    if not value:return
    if os.getenv('WORKFORCE_MAINTENANCE')!='true':raise RuntimeError('TRANSFER_REQUIRES_MAINTENANCE')
    from sqlalchemy.engine import make_url
    url=make_url(value)
    if not url.host or not url.host.endswith('.neon.tech') or url.query.get('sslmode')!='require':
        raise RuntimeError('TRANSFER_INVALID_TARGET')
    from app.db import engine,Base
    target=create_engine(value,pool_pre_ping=True,hide_parameters=True)
    try:
        result=transfer(engine,target,Base.metadata)
        print('WORKFORCE_DATABASE_TRANSFER='+json.dumps(result,sort_keys=True),flush=True)
    except Exception as exc:
        # Connection exceptions may contain credentials: emit only safe error type.
        raise RuntimeError('WORKFORCE_TRANSFER_FAILED_'+type(exc).__name__) from None
    finally:target.dispose()


def install(app):
    from fastapi.responses import JSONResponse
    @app.middleware('http')
    async def maintenance(request,call_next):
        if os.getenv('WORKFORCE_MAINTENANCE')=='true' and request.url.path!='/collector/ready':
            return JSONResponse({'detail':'Database maintenance. Please try again shortly.'},status_code=503,headers={'Retry-After':'120','Cache-Control':'no-store'})
        return await call_next(request)
    app.router.on_startup.insert(0,run_if_configured)
