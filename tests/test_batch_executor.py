from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from membrane_vqc.batch_contracts import load_plan
from membrane_vqc.batch_executor import PymolBatchExecutor
from membrane_vqc.batch_runner import BatchExecutionFailed, BatchInputRejected
from membrane_vqc.orientation_sources import StructureContext
from scripts.materialize_stage5a_example import materialize


ROOT = Path(__file__).resolve().parents[1]


class FakeCmd:
    def __init__(self):
        self.objects = {
            "user_object": [
                SimpleNamespace(
                    model="user_object",
                    chain="A",
                    resi="1",
                    resn="ALA",
                    name="CA",
                    alt="",
                    segi="",
                    symbol="C",
                    coord=(1.0, 2.0, 3.0),
                )
            ]
        }
        self.events = []

    def get_object_list(self, selection):
        name = selection.strip("()")
        return [name] if name in self.objects else []

    def get_model(self, name, state=1):
        self.events.append(("get_model", name, state))
        return SimpleNamespace(atom=self.objects[name])

    def get_names(self, kind):
        return sorted(self.objects) if kind == "objects" else []

    def load(self, path, name):
        self.events.append(("load", name))
        self.objects[name] = [
            SimpleNamespace(
                model=name,
                chain="A",
                resi="1",
                resn="ALA",
                name="CA",
                alt="",
                segi="",
                symbol="C",
                coord=(1.0, 2.0, 3.0),
            )
        ]

    def delete(self, name):
        self.events.append(("delete", name))
        self.objects.pop(name, None)

    def get_version(self):
        return ("test",)


def _report():
    return json.loads((ROOT / "reports" / "bad_core_lys_mvqc.json").read_text(encoding="utf-8"))


def _plan(input_spec):
    return {
        "contract": "mvqc-batch-plan-1.0",
        "jobs": [
            {
                "id": "one",
                "input": input_spec,
                "analysis": {"mode": "legacy_global_z", "zmin": -15, "zmax": 15},
                "output": {"write_csv": False},
            }
        ],
        "execution": {"failure_policy": "continue_on_error", "overwrite": "refuse"},
    }


def test_loaded_user_object_is_preserved_and_calls_are_sequential(tmp_path, monkeypatch):
    cmd = FakeCmd()
    active = False
    calls = []

    def run_check(**kwargs):
        nonlocal active
        assert active is False
        active = True
        calls.append(kwargs["selection"])
        active = False
        return _report()

    monkeypatch.setattr("membrane_vqc.batch_executor.qc.run_check", run_check)
    plan = _plan({"kind": "pymol", "selection": "user_object"})
    executed = PymolBatchExecutor(plan, tmp_path, cmd)(plan["jobs"][0])
    assert executed.coordinate_preserved is True
    assert calls == ["user_object"]
    assert "user_object" in cmd.objects


def test_temporary_file_object_is_deterministic_and_removed(tmp_path, monkeypatch):
    coordinate = tmp_path / "input.pdb"
    coordinate.write_text("ATOM fixture\n", encoding="ascii")
    cmd = FakeCmd()
    monkeypatch.setattr("membrane_vqc.batch_executor.qc.run_check", lambda **kwargs: _report())
    plan = _plan({"kind": "file", "path": "input.pdb"})
    executed = PymolBatchExecutor(plan, tmp_path, cmd)(plan["jobs"][0])
    assert executed.coordinate_preserved is True
    loaded = [event[1] for event in cmd.events if event[0] == "load"]
    assert len(loaded) == 1 and loaded[0].startswith("mvqc_batch_one_")
    assert loaded[0] not in cmd.objects
    assert "user_object" in cmd.objects


def test_file_load_uses_preflighted_private_copy(tmp_path, monkeypatch):
    coordinate = tmp_path / "input.pdb"
    coordinate.write_bytes(b"ORIGINAL\n")

    class CapturingCmd(FakeCmd):
        def load(self, path, name):
            self.loaded_bytes = Path(path).read_bytes()
            self.loaded_path = Path(path)
            super().load(path, name)

    cmd = CapturingCmd()
    monkeypatch.setattr("membrane_vqc.batch_executor.qc.run_check", lambda **kwargs: _report())
    plan = _plan({"kind": "file", "path": "input.pdb"})
    executor = PymolBatchExecutor(plan, tmp_path, cmd)
    coordinate.write_bytes(b"REPLACED\n")
    executor(plan["jobs"][0])
    assert cmd.loaded_bytes == b"ORIGINAL\n"
    assert cmd.loaded_path != coordinate
    assert not cmd.loaded_path.exists()


def test_plan_validation_and_import_are_network_free(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr("socket.socket", forbidden)
    plan, _ = load_plan(ROOT / "data" / "synthetic" / "stage5a_batch_plan.json")
    assert len(plan["jobs"]) == 5


def test_partial_load_failure_still_removes_exact_temporary_object(tmp_path):
    coordinate = tmp_path / "input.pdb"
    coordinate.write_text("ATOM fixture\n", encoding="ascii")

    class PartialLoadCmd(FakeCmd):
        def load(self, path, name):
            super().load(path, name)
            raise RuntimeError("partial load")

    cmd = PartialLoadCmd()
    plan = _plan({"kind": "file", "path": "input.pdb"})
    with pytest.raises(BatchInputRejected, match="INPUT_LOAD_FAILED"):
        PymolBatchExecutor(plan, tmp_path, cmd)(plan["jobs"][0])
    assert not any(name.startswith("mvqc_batch_") for name in cmd.objects)
    assert "user_object" in cmd.objects


def test_preflight_rejection_clears_stale_plugin_state_and_last_report(tmp_path):
    from membrane_vqc import qc

    cmd = FakeCmd()
    cmd.objects["mvqc_slab_lower"] = list(cmd.objects["user_object"])
    plan = _plan({"kind": "file", "path": "missing.pdb"})
    previous = qc.LAST_REPORT
    qc.LAST_REPORT = {"stale": True}
    try:
        with pytest.raises(BatchInputRejected):
            PymolBatchExecutor(plan, tmp_path, cmd)(plan["jobs"][0])
        assert "mvqc_slab_lower" not in cmd.objects
        assert "user_object" in cmd.objects
        assert qc.LAST_REPORT is None
    finally:
        qc.LAST_REPORT = previous


def test_cleanup_failure_cannot_return_success(tmp_path, monkeypatch):
    coordinate = tmp_path / "input.pdb"
    coordinate.write_text("ATOM fixture\n", encoding="ascii")

    class DeleteFailureCmd(FakeCmd):
        def delete(self, name):
            if name.startswith("mvqc_batch_"):
                raise RuntimeError("delete failed")
            super().delete(name)

    cmd = DeleteFailureCmd()
    monkeypatch.setattr("membrane_vqc.batch_executor.qc.run_check", lambda **kwargs: _report())
    plan = _plan({"kind": "file", "path": "input.pdb"})
    with pytest.raises(BatchExecutionFailed, match="CLEANUP_FAILED"):
        PymolBatchExecutor(plan, tmp_path, cmd)(plan["jobs"][0])


def test_coordinate_fingerprint_covers_every_object_state(tmp_path, monkeypatch):
    cmd = FakeCmd()
    cmd.states = {
        "user_object": [list(cmd.objects["user_object"]), list(cmd.objects["user_object"])]
    }

    def count_states(name):
        return len(cmd.states[name])

    def get_model(name, state=1):
        return SimpleNamespace(atom=cmd.states[name][state - 1])

    cmd.count_states = count_states
    cmd.get_model = get_model

    def mutate_second_state(**kwargs):
        cmd.states["user_object"][1][0].coord = (9.0, 9.0, 9.0)
        return _report()

    monkeypatch.setattr("membrane_vqc.batch_executor.qc.run_check", mutate_second_state)
    plan = _plan({"kind": "pymol", "selection": "user_object"})
    executed = PymolBatchExecutor(plan, tmp_path, cmd)(plan["jobs"][0])
    assert executed.coordinate_preserved is False


def test_local_pdbtm_plan_record_id_is_enforced(tmp_path, monkeypatch):
    (tmp_path / "pair.json").write_text("{}", encoding="utf-8")
    (tmp_path / "pair.pdb").write_text("ATOM fixture\n", encoding="ascii")
    plan = _plan({"kind": "pymol", "selection": "user_object"})
    plan["jobs"][0]["analysis"] = {
        "mode": "pdbtm_local",
        "record_id": "test",
        "pdbtm_json": "pair.json",
        "transformed_pdb": "pair.pdb",
    }
    imported = SimpleNamespace(
        membrane=object(),
        evidence=SimpleNamespace(source=SimpleNamespace(record_id="xxxx")),
    )
    monkeypatch.setattr(
        "membrane_vqc.batch_executor.resolve_pdbtm_from_payloads", lambda **kwargs: imported
    )
    with pytest.raises(BatchInputRejected, match="RECORD_ID_MISMATCH"):
        PymolBatchExecutor(plan, tmp_path, FakeCmd())(plan["jobs"][0])


def test_batch_comparison_uses_preflighted_opm_bytes(tmp_path, monkeypatch):
    for name, body in {
        "pair.json": b"{}",
        "pair.pdb": b"ATOM fixture\n",
        "opm.pdb": b"original OPM bytes",
    }.items():
        (tmp_path / name).write_bytes(body)
    plan = _plan({"kind": "pymol", "selection": "user_object"})
    plan["jobs"][0]["analysis"] = {
        "mode": "pdbtm_opm_comparison",
        "pdbtm": {
            "kind": "local",
            "record_id": "test",
            "pdbtm_json": "pair.json",
            "transformed_pdb": "pair.pdb",
        },
        "opm_pdb": "opm.pdb",
    }
    plan["jobs"][0]["output"]["write_csv"] = False
    executor = PymolBatchExecutor(plan, tmp_path, FakeCmd())
    (tmp_path / "opm.pdb").write_bytes(b"replacement")
    captured = []

    class Worker:
        def compare(self, request, operation=None):
            captured.append(request.opm_payload)
            return SimpleNamespace(code="STOP")

    monkeypatch.setattr(
        "membrane_vqc.batch_executor.capture_comparison_snapshot",
        lambda *args, **kwargs: SimpleNamespace(
            structure_context=StructureContext(b"ATOM\n", "test", 1)
        ),
    )
    monkeypatch.setattr("membrane_vqc.batch_executor.ComparisonWorkerOrchestrator", Worker)
    monkeypatch.setattr("membrane_vqc.batch_executor.ComparisonWorkerFailure", SimpleNamespace)
    with pytest.raises(BatchExecutionFailed):
        executor(plan["jobs"][0])
    assert captured == [b"original OPM bytes"]


def test_actual_five_mode_executor_paths_open_no_socket(tmp_path, monkeypatch):
    example = tmp_path / "example"
    plan_path = materialize(example)
    plan, _ = load_plan(plan_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr("socket.socket", forbidden)
    monkeypatch.setattr("socket.create_connection", forbidden)
    reports = {
        "1.1": _report(),
        "1.3": json.loads((ROOT / "reports" / "pdbtm_synthetic_mvqc.json").read_text("utf-8")),
        "1.4": json.loads(
            (ROOT / "reports" / "pdbtm_acquisition_v050_mvqc.json").read_text("utf-8")
        ),
        "1.5": json.loads(
            (ROOT / "reports" / "source_comparison_synthetic_mvqc.json").read_text("utf-8")
        ),
    }
    monkeypatch.setattr("membrane_vqc.batch_executor.qc.run_check", lambda **kwargs: reports["1.1"])

    def run_with_membrane(**kwargs):
        if kwargs.get("pdbtm_acquisition") is not None:
            return reports["1.4"]
        if kwargs.get("orientation_evidence") is not None:
            return reports["1.3"]
        return reports["1.1"]

    monkeypatch.setattr("membrane_vqc.batch_executor.qc.run_check_with_membrane", run_with_membrane)
    monkeypatch.setattr(
        "membrane_vqc.batch_executor.resolve_pdbtm_from_payloads",
        lambda **kwargs: SimpleNamespace(
            membrane=object(),
            evidence=SimpleNamespace(
                source=SimpleNamespace(
                    record_id=(
                        "1tes" if b'"pdb_id":"1tes"' in kwargs["pdbtm_json_payload"] else "test"
                    )
                )
            ),
        ),
    )
    monkeypatch.setattr(
        "membrane_vqc.batch_executor.capture_comparison_snapshot",
        lambda *args, **kwargs: SimpleNamespace(
            structure_context=StructureContext(b"ATOM\n", "test", 1)
        ),
    )
    monkeypatch.setattr(
        "membrane_vqc.batch_executor.comparison_snapshot_is_current", lambda *args, **kwargs: True
    )
    monkeypatch.setattr(
        "membrane_vqc.batch_executor.build_batch_comparison_report",
        lambda *args, **kwargs: reports["1.5"],
    )

    class Worker:
        def compare(self, request, operation=None):
            return object()

    monkeypatch.setattr("membrane_vqc.batch_executor.ComparisonWorkerOrchestrator", Worker)
    executor = PymolBatchExecutor(plan, example, FakeCmd())
    schemas = [executor(job).report["schema_version"] for job in plan["jobs"]]
    assert schemas == ["1.1", "1.1", "1.3", "1.4", "1.5"]
