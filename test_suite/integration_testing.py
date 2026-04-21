from fastapi.testclient import TestClient
from main import app
import main

client = TestClient(app)

# Full integration test
def test_full_integration_live():
    response = client.get("/risk/from-weather?lat=51.61&lon=-3.98")

    assert response.status_code == 200
    data = response.json()

    assert "risk" in data
    assert "component_risk" in data
    assert "input" in data
    assert "tides" in data
    
    
# Cache integration test
def test_cache_behaviour():
    main.cache.clear()

    url = "/risk/from-weather?lat=51.61&lon=-3.98"

    first = client.get(url).json()
    second = client.get(url).json()

    assert first["cached"] is False
    assert second["cached"] is True
    
    
# Partial failure
def test_tide_failure_integration(monkeypatch):
    async def mock_get_next_tide():
        raise Exception("fail")

    monkeypatch.setattr(main, "get_next_tide", mock_get_next_tide)

    response = client.get("/risk/from-weather?lat=51.61&lon=-3.98")

    assert response.status_code == 200
    assert response.json()["tides"]["tide_state"] is None
    

# Failure to get environmental data
def test_environmental_data_failure(monkeypatch):
    async def mock_get_conditions(lat, lon):
        raise Exception("All providers failed")

    monkeypatch.setattr(main, "get_conditions", mock_get_conditions)

    response = client.get("/risk/from-weather?lat=51.61&lon=-3.98")

    assert response.status_code == 503