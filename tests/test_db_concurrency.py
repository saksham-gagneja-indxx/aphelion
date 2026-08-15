"""The database layer has to survive concurrent requests.

The engine previously used StaticPool for file-backed SQLite, which shares ONE
sqlite3 connection across every thread. Two requests overlapping on that
connection interleaved their transactions, and the failures were ugly and
non-deterministic:

    sqlite3.InterfaceError: bad parameter or other API misuse
    sqlite3.OperationalError: cannot commit - no transaction is active
    ValueError: Invalid isoformat string: ''

It reproduced by simply opening the Admin page, which fires three API calls at
once. Every authenticated request writes (last_seen_at), so this is not an
exotic path - it is every request.
"""

import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

import pytest

API_KEY = "test-key-concurrency"


@pytest.fixture
def app(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    monkeypatch.setenv("API_ACCESS_KEY", API_KEY)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")

    import backend.utils.database as database

    database._db_instance = None

    from backend.app import create_app

    application = create_app()
    application.config["TESTING"] = True
    yield application

    database._db_instance = None
    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(path + suffix)
        except OSError:
            pass


@pytest.fixture
def user(app):
    from backend.models.user import User
    from backend.utils.database import get_session

    db = get_session()
    try:
        u = User(
            linkedin_sub="sub-concurrency",
            full_name="Concurrent User",
            email="c@test",
            role="admin",
            is_active=True,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        db.expunge(u)
        return u
    finally:
        db.close()


def test_file_backed_sqlite_does_not_share_one_connection():
    """StaticPool on a file database is the bug; assert we do not use it."""
    from sqlalchemy.pool import StaticPool

    import backend.utils.database as database

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        os.environ["DATABASE_URL"] = f"sqlite:///{path}"
        database._db_instance = None
        db = database.get_db()
        assert not isinstance(db.engine.pool, StaticPool), (
            "file-backed SQLite must not use StaticPool - it shares a single "
            "connection across threads"
        )
    finally:
        database._db_instance = None
        os.environ.pop("DATABASE_URL", None)
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(path + suffix)
            except OSError:
                pass


def test_in_memory_sqlite_still_shares_its_connection():
    """The opposite case: :memory: genuinely needs StaticPool."""
    from sqlalchemy.pool import StaticPool

    import backend.utils.database as database

    try:
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        database._db_instance = None
        db = database.get_db()
        assert isinstance(db.engine.pool, StaticPool)
    finally:
        database._db_instance = None
        os.environ.pop("DATABASE_URL", None)


def test_parallel_authenticated_requests_all_succeed(app, user):
    """What the Admin page does: several authenticated calls at once.

    Every authenticated request writes last_seen_at, so 16 of them in parallel
    is 16 concurrent transactions. On the shared connection this produced 500s
    roughly a third of the time.
    """
    from backend.utils.security import make_session_token

    token = make_session_token(user.id)
    headers = {"Authorization": f"Bearer {token}"}
    paths = ["/api/admin/users", "/api/admin/audit?limit=10", "/api/admin/stats"]

    def hit(i):
        with app.test_client() as client:
            return client.get(paths[i % len(paths)], headers=headers).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(hit, range(24)))

    assert all(code == 200 for code in codes), f"got non-200 responses: {codes}"


def test_parallel_writes_do_not_corrupt_each_other(app, user):
    """Concurrent commits on separate sessions must not interleave."""
    from backend.models.user import User
    from backend.utils.database import get_session

    def rename(i):
        db = get_session()
        try:
            u = db.query(User).filter(User.id == user.id).first()
            u.account_name = f"name-{i}"
            db.commit()
            return True
        except Exception:
            return False
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(rename, range(24)))

    assert all(results), "concurrent writes raised"

    db = get_session()
    try:
        # Whichever won, the row must still be readable and well-formed.
        refreshed = db.query(User).filter(User.id == user.id).first()
        assert refreshed.account_name.startswith("name-")
        assert refreshed.email == "c@test"
    finally:
        db.close()
