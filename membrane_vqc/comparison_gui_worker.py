"""Lazy Qt glue for the Qt-free orientation-comparison orchestrator."""

from __future__ import annotations

from .comparison_worker import ComparisonWorkerOrchestrator


def make_comparison_worker_class(QtCore):
    """Build a QObject class bound to PyMOL's lazily supplied Qt binding."""

    class ComparisonAsyncWorker(QtCore.QObject):
        compare_finished = QtCore.Signal(str, object)
        request_compare = QtCore.Signal(str, object, object)

        def __init__(self, orchestrator: ComparisonWorkerOrchestrator | None = None) -> None:
            super().__init__()
            self._orchestrator = orchestrator or ComparisonWorkerOrchestrator()
            self.request_compare.connect(self._run_compare, QtCore.Qt.QueuedConnection)

        def _run_compare(self, request_id, request, operation) -> None:
            result = self._orchestrator.compare(request, operation)
            self.compare_finished.emit(request_id, result)

    return ComparisonAsyncWorker
