import json
from pathlib import Path

import pytest

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def baseline() -> dict:
    """
    Sorties de référence produites par l'ancien module monolithique
    (generate_week_template.py) avant refactor, pour un jeu de scénarios
    couvrant generate_week_template, generate_macrocycle_plan,
    classify_readiness et adjust_session. Sert de golden file de
    non-régression : le nouveau package doit reproduire ces valeurs bit à bit.
    """
    with open(_FIXTURES_DIR / "baseline_output.json", "r", encoding="utf-8") as f:
        return json.load(f)
