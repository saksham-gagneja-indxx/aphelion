"""Tests for CORS validation, security headers and rate limiting.

These cover the three transport-level findings from the security review. The
point of each test is not that the code runs but that the specific attack it
was written against is actually refused.
"""

import os
import tempfile

import pytest

from backend.utils.http_security import (
    SlidingWindowLimiter,
    security_headers,
    validate_cors_origins,
)


@pytest.fixture
def app(monkeypatch, tmp_path):
    """A real app on a throwaway database.

    Guest sign-in writes a row and a media directory per call, and the rate
    limit test deliberately makes a dozen of them - both need to land
    somewhere disposable.
    """
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    monkeypatch.setenv("API_ACCESS_KEY", "test-key-http-security")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("ALLOW_GUEST_ACCESS", "true")
    monkeypatch.setenv("REELS_FOLDER", str(tmp_path / "reels"))

    import backend.utils.database as database

    database._db_instance = None

    from backend.app import create_app

    application = create_app()
    application.config["TESTING"] = True
    yield application

    database._db_instance = None
    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(db_path + suffix)
        except OSError:
            pass


@pytest.fixture
def client(app):
    return app.test_client()


# ------------------------------------------------------------------- CORS

class TestCorsValidation:
    def test_wildcard_is_dropped_not_passed_through(self):
        """'*' plus credentials is the worst possible CORS config."""
        allowed, problems = validate_cors_origins("*", is_production=True)

        assert allowed == []
        assert len(problems) == 1
        assert "'*'" in problems[0]

    def test_wildcard_dropped_in_development_too(self):
        """A wildcard is never safe, and dev configs get copied to prod."""
        allowed, problems = validate_cors_origins("*", is_production=False)

        assert allowed == []
        assert problems

    def test_localhost_refused_in_production(self):
        """The actual finding: localhost:5173 sitting in a prod allowlist."""
        allowed, problems = validate_cors_origins(
            "https://app.example.com,http://localhost:5173", is_production=True
        )

        assert allowed == ["https://app.example.com"]
        assert len(problems) == 1
        assert "localhost:5173" in problems[0]

    def test_all_loopback_spellings_refused(self):
        """127.0.0.1 and ::1 are the same hole as 'localhost'."""
        allowed, problems = validate_cors_origins(
            "http://127.0.0.1:3000,http://[::1]:3000,http://0.0.0.0:8080",
            is_production=True,
        )

        assert allowed == []
        assert len(problems) == 3

    def test_localhost_kept_in_development(self):
        """Refusing it in dev would break every developer's setup."""
        allowed, problems = validate_cors_origins(
            "http://localhost:5173", is_production=False
        )

        assert allowed == ["http://localhost:5173"]
        assert problems == []

    def test_whitespace_and_empties_tolerated(self):
        allowed, problems = validate_cors_origins(
            " https://a.example.com , , https://b.example.com ",
            is_production=True,
        )

        assert allowed == ["https://a.example.com", "https://b.example.com"]
        assert problems == []

    def test_empty_config_yields_empty_allowlist(self):
        """No origins means no CORS headers, which blocks - it does not open."""
        assert validate_cors_origins("", is_production=True) == ([], [])


# ---------------------------------------------------------------- headers

class TestSecurityHeaders:
    def test_clickjacking_is_blocked_by_both_mechanisms(self):
        headers = security_headers(is_production=True)

        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
        assert headers["X-Frame-Options"] == "DENY"

    def test_csp_forbids_inline_script(self):
        """The control that matters: the session token lives in localStorage,
        so any script execution is a full account takeover."""
        csp = security_headers(is_production=True)["Content-Security-Policy"]

        assert "script-src 'self'" in csp
        assert "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]
        assert "'unsafe-eval'" not in csp

    def test_mime_sniffing_disabled(self):
        assert security_headers(True)["X-Content-Type-Options"] == "nosniff"

    def test_referrer_policy_does_not_leak_paths_cross_origin(self):
        assert (
            security_headers(True)["Referrer-Policy"]
            == "strict-origin-when-cross-origin"
        )

    def test_permissions_policy_is_syntactically_valid(self):
        """A bare `payment()` instead of `payment=()` makes browsers discard
        the entire header - every feature silently re-permitted."""
        import re

        policy = security_headers(True)["Permissions-Policy"]
        for directive in policy.split(","):
            assert re.fullmatch(r"\s*[a-z-]+=\([^)]*\)", directive), directive

    def test_csp_permits_every_remote_origin_the_frontend_loads(self):
        """The CSP is written here but enforced against a bundle built
        elsewhere. Read what the frontend actually imports rather than trusting
        that the two stayed in step - the first draft of this CSP would have
        served the whole app in fallback fonts, and nothing would have failed
        loudly."""
        import re
        from pathlib import Path

        css = Path(__file__).parent.parent / "frontend" / "src" / "index.css"
        if not css.is_file():
            pytest.skip("frontend sources not present")

        csp = security_headers(True)["Content-Security-Policy"]
        imported = set(
            re.findall(r"@import\s+url\(['\"]?(https://[^/'\")]+)", css.read_text(encoding="utf-8"))
        )
        assert imported, "expected at least one remote @import to verify against"

        style_src = csp.split("style-src")[1].split(";")[0]
        for origin in imported:
            assert origin in style_src, (
                f"index.css imports a stylesheet from {origin} but style-src "
                f"does not allow it: {style_src.strip()}"
            )

    def test_vercel_headers_match_the_flask_ones(self):
        """The SPA is served by Vercel in the deployed setup, so Flask's
        after_request hook never runs for it - vercel.json is the only thing
        protecting the actual frontend. Two copies of a policy drift; this
        pins them together.

        connect-src is exempt: Vercel's has to additionally allow
        http://localhost:* because the backend currently runs on the operator's
        own machine, and a page on https:// may only reach it because browsers
        treat loopback as a trustworthy origin.
        """
        import json
        from pathlib import Path

        config = Path(__file__).parent.parent / "frontend" / "vercel.json"
        if not config.is_file():
            pytest.skip("frontend deployment config not present")

        rules = json.loads(config.read_text(encoding="utf-8")).get("headers", [])
        assert rules, "vercel.json ships no security headers at all"

        deployed = {h["key"]: h["value"] for h in rules[0]["headers"]}
        expected = security_headers(is_production=True)

        for key, value in expected.items():
            assert key in deployed, f"vercel.json is missing {key}"
            if key != "Content-Security-Policy":
                assert deployed[key] == value, key

        def directives(csp):
            return {
                d.strip().split(" ")[0]: d.strip()
                for d in csp.split(";") if d.strip()
            }

        flask_csp = directives(expected["Content-Security-Policy"])
        vercel_csp = directives(deployed["Content-Security-Policy"])

        assert set(flask_csp) == set(vercel_csp), "the two CSPs list different directives"
        for name, directive in flask_csp.items():
            if name == "connect-src":
                continue
            assert vercel_csp[name] == directive, name

        # The exemption is only for loopback. Anything else added to Vercel's
        # connect-src should have to be justified here too.
        extra = set(vercel_csp["connect-src"].split()) - set(flask_csp["connect-src"].split())
        assert extra <= {"http://localhost:*", "http://127.0.0.1:*"}, extra

    def test_hsts_only_in_production(self):
        """Sending HSTS from a local http server poisons localhost in the
        developer's browser for every other project on the machine."""
        assert "Strict-Transport-Security" in security_headers(True)
        assert "Strict-Transport-Security" not in security_headers(False)


# ----------------------------------------------------------- rate limiting

class TestSlidingWindowLimiter:
    def test_allows_up_to_the_limit_then_refuses(self):
        limiter = SlidingWindowLimiter()

        for _ in range(3):
            allowed, _ = limiter.check("k", limit=3, window_seconds=60)
            assert allowed

        allowed, retry_after = limiter.check("k", limit=3, window_seconds=60)
        assert not allowed
        assert retry_after > 0

    def test_keys_are_independent(self):
        """One noisy client must not lock out everyone else."""
        limiter = SlidingWindowLimiter()

        for _ in range(3):
            limiter.check("noisy", limit=3, window_seconds=60)

        allowed, _ = limiter.check("quiet", limit=3, window_seconds=60)
        assert allowed

    def test_window_expiry_frees_the_slot(self, monkeypatch):
        limiter = SlidingWindowLimiter()
        clock = {"t": 1000.0}
        monkeypatch.setattr(
            "backend.utils.http_security.time.monotonic", lambda: clock["t"]
        )

        for _ in range(2):
            assert limiter.check("k", limit=2, window_seconds=60)[0]
        assert not limiter.check("k", limit=2, window_seconds=60)[0]

        clock["t"] += 61
        assert limiter.check("k", limit=2, window_seconds=60)[0]

    def test_it_slides_rather_than_resetting_in_fixed_buckets(self, monkeypatch):
        """A fixed-bucket limiter lets 2x the limit through at a boundary.
        Prove this one does not."""
        limiter = SlidingWindowLimiter()
        clock = {"t": 1000.0}
        monkeypatch.setattr(
            "backend.utils.http_security.time.monotonic", lambda: clock["t"]
        )

        # Two hits at the very end of the window.
        clock["t"] = 1059.0
        assert limiter.check("k", limit=2, window_seconds=60)[0]
        assert limiter.check("k", limit=2, window_seconds=60)[0]

        # One second later a fixed bucket would roll over and permit 2 more.
        clock["t"] = 1060.0
        assert not limiter.check("k", limit=2, window_seconds=60)[0]

    def test_retry_after_is_actionable(self, monkeypatch):
        limiter = SlidingWindowLimiter()
        clock = {"t": 1000.0}
        monkeypatch.setattr(
            "backend.utils.http_security.time.monotonic", lambda: clock["t"]
        )

        limiter.check("k", limit=1, window_seconds=60)
        clock["t"] += 20

        allowed, retry_after = limiter.check("k", limit=1, window_seconds=60)
        assert not allowed
        # 40s of the window remain; never advise a client to retry immediately.
        assert 1 <= retry_after <= 42

    def test_rejected_requests_do_not_extend_the_penalty(self, monkeypatch):
        """A client that keeps retrying must still get in when the window
        clears - otherwise a polling client locks itself out permanently."""
        limiter = SlidingWindowLimiter()
        clock = {"t": 1000.0}
        monkeypatch.setattr(
            "backend.utils.http_security.time.monotonic", lambda: clock["t"]
        )

        assert limiter.check("k", limit=1, window_seconds=60)[0]

        for _ in range(10):
            clock["t"] += 1
            assert not limiter.check("k", limit=1, window_seconds=60)[0]

        clock["t"] = 1061.0
        assert limiter.check("k", limit=1, window_seconds=60)[0]


# ------------------------------------------------------- wired into the app

class TestAppIntegration:
    """The unit tests above prove the pieces. These prove they are connected -
    a correct limiter nobody registered protects nothing."""

    def test_rules_cover_the_endpoints_the_review_flagged(self):
        from backend.app import RATE_LIMIT_RULES

        limited = {prefix for _, prefix, _, _ in RATE_LIMIT_RULES}
        assert "/api/auth/guest" in limited
        assert "/api/upload" in limited

    def test_every_rule_targets_a_real_url_prefix(self):
        """Guards against a rule silently doing nothing after a route moves."""
        from backend.api.caption_routes import caption_bp
        from backend.api.composer_routes import composer_bp
        from backend.api.guest_routes import guest_bp
        from backend.app import RATE_LIMIT_RULES

        prefixes = {
            guest_bp.url_prefix,
            caption_bp.url_prefix,
            composer_bp.url_prefix,
            "/api/upload",  # on the catch-all api_bp
        }
        for _, prefix, _, _ in RATE_LIMIT_RULES:
            assert prefix in prefixes, f"{prefix} matches no blueprint"

    def test_limits_are_finite_and_positive(self):
        from backend.app import RATE_LIMIT_RULES

        for method, prefix, limit, window in RATE_LIMIT_RULES:
            assert method in ("POST", "GET", "PUT", "DELETE")
            assert limit > 0, prefix
            assert window > 0, prefix

    def test_headers_reach_a_real_response(self, client):
        """Registered as after_request, so even /health carries them."""
        response = client.get("/health")

        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]

    def test_headers_reach_error_responses_too(self, client):
        """An error page is exactly where a reflected payload would land."""
        response = client.get("/api/definitely-not-a-route")

        assert response.status_code >= 400
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_guest_signin_is_rate_limited_end_to_end(self, client):
        """The actual finding: unauthenticated, creates a row and a directory
        per call, previously unmetered."""
        from backend.app import RATE_LIMIT_RULES
        from backend.utils.http_security import reset_limits

        reset_limits()
        limit = next(l for m, p, l, _ in RATE_LIMIT_RULES if p == "/api/auth/guest")

        statuses = [
            client.post("/api/auth/guest", json={}).status_code
            for _ in range(limit + 2)
        ]

        assert 429 in statuses, f"never rate limited: {statuses}"
        assert statuses[-1] == 429
        # The limit must bite only after the allowance, not before.
        assert 429 not in statuses[:limit]

    def test_rate_limited_response_tells_the_client_when_to_retry(self, client):
        from backend.app import RATE_LIMIT_RULES
        from backend.utils.http_security import reset_limits

        reset_limits()
        # Derived, not hardcoded: a hardcoded count silently stops reaching the
        # limit the moment somebody raises it, and the test starts asserting
        # nothing while still passing.
        limit = next(l for m, p, l, _ in RATE_LIMIT_RULES if p == "/api/auth/guest")

        response = None
        for _ in range(limit + 2):
            response = client.post("/api/auth/guest", json={})
            if response.status_code == 429:
                break

        assert response.status_code == 429
        assert int(response.headers["Retry-After"]) > 0
        assert response.get_json()["retry_after_seconds"] > 0

    def test_unlimited_routes_are_untouched(self, client):
        """A limiter that accidentally matched everything would still pass the
        tests above."""
        from backend.utils.http_security import reset_limits

        reset_limits()
        for _ in range(30):
            assert client.get("/health").status_code != 429
