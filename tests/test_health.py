def test_health_ok_when_db_reachable(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["environment"] == "development"


def test_security_headers_and_csp(client):
    r = client.get("/health")
    csp = r.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "media-src 'self'" in csp
    assert "script-src 'self' https://telegram.org" in csp
    assert "frame-ancestors" in csp and "telegram.org" in csp
    assert "object-src 'none'" in csp
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
