"""Shared test setup.

The suite must not depend on whatever is in the developer's `.env`. Settings
are loaded by pydantic-settings with `env_file=".env"`, so any value sitting in
that file silently becomes the default for every test that does not override
it - and the file is real, local, and edited by hand (and by
`backend.admin_cli pin`).

That produced a genuinely confusing failure: pinning an admin identity wrote
ADMIN_LINKEDIN_SUBS into .env, which disabled the "first account becomes admin"
bootstrap, and four tests started failing locally while CI - which has no .env
at all - stayed green. Tests that pass on one machine and fail on another for
reasons invisible in the diff are worth spending a fixture on.

So: the settings that change identity and access behaviour are cleared before
every test. A test that wants one of them sets it itself, and still can,
because its own monkeypatch runs after this fixture.
"""

import pytest

# Pinned before every test, to the value the model itself defaults to. Scoped
# deliberately tightly: only settings that decide who may sign in and what they
# may do. Infrastructure settings (database, keys, origins) are supplied by
# each test's own fixture already, and clearing those broke app construction
# rather than isolating anything.
#
# Booleans get their real default rather than "" — pydantic refuses an empty
# string as a boolean, which is how this list first went wrong.
ISOLATED_ENV_VARS = {
    "ADMIN_LINKEDIN_SUBS": "",
    "ADMIN_CLERK_EMAILS": "",
    "ALLOW_NEW_SIGNUPS": "true",
    "ALLOW_GUEST_ACCESS": "true",
}


@pytest.fixture(autouse=True)
def isolate_env_from_dotenv(monkeypatch):
    """Neutralise .env values that would otherwise leak into a test.

    setenv rather than delenv: an unset variable falls through to the .env
    file, which is the thing being defended against. An explicit value wins.
    """
    for name, value in ISOLATED_ENV_VARS.items():
        monkeypatch.setenv(name, value)


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Drop rate-limit counters between tests.

    The limiter is process-global by design (one worker, one dict). In the
    suite that means every test client shares the key `ip:127.0.0.1`, so a file
    that legitimately signs in a dozen guests exhausts the hourly allowance and
    the NEXT test fails with a 429 that has nothing to do with what it is
    testing. Same category as the singletons below.
    """
    from backend.utils.http_security import reset_limits

    reset_limits()
    yield
    reset_limits()


@pytest.fixture(autouse=True)
def reset_reel_manager():
    """Drop the cached ReelManager between tests.

    It is a module-level singleton that captures REELS_FOLDER the first time it
    is asked for. Tests each point that at their own tmp_path, so without this
    the second test onwards writes files into the FIRST test's directory while
    the code under test reads the current one - and the mismatch shows up as an
    assertion about orphaned files that makes no sense on its own.
    """
    import backend.core.reel_manager as reel_manager

    reel_manager._reel_manager = None
    yield
    reel_manager._reel_manager = None
