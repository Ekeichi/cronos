import json

from config.loader import CURRENT_POLICY_VERSION
from domain.enums import Phase, Priority, ReadinessBand, SessionRole
from domain.events import DecisionEvent, FeedbackEvent
from domain.models import ReadinessSignals, SessionFeedback, SessionSlot
from persistence.event_log import log_decision, log_feedback, read_decisions, read_feedback


def _make_decision_event(**overrides) -> DecisionEvent:
    planned_slot = SessionSlot(
        role=SessionRole.SEUIL, day_position=2, priority=Priority.HARD,
        duration_min=50, d_plus_target_m=250, intensity_zone="SV1-SV2", notes="seuil planifié",
    )
    adjusted_slot = SessionSlot(
        role=SessionRole.RECUP, day_position=2, priority=Priority.SOFT,
        duration_min=25, d_plus_target_m=0.0, intensity_zone="Z1",
        notes="[readiness] remplacé (repos/récup) — séance SEUIL initialement prévue",
    )
    defaults = dict(
        athlete_id="athlete-1",
        event_date="2026-07-18",
        phase=Phase.SPECIFIC,
        week_in_block=3,
        block_length=4,
        signals=ReadinessSignals(score=22, tsb=-28.4, monotony=1.42, acwr=1.31),
        previous_band=ReadinessBand.LOW,
        resulting_band=ReadinessBand.CRITICAL,
        planned_slot=planned_slot,
        adjusted_slot=adjusted_slot,
        policy_version=CURRENT_POLICY_VERSION,
        raw_signals=None,
    )
    defaults.update(overrides)
    return DecisionEvent(**defaults)


def _make_feedback_event(**overrides) -> FeedbackEvent:
    defaults = dict(
        athlete_id="athlete-1",
        event_date="2026-07-19",
        feedback=SessionFeedback(role=SessionRole.SEUIL, rpe=8.5, actual_duration_min=48.0, completed_as_planned=True, notes="dur mais fait"),
        policy_version=CURRENT_POLICY_VERSION,
    )
    defaults.update(overrides)
    return FeedbackEvent(**defaults)


# ---------------------------------------------------------------------------
# Round-trip log -> read
# ---------------------------------------------------------------------------

def test_log_decision_then_read_decisions_round_trips(tmp_path):
    filepath = str(tmp_path / "decisions.jsonl")
    event = _make_decision_event()

    log_decision(event, filepath=filepath)
    rows = read_decisions(filepath=filepath)

    assert rows == [event.as_dict()]


def test_log_feedback_then_read_feedback_round_trips(tmp_path):
    filepath = str(tmp_path / "feedback.jsonl")
    event = _make_feedback_event()

    log_feedback(event, filepath=filepath)
    rows = read_feedback(filepath=filepath)

    assert rows == [event.as_dict()]


# ---------------------------------------------------------------------------
# Append, pas overwrite
# ---------------------------------------------------------------------------

def test_log_decision_appends_successive_calls_as_separate_lines(tmp_path):
    filepath = str(tmp_path / "decisions.jsonl")
    event1 = _make_decision_event(event_date="2026-07-18")
    event2 = _make_decision_event(event_date="2026-07-19", resulting_band=ReadinessBand.NORMAL)

    log_decision(event1, filepath=filepath)
    log_decision(event2, filepath=filepath)

    rows = read_decisions(filepath=filepath)
    assert len(rows) == 2
    assert rows[0] == event1.as_dict()
    assert rows[1] == event2.as_dict()

    with open(filepath, "r", encoding="utf-8") as f:
        lines = [line for line in f if line.strip()]
    assert len(lines) == 2


def test_log_feedback_appends_successive_calls_as_separate_lines(tmp_path):
    filepath = str(tmp_path / "feedback.jsonl")
    event1 = _make_feedback_event(event_date="2026-07-19")
    event2 = _make_feedback_event(event_date="2026-07-20", feedback=SessionFeedback(role=SessionRole.SL, rpe=6.0))

    log_feedback(event1, filepath=filepath)
    log_feedback(event2, filepath=filepath)

    rows = read_feedback(filepath=filepath)
    assert len(rows) == 2
    assert rows[0] == event1.as_dict()
    assert rows[1] == event2.as_dict()

    with open(filepath, "r", encoding="utf-8") as f:
        lines = [line for line in f if line.strip()]
    assert len(lines) == 2


# ---------------------------------------------------------------------------
# as_dict() : JSON-sérialisable, enums imbriqués convertis en str
# ---------------------------------------------------------------------------

def test_decision_event_as_dict_is_json_serializable():
    event = _make_decision_event()
    payload = event.as_dict()

    serialized = json.dumps(payload)  # ne doit lever aucune exception
    assert json.loads(serialized) == payload

    assert isinstance(payload["phase"], str)
    assert payload["phase"] == "SPECIFIC"
    assert isinstance(payload["previous_band"], str)
    assert payload["previous_band"] == "LOW"
    assert isinstance(payload["resulting_band"], str)
    assert payload["resulting_band"] == "CRITICAL"
    assert isinstance(payload["planned_slot"]["role"], str)
    assert isinstance(payload["planned_slot"]["priority"], str)
    assert isinstance(payload["adjusted_slot"]["role"], str)
    assert isinstance(payload["adjusted_slot"]["priority"], str)


def test_decision_event_as_dict_handles_previous_band_none():
    event = _make_decision_event(previous_band=None)
    payload = event.as_dict()
    assert payload["previous_band"] is None
    json.dumps(payload)  # ne doit lever aucune exception


def test_feedback_event_as_dict_is_json_serializable():
    event = _make_feedback_event()
    payload = event.as_dict()

    serialized = json.dumps(payload)  # ne doit lever aucune exception
    assert json.loads(serialized) == payload

    assert isinstance(payload["feedback"]["role"], str)
    assert payload["feedback"]["role"] == "SEUIL"
