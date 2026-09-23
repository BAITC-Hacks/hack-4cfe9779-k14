from app.models import ChatAttachment, ChatSession, IdempotencyKey, Message, PendingOffer, Product


def test_catalog_constraints_and_indexes_exist() -> None:
    product = Product.__table__
    assert product.c.article.unique is True
    assert product.c.characteristics.type.__class__.__name__ == "JSONB"
    assert any(index.name == "ix_products_search_vector" for index in product.indexes)


def test_temporary_entities_have_expiry_and_creation_time() -> None:
    for model in (PendingOffer, IdempotencyKey, ChatAttachment):
        assert "created_at" in model.__table__.c
        assert "expires_at" in model.__table__.c
        assert any("expires_at" in index.columns.keys() for index in model.__table__.indexes)


def test_chat_entities_are_mapped() -> None:
    assert "chat_sessions" == ChatSession.__tablename__
    assert "messages" == Message.__tablename__
    assert "session_id" in Message.__table__.c
