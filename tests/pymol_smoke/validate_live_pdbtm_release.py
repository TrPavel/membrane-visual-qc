"""One-shot exact-artifact live PDBTM acceptance for the v0.5.0 release.

This script deliberately has no retry path. It drives the artifact's production
transport/provider/cache/retrieval classes and permits exactly the two fixed
provider GET roles for ``1pcr``.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import sys
from unittest.mock import patch


ARTIFACT_ROOT = Path(os.environ["MVQC_ARTIFACT_ROOT"]).resolve()
CACHE_ROOT = Path(os.environ["MVQC_LIVE_CACHE_ROOT"]).resolve()
RESULT_PATH = Path(os.environ["MVQC_LIVE_RESULT"]).resolve()
EXPECTED_VERSION = os.environ.get("MVQC_EXPECTED_VERSION", "0.5.0")
EXPECTED_PAYLOADS = {
    "pdbtm_json": (
        283_537,
        "38b2f724c4271a00bf2b83aa16015783610178f18d8954a88cb932b9152f36e0",
    ),
    "transformed_pdb": (
        628_434,
        "7e52525ff397e4bfa5900e602f39753628e3b1408d513a3d0d76928c0fd10698",
    ),
}
PROXY_VARIABLES = (
    "HTTP_PROXY",
    "http_proxy",
    "HTTPS_PROXY",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
)


class CountingTransport:
    def __init__(self, inner: object) -> None:
        self.inner = inner
        self.calls: list[str] = []

    def fetch(self, record_id: str, role: str, **kwargs: object) -> object:
        self.calls.append(role)
        return self.inner.fetch(record_id, role, **kwargs)


class RecordingProvider:
    def __init__(self, inner: object) -> None:
        self.inner = inner
        self.last_candidate: object | None = None

    def fetch(self, record_id: str, *, cancellation: object | None = None) -> object:
        candidate = self.inner.fetch(record_id, cancellation=cancellation)
        self.last_candidate = candidate
        return candidate


def deny_network(*_args: object, **_kwargs: object) -> object:
    raise AssertionError("network access attempted during forced-offline cache read")


def main() -> int:
    if CACHE_ROOT.exists() and any(CACHE_ROOT.iterdir()):
        raise RuntimeError("live acceptance cache must be new and empty; refusing to retry")
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ARTIFACT_ROOT))

    import membrane_vqc
    import membrane_vqc.pdbtm_transport as transport_module
    from membrane_vqc.pdbtm_cache import CacheRepository
    from membrane_vqc.pdbtm_provider import PdbtmProviderClient
    from membrane_vqc.pdbtm_retrieval import RetrievalHooks, retrieve_validate_and_commit

    if membrane_vqc.__version__ != EXPECTED_VERSION:
        raise RuntimeError("artifact version mismatch")
    if not Path(membrane_vqc.__file__).resolve().is_relative_to(ARTIFACT_ROOT):
        raise RuntimeError("membrane_vqc was not imported from the exact artifact")

    bogus_proxy = "http://release-invalid:release-invalid@127.0.0.1:1"
    for name in PROXY_VARIABLES:
        os.environ[name] = bogus_proxy
    os.environ["NO_PROXY"] = "release-invalid.invalid"
    os.environ["no_proxy"] = "release-invalid.invalid"

    repository = CacheRepository(CACHE_ROOT)
    counting = CountingTransport(transport_module.PdbtmHttpsTransport())
    recording = RecordingProvider(PdbtmProviderClient(counting))
    payloads: dict[str, dict[str, object]] = {}

    def after_pair_validation() -> None:
        candidate = recording.last_candidate
        if candidate is None:
            raise RuntimeError("provider candidate was not recorded")
        for payload in candidate.payloads:
            expected_size, expected_hash = EXPECTED_PAYLOADS[payload.role]
            actual_hash = hashlib.sha256(payload.body).hexdigest()
            if (
                payload.evidence.tls_verified is not True
                or payload.byte_size != expected_size
                or payload.sha256 != expected_hash
                or actual_hash != expected_hash
            ):
                raise RuntimeError(f"accepted evidence mismatch for {payload.role}")
            payloads[payload.role] = {
                "byte_size": payload.byte_size,
                "sha256": payload.sha256,
            }

    committed = retrieve_validate_and_commit(
        "1pcr",
        provider=recording,
        repository=repository,
        hooks=RetrievalHooks(after_pair_validation=after_pair_validation),
    )
    if counting.calls != ["pdbtm_json", "transformed_pdb"]:
        raise RuntimeError(f"unexpected request sequence: {counting.calls}")
    active = repository.read_active("1pcr")
    if active.snapshot_id != committed.snapshot_id:
        raise RuntimeError("active cache did not return the committed snapshot")
    with (
        patch.object(socket, "create_connection", side_effect=deny_network),
        patch.object(socket.socket, "connect", side_effect=deny_network),
        patch.object(transport_module.PdbtmHttpsTransport, "fetch", side_effect=deny_network),
    ):
        offline = repository.read_active("1pcr")
    if offline.snapshot_id != committed.snapshot_id or offline.semantic_result is None:
        raise RuntimeError("forced-offline cache reuse failed")

    result = {
        "artifact_version": membrane_vqc.__version__,
        "cache_commit": "PASS",
        "canonical_record_id": committed.canonical_record_id,
        "forced_offline_reuse": "PASS",
        "pair_id": committed.snapshot_core.pair_id,
        "payloads": payloads,
        "proxy_non_consultation": "PASS",
        "request_count": len(counting.calls),
        "request_roles": counting.calls,
        "snapshot_id": committed.snapshot_id,
        "tls_verification": "PASS",
    }
    RESULT_PATH.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
