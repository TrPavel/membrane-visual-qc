"""Thread-safe Stage 4B1 retrieval/cancellation publication state.

The operation lock only linearizes in-process state transitions.  It is never
held while doing network, scientific validation, or cache repository work.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import threading
from typing import Callable, Protocol, TypeVar

from .pdbtm_errors import Stage4BError, Stage4BErrorCode
from .pdbtm_provider import PdbtmProviderClient, ValidatedPdbtmPair, canonicalize_record_id


class CommitState(str, Enum):
    OPEN = "OPEN"
    CANCELLED = "CANCELLED"
    FAILED_PRE_COMMIT = "FAILED_PRE_COMMIT"
    COMMITTING = "COMMITTING"
    COMMITTED = "COMMITTED"
    COMMIT_FAILED = "COMMIT_FAILED"


class DeliveryDisposition(str, Enum):
    ACTIVE = "ACTIVE"
    IGNORED_STALE = "IGNORED_STALE"


class InternalOutcome(str, Enum):
    COMMITTED_RESULT_IGNORED = "COMMITTED_RESULT_IGNORED"


class CacheRepository(Protocol):
    """Repository surface required by the retrieval orchestrator."""

    def capture_record_generation(self, record_id: str) -> int: ...

    def commit_validated_pair(
        self,
        candidate: ValidatedPdbtmPair,
        *,
        expected_record_generation: int,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class OperationSnapshot:
    commit_state: CommitState
    delivery_disposition: DeliveryDisposition
    internal_outcome: InternalOutcome | None
    error_code: Stage4BErrorCode | None


class RetrievalOperation:
    """Linearize cancellation, commit authorization, and result delivery."""

    def __init__(self) -> None:
        self._mutex = threading.Lock()
        self._state = CommitState.OPEN
        self._delivery = DeliveryDisposition.ACTIVE
        self._error: Stage4BError | None = None
        self._result: object | None = None

    @property
    def is_cancelled(self) -> bool:
        with self._mutex:
            return self._state is CommitState.CANCELLED

    @property
    def commit_state(self) -> CommitState:
        with self._mutex:
            return self._state

    @property
    def delivery_disposition(self) -> DeliveryDisposition:
        with self._mutex:
            return self._delivery

    @property
    def result(self) -> object | None:
        with self._mutex:
            return self._result

    @property
    def error(self) -> Stage4BError | None:
        with self._mutex:
            return self._error

    def request_cancel(self) -> bool:
        """Cancel if OPEN; otherwise make any eventual result stale."""

        with self._mutex:
            if self._state is CommitState.OPEN:
                self._state = CommitState.CANCELLED
                return True
            if self._state in {CommitState.COMMITTING, CommitState.COMMITTED}:
                self._delivery = DeliveryDisposition.IGNORED_STALE
            return False

    def invalidate_delivery(self) -> None:
        """Make a committed/future result informational rather than deliverable."""

        with self._mutex:
            self._delivery = DeliveryDisposition.IGNORED_STALE

    def authorize_commit(self) -> None:
        """Atomically win OPEN -> COMMITTING against cancellation."""

        with self._mutex:
            if self._state is CommitState.CANCELLED:
                raise _cancelled_error()
            if self._state is not CommitState.OPEN:
                raise RuntimeError(f"cannot authorize commit from {self._state.value}")
            self._state = CommitState.COMMITTING

    def fail_pre_commit(self, error: Stage4BError) -> bool:
        """Record an expected failure only while the operation remains OPEN."""

        with self._mutex:
            if self._state is CommitState.OPEN:
                self._state = CommitState.FAILED_PRE_COMMIT
                self._error = error
                return True
            return False

    def commit_succeeded(self, result: object) -> None:
        with self._mutex:
            if self._state is not CommitState.COMMITTING:
                raise RuntimeError(f"cannot complete commit from {self._state.value}")
            self._state = CommitState.COMMITTED
            self._result = result

    def commit_failed(self, error: Stage4BError) -> None:
        with self._mutex:
            if self._state is not CommitState.COMMITTING:
                raise RuntimeError(f"cannot fail commit from {self._state.value}")
            self._state = CommitState.COMMIT_FAILED
            self._error = error

    def snapshot(self) -> OperationSnapshot:
        with self._mutex:
            outcome = (
                InternalOutcome.COMMITTED_RESULT_IGNORED
                if self._state is CommitState.COMMITTED
                and self._delivery is DeliveryDisposition.IGNORED_STALE
                else None
            )
            return OperationSnapshot(
                self._state,
                self._delivery,
                outcome,
                None if self._error is None else self._error.code,
            )


def _cancelled_error() -> Stage4BError:
    return Stage4BError(
        code=Stage4BErrorCode.RETRIEVAL_CANCELLED,
        user_message="PDBTM retrieval was cancelled.",
        retryable=False,
        existing_cache_usable=True,
    )


T = TypeVar("T")
Hook = Callable[[], None]


@dataclass(frozen=True, slots=True)
class RetrievalHooks:
    """Deterministic synchronization points for concurrency/failpoint tests."""

    after_generation_capture: Hook | None = None
    after_pair_validation: Hook | None = None
    before_commit_authorization: Hook | None = None
    after_commit_authorization: Hook | None = None
    after_repository_commit: Hook | None = None


def _run(hook: Hook | None) -> None:
    if hook is not None:
        hook()


def retrieve_validate_and_commit(
    record_id: str,
    *,
    provider: PdbtmProviderClient,
    repository: CacheRepository,
    operation: RetrievalOperation | None = None,
    hooks: RetrievalHooks | None = None,
) -> object:
    """Fetch, validate, then publish one pair under generation authorization."""

    operation = operation or RetrievalOperation()
    hooks = hooks or RetrievalHooks()
    try:
        canonical_id = canonicalize_record_id(record_id)
        generation = repository.capture_record_generation(canonical_id)
        _run(hooks.after_generation_capture)
        if operation.is_cancelled:
            raise _cancelled_error()
        candidate = provider.fetch(canonical_id, cancellation=operation)
        _run(hooks.after_pair_validation)
        if operation.is_cancelled:
            raise _cancelled_error()
        _run(hooks.before_commit_authorization)
        operation.authorize_commit()
    except Stage4BError as error:
        if operation.is_cancelled:
            raise _cancelled_error() from error
        operation.fail_pre_commit(error)
        raise

    _run(hooks.after_commit_authorization)
    try:
        committed = repository.commit_validated_pair(
            candidate,
            expected_record_generation=generation,
        )
        _run(hooks.after_repository_commit)
    except Stage4BError as error:
        operation.commit_failed(error)
        raise
    operation.commit_succeeded(committed)
    return committed
