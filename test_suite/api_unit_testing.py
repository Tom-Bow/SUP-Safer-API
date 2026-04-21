from fastapi.testclient import TestClient
from main import app
import main


client = TestClient(app)


# -----------------------------
# Basic route tests
# -----------------------------
def test_health_route():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# -----------------------------
# Manual risk endpoint
# -----------------------------
def test_manual_risk_route():
    response = client.get(
        "/risk",
        params={
            "wind": 10.0,
            "wind_dir": 10,
            "wave": 0.2,
            "tide_flow": 0.3
        }
    )

    assert response.status_code == 200

    data = response.json()
    assert "risk" in data
    assert "components" in data
    assert "max_severity" in data


# -----------------------------
# /risk/from-weather success case
# -----------------------------
def test_risk_from_weather_success(monkeypatch):
    async def mock_get_conditions(lat, lon):
        return {
            "wind": 9.6,
            "wind_dir": 338,
            "wave": 0.3,
            "tide_flow": 0.43,
            "requested_at": "2026-04-14T21:57:09Z",
            "source": "open-meteo",
            "fresh": True,
            "cached": False,
            "fallback": False,
            "water_temp": 10.4
        }

    async def mock_get_next_tide():
        return {
            "tide_state": "Rising",
            "next_tide": {
                "time": "2026-04-15T16:55:00+00:00",
                "type": "High",
                "height": 8.81
            }
        }

    monkeypatch.setattr(main, "get_conditions", mock_get_conditions)
    monkeypatch.setattr(main, "get_next_tide", mock_get_next_tide)

    response = client.get("/risk/from-weather?lat=51.61&lon=-3.98")

    assert response.status_code == 200

    data = response.json()

    assert "risk" in data
    assert "component_risk" in data
    assert data["source"] == "open-meteo"
    assert data["fresh"] is True
    assert data["cached"] is False
    assert data["fallback"] is False

    assert "input" in data
    assert data["input"]["wind"] == 9.6
    assert data["input"]["wave"] == 0.3
    assert data["input"]["tide_flow"] == 0.43
    assert data["input"]["wind_dir"] == 338

    assert "tides" in data
    assert data["tides"]["tide_state"] == "Rising"
    assert data["tides"]["water_temp"] == 10.4
    assert data["tides"]["next_tide"]["type"] == "High"


# -----------------------------
# Cached response case
# -----------------------------
def test_risk_from_weather_cached(monkeypatch):
    async def mock_get_conditions(lat, lon):
        return {
            "wind": 13.6,
            "wind_dir": 34,
            "wave": 0.94,
            "tide_flow": 1.62,
            "requested_at": "2026-04-15T13:01:39Z",
            "source": "open-meteo",
            "fresh": True,
            "cached": True,
            "fallback": False,
            "water_temp": 10.4
        }

    async def mock_get_next_tide():
        return {
            "tide_state": "Rising",
            "next_tide": {
                "time": "2026-04-15T16:55:00+00:00",
                "type": "High",
                "height": 8.81
            }
        }

    monkeypatch.setattr(main, "get_conditions", mock_get_conditions)
    monkeypatch.setattr(main, "get_next_tide", mock_get_next_tide)

    response = client.get("/risk/from-weather?lat=51.61&lon=-3.98")

    assert response.status_code == 200

    data = response.json()
    assert data["cached"] is True
    assert data["fresh"] is True
    assert data["fallback"] is False


# -----------------------------
# Fallback response case
# -----------------------------
def test_risk_from_weather_fallback(monkeypatch):
    async def mock_get_conditions(lat, lon):
        return {
            "wind": 15.0,
            "wind_dir": 180,
            "wave": 0.8,
            "tide_flow": 1.0,
            "requested_at": "2026-04-15T13:01:39Z",
            "source": "open-meteo",
            "fresh": False,
            "cached": False,
            "fallback": True,
            "water_temp": 10.1
        }

    async def mock_get_next_tide():
        return {
            "tide_state": "Falling",
            "next_tide": {
                "time": "2026-04-15T22:10:00+00:00",
                "type": "Low",
                "height": 2.1
            }
        }

    monkeypatch.setattr(main, "get_conditions", mock_get_conditions)
    monkeypatch.setattr(main, "get_next_tide", mock_get_next_tide)

    response = client.get("/risk/from-weather?lat=51.61&lon=-3.98")

    assert response.status_code == 200

    data = response.json()
    assert data["fallback"] is True
    assert data["fresh"] is False
    assert data["cached"] is False
    assert data["tides"]["tide_state"] == "Falling"


# -----------------------------
# Failure case when get_conditions fails
# -----------------------------
def test_risk_from_weather_failure(monkeypatch):
    async def mock_get_conditions(lat, lon):
        raise Exception("All providers failed!")

    monkeypatch.setattr(main, "get_conditions", mock_get_conditions)

    response = client.get("/risk/from-weather?lat=51.61&lon=-3.98")

    assert response.status_code == 503 # Service Unavailable


# -----------------------------
# Failure case when tide fetch fails
# -----------------------------
def test_risk_from_weather_tide_failure(monkeypatch):
    async def mock_get_conditions(lat, lon):
        return {
            "wind": 9.6,
            "wind_dir": 338,
            "wave": 0.3,
            "tide_flow": 0.43,
            "requested_at": "2026-04-14T21:57:09Z",
            "source": "open-meteo",
            "fresh": True,
            "cached": False,
            "fallback": False,
            "water_temp": 10.4
        }

    async def mock_get_next_tide():
        raise Exception("UKHO unavailable")

    monkeypatch.setattr(main, "get_conditions", mock_get_conditions)
    monkeypatch.setattr(main, "get_next_tide", mock_get_next_tide)

    response = client.get("/risk/from-weather?lat=51.61&lon=-3.98")

    assert response.status_code == 200
    #but
    body = response.json()
    assert body["risk"] is not None
    assert body["tides"]["tide_state"] is None
    assert body["tides"]["next_tide"] is None