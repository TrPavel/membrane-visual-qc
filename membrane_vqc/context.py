"""Deterministic pure-Python local chemical-context evidence analysis."""

from __future__ import annotations

import math
import time
from collections import defaultdict
from typing import Iterable

from .chemistry import (
    ION_ELEMENTS,
    ION_RESIDUES,
    atom_name,
    charged_role,
    donor_acceptor_roles,
    is_polar_heavy_element,
    is_protein,
    is_water,
    residue_name,
    safe_element,
)
from .context_models import (
    ContextContact,
    ExposureAnalysis,
    LocalContextAnalysis,
    LocalContextConfig,
    ResidueLocalContext,
)
from .exposure import collapse_alternate_locations
from .membrane import AtomRecord

ResidueKey = tuple[str, str, str, str]
CONTACT_ORDER = {
    "putative_salt_bridge": 0,
    "distance_only_potential_hbond": 1,
    "nearby_water": 2,
    "nearby_ion": 3,
    "polar_ligand_proximity": 4,
    "ligand_proximity": 5,
}


def analyze_local_context(
    atoms: Iterable[AtomRecord],
    *,
    target_residues: Iterable[ResidueKey],
    exposure_analysis: ExposureAnalysis,
    config: LocalContextConfig | None = None,
) -> LocalContextAnalysis:
    """Analyze conservative contacts for target residues within each model."""
    started = time.perf_counter()
    config = config or LocalContextConfig()
    original = tuple(atoms)
    _validate_coordinates(original)
    collapsed, _, _ = collapse_alternate_locations(original)
    ordered = tuple(sorted(collapsed, key=_atom_key))
    targets = tuple(sorted({_normalize_residue_key(key) for key in target_residues}))
    exposure = exposure_analysis.by_residue()
    grouped = _residue_groups(ordered)
    models: dict[str, tuple[AtomRecord, ...]] = {
        model: tuple(atom for atom in ordered if atom.model == model)
        for model in sorted({atom.model for atom in ordered})
    }
    warnings = _element_warnings(ordered)
    categories = _category_atom_counts(ordered)
    results: list[ResidueLocalContext] = []
    for target_key in targets:
        target_atoms = grouped.get(target_key, ())
        burial = exposure.get(target_key)
        burial_state = burial.classification if burial is not None else "unknown"
        if not target_atoms:
            results.append(
                ResidueLocalContext(
                    *target_key,
                    status="unavailable",
                    burial_state="unknown",
                    contact_support="unavailable",
                    context_state="INSUFFICIENT_CONTEXT",
                    warnings=("No usable atoms were available for this review item.",),
                )
            )
            continue
        if not any(charged_role(atom) or donor_acceptor_roles(atom) for atom in target_atoms):
            results.append(
                ResidueLocalContext(
                    *target_key,
                    status="unavailable",
                    burial_state=burial_state,
                    contact_support="unavailable",
                    context_state="INSUFFICIENT_CONTEXT",
                    warnings=(
                        "No recognized charged, donor, or acceptor target atoms were available.",
                    ),
                )
            )
            continue
        contacts = _contacts_for_target(target_atoms, models[target_key[0]], config)
        support = "detected" if contacts else "not_detected"
        state = derive_context_state(burial_state, support)
        results.append(
            ResidueLocalContext(
                *target_key,
                status="completed",
                burial_state=burial_state,
                contact_support=support,
                context_state=state,
                contacts=contacts,
            )
        )
    return LocalContextAnalysis(
        status="completed" if all(item.status == "completed" for item in results) else "partial",
        residues=tuple(results),
        config=config,
        warnings=tuple(warnings),
        category_atom_counts=tuple(sorted(categories.items())),
        elapsed_seconds=time.perf_counter() - started,
    )


def derive_context_state(burial_state: str, contact_support: str) -> str:
    if burial_state == "unknown" or contact_support == "unavailable":
        return "INSUFFICIENT_CONTEXT"
    detected = contact_support == "detected"
    if burial_state == "buried":
        return "BURIED_WITH_POTENTIAL_SUPPORT" if detected else "BURIED_NO_DETECTED_SUPPORT"
    if burial_state in {"intermediate", "exposed"}:
        return "ACCESSIBLE_WITH_POTENTIAL_SUPPORT" if detected else "ACCESSIBLE_NO_DETECTED_SUPPORT"
    return "INSUFFICIENT_CONTEXT"


def _contacts_for_target(
    target_atoms: tuple[AtomRecord, ...],
    model_atoms: tuple[AtomRecord, ...],
    config: LocalContextConfig,
) -> tuple[ContextContact, ...]:
    candidates: dict[tuple[str, str, str, str, str], ContextContact] = {}
    target_key = _residue_key(target_atoms[0])
    entity_sizes = _entity_sizes(model_atoms)
    for target in target_atoms:
        target_roles = donor_acceptor_roles(target)
        target_charge = charged_role(target)
        target_polar = bool(target_roles or target_charge)
        if not target_polar:
            continue
        for partner in model_atoms:
            partner_key = _residue_key(partner)
            if partner_key == target_key:
                continue
            distance = _distance(target, partner)
            contact_type = ""
            notes: tuple[str, ...] = ()
            partner_charge = charged_role(partner)
            if (
                target_charge
                and partner_charge
                and target_charge != partner_charge
                and distance <= config.salt_bridge_cutoff
            ):
                contact_type = "putative_salt_bridge"
                notes = ("Opposite canonical charged groups within the distance cutoff.",)
            elif is_protein(partner):
                partner_roles = donor_acceptor_roles(partner)
                complementary = ("donor" in target_roles and "acceptor" in partner_roles) or (
                    "acceptor" in target_roles and "donor" in partner_roles
                )
                if (
                    complementary
                    and distance <= config.potential_hbond_cutoff
                    and not _adjacent_backbone_pair(target, partner)
                ):
                    contact_type = "distance_only_potential_hbond"
                    notes = (
                        "Heavy-atom distance only; hydrogen and angular geometry not assessed.",
                    )
            elif is_water(partner):
                if safe_element(partner) == "O" and distance <= config.water_cutoff:
                    contact_type = "nearby_water"
                    notes = ("Nearby water only; no water-bridge claim.",)
            elif _is_ion(partner, entity_sizes):
                if distance <= config.ion_cutoff:
                    contact_type = "nearby_ion"
                    notes = ("Proximity only; no coordination or energetic claim.",)
            elif partner.is_hetatm is True and safe_element(partner) not in {"", "H"}:
                if is_polar_heavy_element(partner) and distance <= config.polar_ligand_cutoff:
                    contact_type = "polar_ligand_proximity"
                    notes = ("Supported ligand N/O/S proximity; chemistry remains unassigned.",)
                elif distance <= config.ligand_cutoff:
                    contact_type = "ligand_proximity"
                    notes = ("Heavy-atom proximity only; ligand chemistry remains unassigned.",)
            if contact_type:
                contact = ContextContact(
                    contact_type=contact_type,
                    target_atom=atom_name(target),
                    partner_model=partner.model,
                    partner_chain=partner.chain or "_",
                    partner_resi=partner.resi,
                    partner_resn=residue_name(partner),
                    partner_atom=atom_name(partner),
                    partner_element=safe_element(partner),
                    distance=distance,
                    notes=notes,
                )
                dedupe = (contact_type, *contact.partner_key)
                previous = candidates.get(dedupe)
                if previous is None or _contact_sort_key(contact) < _contact_sort_key(previous):
                    candidates[dedupe] = contact
    return tuple(sorted(candidates.values(), key=_contact_sort_key))


def _entity_sizes(atoms: tuple[AtomRecord, ...]) -> dict[ResidueKey, int]:
    sizes: dict[ResidueKey, int] = defaultdict(int)
    for atom in atoms:
        sizes[_residue_key(atom)] += 1
    return dict(sizes)


def _category_atom_counts(atoms: tuple[AtomRecord, ...]) -> dict[str, int]:
    entity_sizes = _entity_sizes(atoms)
    counts = {"protein": 0, "water": 0, "ion": 0, "ligand": 0, "other_hetatm": 0}
    for atom in atoms:
        if is_protein(atom):
            category = "protein"
        elif is_water(atom):
            category = "water"
        elif _is_ion(atom, entity_sizes):
            category = "ion"
        elif atom.is_hetatm is True and safe_element(atom) not in {"", "H"}:
            category = "ligand"
        else:
            category = "other_hetatm"
        counts[category] += 1
    return counts


def _element_warnings(atoms: tuple[AtomRecord, ...]) -> list[str]:
    entity_sizes = _entity_sizes(atoms)
    warnings = []
    for atom in atoms:
        if (
            atom.is_hetatm is True
            and not is_water(atom)
            and not _is_ion(atom, entity_sizes)
            and safe_element(atom) == ""
        ):
            warnings.append(
                "Unsupported or ambiguous HETATM element at "
                f"{atom.model}/{atom.chain or '_'}/{atom.resi}/{residue_name(atom)}/{atom_name(atom)}; "
                "excluded from ligand context."
            )
    return list(dict.fromkeys(warnings))


def _is_ion(atom: AtomRecord, entity_sizes: dict[ResidueKey, int]) -> bool:
    if atom.is_hetatm is not True or entity_sizes.get(_residue_key(atom)) != 1:
        return False
    supplied = str(atom.element or "").strip().upper()
    inferred = safe_element(atom)
    return (
        residue_name(atom) in ION_RESIDUES or supplied in ION_ELEMENTS or inferred in ION_ELEMENTS
    )


def _adjacent_backbone_pair(left: AtomRecord, right: AtomRecord) -> bool:
    if (
        left.chain != right.chain
        or atom_name(left) not in {"N", "O", "OXT"}
        or atom_name(right) not in {"N", "O", "OXT"}
    ):
        return False
    try:
        return abs(int(left.resi) - int(right.resi)) == 1
    except ValueError:
        return False


def _residue_groups(atoms: tuple[AtomRecord, ...]) -> dict[ResidueKey, tuple[AtomRecord, ...]]:
    groups: dict[ResidueKey, list[AtomRecord]] = defaultdict(list)
    for atom in atoms:
        groups[_residue_key(atom)].append(atom)
    return {key: tuple(value) for key, value in groups.items()}


def _normalize_residue_key(key: ResidueKey) -> ResidueKey:
    model, chain, resi, resn = key
    return str(model), str(chain or "_"), str(resi), str(resn).upper()


def _residue_key(atom: AtomRecord) -> ResidueKey:
    return atom.model, atom.chain or "_", atom.resi, residue_name(atom)


def _atom_key(atom: AtomRecord) -> tuple[object, ...]:
    return (*_residue_key(atom), atom_name(atom), atom.altloc, atom.x, atom.y, atom.z)


def _contact_sort_key(contact: ContextContact) -> tuple[object, ...]:
    return (
        contact.distance,
        CONTACT_ORDER[contact.contact_type],
        contact.partner_model,
        contact.partner_chain,
        contact.partner_resi,
        contact.partner_resn,
        contact.target_atom,
        contact.partner_atom,
    )


def _distance(left: AtomRecord, right: AtomRecord) -> float:
    return math.sqrt((left.x - right.x) ** 2 + (left.y - right.y) ** 2 + (left.z - right.z) ** 2)


def _validate_coordinates(atoms: tuple[AtomRecord, ...]) -> None:
    for atom in atoms:
        if not all(math.isfinite(float(value)) for value in (atom.x, atom.y, atom.z)):
            raise ValueError("Local-context coordinates must be finite.")
