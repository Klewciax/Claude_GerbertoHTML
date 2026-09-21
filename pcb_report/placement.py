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


def _split_line(line: str, mode: tuple) -> Optional[list[str]]:
    """Splits one data/header line per a mode from _detect_header: either
    ('delim', <char>) for a real delimiter, or ('whitespace',) for KiCad's
    ASCII position-file export, which pads columns with a run of spaces
    instead of using one."""
    if mode[0] == "delim":
        row = next(csv.reader(io.StringIO(line), delimiter=mode[1]), None)
        return [c.strip() for c in row] if row else None
    parts = line.split()
    return parts or None


def _detect_header(lines: list[str]) -> Optional[tuple[int, list[str], tuple]]:
    """Scans the first _HEADER_SCAN_LINES lines for the pick-and-place
    header, trying each as both a delimited row and a whitespace-split row.
    KiCad's own ASCII export prefixes its header with "#" (e.g.
    "# Ref  Val  Package  PosX  PosY  Rot  Side") and pads columns with
    spaces rather than a real delimiter, so a leading "#" is stripped
    before parsing instead of treating every such line as a comment to
    discard outright — most still won't look like a real header once
    parsed (e.g. KiCad's "### Footprint positions - created on ...*%"
    banner lines) and are simply skipped like before.
    """
    for i, raw_line in enumerate(lines[:_HEADER_SCAN_LINES]):
        line = raw_line.rstrip("\r\n")
        candidate = line.lstrip("#").strip()
        if not candidate:
            continue
        delimiter = _sniff_delimiter(line) if any(c in line for c in ",;\t") else None
        if delimiter is not None:
            fields = _split_line(candidate, ("delim", delimiter))
            mode = ("delim", delimiter)
        else:
            fields = _split_line(candidate, ("whitespace",))
            mode = ("whitespace",)
        if fields and len(fields) >= 2 and _looks_like_placement_header(fields):
            return i, fields, mode
    return None


def parse_placement_csv(text: str, unit: str = "mm") -> tuple[list[Placement], list[str]]:
    lines = text.splitlines()
    if not lines:
        return [], ["Plik jest pusty."]

    detected = _detect_header(lines)
    if detected is None:
        return [], [
            "Nie znaleziono wiersza nagłówka z oznaczeniem (Designator) i pozycją X/Y "
            f"(przeszukano pierwsze {_HEADER_SCAN_LINES} niepustych linii pliku). "
            "Sprawdź format pliku pick-and-place."
        ]
    header_index, header_fields, mode = detected

    warnings: list[str] = []
    placements: list[Placement] = []
    for raw_line in lines[header_index + 1 :]:
        line = raw_line.rstrip("\r\n")
        if not line.strip() or line.strip().startswith("#"):
            continue  # blank line, or a trailing comment/footer (e.g. KiCad's "## End")
        values = _split_line(line, mode)
        if not values:
            continue
        clean_row = {header_fields[i]: (values[i].strip() if i < len(values) else "") for i in range(len(header_fields))}
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
