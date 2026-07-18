"""
Charge les fichiers YAML de config/ et les transforme dans les structures
Python attendues par generation/ et readiness/ (dataclasses du domaine).

C'est le seul point du package qui connaît le format sur disque des
paramètres calibrables ; generation/ et readiness/ ne consomment que les
constantes exposées ici.
"""

from pathlib import Path

import yaml

from domain.enums import Phase, Priority, SessionRole
from domain.models import SlotTemplate

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


def load_mesocycle_progression() -> tuple[dict[int, float], float]:
    raw = _load_yaml("mesocycle_progression.yaml")
    progression = {int(week): float(multiplier) for week, multiplier in raw["progression"].items()}
    return progression, float(raw["fallback"])


def load_readiness_adjustment_factors() -> tuple[float, float, float]:
    raw = _load_yaml("readiness_adjustment_factors.yaml")
    return (
        float(raw["hard_session_low_reduction"]),
        float(raw["sl_critical_shorten"]),
        float(raw["recup_replacement_duration_factor"]),
    )


def load_readiness_hysteresis() -> tuple[float, float]:
    raw = _load_yaml("readiness_hysteresis.yaml")
    return (
        float(raw["critical_exit_margin"]),
        float(raw["low_exit_margin"]),
    )


def load_rpe_config() -> tuple[dict[str, float], float, float]:
    raw = _load_yaml("rpe_thresholds.yaml")
    return (
        {role: float(rpe) for role, rpe in raw["expected_rpe_by_role"].items()},
        float(raw["rpe_deviation_low_threshold"]),
        float(raw["rpe_deviation_critical_threshold"]),
    )


def load_policy_version() -> str:
    raw = _load_yaml("policy_version.yaml")
    return str(raw["current"])


PHASE_TEMPLATES: dict[Phase, list[SlotTemplate]] = load_phase_templates()
DEFAULT_TAPER_DECAY: dict[int, list[float]] = load_taper_curves()
DEFAULT_READINESS_THRESHOLDS, ACWR_DANGER_THRESHOLD, MONOTONY_DANGER_THRESHOLD = load_readiness_thresholds()
MESOCYCLE_PROGRESSION_DEFAULT, MESOCYCLE_PROGRESSION_FALLBACK = load_mesocycle_progression()
(
    HARD_SESSION_LOW_REDUCTION_FACTOR,
    SL_CRITICAL_SHORTEN_FACTOR,
    RECUP_REPLACEMENT_DURATION_FACTOR,
) = load_readiness_adjustment_factors()
CRITICAL_EXIT_MARGIN, LOW_EXIT_MARGIN = load_readiness_hysteresis()
EXPECTED_RPE_BY_ROLE, RPE_DEVIATION_LOW_THRESHOLD, RPE_DEVIATION_CRITICAL_THRESHOLD = load_rpe_config()
CURRENT_POLICY_VERSION: str = load_policy_version()
