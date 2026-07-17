import pytest

from training_plan.config.loader import (
    ACWR_DANGER_THRESHOLD,
    DEFAULT_READINESS_THRESHOLDS,
    MONOTONY_DANGER_THRESHOLD,
)
from training_plan.domain.enums import Priority, ReadinessBand, SessionRole
from training_plan.domain.models import ReadinessSignals, SessionSlot
from training_plan.readiness.adjustment import adjust_session, adjust_week
from training_plan.readiness.classification import classify_readiness
from training_plan.generation.week_template import generate_week_template
from training_plan.domain.enums import Phase


# ---------------------------------------------------------------------------
# Non-régression : reproduit exactement les scénarios utilisés pour capturer
# la baseline de l'ancien module monolithique et vérifie l'égalité stricte.
# ---------------------------------------------------------------------------

def test_classify_readiness_matches_baseline(baseline):
    th = DEFAULT_READINESS_THRESHOLDS
    cases = {
        "score_at_critical_max": ReadinessSignals(score=th["critical_max"]),
        "score_just_above_critical_max": ReadinessSignals(score=th["critical_max"] + 1),
        "score_at_low_max": ReadinessSignals(score=th["low_max"]),
        "score_just_above_low_max": ReadinessSignals(score=th["low_max"] + 1),
        "score_at_high_min": ReadinessSignals(score=th["high_min"]),
        "score_just_below_high_min": ReadinessSignals(score=th["high_min"] - 1),
        "score_0": ReadinessSignals(score=0),
        "score_100": ReadinessSignals(score=100),
        "acwr_at_danger_threshold_high_score": ReadinessSignals(score=90, acwr=ACWR_DANGER_THRESHOLD),
        "acwr_just_below_danger_threshold_high_score": ReadinessSignals(score=90, acwr=ACWR_DANGER_THRESHOLD - 0.01),
        "acwr_danger_normal_score": ReadinessSignals(score=65, acwr=ACWR_DANGER_THRESHOLD),
        "monotony_at_danger_threshold_high_score": ReadinessSignals(score=90, monotony=MONOTONY_DANGER_THRESHOLD),
        "monotony_just_below_danger_threshold_high_score": ReadinessSignals(score=90, monotony=MONOTONY_DANGER_THRESHOLD - 0.01),
        "monotony_danger_but_normal_band_unaffected": ReadinessSignals(score=65, monotony=MONOTONY_DANGER_THRESHOLD),
        "acwr_and_monotony_both_danger_high_score": ReadinessSignals(score=95, acwr=1.8, monotony=2.5),
    }
    for key, signals in cases.items():
        assert classify_readiness(signals).value == baseline["classify_readiness"][key], key

    custom = classify_readiness(
        ReadinessSignals(score=45), thresholds={"critical_max": 20, "low_max": 44, "high_min": 70}
    )
    assert custom.value == baseline["classify_readiness"]["custom_thresholds"]


def test_adjust_session_matches_baseline(baseline):
    sample_slots = {
        "EF": SessionSlot(role=SessionRole.EF, day_position=1, priority=Priority.SOFT, duration_min=40, d_plus_target_m=0, intensity_zone="Z1", notes="ef notes"),
        "SEUIL": SessionSlot(role=SessionRole.SEUIL, day_position=2, priority=Priority.HARD, duration_min=50, d_plus_target_m=250, intensity_zone="SV1-SV2", notes="seuil notes"),
        "VMA": SessionSlot(role=SessionRole.VMA, day_position=3, priority=Priority.HARD, duration_min=45, d_plus_target_m=100, intensity_zone="VMA 100-110%", notes="vma notes"),
        "COTES": SessionSlot(role=SessionRole.COTES, day_position=4, priority=Priority.HARD, duration_min=35, d_plus_target_m=600, intensity_zone="cotes", notes="cotes notes"),
        "SL": SessionSlot(role=SessionRole.SL, day_position=6, priority=Priority.HARD, duration_min=150, d_plus_target_m=1400, intensity_zone="Z1-Z2", notes="sl notes"),
        "RENFO": SessionSlot(role=SessionRole.RENFO, day_position=5, priority=Priority.MODERATE, duration_min=25, d_plus_target_m=0, intensity_zone="", notes="renfo notes"),
        "RECUP": SessionSlot(role=SessionRole.RECUP, day_position=7, priority=Priority.SOFT, duration_min=15, d_plus_target_m=0, intensity_zone="Z1", notes="recup notes"),
    }
    for role_name, slot in sample_slots.items():
        for band in [ReadinessBand.CRITICAL, ReadinessBand.LOW, ReadinessBand.NORMAL, ReadinessBand.HIGH]:
            adjusted = adjust_session(slot, band)
            key = f"{role_name}_{band.value}"
            assert adjusted.as_dict() == baseline["adjust_session"][key], key


def test_adjust_week_critical_matches_baseline(baseline):
    week_slots = generate_week_template(
        phase=Phase.SPECIFIC, week_in_block=3, block_length=4,
        base_weekly_volume_min=360, base_weekly_d_plus_m=2500,
    )
    signals_critical = ReadinessSignals(score=22, tsb=-28, monotony=1.4, acwr=1.3)
    adjusted_week = adjust_week(week_slots, signals_critical)
    actual = [s.as_dict() for s in adjusted_week]
    assert actual == baseline["adjust_week_critical"]


# ---------------------------------------------------------------------------
# Cas limites explicites autour de chaque seuil
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("score,expected_band", [
    (30, ReadinessBand.CRITICAL),   # == critical_max
    (31, ReadinessBand.LOW),        # juste au-dessus de critical_max
    (50, ReadinessBand.LOW),        # == low_max
    (51, ReadinessBand.NORMAL),     # juste au-dessus de low_max
    (79, ReadinessBand.NORMAL),     # juste en dessous de high_min
    (80, ReadinessBand.HIGH),       # == high_min
])
def test_classify_readiness_score_thresholds(score, expected_band):
    assert classify_readiness(ReadinessSignals(score=score)) == expected_band


def test_classify_readiness_acwr_override_degrades_high_to_low():
    signals = ReadinessSignals(score=90, acwr=1.5)
    assert classify_readiness(signals) == ReadinessBand.LOW


def test_classify_readiness_acwr_just_below_threshold_no_override():
    signals = ReadinessSignals(score=90, acwr=1.49)
    assert classify_readiness(signals) == ReadinessBand.HIGH


def test_classify_readiness_monotony_override_degrades_high_to_normal():
    signals = ReadinessSignals(score=90, monotony=2.0)
    assert classify_readiness(signals) == ReadinessBand.NORMAL


def test_classify_readiness_monotony_override_does_not_affect_normal_band():
    signals = ReadinessSignals(score=65, monotony=2.0)
    assert classify_readiness(signals) == ReadinessBand.NORMAL


# ---------------------------------------------------------------------------
# adjust_session pour chaque role x chaque bande (comportement attendu)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", [SessionRole.SEUIL, SessionRole.VMA, SessionRole.COTES])
def test_adjust_session_hard_roles_critical_downgrades_to_recup(role):
    slot = SessionSlot(role=role, day_position=2, priority=Priority.HARD, duration_min=50, d_plus_target_m=200)
    adjusted = adjust_session(slot, ReadinessBand.CRITICAL)
    assert adjusted.role == SessionRole.RECUP
    assert adjusted.duration_min == pytest.approx(25.0)
    assert adjusted.d_plus_target_m == 0.0


@pytest.mark.parametrize("role", [SessionRole.SEUIL, SessionRole.VMA, SessionRole.COTES])
def test_adjust_session_hard_roles_low_reduces_by_60_percent(role):
    slot = SessionSlot(role=role, day_position=2, priority=Priority.HARD, duration_min=50, d_plus_target_m=200)
    adjusted = adjust_session(slot, ReadinessBand.LOW)
    assert adjusted.role == role
    assert adjusted.duration_min == pytest.approx(30.0)
    assert adjusted.d_plus_target_m == pytest.approx(120.0)


@pytest.mark.parametrize("role", [SessionRole.SEUIL, SessionRole.VMA, SessionRole.COTES])
@pytest.mark.parametrize("band", [ReadinessBand.NORMAL, ReadinessBand.HIGH])
def test_adjust_session_hard_roles_normal_high_unchanged(role, band):
    slot = SessionSlot(role=role, day_position=2, priority=Priority.HARD, duration_min=50, d_plus_target_m=200)
    adjusted = adjust_session(slot, band)
    assert adjusted == slot


def test_adjust_session_sl_critical_shortens_but_never_drops_entirely():
    slot = SessionSlot(role=SessionRole.SL, day_position=6, priority=Priority.HARD, duration_min=150, d_plus_target_m=1400)
    adjusted = adjust_session(slot, ReadinessBand.CRITICAL)
    assert adjusted.duration_min == pytest.approx(75.0)
    assert adjusted.duration_min > 0
    assert adjusted.d_plus_target_m == 0.0


@pytest.mark.parametrize("band", [ReadinessBand.LOW, ReadinessBand.NORMAL, ReadinessBand.HIGH])
def test_adjust_session_sl_protected_outside_critical(band):
    slot = SessionSlot(role=SessionRole.SL, day_position=6, priority=Priority.HARD, duration_min=150, d_plus_target_m=1400)
    adjusted = adjust_session(slot, band)
    assert adjusted == slot


def test_adjust_session_renfo_critical_downgrades_to_recup():
    slot = SessionSlot(role=SessionRole.RENFO, day_position=5, priority=Priority.MODERATE, duration_min=25)
    adjusted = adjust_session(slot, ReadinessBand.CRITICAL)
    assert adjusted.role == SessionRole.RECUP


@pytest.mark.parametrize("role", [SessionRole.EF, SessionRole.RECUP])
@pytest.mark.parametrize("band", [ReadinessBand.CRITICAL, ReadinessBand.LOW, ReadinessBand.NORMAL, ReadinessBand.HIGH])
def test_adjust_session_ef_recup_never_modified(role, band):
    slot = SessionSlot(role=role, day_position=1, priority=Priority.SOFT, duration_min=40)
    adjusted = adjust_session(slot, band)
    assert adjusted == slot
