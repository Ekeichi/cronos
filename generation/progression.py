"""Multiplicateurs de volume hebdo : progression mésocycle et décroissance taper."""

from config.loader import DEFAULT_TAPER_DECAY, MESOCYCLE_PROGRESSION_DEFAULT, MESOCYCLE_PROGRESSION_FALLBACK

# ---------------------------------------------------------------------------
# Progression mésocycle (schéma 3:1 build/deload par défaut)
# ---------------------------------------------------------------------------
# Le mapping semaine -> multiplicateur et le fallback intermédiaire sont
# définis dans config/mesocycle_progression.yaml (chargés via config.loader).


def _volume_multiplier(week_in_mesocycle: int, mesocycle_length: int) -> float:
    """
    Renvoie le multiplicateur de volume pour la semaine donnée, pour un
    mésocycle BASE ou SPECIFIC (schéma build puis deload en dernière semaine).
    """
    if week_in_mesocycle == mesocycle_length:
        return MESOCYCLE_PROGRESSION_DEFAULT[4]
    return MESOCYCLE_PROGRESSION_DEFAULT.get(week_in_mesocycle, MESOCYCLE_PROGRESSION_FALLBACK)


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
