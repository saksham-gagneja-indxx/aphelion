"""Administrative command line: bootstrap the first admin, manage accounts.

    python -m backend.admin_cli list
    python -m backend.admin_cli promote <id|email>
    python -m backend.admin_cli pin [<id|email>]
    python -m backend.admin_cli sign-out-all --yes
    python -m backend.admin_cli reset-users --yes

Why this exists at all: the admin allowlist (ADMIN_LINKEDIN_SUBS) is keyed on
LinkedIn's `sub` claim, which nobody knows until that person has signed in once.
So there is a chicken-and-egg step - sign in, then pin the identity that
arrived - and doing it by hand means editing a database and a dotenv file
correctly at 2am. `pin` does both halves.

The intended bootstrap is:

    1. reset-users --yes     (only if the database has leftover test accounts)
    2. sign in with LinkedIn - the first account on an empty database is made
       an active admin automatically
    3. pin                   - writes that account's `sub` into .env, which
       turns off the "first account wins" rule permanently

After step 3 the admin role is pinned to one LinkedIn identity. It is
re-asserted on every sign-in, so editing the database by hand cannot take it
away, and nobody else can claim it even on an empty database.
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

from backend.models.user import User
from backend.utils.database import get_session

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


# ----------------------------------------------------------------- utilities


def _find(db, ident: str):
    """Look a user up by numeric id or by email."""
    if ident.isdigit():
        return db.query(User).filter(User.id == int(ident)).first()
    return db.query(User).filter(User.email == ident).first()


def _backup(path: Path) -> Path:
    """Copy a file next to itself before editing it in place."""
    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    return backup


def _set_env_key(path: Path, key: str, value: str) -> None:
    """Set KEY=value in a dotenv file, preserving everything else.

    Rewrites the existing line if the key is present - including when it is
    commented out - and appends otherwise. Comments, ordering and unrelated
    keys survive, because this file is hand-maintained and clobbering it would
    lose real configuration.
    """
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    pattern = re.compile(rf"^\s*#?\s*{re.escape(key)}\s*=", re.IGNORECASE)
    replacement = f"{key}={value}\n"

    for i, line in enumerate(lines):
        if pattern.match(line):
            lines[i] = replacement
            path.write_text("".join(lines), encoding="utf-8")
            return

    if lines and not lines[-1].endswith("\n"):
        lines.append("\n")
    lines.append(replacement)
    path.write_text("".join(lines), encoding="utf-8")


# ------------------------------------------------------------------ commands


def cmd_list(_args) -> int:
    db = get_session()
    try:
        users = db.query(User).order_by(User.id).all()
        if not users:
            print("No accounts. The next LinkedIn sign-in will claim admin.")
            return 0

        print(f"{'id':>3}  {'role':9} {'active':7} {'name':22} {'email':28} sub")
        print("-" * 100)
        for u in users:
            print(
                f"{u.id:>3}  {u.role:9} "
                f"{'yes' if u.is_active else 'PENDING':7} "
                f"{(u.full_name or '-')[:22]:22} "
                f"{(u.email or '-')[:28]:28} "
                f"{u.linkedin_sub or '-'}"
            )

        pending = [u for u in users if not u.is_active]
        if pending:
            print(f"\n{len(pending)} account(s) awaiting approval.")
        return 0
    finally:
        db.close()


def cmd_promote(args) -> int:
    db = get_session()
    try:
        user = _find(db, args.who)
        if user is None:
            print(f"No account matching {args.who!r}.", file=sys.stderr)
            return 1
        user.role = User.ROLE_ADMIN
        user.is_active = True
        db.commit()
        print(f"{user.full_name or user.id} is now an active admin.")
        if not user.linkedin_sub:
            print(
                "Note: this account has no LinkedIn sub yet, so it cannot be "
                "pinned until it signs in."
            )
        return 0
    finally:
        db.close()


def cmd_demote(args) -> int:
    db = get_session()
    try:
        user = _find(db, args.who)
        if user is None:
            print(f"No account matching {args.who!r}.", file=sys.stderr)
            return 1

        remaining = (
            db.query(User)
            .filter(User.role == User.ROLE_ADMIN, User.is_active.is_(True))
            .count()
        )
        if user.role == User.ROLE_ADMIN and remaining <= 1:
            print(
                "Refusing: this is the last active administrator. "
                "Promote another account first.",
                file=sys.stderr,
            )
            return 1

        user.role = User.ROLE_OPERATOR
        db.commit()
        print(f"{user.full_name or user.id} is now an operator.")
        return 0
    finally:
        db.close()


def cmd_pin(args) -> int:
    """Write admin LinkedIn subs into .env so the role cannot be reassigned."""
    db = get_session()
    try:
        if args.who:
            user = _find(db, args.who)
            if user is None:
                print(f"No account matching {args.who!r}.", file=sys.stderr)
                return 1
            targets = [user]
        else:
            targets = (
                db.query(User).filter(User.role == User.ROLE_ADMIN).order_by(User.id).all()
            )

        if not targets:
            print(
                "No admin accounts to pin. Sign in with LinkedIn first - the "
                "first account on an empty database becomes admin.",
                file=sys.stderr,
            )
            return 1

        subs = [u.linkedin_sub for u in targets if u.linkedin_sub]
        missing = [u for u in targets if not u.linkedin_sub]
        for u in missing:
            print(
                f"Skipping {u.full_name or u.id}: no LinkedIn sub recorded "
                f"(this account has never signed in with LinkedIn).",
                file=sys.stderr,
            )

        if not subs:
            print("Nothing to pin.", file=sys.stderr)
            return 1

        if not ENV_PATH.exists():
            print(f"No .env at {ENV_PATH}", file=sys.stderr)
            return 1

        backup = _backup(ENV_PATH)
        _set_env_key(ENV_PATH, "ADMIN_LINKEDIN_SUBS", ",".join(subs))

        print(f"Pinned {len(subs)} admin identity(ies) in .env (backup: {backup.name}).")
        for u in targets:
            if u.linkedin_sub:
                print(f"  {u.full_name or u.id} <{u.email or '-'}>")
        print(
            "\nRestart the server to apply. The 'first account becomes admin' "
            "bootstrap is now off: only these identities can hold admin, and "
            "the role is restored on every sign-in even if the database is reset."
        )
        return 0
    finally:
        db.close()


def cmd_sign_out_all(args) -> int:
    """Invalidate every session by rotating the signing key.

    Session tokens are stateless and signed with SECRET_KEY, so there is no
    session table to clear - but changing the key makes every already-issued
    token fail its signature check at once.
    """
    if not args.yes:
        print("This signs out every user, including you. Re-run with --yes.")
        return 1

    if not ENV_PATH.exists():
        print(f"No .env at {ENV_PATH}", file=sys.stderr)
        return 1

    import secrets

    backup = _backup(ENV_PATH)
    _set_env_key(ENV_PATH, "SECRET_KEY", secrets.token_urlsafe(48))
    print(f"SECRET_KEY rotated (backup: {backup.name}).")
    print(
        "Every session token is now invalid. Restart the server to apply - "
        "until then the running process still holds the old key."
    )
    return 0


def cmd_reset_users(args) -> int:
    """Delete all accounts so the next LinkedIn sign-in claims admin."""
    db = get_session()
    try:
        count = db.query(User).count()
        if not args.yes:
            print(
                f"This deletes all {count} account(s) and everything owned by "
                f"them. Re-run with --yes."
            )
            return 1

        db.query(User).delete()
        db.commit()
        print(f"Deleted {count} account(s).")
        print(
            "The next account to sign in with LinkedIn becomes an active "
            "admin. Run 'pin' afterwards to make that permanent."
        )
        return 0
    finally:
        db.close()


def cmd_purge_guests(args) -> int:
    """Delete guest accounts, which accumulate one per visitor."""
    db = get_session()
    try:
        guests = db.query(User).filter(User.is_guest.is_(True)).all()
        if not args.yes:
            print(f"{len(guests)} guest account(s). Re-run with --yes to delete them.")
            return 1

        for guest in guests:
            db.delete(guest)
        db.commit()
        print(f"Deleted {len(guests)} guest account(s).")
        return 0
    finally:
        db.close()


def cmd_set_github(args) -> int:
    """Map a GitHub login to a backend user ID for MCP authentication"""
    db = get_session()
    try:
        user = _find(db, args.user_id)
        if user is None:
            print(f"No account matching {args.user_id!r}.", file=sys.stderr)
            return 1

        user.github_username = args.github_login
        db.commit()
        print(f"✅ Mapped GitHub:{args.github_login} → User ID:{user.id}")
        return 0
    except Exception as e:
        print(f"❌ Error setting GitHub username: {str(e)}", file=sys.stderr)
        return 1
    finally:
        db.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m backend.admin_cli",
        description="Bootstrap and manage administrator accounts.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="show every account").set_defaults(func=cmd_list)

    p = sub.add_parser("promote", help="make an account an active admin")
    p.add_argument("who", help="user id or email")
    p.set_defaults(func=cmd_promote)

    p = sub.add_parser("demote", help="make an account an operator")
    p.add_argument("who", help="user id or email")
    p.set_defaults(func=cmd_demote)

    p = sub.add_parser("pin", help="write admin LinkedIn subs into .env")
    p.add_argument("who", nargs="?", help="user id or email (default: all admins)")
    p.set_defaults(func=cmd_pin)

    p = sub.add_parser("sign-out-all", help="invalidate every session token")
    p.add_argument("--yes", action="store_true", help="confirm")
    p.set_defaults(func=cmd_sign_out_all)

    p = sub.add_parser("reset-users", help="delete all accounts")
    p.add_argument("--yes", action="store_true", help="confirm")
    p.set_defaults(func=cmd_reset_users)

    p = sub.add_parser("purge-guests", help="delete all guest accounts")
    p.add_argument("--yes", action="store_true", help="confirm")
    p.set_defaults(func=cmd_purge_guests)

    p = sub.add_parser("set-github", help="map GitHub login to user ID for MCP")
    p.add_argument("user_id", help="user id or email")
    p.add_argument("github_login", help="GitHub username")
    p.set_defaults(func=cmd_set_github)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
