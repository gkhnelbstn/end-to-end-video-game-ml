"""Create an admin panel account.

Usage: docker compose exec backend python -m src.backend.create_admin
"""

from getpass import getpass

from sqlalchemy import select

from src.backend import security
from src.backend.database import SessionLocal
from src.backend.models import AdminUser


def main() -> None:
    username = input("Admin username: ").strip()
    password = getpass("Admin password: ")
    if not username or not password:
        raise SystemExit("Username and password are required.")

    with SessionLocal() as db:
        if db.scalar(select(AdminUser).where(AdminUser.username == username)):
            raise SystemExit(f"Admin user '{username}' already exists.")
        db.add(AdminUser(username=username, hashed_password=security.get_password_hash(password)))
        db.commit()
    print(f"Admin user '{username}' created.")


if __name__ == "__main__":
    main()
