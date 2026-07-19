from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from membrane_vqc import commands, qc
from membrane_vqc.orientation_sources import (
    ImportMessage,
    OrientationImportResult,
    StructureContext,
)
from membrane_vqc.pdbtm_adapter import import_pdbtm_orientation
from membrane_vqc.pdbtm_pymol import (
    PdbtmCommandError,
    read_local_payload,
    resolve_pdbtm_from_pymol,
    structure_context_from_pymol,
)
from membrane_vqc.pymol_adapter import MVQC_NAMES, MVQC_SLAB_NAMES
from membrane_vqc.report import build_report, validate_stage4_report_semantics


ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "data" / "synthetic" / "pdbtm_api_v1_test.json"
TRANSFORMED_PATH = ROOT / "data" / "synthetic" / "pdbtm_transformed_test.pdb"
ORIGINAL_PATH = ROOT / "data" / "synthetic" / "pdbtm_original_test.pdb"


def _atoms_from_pdb(text):
    atoms = []
    for line in text.splitlines():
        if not line.startswith("ATOM  "):
            continue
        atoms.append(
            SimpleNamespace(
                chain=line[21:22].strip(),
                resi=line[22:27].strip(),
                resn=line[17:20].strip(),
                name=line[12:16].strip(),
                alt=line[16:17].strip(),
                q=float(line[54:60]),
                coord=(float(line[30:38]), float(line[38:46]), float(line[46:54])),
            )
        )
    return atoms


class SnapshotCmd:
    def __init__(self, pdb_path=TRANSFORMED_PATH, objects=("protein",), states=1):
        self.pdb_text = Path(pdb_path).read_text(encoding="ascii")
        self.objects = list(objects)
        self.states = states
        self.calls = []
        self.atoms = _atoms_from_pdb(self.pdb_text)

    def get_object_list(self, selection):
        self.calls.append(("get_object_list", selection))
        return self.objects

    def count_states(self, object_name):
        self.calls.append(("count_states", object_name))
        return self.states

    def get_model(self, selection, state=1):
        self.calls.append(("get_model", selection, state))
        return SimpleNamespace(atom=self.atoms)

    def get_pdbstr(self, selection, state=1):
        self.calls.append(("get_pdbstr", selection, state))
        return self.pdb_text


def _resolved(pdb_path=TRANSFORMED_PATH, assembly=None):
    return resolve_pdbtm_from_pymol(
        selection="protein and chain A",
        pdbtm_json_path=str(JSON_PATH),
        transformed_pdb_path=str(TRANSFORMED_PATH),
        biological_assembly=assembly,
        cmd_obj=SnapshotCmd(pdb_path),
    )


def test_structure_context_resolves_one_complete_object_for_subset():
    cmd = SnapshotCmd()

    context = structure_context_from_pymol("protein and resi 1", cmd_obj=cmd)

    assert context.pdb_payload == TRANSFORMED_PATH.read_bytes()
    assert context.structure_id is None
    assert context.model_id == 1
    assert context.coordinate_frame == "pymol_current_object"
    assert ("get_model", "protein", 1) in cmd.calls
    assert ("get_pdbstr", "protein", 1) in cmd.calls


@pytest.mark.parametrize("objects", [(), ("one", "two")])
def test_structure_context_rejects_zero_or_multiple_objects(objects):
    with pytest.raises(PdbtmCommandError, match="OBJECT_COUNT"):
        structure_context_from_pymol("all", cmd_obj=SnapshotCmd(objects=objects))


def test_structure_context_accepts_one_state_and_rejects_multiple_states():
    assert structure_context_from_pymol("all", cmd_obj=SnapshotCmd(states=1)).model_id == 1
    with pytest.raises(PdbtmCommandError, match="MULTI_STATE_UNSUPPORTED"):
        structure_context_from_pymol("all", cmd_obj=SnapshotCmd(states=2))


def test_structure_context_rejects_unsafe_current_chain_without_truncation():
    cmd = SnapshotCmd()
    cmd.atoms[0].chain = "AB"

    with pytest.raises(PdbtmCommandError, match="CHAIN_NAMESPACE_UNSAFE"):
        structure_context_from_pymol("all", cmd_obj=cmd)


@pytest.mark.parametrize(
    ("method", "value", "code"),
    [
        ("get_object_list", RuntimeError("bad selection"), "OBJECT_RESOLUTION_FAILED"),
        ("count_states", RuntimeError("bad state"), "STATE_COUNT_FAILED"),
        ("get_model", RuntimeError("bad model"), "SNAPSHOT_FAILED"),
        ("get_pdbstr", RuntimeError("bad snapshot"), "SNAPSHOT_FAILED"),
        ("get_pdbstr", b"not text", "SNAPSHOT_FAILED"),
    ],
)
def test_structure_context_translates_only_snapshot_boundary_failures(method, value, code):
    cmd = SnapshotCmd()

    def fail_or_return(*args, **kwargs):
        if isinstance(value, Exception):
            raise value
        return value

    setattr(cmd, method, fail_or_return)
    with pytest.raises(PdbtmCommandError, match=code):
        structure_context_from_pymol("all", cmd_obj=cmd)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("name", "TOOLONG", "LEGACY_PDB_UNSAFE"),
        ("resn", "\N{GREEK CAPITAL LETTER ALPHA}", "LEGACY_PDB_UNSAFE"),
        ("q", "unknown", "INVALID_OCCUPANCY"),
        ("q", float("nan"), "INVALID_OCCUPANCY"),
    ],
)
def test_structure_context_rejects_unserializable_atom_metadata(field, value, code):
    cmd = SnapshotCmd()
    setattr(cmd.atoms[0], field, value)

    with pytest.raises(PdbtmCommandError, match=code):
        structure_context_from_pymol("all", cmd_obj=cmd)


def test_structure_context_rejects_non_ascii_snapshot():
    cmd = SnapshotCmd()
    cmd.get_pdbstr = lambda *args, **kwargs: "ATOM \N{GREEK CAPITAL LETTER ALPHA}"

    with pytest.raises(PdbtmCommandError, match="LEGACY_PDB_UNSAFE"):
        structure_context_from_pymol("all", cmd_obj=cmd)


def test_local_payload_loader_requires_regular_bounded_local_file(tmp_path):
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"exact\x00bytes")
    assert read_local_payload(str(payload), role="test") == b"exact\x00bytes"

    with pytest.raises(PdbtmCommandError, match="LOCAL_PATH_REQUIRED"):
        read_local_payload("", role="test")
    with pytest.raises(PdbtmCommandError, match="LOCAL_URL_NOT_ALLOWED"):
        read_local_payload("https://example.test/payload", role="test")
    with pytest.raises(PdbtmCommandError, match="LOCAL_FILE_NOT_FOUND"):
        read_local_payload(str(tmp_path / "missing"), role="test")
    with pytest.raises(PdbtmCommandError, match="LOCAL_FILE_NOT_REGULAR"):
        read_local_payload(str(tmp_path), role="test")

    oversized = tmp_path / "oversized.bin"
    oversized.write_bytes(b"x" * (5 * 1024 * 1024 + 1))
    with pytest.raises(PdbtmCommandError, match="PAYLOAD_TOO_LARGE"):
        read_local_payload(str(oversized), role="test")


def test_local_payload_loader_translates_inspection_and_read_errors(tmp_path, monkeypatch):
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"payload")

    original_stat = Path.stat
    monkeypatch.setattr(
        Path,
        "stat",
        lambda self, *args, **kwargs: (
            (_ for _ in ()).throw(OSError("inspection denied"))
            if self == payload
            else original_stat(self, *args, **kwargs)
        ),
    )
    with pytest.raises(PdbtmCommandError, match="LOCAL_FILE_UNREADABLE"):
        read_local_payload(str(payload), role="test")

    monkeypatch.setattr(Path, "stat", original_stat)
    original_read = Path.read_bytes
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda self: (
            (_ for _ in ()).throw(OSError("read denied"))
            if self == payload
            else original_read(self)
        ),
    )
    with pytest.raises(PdbtmCommandError, match="LOCAL_FILE_UNREADABLE"):
        read_local_payload(str(payload), role="test")


def test_resolution_preserves_exact_payload_hashes_without_local_paths():
    result = _resolved()

    assert result.status == "imported"
    assert result.evidence.mapping.method == "identity"
    digests = {item.role: item for item in result.source.raw_payloads}
    assert digests["pdbtm_json"].sha256 == hashlib.sha256(JSON_PATH.read_bytes()).hexdigest()
    assert (
        digests["transformed_pdb"].sha256
        == hashlib.sha256(TRANSFORMED_PATH.read_bytes()).hexdigest()
    )
    assert all(item.source is None and item.retrieved_at is None for item in digests.values())
    assert all(item.retrieval_verified is False for item in digests.values())
    serialized = json.dumps(result.as_dict())
    assert str(JSON_PATH.resolve()) not in serialized
    assert str(TRANSFORMED_PATH.resolve()) not in serialized


def test_resolution_exercises_identity_and_inverse_paths():
    identity = _resolved(TRANSFORMED_PATH)
    inverse = _resolved(ORIGINAL_PATH)

    assert identity.evidence.mapping.method == "identity"
    assert inverse.evidence.mapping.method == "inverse_provider_transform"


def test_resolution_rejects_nonimported_adapter_status(monkeypatch):
    monkeypatch.setattr(
        "membrane_vqc.pdbtm_pymol.import_pdbtm_orientation",
        lambda *args, **kwargs: OrientationImportResult(
            "partial",
            messages=(ImportMessage("TRANSFORMED_COMPANION_REQUIRED", "Need companion."),),
        ),
    )

    with pytest.raises(PdbtmCommandError, match="TRANSFORMED_COMPANION_REQUIRED: Need companion"):
        _resolved()


def test_mvqc_check_pdbtm_builds_schema_1_3_without_local_provider_paths(monkeypatch):
    imported = _resolved()
    monkeypatch.setattr(commands, "clear_owned", lambda: None)
    monkeypatch.setattr(commands, "resolve_pdbtm_from_pymol", lambda **kwargs: imported)

    def fake_run(**kwargs):
        return build_report(
            selection=kwargs["selection"],
            zmin=kwargs["membrane"].lower_offset,
            zmax=kwargs["membrane"].upper_offset,
            ligand_selection=kwargs["ligand"],
            cutoff=kwargs["cutoff"],
            total_residues=1,
            core_residues=1,
            flagged_residues=[],
            ligand_neighbours=[],
            warnings=[],
            membrane=kwargs["membrane"],
            orientation_evidence=kwargs["orientation_evidence"],
        )

    monkeypatch.setattr(qc, "run_check_with_membrane", fake_run)

    report = commands.mvqc_check_pdbtm(
        selection="protein and chain A",
        pdbtm_json=str(JSON_PATH.resolve()),
        transformed_pdb=str(TRANSFORMED_PATH.resolve()),
    )

    assert report["schema_version"] == "1.3"
    assert report["orientation"]["evidence"] == imported.evidence.as_dict()
    validate_stage4_report_semantics(report)
    serialized = json.dumps(report)
    assert str(JSON_PATH.resolve()) not in serialized
    assert str(TRANSFORMED_PATH.resolve()) not in serialized


def _install_owned_state(monkeypatch, initial):
    names = set(initial)
    clears = []

    def clear_owned():
        clears.append(tuple(sorted(names & set(MVQC_NAMES))))
        names.difference_update(MVQC_NAMES)

    monkeypatch.setattr(commands, "clear_owned", clear_owned)
    return names, clears


def test_successful_qc_then_successful_pdbtm_slab_clears_all_prior_state(monkeypatch):
    imported = _resolved()
    rendered = []
    names, clears = _install_owned_state(monkeypatch, {"protein", *MVQC_NAMES})
    monkeypatch.setattr(commands, "resolve_pdbtm_from_pymol", lambda **kwargs: imported)
    monkeypatch.setattr(commands, "protein_atoms", lambda selection: [object()])

    def render(membrane, atoms, selection):
        rendered.append((membrane, atoms, selection))
        names.update(MVQC_SLAB_NAMES)

    monkeypatch.setattr(commands, "create_membrane_planes", render)
    qc.LAST_REPORT = {"stale": True}

    result = commands.mvqc_slab_pdbtm("protein", str(JSON_PATH), str(TRANSFORMED_PATH))

    assert result is imported
    assert rendered[0][0] is imported.membrane
    assert names == {"protein", *MVQC_SLAB_NAMES}
    assert clears and qc.LAST_REPORT is None


def test_successful_qc_then_failed_pdbtm_slab_clears_everything(monkeypatch):
    names, clears = _install_owned_state(monkeypatch, {"protein", *MVQC_NAMES})
    monkeypatch.setattr(
        commands,
        "resolve_pdbtm_from_pymol",
        lambda **kwargs: (_ for _ in ()).throw(PdbtmCommandError("PAIR_MISMATCH", "wrong pair")),
    )
    qc.LAST_REPORT = {"stale": True}

    with pytest.raises(PdbtmCommandError, match="PAIR_MISMATCH"):
        commands.mvqc_slab_pdbtm("protein", str(JSON_PATH), str(TRANSFORMED_PATH))

    assert names == {"protein"}
    assert len(clears) == 2
    assert qc.LAST_REPORT is None


def test_successful_pdbtm_slab_then_failed_slab_removes_previous_slab(monkeypatch):
    imported = _resolved()
    names, _ = _install_owned_state(monkeypatch, {"protein"})
    monkeypatch.setattr(commands, "protein_atoms", lambda selection: [object()])
    monkeypatch.setattr(
        commands,
        "create_membrane_planes",
        lambda membrane, atoms, selection: names.update(MVQC_SLAB_NAMES),
    )
    monkeypatch.setattr(commands, "resolve_pdbtm_from_pymol", lambda **kwargs: imported)
    commands.mvqc_slab_pdbtm("protein", str(JSON_PATH), str(TRANSFORMED_PATH))
    assert names == {"protein", *MVQC_SLAB_NAMES}

    monkeypatch.setattr(
        commands,
        "resolve_pdbtm_from_pymol",
        lambda **kwargs: (_ for _ in ()).throw(PdbtmCommandError("PAIR_MISMATCH", "wrong pair")),
    )
    with pytest.raises(PdbtmCommandError, match="PAIR_MISMATCH"):
        commands.mvqc_slab_pdbtm("protein", str(JSON_PATH), str(TRANSFORMED_PATH))

    assert names == {"protein"}
    assert qc.LAST_REPORT is None


def test_successful_pdbtm_slab_makes_stale_report_unexportable(monkeypatch, tmp_path):
    imported = _resolved()
    names, _ = _install_owned_state(monkeypatch, {"protein", *MVQC_NAMES})
    monkeypatch.setattr(commands, "resolve_pdbtm_from_pymol", lambda **kwargs: imported)
    monkeypatch.setattr(commands, "protein_atoms", lambda selection: [object()])
    monkeypatch.setattr(
        commands,
        "create_membrane_planes",
        lambda membrane, atoms, selection: names.update(MVQC_SLAB_NAMES),
    )
    qc.LAST_REPORT = {"stale": True}

    commands.mvqc_slab_pdbtm("protein", str(JSON_PATH), str(TRANSFORMED_PATH))

    with pytest.raises(RuntimeError, match="No QC report"):
        commands.mvqc_export(str(tmp_path / "stale.json"))
    assert not (tmp_path / "stale.json").exists()
    assert names == {"protein", *MVQC_SLAB_NAMES}


def test_pdbtm_command_failure_clears_state_and_report(monkeypatch):
    cleared = []
    monkeypatch.setattr(commands, "clear_owned", lambda: cleared.append("clear"))
    monkeypatch.setattr(
        commands,
        "resolve_pdbtm_from_pymol",
        lambda **kwargs: (_ for _ in ()).throw(PdbtmCommandError("PAIR_MISMATCH", "wrong pair")),
    )
    qc.LAST_REPORT = {"stale": True}

    with pytest.raises(PdbtmCommandError, match="PAIR_MISMATCH"):
        commands.mvqc_check_pdbtm("protein", str(JSON_PATH), str(TRANSFORMED_PATH))

    assert cleared == ["clear", "clear"]
    assert qc.LAST_REPORT is None


def test_register_commands_includes_pdbtm_workflow():
    registered = {}
    commands.register_commands(
        SimpleNamespace(extend=lambda name, fn: registered.setdefault(name, fn))
    )

    assert registered["mvqc_check_pdbtm"] is commands.mvqc_check_pdbtm
    assert registered["mvqc_slab_pdbtm"] is commands.mvqc_slab_pdbtm


def test_adapter_pair_fixture_matches_direct_core_contract():
    imported = import_pdbtm_orientation(
        JSON_PATH.read_bytes(),
        TRANSFORMED_PATH.read_bytes(),
        StructureContext(TRANSFORMED_PATH.read_bytes(), None, 1),
    )
    assert imported.status == "imported"
