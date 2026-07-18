from dataclasses import FrozenInstanceError
import math

import pytest

from membrane_vqc.errors import OrientationError
from membrane_vqc.orientation_sources import (
    ImportMessage,
    OrientationImportResult,
    PayloadDigest,
    PlanarGeometryEvidence,
    StructureContext,
)


def test_domain_values_are_frozen_and_json_safe():
    digest = PayloadDigest("json", "a" * 64, 12)
    message = ImportMessage("CODE", "Readable message.")
    result = OrientationImportResult("partial", messages=(message,))

    with pytest.raises(FrozenInstanceError):
        digest.byte_size = 13
    assert digest.as_dict()["sha256"] == "a" * 64
    assert result.as_dict()["messages"] == [{"code": "CODE", "message": "Readable message."}]


def test_non_imported_result_cannot_carry_membrane_and_imported_requires_evidence():
    with pytest.raises(OrientationError, match="requires evidence"):
        OrientationImportResult("imported")


def test_structure_context_requires_explicit_positive_model_and_bytes():
    with pytest.raises(OrientationError, match="positive integer"):
        StructureContext(b"ATOM", "x", 0)
    with pytest.raises(OrientationError, match="must be bytes"):
        StructureContext("ATOM", "x", 1)


def test_payload_digest_rejects_invalid_hash_and_finite_contract_is_enforced():
    with pytest.raises(OrientationError, match="64 lowercase"):
        PayloadDigest("json", "not-a-hash", 1)
    assert not math.isnan(float(PayloadDigest("json", "0" * 64, 1).byte_size))


def test_payload_digest_never_trusts_caller_retrieval_verification():
    digest = PayloadDigest("json", "0" * 64, 1, retrieval_verified=True)

    assert digest.retrieval_verified is False


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"normal": (0.0, 0.0, 0.0)}, "non-zero"),
        ({"normal": (0.0, 0.0, 2.0)}, "unit vector"),
        ({"interface_width": -1.0}, "non-negative"),
    ],
)
def test_planar_geometry_evidence_enforces_unit_normal_and_width(kwargs, message):
    values = {
        "center": (0.0, 0.0, 0.0),
        "normal": (0.0, 0.0, 1.0),
        "lower_offset": -1.0,
        "upper_offset": 1.0,
        "interface_width": None,
        "frame": "source",
    }
    values.update(kwargs)

    with pytest.raises(OrientationError, match=message):
        PlanarGeometryEvidence(**values)
