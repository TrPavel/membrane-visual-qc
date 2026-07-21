from __future__ import annotations

from types import SimpleNamespace

import pytest

from membrane_vqc.pdbtm_errors import Stage4BError, Stage4BErrorCode
from membrane_vqc.pdbtm_retrieval import RetrievalOperation
from membrane_vqc.pdbtm_worker import (
    ClearResult,
    InspectResult,
    PdbtmWorkerOrchestrator,
    WorkerFailure,
    failure_from_error,
)


def _error(code=Stage4BErrorCode.CACHE_MISS):
    return Stage4BError(
        code=code, user_message="safe message", retryable=True, existing_cache_usable=False
    )


class FakeCacheRepository:
    def __init__(self, *, inspection=None, active=None, clear_result=5, generation=3):
        self.inspection = inspection
        self.active = active
        self.clear_result = clear_result
        self.generation = generation
        self.cleared = []
        self.read_active_calls = []
        self.capture_calls = []
        self.commits = []

    def inspect(self):
        return self.inspection

    def read_active(self, record_id, *, validator=None):
        self.read_active_calls.append(record_id)
        if isinstance(self.active, Exception):
            raise self.active
        return self.active

    def clear(self, record_id):
        self.cleared.append(record_id)
        if isinstance(self.clear_result, Exception):
            raise self.clear_result
        return self.clear_result

    def capture_record_generation(self, record_id):
        self.capture_calls.append(record_id)
        return self.generation

    def commit_validated_pair(self, candidate, *, expected_record_generation):
        self.commits.append((candidate, expected_record_generation))
        return "committed-snapshot"


class FakeProvider:
    def __init__(self, candidate="candidate", error=None):
        self.candidate = candidate
        self.error = error
        self.calls = []

    def fetch(self, record_id, *, cancellation=None):
        self.calls.append((record_id, cancellation))
        if self.error:
            raise self.error
        return self.candidate


def _orchestrator(repository, provider=None):
    return PdbtmWorkerOrchestrator(
        cache_repository_factory=lambda: repository,
        provider_factory=lambda: provider or FakeProvider(),
    )


def test_inspect_reports_absent_record_as_not_present():
    repository = FakeCacheRepository(inspection=SimpleNamespace(generation=7, records={}))
    orchestrator = _orchestrator(repository)

    result = orchestrator.inspect("1pcr")

    assert result == InspectResult("1pcr", 7, False, None, 0)


def test_inspect_reports_present_record_with_active_snapshot():
    record = SimpleNamespace(active_snapshot_id="a" * 64, snapshot_ids=("a" * 64, "b" * 64))
    repository = FakeCacheRepository(
        inspection=SimpleNamespace(generation=2, records={"1pcr": record})
    )
    orchestrator = _orchestrator(repository)

    result = orchestrator.inspect("1PCR")

    assert result == InspectResult("1pcr", 2, True, "a" * 64, 2)


def test_inspect_rejects_invalid_record_id_without_touching_repository():
    repository = FakeCacheRepository(inspection=SimpleNamespace(generation=0, records={}))
    orchestrator = _orchestrator(repository)

    with pytest.raises(Stage4BError) as caught:
        orchestrator.inspect("not-an-id")
    assert caught.value.code is Stage4BErrorCode.INVALID_RECORD_ID


def test_fetch_delegates_to_retrieve_validate_and_commit():
    repository = FakeCacheRepository(generation=4)
    provider = FakeProvider(candidate="candidate-pair")
    orchestrator = _orchestrator(repository, provider)
    operation = RetrievalOperation()

    result = orchestrator.fetch("1pcr", operation)

    assert result == "committed-snapshot"
    assert provider.calls[0][0] == "1pcr"
    assert repository.commits == [("candidate-pair", 4)]


def test_fetch_propagates_cancellation_before_commit():
    repository = FakeCacheRepository()
    provider = FakeProvider()
    orchestrator = _orchestrator(repository, provider)
    operation = RetrievalOperation()
    operation.request_cancel()

    with pytest.raises(Stage4BError) as caught:
        orchestrator.fetch("1pcr", operation)
    assert caught.value.code is Stage4BErrorCode.RETRIEVAL_CANCELLED
    assert provider.calls == []


def test_use_cached_pair_reads_active_snapshot():
    snapshot = SimpleNamespace(canonical_record_id="1pcr")
    repository = FakeCacheRepository(active=snapshot)
    orchestrator = _orchestrator(repository)

    result = orchestrator.use_cached_pair("1PCR")

    assert result is snapshot
    assert repository.read_active_calls == ["1pcr"]


def test_use_cached_pair_propagates_cache_miss():
    repository = FakeCacheRepository(active=_error(Stage4BErrorCode.CACHE_MISS))
    orchestrator = _orchestrator(repository)

    with pytest.raises(Stage4BError) as caught:
        orchestrator.use_cached_pair("1pcr")
    assert caught.value.code is Stage4BErrorCode.CACHE_MISS


def test_clear_returns_tombstone_generation():
    repository = FakeCacheRepository(clear_result=9)
    orchestrator = _orchestrator(repository)

    result = orchestrator.clear("1PCR")

    assert result == ClearResult("1pcr", 9)
    assert repository.cleared == ["1pcr"]


def test_clear_propagates_failure():
    repository = FakeCacheRepository(clear_result=_error(Stage4BErrorCode.CACHE_CLEAR_FAILED))
    orchestrator = _orchestrator(repository)

    with pytest.raises(Stage4BError) as caught:
        orchestrator.clear("1pcr")
    assert caught.value.code is Stage4BErrorCode.CACHE_CLEAR_FAILED


def test_factories_are_invoked_fresh_for_every_call():
    counts = {"repo": 0, "provider": 0}

    def repo_factory():
        counts["repo"] += 1
        return FakeCacheRepository(inspection=SimpleNamespace(generation=0, records={}))

    def provider_factory():
        counts["provider"] += 1
        return FakeProvider()

    orchestrator = PdbtmWorkerOrchestrator(
        cache_repository_factory=repo_factory, provider_factory=provider_factory
    )
    orchestrator.inspect("1pcr")
    orchestrator.inspect("1pcr")

    assert counts["repo"] == 2
    assert counts["provider"] == 0


def test_failure_from_error_copies_stable_metadata():
    error = Stage4BError(
        code=Stage4BErrorCode.NETWORK_TIMEOUT,
        user_message="PDBTM did not respond within the allowed time.",
        retryable=True,
        existing_cache_usable=True,
    )

    failure = failure_from_error(error)

    assert failure == WorkerFailure(
        code="NETWORK_TIMEOUT",
        message="PDBTM did not respond within the allowed time.",
        retryable=True,
        existing_cache_usable=True,
    )
