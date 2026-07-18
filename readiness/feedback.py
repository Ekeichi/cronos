"""Couche readiness : interprétation du RPE post-séance."""

from config.loader import EXPECTED_RPE_BY_ROLE
from domain.models import SessionFeedback


def rpe_deviation(feedback: SessionFeedback) -> float:
    """
    Écart entre le RPE réellement vécu et le RPE attendu pour ce rôle de
    séance. Positif = séance vécue plus dure que prévu.
    """
    return feedback.rpe - EXPECTED_RPE_BY_ROLE[feedback.role.value]
