"""Macrocycle : assemblage des blocs (mésocycles BASE/SPECIFIC + bloc TAPER)."""

from training_plan.domain.enums import Phase
from training_plan.domain.models import MacrocycleBlock, SessionSlot
from training_plan.generation.week_template import generate_week_template


def generate_macrocycle_plan(
    blocks: list[MacrocycleBlock],
    base_weekly_volume_min: float,
    base_weekly_d_plus_m: float = 0.0,
) -> dict[int, list[SessionSlot]]:
    """
    Assemble une séquence de blocs (mésocycles + taper) en un planning complet.

    Pour les blocs BASE/SPECIFIC, la référence de volume est toujours
    base_weekly_volume_min (le multiplicateur build/deload s'applique dessus).
    Pour un bloc TAPER, la référence n'est PAS base_weekly_volume_min mais le
    volume réel de la dernière semaine générée juste avant le taper (le pic
    du mésocycle précédent) — la décroissance part de ce qui a été réellement
    couru, pas d'une valeur théorique.

    Renvoie un dict {numéro de semaine global (1-indexed) -> semaine générée}.
    """
    plan: dict[int, list[SessionSlot]] = {}
    global_week = 1
    last_week_volume = base_weekly_volume_min
    last_week_d_plus = base_weekly_d_plus_m

    for block in blocks:
        if block.phase == Phase.TAPER:
            # référence figée une fois pour tout le bloc taper = pic pré-taper
            peak_volume = last_week_volume
            peak_d_plus = last_week_d_plus
            for week_in_block in range(1, block.n_weeks + 1):
                slots = generate_week_template(
                    phase=block.phase,
                    week_in_block=week_in_block,
                    block_length=block.n_weeks,
                    base_weekly_volume_min=peak_volume,
                    base_weekly_d_plus_m=peak_d_plus,
                    decay_curve=block.decay_curve,
                )
                plan[global_week] = slots
                global_week += 1
        else:
            for week_in_block in range(1, block.n_weeks + 1):
                slots = generate_week_template(
                    phase=block.phase,
                    week_in_block=week_in_block,
                    block_length=block.n_weeks,
                    base_weekly_volume_min=base_weekly_volume_min,
                    base_weekly_d_plus_m=base_weekly_d_plus_m,
                )
                plan[global_week] = slots
                # on garde trace de la semaine réellement générée, pour servir
                # de référence si le bloc suivant est un TAPER
                last_week_volume = sum(s.duration_min for s in slots)
                last_week_d_plus = sum(s.d_plus_target_m for s in slots)
                global_week += 1

    return plan
