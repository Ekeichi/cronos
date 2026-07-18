from datetime import date, timedelta

import pytest

from config.loader import EXPECTED_RPE_BY_ROLE, RPE_DEVIATION_CRITICAL_THRESHOLD
from domain.enums import Phase, ReadinessBand, SessionRole
from domain.models import AthletePlanContext, MacrocycleBlock, ReadinessSignals, SessionFeedback
from generation.macrocycle import generate_macrocycle_plan
from orchestration.daily_run import record_session_feedback, run_daily_adjustment
from persistence.event_log import read_decisions
from readiness.classification import classify_readiness


def _make_context(athlete_id: str = "athlete-1", plan_start_date: date = date(2026, 7, 1)) -> AthletePlanContext:
    blocks = [
        MacrocycleBlock(phase=Phase.BASE, n_weeks=4),
        MacrocycleBlock(phase=Phase.SPECIFIC, n_weeks=4),
        MacrocycleBlock(phase=Phase.TAPER, n_weeks=2),
    ]
    macrocycle_plan = generate_macrocycle_plan(blocks=blocks, base_weekly_volume_min=360, base_weekly_d_plus_m=2500)
    return AthletePlanContext(
        athlete_id=athlete_id,
        blocks=blocks,
        macrocycle_plan=macrocycle_plan,
        plan_start_date=plan_start_date,
    )


def _filepaths(tmp_path):
    return str(tmp_path / "decisions.jsonl"), str(tmp_path / "feedback.jsonl")


# ---------------------------------------------------------------------------
# Jour 1 : pas d'historique, previous_band=None, décision loggée
# ---------------------------------------------------------------------------

def test_run_daily_adjustment_day_one_has_no_previous_band_and_logs_decision(tmp_path):
    context = _make_context()
    decisions_filepath, feedback_filepath = _filepaths(tmp_path)
    today = context.plan_start_date  # jour 1 du plan

    signals = ReadinessSignals(score=70)
    adjusted_slots = run_daily_adjustment(
        context, today, signals,
        decisions_filepath=decisions_filepath, feedback_filepath=feedback_filepath,
    )

    expected_planned = [s for s in context.macrocycle_plan[1] if s.day_position == 1]
    assert len(expected_planned) == 1  # BASE day_position=1 : un seul slot (EF)
    assert len(adjusted_slots) == 1

    rows = read_decisions(filepath=decisions_filepath)
    assert len(rows) == 1
    assert rows[0]["athlete_id"] == "athlete-1"
    assert rows[0]["event_date"] == today.isoformat()
    assert rows[0]["previous_band"] is None
    assert rows[0]["phase"] == "BASE"
    assert rows[0]["week_in_block"] == 1
    assert rows[0]["block_length"] == 4
    assert rows[0]["planned_slot"]["day_position"] == 1


# ---------------------------------------------------------------------------
# Hystérésis bout en bout : le second appel lit bien le resulting_band du
# premier comme previous_band.
# ---------------------------------------------------------------------------

def test_run_daily_adjustment_propagates_previous_band_across_days(tmp_path):
    context = _make_context()
    decisions_filepath, feedback_filepath = _filepaths(tmp_path)

    day1 = context.plan_start_date
    day2 = day1 + timedelta(days=1)

    run_daily_adjustment(
        context, day1, ReadinessSignals(score=49),  # <= low_max(50) -> LOW
        decisions_filepath=decisions_filepath, feedback_filepath=feedback_filepath,
    )
    rows_after_day1 = read_decisions(filepath=decisions_filepath)
    assert rows_after_day1[0]["resulting_band"] == "LOW"

    run_daily_adjustment(
        context, day2, ReadinessSignals(score=51),  # > low_max mais <= low_max + marge(5)
        decisions_filepath=decisions_filepath, feedback_filepath=feedback_filepath,
    )
    rows = read_decisions(filepath=decisions_filepath)
    day2_rows = [r for r in rows if r["event_date"] == day2.isoformat()]
    assert len(day2_rows) == 1
    assert day2_rows[0]["previous_band"] == "LOW"
    assert day2_rows[0]["resulting_band"] == "LOW"  # hystérésis : reste LOW malgré le score

    # preuve que c'est bien l'hystérésis (via previous_band) qui agit : le
    # même score, sans previous_band, classe en NORMAL au niveau unitaire.
    assert classify_readiness(ReadinessSignals(score=51)) == ReadinessBand.NORMAL


# ---------------------------------------------------------------------------
# Override RPE bout en bout, via record_session_feedback
# ---------------------------------------------------------------------------

def test_record_session_feedback_influences_next_run_within_lookback(tmp_path):
    context = _make_context()
    decisions_filepath, feedback_filepath = _filepaths(tmp_path)

    day1 = context.plan_start_date
    day2 = day1 + timedelta(days=1)

    catastrophic_feedback = SessionFeedback(
        role=SessionRole.SEUIL,
        rpe=EXPECTED_RPE_BY_ROLE["SEUIL"] + RPE_DEVIATION_CRITICAL_THRESHOLD,
    )
    record_session_feedback(context.athlete_id, day1, catastrophic_feedback, feedback_filepath=feedback_filepath)

    # bon score composite day2, mais le RPE catastrophique de day1 (dans la
    # fenêtre de lookback par défaut de 2 jours) doit forcer CRITICAL.
    run_daily_adjustment(
        context, day2, ReadinessSignals(score=90),
        decisions_filepath=decisions_filepath, feedback_filepath=feedback_filepath,
    )
    rows = read_decisions(filepath=decisions_filepath)
    assert all(r["resulting_band"] == "CRITICAL" for r in rows)


def test_feedback_outside_lookback_window_is_ignored(tmp_path):
    context = _make_context()
    decisions_filepath, feedback_filepath = _filepaths(tmp_path)

    day1 = context.plan_start_date
    day_far = day1 + timedelta(days=5)  # hors de la fenêtre de lookback par défaut (2 jours)

    catastrophic_feedback = SessionFeedback(
        role=SessionRole.SEUIL,
        rpe=EXPECTED_RPE_BY_ROLE["SEUIL"] + RPE_DEVIATION_CRITICAL_THRESHOLD,
    )
    record_session_feedback(context.athlete_id, day1, catastrophic_feedback, feedback_filepath=feedback_filepath)

    run_daily_adjustment(
        context, day_far, ReadinessSignals(score=90),
        decisions_filepath=decisions_filepath, feedback_filepath=feedback_filepath,
    )
    rows = read_decisions(filepath=decisions_filepath)
    day_far_rows = [r for r in rows if r["event_date"] == day_far.isoformat()]
    assert len(day_far_rows) >= 1
    assert all(r["resulting_band"] == "HIGH" for r in day_far_rows)


# ---------------------------------------------------------------------------
# today hors des bornes du plan
# ---------------------------------------------------------------------------

def test_run_daily_adjustment_before_plan_start_raises(tmp_path):
    context = _make_context()
    decisions_filepath, feedback_filepath = _filepaths(tmp_path)
    before_start = context.plan_start_date - timedelta(days=1)

    with pytest.raises(ValueError):
        run_daily_adjustment(
            context, before_start, ReadinessSignals(score=70),
            decisions_filepath=decisions_filepath, feedback_filepath=feedback_filepath,
        )


def test_run_daily_adjustment_after_macrocycle_end_raises(tmp_path):
    context = _make_context()
    decisions_filepath, feedback_filepath = _filepaths(tmp_path)
    total_weeks = sum(b.n_weeks for b in context.blocks)  # 4 + 4 + 2 = 10
    after_end = context.plan_start_date + timedelta(days=total_weeks * 7)  # premier jour hors macrocycle

    with pytest.raises(ValueError):
        run_daily_adjustment(
            context, after_end, ReadinessSignals(score=70),
            decisions_filepath=decisions_filepath, feedback_filepath=feedback_filepath,
        )
