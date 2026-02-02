from __future__ import annotations

import argparse

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User
from app.repositories import users as users_repo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an admin user for the CAPA app.")
    parser.add_argument("--username", required=True, help="Admin username")
    parser.add_argument("--password", required=True, help="Admin password")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db = SessionLocal()
    try:
        existing = users_repo.get_user_by_username(db, args.username)
        if existing:
            print(f"User '{args.username}' already exists.")
            return
        user = User(
            username=args.username,
            password_hash=hash_password(args.password),
            role="admin",
            is_active=True,
        )
        users_repo.create_user(db, user)
        print(f"Created admin user '{args.username}'.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
