"""Enums partagés par l'ensemble du projet."""

from enum import Enum


class Phase(str, Enum):
    BASE = "BASE"
    SPECIFIC = "SPECIFIC"
    TAPER = "TAPER"


class SessionRole(str, Enum):
    EF = "EF"           # endurance fondamentale
    SEUIL = "SEUIL"      # tempo / seuil lactique
    VMA = "VMA"          # fractionné court-moyen
    COTES = "COTES"      # côtes courtes ou longues
    SL = "SL"            # sortie longue
    RENFO = "RENFO"      # renforcement musculaire
    RECUP = "RECUP"       # footing / repos actif


class Priority(str, Enum):
    HARD = "HARD"         # séance à forte contrainte physio, difficile à déplacer
    MODERATE = "MODERATE"  # déplaçable dans la semaine si besoin
    SOFT = "SOFT"          # variable d'ajustement libre (raccourcir/annuler sans casser le plan)


class ReadinessBand(str, Enum):
    CRITICAL = "CRITICAL"
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
