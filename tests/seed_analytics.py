"""Seed a synthetic Analytics row so the Analytics UI can be exercised
before real Instagram engagement data exists.

Run:  .venv/Scripts/python.exe tests/seed_analytics.py
Undo: .venv/Scripts/python.exe tests/seed_analytics.py --clear
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.utils.database import get_session, init_db  # noqa: E402
from backend.models.analytics import Analytics  # noqa: E402

USER_ID = 1


def main() -> int:
    init_db()
    db = get_session()

    existing = db.query(Analytics).filter(Analytics.user_id == USER_ID).all()
    for row in existing:
        db.delete(row)
    db.commit()

    if "--clear" in sys.argv:
        print(f"Cleared {len(existing)} analytics row(s) for user {USER_ID}")
        db.close()
        return 0

    row = Analytics(
        user_id=USER_ID,
        total_posts_analyzed=42,
        average_likes=318.5,
        average_comments=24.25,
        # 0=Monday .. 6=Sunday, matching Python's weekday()
        best_posting_hours=[18, 21, 12],
        best_posting_days=[2, 4, 6],
        peak_engagement_hour=21,
        # Stored naive-UTC to match the rest of the models' columns.
        last_calculated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(row)
    db.commit()

    print(f"Seeded analytics for user {USER_ID}: id={row.id}")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
