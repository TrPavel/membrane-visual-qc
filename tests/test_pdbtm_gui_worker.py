"""Fake-Qt tests for the Stage 4B3 QObject/QThread glue layer.

These tests never import a real Qt binding: ``FakeQtCore`` below provides
just enough of the ``QObject``/``Signal`` surface (synchronous, single
threaded ``emit`` -> connected slots) to exercise request routing, failure
conversion, and per-request cancellation plumbing in
``membrane_vqc.pdbtm_gui_worker``. Genuine cross-thread/queued-connection
behaviour is exercised separately by the manual headless PyQt5 smoke, which
is outside the scope of ordinary CI.
"""

from __future__ import annotations

from membrane_vqc.pdbtm_errors import Stage4BError, Stage4BErrorCode
from membrane_vqc.pdbtm_gui_worker import make_worker_class
from membrane_vqc.pdbtm_worker import WorkerFailure


class _FakeSignalInstance:
    def __init__(self):
        self._slots = []

    def connect(self, slot):
        self._slots.append(slot)

    def emit(self, *args):
        for slot in list(self._slots):
            slot(*args)


class _FakeSignalDescriptor:
    def __init__(self, *_types):
        self._types = _types

    def __set_name__(self, owner, name):
        self._attr = f"_fake_signal_{name}"

    def __get__(self, instance, owner):
        if instance is None:
            return self
        if not hasattr(instance, self._attr):
            setattr(instance, self._attr, _FakeSignalInstance())
        return getattr(instance, self._attr)


class FakeQObject:
    def __init__(self):
        pass


class FakeQtCore:
    QObject = FakeQObject
    Signal = _FakeSignalDescriptor


class RecordingOrchestrator:
    def __init__(
        self,
        *,
        inspect_result=None,
        fetch_result=None,
        use_cached_result=None,
        clear_result=None,
        on_fetch=None,
    ):
        self.inspect_result = inspect_result
        self.fetch_result = fetch_result
        self.use_cached_result = use_cached_result
        self.clear_result = clear_result
        self.on_fetch = on_fetch
        self.calls = []

    def inspect(self, record_id):
        self.calls.append(("inspect", record_id))
        if isinstance(self.inspect_result, Exception):
            raise self.inspect_result
        return self.inspect_result

    def fetch(self, record_id, operation):
        self.calls.append(("fetch", record_id))
        if self.on_fetch is not None:
            self.on_fetch(operation)
        if operation.is_cancelled():
            raise Stage4BError(
                Stage4BErrorCode.RETRIEVAL_CANCELLED,
                user_message="PDBTM retrieval was cancelled.",
                retryable=True,
                existing_cache_usable=True,
            )
        if isinstance(self.fetch_result, Exception):
            raise self.fetch_result
        return self.fetch_result

    def use_cached_pair(self, record_id):
        self.calls.append(("use_cached_pair", record_id))
        if isinstance(self.use_cached_result, Exception):
            raise self.use_cached_result
        return self.use_cached_result

    def clear(self, record_id):
        self.calls.append(("clear", record_id))
        if isinstance(self.clear_result, Exception):
            raise self.clear_result
        return self.clear_result


def _worker(orchestrator):
    worker_class = make_worker_class(FakeQtCore)
    worker = worker_class(orchestrator)
    return worker


def test_request_inspect_emits_inspect_finished_with_result():
    orchestrator = RecordingOrchestrator(inspect_result="inspect-ok")
    worker = _worker(orchestrator)
    results = []
    worker.inspect_finished.connect(lambda rid, res: results.append((rid, res)))

    worker.request_inspect.emit("req-1", "1pcr")

    assert results == [("req-1", "inspect-ok")]
    assert orchestrator.calls == [("inspect", "1pcr")]


def test_request_inspect_failure_becomes_worker_failure():
    error = Stage4BError(
        Stage4BErrorCode.INVALID_RECORD_ID,
        user_message="Enter a four-character PDB ID such as 1pcr.",
        retryable=False,
        existing_cache_usable=True,
    )
    worker = _worker(RecordingOrchestrator(inspect_result=error))
    results = []
    worker.inspect_finished.connect(lambda rid, res: results.append((rid, res)))

    worker.request_inspect.emit("req-1", "bad")

    assert len(results) == 1
    request_id, failure = results[0]
    assert request_id == "req-1"
    assert isinstance(failure, WorkerFailure)
    assert failure.code == "INVALID_RECORD_ID"
    assert failure.message == "Enter a four-character PDB ID such as 1pcr."


def test_request_fetch_emits_fetch_finished_with_committed_snapshot():
    worker = _worker(RecordingOrchestrator(fetch_result="snapshot"))
    results = []
    worker.fetch_finished.connect(lambda rid, res: results.append((rid, res)))

    worker.request_fetch.emit("req-1", "1pcr")

    assert results == [("req-1", "snapshot")]


def test_request_use_cached_emits_use_cached_finished():
    worker = _worker(RecordingOrchestrator(use_cached_result="cached-snapshot"))
    results = []
    worker.use_cached_finished.connect(lambda rid, res: results.append((rid, res)))

    worker.request_use_cached.emit("req-1", "1pcr")

    assert results == [("req-1", "cached-snapshot")]


def test_request_use_cached_failure_becomes_worker_failure():
    error = Stage4BError(Stage4BErrorCode.CACHE_MISS)
    worker = _worker(RecordingOrchestrator(use_cached_result=error))
    results = []
    worker.use_cached_finished.connect(lambda rid, res: results.append((rid, res)))

    worker.request_use_cached.emit("req-1", "1pcr")

    assert isinstance(results[0][1], WorkerFailure)
    assert results[0][1].code == "CACHE_MISS"


def test_request_clear_emits_clear_finished():
    worker = _worker(RecordingOrchestrator(clear_result="cleared"))
    results = []
    worker.clear_finished.connect(lambda rid, res: results.append((rid, res)))

    worker.request_clear.emit("req-1", "1pcr")

    assert results == [("req-1", "cleared")]


def test_cancel_signal_cancels_the_in_flight_fetch_operation():
    cancelled_flags = []

    def on_fetch(operation):
        worker.request_cancel.emit("req-1")
        cancelled_flags.append(operation.is_cancelled())

    orchestrator = RecordingOrchestrator(on_fetch=on_fetch)
    worker = _worker(orchestrator)
    results = []
    worker.fetch_finished.connect(lambda rid, res: results.append((rid, res)))

    worker.request_fetch.emit("req-1", "1pcr")

    assert cancelled_flags == [True]
    assert isinstance(results[0][1], WorkerFailure)
    assert results[0][1].code == "RETRIEVAL_CANCELLED"


def test_cancel_signal_for_unknown_request_id_is_a_no_op():
    worker = _worker(RecordingOrchestrator(fetch_result="snapshot"))
    # No fetch is in flight yet; cancelling an unknown ID must not raise.
    worker.request_cancel.emit("never-requested")

    results = []
    worker.fetch_finished.connect(lambda rid, res: results.append((rid, res)))
    worker.request_fetch.emit("req-1", "1pcr")
    assert results == [("req-1", "snapshot")]


def test_operation_bookkeeping_is_cleared_after_each_fetch():
    worker = _worker(RecordingOrchestrator(fetch_result="snapshot"))
    worker.request_fetch.emit("req-1", "1pcr")
    assert worker._operations == {}
