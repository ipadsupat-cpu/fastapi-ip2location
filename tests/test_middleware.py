import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi_ip2location import IP2LocationMiddleware

# --- HELPER FACTORY ---
def create_test_app(**middleware_kwargs):
    app = FastAPI()
    app.add_middleware(IP2LocationMiddleware, **middleware_kwargs)
    
    @app.get("/")
    async def root(request: Request):
        return request.state.location
        
    return app

# --- TEST 1: BIN MODE ---
@patch("os.path.exists", return_value=True)
@patch("IP2Location.IP2Location")
def test_middleware_bin_mode(mock_ip2location_class, mock_exists):
    mock_db_instance = MagicMock()
    mock_record = MagicMock()
    mock_record.country_short = "US"
    mock_record.country_long = "United States"
    mock_record.city = "Mountain View"
    mock_db_instance.get_all.return_value = mock_record
    mock_ip2location_class.return_value = mock_db_instance

    app = create_test_app(bin_path="dummy_database.bin", test_ip="8.8.8.8")
    client = TestClient(app)

    # FIX: Send a local IP header so the middleware triggers the test_ip override
    response = client.get("/", headers={"X-Forwarded-For": "127.0.0.1"})
    assert response.status_code == 200
    
    data = response.json()
    assert data["ip"] == "8.8.8.8"
    assert data["country_short"] == "US"
    assert data["city"] == "Mountain View"
    assert data["error"] is None

# --- TEST 2: API MODE ---
@patch("httpx.AsyncClient.get", new_callable=AsyncMock)
def test_middleware_api_mode(mock_http_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "country_code": "JP",
        "country_name": "Japan",
        "city_name": "Tokyo",
        "continent": {"name": "Asia", "code": "AS"}
    }
    mock_response.raise_for_status.return_value = None
    mock_http_get.return_value = mock_response

    app = create_test_app(api_key="dummy_api_key", test_ip="8.8.8.8", language="ja")
    client = TestClient(app)

    # FIX: Send a local IP header so the middleware triggers the test_ip override
    response = client.get("/", headers={"X-Forwarded-For": "127.0.0.1"})
    assert response.status_code == 200
    
    data = response.json()
    assert data["ip"] == "8.8.8.8"
    assert data["country_short"] == "JP"
    assert data["country_long"] == "Japan"
    assert data["city"] == "Tokyo"
    assert data["continent_name"] == "Asia"
    assert data["error"] is None

# --- TEST 3: VALIDATION ERROR ---
def test_middleware_missing_config():
    app = FastAPI()
    
    # FIX: Instantiate the middleware directly to test its __init__ logic
    # instead of relying on FastAPI's lazy test client lifecycle.
    with pytest.raises(ValueError, match="Configuration Error"):
        IP2LocationMiddleware(app=app)