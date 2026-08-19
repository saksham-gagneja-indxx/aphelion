"""Tests for immediate publish and retraction.

The important property here is ownership: this is now a multi-user system, so
one operator must not be able to publish or delete another's posts by guessing
an id. The rest covers the failure paths, which is where a publish endpoint
does most of its work.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from backend.core.publishers.base import PublishResult

API_KEY = "publish-test-key"


@pytest.fixture
def app(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("API_ACCESS_KEY", API_KEY)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")

    import backend.utils.database as database

    database._db_instance = None

    from backend.app import create_app

    application = create_app()
    application.config["TESTING"] = True
    yield application

    database._db_instance = None
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    from backend.utils.database import get_session

    session = get_session()
    yield session
    session.close()


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "reel.mp4"
    path.write_bytes(b"\x00" * (200 * 1024))
    return path


def make_user(db, sub, **kwargs):
    from backend.models.user import User

    user = User(linkedin_sub=sub, full_name=sub, is_active=True, **kwargs)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_post(db, user_id, video, **kwargs):
    from backend.models.post import Post

    defaults = {
        "user_id": user_id,
        "video_path": str(video),
        "caption": "hello",
        "platform": "linkedin",
        "status": "draft",
    }
    defaults.update(kwargs)
    post = Post(**defaults)
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def session_for(app, user_id):
    from backend.utils.security import make_session_token

    with app.app_context():
        return make_session_token(user_id)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def connected_publisher(result=None):
    publisher = MagicMock()
    publisher.is_connected.return_value = True
    publisher.platform = "linkedin"
    publisher.publish.return_value = result or PublishResult.ok(
        "urn:li:share:123", "https://linkedin.com/feed/update/urn:li:share:123/"
    )
    publisher.delete.return_value = (True, "")
    return publisher


# ------------------------------------------------------------- authorization


def test_publish_requires_authentication(client, db, video):
    user = make_user(db, "sub-a")
    post = make_post(db, user.id, video)
    assert client.post(f"/api/posts/{post.id}/publish").status_code == 401


def test_user_cannot_publish_another_users_post(app, client, db, video):
    """The core multi-tenancy guarantee."""
    owner = make_user(db, "sub-owner")
    intruder = make_user(db, "sub-intruder")
    post = make_post(db, owner.id, video)

    with patch("backend.api.publish_routes.get_publisher") as gp:
        gp.return_value = connected_publisher()
        response = client.post(
            f"/api/posts/{post.id}/publish", headers=auth(session_for(app, intruder.id))
        )

    # 404 not 403 - confirming existence would let ids be enumerated.
    assert response.status_code == 404
    gp.assert_not_called()


def test_user_cannot_delete_another_users_post(app, client, db, video):
    owner = make_user(db, "sub-owner2")
    intruder = make_user(db, "sub-intruder2")
    post = make_post(db, owner.id, video, status="posted", linkedin_post_id="urn:x")

    response = client.delete(
        f"/api/posts/{post.id}/published", headers=auth(session_for(app, intruder.id))
    )
    assert response.status_code == 404


# ------------------------------------------------------------------ publish


def test_successful_publish_updates_the_post(app, client, db, video):
    user = make_user(db, "sub-pub")
    post = make_post(db, user.id, video)

    with patch("backend.api.publish_routes.get_publisher") as gp:
        gp.return_value = connected_publisher()
        response = client.post(
            f"/api/posts/{post.id}/publish", headers=auth(session_for(app, user.id))
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["platform_post_id"] == "urn:li:share:123"

    db.refresh(post)
    assert post.status == "posted"
    assert post.linkedin_post_id == "urn:li:share:123"


def test_publish_records_an_audit_entry(app, client, db, video):
    from backend.models.audit import AuditLog

    user = make_user(db, "sub-audit")
    post = make_post(db, user.id, video)

    with patch("backend.api.publish_routes.get_publisher") as gp:
        gp.return_value = connected_publisher()
        client.post(
            f"/api/posts/{post.id}/publish", headers=auth(session_for(app, user.id))
        )

    assert db.query(AuditLog).filter(AuditLog.action == "post.published").count() == 1


def test_publish_failure_marks_the_post_failed(app, client, db, video):
    user = make_user(db, "sub-fail")
    post = make_post(db, user.id, video)

    with patch("backend.api.publish_routes.get_publisher") as gp:
        gp.return_value = connected_publisher(
            PublishResult.failure("LinkedIn said no", retryable=True)
        )
        response = client.post(
            f"/api/posts/{post.id}/publish", headers=auth(session_for(app, user.id))
        )

    # 502: the upstream platform failed, the request was not malformed.
    assert response.status_code == 502
    assert response.get_json()["retryable"] is True

    db.refresh(post)
    assert post.status == "failed"
    assert "LinkedIn said no" in post.error_message


def test_publishing_twice_is_refused(app, client, db, video):
    user = make_user(db, "sub-twice")
    post = make_post(db, user.id, video, status="posted", linkedin_post_id="urn:x")

    response = client.post(
        f"/api/posts/{post.id}/publish", headers=auth(session_for(app, user.id))
    )
    assert response.status_code == 409


def test_missing_video_file_fails_before_calling_the_platform(app, client, db, tmp_path):
    user = make_user(db, "sub-missing")
    post = make_post(db, user.id, tmp_path / "gone.mp4")

    with patch("backend.api.publish_routes.get_publisher") as gp:
        response = client.post(
            f"/api/posts/{post.id}/publish", headers=auth(session_for(app, user.id))
        )

    assert response.status_code == 404
    gp.assert_not_called()

    db.refresh(post)
    assert post.status == "failed"


def test_disconnected_platform_is_refused(app, client, db, video):
    user = make_user(db, "sub-disc")
    post = make_post(db, user.id, video)

    publisher = MagicMock()
    publisher.is_connected.return_value = False
    publisher.connection_status.return_value = {"reason": "Not connected"}

    with patch("backend.api.publish_routes.get_publisher", return_value=publisher):
        response = client.post(
            f"/api/posts/{post.id}/publish", headers=auth(session_for(app, user.id))
        )

    assert response.status_code == 409
    publisher.publish.assert_not_called()


# ------------------------------------------------------------------- delete


def test_delete_retracts_and_marks_cancelled(app, client, db, video):
    user = make_user(db, "sub-del")
    post = make_post(db, user.id, video, status="posted", linkedin_post_id="urn:li:share:9")

    with patch("backend.api.publish_routes.get_publisher") as gp:
        gp.return_value = connected_publisher()
        response = client.delete(
            f"/api/posts/{post.id}/published", headers=auth(session_for(app, user.id))
        )

    assert response.status_code == 200
    db.refresh(post)
    # The row is kept so the audit trail still shows it was published.
    assert post.status == "cancelled"


def test_deleting_an_unpublished_post_is_refused(app, client, db, video):
    user = make_user(db, "sub-nodel")
    post = make_post(db, user.id, video)

    response = client.delete(
        f"/api/posts/{post.id}/published", headers=auth(session_for(app, user.id))
    )
    assert response.status_code == 409


# ------------------------------------------------------ unified delete_post


def test_delete_post_retracts_a_posted_post(app, client, db, video):
    """The unified endpoint does the same real-platform retract as /published."""
    user = make_user(db, "sub-unideleted")
    post = make_post(db, user.id, video, status="posted", linkedin_post_id="urn:li:share:1")

    with patch("backend.api.publish_routes.get_publisher") as gp:
        publisher = connected_publisher()
        gp.return_value = publisher
        response = client.post(
            f"/api/posts/{post.id}/delete", headers=auth(session_for(app, user.id))
        )

    assert response.status_code == 200
    publisher.delete.assert_called_once_with("urn:li:share:1")
    db.refresh(post)
    assert post.status == "cancelled"


def test_delete_post_cancels_the_real_scheduler_job(app, client, db, video):
    """A scheduled post's job must actually be removed, not just the row
    marked cancelled - a fired job would still publish otherwise."""
    user = make_user(db, "sub-schedcancel")
    post = make_post(
        db, user.id, video, status="scheduled", job_id="post_1_9999999999"
    )

    with patch("backend.api.publish_routes.get_scheduler") as gs:
        scheduler = MagicMock()
        gs.return_value = scheduler
        response = client.post(
            f"/api/posts/{post.id}/delete", headers=auth(session_for(app, user.id))
        )

    assert response.status_code == 200
    scheduler.cancel_post.assert_called_once_with(post.id)


def test_delete_post_on_a_draft_needs_nothing_external(app, client, db, video):
    user = make_user(db, "sub-draftdel")
    post = make_post(db, user.id, video, status="draft")

    with patch("backend.api.publish_routes.get_scheduler") as gs, \
         patch("backend.api.publish_routes.get_publisher") as gp:
        response = client.post(
            f"/api/posts/{post.id}/delete", headers=auth(session_for(app, user.id))
        )

    gs.return_value.cancel_post.assert_not_called()
    gp.assert_not_called()
    assert response.status_code == 200
    db.refresh(post)
    assert post.status == "cancelled"


def test_deleting_an_already_deleted_post_is_refused(app, client, db, video):
    user = make_user(db, "sub-redel")
    post = make_post(db, user.id, video, status="cancelled")

    response = client.post(
        f"/api/posts/{post.id}/delete", headers=auth(session_for(app, user.id))
    )
    assert response.status_code == 409


def test_user_cannot_delete_another_users_post_via_unified_endpoint(app, client, db, video):
    owner = make_user(db, "sub-owner-del")
    intruder = make_user(db, "sub-intruder-del")
    post = make_post(db, owner.id, video)

    response = client.post(
        f"/api/posts/{post.id}/delete", headers=auth(session_for(app, intruder.id))
    )
    assert response.status_code == 404


# ---------------------------------------------------------------- edit_post


def test_edit_post_rejects_a_posted_post(app, client, db, video):
    user = make_user(db, "sub-editposted")
    post = make_post(db, user.id, video, status="posted", linkedin_post_id="urn:li:share:2")

    response = client.patch(
        f"/api/posts/{post.id}",
        json={"caption": "new caption"},
        headers=auth(session_for(app, user.id)),
    )
    assert response.status_code == 409
    db.refresh(post)
    assert post.caption == "hello"


def test_edit_post_updates_the_caption_on_a_draft(app, client, db, video):
    user = make_user(db, "sub-editcaption")
    post = make_post(db, user.id, video, status="draft")

    response = client.patch(
        f"/api/posts/{post.id}",
        json={"caption": "a better caption"},
        headers=auth(session_for(app, user.id)),
    )

    assert response.status_code == 200
    db.refresh(post)
    assert post.caption == "a better caption"


def test_edit_post_moves_a_scheduled_job_to_the_new_time(app, client, db, video):
    """Changing scheduled_time on an already-scheduled post must cancel the
    old job and create a new one - overwriting the column alone would leave
    the original job firing at the old time regardless."""
    user = make_user(db, "sub-editreschedule")
    post = make_post(
        db, user.id, video, status="scheduled", job_id="post_1_1111111111"
    )

    with patch("backend.api.publish_routes.get_scheduler") as gs:
        scheduler = MagicMock()
        scheduler.schedule_post.return_value = "post_1_2222222222"
        gs.return_value = scheduler
        response = client.patch(
            f"/api/posts/{post.id}",
            json={"scheduled_time": "2099-01-01T10:00:00Z"},
            headers=auth(session_for(app, user.id)),
        )

    assert response.status_code == 200
    scheduler.cancel_post.assert_called_once_with(post.id)
    scheduler.schedule_post.assert_called_once()


def test_edit_post_rejects_a_scheduled_time_in_the_past(app, client, db, video):
    user = make_user(db, "sub-editpast")
    post = make_post(db, user.id, video, status="draft")

    response = client.patch(
        f"/api/posts/{post.id}",
        json={"scheduled_time": "2000-01-01T10:00:00Z"},
        headers=auth(session_for(app, user.id)),
    )
    assert response.status_code == 400


def test_edit_post_requires_at_least_one_field(app, client, db, video):
    user = make_user(db, "sub-editempty")
    post = make_post(db, user.id, video, status="draft")

    response = client.patch(
        f"/api/posts/{post.id}", json={}, headers=auth(session_for(app, user.id))
    )
    assert response.status_code == 400


def test_user_cannot_edit_another_users_post(app, client, db, video):
    owner = make_user(db, "sub-owner-edit")
    intruder = make_user(db, "sub-intruder-edit")
    post = make_post(db, owner.id, video)

    response = client.patch(
        f"/api/posts/{post.id}",
        json={"caption": "hijacked"},
        headers=auth(session_for(app, intruder.id)),
    )
    assert response.status_code == 404
    db.refresh(post)
    assert post.caption == "hello"
