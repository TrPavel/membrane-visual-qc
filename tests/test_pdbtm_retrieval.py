from __future__ import annotations

import threading

import pytest

from membrane_vqc.pdbtm_errors import Stage4BError, Stage4BErrorCode
from membrane_vqc.pdbtm_retrieval import (
    CommitState,
    DeliveryDisposition,
    InternalOutcome,
    RetrievalHooks,
    RetrievalOperation,
    retrieve_validate_and_commit,
)


def _error(code=Stage4BErrorCode.CACHE_WRITE_FAILED):
    return Stage4BError(
        code=code,
        user_message="safe message",
        retryable=False,
        existing_cache_usable=True,
    )


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


class FakeRepository:
    def __init__(self, *, generation=3, result="snapshot", error=None):
        self.generation = generation
        self.result = result
        self.error = error
        self.captured = []
        self.commits = []

    def capture_record_generation(self, record_id):
        self.captured.append(record_id)
        return self.generation

    def commit_validated_pair(self, candidate, *, expected_record_generation):
        self.commits.append((candidate, expected_record_generation))
        if self.error:
            raise self.error
        return self.result


def test_successful_operation_commits_canonical_record_and_exposes_result():
    operation = RetrievalOperation()
    provider = FakeProvider()
    repository = FakeRepository()

    result = retrieve_validate_and_commit(
        "1AbC", provider=provider, repository=repository, operation=operation
    )

    assert result == "snapshot"
    assert repository.captured == ["1abc"]
    assert provider.calls[0][0] == "1abc"
    assert repository.commits == [("candidate", 3)]
    assert operation.commit_state is CommitState.COMMITTED
    assert operation.result == "snapshot"
    assert operation.snapshot().internal_outcome is None


def test_pre_network_cancellation_prevents_fetch_and_publication():
    operation = RetrievalOperation()
    assert operation.request_cancel()
    provider = FakeProvider()
    repository = FakeRepository()

    with pytest.raises(Stage4BError) as caught:
        retrieve_validate_and_commit(
            "1abc", provider=provider, repository=repository, operation=operation
        )
    assert caught.value.code is Stage4BErrorCode.RETRIEVAL_CANCELLED
    assert provider.calls == []
    assert repository.commits == []
    assert operation.commit_state is CommitState.CANCELLED


def test_expected_provider_failure_is_failed_pre_commit():
    error = _error(Stage4BErrorCode.PAIR_VALIDATION_FAILED)
    operation = RetrievalOperation()
    with pytest.raises(Stage4BError) as caught:
        retrieve_validate_and_commit(
            "1abc",
            provider=FakeProvider(error=error),
            repository=FakeRepository(),
            operation=operation,
        )
    assert caught.value is error
    assert operation.commit_state is CommitState.FAILED_PRE_COMMIT
    assert operation.error is error


def test_cancellation_wins_race_with_precommit_failure_recording():
    class RaceOperation(RetrievalOperation):
        def fail_pre_commit(self, error):
            self.request_cancel()
            return super().fail_pre_commit(error)

    operation = RaceOperation()
    with pytest.raises(Stage4BError) as caught:
        retrieve_validate_and_commit(
            "1abc",
            provider=FakeProvider(error=_error(Stage4BErrorCode.NETWORK_TIMEOUT)),
            repository=FakeRepository(),
            operation=operation,
        )
    assert caught.value.code is Stage4BErrorCode.RETRIEVAL_CANCELLED
    assert operation.commit_state is CommitState.CANCELLED


def test_repository_failure_after_authorization_is_commit_failed():
    error = _error(Stage4BErrorCode.CACHE_CONFLICT)
    operation = RetrievalOperation()
    with pytest.raises(Stage4BError) as caught:
        retrieve_validate_and_commit(
            "1abc",
            provider=FakeProvider(),
            repository=FakeRepository(error=error),
            operation=operation,
        )
    assert caught.value is error
    assert operation.commit_state is CommitState.COMMIT_FAILED
    assert operation.error is error


def test_cancellation_wins_before_commit_authorization_with_events():
    entered = threading.Event()
    release = threading.Event()
    operation = RetrievalOperation()
    repository = FakeRepository()
    caught = []

    def barrier():
        entered.set()
        assert release.wait(5)

    def worker():
        try:
            retrieve_validate_and_commit(
                "1abc",
                provider=FakeProvider(),
                repository=repository,
                operation=operation,
                hooks=RetrievalHooks(before_commit_authorization=barrier),
            )
        except Stage4BError as error:
            caught.append(error)

    thread = threading.Thread(target=worker)
    thread.start()
    assert entered.wait(5)
    assert operation.request_cancel()
    release.set()
    thread.join(5)

    assert not thread.is_alive()
    assert caught[0].code is Stage4BErrorCode.RETRIEVAL_CANCELLED
    assert operation.commit_state is CommitState.CANCELLED
    assert repository.commits == []


def test_commit_authorization_wins_then_cancellation_marks_delivery_stale():
    authorized = threading.Event()
    release = threading.Event()
    operation = RetrievalOperation()
    repository = FakeRepository()
    caught = []

    def barrier():
        authorized.set()
        assert release.wait(5)

    def worker():
        try:
            retrieve_validate_and_commit(
                "1abc",
                provider=FakeProvider(),
                repository=repository,
                operation=operation,
                hooks=RetrievalHooks(after_commit_authorization=barrier),
            )
        except BaseException as error:  # pragma: no cover - diagnostic only
            caught.append(error)

    thread = threading.Thread(target=worker)
    thread.start()
    assert authorized.wait(5)
    assert not operation.request_cancel()
    assert operation.commit_state is CommitState.COMMITTING
    release.set()
    thread.join(5)

    assert not thread.is_alive()
    assert caught == []
    assert repository.commits == [("candidate", 3)]
    snapshot = operation.snapshot()
    assert snapshot.commit_state is CommitState.COMMITTED
    assert snapshot.delivery_disposition is DeliveryDisposition.IGNORED_STALE
    assert snapshot.internal_outcome is InternalOutcome.COMMITTED_RESULT_IGNORED


def test_explicit_stale_delivery_after_commit_is_informational_not_exception():
    operation = RetrievalOperation()
    retrieve_validate_and_commit(
        "1abc", provider=FakeProvider(), repository=FakeRepository(), operation=operation
    )
    operation.invalidate_delivery()
    snapshot = operation.snapshot()
    assert snapshot.commit_state is CommitState.COMMITTED
    assert snapshot.internal_outcome is InternalOutcome.COMMITTED_RESULT_IGNORED


def test_failure_after_repository_publication_keeps_committed_state():
    operation = RetrievalOperation()

    def fail_after_publication():
        raise RuntimeError("delivery callback failed")

    with pytest.raises(RuntimeError, match="delivery callback failed"):
        retrieve_validate_and_commit(
            "1abc",
            provider=FakeProvider(),
            repository=FakeRepository(result="published"),
            operation=operation,
            hooks=RetrievalHooks(after_repository_commit=fail_after_publication),
        )
    assert operation.commit_state is CommitState.COMMITTED
    assert operation.result == "published"


def test_invalid_transition_is_not_silently_suppressed():
    operation = RetrievalOperation()
    operation.authorize_commit()
    with pytest.raises(RuntimeError, match="cannot authorize"):
        operation.authorize_commit()
