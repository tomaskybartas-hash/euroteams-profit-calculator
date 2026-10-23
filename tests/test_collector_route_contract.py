from pathlib import Path


def test_collector_routes_require_registered_source():
    text=Path('collector/runtime_routes.pyfrag').read_text()
    assert 'assert_ingestion_allowed(source_key)' in text
    assert 'source_cfg.permission_basis' in text
    assert '@app.get("/collector/health")' in text


def test_collector_template_uses_source_registry_selector():
    text=Path('collector/collector.html').read_text()
    assert 'name="source_key"' in text
    assert '{% for s in sources %}' in text
    assert 'name="source"' not in text
