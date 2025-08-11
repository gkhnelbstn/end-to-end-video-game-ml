"""
A script to create an initial admin user for the Game Insight project.
"""
import asyncio
from getpass import getpass
from sqlalchemy.orm import Session
from src.backend.database import SessionLocal
from src.backend.models import User, UserRole
from src.backend.admin import pwd_context

async def create_admin_user():
    """
    Creates an admin user in the database.
    """
    print("Creating admin user...")
    email = input("Admin Email: ")
    password = getpass("Admin Password: ")

    db: Session = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    if user:
        print("User with this email already exists.")
        db.close()
        return

    hashed_password = pwd_context.hash(password)
    admin_user = User(
        email=email,
        hashed_password=hashed_password,
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin_user)
    db.commit()
    db.close()
    print(f"Admin user {email} created successfully.")

if __name__ == "__main__":
    asyncio.run(create_admin_user())
