"""Stable user-facing errors for Stage 4B network and cache operations."""

from __future__ import annotations

from enum import Enum

from .errors import MVQCError


class Stage4BErrorCode(str, Enum):
    """Stable machine-readable failure codes for the Stage 4B contract."""

    INVALID_RECORD_ID = "INVALID_RECORD_ID"
    CACHE_MISS = "CACHE_MISS"
    CACHE_CORRUPT = "CACHE_CORRUPT"
    CACHE_WRITE_FAILED = "CACHE_WRITE_FAILED"
    CACHE_CONFLICT = "CACHE_CONFLICT"
    CACHE_FORMAT_UNSUPPORTED = "CACHE_FORMAT_UNSUPPORTED"
    CACHE_CLEAR_FAILED = "CACHE_CLEAR_FAILED"
    CACHE_OPEN_FAILED = "CACHE_OPEN_FAILED"
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    NETWORK_UNAVAILABLE = "NETWORK_UNAVAILABLE"
    PROXY_UNSUPPORTED = "PROXY_UNSUPPORTED"
    TLS_ERROR = "TLS_ERROR"
    REDIRECT_DISALLOWED = "REDIRECT_DISALLOWED"
    RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE"
    PROVIDER_NOT_FOUND = "PROVIDER_NOT_FOUND"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    PROVIDER_SERVER_ERROR = "PROVIDER_SERVER_ERROR"
    PROVIDER_RESPONSE_INVALID = "PROVIDER_RESPONSE_INVALID"
    COMPANION_ID_MISMATCH = "COMPANION_ID_MISMATCH"
    PAIR_VALIDATION_FAILED = "PAIR_VALIDATION_FAILED"
    RETRIEVAL_CANCELLED = "RETRIEVAL_CANCELLED"


_ERROR_METADATA: dict[Stage4BErrorCode, tuple[str, bool, bool]] = {
    Stage4BErrorCode.INVALID_RECORD_ID: (
        "Enter a four-character PDB ID such as 1pcr.",
        False,
        True,
    ),
    Stage4BErrorCode.CACHE_MISS: (
        "No validated cached PDBTM pair is available.",
        True,
        False,
    ),
    Stage4BErrorCode.CACHE_CORRUPT: (
        "Cached pair failed integrity validation and will not be used.",
        True,
        False,
    ),
    Stage4BErrorCode.CACHE_WRITE_FAILED: (
        "The validated pair could not be saved; the previous cache remains active.",
        True,
        True,
    ),
    Stage4BErrorCode.CACHE_CONFLICT: (
        "The cached record changed during retrieval; refresh again if needed.",
        True,
        True,
    ),
    Stage4BErrorCode.CACHE_FORMAT_UNSUPPORTED: (
        "The cache format is not supported by this version.",
        False,
        False,
    ),
    Stage4BErrorCode.CACHE_CLEAR_FAILED: (
        "The cached record could not be cleared.",
        True,
        True,
    ),
    Stage4BErrorCode.CACHE_OPEN_FAILED: (
        "The PDBTM cache could not be opened safely.",
        True,
        False,
    ),
    Stage4BErrorCode.NETWORK_TIMEOUT: (
        "PDBTM did not respond within the allowed time.",
        True,
        True,
    ),
    Stage4BErrorCode.NETWORK_UNAVAILABLE: (
        "The PDBTM service is currently unreachable.",
        True,
        True,
    ),
    Stage4BErrorCode.PROXY_UNSUPPORTED: (
        "This version supports direct HTTPS connections only. Configure direct access or use "
        "an existing offline/cached PDBTM pair.",
        True,
        True,
    ),
    Stage4BErrorCode.TLS_ERROR: (
        "Secure connection verification failed; no data was accepted.",
        True,
        True,
    ),
    Stage4BErrorCode.REDIRECT_DISALLOWED: (
        "The provider redirected outside the reviewed endpoint contract.",
        False,
        True,
    ),
    Stage4BErrorCode.RESPONSE_TOO_LARGE: (
        "Provider response exceeded the safety limit.",
        False,
        True,
    ),
    Stage4BErrorCode.PROVIDER_NOT_FOUND: (
        "PDBTM has no record for this identifier.",
        False,
        True,
    ),
    Stage4BErrorCode.PROVIDER_RATE_LIMITED: (
        "PDBTM rate-limited this request; retry manually later.",
        True,
        True,
    ),
    Stage4BErrorCode.PROVIDER_SERVER_ERROR: (
        "PDBTM returned a server error; the record status is unknown.",
        True,
        True,
    ),
    Stage4BErrorCode.PROVIDER_RESPONSE_INVALID: (
        "The provider response does not match the reviewed contract.",
        True,
        True,
    ),
    Stage4BErrorCode.COMPANION_ID_MISMATCH: (
        "The two provider payloads do not identify one record.",
        True,
        True,
    ),
    Stage4BErrorCode.PAIR_VALIDATION_FAILED: (
        "The retrieved pair failed scientific contract validation.",
        True,
        True,
    ),
    Stage4BErrorCode.RETRIEVAL_CANCELLED: (
        "PDBTM retrieval was cancelled.",
        True,
        True,
    ),
}


class Stage4BError(MVQCError):
    """A redacted expected failure with stable handling metadata."""

    def __init__(
        self,
        code: Stage4BErrorCode,
        *,
        user_message: str | None = None,
        retryable: bool | None = None,
        existing_cache_usable: bool | None = None,
    ) -> None:
        default_message, default_retryable, default_cache_usable = _ERROR_METADATA[code]
        self.code = code
        self.user_message = user_message if user_message is not None else default_message
        self.retryable = default_retryable if retryable is None else retryable
        self.existing_cache_usable = (
            default_cache_usable if existing_cache_usable is None else existing_cache_usable
        )
        super().__init__(self.user_message)
