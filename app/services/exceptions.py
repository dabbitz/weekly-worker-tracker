class ServiceError(Exception):
    """Base class for business-rule failures mapped to HTTP responses."""

    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(ServiceError):
    status_code = 404


class ConflictError(ServiceError):
    status_code = 409


class ValidationError(ServiceError):
    status_code = 422
