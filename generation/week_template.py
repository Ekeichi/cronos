"""
Génère un squelette de semaine d'entraînement (SessionSlot[]) en fonction de :
  - la phase du macrocycle (BASE / SPECIFIC / TAPER)
  - la position dans le mésocycle (progression / deload)

Ce module est volontairement déterministe et ne connaît rien du readiness.
Il produit le "plan idéal si tout va bien" — la baseline sur laquelle
l'heuristique de readiness viendra moduler intensité/volume/contenu.
"""

from config.loader import PHASE_TEMPLATES
from domain.enums import Phase
from domain.models import SessionSlot
from generation.progression import _taper_multiplier, _volume_multiplier


def _resolve_slots(
    phase: Phase,
    resolved_weekly_volume: float,
    resolved_weekly_d_plus: float,
) -> list[SessionSlot]:
    """Applique les ratios du template de phase à des totaux hebdo déjà résolus."""
    slots = [
        SessionSlot(
            role=tmpl.role,
            day_position=tmpl.day_position,
            priority=tmpl.priority,
            duration_min=tmpl.duration_ratio * resolved_weekly_volume,
            d_plus_target_m=tmpl.d_plus_ratio * resolved_weekly_d_plus,
            intensity_zone=tmpl.intensity_zone,
            notes=tmpl.notes,
        )
        for tmpl in PHASE_TEMPLATES[phase]
    ]
    return sorted(slots, key=lambda s: s.day_position)


def generate_week_template(
    phase: Phase,
    week_in_block: int,
    block_length: int,
    base_weekly_volume_min: float,
    base_weekly_d_plus_m: float = 0.0,
    decay_curve: list[float] | None = None,
) -> list[SessionSlot]:
    """
    Génère le squelette déterministe d'une semaine d'entraînement, quelle
    que soit la phase.

    Le "block" est générique : pour BASE/SPECIFIC c'est un mésocycle
    (progression build sur block_length-1 semaines puis deload en dernière
    semaine) ; pour TAPER c'est le bloc de taper (décroissance monotone via
    decay_curve, pas de montée). La distinction de forme de progression est
    gérée en interne, l'appelant n'a qu'à fournir phase + position dans le bloc.

    Args:
        phase: phase du macrocycle (BASE / SPECIFIC / TAPER)
        week_in_block: position dans le bloc courant (1-indexed)
        block_length: nombre de semaines du bloc (mésocycle ou taper)
        base_weekly_volume_min: volume hebdo de référence en minutes
        base_weekly_d_plus_m: D+ hebdo de référence en mètres
        decay_curve: courbe de décroissance custom, uniquement utilisée si
            phase == TAPER (sinon ignorée)

    Returns:
        Liste de SessionSlot représentant la semaine, triée par day_position.
    """
    if phase not in PHASE_TEMPLATES:
        raise ValueError(f"Phase inconnue: {phase}")
    if week_in_block < 1 or week_in_block > block_length:
        raise ValueError("week_in_block hors bornes du bloc")

    if phase == Phase.TAPER:
        multiplier = _taper_multiplier(week_in_block, block_length, decay_curve)
    else:
        multiplier = _volume_multiplier(week_in_block, block_length)

    resolved_weekly_volume = base_weekly_volume_min * multiplier
    resolved_weekly_d_plus = base_weekly_d_plus_m * multiplier

    return _resolve_slots(phase, resolved_weekly_volume, resolved_weekly_d_plus)
