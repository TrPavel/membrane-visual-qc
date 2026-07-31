from pathlib import Path

from membrane_vqc.batch_contracts import load_plan
from membrane_vqc.pdbtm_cache import CacheRepository
from scripts.materialize_stage5a_example import SNAPSHOT_ID, materialize


def test_materialized_five_mode_example_has_exact_synthetic_snapshot(tmp_path):
    plan_path = materialize(tmp_path / "example")
    plan, _ = load_plan(plan_path)
    cached = plan["jobs"][3]["analysis"]
    assert cached == {
        "mode": "pdbtm_cache",
        "record_id": "1tes",
        "snapshot_id": SNAPSHOT_ID,
    }
    snapshot = CacheRepository(plan_path.parent / plan["cache_root"]).read_snapshot(
        "1tes", SNAPSHOT_ID
    )
    assert snapshot.snapshot_id == SNAPSHOT_ID
    assert [job["analysis"]["mode"] for job in plan["jobs"]] == [
        "legacy_global_z",
        "planar_orientation",
        "pdbtm_local",
        "pdbtm_cache",
        "pdbtm_opm_comparison",
    ]


def test_materializer_accepts_documented_relative_destination(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    plan_path = materialize(Path("example"))
    assert plan_path.is_absolute()
    assert plan_path.is_file()
