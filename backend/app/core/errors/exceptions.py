class AppError(Exception):
    """
    Base for all application errors. Every error carries a stable
    machine-readable `code` (for clients/frontends to branch on)
    and a human `message`. Never leak internals (stack traces, SQL,
    file paths) in `message` — that's what logging is for.
    """

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        self.message = message
        if code:
            self.code = code
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    """
    Raised whenever a permission check fails — ownership, role, or
    organization scope. This is the exception every ROLE_PROTECTED /
    OWNER_PROTECTED / ADMIN_ONLY endpoint raises on a failed check.
    """

    status_code = 403
    code = "forbidden"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"
