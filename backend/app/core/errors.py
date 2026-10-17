"""Application errors. Each one carries an HTTP status and a short machine-readable code."""


class AppError(Exception):
    status_code: int = 500
    code: str = "app_error"

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class InvalidStatusTransitionError(ConflictError):
    code = "invalid_status_transition"


class DatabaseError(AppError):
    status_code = 500
    code = "database_error"