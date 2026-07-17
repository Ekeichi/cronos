"""
Charge les fichiers YAML de config/ et les transforme dans les structures
Python attendues par generation/ et readiness/ (dataclasses du domaine).

C'est le seul point du package qui connaît le format sur disque des
paramètres calibrables ; generation/ et readiness/ ne consomment que les
constantes exposées ici.
"""

from pathlib import Path

import yaml

from training_plan.domain.enums import Phase, Priority, SessionRole
from training_plan.domain.models import SlotTemplate

_CONFIG_DIR = Path(__file__).parent


def _load_yaml(filename: str) -> dict:
    with open(_CONFIG_DIR / filename, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_phase_templates() -> dict[Phase, list[SlotTemplate]]:
    raw = _load_yaml("phase_templates.yaml")
    return {
        Phase(phase_name): [
            SlotTemplate(
                role=SessionRole(entry["role"]),
                day_position=entry["day_position"],
                priority=Priority(entry["priority"]),
                duration_ratio=entry["duration_ratio"],
                d_plus_ratio=entry.get("d_plus_ratio", 0.0),
                intensity_zone=entry.get("intensity_zone", ""),
                notes=entry.get("notes", ""),
            )
            for entry in entries
        ]
        for phase_name, entries in raw.items()
    }


def load_taper_curves() -> dict[int, list[float]]:
    raw = _load_yaml("taper_curves.yaml")
    return {int(n_weeks): curve for n_weeks, curve in raw.items()}


def load_readiness_thresholds() -> tuple[dict, float, float]:
    raw = _load_yaml("readiness_thresholds.yaml")
    return (
        dict(raw["readiness_thresholds"]),
        float(raw["acwr_danger_threshold"]),
        float(raw["monotony_danger_threshold"]),
    )


PHASE_TEMPLATES: dict[Phase, list[SlotTemplate]] = load_phase_templates()
DEFAULT_TAPER_DECAY: dict[int, list[float]] = load_taper_curves()
DEFAULT_READINESS_THRESHOLDS, ACWR_DANGER_THRESHOLD, MONOTONY_DANGER_THRESHOLD = load_readiness_thresholds()
