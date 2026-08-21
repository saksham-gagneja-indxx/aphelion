"""
Main Flask Application for Aphelion
Entry point for the entire application
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, send_file, send_from_directory
from flask_cors import CORS
from backend.utils.config import (
    get_settings,
    validate_settings,
    instagram_configured,
    linkedin_configured,
    is_placeholder,
)
from backend.utils.logger import setup_logging, get_logger
from backend.utils.database import init_db, get_db
from backend.utils.http_security import (
    enforce as rate_limit_enforce,
    security_headers,
    validate_cors_origins,
)


# (method, path prefix, max requests, window in seconds). First match wins, so
# the more specific prefix must come first.
#
# Guest sign-in is the one rule counted by IP rather than by user - it is what
# an anonymous visitor calls to GET a session, so there is no user yet. That
# makes it the rule most likely to hit an innocent bystander: an office, campus
# or mobile carrier behind one NAT shares a single counter. Hence 25 rather
# than the ~10 abuse alone would justify. Anyone caught by it gets a 429 with
# a Retry-After rather than a dead button, and the ceiling still caps an
# attacker at a few hundred throwaway rows a day instead of unbounded.
RATE_LIMIT_RULES = (
    ("POST", "/api/auth/guest", 25, 3600),
    ("POST", "/api/upload", 20, 3600),
    ("POST", "/api/captions", 30, 3600),
    ("POST", "/api/composer", 60, 3600),
)

_rate_limit_hook = rate_limit_enforce(RATE_LIMIT_RULES)


# Headroom for multipart envelope overhead on top of the configured file-size
# limit. Generous on purpose: it only affects where the transport-level cutoff
# sits, while the real per-file limit is enforced in ReelManager.validate_video.
MULTIPART_OVERHEAD_BYTES = 1024 * 1024  # 1MB


def create_app():
    """Application factory function"""

    # Initialize logging
    logger = setup_logging()
    logger.info("🚀 Starting Aphelion")

    # Serve the built SPA from this same app when it is present (production
    # image). In development the Vite dev server serves it instead and this
    # directory does not exist, so the block below is skipped.
    frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
    serve_frontend = frontend_dist.is_dir()

    # static_folder is deliberately disabled. Setting it with static_url_path=""
    # makes Flask register its own "/<path:filename>" rule, which matches
    # client-side routes like /admin before the SPA fallback below and 404s
    # because no such file exists - breaking every deep link and hard refresh.
    # Serving the files explicitly keeps routing precedence in one place.
    app = Flask(__name__, static_folder=None)

    # Load configuration
    settings = get_settings()
    app.config["SECRET_KEY"] = settings.secret_key
    app.config["DEBUG"] = settings.debug
    app.config["JSON_SORT_KEYS"] = False

    # Reject oversized uploads at the transport layer instead of streaming the
    # whole body to disk and only then failing validation. The allowance on top
    # of max_upload_size covers multipart framing (boundaries, headers, the
    # user_id field) so a file exactly at the limit still succeeds.
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_size + MULTIPART_OVERHEAD_BYTES

    # Restrict CORS to known frontend origins. A wildcard here would let any
    # website a user visits issue requests against this API from their browser.
    #
    # The allowlist is validated rather than trusted: a wildcard is dropped
    # outright, and in production so is any localhost origin. Both were
    # reachable purely by editing an env var, and both hand a signed-in user's
    # session to code the operator never intended to trust.
    is_production = settings.flask_env.lower() in ("production", "prod")
    allowed_origins, cors_problems = validate_cors_origins(
        settings.cors_origins, is_production
    )
    for problem in cors_problems:
        logger.error(f"🚨 {problem}")

    if not allowed_origins:
        # Fail loud, not open. An empty list makes flask-cors send no CORS
        # headers at all, so the browser blocks every cross-origin call - the
        # safe outcome, but one that looks like a mystery app-wide outage
        # unless it is said plainly here.
        logger.error(
            "🚨 No usable CORS origins configured. Every cross-origin browser "
            "request will be blocked. Set CORS_ORIGINS to your frontend URL."
        )

    CORS(
        app,
        resources={r"/api/*": {"origins": allowed_origins}},
        supports_credentials=True,
    )
    logger.info(f"🔒 CORS restricted to: {', '.join(allowed_origins) or '(none)'}")

    # Security headers on every response. Computed once - they do not vary per
    # request - and applied in an after_request hook so error responses and
    # static SPA files carry them too, not just the JSON routes.
    _security_headers = security_headers(is_production)

    @app.after_request
    def apply_security_headers(response):
        for header, value in _security_headers.items():
            # setdefault semantics: never clobber a header a route set
            # deliberately for itself.
            response.headers.setdefault(header, value)
        return response

    # Require an API key on every /api/* route except an explicit allowlist.
    # Registered as a before_request hook rather than per-route decorators so
    # that any endpoint added later is protected by default.
    from backend.utils.security import api_key_configured, authenticate_request

    @app.before_request
    def enforce_authentication():
        return authenticate_request()

    # Rate limits, registered AFTER authentication so `current_user()` is
    # already resolved and a signed-in caller is counted by user id instead of
    # by IP - stable across a phone changing networks, and unspoofable.
    #
    # The numbers are set where a human never reaches them and a script does:
    #
    #   guest sign-in   - public and unauthenticated, so it is the one route an
    #                     anonymous visitor can hammer. Each success creates a
    #                     database row and a sandbox directory, so an unmetered
    #                     endpoint is a free disk-filling primitive.
    #   uploads         - each one costs a large write plus ffmpeg probing and
    #                     thumbnail extraction. The expensive route in the app.
    #   caption/composer- each call spends real money at the model API. This is
    #                     the limit that stops one runaway client from turning
    #                     a bug into a bill.
    @app.before_request
    def enforce_rate_limits():
        return _rate_limit_hook()

    if not api_key_configured():
        logger.error(
            "🚨 API_ACCESS_KEY is not set - all /api/* requests will be "
            "rejected with 503. Set it in the environment."
        )
    else:
        logger.info("🔑 API key authentication enabled")

    # Validate settings
    if not validate_settings():
        logger.error("❌ Configuration validation failed")
        raise RuntimeError("Invalid configuration. Check .env file.")

    # Initialize database
    init_db()

    # Start the scheduler here, not on the first request that happens to touch
    # it. get_scheduler() is lazy and every caller is a request handler, so a
    # process nobody visited had no scheduler at all - it restored nothing and
    # watched no clock. Posts due during a quiet period simply never fired.
    #
    # A scheduler that fails to start must not take the API down with it:
    # uploads, the queue and sign-in all still work without it. Log it loudly
    # and keep serving.
    if settings.scheduler_enabled:
        try:
            from backend.core.scheduler import get_scheduler

            scheduler = get_scheduler()
            logger.info(
                f"⏰ Scheduler started with "
                f"{scheduler.get_jobs_count()['total_jobs']} job(s) restored"
            )
        except Exception:
            logger.exception(
                "🚨 Scheduler failed to start - scheduled posts will NOT publish. "
                "The rest of the API is unaffected."
            )
    else:
        logger.warning("⏸️  SCHEDULER_ENABLED is false - scheduled posts will not publish")

    # Register blueprints
    from backend.api.routes import api_bp
    from backend.api.auth_routes import auth_bp
    from backend.api.linkedin_routes import linkedin_bp
    from backend.api.media_routes import media_bp
    from backend.api.caption_generation_routes import caption_bp
    from backend.api.post_routes import post_bp
    from backend.api.scheduler_routes import scheduler_bp
    from backend.api.admin_routes import admin_bp
    from backend.api.publish_routes import publish_bp
    from backend.api.caption_routes import caption_bp as caption_bp_legacy
    from backend.api.composer_routes import composer_bp
    from backend.api.guest_routes import guest_bp
    from backend.api.console_routes import console_bp
    from backend.api.integrations_routes import integrations_bp
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(linkedin_bp)  # LinkedIn OAuth & credentials
    app.register_blueprint(media_bp)  # Media upload & management
    app.register_blueprint(caption_bp)  # Caption generation
    app.register_blueprint(post_bp)  # Post creation & publishing
    app.register_blueprint(scheduler_bp)  # Scheduling & optimal timing
    app.register_blueprint(admin_bp)
    app.register_blueprint(publish_bp)
    app.register_blueprint(caption_bp_legacy)  # Legacy captions
    app.register_blueprint(composer_bp)
    app.register_blueprint(guest_bp)
    app.register_blueprint(console_bp)
    app.register_blueprint(integrations_bp)

    # Health check endpoint
    @app.route("/health", methods=["GET"])
    def health_check():
        """Health check endpoint"""
        try:
            db = get_db()
            if db.health_check():
                return jsonify({
                    "status": "healthy",
                    "database": "connected",
                    "version": "1.0.0"
                }), 200
            else:
                return jsonify({
                    "status": "degraded",
                    "database": "disconnected"
                }), 503
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({
                "status": "unhealthy",
                "error": "Health check failed"
            }), 500

    # API status endpoint
    @app.route("/api/status", methods=["GET"])
    def api_status():
        """Get API status"""
        settings = get_settings()
        return jsonify({
            "app": "Aphelion",
            "version": "1.0.0",
            "environment": settings.flask_env,
            "debug": settings.debug,
            # ONLY the backend type. This previously returned the raw
            # DATABASE_URL, which embeds the database password - any caller
            # holding the API key could read it, and it would land in logs,
            # screenshots, and error reports. The dialect is all the UI needs.
            "database": settings.database_url.split("://", 1)[0] or "unknown",
            # Placeholder credentials must not report as configured — the
            # React Settings page keys off this to show connection state.
            "instagram_configured": instagram_configured(),
            "claude_configured": not is_placeholder(settings.claude_api_key),
            # Whether the OAuth *app* is set up. Whether any member has
            # authorized it is per-user: /api/auth/linkedin/status.
            "linkedin_configured": linkedin_configured(),
            # Instagram publishing stays off until Meta App Review completes;
            # the UI uses this to avoid offering a platform that cannot work.
            "publishing_enabled": {"linkedin": True, "instagram": False},
        }), 200

    # Serve the SPA. Registered AFTER the API blueprints so their routes win,
    # and it explicitly refuses /api and /health so a typo in an endpoint path
    # returns a JSON 404 instead of silently handing back index.html - which
    # would surface as a confusing "unexpected token <" JSON parse error in the
    # browser rather than a clear 404.
    if serve_frontend:
        index_file = frontend_dist / "index.html"

        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def serve_spa(path):
            if path.startswith("api/") or path == "health":
                return jsonify({"error": "Not found"}), 404

            requested = frontend_dist / path
            if path and requested.is_file():
                return send_from_directory(str(frontend_dist), path)

            # Any other path is a client-side route (/admin, /queue, ...).
            # Returning index.html is what makes a hard refresh or a pasted
            # deep link work instead of 404ing.
            return send_file(str(index_file))

        logger.info(f"🖥️  Serving frontend from {frontend_dist}")
    else:
        logger.info("🖥️  No frontend build found - API only (Vite serves the SPA in dev)")

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not found", "message": str(error)}), 404

    @app.errorhandler(413)
    def payload_too_large(error):
        """Return JSON (not Flask's default HTML) so the SPA can show the reason."""
        limit_mb = settings.max_upload_size / 1024 / 1024
        return jsonify({
            "error": f"File exceeds the maximum upload size of {limit_mb:.0f}MB"
        }), 413

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({"error": "Internal server error"}), 500

    # Request logging middleware
    @app.before_request
    def log_request():
        """Log incoming requests"""
        from flask import request
        logger = get_logger("social_media_automation.api")
        logger.info(f"{request.method} {request.path}")

    @app.after_request
    def log_response(response):
        """Log response status"""
        from flask import request
        logger = get_logger("social_media_automation.api")
        logger.info(f"Response: {response.status_code}")
        return response

    logger.info("✅ Flask application initialized")
    logger.info(f"🌐 Running on {settings.flask_env} mode, port {settings.flask_port}")

    return app


if __name__ == "__main__":
    # Create and run app
    app = create_app()

    settings = get_settings()

    print("\n" + "=" * 60)
    print("🚀 Aphelion")
    print("=" * 60)
    print(f"🌐 Environment: {settings.flask_env}")
    print(f"🔌 Port: {settings.flask_port}")
    print(f"📦 Database: {settings.database_url}")
    print(f"📍 Timezone: {settings.timezone}")
    print(f"📱 Instagram: {settings.instagram_username}")
    print("=" * 60)
    print("\n✅ Server starting...")
    print(f"📌 Open http://localhost:{settings.flask_port} in your browser\n")

    # Run Flask development server
    app.run(
        host="0.0.0.0",
        port=settings.flask_port,
        debug=settings.debug,
        use_reloader=True
    )
