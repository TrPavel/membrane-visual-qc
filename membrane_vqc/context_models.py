"""Immutable data models shared by exposure and later context analysis."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


EXPOSURE_CLASSES = frozenset({"buried", "intermediate", "exposed", "unknown"})
TARGET_SCOPES = frozenset({"review_items", "all_residues", "explicit"})
CONTACT_SUPPORT_VALUES = frozenset({"detected", "not_detected", "unavailable"})
CONTEXT_STATE_PRIORITY = {
    "BURIED_NO_DETECTED_SUPPORT": 0,
    "BURIED_WITH_POTENTIAL_SUPPORT": 1,
    "INSUFFICIENT_CONTEXT": 2,
    "ACCESSIBLE_NO_DETECTED_SUPPORT": 3,
    "ACCESSIBLE_WITH_POTENTIAL_SUPPORT": 4,
}
CONTEXT_STATES = frozenset(CONTEXT_STATE_PRIORITY)
CONTACT_TYPES = frozenset(
    {
        "putative_salt_bridge",
        "distance_only_potential_hbond",
        "nearby_water",
        "nearby_ion",
        "ligand_proximity",
        "polar_ligand_proximity",
    }
)


@dataclass(frozen=True)
class ExposureConfig:
    """Validated parameters for deterministic solvent-exposure analysis."""

    probe_radius: float = 1.4
    sphere_points: int = 240
    target_scope: str = "review_items"
    include_hydrogens: bool = False
    include_nonprotein_occluders: bool = False
    radii_model: str = "element_vdw_v1"
    rsa_reference: str = "tien_2013_theoretical"
    buried_rsa_threshold: float = 0.05
    exposed_rsa_threshold: float = 0.25

    def __post_init__(self) -> None:
        if isinstance(self.sphere_points, bool) or not isinstance(self.sphere_points, int):
            raise ValueError("sphere_points must be an integer.")
        if self.sphere_points <= 0:
            raise ValueError("sphere_points must be greater than zero.")
        if not math.isfinite(float(self.probe_radius)) or self.probe_radius <= 0.0:
            raise ValueError("probe_radius must be finite and greater than zero.")
        if self.target_scope not in TARGET_SCOPES:
            raise ValueError(f"target_scope must be one of {sorted(TARGET_SCOPES)}.")
        if not isinstance(self.include_hydrogens, bool):
            raise ValueError("include_hydrogens must be boolean.")
        if not isinstance(self.include_nonprotein_occluders, bool):
            raise ValueError("include_nonprotein_occluders must be boolean.")
        if self.radii_model != "element_vdw_v1":
            raise ValueError("Unsupported radii_model; expected 'element_vdw_v1'.")
        if self.rsa_reference != "tien_2013_theoretical":
            raise ValueError("Unsupported rsa_reference; expected 'tien_2013_theoretical'.")
        thresholds = (float(self.buried_rsa_threshold), float(self.exposed_rsa_threshold))
        if not all(math.isfinite(value) for value in thresholds):
            raise ValueError("RSA thresholds must be finite.")
        if not 0.0 <= thresholds[0] < thresholds[1]:
            raise ValueError(
                "RSA thresholds must satisfy 0 <= buried_rsa_threshold < exposed_rsa_threshold."
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "probe_radius_angstrom": float(self.probe_radius),
            "sphere_points": self.sphere_points,
            "target_scope": self.target_scope,
            "include_hydrogens": self.include_hydrogens,
            "include_nonprotein_occluders": self.include_nonprotein_occluders,
            "radii_model": self.radii_model,
            "rsa_reference": self.rsa_reference,
            "buried_rsa_threshold": float(self.buried_rsa_threshold),
            "exposed_rsa_threshold": float(self.exposed_rsa_threshold),
        }


@dataclass(frozen=True)
class SurfacePartition:
    """Accessible area split by membrane region."""

    core_area: float | None
    interface_area: float | None
    outside_area: float | None
    core_fraction: float | None
    interface_fraction: float | None
    outside_fraction: float | None
    membrane_fraction: float | None

    def as_dict(self, *, prefix: str = "") -> dict[str, float | None]:
        return {
            f"{prefix}core_region_accessible_area": self.core_area,
            f"{prefix}interface_region_accessible_area": self.interface_area,
            f"{prefix}outside_region_accessible_area": self.outside_area,
            f"{prefix}core_region_accessible_fraction": self.core_fraction,
            f"{prefix}interface_region_accessible_fraction": self.interface_fraction,
            f"{prefix}outside_region_accessible_fraction": self.outside_fraction,
            f"{prefix}membrane_region_accessible_fraction": self.membrane_fraction,
        }


@dataclass(frozen=True)
class AtomSASA:
    """SASA evidence for one evaluated atom."""

    atom_key: tuple[str, str, str, str, str]
    element: str
    radius: float
    sasa: float
    accessible_points: int
    sphere_points: int
    partition: SurfacePartition


@dataclass(frozen=True)
class ResidueExposure:
    """Aggregated solvent exposure for one target residue."""

    model: str
    chain: str
    resi: str
    resn: str
    status: str
    residue_sasa: float | None
    sidechain_sasa: float | None
    relative_sasa: float | None
    reference_max_sasa: float | None
    reference_status: str
    classification: str
    partition: SurfacePartition
    sidechain_partition: SurfacePartition
    atom_sasa: tuple[AtomSASA, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def residue_key(self) -> tuple[str, str, str, str]:
        return self.model, self.chain, self.resi, self.resn

    def as_report_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": self.status,
            "residue_sasa": self.residue_sasa,
            "sidechain_sasa": self.sidechain_sasa,
            "relative_sasa": self.relative_sasa,
            "reference_max_sasa": self.reference_max_sasa,
            "reference_status": self.reference_status,
            "classification": self.classification,
            "warnings": list(self.warnings),
        }
        result.update(self.partition.as_dict())
        result.update(self.sidechain_partition.as_dict(prefix="sidechain_"))
        return result


@dataclass(frozen=True)
class ExposureBackendMetadata:
    """Backend, preprocessing, warning, and timing metadata."""

    backend: str
    backend_version: str
    config: ExposureConfig
    alternate_atoms_seen: int
    alternate_atoms_discarded: int
    alternate_location_policy: str
    models: tuple[str, ...]
    freesasa_status: str
    warnings: tuple[str, ...]
    elapsed_seconds: float

    def as_report_dict(self) -> dict[str, Any]:
        result = {
            "backend": self.backend,
            "backend_version": self.backend_version,
            **self.config.as_dict(),
            "alternate_atoms_seen": self.alternate_atoms_seen,
            "alternate_atoms_discarded": self.alternate_atoms_discarded,
            "alternate_location_policy": self.alternate_location_policy,
            "models": list(self.models),
            "freesasa_status": self.freesasa_status,
            "warnings": list(self.warnings),
            "elapsed_seconds": self.elapsed_seconds,
        }
        return result


@dataclass(frozen=True)
class ExposureAnalysis:
    """Complete immutable exposure-analysis result."""

    status: str
    residues: tuple[ResidueExposure, ...]
    metadata: ExposureBackendMetadata

    def by_residue(self) -> dict[tuple[str, str, str, str], ResidueExposure]:
        return {result.residue_key: result for result in self.residues}

    def as_report_metadata(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "target_scope": self.metadata.config.target_scope,
            "exposure": self.metadata.as_report_dict(),
        }


@dataclass(frozen=True)
class LocalContextConfig:
    """Validated conservative distance thresholds for local-context evidence."""

    salt_bridge_cutoff: float = 4.0
    potential_hbond_cutoff: float = 3.5
    water_cutoff: float = 3.5
    ion_cutoff: float = 4.0
    ligand_cutoff: float = 5.0
    polar_ligand_cutoff: float = 3.8
    atom_role_policy: str = "standard_residue_roles_v1"

    def __post_init__(self) -> None:
        for name in (
            "salt_bridge_cutoff",
            "potential_hbond_cutoff",
            "water_cutoff",
            "ion_cutoff",
            "ligand_cutoff",
            "polar_ligand_cutoff",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(float(value)) or float(value) <= 0:
                raise ValueError(f"{name} must be finite and greater than zero.")
        if self.atom_role_policy != "standard_residue_roles_v1":
            raise ValueError("Unsupported atom_role_policy.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "salt_bridge_cutoff_angstrom": float(self.salt_bridge_cutoff),
            "potential_hbond_cutoff_angstrom": float(self.potential_hbond_cutoff),
            "water_cutoff_angstrom": float(self.water_cutoff),
            "ion_cutoff_angstrom": float(self.ion_cutoff),
            "ligand_cutoff_angstrom": float(self.ligand_cutoff),
            "polar_ligand_cutoff_angstrom": float(self.polar_ligand_cutoff),
            "atom_role_policy": self.atom_role_policy,
        }


@dataclass(frozen=True)
class ContextContact:
    """One minimum-distance, conservatively labelled contact record."""

    contact_type: str
    target_atom: str
    partner_model: str
    partner_chain: str
    partner_resi: str
    partner_resn: str
    partner_atom: str
    distance: float
    partner_element: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.contact_type not in CONTACT_TYPES:
            raise ValueError("Unsupported local-context contact type.")
        if not math.isfinite(float(self.distance)) or self.distance < 0:
            raise ValueError("Contact distance must be finite and non-negative.")

    @property
    def partner_key(self) -> tuple[str, str, str, str]:
        return self.partner_model, self.partner_chain, self.partner_resi, self.partner_resn

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.contact_type,
            "target_atom": self.target_atom,
            "partner": {
                "model": self.partner_model,
                "chain": self.partner_chain,
                "resi": self.partner_resi,
                "resn": self.partner_resn,
                "atom": self.partner_atom,
                "element": self.partner_element,
            },
            "distance_angstrom": float(self.distance),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class ResidueLocalContext:
    """Independent local-context evidence for one review residue."""

    model: str
    chain: str
    resi: str
    resn: str
    status: str
    burial_state: str
    contact_support: str
    context_state: str
    contacts: tuple[ContextContact, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.status not in {"completed", "unavailable"}:
            raise ValueError("Local-context status must be completed or unavailable.")
        if self.burial_state not in EXPOSURE_CLASSES:
            raise ValueError("Unsupported burial_state.")
        if self.contact_support not in CONTACT_SUPPORT_VALUES:
            raise ValueError("Unsupported contact_support.")
        if self.context_state not in CONTEXT_STATES:
            raise ValueError("Unsupported context_state.")

    @property
    def residue_key(self) -> tuple[str, str, str, str]:
        return self.model, self.chain, self.resi, self.resn

    def as_report_dict(self) -> dict[str, Any]:
        counts = {
            "putative_salt_bridges": 0,
            "potential_hbonds": 0,
            "waters": 0,
            "ions": 0,
            "ligand_contacts": 0,
        }
        count_keys = {
            "putative_salt_bridge": "putative_salt_bridges",
            "distance_only_potential_hbond": "potential_hbonds",
            "nearby_water": "waters",
            "nearby_ion": "ions",
            "ligand_proximity": "ligand_contacts",
            "polar_ligand_proximity": "ligand_contacts",
        }
        ligand_partners: set[tuple[str, str, str, str]] = set()
        for contact in self.contacts:
            key = count_keys[contact.contact_type]
            if key == "ligand_contacts":
                ligand_partners.add(contact.partner_key)
            else:
                counts[key] += 1
        counts["ligand_contacts"] = len(ligand_partners)
        return {
            "status": self.status,
            "burial_state": self.burial_state,
            "contact_support": self.contact_support,
            "context_state": self.context_state,
            "counts": counts,
            "contacts": [contact.as_dict() for contact in self.contacts],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class LocalContextAnalysis:
    """Complete immutable local-context result."""

    status: str
    residues: tuple[ResidueLocalContext, ...]
    config: LocalContextConfig
    warnings: tuple[str, ...] = field(default_factory=tuple)
    category_atom_counts: tuple[tuple[str, int], ...] = field(default_factory=tuple)
    elapsed_seconds: float = 0.0

    def by_residue(self) -> dict[tuple[str, str, str, str], ResidueLocalContext]:
        return {result.residue_key: result for result in self.residues}

    def state_counts(self) -> dict[str, int]:
        return {
            state: sum(item.context_state == state for item in self.residues)
            for state in CONTEXT_STATE_PRIORITY
        }

    def as_report_metadata(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "local_context": {
                **self.config.as_dict(),
                "warnings": list(self.warnings),
                "category_atom_counts": dict(self.category_atom_counts),
                "elapsed_seconds": float(self.elapsed_seconds),
                "context_state_counts": self.state_counts(),
            },
        }
