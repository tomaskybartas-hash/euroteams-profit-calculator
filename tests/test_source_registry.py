import pytest
from collector.source_registry import SourceConfig, SourceRegistry, default_registry


def test_first_party_sources_are_enabled():
    keys={x.key for x in default_registry().enabled()}
    assert "euroteams-existing" in keys
    assert "euroteams-portal" in keys
    assert "licensed-jobboard" not in keys


def test_disabled_source_cannot_ingest():
    registry=default_registry()
    with pytest.raises(PermissionError):registry.assert_ingestion_allowed("licensed-jobboard")


def test_enabled_source_requires_permission_basis():
    registry=SourceRegistry()
    with pytest.raises(ValueError):registry.register(SourceConfig("bad","Bad","PARTNER",True,"API",""))
