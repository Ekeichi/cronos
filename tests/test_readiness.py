import pytest

from config.loader import (
    ACWR_DANGER_THRESHOLD,
    CRITICAL_EXIT_MARGIN,
    DEFAULT_READINESS_THRESHOLDS,
    EXPECTED_RPE_BY_ROLE,
    LOW_EXIT_MARGIN,
    MONOTONY_DANGER_THRESHOLD,
    RPE_DEVIATION_CRITICAL_THRESHOLD,
    RPE_DEVIATION_LOW_THRESHOLD,
)
from domain.enums import Priority, ReadinessBand, SessionRole
from domain.models import ReadinessSignals, SessionFeedback, SessionSlot
from readiness.adjustment import adjust_session, adjust_week
from readiness.classification import classify_readiness
from readiness.feedback import rpe_deviation
from generation.week_template import generate_week_template
from domain.enums import Phase


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
    adjusted_week, resulting_band = adjust_week(week_slots, signals_critical)
    actual = [s.as_dict() for s in adjusted_week]
    assert actual == baseline["adjust_week_critical"]
    assert resulting_band == ReadinessBand.CRITICAL


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


# ---------------------------------------------------------------------------
# Hystérésis asymétrique (previous_band)
# ---------------------------------------------------------------------------

def test_hysteresis_low_to_normal_blocked_without_exceeding_margin():
    th = DEFAULT_READINESS_THRESHOLDS
    signals = ReadinessSignals(score=th["low_max"] + 1)  # 51 : NORMAL sans hystérésis
    assert classify_readiness(signals, previous_band=ReadinessBand.LOW) == ReadinessBand.LOW
    assert classify_readiness(signals, previous_band=None) == ReadinessBand.NORMAL
    assert classify_readiness(signals, previous_band=ReadinessBand.NORMAL) == ReadinessBand.NORMAL


def test_hysteresis_low_to_normal_boundary_at_margin():
    th = DEFAULT_READINESS_THRESHOLDS
    at_margin = ReadinessSignals(score=th["low_max"] + LOW_EXIT_MARGIN)       # 55 : reste LOW
    past_margin = ReadinessSignals(score=th["low_max"] + LOW_EXIT_MARGIN + 1)  # 56 : repasse NORMAL
    assert classify_readiness(at_margin, previous_band=ReadinessBand.LOW) == ReadinessBand.LOW
    assert classify_readiness(past_margin, previous_band=ReadinessBand.LOW) == ReadinessBand.NORMAL


def test_hysteresis_critical_to_low_blocked_without_exceeding_margin():
    th = DEFAULT_READINESS_THRESHOLDS
    signals = ReadinessSignals(score=th["critical_max"] + 1)  # 31 : LOW sans hystérésis
    assert classify_readiness(signals, previous_band=ReadinessBand.CRITICAL) == ReadinessBand.CRITICAL
    assert classify_readiness(signals, previous_band=None) == ReadinessBand.LOW


def test_hysteresis_critical_to_low_boundary_at_margin():
    th = DEFAULT_READINESS_THRESHOLDS
    at_margin = ReadinessSignals(score=th["critical_max"] + CRITICAL_EXIT_MARGIN)       # 35 : reste CRITICAL
    past_margin = ReadinessSignals(score=th["critical_max"] + CRITICAL_EXIT_MARGIN + 1)  # 36 : passe LOW
    assert classify_readiness(at_margin, previous_band=ReadinessBand.CRITICAL) == ReadinessBand.CRITICAL
    assert classify_readiness(past_margin, previous_band=ReadinessBand.CRITICAL) == ReadinessBand.LOW


def test_hysteresis_degradation_is_immediate_no_margin_on_entry():
    # Dégrader reste immédiat : aucune marge ne protège l'ENTRÉE dans une
    # bande dégradée, même si la bande précédente était haute.
    critical_signals = ReadinessSignals(score=10)
    assert classify_readiness(critical_signals, previous_band=ReadinessBand.HIGH) == ReadinessBand.CRITICAL
    assert classify_readiness(critical_signals, previous_band=ReadinessBand.NORMAL) == ReadinessBand.CRITICAL

    low_signals = ReadinessSignals(score=40)
    assert classify_readiness(low_signals, previous_band=ReadinessBand.HIGH) == ReadinessBand.LOW
    assert classify_readiness(low_signals, previous_band=ReadinessBand.NORMAL) == ReadinessBand.LOW


def test_hysteresis_sequence_stabilizes_band_vs_oscillation_without_it():
    scores = [51, 49, 52, 48, 49, 52, 56]

    with_hysteresis = []
    previous_band = None
    for score in scores:
        band = classify_readiness(ReadinessSignals(score=score), previous_band=previous_band)
        with_hysteresis.append(band)
        previous_band = band

    without_hysteresis = [
        classify_readiness(ReadinessSignals(score=score), previous_band=None) for score in scores
    ]

    assert with_hysteresis == [
        ReadinessBand.NORMAL,
        ReadinessBand.LOW,
        ReadinessBand.LOW,
        ReadinessBand.LOW,
        ReadinessBand.LOW,
        ReadinessBand.LOW,
        ReadinessBand.NORMAL,
    ]
    assert without_hysteresis == [
        ReadinessBand.NORMAL,
        ReadinessBand.LOW,
        ReadinessBand.NORMAL,
        ReadinessBand.LOW,
        ReadinessBand.LOW,
        ReadinessBand.NORMAL,
        ReadinessBand.NORMAL,
    ]
    # avec hystérésis : une fois dégradée en LOW, la bande ne remonte qu'au
    # dernier score (56, > low_max + marge) — pas d'oscillation entretemps.
    assert with_hysteresis[1:6] == [ReadinessBand.LOW] * 5
    # sans hystérésis : la bande oscille LOW <-> NORMAL au fil des scores.
    assert without_hysteresis != with_hysteresis


# ---------------------------------------------------------------------------
# Override RPE post-séance
# ---------------------------------------------------------------------------

def test_rpe_deviation_per_role():
    for role_name, expected in EXPECTED_RPE_BY_ROLE.items():
        feedback = SessionFeedback(role=SessionRole(role_name), rpe=expected + 2)
        assert rpe_deviation(feedback) == pytest.approx(2.0)

        feedback_negative = SessionFeedback(role=SessionRole(role_name), rpe=max(expected - 1, 0))
        assert rpe_deviation(feedback_negative) == pytest.approx(max(expected - 1, 0) - expected)


def test_rpe_override_forces_low_from_normal():
    feedback = SessionFeedback(role=SessionRole.SEUIL, rpe=EXPECTED_RPE_BY_ROLE["SEUIL"] + RPE_DEVIATION_LOW_THRESHOLD)
    signals = ReadinessSignals(score=65)  # NORMAL sur le seul score composite
    assert classify_readiness(signals) == ReadinessBand.NORMAL
    assert classify_readiness(signals, last_session_feedback=feedback) == ReadinessBand.LOW


def test_rpe_override_forces_low_from_high():
    feedback = SessionFeedback(role=SessionRole.VMA, rpe=EXPECTED_RPE_BY_ROLE["VMA"] + RPE_DEVIATION_LOW_THRESHOLD)
    signals = ReadinessSignals(score=90)  # HIGH sur le seul score composite
    assert classify_readiness(signals) == ReadinessBand.HIGH
    assert classify_readiness(signals, last_session_feedback=feedback) == ReadinessBand.LOW


def test_rpe_override_forces_critical_even_with_good_score():
    feedback = SessionFeedback(role=SessionRole.COTES, rpe=EXPECTED_RPE_BY_ROLE["COTES"] + RPE_DEVIATION_CRITICAL_THRESHOLD)
    signals = ReadinessSignals(score=90)  # bon score composite
    assert classify_readiness(signals, last_session_feedback=feedback) == ReadinessBand.CRITICAL


def test_rpe_low_deviation_does_not_change_band():
    feedback = SessionFeedback(role=SessionRole.SEUIL, rpe=EXPECTED_RPE_BY_ROLE["SEUIL"] + RPE_DEVIATION_LOW_THRESHOLD - 1)
    signals = ReadinessSignals(score=90)
    assert classify_readiness(signals, last_session_feedback=feedback) == ReadinessBand.HIGH


def test_rpe_negative_deviation_does_not_change_band():
    feedback = SessionFeedback(role=SessionRole.SEUIL, rpe=max(EXPECTED_RPE_BY_ROLE["SEUIL"] - 3, 0))
    signals = ReadinessSignals(score=90)
    assert classify_readiness(signals, last_session_feedback=feedback) == ReadinessBand.HIGH


def test_rpe_override_never_upgrades_a_critical_band():
    # Asymétrie safety-first : un très bon RPE (séance ressentie plus facile
    # que prévu) ne doit jamais faire remonter une bande CRITICAL.
    feedback = SessionFeedback(role=SessionRole.RECUP, rpe=0)
    signals = ReadinessSignals(score=10)  # CRITICAL sur le score composite
    assert classify_readiness(signals, last_session_feedback=feedback) == ReadinessBand.CRITICAL


def test_rpe_override_never_upgrades_a_low_band():
    feedback = SessionFeedback(role=SessionRole.RECUP, rpe=0)
    signals = ReadinessSignals(score=40)  # LOW sur le score composite
    assert classify_readiness(signals, last_session_feedback=feedback) == ReadinessBand.LOW


def test_combined_hysteresis_acwr_and_rpe_order_of_application():
    # Score seul (avec hystérésis, ici sans effet car le score dépasse
    # largement la marge) -> HIGH. Garde-fou ACWR ensuite -> LOW. Override
    # RPE en tout dernier -> CRITICAL. Le résultat final ne peut être
    # CRITICAL que si les trois étapes s'enchaînent dans cet ordre.
    signals = ReadinessSignals(score=90, acwr=ACWR_DANGER_THRESHOLD)
    feedback = SessionFeedback(role=SessionRole.VMA, rpe=EXPECTED_RPE_BY_ROLE["VMA"] + RPE_DEVIATION_CRITICAL_THRESHOLD)

    # étape 1 seule (hystérésis, no-op ici) : HIGH
    assert classify_readiness(ReadinessSignals(score=90), previous_band=ReadinessBand.LOW) == ReadinessBand.HIGH
    # étape 1+2 (garde-fou ACWR) : LOW
    assert classify_readiness(signals, previous_band=ReadinessBand.LOW) == ReadinessBand.LOW
    # étape 1+2+3 (override RPE) : CRITICAL
    assert classify_readiness(signals, previous_band=ReadinessBand.LOW, last_session_feedback=feedback) == ReadinessBand.CRITICAL


# ---------------------------------------------------------------------------
# adjust_week : nouveaux paramètres, valeur de retour (slots, bande)
# ---------------------------------------------------------------------------

def test_adjust_week_returns_slots_and_resulting_band():
    week_slots = generate_week_template(
        phase=Phase.SPECIFIC, week_in_block=1, block_length=4,
        base_weekly_volume_min=360, base_weekly_d_plus_m=2500,
    )
    signals = ReadinessSignals(score=90)
    adjusted_slots, band = adjust_week(week_slots, signals)
    assert band == ReadinessBand.HIGH
    assert adjusted_slots == [adjust_session(slot, band) for slot in week_slots]


def test_adjust_week_propagates_previous_band_and_feedback():
    week_slots = generate_week_template(
        phase=Phase.SPECIFIC, week_in_block=1, block_length=4,
        base_weekly_volume_min=360, base_weekly_d_plus_m=2500,
    )
    signals = ReadinessSignals(score=51)  # NORMAL sans hystérésis
    _, band_without_hysteresis = adjust_week(week_slots, signals)
    _, band_with_hysteresis = adjust_week(week_slots, signals, previous_band=ReadinessBand.LOW)
    assert band_without_hysteresis == ReadinessBand.NORMAL
    assert band_with_hysteresis == ReadinessBand.LOW

    feedback = SessionFeedback(role=SessionRole.SEUIL, rpe=EXPECTED_RPE_BY_ROLE["SEUIL"] + RPE_DEVIATION_CRITICAL_THRESHOLD)
    _, band_with_rpe_override = adjust_week(week_slots, signals, last_session_feedback=feedback)
    assert band_with_rpe_override == ReadinessBand.CRITICAL
