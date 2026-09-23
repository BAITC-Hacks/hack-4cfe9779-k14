from pydantic import BaseModel, Field


class CleanupResult(BaseModel):
    expired_offers: int = Field(ge=0)
    expired_idempotency_keys: int = Field(ge=0)
    expired_attachments: int = Field(ge=0)
