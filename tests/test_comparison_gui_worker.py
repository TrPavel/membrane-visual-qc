from membrane_vqc.comparison_gui_worker import make_comparison_worker_class


class _SignalInstance:
    def __init__(self):
        self.slots = []

    def connect(self, slot, connection_type=None):
        self.slots.append((slot, connection_type))

    def emit(self, *args):
        for slot, _ in self.slots:
            slot(*args)


class _SignalDescriptor:
    def __init__(self, *types):
        self.name = None

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        key = f"__signal_{self.name}"
        if key not in instance.__dict__:
            instance.__dict__[key] = _SignalInstance()
        return instance.__dict__[key]


class FakeQtCore:
    class QObject:
        pass

    class Qt:
        QueuedConnection = "queued"

    Signal = _SignalDescriptor


class Orchestrator:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def compare(self, request, operation):
        self.calls.append((request, operation))
        return self.result


def test_request_signal_routes_to_orchestrator_and_emits_request_id():
    orchestrator = Orchestrator("completed")
    worker = make_comparison_worker_class(FakeQtCore)(orchestrator)
    delivered = []
    worker.compare_finished.connect(
        lambda request_id, result: delivered.append((request_id, result))
    )

    worker.request_compare.emit("session:1", "request", "operation")

    assert orchestrator.calls == [("request", "operation")]
    assert delivered == [("session:1", "completed")]


def test_worker_request_uses_explicit_queued_connection():
    worker = make_comparison_worker_class(FakeQtCore)(Orchestrator(None))

    assert worker.request_compare.slots[0][1] == FakeQtCore.Qt.QueuedConnection
