"""
Orchestration : compose generation/, readiness/ et persistence/ pour un
athlète et un jour donnés. Ce n'est pas un scheduler de production (pas de
cron, pas d'API HTTP) — juste la logique de composition avec effets de bord
(lecture du dernier band, lecture du feedback récent, écriture du log),
appelable telle quelle et prête à être branchée derrière un scheduler ou
une API plus tard.

generation/ et readiness/ restent pures : cette couche les appelle, elle
n'est jamais appelée par elles. Le bouclage sur tous les athlètes chaque
jour est une couche encore au-dessus, hors scope ici — un appel = un
athlète, un jour.
"""

from datetime import date, timedelta

from config.loader import CURRENT_POLICY_VERSION
from domain.enums import ReadinessBand, SessionRole
from domain.events import DecisionEvent, FeedbackEvent
from domain.models import AthletePlanContext, ReadinessSignals, SessionFeedback, SessionSlot
from generation.macrocycle import resolve_block_position
from persistence.event_log import log_decision, log_feedback, read_decisions, read_feedback
from readiness.adjustment import adjust_session
from readiness.classification import classify_readiness


def _resolve_today(context: AthletePlanContext, today: date) -> tuple[int, int, int, list[SessionSlot]]:
    """
    Calcule la position de `today` dans le plan de l'athlète et renvoie
    (global_week, week_in_block, block_length, slots planifiés du jour).

    global_week et day_position sont dérivés de (today - plan_start_date),
    7 jours par semaine, day_position 1-indexed. phase/week_in_block/
    block_length sont résolus via resolve_block_position sur ces mêmes
    blocs. La phase elle-même n'est pas renvoyée ici : l'appelant qui en a
    besoin (run_daily_adjustment, pour construire le DecisionEvent) la
    retrouve via un second appel à resolve_block_position — opération pure
    et immédiate, sans coût réel à la dupliquer.

    Lève ValueError si today est hors des bornes du plan (avant
    plan_start_date, ou après la dernière semaine du macrocycle).
    """
    delta_days = (today - context.plan_start_date).days
    if delta_days < 0:
        raise ValueError(
            f"{today.isoformat()} est avant le début du plan de {context.athlete_id} "
            f"({context.plan_start_date.isoformat()})"
        )

    global_week, day_position_zero_indexed = divmod(delta_days, 7)
    global_week += 1
    day_position = day_position_zero_indexed + 1

    # lève ValueError si global_week dépasse la dernière semaine du macrocycle
    _, week_in_block, block_length = resolve_block_position(context.blocks, global_week)

    if global_week not in context.macrocycle_plan:
        raise ValueError(
            f"{today.isoformat()} (semaine {global_week}) n'a pas de plan généré "
            f"pour {context.athlete_id} — macrocycle_plan et blocks sont incohérents"
        )

    slots_today = [slot for slot in context.macrocycle_plan[global_week] if slot.day_position == day_position]

    return global_week, week_in_block, block_length, slots_today


def _get_previous_band(athlete_id: str, today: date, decisions_filepath: str) -> ReadinessBand | None:
    """
    Bande retenue lors de la décision la plus récente strictement antérieure
    à `today` pour cet athlète, ou None s'il n'y en a aucune (premier jour du
    plan, ou fichier de décisions pas encore créé — géré sans lever
    d'exception).
    """
    try:
        rows = read_decisions(filepath=decisions_filepath)
    except FileNotFoundError:
        return None

    today_iso = today.isoformat()
    matching = [
        row for row in rows
        if row["athlete_id"] == athlete_id and row["event_date"] < today_iso
    ]
    if not matching:
        return None

    most_recent = max(matching, key=lambda row: row["event_date"])
    return ReadinessBand(most_recent["resulting_band"])


def _get_recent_feedback(
    athlete_id: str,
    today: date,
    feedback_filepath: str,
    lookback_days: int = 2,
) -> SessionFeedback | None:
    """
    Feedback le plus récent dans la fenêtre [today - lookback_days, today)
    pour cet athlète, reconstruit en SessionFeedback (pas le dict brut), ou
    None si aucun (y compris si le fichier de feedback n'existe pas encore).

    Une fenêtre de lookback existe parce que classify_readiness n'a pas de
    mémoire propre sur l'override RPE : sans borne, un unique feedback
    catastrophique loggé un jour continuerait à dégrader la bande de tous
    les jours suivants indéfiniment. Au-delà de quelques jours, un RPE
    post-séance ne doit plus influencer le readiness du jour — la charge
    récente est déjà reflétée par ailleurs dans le score composite (TSB,
    monotony, ACWR).
    """
    try:
        rows = read_feedback(filepath=feedback_filepath)
    except FileNotFoundError:
        return None

    window_start_iso = (today - timedelta(days=lookback_days)).isoformat()
    today_iso = today.isoformat()
    matching = [
        row for row in rows
        if row["athlete_id"] == athlete_id and window_start_iso <= row["event_date"] < today_iso
    ]
    if not matching:
        return None

    most_recent = max(matching, key=lambda row: row["event_date"])
    feedback_dict = most_recent["feedback"]
    return SessionFeedback(
        role=SessionRole(feedback_dict["role"]),
        rpe=feedback_dict["rpe"],
        actual_duration_min=feedback_dict["actual_duration_min"],
        completed_as_planned=feedback_dict["completed_as_planned"],
        notes=feedback_dict["notes"],
    )


def run_daily_adjustment(
    context: AthletePlanContext,
    today: date,
    signals: ReadinessSignals,
    decisions_filepath: str = "decisions.jsonl",
    feedback_filepath: str = "feedback.jsonl",
    feedback_lookback_days: int = 2,
) -> list[SessionSlot]:
    """
    Résout, ajuste et logge la ou les séances du jour pour un athlète.

    Le readiness est un état du jour, pas par séance : classify_readiness
    n'est appelé qu'une seule fois, puis adjust_session est appliqué à
    chaque slot planifié du jour avec cette même bande. Un DecisionEvent
    est loggé par slot (planned_slot / adjusted_slot), pas un seul événement
    agrégé pour le jour.

    Renvoie la liste des slots ajustés du jour — ce que l'appelant présente
    à l'athlète.
    """
    global_week, week_in_block, block_length, planned_slots = _resolve_today(context, today)
    phase, _, _ = resolve_block_position(context.blocks, global_week)

    previous_band = _get_previous_band(context.athlete_id, today, decisions_filepath)
    last_session_feedback = _get_recent_feedback(
        context.athlete_id, today, feedback_filepath, lookback_days=feedback_lookback_days
    )

    resulting_band = classify_readiness(
        signals,
        previous_band=previous_band,
        last_session_feedback=last_session_feedback,
    )

    adjusted_slots = []
    for planned_slot in planned_slots:
        adjusted_slot = adjust_session(planned_slot, resulting_band)
        adjusted_slots.append(adjusted_slot)

        event = DecisionEvent(
            athlete_id=context.athlete_id,
            event_date=today.isoformat(),
            phase=phase,
            week_in_block=week_in_block,
            block_length=block_length,
            signals=signals,
            previous_band=previous_band,
            resulting_band=resulting_band,
            planned_slot=planned_slot,
            adjusted_slot=adjusted_slot,
            policy_version=CURRENT_POLICY_VERSION,
        )
        log_decision(event, filepath=decisions_filepath)

    return adjusted_slots


def record_session_feedback(
    athlete_id: str,
    today: date,
    feedback: SessionFeedback,
    feedback_filepath: str = "feedback.jsonl",
) -> None:
    """
    Enregistre le feedback post-séance d'un athlète. Point d'entrée séparé
    de run_daily_adjustment, à appeler après la séance quand l'athlète
    rapporte son RPE — jamais depuis run_daily_adjustment elle-même.
    """
    event = FeedbackEvent(
        athlete_id=athlete_id,
        event_date=today.isoformat(),
        feedback=feedback,
        policy_version=CURRENT_POLICY_VERSION,
    )
    log_feedback(event, filepath=feedback_filepath)
