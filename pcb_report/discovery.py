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
import sys
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


_HEADER_SCAN_LINES = 20


def _iter_text_header_candidates(path: Path, max_lines: int = _HEADER_SCAN_LINES):
    """Yields each of the first `max_lines` non-empty lines of a delimited
    text file, parsed as a header row. Altium's ASCII pick-and-place report
    (and some BOM CSV exports) start with a title/date banner before the
    actual column header line, so — same issue as the xlsx banner-row case
    above — several lines are offered as candidates rather than assuming
    line 1 is the header. A leading "#" is stripped before parsing rather
    than treating every such line as a comment to discard outright, since
    KiCad's own ASCII position-file export prefixes its header line with
    one ("# Ref  Val  Package  PosX  PosY  Rot  Side") — other, genuinely
    non-header "#" lines (its date/unit banner) just won't parse into
    anything recognizable and are skipped same as before.
    """
    try:
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
            lines = []
            for line in f:
                lines.append(line)
                if len(lines) >= max_lines:
                    break
    except OSError:
        return

    for line in lines:
        line = line.rstrip("\r\n")
        candidate = line.lstrip("#").strip()
        if not candidate:
            continue
        delimiter = None
        if any(c in line for c in ",;\t"):
            try:
                delimiter = csv.Sniffer().sniff(line, delimiters=",;\t").delimiter
            except csv.Error:
                delimiter = "," if "," in line else "\t" if "\t" in line else ";"
        if delimiter is not None:
            row = next(csv.reader(io.StringIO(candidate), delimiter=delimiter), None)
            fields = [c.strip() for c in row] if row else None
        else:
            # No conventional delimiter -- KiCad pads columns with a run of
            # spaces instead of using one.
            fields = candidate.split() or None
        if fields and len(fields) >= 2:
            yield fields


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


_SIDE_TOKENS = {"top", "bottom", "bot"}


def _common_prefix(strings: list[str]) -> str:
    if not strings:
        return ""
    prefix = strings[0]
    for s in strings[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""
    return prefix


def _derive_variant_labels(paths: list[Path]) -> dict[Path, str]:
    """Best-effort short label per file, derived from what differs after
    their shared filename prefix — e.g. "..._Critical.xlsx" vs.
    "..._NotCritical.xlsx" -> "Critical" / "NotCritical" — since Altium
    project variants are conventionally exported as one BOM/pick-and-place
    file per variant, all sharing the project's base filename. Falls back
    to the plain filename when the derived label would be empty or collide
    with another file's label, so every file always gets a usable label
    even when the naming doesn't share a clean prefix.
    """
    stems = [p.stem for p in paths]
    prefix = _common_prefix(stems)
    if prefix and not any(s == prefix for s in stems):
        # The prefix doesn't correspond to any file's full name by itself,
        # so it may land mid-word for the others (e.g. cut off partway
        # through a shared word) — back up to the last separator. When one
        # stem *is* exactly the prefix (the base/no-suffix variant), trust
        # it as-is instead: it's a real, complete name, not a partial one.
        cut = len(prefix)
        while cut > 0 and prefix[cut - 1] not in "-_ ":
            cut -= 1
        prefix = prefix[:cut]

    labels: dict[Path, str] = {}
    seen: set[str] = set()
    for p, stem in zip(paths, stems):
        suffix = stem[len(prefix):].strip("-_ ").strip("[]").strip()
        label = suffix or "Podstawowy"
        if label in seen:
            label = stem
        seen.add(label)
        labels[p] = label
    return labels


def _is_side_split(paths: list[Path]) -> bool:
    """True when a set of pick-and-place candidates differ only by a
    top/bottom-side token (the common case of separate Top/Bottom reports),
    as opposed to genuinely different assembly variants — the former should
    still be merged together, the latter should not."""
    labels = _derive_variant_labels(paths)
    return all(_compact(label) in _SIDE_TOKENS for label in labels.values())


def _pair_variant_labels(bom_labels: dict[Path, str], pnp_labels: dict[Path, str]) -> dict[str, Path]:
    """Best-effort match of each BOM variant label to a pick-and-place file
    carrying recognizably similar wording in its own label (e.g. BOM
    "Critical" <-> pick-and-place "..._Critical") — variant naming isn't
    standardized, so this deliberately uses a forgiving substring match on
    a compacted, lowercased label rather than requiring an exact one.
    Leftover single BOM/pick-and-place variants that couldn't be matched by
    wording (e.g. BOM's default-variant label vs. a pick-and-place file
    named "No Variations") are then paired positionally as a last resort.
    """
    used: set[Path] = set()
    pairing: dict[str, Path] = {}

    # Pass 1: exact match on the compacted label — the overwhelmingly
    # common case for real variant names, and immune to one label being an
    # accidental substring of another ("Critical" is literally a substring
    # of "NotCritical", so a same-pass substring check would risk cross-
    # matching them depending on dict iteration order).
    for bom_label in bom_labels.values():
        bom_c = _compact(bom_label)
        if not bom_c:
            continue
        for pnp_path, pnp_label in pnp_labels.items():
            if pnp_path in used:
                continue
            if bom_c == _compact(pnp_label):
                pairing[bom_label] = pnp_path
                used.add(pnp_path)
                break

    # Pass 2: forgiving substring match for whatever's left (e.g. a
    # pick-and-place filename that repeats the project code around the
    # variant name) — only among labels pass 1 couldn't resolve.
    for bom_label in bom_labels.values():
        if bom_label in pairing:
            continue
        bom_c = _compact(bom_label)
        if not bom_c:
            continue
        for pnp_path, pnp_label in pnp_labels.items():
            if pnp_path in used:
                continue
            pnp_c = _compact(pnp_label)
            if bom_c in pnp_c or pnp_c in bom_c:
                pairing[bom_label] = pnp_path
                used.add(pnp_path)
                break

    unmatched_bom = [label for label in bom_labels.values() if label not in pairing]
    unmatched_pnp = [p for p in pnp_labels if p not in used]
    if len(unmatched_bom) == 1 and len(unmatched_pnp) == 1:
        pairing[unmatched_bom[0]] = unmatched_pnp[0]
    return pairing


@dataclass
class DiscoveryResult:
    gerber_paths: list[str] = field(default_factory=list)
    bom_path: Optional[str] = None
    pnp_paths: list[str] = field(default_factory=list)
    # Populated instead of bom_path/pnp_paths when several BOM files were
    # found that look like assembly variants of the same project (e.g.
    # Altium's Critical/NotCritical/... project variants) rather than one
    # unambiguous BOM: label -> file path, and label -> matching
    # pick-and-place file(s) when one could be paired to it by name.
    bom_variants: dict[str, str] = field(default_factory=dict)
    pnp_variants: dict[str, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _prompt_file_kind(path: Path, project_dir: Path) -> str:
    """Asks the person running the tool what an unrecognized file actually
    is, instead of just silently ignoring it. Returns 'bom', 'pnp', or
    'skip'."""
    try:
        rel = str(path.relative_to(project_dir))
    except ValueError:
        rel = str(path)
    print(f"\nNie rozpoznano automatycznie przeznaczenia pliku:\n  {rel}", file=sys.stderr)
    while True:
        try:
            choice = input("  Co to jest? [b] BOM   [p] Pick-and-place   [Enter] pomiń: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "skip"
        if choice in ("", "s", "skip", "pomin", "pomiń"):
            return "skip"
        if choice in ("b", "bom"):
            return "bom"
        if choice in ("p", "pnp"):
            return "pnp"
        print("  Nie rozpoznano odpowiedzi — wpisz 'b', 'p' albo wciśnij Enter, by pominąć.", file=sys.stderr)


def discover_project_files(project_dir: Path, interactive: bool = True) -> DiscoveryResult:
    """Searches the *entire* directory tree under project_dir, not just its
    top level — Altium's "Project Outputs" folder typically splits Gerber /
    NC Drill / Bill of Materials / Pick and Place into separate
    subfolders, at an arbitrary nesting depth and under arbitrary names.

    `interactive` (only meaningful when running in a real terminal — see
    the `sys.stdin.isatty()` check below) lets the person running the tool
    manually classify a file whose purpose content-sniffing couldn't
    determine (e.g. a status/report text file that isn't a BOM or
    pick-and-place export but happens to look tabular) instead of it just
    being silently ignored.
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
            kind = "unknown"
            for header in _iter_text_header_candidates(path):
                kind = classify_tabular_header(header)
                if kind != "unknown":
                    break
            if kind == "pnp":
                pnp_candidates.append(path)
            elif kind == "bom":
                bom_candidates.append(path)
            else:
                unresolved.append(path)
            continue

        # Anything else (readme, zip, pdf report, ...) is silently ignored.

    if unresolved and interactive and sys.stdin.isatty():
        still_unresolved: list[Path] = []
        for path in unresolved:
            kind = _prompt_file_kind(path, project_dir)
            if kind == "bom":
                bom_candidates.append(path)
            elif kind == "pnp":
                pnp_candidates.append(path)
            else:
                still_unresolved.append(path)
        unresolved = still_unresolved

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(project_dir))
        except ValueError:
            return str(p)

    pnp_consumed_as_variants = False

    if len(bom_candidates) == 1:
        result.bom_path = str(bom_candidates[0])
    elif len(bom_candidates) > 1:
        bom_labels = _derive_variant_labels(bom_candidates)  # Path -> label
        result.bom_variants = {label: str(path) for path, label in bom_labels.items()}

        pnp_labels: dict[Path, str] = {}
        if len(pnp_candidates) > 1 and not _is_side_split(pnp_candidates):
            pnp_labels = _derive_variant_labels(pnp_candidates)
            pnp_consumed_as_variants = True

        variant_names = ", ".join(sorted(result.bom_variants))
        if pnp_labels:
            pairing = _pair_variant_labels(bom_labels, pnp_labels)
            for bom_label, pnp_path in pairing.items():
                result.pnp_variants[bom_label] = [str(pnp_path)]
            unpaired = sorted(set(result.bom_variants) - set(pairing))
            result.warnings.append(
                f"Wykryto {len(bom_labels)} wariantów montażu ({variant_names}) — pick-and-place dopasowano "
                f"automatycznie po nazwie dla: {', '.join(sorted(pairing)) or '(brak)'}."
                + (f" Bez dopasowania (pozycjonowanie ręczne): {', '.join(unpaired)}." if unpaired else "")
                + " Wybór wariantu montażu jest dostępny w wygenerowanym raporcie."
            )
        else:
            result.warnings.append(
                f"Wykryto {len(bom_labels)} wariantów montażu ({variant_names}) — wybór wariantu montażu "
                "jest dostępny w wygenerowanym raporcie."
            )

    if pnp_candidates and not pnp_consumed_as_variants:
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
    if result.bom_path is None and not result.bom_variants and not any("BOM" in e for e in result.errors):
        result.errors.append(f"Nie znaleziono pliku BOM w '{project_dir}' — wskaż go przez --bom.")

    return result
