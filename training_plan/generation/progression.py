"""Multiplicateurs de volume hebdo : progression mésocycle et décroissance taper."""

from training_plan.config.loader import DEFAULT_TAPER_DECAY

# ---------------------------------------------------------------------------
# Progression mésocycle (schéma 3:1 build/deload par défaut)
# ---------------------------------------------------------------------------

DEFAULT_MESOCYCLE_PROGRESSION = {
    # week_in_mesocycle (1-indexed) -> multiplicateur de volume hebdo
    1: 1.00,
    2: 1.08,
    3: 1.15,
    4: 0.65,   # semaine deload
}


def _volume_multiplier(week_in_mesocycle: int, mesocycle_length: int) -> float:
    """
    Renvoie le multiplicateur de volume pour la semaine donnée, pour un
    mésocycle BASE ou SPECIFIC (schéma build puis deload en dernière semaine).
    """
    if week_in_mesocycle == mesocycle_length:
        return DEFAULT_MESOCYCLE_PROGRESSION.get(4, 0.65)
    return DEFAULT_MESOCYCLE_PROGRESSION.get(week_in_mesocycle, 1.10)


# ---------------------------------------------------------------------------
# Progression TAPER : décroissance monotone dédiée, PAS un cycle build/deload
# ---------------------------------------------------------------------------
# Le taper n'a pas la même forme qu'un mésocycle BASE/SPECIFIC : pas de montée,
# juste une réduction progressive du volume à mesure qu'on approche la course.
# Courbes par défaut selon la durée du taper (1 à 3 semaines, cas les plus
# courants). Dernière valeur = semaine de course.

def _taper_multiplier(
    week_in_taper: int,
    total_taper_weeks: int,
    decay_curve: list[float] | None = None,
) -> float:
    """
    Renvoie le multiplicateur de volume pour une semaine de taper donnée.

    Args:
        week_in_taper: position dans le taper (1-indexed, 1 = la plus loin
            de la course, total_taper_weeks = semaine de course)
        total_taper_weeks: durée totale du taper
        decay_curve: courbe personnalisée (liste de multiplicateurs, longueur
            = total_taper_weeks). Si None, utilise DEFAULT_TAPER_DECAY.
    """
    curve = decay_curve or DEFAULT_TAPER_DECAY.get(total_taper_weeks)
    if curve is None:
        raise ValueError(
            f"Pas de courbe de taper par défaut pour {total_taper_weeks} semaines; "
            "fournis un decay_curve explicite."
        )
    if len(curve) != total_taper_weeks:
        raise ValueError("decay_curve doit avoir une longueur == total_taper_weeks")
    if week_in_taper < 1 or week_in_taper > total_taper_weeks:
        raise ValueError("week_in_taper hors bornes du taper")

    return curve[week_in_taper - 1]
