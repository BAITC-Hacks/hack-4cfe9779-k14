class ApplicationError(Exception):
    """Base class for expected application errors."""

    code = "application_error"
    status_code = 400


class ResourceNotFound(ApplicationError):
    code = "not_found"
    status_code = 404


class OfferConflict(ApplicationError):
    code = "offer_conflict"
    status_code = 409


class OfferPreconditionFailed(ApplicationError):
    code = "offer_precondition_failed"
    status_code = 409


class AttachmentTooLarge(ApplicationError):
    code = "attachment_too_large"
    status_code = 413


class UnsupportedAttachment(ApplicationError):
    code = "unsupported_attachment"
    status_code = 415


class AttachmentProcessingFailed(ApplicationError):
    code = "attachment_processing_failed"
    status_code = 422


class CatalogUnavailable(ApplicationError):
    code = "catalog_unavailable"
    status_code = 503


class CatalogAuthenticationFailed(ApplicationError):
    code = "catalog_authentication_failed"
    status_code = 503


class CatalogDataInvalid(ApplicationError):
    code = "catalog_data_invalid"
    status_code = 502
