"""Parse pick-and-place CSV/TXT files into Placement records."""

from __future__ import annotations

import csv
import io
import re
from typing import Optional

from .models import Placement

DESIGNATOR_KEYS = {"designator", "ref", "refdes", "ref des"}
ROTATION_KEYS = {"rotation", "rot"}
SIDE_KEYS = {"layer", "side"}

# Matches "X", "Mid X", "PosX", "Center-X(mm)", "Ref X (mil)", "XLocation", ...
# — Altium and KiCad both name this column differently depending on export
# settings, so column *identity* is matched loosely; a unit suffix embedded
# in the name (mm/mil/in) is then used to override --unit for that column.
_X_PATTERN = re.compile(r"^(mid|pos|center|ref|location)?x(location)?(mm|mil|inch|in)?$")
_Y_PATTERN = re.compile(r"^(mid|pos|center|ref|location)?y(location)?(mm|mil|inch|in)?$")
_UNIT_SUFFIX = re.compile(r"(mm|mil|inch|in)$")

INCH_TO_MM = 25.4
MIL_TO_MM = 0.0254


def _normalize_key(key: str) -> str:
    key = key.strip().lower()
    key = re.sub(r"[_.]", " ", key)
    key = re.sub(r"\s+", " ", key)
    return key


def _compact(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _find_field(row: dict[str, str], candidates: set[str]) -> Optional[str]:
    normalized = {_normalize_key(k): v for k, v in row.items() if k is not None}
    for candidate in candidates:
        value = normalized.get(candidate)
        if value:
            return value
    return None


def _find_axis_field(row: dict[str, str], pattern: re.Pattern) -> tuple[Optional[str], Optional[str]]:
    """Returns (value, unit_suffix_or_None) for the first column matching pattern."""
    for key, value in row.items():
        if key is None or not value:
            continue
        compact = _compact(key)
        match = pattern.match(compact)
        if match:
            unit_match = _UNIT_SUFFIX.search(compact)
            return value, (unit_match.group(1) if unit_match else None)
    return None, None


def _unit_factor(explicit_unit: str, header_unit: Optional[str]) -> float:
    if header_unit in ("mil",):
        return MIL_TO_MM
    if header_unit in ("in", "inch"):
        return INCH_TO_MM
    if header_unit == "mm":
        return 1.0
    return INCH_TO_MM if explicit_unit == "inch" else 1.0


def _parse_side(raw: Optional[str]) -> str:
    if not raw:
        return "top"
    value = raw.strip().lower()
    if value.startswith("b"):
        return "bottom"
    return "top"


def _sniff_delimiter(sample_line: str) -> str:
    try:
        return csv.Sniffer().sniff(sample_line, delimiters=",;\t").delimiter
    except csv.Error:
        if "\t" in sample_line:
            return "\t"
        if ";" in sample_line:
            return ";"
        return ","


# Altium's ASCII pick-and-place report starts with a title/date banner
# before the actual column header line ("Free Format Pick and Place data
# for ..."), so — like the analogous BOM/xlsx banner-row issue — the header
# can't be assumed to be line 1; several lines are scanned for the first
# one that actually looks like a Designator+X+Y header.
_HEADER_SCAN_LINES = 20


def _looks_like_placement_header(fields: list[str]) -> bool:
    has_designator = any(_normalize_key(h) in DESIGNATOR_KEYS for h in fields)
    has_x = any(_X_PATTERN.match(_compact(h)) for h in fields)
    has_y = any(_Y_PATTERN.match(_compact(h)) for h in fields)
    return has_designator and has_x and has_y


def parse_placement_csv(text: str, unit: str = "mm") -> tuple[list[Placement], list[str]]:
    warnings: list[str] = []

    lines = [line for line in text.splitlines() if not line.strip().startswith("#")]
    if not lines:
        return [], ["Plik jest pusty."]

    header_index = None
    delimiter = None
    for i, line in enumerate(lines[:_HEADER_SCAN_LINES]):
        if not line.strip():
            continue
        d = _sniff_delimiter(line)
        row = next(csv.reader(io.StringIO(line), delimiter=d), None)
        if not row or len(row) < 2:
            continue
        if _looks_like_placement_header([c.strip() for c in row]):
            header_index, delimiter = i, d
            break

    if header_index is None:
        return [], [
            "Nie znaleziono wiersza nagłówka z oznaczeniem (Designator) i pozycją X/Y "
            f"(przeszukano pierwsze {_HEADER_SCAN_LINES} niepustych linii pliku). "
            "Sprawdź format pliku pick-and-place."
        ]

    reader = csv.DictReader(io.StringIO("\n".join(lines[header_index:])), delimiter=delimiter)
    if reader.fieldnames is None:
        return [], ["Plik jest pusty lub nie zawiera nagłówka."]

    placements: list[Placement] = []
    for row in reader:
        clean_row = {(k or "").strip(): (v or "").strip() for k, v in row.items() if k is not None}
        designator = _find_field(clean_row, DESIGNATOR_KEYS)
        x_raw, x_unit = _find_axis_field(clean_row, _X_PATTERN)
        y_raw, y_unit = _find_axis_field(clean_row, _Y_PATTERN)
        if not designator or x_raw is None or y_raw is None:
            continue
        try:
            x = float(x_raw) * _unit_factor(unit, x_unit)
            y = float(y_raw) * _unit_factor(unit, y_unit)
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
            "Nie znaleziono poprawnych wierszy z pozycją (Designator, Mid X/Center-X, Mid Y/Center-Y). "
            "Sprawdź nagłówki pliku pick-and-place."
        )

    return placements, warnings


def parse_placement_file(path: str, unit: str = "mm") -> tuple[list[Placement], list[str]]:
    with open(path, "r", encoding="utf-8-sig") as f:
        text = f.read()
    return parse_placement_csv(text, unit=unit)
