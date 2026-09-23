import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")

os.environ["OPENAI_API_KEY"] = ""  # Unit tests must never use a local real key.
