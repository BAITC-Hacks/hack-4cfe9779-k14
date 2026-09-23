import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://frontend.test")
