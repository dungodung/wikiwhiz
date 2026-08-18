#!/usr/bin/env python3
"""Bootstrap or manage WikiWhiz admins.

Usage:
  promote_admin.py --username SomeWikimediaUsername
  promote_admin.py --username SomeWikimediaUsername --demote

The user must have logged in at least once already (via OAuth) so their
`users` row exists -- this script only flips the `is_admin` flag, it doesn't
create accounts. This is the only way to create the *first* admin, since the
in-app admin panel (which can promote/demote other users) itself requires
being an admin to reach.
"""

import argparse
import sys

from _db import session_scope

from backend.app.models.user import User


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True, help="Wikimedia username, exact match")
    parser.add_argument("--demote", action="store_true", help="Remove admin instead of granting it")
    args = parser.parse_args()

    with session_scope() as session:
        user = session.query(User).filter_by(wikimedia_username=args.username).first()
        if not user:
            print(
                f"ERROR: no user named {args.username!r} found -- they need to log in via "
                "OAuth at least once first.",
                file=sys.stderr,
            )
            return 1

        if args.demote:
            if user.is_admin:
                other_admins = session.query(User).filter(User.is_admin.is_(True), User.id != user.id).count()
                if other_admins == 0:
                    print("ERROR: refusing to demote the last remaining admin.", file=sys.stderr)
                    return 1
            user.is_admin = False
            print(f"OK: {args.username} is no longer an admin")
        else:
            user.is_admin = True
            print(f"OK: {args.username} is now an admin")

    return 0


if __name__ == "__main__":
    sys.exit(main())
