"""
Journalisation append-only des décisions et feedbacks, en JSONL (une ligne
JSON par événement, un fichier par type d'événement). Format choisi pour
rester lisible, versionnable, et facile à reparser plus tard en
pandas/PyTorch, sans dépendance à une DB pour cette v1.

Ceci est un effet de bord explicite : appelé par le code appelant
(l'orchestrateur applicatif), jamais depuis generation/ ou readiness/, qui
restent des couches pures sans écriture disque.

Jointure a posteriori
----------------------
decisions.jsonl et feedback.jsonl ne sont jamais synchronisés en écriture :
pour une séance donnée, le feedback (RPE post-séance) arrive typiquement
après coup — le jour même ou le lendemain, une fois la séance réalisée — pas
au moment où la décision est loggée. La jointure entre les deux se fait donc
en aval, à la lecture/analyse, sur la clé (athlete_id, event_date) ; ce n'est
pas une contrainte imposée à l'écriture.

policy_version est dupliqué dans les deux types d'événement (plutôt que
déduit via le join) pour pouvoir filtrer par version de politique directement
sur l'un ou l'autre fichier, sans avoir à les joindre au préalable.

Erreurs d'écriture/lecture (disque plein, chemin invalide, JSON corrompu...)
ne sont volontairement pas interceptées ici : elles remontent telles quelles
plutôt que d'être avalées silencieusement.
"""

import json

from domain.events import DecisionEvent, FeedbackEvent


def log_decision(event: DecisionEvent, filepath: str = "decisions.jsonl") -> None:
    """Append event.as_dict() comme une ligne JSON dans filepath (créé si absent)."""
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(event.as_dict(), ensure_ascii=False) + "\n")


def log_feedback(event: FeedbackEvent, filepath: str = "feedback.jsonl") -> None:
    """Append event.as_dict() comme une ligne JSON dans filepath (créé si absent)."""
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(event.as_dict(), ensure_ascii=False) + "\n")


def read_decisions(filepath: str = "decisions.jsonl") -> list[dict]:
    """Lit et parse toutes les lignes de filepath en liste de dicts."""
    with open(filepath, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def read_feedback(filepath: str = "feedback.jsonl") -> list[dict]:
    """Lit et parse toutes les lignes de filepath en liste de dicts."""
    with open(filepath, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
