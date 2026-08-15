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
