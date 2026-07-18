"""
Événements d'historique : une décision (état + action prescrite) ou un
feedback post-séance. Ce sont des structures pures, sans effet de bord —
la persistance (JSONL) vit dans persistence/event_log.py, appelée depuis l'extérieur
de generation/ et readiness/.

Destinés à constituer, par athlète et dans le temps, des séquences
(état, action, résultat) exploitables plus tard pour entraîner un modèle
de représentation d'état (type JEPA).
"""

from dataclasses import dataclass

from domain.enums import Phase, ReadinessBand
from domain.models import ReadinessSignals, SessionFeedback, SessionSlot


@dataclass
class DecisionEvent:
    athlete_id: str
    event_date: str              # ISO 8601, YYYY-MM-DD
    phase: Phase
    week_in_block: int
    block_length: int
    signals: ReadinessSignals
    previous_band: ReadinessBand | None
    resulting_band: ReadinessBand
    planned_slot: SessionSlot        # la proposition du plan de base, avant ajustement readiness
    adjusted_slot: SessionSlot       # l'action réellement prescrite, après adjust_session
    policy_version: str
    raw_signals: dict | None = None  # réservé pour signaux bruts futurs (série HRV nuit par nuit,
                                      # sommeil détaillé) — non peuplé aujourd'hui, juste le champ
                                      # pour ne pas devoir réinstrumenter plus tard

    def as_dict(self) -> dict:
        return {
            "athlete_id": self.athlete_id,
            "event_date": self.event_date,
            "phase": self.phase.value,
            "week_in_block": self.week_in_block,
            "block_length": self.block_length,
            "signals": self.signals.as_dict(),
            "previous_band": self.previous_band.value if self.previous_band is not None else None,
            "resulting_band": self.resulting_band.value,
            "planned_slot": self.planned_slot.as_dict(),
            "adjusted_slot": self.adjusted_slot.as_dict(),
            "policy_version": self.policy_version,
            "raw_signals": self.raw_signals,
        }


@dataclass
class FeedbackEvent:
    athlete_id: str
    event_date: str
    feedback: SessionFeedback
    policy_version: str

    def as_dict(self) -> dict:
        return {
            "athlete_id": self.athlete_id,
            "event_date": self.event_date,
            "feedback": self.feedback.as_dict(),
            "policy_version": self.policy_version,
        }
