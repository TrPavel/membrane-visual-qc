"""Deterministic schema-1.5 orientation-comparison reports."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Mapping

from .errors import ReportError
from .orientation_comparison import (
    ComparableOrientation,
    ComparisonMetrics,
    ComparisonThresholds,
    OrientationComparisonResult,
    compare_orientations,
)
from .orientation_sources import PlanarGeometryEvidence, StructureScope

SCHEMA_VERSION = "1.5"
REPORT_TYPE = "orientation_source_comparison"
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
_LOCAL_PATH_TOKEN = re.compile(
    r"(?:file://|(?<![A-Za-z0-9])[A-Za-z]:[\\/]|\\\\[^\\\s]+[\\/]|(?<![A-Za-z0-9:])/(?:Users|home|tmp|var|etc|opt|mnt|Volumes)/)",
    re.IGNORECASE,
)
COORDINATE_FINGERPRINT_ALGORITHM = "mvqc_atom_identity_coordinates_sha256:v1:legacy_pdb_3dp"


def _text(value: object, label: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise ReportError(f"{label} must be text.")
    text = value.strip()
    if (
        not text
        or len(text) > 512
        or any(ord(character) < 32 or ord(character) == 127 for character in text)
    ):
        raise ReportError(f"{label} must be bounded text without controls.")
    if _LOCAL_PATH_TOKEN.search(text):
        raise ReportError(f"{label} must not contain a local path.")
    return text


@dataclass(frozen=True, slots=True)
class ComparisonPayloadDigest:
    role: str
    sha256: str
    byte_size: int
    media_type: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", _text(self.role, "payload role"))
        digest = str(self.sha256)
        if not _SHA256.fullmatch(digest):
            raise ReportError("payload sha256 must be lowercase hexadecimal.")
        if (
            type(self.byte_size) is not int
            or self.byte_size < 0
            or self.byte_size > 5 * 1024 * 1024
        ):
            raise ReportError("payload byte_size is outside the reviewed limit.")
        if self.media_type is not None:
            object.__setattr__(self, "media_type", _text(self.media_type, "media_type"))

    def as_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "sha256": self.sha256,
            "byte_size": self.byte_size,
            "media_type": self.media_type,
        }


@dataclass(frozen=True, slots=True)
class ComparisonReportSource:
    source_key: str
    provider_name: str
    adapter_name: str
    adapter_version: str
    record_id: str
    resource_version: str | None
    software_version: str | None
    evidence_id: str
    comparison_input: ComparableOrientation
    payloads: tuple[ComparisonPayloadDigest, ...]
    pdbtm_cached_acquisition: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        for field in (
            "source_key",
            "provider_name",
            "adapter_name",
            "adapter_version",
            "record_id",
        ):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        for field in ("resource_version", "software_version"):
            object.__setattr__(self, field, _text(getattr(self, field), field, optional=True))
        if not _SHA256.fullmatch(str(self.evidence_id)):
            raise ReportError("evidence_id must be a lowercase SHA-256 digest.")
        if self.source_key != self.comparison_input.source_key:
            raise ReportError("Report source key contradicts comparison input.")
        roles = [payload.role for payload in self.payloads]
        if not roles or len(roles) != len(set(roles)):
            raise ReportError("Each source requires uniquely named payload digests.")
        object.__setattr__(
            self, "payloads", tuple(sorted(self.payloads, key=lambda item: item.role))
        )
        acquisition = self.pdbtm_cached_acquisition
        if acquisition is not None:
            if self.source_key != "pdbtm":
                raise ReportError("Only PDBTM may carry cached acquisition provenance.")
            try:
                acquisition = json.loads(json.dumps(dict(acquisition), allow_nan=False))
            except (TypeError, ValueError) as exc:
                raise ReportError(
                    "Cached acquisition provenance must be finite JSON data."
                ) from exc
            acquisition = _project_cached_acquisition(acquisition)
            _validate_cached_acquisition(acquisition, self.record_id, self.payloads)
            _validate_no_sensitive_material(acquisition, "pdbtm_cached_acquisition")
            object.__setattr__(self, "pdbtm_cached_acquisition", acquisition)

    def as_dict(self) -> dict[str, object]:
        item = self.comparison_input
        scope = item.scope
        geometry = item.geometry
        return {
            "source_key": self.source_key,
            "provider_name": self.provider_name,
            "adapter": {"name": self.adapter_name, "version": self.adapter_version},
            "record_id": self.record_id,
            "provider_versions": {
                "resource_version": self.resource_version,
                "software_version": self.software_version,
            },
            "evidence_id": self.evidence_id,
            "payloads": [payload.as_dict() for payload in self.payloads],
            "pdbtm_cached_acquisition": self.pdbtm_cached_acquisition,
            "applicability": {
                "established": item.applicable,
                "status": "applicable" if item.applicable else "not_applicable",
                "method": item.applicability_method,
                "matched_atom_count": item.matched_atom_count,
                "matched_residue_count": item.matched_residue_count,
                "scope": None
                if scope is None
                else {
                    "structure_id": scope.structure_id,
                    "model_id": scope.model_id,
                    "biological_assembly": scope.biological_assembly,
                    "chains": list(scope.chains),
                    "coordinate_frame": scope.coordinate_frame,
                    "coordinate_fingerprint": scope.coordinate_fingerprint,
                    "coordinate_fingerprint_algorithm": COORDINATE_FINGERPRINT_ALGORITHM,
                },
                "current_geometry": None if geometry is None else geometry.as_dict(),
                "warnings": list(item.warnings),
            },
        }


def _validate_cached_acquisition(
    value: object, record_id: str, payloads: tuple[ComparisonPayloadDigest, ...]
) -> None:
    acquisition = _mapping(value, "pdbtm_cached_acquisition")
    required = {
        "model_version",
        "provider_kind",
        "provider_name",
        "provider_contract",
        "canonical_record_id",
        "acquisition_mode",
        "consumption_mode",
        "pair_id",
        "snapshot_id",
        "cache_generation",
        "provider_versions",
        "validated_at",
        "payloads",
        "pair_self_consistency",
        "object_applicability",
    }
    if set(acquisition) != required:
        raise ReportError("Cached acquisition provenance has an unexpected field set.")
    if acquisition.get("provider_kind") != "pdbtm_api_v1":
        raise ReportError("Cached acquisition provenance is not PDBTM API v1.")
    constants = {
        "model_version": "1",
        "provider_name": "PDBTM",
        "acquisition_mode": "direct_https_provider_fetch",
    }
    for field, expected_value in constants.items():
        if acquisition.get(field) != expected_value:
            raise ReportError(f"Cached acquisition {field} is invalid.")
    if acquisition.get("consumption_mode") not in {
        "active_cache_read",
        "snapshot_cache_read",
    }:
        raise ReportError("Cached acquisition consumption_mode is invalid.")
    cache_generation = acquisition.get("cache_generation")
    if cache_generation is not None and (type(cache_generation) is not int or cache_generation < 0):
        raise ReportError("Cached acquisition cache_generation is invalid.")
    if not _TIMESTAMP.fullmatch(str(acquisition.get("validated_at", ""))):
        raise ReportError("Cached acquisition validated_at is invalid.")
    for field in (
        "provider_contract",
        "canonical_record_id",
    ):
        _text(acquisition.get(field), f"cached acquisition {field}")
    if str(acquisition.get("canonical_record_id", "")).casefold() != record_id.casefold():
        raise ReportError("Cached acquisition record ID contradicts comparison source.")
    for field in ("pair_id", "snapshot_id"):
        if not _SHA256.fullmatch(str(acquisition.get(field, ""))):
            raise ReportError(f"Cached acquisition {field} must be a SHA-256 digest.")
    acquired_payloads = acquisition.get("payloads")
    if not isinstance(acquired_payloads, list) or len(acquired_payloads) != 2:
        raise ReportError("Cached acquisition must contain exactly two payload records.")
    expected = {(item.role, item.sha256, item.byte_size) for item in payloads}
    actual = {
        (item.get("role"), item.get("sha256"), item.get("byte_size"))
        for item in acquired_payloads
        if isinstance(item, Mapping)
    }
    if actual != expected:
        raise ReportError("Cached acquisition payloads contradict source payload digests.")
    provider_versions = _mapping(
        acquisition.get("provider_versions"), "cached acquisition provider_versions"
    )
    for field in ("resource_version", "software_version"):
        _text(
            provider_versions.get(field),
            f"cached acquisition provider_versions.{field}",
            optional=True,
        )
    pair = _mapping(
        acquisition.get("pair_self_consistency"), "cached acquisition pair_self_consistency"
    )
    expected_pair = {
        "adapter_name": "pdbtm_api_v1_offline",
        "adapter_version": "1",
        "method": "identity",
        "coordinate_frame": "pdbtm_transformed_companion",
        "fingerprint_match": True,
    }
    if any(pair.get(field) != expected_value for field, expected_value in expected_pair.items()):
        raise ReportError("Cached acquisition pair self-consistency is invalid.")
    for field in ("rmsd", "maximum_residual"):
        value = pair.get(field)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ReportError("Cached acquisition pair self-consistency metric is invalid.")
    applicability = _mapping(
        acquisition.get("object_applicability"), "cached acquisition object_applicability"
    )
    if (
        applicability.get("established") is not False
        or applicability.get("scope") != "not_evaluated"
    ):
        raise ReportError("Cached acquisition object applicability is invalid.")
    _text(applicability.get("statement"), "cached acquisition object applicability statement")


def _project_cached_acquisition(value: object) -> dict[str, object]:
    """Close and sanitize Stage-4B2 provenance for the schema-1.5 contract."""

    acquisition = _mapping(value, "pdbtm_cached_acquisition")
    payloads = acquisition.get("payloads")
    if not isinstance(payloads, list) or len(payloads) != 2:
        raise ReportError("Cached acquisition must contain exactly two payload records.")
    input_payload_keys = {
        "role",
        "byte_size",
        "sha256",
        "content_type",
        "requested_url",
        "final_url",
        "requested_at",
        "completed_at",
        "etag",
        "last_modified",
        "transport_verification",
    }
    projected_payloads = []
    for payload in payloads:
        item = _mapping(payload, "cached acquisition payload")
        if set(item) not in ({"role", "byte_size", "sha256"}, input_payload_keys):
            raise ReportError("Cached acquisition payload has an unexpected field set.")
        projected_payloads.append(
            {
                "role": item.get("role"),
                "byte_size": item.get("byte_size"),
                "sha256": item.get("sha256"),
            }
        )
    provider_versions = _mapping(
        acquisition.get("provider_versions"), "cached acquisition provider_versions"
    )
    if set(provider_versions) != {"resource_version", "software_version"}:
        raise ReportError("Cached acquisition provider_versions has an unexpected field set.")
    pair = _mapping(
        acquisition.get("pair_self_consistency"), "cached acquisition pair_self_consistency"
    )
    pair_keys = {
        "adapter_name",
        "adapter_version",
        "method",
        "coordinate_frame",
        "rmsd",
        "maximum_residual",
        "fingerprint_match",
    }
    if set(pair) != pair_keys:
        raise ReportError("Cached acquisition pair_self_consistency has an unexpected field set.")
    applicability = _mapping(
        acquisition.get("object_applicability"), "cached acquisition object_applicability"
    )
    if set(applicability) != {"established", "scope", "statement"}:
        raise ReportError("Cached acquisition object_applicability has an unexpected field set.")
    projected = dict(acquisition)
    projected["provider_versions"] = dict(provider_versions)
    projected["payloads"] = projected_payloads
    projected["pair_self_consistency"] = dict(pair)
    projected["object_applicability"] = dict(applicability)
    return projected


@dataclass(frozen=True, slots=True)
class SelectedObjectEvidence:
    structure_id: str
    model_id: str
    biological_assembly: str | None
    chains: tuple[str, ...]
    coordinate_frame: str
    coordinate_fingerprint: str
    atom_count: int

    def __post_init__(self) -> None:
        for field in ("structure_id", "model_id", "coordinate_frame"):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        object.__setattr__(
            self,
            "biological_assembly",
            _text(self.biological_assembly, "biological_assembly", optional=True),
        )
        object.__setattr__(self, "chains", tuple(sorted({_text(x, "chain") for x in self.chains})))
        if not self.chains:
            raise ReportError("selected object requires at least one chain.")
        if not _SHA256.fullmatch(str(self.coordinate_fingerprint)):
            raise ReportError("selected-object fingerprint must be lowercase SHA-256.")
        if type(self.atom_count) is not int or self.atom_count < 1:
            raise ReportError("selected-object atom_count must be positive.")

    def as_dict(self) -> dict[str, object]:
        return {
            "structure_id": self.structure_id,
            "model_id": self.model_id,
            "biological_assembly": self.biological_assembly,
            "chains": list(self.chains),
            "coordinate_frame": self.coordinate_frame,
            "coordinate_fingerprint": self.coordinate_fingerprint,
            "coordinate_fingerprint_algorithm": COORDINATE_FINGERPRINT_ALGORITHM,
            "atom_count": self.atom_count,
        }


def build_comparison_report(
    *,
    generated_at: str,
    software_name: str,
    software_version: str,
    software_commit: str,
    python_version: str,
    pymol_version: str,
    platform: str,
    selected_object: SelectedObjectEvidence,
    first_source: ComparisonReportSource,
    second_source: ComparisonReportSource,
    comparison: OrientationComparisonResult,
) -> dict[str, object]:
    """Build one deterministic report; time/runtime values are explicit inputs."""

    if not _TIMESTAMP.fullmatch(str(generated_at)):
        raise ReportError("generated_at must be an RFC3339 UTC timestamp ending in Z.")
    if (first_source.source_key, second_source.source_key) != ("pdbtm", "opm"):
        raise ReportError("Schema 1.5 source order must be exactly pdbtm then opm.")
    if (comparison.first_source, comparison.second_source) != ("pdbtm", "opm"):
        raise ReportError("Comparison source identities contradict report sources.")
    report = {
        "schema_version": SCHEMA_VERSION,
        "report_type": REPORT_TYPE,
        "software": {
            "name": _text(software_name, "software_name"),
            "version": _text(software_version, "software_version"),
            "commit": _text(software_commit, "software_commit"),
        },
        "runtime": {
            "python": _text(python_version, "python_version"),
            "pymol": _text(pymol_version, "pymol_version"),
            "platform": _text(platform, "platform"),
        },
        "generated_at": generated_at,
        "selected_object": selected_object.as_dict(),
        "sources": [first_source.as_dict(), second_source.as_dict()],
        "comparison": comparison.as_dict(),
    }
    validate_comparison_report(report)
    return report


def validate_comparison_report(report: dict[str, object]) -> None:
    """Validate cross-field and privacy invariants beyond JSON Schema."""

    _validate_report_shape(report)
    if report.get("schema_version") != SCHEMA_VERSION or report.get("report_type") != REPORT_TYPE:
        raise ReportError("Not a schema-1.5 orientation comparison report.")
    sources = report.get("sources")
    if not isinstance(sources, list) or len(sources) != 2:
        raise ReportError("Comparison report requires exactly two sources.")
    keys = tuple(source.get("source_key") for source in sources if isinstance(source, dict))
    if keys != ("pdbtm", "opm"):
        raise ReportError("Comparison sources must be ordered pdbtm then opm.")
    comparison = report.get("comparison")
    if not isinstance(comparison, dict):
        raise ReportError("Comparison result is required.")
    interpretation = comparison.get("interpretation")
    if not isinstance(interpretation, dict) or interpretation.get("consensus") is not False:
        raise ReportError("Comparison report must explicitly disclaim consensus.")
    if (
        interpretation.get("ranking") is not False
        or interpretation.get("preferred_source") is not None
        or interpretation.get("biological_verdict") is not False
    ):
        raise ReportError("Comparison report cannot rank, select, or make a biological verdict.")
    _validate_comparison_consistency(report, sources, comparison)
    _validate_no_sensitive_material(report)


def _exact_keys(value: object, expected: set[str], label: str) -> Mapping[str, object]:
    mapping = _mapping(value, label)
    if set(mapping) != expected:
        raise ReportError(f"{label} has an unexpected field set.")
    return mapping


def _validate_report_shape(report: Mapping[str, object]) -> None:
    """Mirror schema 1.5's closed object topology without a runtime dependency."""

    _exact_keys(
        report,
        {
            "schema_version",
            "report_type",
            "software",
            "runtime",
            "generated_at",
            "selected_object",
            "sources",
            "comparison",
        },
        "report",
    )
    _exact_keys(report.get("software"), {"name", "version", "commit"}, "software")
    _exact_keys(report.get("runtime"), {"python", "pymol", "platform"}, "runtime")
    _exact_keys(
        report.get("selected_object"),
        {
            "structure_id",
            "model_id",
            "biological_assembly",
            "chains",
            "coordinate_frame",
            "coordinate_fingerprint",
            "coordinate_fingerprint_algorithm",
            "atom_count",
        },
        "selected_object",
    )
    sources = report.get("sources")
    if not isinstance(sources, list) or len(sources) != 2:
        raise ReportError("Comparison report requires exactly two sources.")
    for index, raw_source in enumerate(sources):
        source = _exact_keys(
            raw_source,
            {
                "source_key",
                "provider_name",
                "adapter",
                "record_id",
                "provider_versions",
                "evidence_id",
                "payloads",
                "pdbtm_cached_acquisition",
                "applicability",
            },
            f"sources[{index}]",
        )
        _exact_keys(source.get("adapter"), {"name", "version"}, "source adapter")
        _exact_keys(
            source.get("provider_versions"),
            {"resource_version", "software_version"},
            "source provider_versions",
        )
        payloads = source.get("payloads")
        if not isinstance(payloads, list) or not 1 <= len(payloads) <= 4:
            raise ReportError("Source payloads must contain one to four records.")
        for payload in payloads:
            _exact_keys(
                payload,
                {"role", "sha256", "byte_size", "media_type"},
                "source payload",
            )
        acquisition = source.get("pdbtm_cached_acquisition")
        if acquisition is not None:
            digests = tuple(
                ComparisonPayloadDigest(
                    item.get("role"),
                    item.get("sha256"),
                    item.get("byte_size"),
                    item.get("media_type"),
                )
                for item in payloads
                if isinstance(item, Mapping)
            )
            _validate_cached_acquisition(acquisition, str(source.get("record_id", "")), digests)
        applicability = _exact_keys(
            source.get("applicability"),
            {
                "established",
                "status",
                "method",
                "matched_atom_count",
                "matched_residue_count",
                "scope",
                "current_geometry",
                "warnings",
            },
            "source applicability",
        )
        if applicability.get("scope") is not None:
            _exact_keys(
                applicability.get("scope"),
                {
                    "structure_id",
                    "model_id",
                    "biological_assembly",
                    "chains",
                    "coordinate_frame",
                    "coordinate_fingerprint",
                    "coordinate_fingerprint_algorithm",
                },
                "source applicability scope",
            )
        if applicability.get("current_geometry") is not None:
            _exact_keys(
                applicability.get("current_geometry"),
                {
                    "geometry",
                    "center",
                    "normal",
                    "lower_offset",
                    "upper_offset",
                    "interface_width",
                    "frame",
                },
                "source current geometry",
            )
    comparison = _exact_keys(
        report.get("comparison"),
        {
            "method",
            "method_version",
            "first_source",
            "second_source",
            "comparable",
            "band",
            "thresholds",
            "metrics",
            "reasons",
            "warnings",
            "interpretation",
        },
        "comparison",
    )
    _exact_keys(
        comparison.get("thresholds"),
        {
            "normal_axis_angle_degrees",
            "center_displacement_angstrom",
            "thickness_difference_angstrom",
            "interpretation",
        },
        "comparison thresholds",
    )
    metrics = comparison.get("metrics")
    if metrics is not None:
        _exact_keys(metrics, set(ComparisonMetrics.__dataclass_fields__), "comparison metrics")
    _exact_keys(
        comparison.get("interpretation"),
        {"consensus", "ranking", "preferred_source", "biological_verdict", "statement"},
        "comparison interpretation",
    )


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ReportError(f"{label} must be an object.")
    return value


def _source_input_from_dict(value: object) -> ComparableOrientation:
    source = _mapping(value, "source")
    applicability = _mapping(source.get("applicability"), "source applicability")
    raw_scope = applicability.get("scope")
    scope = None
    if raw_scope is not None:
        scope_data = _mapping(raw_scope, "source applicability scope")
        scope = StructureScope(
            scope_data.get("structure_id"),
            str(scope_data.get("model_id", "")),
            scope_data.get("biological_assembly"),
            tuple(scope_data.get("chains", ())),
            "comparison_report",
            str(scope_data.get("coordinate_frame", "")),
            scope_data.get("coordinate_fingerprint"),
        )
    raw_geometry = applicability.get("current_geometry")
    geometry = None
    if raw_geometry is not None:
        geometry_data = _mapping(raw_geometry, "source current geometry")
        geometry = PlanarGeometryEvidence(
            tuple(geometry_data.get("center", ())),
            tuple(geometry_data.get("normal", ())),
            geometry_data.get("lower_offset"),
            geometry_data.get("upper_offset"),
            geometry_data.get("interface_width"),
            str(geometry_data.get("frame", "")),
        )
    return ComparableOrientation(
        str(source.get("source_key", "")),
        applicability.get("established") is True,
        scope,
        geometry,
        applicability.get("method"),
        applicability.get("matched_atom_count"),
        applicability.get("matched_residue_count"),
        tuple(applicability.get("warnings", ())),
    )


def _validate_comparison_consistency(
    report: Mapping[str, object], sources: list[object], comparison: Mapping[str, object]
) -> None:
    try:
        thresholds_data = _mapping(comparison.get("thresholds"), "comparison thresholds")
        thresholds = ComparisonThresholds(
            thresholds_data.get("normal_axis_angle_degrees"),
            thresholds_data.get("center_displacement_angstrom"),
            thresholds_data.get("thickness_difference_angstrom"),
        )
        if thresholds != ComparisonThresholds():
            raise ReportError("Schema 1.5 uses the fixed reviewed comparison thresholds.")
        expected = compare_orientations(
            _source_input_from_dict(sources[0]),
            _source_input_from_dict(sources[1]),
            thresholds=thresholds,
        ).as_dict()
    except ReportError:
        raise
    except Exception as exc:
        raise ReportError(f"Invalid comparison evidence: {exc}") from exc
    if dict(comparison) != expected:
        raise ReportError("Comparison result does not match its serialized source evidence.")

    selected = _mapping(report.get("selected_object"), "selected_object")
    for source in sources:
        applicability = _mapping(
            _mapping(source, "source").get("applicability"), "source applicability"
        )
        if applicability.get("established") is not True:
            continue
        scope = _mapping(applicability.get("scope"), "applicable source scope")
        for field in ("model_id", "coordinate_frame"):
            if selected.get(field) != scope.get(field):
                raise ReportError(f"Applicable source {field} contradicts selected object.")
        if (
            selected.get("coordinate_fingerprint_algorithm") != COORDINATE_FINGERPRINT_ALGORITHM
            or scope.get("coordinate_fingerprint_algorithm") != COORDINATE_FINGERPRINT_ALGORITHM
        ):
            raise ReportError("Coordinate fingerprint algorithm is not the reviewed contract.")
        if selected.get("coordinate_fingerprint") != scope.get("coordinate_fingerprint"):
            raise ReportError(
                "Applicable source fingerprint contradicts the selected-object snapshot."
            )
        selected_id, source_id = selected.get("structure_id"), scope.get("structure_id")
        if source_id is not None and str(selected_id).casefold() != str(source_id).casefold():
            raise ReportError("Applicable source structure_id contradicts selected object.")
        if tuple(selected.get("chains", ())) != tuple(scope.get("chains", ())):
            raise ReportError("Applicable source chains contradict selected object.")
        selected_assembly = selected.get("biological_assembly")
        source_assembly = scope.get("biological_assembly")
        if (
            selected_assembly is not None
            and source_assembly is not None
            and selected_assembly != source_assembly
        ):
            raise ReportError("Applicable source assembly contradicts selected object.")


def _validate_no_sensitive_material(value: object, path: str = "report") -> None:
    if isinstance(value, bytes):
        raise ReportError(f"Raw payload bytes are forbidden at {path}.")
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).casefold()
            if lowered in {"path", "raw_payload", "raw_payloads", "payload_content", "credentials"}:
                raise ReportError(f"Sensitive field {key!r} is forbidden at {path}.")
            _validate_no_sensitive_material(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_no_sensitive_material(item, f"{path}[{index}]")
    elif isinstance(value, str):
        if _LOCAL_PATH_TOKEN.search(value):
            raise ReportError(f"Local path is forbidden at {path}.")


def export_comparison_report(report: dict[str, object], path: str | Path) -> Path:
    """Atomically export canonical UTF-8 JSON after semantic validation."""

    validate_comparison_report(report)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return output
