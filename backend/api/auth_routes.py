"""LinkedIn OAuth 2.0 - used for BOTH sign-in and publish authorization.

One consent screen does two jobs. The member authorizes the app once and we
receive:

  * their identity  (openid, profile) - who they are, used to sign them in
  * publish rights  (w_member_social) - permission to post as them

That is the whole reason LinkedIn is the right identity provider here rather
than Google or Microsoft: with those, you would authenticate someone and then
still need a separate LinkedIn grant to publish. Two consent screens, one job.

We never see or store a password.

Endpoints:
    GET  /api/auth/linkedin/login     public  - sign in / sign up
    GET  /api/auth/linkedin/callback  public  - protected by signed state
    GET  /api/auth/linkedin/start     authed  - re-connect an existing account
    GET  /api/auth/linkedin/status    authed
    POST /api/auth/linkedin/disconnect authed
    GET  /api/me                      authed
    POST /api/logout                  authed

Access policy: the FIRST account to sign in becomes an active administrator.
Every account after that is created as an INACTIVE operator and cannot use the
API until an administrator approves it. Sign-in is necessarily public - it is
what an anonymous visitor clicks - so approval, not the login endpoint, is
where access is actually controlled.
"""

import base64
import binascii
import json
from datetime import timedelta
from typing import Optional
from urllib.parse import urlencode

import requests
from flask import Blueprint, jsonify, redirect, request

from backend.models.audit import record as audit
from backend.models.user import User
from backend.utils.config import (
    admin_allowlist_enabled,
    get_settings,
    is_admin_sub,
    is_placeholder,
    linkedin_configured,
)
from backend.utils.database import get_session
from backend.utils.logger import get_logger
from backend.utils.security import (
    current_user,
    make_mcp_connector_grant,
    make_oauth_state,
    make_session_token,
    require_admin,
    verify_mcp_connector_grant,
    verify_oauth_state,
)
from backend.utils.timeutil import utcnow

logger = get_logger("social_media_automation.auth")

auth_bp = Blueprint("auth", __name__, url_prefix="/api")

AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

SCOPES = "openid profile w_member_social"

# Sentinel user_id inside the signed state meaning "this is a sign-in; resolve
# the account from the LinkedIn subject claim" rather than "re-connect user N".
LOGIN_USER_ID = 0


def _claims_from_id_token(id_token: Optional[str]) -> dict:
    """Read the OIDC identity claims out of the id_token.

    We request the `openid` scope, so the token response carries an id_token
    holding exactly what the userinfo endpoint would return: sub, name, email,
    picture. Reading it here removes an HTTP round trip, and with it a whole
    failure mode - userinfo lives on api.linkedin.com, a different host from
    the token endpoint, so sign-in used to depend on BOTH being reachable.
    That is not hypothetical: on a network that filters api.linkedin.com by
    SNI, the token exchange succeeds and sign-in then dies at userinfo with an
    SSL error.

    The signature is deliberately not verified, which is sound specifically
    here and would not be elsewhere. This token was just fetched by us, over a
    verified TLS connection, directly from LinkedIn's token endpoint, in the
    authorization code flow - so TLS already establishes who sent it and that
    nobody altered it in transit. OpenID Connect Core 3.1.3.7 permits exactly
    this substitution. An id_token arriving by any other route (an implicit
    flow, or one handed to us by a client) would have to be verified properly.

    Returns {} when there is no usable token, so the caller falls back to
    querying userinfo rather than treating the sign-in as anonymous.
    """
    if not id_token:
        return {}

    try:
        payload_segment = id_token.split(".")[1]
        padding = "=" * (-len(payload_segment) % 4)
        claims = json.loads(
            base64.urlsafe_b64decode(payload_segment + padding).decode("utf-8")
        )
    except (IndexError, ValueError, UnicodeDecodeError, binascii.Error) as e:
        # Malformed rather than fatal: fall back to userinfo.
        logger.warning(f"Could not read id_token claims, falling back: {e}")
        return {}

    if not isinstance(claims, dict) or not claims.get("sub"):
        return {}

    return claims


def _frontend_url(status: str, token: str = None, mcp: bool = False) -> str:
    """Build the post-OAuth redirect back to the SPA.

    The session token is delivered in the URL FRAGMENT, not the query string.
    Fragments are never sent to a server, so the token stays out of access
    logs and out of Referer headers. The SPA reads it and strips it from the
    address bar.

    `mcp=True` routes to a distinct, standalone page (/mcp-connected) instead
    of the normal dashboard landing - this callback was reached via
    mcp_link_start's self-serve flow, so the person's next real move is
    switching back to the Claude tab, not looking at a web dashboard. That
    page shows a brief confirmation and auto-redirects to claude.ai itself.
    """
    base = get_settings().frontend_url.rstrip("/")
    path = "/mcp-connected" if mcp else "/"
    url = f"{base}{path}?{'linkedin' if not mcp else 'status'}={status}"
    if token:
        url += f"#token={token}"
    return url


def _next_redirect(next_path: str, token: Optional[str] = None, error: Optional[str] = None) -> str:
    """Build the post-OAuth redirect when the state carried a `next` (see
    make_oauth_state) - lands back on that exact frontend path/query instead
    of the normal dashboard or /mcp-connected. Used by the MCP connector
    flow's /mcp-authorize page, which already knows why it's there from its
    own query params and just needs the token (or an error) appended.
    """
    base = get_settings().frontend_url.rstrip("/")
    sep = "&" if "?" in next_path else "?"
    url = f"{base}{next_path}"
    if error:
        url += f"{sep}auth_error={error}"
        sep = "&"
    if token:
        url += f"#token={token}"
    return url


def _authorize_url(
    user_id: int,
    client_id: Optional[str] = None,
    link_github: Optional[str] = None,
    next: Optional[str] = None,
) -> str:
    """`client_id` overrides the server's own app for a known account that
    configured its own LinkedIn app (see User.effective_linkedin_client_id).
    Left unset for the plain sign-in entry point, where there is no account
    yet to have configured anything.

    `link_github` carries a GitHub login (already verified by the MCP
    Worker's own OAuth) through to the callback, so it can set
    User.github_username automatically - see /api/mcp/link-start.

    `next` carries a frontend path to land on instead of the normal
    dashboard - see make_oauth_state."""
    settings = get_settings()
    params = {
        "response_type": "code",
        "client_id": client_id or settings.linkedin_client_id,
        "redirect_uri": settings.linkedin_redirect_uri,
        "state": make_oauth_state(user_id, link_github=link_github, next=next),
        "scope": SCOPES,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def _authorize_response(user_id: int, client_id: Optional[str] = None):
    """Send the caller to LinkedIn, or hand back the URL for it to open itself.

    `?format=json` exists because /start requires a bearer token, and a
    top-level browser navigation cannot carry one - it just 401s. The SPA
    fetches the URL through apiFetch instead and opens it in a new tab, which
    also leaves the current page intact while the member consents.
    """
    next_path = request.args.get("next")
    url = _authorize_url(user_id, client_id=client_id, next=next_path)
    if request.args.get("format") == "json":
        return jsonify({"url": url}), 200
    return redirect(url)


@auth_bp.route("/auth/linkedin/login", methods=["GET"])
def linkedin_login():
    """Public sign-in entry point.

    `?next=/some/frontend/path` sends the browser there instead of the normal
    dashboard once signed in - used by the MCP connector's /mcp-authorize
    page (see make_oauth_state's `next`), which needs LinkedIn sign-in to
    return to itself rather than to "/"."""
    if not linkedin_configured():
        return jsonify({
            "error": "LinkedIn sign-in is not configured on this server."
        }), 503
    return _authorize_response(LOGIN_USER_ID)


@auth_bp.route("/auth/linkedin/start", methods=["GET"])
def linkedin_start():
    """Re-connect LinkedIn for the signed-in user (e.g. after token expiry).

    Uses the account's own LinkedIn app if it configured one (see
    User.effective_linkedin_client_id); otherwise falls back to the server's
    app, same as before per-user credentials existed. A machine caller with no
    account on record has neither, so it is restricted to the server-wide
    check below.
    """
    user = current_user()
    if user is None:
        # A machine caller has no identity to reconnect; require an explicit id.
        user_id = request.args.get("user_id", type=int)
        if not user_id:
            return jsonify({"error": "user_id is required for machine callers"}), 400
        if not linkedin_configured():
            return jsonify({"error": "LinkedIn is not configured."}), 503
        return _authorize_response(user_id)

    client_id = user.effective_linkedin_client_id()
    if not client_id or is_placeholder(client_id):
        return jsonify({
            "error": "LinkedIn is not configured. Add your own LinkedIn app "
                     "in Setup, or ask an administrator to configure one."
        }), 503

    return _authorize_response(user.id, client_id=client_id)


@auth_bp.route("/mcp/link-start", methods=["POST"])
def mcp_link_start():
    """Begin self-serve onboarding for a GitHub identity with no backend
    account mapped yet.

    Machine-only (see require_admin's is_machine bypass): the caller is the
    MCP Worker, which has already run its own GitHub OAuth and knows this
    login is genuinely who they say they are. This endpoint hands back a
    LinkedIn sign-in URL whose state carries that (already-verified) login
    signed into itself - see make_oauth_state's link_github - so the
    LinkedIn callback can set User.github_username automatically on success
    instead of requiring `admin_cli set-github`.

    This does NOT bypass account approval: a brand new account still lands
    is_active=False same as any other sign-up (see _resolve_user), and still
    needs approving before real tools work. It only removes the manual
    identity-linking step - not the trust decision after it.
    """
    denied = require_admin()
    if denied:
        return denied

    if not linkedin_configured():
        return jsonify({"error": "LinkedIn is not configured on this server."}), 503

    data = request.get_json(silent=True) or {}
    github_username = (data.get("github_username") or "").strip()
    if not github_username:
        return jsonify({"error": "github_username is required"}), 400

    url = _authorize_url(LOGIN_USER_ID, link_github=github_username)
    return jsonify({"url": url}), 200


@auth_bp.route("/mcp/authorize-connector", methods=["POST"])
def mcp_authorize_connector():
    """Approve one MCP connector authorization attempt as the signed-in user.

    This is the piece that lets connecting Post Pilot skip GitHub (or any
    third-party OAuth screen) entirely: the Cloudflare Worker's own OAuth
    flow sends the browser to the WEBSITE instead of a third party, the
    website is what actually authenticates them (however they normally sign
    in here), and this endpoint is the last step of that - it hands back a
    short-lived signed grant (see make_mcp_connector_grant) proving "the
    person who just signed in on this website approved this exact connector
    attempt". The frontend redirects the browser straight back to the
    Worker's callback with it, which verifies it via
    /mcp/verify-connector-grant below and finishes Claude's own handshake.

    Deliberately requires a real human session, not a machine/API-key
    caller: an API key has no single identity to grant a connector to.
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Sign in first."}), 401

    data = request.get_json(silent=True) or {}
    worker_state = (data.get("worker_state") or "").strip()
    if not worker_state:
        return jsonify({"error": "worker_state is required"}), 400

    grant = make_mcp_connector_grant(user.id, worker_state)
    return jsonify({"grant": grant}), 200


@auth_bp.route("/mcp/verify-connector-grant", methods=["POST"])
def mcp_verify_connector_grant():
    """Redeem a grant minted by /mcp/authorize-connector.

    Admin-or-machine, via require_admin: in practice always the Worker
    itself (a machine caller, via BACKEND_API_KEY) completing its own OAuth
    handshake with Claude - an ordinary signed-in user has no reason to call
    this. Returns the account the grant was issued for, same shape as
    /api/users/by-github/<username> so the Worker's downstream handling
    stays the same regardless of which path resolved the identity.
    """
    denied = require_admin()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    grant = data.get("grant")
    worker_state = (data.get("worker_state") or "").strip()
    if not worker_state:
        return jsonify({"error": "worker_state is required"}), 400

    user_id = verify_mcp_connector_grant(grant, worker_state)
    if user_id is None:
        return jsonify({"error": "Invalid or expired grant."}), 401

    db = get_session()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None or not user.is_active:
            return jsonify({"error": "No active account for that grant."}), 404
        return jsonify({"id": user.id, "name": user.full_name, "role": user.role}), 200
    finally:
        db.close()


@auth_bp.route("/auth/linkedin/callback", methods=["GET"])
def linkedin_callback():
    """Exchange the code, sign the member in, store their publish token."""
    error = request.args.get("error")
    if error:
        logger.warning(
            f"LinkedIn authorization denied: {error} "
            f"{request.args.get('error_description', '')}"
        )
        return redirect(_frontend_url("denied"))

    # Public endpoint: LinkedIn's redirect cannot carry a bearer token. The
    # signed state IS the authorization - nothing is written unless it verifies.
    state_user_id, state_error, link_github, next_path = verify_oauth_state(
        request.args.get("state")
    )
    if state_user_id is None:
        logger.warning(f"LinkedIn callback rejected: {state_error}")
        return redirect(_frontend_url("state_mismatch"))

    is_mcp_flow = bool(link_github)

    def _redirect(status: str, token: Optional[str] = None):
        """Route to `next` (see make_oauth_state) when the state carries one -
        the MCP connector flow's /mcp-authorize page - else the usual target."""
        if next_path:
            return redirect(_next_redirect(next_path, token=token, error=None if token else status))
        return redirect(_frontend_url(status, token=token, mcp=is_mcp_flow))

    code = request.args.get("code")
    if not code:
        return _redirect("missing_code")

    settings = get_settings()

    # The token exchange must present the SAME app credentials that were used
    # to build the authorize URL - LinkedIn issued the code to a specific
    # client_id. For a reconnect (state carries a real user id) that may be
    # the account's own app; a plain sign-in has no account yet and always
    # uses the server's.
    client_id, client_secret = settings.linkedin_client_id, settings.linkedin_client_secret
    if state_user_id != LOGIN_USER_ID:
        _db_for_creds = get_session()
        try:
            _target = _db_for_creds.query(User).filter(User.id == state_user_id).first()
            if _target is not None:
                client_id = _target.effective_linkedin_client_id()
                client_secret = _target.effective_linkedin_client_secret()
        finally:
            _db_for_creds.close()

    try:
        token_response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": settings.linkedin_redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        if token_response.status_code >= 400:
            logger.error(
                f"LinkedIn token exchange failed "
                f"({token_response.status_code}): {token_response.text[:300]}"
            )
            return _redirect("token_failed")

        token = token_response.json()
        access_token = token.get("access_token")
        if not access_token:
            return _redirect("token_failed")

        # Identity comes from the id_token when there is one, and only falls
        # back to the userinfo endpoint otherwise. See _claims_from_id_token.
        userinfo = _claims_from_id_token(token.get("id_token"))

        if not userinfo.get("sub"):
            userinfo_response = requests.get(
                USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30,
            )
            if userinfo_response.status_code >= 400:
                logger.error(
                    f"LinkedIn userinfo failed "
                    f"({userinfo_response.status_code}): {userinfo_response.text[:300]}"
                )
                return _redirect("userinfo_failed")
            userinfo = userinfo_response.json()

        subject = userinfo.get("sub")
        if not subject:
            return _redirect("userinfo_failed")

        expires_at = None
        if token.get("expires_in"):
            expires_at = utcnow() + timedelta(seconds=int(token["expires_in"]))

        db = get_session()
        try:
            user, created = _resolve_user(db, state_user_id, subject, userinfo)
            if user is None:
                # Either sign-ups are closed, or a re-connect named an account
                # that no longer exists. Neither should look like a crash.
                return _redirect("not_permitted")

            if link_github and user.github_username != link_github:
                # github_username is unique - a login already claimed by a
                # DIFFERENT account must not be silently reassigned onto this
                # one (whoever set it first, admin_cli or an earlier self-serve
                # link, keeps it). Sign-in still proceeds either way; only the
                # mapping is skipped.
                conflict = (
                    db.query(User)
                    .filter(User.github_username == link_github, User.id != user.id)
                    .first()
                )
                if conflict is not None:
                    logger.warning(
                        f"MCP self-serve link skipped: GitHub login {link_github!r} "
                        f"already maps to user {conflict.id}, not {user.id}"
                    )
                else:
                    user.github_username = link_github
                    logger.info(
                        f"Linked GitHub login {link_github!r} to user {user.id} "
                        "via self-serve MCP flow"
                    )

            user.store_linkedin_token(
                access_token=access_token,
                person_urn=f"urn:li:person:{subject}",
                expires_at=expires_at,
                refresh_token=token.get("refresh_token"),
                # What was actually granted, which is not necessarily what was
                # requested - a missing product silently drops its scope.
                scope=token.get("scope"),
            )
            # Refresh profile fields on every sign-in so a renamed account or
            # changed avatar does not go stale.
            user.full_name = userinfo.get("name") or user.full_name
            user.email = userinfo.get("email") or user.email
            user.avatar_url = userinfo.get("picture") or user.avatar_url
            user.touch_last_seen()

            audit(
                db,
                action="user.signed_up" if created else "user.signed_in",
                actor=user,
                target=f"user:{user.id}",
                detail=f"role={user.role} active={user.is_active}",
                ip_address=request.remote_addr,
            )
            db.commit()

            if not user.is_active:
                logger.info(f"Sign-in by pending account {user.id} ({user.email})")
                return _redirect("pending_approval")

            session_token = make_session_token(user.id)
            logger.info(f"✅ Signed in: {user.full_name} (id={user.id}, {user.role})")
        finally:
            db.close()

        return _redirect("connected", token=session_token)

    except requests.RequestException as e:
        logger.error(f"LinkedIn OAuth network failure: {e}")
        return _redirect("network_error")


def _resolve_user(db, state_user_id: int, subject: str, userinfo: dict):
    """Find or create the account this callback belongs to.

    Returns (user, was_created).

    Matching is by LinkedIn's `sub` claim, which is stable for the account. It
    is deliberately NOT by email: a member can change their email, and two
    accounts could in principle present the same one.
    """
    if state_user_id != LOGIN_USER_ID:
        # Re-connect flow: the state names an existing account.
        user = db.query(User).filter(User.id == state_user_id).first()
        return user, False

    allowlisted = is_admin_sub(subject)

    user = db.query(User).filter(User.linkedin_sub == subject).first()
    if user is not None:
        # Re-assert the allowlist on every sign-in. This is self-healing: if
        # the database is ever reset or the role edited by hand, the intended
        # administrator is restored on their next login and nobody else is.
        if allowlisted and (user.role != User.ROLE_ADMIN or not user.is_active):
            logger.info(f"Restoring admin role for allowlisted account {user.id}")
            user.role = User.ROLE_ADMIN
            user.is_active = True
        return user, False

    if allowlisted:
        role, active = User.ROLE_ADMIN, True
    elif admin_allowlist_enabled():
        # An allowlist exists and this identity is not on it. It can never be
        # an admin, and needs approval before it can do anything.
        if not get_settings().allow_new_signups:
            logger.warning(f"Rejected sign-up (signups disabled): sub={subject}")
            return None, False
        role, active = User.ROLE_OPERATOR, False
    else:
        # Bootstrap: no allowlist configured yet, so the first account to sign
        # in becomes an active admin - otherwise the tool has no administrator
        # and cannot be set up. Anyone after is inactive pending approval.
        # Set ADMIN_LINKEDIN_SUBS to close this path permanently.
        is_first_user = db.query(User).count() == 0
        if not is_first_user and not get_settings().allow_new_signups:
            logger.warning(f"Rejected sign-up (signups disabled): sub={subject}")
            return None, False
        role, active = (
            (User.ROLE_ADMIN, True) if is_first_user else (User.ROLE_OPERATOR, False)
        )

    user = User(
        linkedin_sub=subject,
        full_name=userinfo.get("name"),
        email=userinfo.get("email"),
        avatar_url=userinfo.get("picture"),
        role=role,
        is_active=active,
        timezone=get_settings().timezone,
    )
    db.add(user)
    db.flush()  # assign an id before the audit entry references it

    logger.info(
        f"Created account {user.id} ({user.full_name}) "
        f"role={user.role} active={user.is_active}"
    )
    return user, True


def _resolve_clerk_user(db, clerk_id: str, profile: dict):
    """Find or create the account behind a verified Clerk identity.

    Mirrors _resolve_user's admin/allowlist logic but keyed on `clerk_id`
    instead of `linkedin_sub`, and with one deliberate difference: Clerk
    accounts are active immediately rather than pending approval. Clerk has
    already gated sign-up (verified email or an OAuth provider); the
    LinkedIn-login pending-approval gate exists because THAT endpoint is
    reachable by anyone with no verification at all.

    Returns (user, was_created).
    """
    from backend.utils.config import admin_clerk_emails, is_admin_clerk_email

    email = profile.get("email")
    is_admin_email = is_admin_clerk_email(email)
    role_claim = (profile.get("public_metadata") or {}).get("role")

    user = db.query(User).filter(User.clerk_id == clerk_id).first()
    if user is not None:
        # Self-healing, same reasoning as the LinkedIn allowlist: if the
        # database is reset or the role edited by hand, the intended admin
        # is restored on next sign-in.
        should_be_admin = is_admin_email or role_claim == User.ROLE_ADMIN
        if should_be_admin and user.role != User.ROLE_ADMIN:
            logger.info(f"Restoring admin role for Clerk account {user.id}")
            user.role = User.ROLE_ADMIN
        user.full_name = profile.get("name") or user.full_name
        user.email = email or user.email
        user.avatar_url = profile.get("avatar_url") or user.avatar_url
        if not user.is_active:
            user.is_active = True
        return user, False

    # Same bootstrap as the LinkedIn path: with ADMIN_CLERK_EMAILS unset and no
    # existing account at all (of either provider), the very first sign-in
    # becomes an admin so the tool has someone who can approve/administer it.
    # Every account after that is a plain operator unless explicitly
    # allowlisted. Sound because whoever runs the deploy is whoever signs in
    # first - the same assumption the LinkedIn bootstrap already makes.
    is_first_user_ever = not admin_clerk_emails() and db.query(User).count() == 0

    should_be_admin = is_admin_email or role_claim == User.ROLE_ADMIN or is_first_user_ever
    role = User.ROLE_ADMIN if should_be_admin else User.ROLE_OPERATOR

    user = User(
        clerk_id=clerk_id,
        full_name=profile.get("name"),
        email=email,
        avatar_url=profile.get("avatar_url"),
        role=role,
        is_active=True,
        timezone=get_settings().timezone,
    )
    db.add(user)
    db.flush()

    logger.info(f"Created Clerk account {user.id} ({user.full_name}) role={user.role}")
    return user, True


@auth_bp.route("/auth/clerk/verify", methods=["POST"])
def clerk_verify():
    """Exchange a verified Clerk session token for this app's own session token.

    Public: the caller has no app session yet, by definition. Safe because
    nothing is trusted until the token verifies against Clerk's JWKS - see
    backend/utils/clerk_auth.py. The app's own session token, once minted,
    behaves identically to one issued via LinkedIn: same signature, same
    is_active check on every request, same admin/audit/ownership logic.
    """
    from backend.utils.clerk_auth import ClerkVerificationError, verify_and_fetch
    from backend.utils.config import clerk_configured

    if not clerk_configured():
        return jsonify({"error": "Clerk sign-in is not configured on this server."}), 503

    body = request.get_json(silent=True) or {}
    token = body.get("token")
    if not token:
        return jsonify({"error": "token is required."}), 400

    try:
        clerk_id, profile = verify_and_fetch(token)
    except ClerkVerificationError as e:
        logger.warning(f"Clerk verification rejected: {e}")
        return jsonify({"error": "Could not verify sign-in."}), 401

    db = get_session()
    try:
        user, created = _resolve_clerk_user(db, clerk_id, profile)

        audit(
            db,
            action="user.signed_up" if created else "user.signed_in",
            actor=user,
            target=f"user:{user.id}",
            detail=f"role={user.role} via=clerk",
            ip_address=request.remote_addr,
        )
        db.commit()

        db.refresh(user)
        identity = user.to_identity()
        session_token = make_session_token(user.id)
    finally:
        db.close()

    logger.info(f"✅ Signed in via Clerk: {identity['name']} (id={identity['id']}, {identity['role']})")
    return jsonify({"token": session_token, "user": identity}), 200


@auth_bp.route("/me", methods=["GET"])
def me():
    """Identity of the caller. The SPA gates the whole app on this."""
    user = current_user()
    if user is None:
        # A machine caller is authenticated but is not a person.
        return jsonify({"error": "No user session. This is a machine token."}), 401
    return jsonify(user.to_identity()), 200


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Sign out.

    Session tokens are stateless and signed, so there is nothing to delete
    server-side - the client discards the token. Documented plainly rather
    than pretending a server-side revocation happened.

    Immediate revocation is available by other means: deactivating a user is
    enforced on every request.
    """
    user = current_user()
    if user is not None:
        db = get_session()
        try:
            audit(
                db,
                action="user.signed_out",
                actor=user,
                target=f"user:{user.id}",
                ip_address=request.remote_addr,
            )
            db.commit()
        finally:
            db.close()

    return jsonify({
        "ok": True,
        "message": "Discard the session token on the client to complete sign-out.",
    }), 200


@auth_bp.route("/auth/linkedin/status", methods=["GET"])
def linkedin_status():
    """LinkedIn connection state for the signed-in user."""
    user = current_user()

    if user is None:
        user_id = request.args.get("user_id", type=int)
        if not user_id:
            return jsonify({"error": "user_id is required for machine callers"}), 400
        db = get_session()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user is None:
                return jsonify({"error": "User not found"}), 404
            return jsonify(_status_payload(user)), 200
        finally:
            db.close()

    return jsonify(_status_payload(user)), 200


def _status_payload(user: User) -> dict:
    expires_at = user.linkedin_token_expires_at
    return {
        "app_configured": linkedin_configured(),
        "connected": user.linkedin_token_valid(),
        "person_urn": user.linkedin_person_urn,
        "email": user.email,
        # Sign-in succeeding says nothing about publishing: without the "Share
        # on LinkedIn" product the grant carries no w_member_social and every
        # post fails. Reported so setup can say so instead of the user finding
        # out when a scheduled post fires.
        "can_publish": user.can_publish_to_linkedin(),
        "granted_scopes": user.linkedin_scope_list() or None,
        "token_expires_at": expires_at.isoformat() if expires_at else None,
        # A lapsed token is a different state from never having connected and
        # needs a different message in the UI.
        "token_expired": bool(
            user.linkedin_access_token and not user.linkedin_token_valid()
        ),
    }


@auth_bp.route("/setup/state", methods=["GET"])
def setup_state():
    """What the caller still has to do before they can publish.

    The onboarding flow sends people out to the LinkedIn developer portal, and
    they come back with no way to know whether what they did worked. This is
    what it polls on their return: each step reports done/not done from real
    state, so the wizard advances by observation rather than by asking "did
    that work?" and believing the answer.
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "No user session."}), 401

    settings = get_settings()
    # Done via EITHER path: the server's shared app, or this account's own -
    # see User.effective_linkedin_client_id. An account that brought its own
    # app is never blocked on an administrator finishing server-side setup.
    app_ready = linkedin_configured() or user.has_own_linkedin_app()
    connected = user.linkedin_token_valid()
    can_publish = user.can_publish_to_linkedin()

    if app_ready:
        app_detail = None
    elif user.is_admin():
        app_detail = (
            "LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET are not set on "
            "the server. Set them, or add your own app below."
        )
    else:
        app_detail = (
            "No app is configured for your account yet. Add your own "
            "LinkedIn app below, or ask an administrator to finish server "
            "setup."
        )

    steps = [
        {
            "id": "app",
            "title": "Register a LinkedIn app",
            "done": app_ready,
            "detail": app_detail,
        },
        {
            "id": "redirect",
            "title": "Add the redirect URL",
            # Cannot be observed directly - LinkedIn only reveals a mismatch by
            # rejecting a live attempt. Treated as done once a grant has
            # actually come back through it, which is proof it matched.
            "done": connected,
            "detail": settings.linkedin_redirect_uri,
        },
        {
            "id": "connect",
            "title": "Connect your LinkedIn account",
            "done": connected,
            "detail": user.linkedin_person_urn if connected else None,
        },
        {
            "id": "publish",
            "title": "Grant publishing permission",
            "done": can_publish,
            "detail": None if can_publish else (
                "The grant does not include w_member_social. Add the "
                "\"Share on LinkedIn\" product to the app, then reconnect."
            ),
        },
    ]

    return jsonify({
        "steps": steps,
        "complete": all(s["done"] for s in steps),
        "redirect_uri": settings.linkedin_redirect_uri,
        "is_admin": user.is_admin(),
        "has_own_linkedin_app": user.has_own_linkedin_app(),
        "own_linkedin_client_id": user.linkedin_own_client_id,
    }), 200


@auth_bp.route("/auth/linkedin/disconnect", methods=["POST"])
def linkedin_disconnect():
    """Forget the stored token.

    Local only - it does not revoke the grant at LinkedIn. Only the member can
    do that, from their own LinkedIn settings.
    """
    user = current_user()
    user_id = user.id if user else (request.get_json(silent=True) or {}).get("user_id")

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    db = get_session()
    try:
        target = db.query(User).filter(User.id == user_id).first()
        if target is None:
            return jsonify({"error": "User not found"}), 404

        target.clear_linkedin_token()
        audit(
            db,
            action="linkedin.disconnected",
            actor=user or target,
            target=f"user:{target.id}",
            ip_address=request.remote_addr,
        )
        db.commit()

        return jsonify({
            "message": "LinkedIn disconnected locally. To fully revoke access, "
                       "remove the app from your LinkedIn account settings.",
            "connected": False,
        }), 200
    finally:
        db.close()
