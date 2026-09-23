from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes.offers import get_offer_service
from app.main import app
from app.schemas.offers import ConfirmOfferResult, PendingOfferStatus, PendingOfferView


class ApiOfferService:
    def __init__(self) -> None:
        self.offer_id = uuid4()
        self.confirm_calls = []

    def view(self, session_id):
        now = datetime.now(timezone.utc)
        return PendingOfferView(
            offer_id=self.offer_id, session_id=session_id, product_identifier="product-1", article="A-1",
            quantity=1, price_at_offer=Decimal("10"), created_at=now,
            expires_at=now + timedelta(minutes=5), status=PendingOfferStatus.PENDING,
        )

    async def create_offer(self, session_id, payload):
        return self.view(session_id)

    async def confirm_offer(self, session_id, offer_id, idempotency_key):
        self.confirm_calls.append((session_id, offer_id, idempotency_key))
        return ConfirmOfferResult(offer=self.view(session_id), outcome="confirmed", message="added", cart_url="https://cart.invalid")


def test_offer_routes_require_concrete_offer_and_idempotency_key() -> None:
    service = ApiOfferService()
    session_id = uuid4()
    app.dependency_overrides[get_offer_service] = lambda: service
    try:
        with TestClient(app) as client:
            created = client.post(
                f"/api/chat/sessions/{session_id}/offers",
                json={"product_identifier": "product-1", "article": "A-1", "quantity": 1},
            )
            missing_key = client.post(f"/api/chat/sessions/{session_id}/offers/{service.offer_id}/confirm")
            confirmed = client.post(
                f"/api/chat/sessions/{session_id}/offers/{service.offer_id}/confirm",
                headers={"Idempotency-Key": "idem-key-1"},
                json={"article": "ATTEMPTED-CHANGE", "quantity": 999},
            )
        assert created.status_code == 201
        assert missing_key.status_code == 422
        assert confirmed.status_code == 200
        assert confirmed.json()["outcome"] == "confirmed"
        assert service.confirm_calls == [(session_id, service.offer_id, "idem-key-1")]
    finally:
        app.dependency_overrides.clear()
