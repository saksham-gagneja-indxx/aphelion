"""Tests for serving the built SPA from Flask.

These exist because of a bug found in review: setting Flask's `static_folder`
with `static_url_path=""` registers an internal "/<path:filename>" rule that
matches client-side routes like /admin BEFORE the SPA fallback, and 404s
because no such file exists. Every deep link and hard refresh broke.

The failure is easy to reintroduce and invisible in development, where Vite
serves the SPA and Flask never sees those paths.
"""

import pathlib

import pytest

DIST = pathlib.Path(__file__).parent.parent / "frontend" / "dist"

pytestmark = pytest.mark.skipif(
    not DIST.is_dir(),
    reason="frontend/dist not built; run `npm run build` in frontend/",
)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("API_ACCESS_KEY", "spa-test-key")

    from backend.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_root_serves_the_spa(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.content_type


@pytest.mark.parametrize("route", ["/admin", "/queue", "/settings", "/analytics"])
def test_client_side_routes_serve_index(client, route):
    """A hard refresh on a client-side route must return the SPA, not a 404."""
    response = client.get(route)
    assert response.status_code == 200, route
    assert "text/html" in response.content_type


def test_static_assets_are_served_with_correct_type(client):
    asset = next((DIST / "assets").glob("*.js"), None)
    if asset is None:
        pytest.skip("no built JS asset found")

    response = client.get(f"/assets/{asset.name}")
    assert response.status_code == 200
    assert "javascript" in response.content_type


def test_unknown_api_route_returns_json_not_html(client):
    """Falling back to index.html here would surface in the browser as an
    'unexpected token <' JSON parse error instead of a clear 404."""
    response = client.get(
        "/api/does-not-exist", headers={"Authorization": "Bearer spa-test-key"}
    )
    assert response.status_code == 404
    assert "application/json" in response.content_type


def test_health_is_not_shadowed_by_the_spa(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert "application/json" in response.content_type


def test_api_auth_still_enforced_with_spa_mounted(client):
    """Mounting a catch-all must not accidentally bypass the auth gate."""
    assert client.get("/api/me").status_code == 401
