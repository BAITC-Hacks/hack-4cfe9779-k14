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
