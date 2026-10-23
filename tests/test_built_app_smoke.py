from fastapi.testclient import TestClient
from app.main import app


def test_collector_health_and_login_surface():
    client=TestClient(app)
    health=client.get('/collector/health')
    assert health.status_code==200
    payload=health.json()
    assert payload['ok'] is True
    assert payload['module']=='worker-collector-v1'
    assert 'euroteams-existing' in payload['enabled_sources']
    login=client.get('/login')
    assert login.status_code==200
    assert 'Euroteams' in login.text
    protected=client.get('/collector',follow_redirects=False)
    assert protected.status_code in (302,303,307)
    assert '/login' in protected.headers.get('location','')
