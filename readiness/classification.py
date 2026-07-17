"""
Couche readiness : classification du jour en bande discrète.

Cette couche ne connaît rien de la génération du plan de base — elle prend
une semaine déjà générée (List[SessionSlot]) et la module en fonction de
signaux de readiness. Elle peut être remplacée/étendue indépendamment
(règles -> ML) sans toucher à generate_week_template / generate_macrocycle_plan.
"""

from config.loader import (
    ACWR_DANGER_THRESHOLD,
    DEFAULT_READINESS_THRESHOLDS,
    MONOTONY_DANGER_THRESHOLD,
)
from domain.enums import ReadinessBand
from domain.models import ReadinessSignals


def classify_readiness(
    signals: ReadinessSignals,
    thresholds: dict | None = None,
) -> ReadinessBand:
    """
    Classe le readiness du jour en bande discrète, à partir du score et de
    deux garde-fous indépendants (ACWR, monotony) qui peuvent dégrader la
    bande même si le score isolé paraît correct.
    """
    th = thresholds or DEFAULT_READINESS_THRESHOLDS

    if signals.score <= th["critical_max"]:
        band = ReadinessBand.CRITICAL
    elif signals.score <= th["low_max"]:
        band = ReadinessBand.LOW
    elif signals.score >= th["high_min"]:
        band = ReadinessBand.HIGH
    else:
        band = ReadinessBand.NORMAL

    # garde-fou ACWR : pic de charge récent -> jamais HIGH/NORMAL non filtré
    if signals.acwr >= ACWR_DANGER_THRESHOLD and band in (ReadinessBand.NORMAL, ReadinessBand.HIGH):
        band = ReadinessBand.LOW

    # garde-fou monotony : charge trop répétitive -> pas de bonus HIGH
    if signals.monotony >= MONOTONY_DANGER_THRESHOLD and band == ReadinessBand.HIGH:
        band = ReadinessBand.NORMAL

    return band
