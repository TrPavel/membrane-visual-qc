"""Lazy optional FreeSASA reference adapter for exposure parity checks."""

from __future__ import annotations

import importlib
import time
from collections import defaultdict
from dataclasses import replace
from typing import Iterable

from .context_models import (
    AtomSASA,
    ExposureAnalysis,
    ExposureBackendMetadata,
    ExposureConfig,
    ResidueExposure,
    SurfacePartition,
)
from .exposure import (
    ALTLOC_POLICY,
    TIEN_2013_THEORETICAL_MAX_ASA,
    ResidueKey,
    _aggregate_residue_results,
    _atom_identity,
    _residue_key,
    _target_residue_keys,
    _validate_coordinates,
    collapse_alternate_locations,
    prepare_atoms,
)
from .membrane import AtomRecord

BACKEND_NAME = "freesasa_reference"


def calculate_freesasa_exposure(
    atoms: Iterable[AtomRecord],
    *,
    config: ExposureConfig | None = None,
    target_residues: Iterable[ResidueKey] | None = None,
) -> ExposureAnalysis:
    """Calculate reference SASA, returning typed unavailable evidence if FreeSASA is absent.

    FreeSASA is imported only inside this function. Membrane-region sample points are not
    exposed by its Python API, so region partitions are explicitly unavailable here.
    """
    started = time.perf_counter()
    config = config or ExposureConfig()
    original = tuple(atoms)
    _validate_coordinates(original)
    collapsed, alternate_seen, alternate_discarded = collapse_alternate_locations(original)
    requested = _target_residue_keys(collapsed, config, target_residues)
    prepared = prepare_atoms(collapsed, config, alternate_seen, alternate_discarded)
    models = tuple(sorted({atom.model for atom in collapsed}))
    warnings = list(prepared.warnings)
    if len(models) > 1:
        warnings.append(
            "Exposure selection spans multiple models; each model was calculated independently "
            "without cross-model occlusion."
        )

    try:
        freesasa = importlib.import_module("freesasa")
    except ImportError:
        warning = (
            "FreeSASA reference backend is unavailable; install the exposure-reference extra "
            "to enable it."
        )
        warnings.append(warning)
        return ExposureAnalysis(
            status="unavailable",
            residues=tuple(_unavailable_residue(key, warning) for key in sorted(requested)),
            metadata=_metadata(
                config,
                models,
                alternate_seen,
                alternate_discarded,
                "unavailable",
                "",
                warnings,
                started,
            ),
        )

    warnings.append(
        "FreeSASA does not expose accessible sample coordinates through calcCoord; "
        "membrane-region surface partitions are unavailable for this reference backend."
    )
    atom_results: dict[int, AtomSASA] = {}
    indices_by_model: dict[str, list[int]] = defaultdict(list)
    for model in models:
        indices_by_model[model] = []
    for index, atom in enumerate(prepared.atoms):
        indices_by_model[atom.model].append(index)

    parameters = freesasa.Parameters(
        {
            "algorithm": freesasa.ShrakeRupley,
            "probe-radius": float(config.probe_radius),
            "n-points": config.sphere_points,
        }
    )
    unavailable_partition = SurfacePartition(None, None, None, None, None, None, None)
    processed_models: set[str] = set()
    skipped_model_warnings: dict[str, str] = {}
    for model in sorted(indices_by_model):
        indices = indices_by_model[model]
        if len(indices) < 2:
            warning = (
                "FreeSASA reference calculation was skipped for model "
                f"{model!r} because it has fewer than two supported atoms; "
                "the native singleton calculation is not called."
            )
            warnings.append(warning)
            skipped_model_warnings[model] = warning
            continue
        coordinates = [
            coordinate
            for index in indices
            for coordinate in (
                float(prepared.atoms[index].x),
                float(prepared.atoms[index].y),
                float(prepared.atoms[index].z),
            )
        ]
        radii = [prepared.radii[index] for index in indices]
        result = freesasa.calcCoord(coordinates, radii, parameters)
        processed_models.add(model)
        for local_index, atom_index in enumerate(indices):
            atom = prepared.atoms[atom_index]
            if _residue_key(atom) not in requested:
                continue
            atom_results[atom_index] = AtomSASA(
                atom_key=_atom_identity(atom),
                element=atom.element,
                radius=prepared.radii[atom_index],
                sasa=float(result.atomArea(local_index)),
                accessible_points=-1,
                sphere_points=config.sphere_points,
                partition=unavailable_partition,
            )

    residue_results = _aggregate_residue_results(
        prepared.atoms,
        atom_results,
        requested,
        config,
        None,
        warnings,
    )
    residue_results = [
        replace(
            item,
            warnings=tuple(dict.fromkeys((*item.warnings, skipped_model_warnings[item.model]))),
        )
        if item.status == "unavailable" and item.model in skipped_model_warnings
        else item
        for item in residue_results
    ]
    version = str(getattr(freesasa, "__version__", ""))
    completed_count = sum(item.status == "completed" for item in residue_results)
    if not processed_models:
        status = "unavailable"
    elif skipped_model_warnings or completed_count != len(residue_results):
        status = "partial"
    else:
        status = "completed"
    return ExposureAnalysis(
        status=status,
        residues=tuple(residue_results),
        metadata=_metadata(
            config,
            models,
            alternate_seen,
            alternate_discarded,
            "used" if processed_models else "available",
            version,
            warnings,
            started,
        ),
    )


def _metadata(
    config: ExposureConfig,
    models: tuple[str, ...],
    alternate_seen: int,
    alternate_discarded: int,
    freesasa_status: str,
    backend_version: str,
    warnings: list[str],
    started: float,
) -> ExposureBackendMetadata:
    return ExposureBackendMetadata(
        backend=BACKEND_NAME,
        backend_version=backend_version or "unknown",
        config=config,
        alternate_atoms_seen=alternate_seen,
        alternate_atoms_discarded=alternate_discarded,
        alternate_location_policy=ALTLOC_POLICY,
        models=models,
        freesasa_status=freesasa_status,
        warnings=tuple(dict.fromkeys(warnings)),
        elapsed_seconds=time.perf_counter() - started,
    )


def _unavailable_residue(key: ResidueKey, warning: str) -> ResidueExposure:
    partition = SurfacePartition(None, None, None, None, None, None, None)
    reference = TIEN_2013_THEORETICAL_MAX_ASA.get(key[3])
    return ResidueExposure(
        *key,
        status="unavailable",
        residue_sasa=None,
        sidechain_sasa=None,
        relative_sasa=None,
        reference_max_sasa=reference,
        reference_status="available" if reference is not None else "unavailable",
        classification="unknown",
        partition=partition,
        sidechain_partition=partition,
        warnings=(warning,),
    )
