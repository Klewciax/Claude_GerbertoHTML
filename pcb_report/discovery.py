"""Auto-detect Gerber / BOM / pick-and-place files in a project folder.

Built for the common case (confirmed with an actual user of this tool):
Altium Designer or KiCad export folders, run over and over as a project
changes. Gerber layers are unambiguous by extension. BOM and pick-and-place
are the tricky part, because both tools happily export either as `.csv`,
and Altium's pick-and-place report is very often a `.txt` file — the same
extension Altium also uses for its Excellon drill file. So instead of
guessing from the extension alone, ambiguous files are opened and their
actual content decides:

- Drill file? Try parsing it as Excellon (via gerbonara) — if that
  succeeds and finds real tool/hit data, it's a drill layer, not a BOM
  or PnP file.
- Otherwise, read the header row and look for paired X/Y position columns
  (pick-and-place always has them; a BOM never does).
- Otherwise, if it has a Designator/Reference-like column, it's a BOM.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .bom import _compact, _normalize_key, iter_xlsx_header_candidates, looks_like_designator_header

GERBER_EXTENSIONS = {
    # Generic / KiCad (layer identity comes from the filename, not the extension)
    "gbr", "gko", "gml",
    # Altium / Eagle classic per-layer extensions
    "gtl", "gbl", "gto", "gbo", "gts", "gbs", "gtp", "gbp",
    # Drill
    "drl", "xnc", "tho", "thd", "nc",
}
# Inner-copper layers: .g1..g32 / .gp1..gp32
_INNER_COPPER_RE = re.compile(r"^gp?\d+$")
# Altium mechanical layers: .gm1..gm16
_MECHANICAL_RE = re.compile(r"^gm\d+$")

_TABULAR_EXTENSIONS = {"csv", "txt"}
_EXCEL_EXTENSIONS = {"xlsx"}

_X_PATTERN = re.compile(r"^(mid|pos|center|ref|location)?x(location)?(mm|mil|in|inch)?$")
_Y_PATTERN = re.compile(r"^(mid|pos|center|ref|location)?y(location)?(mm|mil|in|inch)?$")


def is_gerber_extension(ext: str) -> bool:
    ext = ext.lower().lstrip(".")
    return ext in GERBER_EXTENSIONS or bool(_INNER_COPPER_RE.match(ext)) or bool(_MECHANICAL_RE.match(ext))


def _read_header_row(path: Path) -> Optional[list[str]]:
    """Best-effort header row for a delimited text file, or None if it
    doesn't look tabular at all (e.g. an Excellon drill file)."""
    try:
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
            sample = f.read(8192)
    except OSError:
        return None

    first_line = sample.splitlines()[0] if sample.splitlines() else ""
    if not first_line:
        return None

    try:
        dialect = csv.Sniffer().sniff(first_line, delimiters=",;\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = "," if "," in first_line else "\t" if "\t" in first_line else ";" if ";" in first_line else None
    if delimiter is None:
        return None

    row = next(csv.reader(io.StringIO(first_line), delimiter=delimiter), None)
    if not row or len(row) < 2:
        return None
    return [c.strip() for c in row]


def _looks_like_excellon_drill(path: Path) -> bool:
    try:
        from gerbonara.excellon import ExcellonFile
        drill = ExcellonFile.open(str(path))
        return not drill.is_empty
    except Exception:
        return False


def classify_tabular_header(header: list[str]) -> str:
    """Returns 'pnp', 'bom', or 'unknown' for a header row."""
    normalized = [_compact(_normalize_key(h)) for h in header]
    has_x = any(_X_PATTERN.match(h) for h in normalized)
    has_y = any(_Y_PATTERN.match(h) for h in normalized)
    if has_x and has_y:
        return "pnp"

    if looks_like_designator_header(header):
        return "bom"
    return "unknown"


@dataclass
class DiscoveryResult:
    gerber_paths: list[str] = field(default_factory=list)
    bom_path: Optional[str] = None
    pnp_paths: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def discover_project_files(project_dir: Path) -> DiscoveryResult:
    """Searches the *entire* directory tree under project_dir, not just its
    top level — Altium's "Project Outputs" folder typically splits Gerber /
    NC Drill / Bill of Materials / Pick and Place into separate
    subfolders, at an arbitrary nesting depth and under arbitrary names.
    """
    result = DiscoveryResult()
    files = [p for p in project_dir.rglob("*") if p.is_file()]

    bom_candidates: list[Path] = []
    pnp_candidates: list[Path] = []
    unresolved: list[Path] = []

    for path in files:
        ext = path.suffix.lower().lstrip(".")

        if is_gerber_extension(ext):
            result.gerber_paths.append(str(path))
            continue

        if ext in _EXCEL_EXTENSIONS:
            kind = "unknown"
            for _, _, header in iter_xlsx_header_candidates(path):
                kind = classify_tabular_header(header)
                if kind != "unknown":
                    break
            if kind == "bom":
                bom_candidates.append(path)
            elif kind == "pnp":
                pnp_candidates.append(path)
            else:
                unresolved.append(path)
            continue

        if ext in _TABULAR_EXTENSIONS:
            if _looks_like_excellon_drill(path):
                result.gerber_paths.append(str(path))
                continue
            header = _read_header_row(path)
            kind = classify_tabular_header(header) if header else "unknown"
            if kind == "pnp":
                pnp_candidates.append(path)
            elif kind == "bom":
                bom_candidates.append(path)
            else:
                unresolved.append(path)
            continue

        # Anything else (readme, zip, pdf report, ...) is silently ignored.

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(project_dir))
        except ValueError:
            return str(p)

    if len(bom_candidates) == 1:
        result.bom_path = str(bom_candidates[0])
    elif len(bom_candidates) > 1:
        names = ", ".join(_rel(p) for p in bom_candidates)
        result.errors.append(
            f"Znaleziono więcej niż jeden plik wyglądający na BOM ({names}) — wskaż właściwy przez --bom."
        )

    if pnp_candidates:
        result.pnp_paths = [str(p) for p in pnp_candidates]
        if len(pnp_candidates) > 1:
            names = ", ".join(_rel(p) for p in pnp_candidates)
            result.warnings.append(
                f"Znaleziono kilka plików pick-and-place ({names}) — połączono je razem "
                "(typowe dla oddzielnych raportów Top/Bottom w Altium)."
            )

    if unresolved:
        names = ", ".join(_rel(p) for p in unresolved)
        result.warnings.append(
            f"Nie rozpoznano przeznaczenia plików: {names} — zignorowano. "
            "Jeśli to BOM lub pick-and-place, wskaż je jawnie przez --bom / --pnp."
        )

    if not result.gerber_paths:
        result.errors.append(f"Nie znaleziono żadnych plików Gerber/Excellon w '{project_dir}'.")
    if result.bom_path is None and not any("BOM" in e for e in result.errors):
        result.errors.append(f"Nie znaleziono pliku BOM w '{project_dir}' — wskaż go przez --bom.")

    return result
