from app import app


def test_health():
    client = app.test_client()
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_depositor_data_needs_login():
    # Login pannaama data kekkuren
    client = app.test_client()
    response = client.get("/api/depositor/PILOT1001")
    assert response.status_code == 403


def test_admin_dashboard_needs_login():
    # Admin login illaama dashboard kekkuren
    client = app.test_client()
    response = client.get("/api/admin/dashboard")
    assert response.status_code == 403


def test_wrong_otp_is_rejected():
    client = app.test_client()
    # Mudhalla OTP request pannuren
    client.post("/api/request-otp", json={"depositor_no": "PILOT1001"})
    # Appuram thappaana OTP kudukkuren
    response = client.post(
        "/api/verify-otp",
        json={"depositor_no": "PILOT1001", "otp": "000000"},
    )
    assert response.status_code == 401
def test_metrics_endpoint():
    client = app.test_client()
    client.get("/api/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"http_requests_total" in response.data
