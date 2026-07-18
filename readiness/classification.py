"""
Couche readiness : classification du jour en bande discrète.

Cette couche ne connaît rien de la génération du plan de base — elle prend
une semaine déjà générée (List[SessionSlot]) et la module en fonction de
signaux de readiness. Elle peut être remplacée/étendue indépendamment
(règles -> ML) sans toucher à generate_week_template / generate_macrocycle_plan.
"""

from config.loader import (
    ACWR_DANGER_THRESHOLD,
    CRITICAL_EXIT_MARGIN,
    DEFAULT_READINESS_THRESHOLDS,
    LOW_EXIT_MARGIN,
    MONOTONY_DANGER_THRESHOLD,
    RPE_DEVIATION_CRITICAL_THRESHOLD,
    RPE_DEVIATION_LOW_THRESHOLD,
)
from domain.enums import ReadinessBand
from domain.models import ReadinessSignals, SessionFeedback
from readiness.feedback import rpe_deviation


def classify_readiness(
    signals: ReadinessSignals,
    thresholds: dict | None = None,
    previous_band: ReadinessBand | None = None,
    last_session_feedback: SessionFeedback | None = None,
) -> ReadinessBand:
    """
    Classe le readiness du jour en bande discrète, à partir du score et de
    deux garde-fous indépendants (ACWR, monotony) qui peuvent dégrader la
    bande même si le score isolé paraît correct.

    Hystérésis asymétrique (previous_band) : dégrader une bande reste
    immédiat ; remonter d'une bande dégradée (CRITICAL -> LOW, LOW -> NORMAL)
    exige que le score dépasse le seuil habituel d'une marge supplémentaire
    (config/readiness_hysteresis.yaml). Sans previous_band, aucune marge
    n'est appliquée — comportement identique à l'ancienne version stateless.

    Override RPE (last_session_feedback) : appliqué en tout dernier, après
    l'hystérésis et les garde-fous ACWR/monotony. Le RPE post-séance est,
    selon la littérature sur l'autorégulation, le signal le mieux soutenu
    par la recherche (au contraire du score composite, le moins soutenu) ;
    il peut donc surclasser la classification par score, mais uniquement
    pour dégrader — jamais pour améliorer une bande (asymétrie safety-first).
    Sans last_session_feedback, aucun override n'est appliqué.
    """
    th = thresholds or DEFAULT_READINESS_THRESHOLDS

    critical_max = th["critical_max"]
    low_max = th["low_max"]
    high_min = th["high_min"]

    if previous_band == ReadinessBand.CRITICAL:
        critical_max = critical_max + CRITICAL_EXIT_MARGIN
    elif previous_band == ReadinessBand.LOW:
        low_max = low_max + LOW_EXIT_MARGIN

    if signals.score <= critical_max:
        band = ReadinessBand.CRITICAL
    elif signals.score <= low_max:
        band = ReadinessBand.LOW
    elif signals.score >= high_min:
        band = ReadinessBand.HIGH
    else:
        band = ReadinessBand.NORMAL

    # garde-fou ACWR : pic de charge récent -> jamais HIGH/NORMAL non filtré
    if signals.acwr >= ACWR_DANGER_THRESHOLD and band in (ReadinessBand.NORMAL, ReadinessBand.HIGH):
        band = ReadinessBand.LOW

    # garde-fou monotony : charge trop répétitive -> pas de bonus HIGH
    if signals.monotony >= MONOTONY_DANGER_THRESHOLD and band == ReadinessBand.HIGH:
        band = ReadinessBand.NORMAL

    # override RPE post-séance : dernier mot, dégradation uniquement
    if last_session_feedback is not None:
        deviation = rpe_deviation(last_session_feedback)
        if deviation >= RPE_DEVIATION_CRITICAL_THRESHOLD:
            band = ReadinessBand.CRITICAL
        elif deviation >= RPE_DEVIATION_LOW_THRESHOLD and band in (ReadinessBand.NORMAL, ReadinessBand.HIGH):
            band = ReadinessBand.LOW

    return band
