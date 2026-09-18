"""Service-layer failures and the HTTP status each one becomes.

Services must not import FastAPI (they are reused by the background task and by scripts/),
so they raise these instead. `create_app()` installs one handler for the whole hierarchy
and renders `{"detail": exc.detail}`.
"""


class AppError(Exception):
    """Base class. `detail` is rendered as the JSON body's `detail` field."""

    status_code: int = 400

    def __init__(self, detail: object) -> None:
        super().__init__(detail if isinstance(detail, str) else repr(detail))
        self.detail = detail


class NotFoundError(AppError):
    """Missing, or owned by another tenant — docs/PLAN.md section 4 says 404, not 403."""

    status_code = 404


class ConflictError(AppError):
    """The row exists but is in the wrong state for this transition."""

    status_code = 409


class InvalidConfigError(AppError):
    """A config_overrides payload PipelineConfig refuses."""

    status_code = 422


class DuplicateUploadError(AppError):
    status_code = 409


class FileTooLargeError(AppError):
    status_code = 413


class InvalidUploadError(AppError):
    status_code = 422


class UnsupportedMediaError(AppError):
    """The bytes don't match any accepted file type (docs/PLAN.md section 6, proof uploads)."""

    status_code = 415
