"""Tests for what happens to a scheduled post when nothing was running.

The process is not always up when a post comes due — a deploy, a crash, or a
free instance sleeping through the moment. APScheduler keeps its jobs in
memory, so every restart rebuilds the timers from the Post table, and these
tests cover that rebuild. It is the path that was broken:

  * the scheduler only started when a request happened to touch it, so a
    process nobody visited restored nothing;
  * `misfire_grace_time=60` discarded every restored job, because a restart is
    never within a minute of the scheduled time;
  * a discarded job left the post `scheduled` forever, so the Queue — the
    screen built to say why a post did not go out — showed it as pending and
    said nothing;
  * `scheduled_time` is a naive column holding the user's local wall clock, so
    handing it to APScheduler unlocalised published every restored post off by
    the timezone offset.

Each of those is a test below. They drive `_restore_scheduled_jobs` directly
rather than through Flask: the bug lived in the rebuild, and a real scheduler
with a real clock would mean sleeping through the assertions.
"""

import os
import tempfile
from datetime import datetime, timedelta

import pytest
import pytz

TZ_NAME = "Asia/Kolkata"


def status_of(post) -> str:
    """`status` is a String column, so a refreshed row hands back a plain str
    while an in-session one still holds the PostStatus member."""
    return getattr(post.status, "value", post.status)


@pytest.fixture
def db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")

    import backend.utils.database as database

    database._db_instance = None
    database.init_db()

    session = database.get_session()
    yield session
    session.close()

    database._db_instance = None
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def scheduler(monkeypatch):
    """A SmartScheduler whose jobs are recorded instead of run.

    `initialize()` is deliberately not called — starting a real
    BackgroundScheduler would arm real timers against the wall clock.
    """
    from backend.core.scheduler import SmartScheduler

    instance = SmartScheduler()
    armed = []

    def fake_add_job(**kwargs):
        armed.append(kwargs)

    monkeypatch.setattr(instance.scheduler, "add_job", lambda **kw: fake_add_job(**kw))
    instance.armed = armed
    return instance


def make_scheduled_post(db, when, tz_name=TZ_NAME):
    """A post sitting in the state a restart finds it in.

    `when` is naive: that is what the column holds, because the write path
    localises the picked time and Postgres keeps the wall clock.
    """
    from backend.models.post import Post
    from backend.models.user import User

    user = User(linkedin_sub=f"sub-{when.isoformat()}", full_name="Op", is_active=True)
    user.timezone = tz_name
    db.add(user)
    db.commit()
    db.refresh(user)

    post = Post(
        user_id=user.id,
        video_path="/tmp/reel.mp4",
        caption="hello",
        platform="linkedin",
        status="scheduled",
        scheduled_time=when,
        job_id=f"post_{user.id}_{int(when.timestamp())}",
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def local_now(tz_name=TZ_NAME):
    """Naive 'now' in the user's zone — the same shape the column holds."""
    return datetime.now(pytz.timezone(tz_name)).replace(tzinfo=None)


def test_future_post_is_rearmed_after_restart(db, scheduler):
    post = make_scheduled_post(db, local_now() + timedelta(hours=2))

    scheduler._restore_scheduled_jobs()

    assert len(scheduler.armed) == 1, "a future post must survive a restart"
    assert scheduler.armed[0]["id"] == post.job_id
    db.refresh(post)
    assert status_of(post) == "scheduled"


def test_rearmed_job_keeps_the_users_wall_clock(db, scheduler):
    """The regression that a grace-window fix would otherwise expose.

    `scheduled_time` is naive and means 09:00 *in the user's zone*. Read in the
    container's zone (UTC in production) the same value is 09:00 UTC — 14:30
    for Asia/Kolkata, five and a half hours late.
    """
    tz = pytz.timezone(TZ_NAME)
    naive_nine_am = (datetime.now(tz) + timedelta(days=1)).replace(
        hour=9, minute=0, second=0, microsecond=0, tzinfo=None
    )
    make_scheduled_post(db, naive_nine_am)

    scheduler._restore_scheduled_jobs()

    run_date = scheduler.armed[0]["trigger"].run_date
    assert run_date.tzinfo is not None, "an unlocalised trigger drifts by the offset"
    assert run_date.astimezone(tz).hour == 9
    assert run_date.astimezone(tz).minute == 0


def test_slightly_late_post_still_publishes(db, scheduler, monkeypatch):
    """Within the grace window the post is armed, not written off.

    This is the deploy-and-restart case: a few minutes of downtime should not
    cost the post.
    """
    monkeypatch.setattr(
        scheduler.settings, "scheduler_misfire_grace_seconds", 3600, raising=False
    )
    post = make_scheduled_post(db, local_now() - timedelta(minutes=10))

    scheduler._restore_scheduled_jobs()

    assert len(scheduler.armed) == 1, "10 minutes late is inside a 1 hour window"
    db.refresh(post)
    assert status_of(post) == "scheduled"


def test_overdue_post_is_failed_with_a_reason_not_silently_dropped(
    db, scheduler, monkeypatch
):
    """The core bug: a missed post used to stay `scheduled` forever.

    Nothing fired, nothing failed, and the Queue reported it as pending — so
    the one screen built to explain a missing post explained nothing.
    """
    monkeypatch.setattr(
        scheduler.settings, "scheduler_misfire_grace_seconds", 3600, raising=False
    )
    post = make_scheduled_post(db, local_now() - timedelta(hours=9))

    scheduler._restore_scheduled_jobs()

    assert scheduler.armed == [], "a post this late must not publish at the wrong hour"
    db.refresh(post)
    assert status_of(post) == "failed"
    assert "9h" in post.error_message, post.error_message
    assert "Reschedule" in post.error_message


def test_a_post_missing_its_job_id_is_reported_not_skipped(db, scheduler, caplog):
    """It cannot fire and cannot explain itself, so it must at least be logged."""
    post = make_scheduled_post(db, local_now() + timedelta(hours=1))
    post.job_id = None
    db.commit()

    scheduler._restore_scheduled_jobs()

    assert scheduler.armed == []
    assert any(str(post.id) in record.message for record in caplog.records)
