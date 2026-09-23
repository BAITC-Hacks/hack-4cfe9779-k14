"""Reusable OpenAPI metadata for the public browser/API contract."""

from app.schemas.errors import ErrorResponse


_ERROR_DESCRIPTIONS = {
    400: "Malformed client request.",
    404: "Requested session, offer or product was not found.",
    409: "The resource cannot transition from its current state.",
    413: "Attachment is larger than the configured limit.",
    415: "Attachment type is not supported.",
    422: "Request validation or attachment processing failed.",
    502: "The upstream catalog returned invalid data.",
    503: "A required dependency is unavailable.",
}


def public_error_responses(*status_codes: int) -> dict[int, dict[str, object]]:
    """Describe the global ``{code, message}`` error envelope in OpenAPI."""

    return {
        status_code: {
            "model": ErrorResponse,
            "description": _ERROR_DESCRIPTIONS[status_code],
        }
        for status_code in status_codes
    }
