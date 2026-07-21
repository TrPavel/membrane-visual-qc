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

        request_inspect = QtCore.Signal(str, str)
        request_fetch = QtCore.Signal(str, str)
        request_use_cached = QtCore.Signal(str, str)
        request_clear = QtCore.Signal(str, str)
        request_cancel = QtCore.Signal(str)

        def __init__(self, orchestrator: PdbtmWorkerOrchestrator | None = None) -> None:
            super().__init__()
            self._orchestrator = orchestrator or PdbtmWorkerOrchestrator()
            self._operations: dict[str, RetrievalOperation] = {}
            self.request_inspect.connect(self._run_inspect)
            self.request_fetch.connect(self._run_fetch)
            self.request_use_cached.connect(self._run_use_cached)
            self.request_clear.connect(self._run_clear)
            self.request_cancel.connect(self._run_cancel)

        def _run_cancel(self, request_id: str) -> None:
            """Cooperatively request cancellation of an in-flight fetch, if any."""

            operation = self._operations.get(request_id)
            if operation is not None:
                operation.request_cancel()

        def _run_inspect(self, request_id: str, record_id: str) -> None:
            try:
                result = self._orchestrator.inspect(record_id)
            except Stage4BError as error:
                self.inspect_finished.emit(request_id, failure_from_error(error))
                return
            self.inspect_finished.emit(request_id, result)

        def _run_fetch(self, request_id: str, record_id: str) -> None:
            operation = RetrievalOperation()
            self._operations[request_id] = operation
            try:
                result = self._orchestrator.fetch(record_id, operation)
            except Stage4BError as error:
                self.fetch_finished.emit(request_id, failure_from_error(error))
                return
            finally:
                self._operations.pop(request_id, None)
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
