import pytest

from training_plan.domain.enums import Phase
from training_plan.generation.week_template import generate_week_template


# ---------------------------------------------------------------------------
# Non-régression : reproduit exactement les scénarios utilisés pour capturer
# la baseline de l'ancien module monolithique et vérifie l'égalité stricte.
# ---------------------------------------------------------------------------

def _build_week_template_cases() -> dict:
    cases = {}
    for phase in [Phase.BASE, Phase.SPECIFIC, Phase.TAPER]:
        block_length = 4 if phase != Phase.TAPER else 3
        for week_in_block in range(1, block_length + 1):
            key = f"{phase.value}_w{week_in_block}_of_{block_length}"
            slots = generate_week_template(
                phase=phase,
                week_in_block=week_in_block,
                block_length=block_length,
                base_weekly_volume_min=360,
                base_weekly_d_plus_m=2500,
            )
            cases[key] = [s.as_dict() for s in slots]

    for phase in [Phase.BASE, Phase.SPECIFIC, Phase.TAPER]:
        block_length = 4 if phase != Phase.TAPER else 2
        key = f"{phase.value}_w1_of_{block_length}_no_dplus"
        slots = generate_week_template(
            phase=phase,
            week_in_block=1,
            block_length=block_length,
            base_weekly_volume_min=300,
        )
        cases[key] = [s.as_dict() for s in slots]

    slots = generate_week_template(
        phase=Phase.TAPER,
        week_in_block=2,
        block_length=3,
        base_weekly_volume_min=400,
        base_weekly_d_plus_m=3000,
        decay_curve=[0.9, 0.7, 0.4],
    )
    cases["TAPER_custom_decay_w2_of_3"] = [s.as_dict() for s in slots]
    return cases


def test_week_template_matches_baseline(baseline):
    actual = _build_week_template_cases()
    assert actual == baseline["week_template"]


# ---------------------------------------------------------------------------
# Tests structurels ciblés par phase
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("phase,block_length", [
    (Phase.BASE, 4),
    (Phase.SPECIFIC, 4),
    (Phase.TAPER, 2),
])
def test_generate_week_template_sorted_by_day_position(phase, block_length):
    slots = generate_week_template(
        phase=phase,
        week_in_block=1,
        block_length=block_length,
        base_weekly_volume_min=360,
        base_weekly_d_plus_m=2500,
    )
    day_positions = [s.day_position for s in slots]
    assert day_positions == sorted(day_positions)


def test_generate_week_template_base_deload_week_reduces_volume():
    week1 = generate_week_template(Phase.BASE, 1, 4, base_weekly_volume_min=360)
    week4_deload = generate_week_template(Phase.BASE, 4, 4, base_weekly_volume_min=360)
    assert sum(s.duration_min for s in week4_deload) < sum(s.duration_min for s in week1)


def test_generate_week_template_specific_has_back_to_back_sl():
    slots = generate_week_template(Phase.SPECIFIC, 1, 4, base_weekly_volume_min=360, base_weekly_d_plus_m=2500)
    sl_slots = [s for s in slots if s.role.value == "SL"]
    assert len(sl_slots) == 2
    assert {s.day_position for s in sl_slots} == {6, 7}


def test_generate_week_template_taper_last_week_is_smallest():
    volumes = [
        sum(s.duration_min for s in generate_week_template(Phase.TAPER, w, 3, base_weekly_volume_min=400))
        for w in range(1, 4)
    ]
    assert volumes[0] > volumes[1] > volumes[2]


def test_generate_week_template_invalid_phase_raises():
    with pytest.raises(ValueError):
        generate_week_template("NOT_A_PHASE", 1, 4, base_weekly_volume_min=360)


def test_generate_week_template_week_out_of_bounds_raises():
    with pytest.raises(ValueError):
        generate_week_template(Phase.BASE, 5, 4, base_weekly_volume_min=360)
