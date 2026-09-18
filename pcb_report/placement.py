"""Parse pick-and-place CSV files into Placement records."""

from __future__ import annotations

import csv
import io
import re
from typing import Optional

from .models import Placement

DESIGNATOR_KEYS = {"designator", "ref", "refdes", "ref des"}
X_KEYS = {"mid x", "midx", "x", "pos x", "posx", "x (mm)", "x(mm)"}
Y_KEYS = {"mid y", "midy", "y", "pos y", "posy", "y (mm)", "y(mm)"}
ROTATION_KEYS = {"rotation", "rot"}
SIDE_KEYS = {"layer", "side"}

INCH_TO_MM = 25.4


def _normalize_key(key: str) -> str:
    key = key.strip().lower()
    key = re.sub(r"[_.]", " ", key)
    key = re.sub(r"\s+", " ", key)
    return key


def _find_field(row: dict[str, str], candidates: set[str]) -> Optional[str]:
    normalized = {_normalize_key(k): v for k, v in row.items() if k is not None}
    for candidate in candidates:
        value = normalized.get(candidate)
        if value:
            return value
    return None


def _parse_side(raw: Optional[str]) -> str:
    if not raw:
        return "top"
    value = raw.strip().lower()
    if value.startswith("b"):
        return "bottom"
    return "top"


def parse_placement_csv(text: str, unit: str = "mm") -> tuple[list[Placement], list[str]]:
    warnings: list[str] = []
    factor = INCH_TO_MM if unit == "inch" else 1.0

    lines = [line for line in text.splitlines() if not line.strip().startswith("#")]
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    if reader.fieldnames is None:
        return [], ["Plik CSV jest pusty lub nie zawiera nagłówka."]

    placements: list[Placement] = []
    for row in reader:
        clean_row = {(k or "").strip(): (v or "").strip() for k, v in row.items() if k is not None}
        designator = _find_field(clean_row, DESIGNATOR_KEYS)
        x_raw = _find_field(clean_row, X_KEYS)
        y_raw = _find_field(clean_row, Y_KEYS)
        if not designator or x_raw is None or y_raw is None:
            continue
        try:
            x = float(x_raw) * factor
            y = float(y_raw) * factor
        except ValueError:
            continue

        rotation_raw = _find_field(clean_row, ROTATION_KEYS)
        try:
            rotation = float(rotation_raw) if rotation_raw else 0.0
        except ValueError:
            rotation = 0.0

        placements.append(
            Placement(
                designator=designator.strip(),
                x=x,
                y=y,
                rotation=rotation,
                side=_parse_side(_find_field(clean_row, SIDE_KEYS)),
            )
        )

    if not placements:
        warnings.append(
            "Nie znaleziono poprawnych wierszy z pozycją (Designator, Mid X, Mid Y). "
            "Sprawdź nagłówki pliku pick-and-place."
        )

    return placements, warnings


def parse_placement_file(path: str, unit: str = "mm") -> tuple[list[Placement], list[str]]:
    with open(path, "r", encoding="utf-8-sig") as f:
        text = f.read()
    return parse_placement_csv(text, unit=unit)
