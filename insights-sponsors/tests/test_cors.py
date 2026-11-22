"""A browser app on another origin (Vite dev server, Vercel) must be able to call the API."""


def test_preflight_allows_authorization_header_and_methods(client):
    for method in ("GET", "POST", "DELETE"):
        r = client.options(
            "/me/faves/fact.pktrm.1",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": method,
                     "Access-Control-Request-Headers": "authorization,content-type"},
        )
        assert r.status_code == 200, (method, r.text)
        assert r.headers["access-control-allow-origin"] in ("*", "http://localhost:5173")
        assert "authorization" in r.headers["access-control-allow-headers"].lower()


def test_simple_request_carries_cors_header(client, auth_headers):
    r = client.get("/categories", headers={**auth_headers, "Origin": "https://tquest.vercel.app"})
    assert r.status_code == 200 and "access-control-allow-origin" in r.headers
