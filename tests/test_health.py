from collections.abc import AsyncGenerator

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.config.database import get_db
from app.main import app


class FakeSession:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def execute(self, statement):
        if self.fail:
            raise OperationalError("SELECT 1", {}, RuntimeError("connection refused"))
        return 1


def override_session(fail: bool = False):
    async def dependency() -> AsyncGenerator[FakeSession, None]:
        yield FakeSession(fail=fail)

    return dependency


def test_health_reports_api_and_database_ok() -> None:
    app.dependency_overrides[get_db] = override_session()
    try:
        with TestClient(app) as client:
            response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "ok"}
    finally:
        app.dependency_overrides.clear()


def test_health_reports_database_unavailable() -> None:
    app.dependency_overrides[get_db] = override_session(fail=True)
    try:
        with TestClient(app) as client:
            response = client.get("/health")
        assert response.status_code == 503
        assert response.json()["code"] == "database_unavailable"
    finally:
        app.dependency_overrides.clear()
