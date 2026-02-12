from app.core.config import settings
from sqlalchemy import create_engine, text

uri = settings.sqlalchemy_database_uri
engine = create_engine(
    uri,
    connect_args={"check_same_thread": False} if uri.startswith("sqlite") else {},
)

with engine.connect() as c:
    cols = c.execute(text("PRAGMA table_info(champions)")).fetchall()

print("URI =", uri)
print("COLS =", [r[1] for r in cols])
