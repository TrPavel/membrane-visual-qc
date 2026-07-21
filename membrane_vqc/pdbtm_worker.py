"""Stage 4B3 Qt-free asynchronous PDBTM orchestration.

This module is the sole plain-Python glue between the GUI and the Stage 4B1
transport/cache stack and the Stage 4B2 report-provenance conversion. It may
perform network and filesystem I/O, but it must never import PyMOL or Qt, and
it never touches a live PyMOL object, a widget, or ``qc.LAST_REPORT``. Every
request handler here is a plain function/method: fully unit-testable with
fakes, with no thread or signal concerns of its own. A thin Qt/QThread glue
layer (``pdbtm_gui_worker``) wraps this orchestrator for the dialog.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .pdbtm_cache import CachedSnapshot, PdbtmCacheRepository
from .pdbtm_errors import Stage4BError
from .pdbtm_provider import PdbtmProviderClient, canonicalize_record_id
from .pdbtm_retrieval import RetrievalOperation, retrieve_validate_and_commit
from .pdbtm_transport import PdbtmHttpsTransport

CacheRepositoryFactory = Callable[[], PdbtmCacheRepository]
ProviderFactory = Callable[[], PdbtmProviderClient]


def _default_provider() -> PdbtmProviderClient:
    return PdbtmProviderClient(PdbtmHttpsTransport())


@dataclass(frozen=True, slots=True)
class InspectResult:
    """Safe, display-only cache status for one canonical record ID."""

    canonical_record_id: str
    cache_generation: int
    record_present: bool
    active_snapshot_id: str | None
    snapshot_count: int


@dataclass(frozen=True, slots=True)
class ClearResult:
    """Outcome of clearing one cached record."""

    canonical_record_id: str
    tombstone_generation: int


@dataclass(frozen=True, slots=True)
class WorkerFailure:
    """A redacted, stable failure independent of Qt/PyMOL, safe to display."""

    code: str
    message: str
    retryable: bool
    existing_cache_usable: bool


def failure_from_error(error: Stage4BError) -> WorkerFailure:
    return WorkerFailure(
        code=error.code.value,
        message=error.user_message,
        retryable=error.retryable,
        existing_cache_usable=error.existing_cache_usable,
    )


class PdbtmWorkerOrchestrator:
    """Pure-Python request handlers; safe to call from any single thread.

    One instance is normally created per dialog/session and driven from a
    single background thread at a time; it holds no cross-request mutable
    state of its own beyond the factories used to construct a repository or
    provider client per call.
    """

    def __init__(
        self,
        *,
        cache_repository_factory: CacheRepositoryFactory = PdbtmCacheRepository,
        provider_factory: ProviderFactory = _default_provider,
    ) -> None:
        self._cache_repository_factory = cache_repository_factory
        self._provider_factory = provider_factory

    def inspect(self, record_id: str) -> InspectResult:
        """Return safe, network-free cache status for one canonical record ID."""

        canonical_id = canonicalize_record_id(record_id)
        repository = self._cache_repository_factory()
        inspection = repository.inspect()
        record = inspection.records.get(canonical_id)
        if record is None:
            return InspectResult(canonical_id, inspection.generation, False, None, 0)
        return InspectResult(
            canonical_id,
            inspection.generation,
            True,
            record.active_snapshot_id,
            len(record.snapshot_ids),
        )

    def fetch(self, record_id: str, operation: RetrievalOperation) -> CachedSnapshot:
        """Retrieve, validate, and commit one pair. The only network-causing call."""

        canonical_id = canonicalize_record_id(record_id)
        repository = self._cache_repository_factory()
        provider = self._provider_factory()
        return retrieve_validate_and_commit(
            canonical_id,
            provider=provider,
            repository=repository,
            operation=operation,
        )

    def use_cached_pair(self, record_id: str) -> CachedSnapshot:
        """Integrity-read and semantically revalidate the active cached snapshot."""

        canonical_id = canonicalize_record_id(record_id)
        repository = self._cache_repository_factory()
        return repository.read_active(canonical_id)

    def clear(self, record_id: str) -> ClearResult:
        """Clear one cached record. Never touches PyMOL objects or reports."""

        canonical_id = canonicalize_record_id(record_id)
        repository = self._cache_repository_factory()
        tombstone = repository.clear(canonical_id)
        return ClearResult(canonical_id, tombstone)
