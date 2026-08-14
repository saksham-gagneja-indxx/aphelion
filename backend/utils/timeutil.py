"""Time helpers.

`datetime.utcnow()` is deprecated from Python 3.12 and scheduled for removal.
The documented replacement, `datetime.now(timezone.utc)`, returns an *aware*
datetime - which is not a drop-in swap here, because every DateTime column in
this project stores naive UTC. Mixing the two raises
"can't compare offset-naive and offset-aware datetimes" at runtime.

`utcnow()` below computes the time correctly and strips the tzinfo, so it
matches what the existing columns and comparisons expect while removing the
deprecated call. Storing aware UTC end-to-end is the better long-term fix, but
that is a schema-wide change, not a 24h-sprint change.
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (tzinfo stripped)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
