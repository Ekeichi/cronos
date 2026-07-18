"""Couche readiness : ajustement des séances d'une semaine déjà générée."""

from config.loader import (
    HARD_SESSION_LOW_REDUCTION_FACTOR,
    RECUP_REPLACEMENT_DURATION_FACTOR,
    SL_CRITICAL_SHORTEN_FACTOR,
)
from domain.enums import Priority, ReadinessBand, SessionRole
from domain.models import ReadinessSignals, SessionFeedback, SessionSlot
from readiness.classification import classify_readiness

# --- Helpers de transformation d'un slot ------------------------------------


def _downgrade_to_recup(slot: SessionSlot) -> SessionSlot:
    """Une séance HARD devient une récup courte — utilisé en CRITICAL."""
    return SessionSlot(
        role=SessionRole.RECUP,
        day_position=slot.day_position,
        priority=Priority.SOFT,
        duration_min=slot.duration_min * RECUP_REPLACEMENT_DURATION_FACTOR,
        d_plus_target_m=0.0,
        intensity_zone="Z1",
        notes=f"[readiness] remplacé (repos/récup) — séance {slot.role.value} initialement prévue",
    )


def _reduce_intensity_session(slot: SessionSlot, factor: float) -> SessionSlot:
    """Séance HARD maintenue mais réduite en volume/D+ — utilisé en LOW."""
    return SessionSlot(
        role=slot.role,
        day_position=slot.day_position,
        priority=slot.priority,
        duration_min=slot.duration_min * factor,
        d_plus_target_m=slot.d_plus_target_m * factor,
        intensity_zone=slot.intensity_zone,
        notes=f"[readiness] réduit ({int(factor*100)}%) — {slot.notes}".strip(" —"),
    )


def _shorten_long_session(slot: SessionSlot, factor: float, drop_d_plus: bool) -> SessionSlot:
    """SL raccourcie en cas de readiness critique — jamais annulée entièrement."""
    return SessionSlot(
        role=slot.role,
        day_position=slot.day_position,
        priority=slot.priority,
        duration_min=slot.duration_min * factor,
        d_plus_target_m=0.0 if drop_d_plus else slot.d_plus_target_m * factor,
        intensity_zone=slot.intensity_zone,
        notes=f"[readiness] raccourci ({int(factor*100)}%) — {slot.notes}".strip(" —"),
    )


# --- Règles d'ajustement par rôle -------------------------------------------

_HARD_ROLES = {SessionRole.SEUIL, SessionRole.VMA, SessionRole.COTES}


def adjust_session(slot: SessionSlot, band: ReadinessBand) -> SessionSlot:
    """
    Ajuste un slot individuel selon la bande de readiness du jour.

    Règles v1 (volontairement simples, pas de mémoire d'un jour à l'autre —
    l'hystérésis / les garde-fous hebdo viendront dans une couche au-dessus) :

      - HARD (SEUIL/VMA/COTES) : le plus sacrifié. CRITICAL -> recup,
        LOW -> réduit, NORMAL/HIGH -> inchangé.
      - SL : protégée. Seule CRITICAL la raccourcit (jamais supprimée) ;
        son bénéfice ne se substitue à rien d'autre.
      - RENFO : sacrifiée avant les séances cardio en CRITICAL (fatigue
        neuromusculaire déjà là), sinon inchangée.
      - EF / RECUP : jamais modifiées automatiquement — c'est le tampon,
        pas la cible d'ajustement.
    """
    if slot.role in _HARD_ROLES:
        if band == ReadinessBand.CRITICAL:
            return _downgrade_to_recup(slot)
        if band == ReadinessBand.LOW:
            return _reduce_intensity_session(slot, factor=HARD_SESSION_LOW_REDUCTION_FACTOR)
        return slot  # NORMAL / HIGH inchangé pour l'instant (v1 prudente)

    if slot.role == SessionRole.SL:
        if band == ReadinessBand.CRITICAL:
            return _shorten_long_session(slot, factor=SL_CRITICAL_SHORTEN_FACTOR, drop_d_plus=True)
        return slot

    if slot.role == SessionRole.RENFO:
        if band == ReadinessBand.CRITICAL:
            return _downgrade_to_recup(slot)
        return slot

    return slot  # EF, RECUP


def adjust_week(
    week_slots: list[SessionSlot],
    signals: ReadinessSignals,
    previous_band: ReadinessBand | None = None,
    last_session_feedback: SessionFeedback | None = None,
) -> tuple[list[SessionSlot], ReadinessBand]:
    """
    Applique adjust_session à toute une semaine à partir d'un seul jeu de
    signaux readiness (v1 : un score représentatif de la semaine, ou appelé
    jour par jour en amont si le readiness est recalculé quotidiennement).

    previous_band et last_session_feedback sont transmis tels quels à
    classify_readiness (hystérésis et override RPE respectivement) ; laissés
    à None, le comportement est identique à l'ancienne version stateless.

    Renvoie un tuple (slots ajustés, bande retenue) : l'appelant doit
    persister la bande retenue pour la fournir comme previous_band au
    prochain appel (c'est ce qui fait fonctionner l'hystérésis d'un jour
    sur l'autre).
    """
    band = classify_readiness(
        signals,
        previous_band=previous_band,
        last_session_feedback=last_session_feedback,
    )
    return [adjust_session(slot, band) for slot in week_slots], band
