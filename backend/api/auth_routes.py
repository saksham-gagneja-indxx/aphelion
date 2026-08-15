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

from datetime import timedelta
from urllib.parse import urlencode

import requests
from flask import Blueprint, jsonify, redirect, request

from backend.models.audit import record as audit
from backend.models.user import User
from backend.utils.config import (
    admin_allowlist_enabled,
    get_settings,
    is_admin_sub,
    linkedin_configured,
)
from backend.utils.database import get_session
from backend.utils.logger import get_logger
from backend.utils.security import (
    current_user,
    make_oauth_state,
    make_session_token,
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


def _frontend_url(status: str, token: str = None) -> str:
    """Build the post-OAuth redirect back to the SPA.

    The session token is delivered in the URL FRAGMENT, not the query string.
    Fragments are never sent to a server, so the token stays out of access
    logs and out of Referer headers. The SPA reads it and strips it from the
    address bar.
    """
    base = get_settings().frontend_url.rstrip("/")
    url = f"{base}/?linkedin={status}"
    if token:
        url += f"#token={token}"
    return url


def _authorize_url(user_id: int) -> str:
    settings = get_settings()
    params = {
        "response_type": "code",
        "client_id": settings.linkedin_client_id,
        "redirect_uri": settings.linkedin_redirect_uri,
        "state": make_oauth_state(user_id),
        "scope": SCOPES,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def _authorize_response(user_id: int):
    """Send the caller to LinkedIn, or hand back the URL for it to open itself.

    `?format=json` exists because /start requires a bearer token, and a
    top-level browser navigation cannot carry one - it just 401s. The SPA
    fetches the URL through apiFetch instead and opens it in a new tab, which
    also leaves the current page intact while the member consents.
    """
    url = _authorize_url(user_id)
    if request.args.get("format") == "json":
        return jsonify({"url": url}), 200
    return redirect(url)


@auth_bp.route("/auth/linkedin/login", methods=["GET"])
def linkedin_login():
    """Public sign-in entry point."""
    if not linkedin_configured():
        return jsonify({
            "error": "LinkedIn sign-in is not configured on this server."
        }), 503
    return _authorize_response(LOGIN_USER_ID)


@auth_bp.route("/auth/linkedin/start", methods=["GET"])
def linkedin_start():
    """Re-connect LinkedIn for the signed-in user (e.g. after token expiry)."""
    if not linkedin_configured():
        return jsonify({"error": "LinkedIn is not configured."}), 503

    user = current_user()
    if user is None:
        # A machine caller has no identity to reconnect; require an explicit id.
        user_id = request.args.get("user_id", type=int)
        if not user_id:
            return jsonify({"error": "user_id is required for machine callers"}), 400
        return _authorize_response(user_id)

    return _authorize_response(user.id)


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
    state_user_id, state_error = verify_oauth_state(request.args.get("state"))
    if state_user_id is None:
        logger.warning(f"LinkedIn callback rejected: {state_error}")
        return redirect(_frontend_url("state_mismatch"))

    code = request.args.get("code")
    if not code:
        return redirect(_frontend_url("missing_code"))

    settings = get_settings()

    try:
        token_response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.linkedin_client_id,
                "client_secret": settings.linkedin_client_secret,
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
            return redirect(_frontend_url("token_failed"))

        token = token_response.json()
        access_token = token.get("access_token")
        if not access_token:
            return redirect(_frontend_url("token_failed"))

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
            return redirect(_frontend_url("userinfo_failed"))

        userinfo = userinfo_response.json()
        subject = userinfo.get("sub")
        if not subject:
            return redirect(_frontend_url("userinfo_failed"))

        expires_at = None
        if token.get("expires_in"):
            expires_at = utcnow() + timedelta(seconds=int(token["expires_in"]))

        db = get_session()
        try:
            user, created = _resolve_user(db, state_user_id, subject, userinfo)
            if user is None:
                # Either sign-ups are closed, or a re-connect named an account
                # that no longer exists. Neither should look like a crash.
                return redirect(_frontend_url("not_permitted"))

            user.store_linkedin_token(
                access_token=access_token,
                person_urn=f"urn:li:person:{subject}",
                expires_at=expires_at,
                refresh_token=token.get("refresh_token"),
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
                return redirect(_frontend_url("pending_approval"))

            session_token = make_session_token(user.id)
            logger.info(f"✅ Signed in: {user.full_name} (id={user.id}, {user.role})")
        finally:
            db.close()

        return redirect(_frontend_url("connected", token=session_token))

    except requests.RequestException as e:
        logger.error(f"LinkedIn OAuth network failure: {e}")
        return redirect(_frontend_url("network_error"))


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
        "token_expires_at": expires_at.isoformat() if expires_at else None,
        # A lapsed token is a different state from never having connected and
        # needs a different message in the UI.
        "token_expired": bool(
            user.linkedin_access_token and not user.linkedin_token_valid()
        ),
    }


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
