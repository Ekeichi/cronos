"""Export du plan global vers un fichier CSV."""

import csv

from domain.models import SessionSlot


def export_plan_to_csv(plan: dict[int, list[SessionSlot]], filepath: str) -> None:
    """
    Exporte le plan global (semaine -> slots) dans un CSV, une ligne par slot.
    Trié par semaine puis par day_position pour rester lisible tel quel.
    """
    fieldnames = [
        "week", "day_position", "role", "priority",
        "duration_min", "d_plus_target_m", "intensity_zone", "notes",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for week_num in sorted(plan.keys()):
            for slot in sorted(plan[week_num], key=lambda s: s.day_position):
                row = slot.as_dict()
                row["week"] = week_num
                writer.writerow(row)
