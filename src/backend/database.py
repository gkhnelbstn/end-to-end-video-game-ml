# """
# Database connection and session management for the Game Insight project.
#
# This module sets up the SQLAlchemy engine and session factory.
# """
import os
from sqlalchemy import create_engine, text # event import'ını kaldırabilirsin
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
# from sqlalchemy.pool import Pool # Gerekmiyorsa kaldır
# from sqlalchemy import event # Gerekmiyorsa kaldır

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set.")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Bu kısmı kaldır veya yorum satırına al
# @event.listens_for(Pool, "connect")
# def on_connect(dbapi_con, connection_record):
#     """
#     Execute the views.sql file on each new connection.
#     This ensures the view is always up to date.
#     """
#     cursor = dbapi_con.cursor()
#     try:
#         with open('src/backend/views.sql', 'r') as f:
#             sql = f.read()
#             if sql.strip():
#                 cursor.execute(sql)
#     finally:
#         cursor.close()

def get_db():
    """
    Dependency to get a database session.

    Yields:
        A new database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# engine'in dışa aktarılması önemliydi, onu koru
__all__ = ["Base", "engine", "SessionLocal"]