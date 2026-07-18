from dataclasses import FrozenInstanceError
import math

import pytest

from membrane_vqc.errors import OrientationError
from membrane_vqc.orientation_sources import (
    ImportMessage,
    OrientationImportResult,
    PayloadDigest,
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
