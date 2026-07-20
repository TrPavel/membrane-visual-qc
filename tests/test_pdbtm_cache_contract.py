from dataclasses import replace
import json

import pytest

from membrane_vqc.pdbtm_cache_contract import (
    AcquisitionPayload,
    CacheContractError,
    ContentTypeEvidence,
    FormatCore,
    IndexCore,
    IndexRecord,
    PairCore,
    PayloadIdentity,
    ProviderVersions,
    ResponseHeaders,
    SnapshotCore,
    canonical_json_bytes,
    compute_format_id,
    compute_index_id,
    compute_pair_id,
    compute_snapshot_id,
    make_format_envelope,
    make_index_envelope,
    make_pair_envelope,
    make_snapshot_envelope,
    parse_format_envelope,
    parse_index_envelope,
    parse_pair_envelope,
    parse_snapshot_envelope,
    serialize_format_envelope,
    serialize_index_envelope,
    serialize_pair_envelope,
    serialize_snapshot_envelope,
    validate_format_core,
    validate_index_core,
    validate_pair_core,
    validate_snapshot_core,
)

JSON_SHA = "38b2f724c4271a00bf2b83aa16015783610178f18d8954a88cb932b9152f36e0"
PDB_SHA = "7e52525ff397e4bfa5900e602f39753628e3b1408d513a3d0d76928c0fd10698"
PAIR_ID = "99b69dbd1b6c813dafb045747af410baade7001dfea9af905705728fa8e82c52"
SNAPSHOT_ID = "4bba46290d044828df412bb1f9fdc542bc440ba4aa99518664de6ef38f2e9ef5"
INDEX_ID = "b28cb5c9c519950f03af7a88ee37698d1646760e50bd7d4e09a8cd6a08ecc3cd"
FORMAT_ID = "d1e17f7d64ece8a7423e7214bcbb4a4a65f6307cc3e1bc6b36fb49bc5bab5cd4"

PAIR_BYTES = (
    b'{"cache_contract":"pdbtm-api-v1/cache-v1","canonical_record_id":"1pcr",'
    b'"payloads":[{"byte_size":283537,"role":"pdbtm_json","sha256":"'
    + JSON_SHA.encode()
    + b'"},{"byte_size":628434,"role":"transformed_pdb","sha256":"'
    + PDB_SHA.encode()
    + b'"}],"provider":"pdbtm_api_v1"}'
)

SNAPSHOT_BYTES = (
    b'{"cache_contract":"pdbtm-api-v1/cache-v1","canonical_record_id":"1pcr",'
    b'"pair_id":"'
    + PAIR_ID.encode()
    + b'","payloads":[{"byte_size":283537,"completed_at":"2026-07-20T00:00:01.000000Z",'
    b'"final_url":"https://pdbtm.unitmp.org/api/v1/entry/1pcr.json","headers":'
    b'{"content_encoding":null,"content_type":{"charset":"utf-8","media_type":"text/plain"},'
    b'"etag":null,"last_modified":null},"requested_at":"2026-07-20T00:00:00.000000Z",'
    b'"requested_url":"https://pdbtm.unitmp.org/api/v1/entry/1pcr.json","role":"pdbtm_json",'
    b'"sha256":"'
    + JSON_SHA.encode()
    + b'","status":200,"transport_verification":"direct_https_tls_verified"},'
    b'{"byte_size":628434,"completed_at":"2026-07-20T00:00:03.000000Z",'
    b'"final_url":"https://pdbtm.unitmp.org/api/v1/entry/1pcr.trpdb","headers":'
    b'{"content_encoding":null,"content_type":{"charset":"utf-8","media_type":"text/plain"},'
    b'"etag":null,"last_modified":null},"requested_at":"2026-07-20T00:00:02.000000Z",'
    b'"requested_url":"https://pdbtm.unitmp.org/api/v1/entry/1pcr.trpdb",'
    b'"role":"transformed_pdb","sha256":"'
    + PDB_SHA.encode()
    + b'","status":200,"transport_verification":"direct_https_tls_verified"}],'
    b'"provider":"pdbtm_api_v1","provider_versions":{"resource_version":"1017",'
    b'"software_version":"3.2.134"},"validated_at":"2026-07-20T00:00:04.000000Z",'
    b'"validation_profile":"pdbtm-api-v1-format-precision-envelope-v1"}'
)

INDEX_BYTES = (
    b'{"cache_contract":"pdbtm-api-v1/cache-v1","generation":1,"records":{"1pcr":'
    b'{"active_snapshot_id":"'
    + SNAPSHOT_ID.encode()
    + b'","generation":1,"snapshot_ids":["'
    + SNAPSHOT_ID.encode()
    + b'"]}}}'
)

FORMAT_BYTES = (
    b'{"cache_contract":"pdbtm-api-v1/cache-v1",'
    b'"canonical_json":"mvqc-canonical-json-v1","digest_algorithm":"sha256",'
    b'"provider":"pdbtm_api_v1"}'
)


def pair_core() -> PairCore:
    return PairCore(
        canonical_record_id="1pcr",
        payloads=(
            PayloadIdentity("pdbtm_json", JSON_SHA, 283537),
            PayloadIdentity("transformed_pdb", PDB_SHA, 628434),
        ),
    )


def snapshot_core() -> SnapshotCore:
    headers = ResponseHeaders(ContentTypeEvidence("text/plain", "utf-8"))
    return SnapshotCore(
        canonical_record_id="1pcr",
        pair_id=PAIR_ID,
        payloads=(
            AcquisitionPayload(
                role="pdbtm_json",
                sha256=JSON_SHA,
                byte_size=283537,
                requested_url="https://pdbtm.unitmp.org/api/v1/entry/1pcr.json",
                final_url="https://pdbtm.unitmp.org/api/v1/entry/1pcr.json",
                requested_at="2026-07-20T00:00:00.000000Z",
                completed_at="2026-07-20T00:00:01.000000Z",
                status=200,
                headers=headers,
            ),
            AcquisitionPayload(
                role="transformed_pdb",
                sha256=PDB_SHA,
                byte_size=628434,
                requested_url="https://pdbtm.unitmp.org/api/v1/entry/1pcr.trpdb",
                final_url="https://pdbtm.unitmp.org/api/v1/entry/1pcr.trpdb",
                requested_at="2026-07-20T00:00:02.000000Z",
                completed_at="2026-07-20T00:00:03.000000Z",
                status=200,
                headers=headers,
            ),
        ),
        provider_versions=ProviderVersions("1017", "3.2.134"),
        validated_at="2026-07-20T00:00:04.000000Z",
    )


def index_core() -> IndexCore:
    return IndexCore(
        generation=1,
        records={"1pcr": IndexRecord(1, SNAPSHOT_ID, (SNAPSHOT_ID,))},
    )


@pytest.mark.parametrize(
    ("core", "expected_bytes", "expected_id", "compute"),
    [
        (pair_core(), PAIR_BYTES, PAIR_ID, compute_pair_id),
        (snapshot_core(), SNAPSHOT_BYTES, SNAPSHOT_ID, compute_snapshot_id),
        (index_core(), INDEX_BYTES, INDEX_ID, compute_index_id),
        (FormatCore(), FORMAT_BYTES, FORMAT_ID, compute_format_id),
    ],
)
def test_frozen_golden_core_vectors(core, expected_bytes, expected_id, compute):
    encoded = canonical_json_bytes(core.to_dict())
    assert encoded == expected_bytes
    assert (
        len(encoded)
        == {PAIR_ID: 349, SNAPSHOT_ID: 1443, INDEX_ID: 265, FORMAT_ID: 138}[expected_id]
    )
    assert compute(core) == expected_id


@pytest.mark.parametrize(
    ("make", "serialize", "parse"),
    [
        (lambda: make_pair_envelope(pair_core()), serialize_pair_envelope, parse_pair_envelope),
        (
            lambda: make_snapshot_envelope(snapshot_core()),
            serialize_snapshot_envelope,
            parse_snapshot_envelope,
        ),
        (lambda: make_index_envelope(index_core()), serialize_index_envelope, parse_index_envelope),
        (make_format_envelope, serialize_format_envelope, parse_format_envelope),
    ],
)
def test_envelope_round_trip(make, serialize, parse):
    envelope = make()
    encoded = serialize(envelope)
    assert parse(encoded) == envelope
    assert not encoded.startswith(b"\xef\xbb\xbf")
    assert not encoded.endswith(b"\n")


def test_object_insertion_order_does_not_change_canonical_bytes():
    assert canonical_json_bytes({"z": 1, "a": 2}) == b'{"a":2,"z":1}'
    assert canonical_json_bytes({"a": 2, "z": 1}) == b'{"a":2,"z":1}'


def test_explicit_core_validation_boundary_accepts_all_frozen_models():
    validate_pair_core(pair_core())
    validate_snapshot_core(snapshot_core())
    validate_index_core(index_core())
    validate_format_core(FormatCore())

    with pytest.raises(CacheContractError, match="exact PairCore"):
        validate_pair_core(pair_core().to_dict())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value",
    [1.0, float("nan"), float("inf"), b"bytes", {"set"}, ("tuple",)],
)
def test_canonical_serializer_rejects_values_outside_domain(value):
    with pytest.raises(CacheContractError):
        canonical_json_bytes({"value": value})


def test_canonical_serializer_rejects_custom_subclasses_and_lone_surrogates():
    class IntSubclass(int):
        pass

    class DictSubclass(dict):
        pass

    for value in (IntSubclass(1), DictSubclass(), "\ud800"):
        with pytest.raises(CacheContractError):
            canonical_json_bytes({"value": value})


@pytest.mark.parametrize(
    "mutation",
    [
        lambda data: b"\xef\xbb\xbf" + data,
        lambda data: data + b"\n",
        lambda data: data + b"\r\n",
        lambda data: data.replace(b'"format_id":', b' "format_id":', 1),
    ],
)
def test_parser_rejects_noncanonical_storage_bytes(mutation):
    encoded = serialize_format_envelope(make_format_envelope())
    with pytest.raises(CacheContractError):
        parse_format_envelope(mutation(encoded))


def test_parser_rejects_duplicate_keys_before_shape_validation():
    encoded = serialize_format_envelope(make_format_envelope())
    duplicate = encoded.replace(
        b'{"format_core":', b'{"format_id":"' + FORMAT_ID.encode() + b'","format_core":'
    )
    with pytest.raises(CacheContractError, match="duplicate"):
        parse_format_envelope(duplicate)


def test_parser_rejects_float_and_nonfinite_json_tokens():
    valid = json.loads(serialize_index_envelope(make_index_envelope(index_core())))
    for token in (b"1.0", b"NaN", b"Infinity"):
        encoded = canonical_json_bytes(valid).replace(
            b'"generation":1', b'"generation":' + token, 1
        )
        with pytest.raises(CacheContractError):
            parse_index_envelope(encoded)


def test_payload_order_is_semantic_and_never_sorted():
    core = pair_core()
    with pytest.raises(CacheContractError, match="exactly pdbtm_json then transformed_pdb"):
        PairCore(core.canonical_record_id, tuple(reversed(core.payloads)))  # type: ignore[arg-type]


def test_malformed_payload_constructor_type_is_rejected_deterministically():
    with pytest.raises(CacheContractError, match="invalid payload type"):
        PairCore("1pcr", (object(), object()))  # type: ignore[arg-type]


def test_bool_is_not_accepted_for_integer_fields():
    with pytest.raises(CacheContractError, match="exact type int"):
        PayloadIdentity("pdbtm_json", JSON_SHA, True)  # type: ignore[arg-type]
    with pytest.raises(CacheContractError, match="exact type int"):
        IndexCore(True, {})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "record_id",
    ["1PCR", " 1pcr", "1pcr ", "../x", "аpcr", "1pc%", "1pc/"],
)
def test_only_canonical_lowercase_domain_identifiers_are_accepted(record_id):
    with pytest.raises(CacheContractError):
        replace(pair_core(), canonical_record_id=record_id)


@pytest.mark.parametrize(
    "bad_digest",
    [JSON_SHA.upper(), "0" * 63, "g" * 64],
)
def test_only_lowercase_sha256_is_accepted(bad_digest):
    with pytest.raises(CacheContractError):
        PayloadIdentity("pdbtm_json", bad_digest, 1)


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-07-20T00:00:00Z",
        "2026-07-20t00:00:00.000000Z",
        "2026-07-20T00:00:00.000000+00:00",
        "2026-02-30T00:00:00.000000Z",
    ],
)
def test_timestamps_have_one_exact_utc_form(timestamp):
    with pytest.raises(CacheContractError):
        replace(snapshot_core(), validated_at=timestamp)


def test_acquisition_times_must_be_chronological():
    payload = snapshot_core().payloads[0]
    with pytest.raises(CacheContractError, match="must not precede"):
        replace(payload, completed_at="2026-07-19T23:59:59.000000Z")


@pytest.mark.parametrize(
    "url",
    [
        "http://pdbtm.unitmp.org/api/v1/entry/1pcr.json",
        "https://evil.example/api/v1/entry/1pcr.json",
        "https://pdbtm.unitmp.org:443/api/v1/entry/1pcr.json",
        "https://pdbtm.unitmp.org/api/v1/entry/1PCR.json",
        "https://pdbtm.unitmp.org/api/v1/entry/1pcr.json?x=1",
    ],
)
def test_only_exact_approved_urls_are_accepted(url):
    payload = snapshot_core().payloads[0]
    with pytest.raises(CacheContractError):
        replace(payload, requested_url=url, final_url=url)


def test_redirected_final_url_is_rejected():
    payload = snapshot_core().payloads[0]
    with pytest.raises(CacheContractError, match="exactly equal"):
        replace(
            payload,
            final_url="https://pdbtm.unitmp.org/api/v1/entry/1a0s.json",
        )


def test_pair_and_snapshot_self_identifiers_exclude_envelope_identifier():
    pair = make_pair_envelope(pair_core())
    pair_data = json.loads(serialize_pair_envelope(pair))
    pair_data["pair_id"] = "0" * 64
    tampered = canonical_json_bytes(pair_data)
    with pytest.raises(CacheContractError, match="does not match"):
        parse_pair_envelope(tampered)

    snapshot = make_snapshot_envelope(snapshot_core())
    snapshot_data = json.loads(serialize_snapshot_envelope(snapshot))
    snapshot_data["snapshot_id"] = "0" * 64
    with pytest.raises(CacheContractError, match="does not match"):
        parse_snapshot_envelope(canonical_json_bytes(snapshot_data))


def test_closed_shapes_reject_missing_and_extra_fields():
    envelope = json.loads(serialize_format_envelope(make_format_envelope()))
    envelope["unexpected"] = None
    with pytest.raises(CacheContractError, match="closed shape"):
        parse_format_envelope(canonical_json_bytes(envelope))

    del envelope["unexpected"]
    del envelope["format_core"]["provider"]
    with pytest.raises(CacheContractError, match="closed shape"):
        parse_format_envelope(canonical_json_bytes(envelope))


def test_index_requires_sorted_unique_membership_and_generation_consistency():
    with pytest.raises(CacheContractError, match="unique"):
        IndexRecord(1, None, ("f" * 64, "a" * 64))
    with pytest.raises(CacheContractError, match="member"):
        IndexRecord(1, "a" * 64, ())
    with pytest.raises(CacheContractError, match="global generation"):
        IndexCore(1, {"1pcr": IndexRecord(2, None, ())})


def test_snapshot_pair_id_and_record_url_are_cross_checked():
    with pytest.raises(CacheContractError, match="pair_id"):
        replace(snapshot_core(), pair_id="0" * 64)
    with pytest.raises(CacheContractError, match="canonical_record_id"):
        replace(snapshot_core(), canonical_record_id="1a0s")


def test_header_evidence_is_closed_safe_and_role_specific():
    headers = ResponseHeaders(
        ContentTypeEvidence("application/json", None),
        content_encoding="identity",
        etag='"safe"',
        last_modified="Sun, 20 Jul 2026 00:00:00 GMT",
    )
    payload = replace(snapshot_core().payloads[0], headers=headers)
    assert payload.headers.content_encoding == "identity"
    with pytest.raises(CacheContractError):
        ResponseHeaders(ContentTypeEvidence("text/plain", "utf-8"), etag="bad\r\nheader")
    with pytest.raises(CacheContractError):
        replace(snapshot_core().payloads[1], headers=headers)


def test_noncanonical_escaped_lone_surrogate_is_rejected():
    encoded = serialize_format_envelope(make_format_envelope())
    changed = encoded.replace(b'"provider":"pdbtm_api_v1"', b'"provider":"\\ud800"')
    with pytest.raises(CacheContractError, match="Unicode scalar"):
        parse_format_envelope(changed)
