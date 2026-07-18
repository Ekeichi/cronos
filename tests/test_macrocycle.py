import pytest

from domain.enums import Phase
from domain.models import MacrocycleBlock
from generation.macrocycle import generate_macrocycle_plan, resolve_block_position


# ---------------------------------------------------------------------------
# Non-régression : reproduit exactement les scénarios utilisés pour capturer
# la baseline de l'ancien module monolithique et vérifie l'égalité stricte.
# ---------------------------------------------------------------------------

def test_macrocycle_plan_matches_baseline(baseline):
    blocks = [
        MacrocycleBlock(phase=Phase.BASE, n_weeks=4),
        MacrocycleBlock(phase=Phase.SPECIFIC, n_weeks=4),
        MacrocycleBlock(phase=Phase.SPECIFIC, n_weeks=2),
        MacrocycleBlock(phase=Phase.TAPER, n_weeks=2),
    ]
    plan = generate_macrocycle_plan(blocks=blocks, base_weekly_volume_min=360, base_weekly_d_plus_m=2500)
    actual = {str(week_num): [s.as_dict() for s in slots] for week_num, slots in plan.items()}
    assert actual == baseline["macrocycle_plan"]


def test_macrocycle_plan_taper1_matches_baseline(baseline):
    blocks = [
        MacrocycleBlock(phase=Phase.BASE, n_weeks=3),
        MacrocycleBlock(phase=Phase.TAPER, n_weeks=1),
    ]
    plan = generate_macrocycle_plan(blocks=blocks, base_weekly_volume_min=300, base_weekly_d_plus_m=2000)
    actual = {str(week_num): [s.as_dict() for s in slots] for week_num, slots in plan.items()}
    assert actual == baseline["macrocycle_plan_taper1"]


def test_macrocycle_plan_taper3_matches_baseline(baseline):
    blocks = [
        MacrocycleBlock(phase=Phase.SPECIFIC, n_weeks=4),
        MacrocycleBlock(phase=Phase.TAPER, n_weeks=3),
    ]
    plan = generate_macrocycle_plan(blocks=blocks, base_weekly_volume_min=420, base_weekly_d_plus_m=3200)
    actual = {str(week_num): [s.as_dict() for s in slots] for week_num, slots in plan.items()}
    assert actual == baseline["macrocycle_plan_taper3"]


# ---------------------------------------------------------------------------
# Comportement structurel explicitement attendu : le taper part du pic réel
# de la dernière semaine générée avant lui, pas d'une valeur théorique.
# ---------------------------------------------------------------------------

def test_taper_starts_from_actual_peak_of_previous_block():
    blocks = [
        MacrocycleBlock(phase=Phase.SPECIFIC, n_weeks=4),
        MacrocycleBlock(phase=Phase.TAPER, n_weeks=2),
    ]
    plan = generate_macrocycle_plan(blocks=blocks, base_weekly_volume_min=360, base_weekly_d_plus_m=2500)

    peak_week = plan[4]  # dernière semaine SPECIFIC = semaine deload du mésocycle, generee juste avant le taper
    peak_volume = sum(s.duration_min for s in peak_week)
    peak_d_plus = sum(s.d_plus_target_m for s in peak_week)

    taper_week1 = plan[5]
    # semaine 1 de taper 2 semaines -> decay_curve par defaut [0.80, 0.55]
    expected_volume = peak_volume * 0.80
    expected_d_plus = peak_d_plus * 0.80

    assert sum(s.duration_min for s in taper_week1) == pytest.approx(expected_volume)
    assert sum(s.d_plus_target_m for s in taper_week1) == pytest.approx(expected_d_plus, abs=1.0)


def test_taper_does_not_use_theoretical_base_volume():
    # base_weekly_volume_min sert de reference pour BASE/SPECIFIC mais PAS pour
    # le taper : si on force un pic tres different de base_weekly_volume_min,
    # le taper doit suivre le pic reel, pas la base theorique.
    blocks_short = [
        MacrocycleBlock(phase=Phase.BASE, n_weeks=1),  # semaine unique = deload (0.65x)
        MacrocycleBlock(phase=Phase.TAPER, n_weeks=1),
    ]
    plan = generate_macrocycle_plan(blocks=blocks_short, base_weekly_volume_min=360)
    peak_volume = sum(s.duration_min for s in plan[1])
    theoretical_volume_if_using_base = 360 * 0.55  # decay 1 semaine

    taper_volume = sum(s.duration_min for s in plan[2])
    assert taper_volume == pytest.approx(peak_volume * 0.55)
    assert taper_volume != pytest.approx(theoretical_volume_if_using_base)


# ---------------------------------------------------------------------------
# resolve_block_position : cohérence avec generate_macrocycle_plan
# ---------------------------------------------------------------------------

def test_resolve_block_position_matches_blocks_used_by_generate_macrocycle_plan():
    blocks = [
        MacrocycleBlock(phase=Phase.BASE, n_weeks=4),
        MacrocycleBlock(phase=Phase.SPECIFIC, n_weeks=4),
        MacrocycleBlock(phase=Phase.SPECIFIC, n_weeks=2),
        MacrocycleBlock(phase=Phase.TAPER, n_weeks=2),
    ]
    plan = generate_macrocycle_plan(blocks=blocks, base_weekly_volume_min=360, base_weekly_d_plus_m=2500)

    global_week = 1
    for block in blocks:
        for week_in_block in range(1, block.n_weeks + 1):
            phase, resolved_week_in_block, resolved_block_length = resolve_block_position(blocks, global_week)
            assert phase == block.phase, global_week
            assert resolved_week_in_block == week_in_block, global_week
            assert resolved_block_length == block.n_weeks, global_week
            assert global_week in plan
            global_week += 1

    total_weeks = sum(b.n_weeks for b in blocks)
    assert set(plan.keys()) == set(range(1, total_weeks + 1))


def test_resolve_block_position_out_of_bounds_raises():
    blocks = [MacrocycleBlock(phase=Phase.BASE, n_weeks=4), MacrocycleBlock(phase=Phase.TAPER, n_weeks=2)]
    total_weeks = sum(b.n_weeks for b in blocks)

    with pytest.raises(ValueError):
        resolve_block_position(blocks, 0)
    with pytest.raises(ValueError):
        resolve_block_position(blocks, total_weeks + 1)
