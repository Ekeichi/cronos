"""Structures de données partagées par l'ensemble du projet."""

from dataclasses import dataclass

from domain.enums import Phase, Priority, SessionRole


@dataclass
class SessionSlot:
    role: SessionRole
    day_position: int              # 1..7, position relative dans la semaine (pas une date)
    priority: Priority
    duration_min: float            # durée cible en minutes, déjà résolue depuis les ratios
    d_plus_target_m: float = 0.0   # dénivelé positif cible (0 si non pertinent)
    intensity_zone: str = ""       # libellé libre ("Z1", "SV1-SV2", "VMA 100-110%", ...)
    notes: str = ""

    def as_dict(self) -> dict:
        return {
            "role": self.role.value,
            "day_position": self.day_position,
            "priority": self.priority.value,
            "duration_min": round(self.duration_min, 1),
            "d_plus_target_m": round(self.d_plus_target_m, 0),
            "intensity_zone": self.intensity_zone,
            "notes": self.notes,
        }


@dataclass
class SlotTemplate:
    """Squelette non résolu : ratios plutôt que valeurs absolues."""
    role: SessionRole
    day_position: int
    priority: Priority
    duration_ratio: float          # fraction de la durée totale hebdo dévolue à ce slot
    d_plus_ratio: float = 0.0      # fraction du D+ hebdo dévolue à ce slot
    intensity_zone: str = ""
    notes: str = ""


@dataclass
class MacrocycleBlock:
    phase: Phase                                # BASE, SPECIFIC, ou TAPER
    n_weeks: int                                 # longueur du bloc
    decay_curve: list[float] | None = None       # pertinent uniquement si TAPER


@dataclass
class ReadinessSignals:
    score: float            # readiness score existant (0-100)
    tsb: float = 0.0        # Training Stress Balance (Banister)
    monotony: float = 1.0   # index de Foster (moyenne/écart-type charge 7j)
    acwr: float = 1.0       # acute:chronic workload ratio (charge 7j / charge 28j)


@dataclass
class SessionFeedback:
    """Retour post-séance sur la dernière séance dure. Pas de tags qualitatifs
    de chatbot ici — hors scope, prévu pour plus tard."""
    role: SessionRole
    rpe: float                          # échelle Borg CR10, 0-10
    actual_duration_min: float = 0.0
    completed_as_planned: bool = True
    notes: str = ""
