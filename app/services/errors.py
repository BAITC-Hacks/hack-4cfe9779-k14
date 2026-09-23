class ApplicationError(Exception):
    """Base class for expected application errors."""

    code = "application_error"
    status_code = 400


class ResourceNotFound(ApplicationError):
    code = "not_found"
    status_code = 404
