"""Lazy Qt/QThread glue between ``MembraneVQCDialog`` and ``PdbtmWorkerOrchestrator``.

Qt is never imported at module import time here -- only inside
:func:`make_worker_class`, which the dialog calls lazily (mirroring
``gui.show_dialog``'s existing ``from pymol.Qt import ...`` pattern). This
keeps the module importable without PyQt5/PySide installed, which is required
for it to be exercised by ordinary ``pytest`` collection.

The produced ``QObject`` subclass never imports ``pymol``, never calls a
``cmd`` method, never reads or writes a widget, and never tests applicability
against a live PyMOL object: it only calls into :mod:`membrane_vqc.pdbtm_worker`
and emits Qt signals carrying plain data (or a :class:`WorkerFailure`) back to
whichever thread is connected -- ordinarily the main/GUI thread via a queued
connection because the worker instance has been moved to a separate
``QThread``.

Every ``connect()`` call in this module passes ``QtCore.Qt.QueuedConnection``
explicitly rather than relying on ``Qt.AutoConnection``'s cross-thread
detection: empirically, against the bundled Incentive PyMOL PyQt5 build,
``Qt.AutoConnection`` did not reliably resolve to a queued connection for
these self-connected-signal / plain-Python-slot patterns, and ``emit()``
blocked the calling thread for the slot's full duration instead of posting
and returning immediately -- silently defeating the entire point of moving
work off the GUI thread. This was caught only by an actual headless
``QThread`` smoke run (see ``docs/stage4b4_exact_acceptance.md``), not by
static review or the synchronous fake-Qt unit tests, which cannot observe
connection-type semantics at all. Being explicit here removes the ambiguity
regardless of binding/version quirks.

Cancellation is deliberately NOT delivered as a queued signal into the worker
thread: ``_run_fetch`` blocks that thread's event loop for the entire fetch
(it is a single synchronous call into the Qt-free orchestrator), so a
cross-thread signal aimed at that thread would simply queue up behind the
blocking call and only be processed once the fetch has already finished --
useless for actually interrupting it. Instead, ``fetch_started`` hands the
GUI a direct reference to the shared, thread-safe ``RetrievalOperation`` the
moment a fetch begins; the GUI calls ``operation.request_cancel()`` on it
directly (a plain, lock-guarded Python method call, not a Qt dispatch), which
the already-blocked fetch call observes at its next internal cooperative
checkpoint regardless of the worker thread's event-loop state.
"""

from __future__ import annotations

from .pdbtm_errors import Stage4BError
from .pdbtm_retrieval import RetrievalOperation
from .pdbtm_worker import PdbtmWorkerOrchestrator, failure_from_error


def make_worker_class(QtCore):
    """Build one ``QObject`` subclass bound to the caller's Qt binding.

    Called once per dialog (or once per Qt binding in tests) so the class
    body's ``QtCore.Signal`` references bind to a real or fake Qt module
    supplied by the caller -- this module itself never imports Qt.
    """

    class PdbtmAsyncWorker(QtCore.QObject):
        """Runs one request at a time; safe to move to its own ``QThread``.

        Callers (the GUI, on whatever thread it lives on) trigger work by
        emitting the ``request_*`` signals rather than calling the ``_run_*``
        methods directly: a direct Python call always executes on the
        caller's thread, but a signal connected with Qt's default ("Auto")
        connection type is automatically queued to the *receiver's* thread
        affinity -- which is this worker's own ``QThread`` once
        ``moveToThread`` has been called. The ``_run_*`` slots are connected
        to their matching ``request_*`` signal once, in ``__init__``.
        """

        inspect_finished = QtCore.Signal(str, object)
        fetch_finished = QtCore.Signal(str, object)
        use_cached_finished = QtCore.Signal(str, object)
        clear_finished = QtCore.Signal(str, object)
        fetch_started = QtCore.Signal(str, object)

        request_inspect = QtCore.Signal(str, str)
        request_fetch = QtCore.Signal(str, str)
        request_use_cached = QtCore.Signal(str, str)
        request_clear = QtCore.Signal(str, str)

        def __init__(self, orchestrator: PdbtmWorkerOrchestrator | None = None) -> None:
            super().__init__()
            self._orchestrator = orchestrator or PdbtmWorkerOrchestrator()
            queued = QtCore.Qt.QueuedConnection
            self.request_inspect.connect(self._run_inspect, queued)
            self.request_fetch.connect(self._run_fetch, queued)
            self.request_use_cached.connect(self._run_use_cached, queued)
            self.request_clear.connect(self._run_clear, queued)

        def _run_inspect(self, request_id: str, record_id: str) -> None:
            try:
                result = self._orchestrator.inspect(record_id)
            except Stage4BError as error:
                self.inspect_finished.emit(request_id, failure_from_error(error))
                return
            self.inspect_finished.emit(request_id, result)

        def _run_fetch(self, request_id: str, record_id: str) -> None:
            operation = RetrievalOperation()
            self.fetch_started.emit(request_id, operation)
            try:
                result = self._orchestrator.fetch(record_id, operation)
            except Stage4BError as error:
                self.fetch_finished.emit(request_id, failure_from_error(error))
                return
            self.fetch_finished.emit(request_id, result)

        def _run_use_cached(self, request_id: str, record_id: str) -> None:
            try:
                result = self._orchestrator.use_cached_pair(record_id)
            except Stage4BError as error:
                self.use_cached_finished.emit(request_id, failure_from_error(error))
                return
            self.use_cached_finished.emit(request_id, result)

        def _run_clear(self, request_id: str, record_id: str) -> None:
            try:
                result = self._orchestrator.clear(record_id)
            except Stage4BError as error:
                self.clear_finished.emit(request_id, failure_from_error(error))
                return
            self.clear_finished.emit(request_id, result)

    return PdbtmAsyncWorker
