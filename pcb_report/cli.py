"""Command-line entry point.

    python -m pcb_report [KATALOG_PROJEKTU] [--gerber f1.gbr f2.gbr ...] [--bom bom.csv] [--pnp pnp.csv ...] [-o report.html]

Gerber/BOM/pick-and-place są auto-wykrywane w KATALOGU_PROJEKTU (domyślnie
bieżący katalog) kiedy odpowiedni argument nie jest podany jawnie — patrz
discovery.py.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .bom import parse_bom_file
from .discovery import discover_project_files
from .gerber import render_gerber_files
from .models import BomVariant, GerberRenderResult, Placement
from .placement import parse_placement_file
from .report import build_report_html


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pcb_report",
        description="Generuje statyczny, interaktywny raport HTML (Assembly + Traceability) z plików Gerber, BOM i pick-and-place.",
    )
    parser.add_argument(
        "project",
        nargs="?",
        default=".",
        metavar="KATALOG",
        help="Katalog projektu do przeszukania (domyślnie bieżący katalog). Gerber/BOM/pick-and-place, "
        "które nie zostały podane jawnie poniżej, są w nim auto-wykrywane.",
    )
    parser.add_argument("--gerber", nargs="+", metavar="PLIK", default=None, help="Pliki Gerber/Excellon (RS-274X). Pominięcie = auto-wykrywanie w KATALOGU.")
    parser.add_argument("--bom", metavar="PLIK", default=None, help="Plik BOM (.csv, .xml lub .xlsx). Pominięcie = auto-wykrywanie w KATALOGU.")
    parser.add_argument("--pnp", nargs="+", metavar="PLIK", default=None, help="Plik(i) pick-and-place (.csv) — więcej niż jeden dla oddzielnych raportów Top/Bottom (zostaną połączone). Pominięcie = auto-wykrywanie w KATALOGU (obejmuje też wykrywanie wariantów montażu, patrz README).")
    parser.add_argument("--unit", choices=["mm", "inch"], default="mm", help="Jednostki współrzędnych w pliku pick-and-place (domyślnie mm).")
    parser.add_argument(
        "--all-layers",
        action="store_true",
        help="Renderuj też maskę lutowniczą, wewnętrzne warstwy miedzi i inne nierozpoznane warstwy "
        "mechaniczne Altium (domyślnie pomijane w widoku Assembly jako nieistotne do rozmieszczania "
        "komponentów — zostaje obrys, miedź zewnętrzna, silkscreen, pasta, courtyard i wiertła).",
    )
    parser.add_argument("-o", "--output", default=None, metavar="PLIK", help="Ścieżka wyjściowego pliku HTML (domyślnie <KATALOG>/report.html).")
    parser.add_argument("--report-id", default=None, help="Wymuś konkretne ID raportu (klucz localStorage) zamiast wyliczonego automatycznie.")
    return parser


@dataclass
class ResolvedInputs:
    gerber_paths: list[str]
    bom_path: Optional[str] = None
    pnp_paths: list[str] = field(default_factory=list)
    # Populated instead of bom_path/pnp_paths when several BOM files were
    # auto-detected as assembly variants of the same project (see
    # discovery.py) — label -> file path, and label -> matched
    # pick-and-place file(s) where one was found.
    bom_variants: dict[str, str] = field(default_factory=dict)
    pnp_variants: dict[str, list[str]] = field(default_factory=dict)


def _resolve_inputs(args: argparse.Namespace, project_dir: Path) -> Optional[ResolvedInputs]:
    """Fills in --gerber/--bom/--pnp from auto-discovery where omitted.
    Returns None (after printing an error) if something required is
    still missing.
    """
    need_discovery = args.gerber is None or args.bom is None or args.pnp is None
    discovered = discover_project_files(project_dir) if need_discovery else None

    def _rel(p: str) -> str:
        try:
            return str(Path(p).relative_to(project_dir))
        except ValueError:
            return p

    gerber_paths = args.gerber
    if gerber_paths is None:
        gerber_paths = discovered.gerber_paths
        if gerber_paths:
            print(f"Auto-wykryto {len(gerber_paths)} plik(ów) Gerber w '{project_dir}' (przeszukano wszystkie podfoldery): " + ", ".join(_rel(p) for p in gerber_paths))

    bom_path = args.bom
    bom_variants: dict[str, str] = {}
    pnp_variants: dict[str, list[str]] = {}
    if bom_path is None:
        bom_path = discovered.bom_path
        if bom_path:
            print(f"Auto-wykryto plik BOM: {_rel(bom_path)}")
        elif discovered.bom_variants:
            bom_variants = discovered.bom_variants
            pnp_variants = discovered.pnp_variants
            print(f"Auto-wykryto {len(bom_variants)} wariantów montażu: " + ", ".join(sorted(bom_variants)))

    pnp_paths = args.pnp
    if pnp_paths is None:
        pnp_paths = [] if bom_variants else discovered.pnp_paths
        if pnp_paths:
            print(f"Auto-wykryto plik(i) pick-and-place: " + ", ".join(_rel(p) for p in pnp_paths))

    if need_discovery:
        for warning in discovered.warnings:
            print(f"  ⚠ {warning}", file=sys.stderr)

    errors = []
    if need_discovery:
        # Discovery's own errors already explain a missing Gerber set or an
        # unresolvable BOM; only surface the ones for pieces that weren't
        # given explicitly (an explicit --bom/--gerber can't itself be
        # "missing"), and never for BOM once variants cover it.
        for err in discovered.errors:
            if "BOM" in err and (args.bom is not None or bom_variants):
                continue
            if "Gerber" in err and args.gerber is not None:
                continue
            errors.append(err)
    elif not gerber_paths:
        errors.append("Nie podano żadnych plików Gerber. Użyj --gerber.")
    elif not bom_path:
        errors.append("Nie podano pliku BOM. Użyj --bom.")

    if errors:
        for err in errors:
            print(f"Błąd: {err}", file=sys.stderr)
        return None

    return ResolvedInputs(
        gerber_paths=gerber_paths,
        bom_path=bom_path,
        pnp_paths=pnp_paths or [],
        bom_variants=bom_variants,
        pnp_variants=pnp_variants,
    )


_DEFAULT_VARIANT_PREFERENCE = [
    "podstawowy", "domyslny", "domyśny", "domyślny", "pelny", "pełny",
    "full", "novariations", "default", "all",
]


def _pick_default_variant(names: list[str]) -> str:
    """Prefers a variant that looks like "everything"/"no variant applied"
    (by common naming across Altium/company templates) as the one selected
    by default when a report first opens; falls back to alphabetical order
    when nothing recognizable is found."""
    compacted = {name: re.sub(r"[^a-z0-9]", "", name.lower()) for name in names}
    for pref in _DEFAULT_VARIANT_PREFERENCE:
        for name, c in compacted.items():
            if c == pref:
                return name
    return sorted(names)[0]


def _load_variant(name: str, bom_path: str, pnp_paths: list[str], unit: str) -> BomVariant:
    print(f"Parsowanie BOM (wariant '{name}'): {bom_path}")
    components, bom_warnings = parse_bom_file(bom_path)
    for warning in bom_warnings:
        print(f"  ⚠ {warning}", file=sys.stderr)
    print(f"  → {len(components)} pozycji BOM ({sum(len(c.designators) for c in components)} oznaczeń)")

    placements: dict[str, Placement] = {}
    if pnp_paths:
        for pnp_path in pnp_paths:
            print(f"Parsowanie pick-and-place (wariant '{name}'): {pnp_path}")
            placement_list, pnp_warnings = parse_placement_file(pnp_path, unit=unit)
            for warning in pnp_warnings:
                print(f"  ⚠ {warning}", file=sys.stderr)
            for p in placement_list:
                placements[p.designator] = p
        print(f"  → {len(placements)} pozycji łącznie")

        all_designators = {d for c in components for d in c.designators}
        missing = sorted(all_designators - set(placements.keys()))
        if missing:
            print(f"  ⚠ Brak pozycji dla {len(missing)} oznaczeń (można ustawić ręcznie w raporcie): {', '.join(missing[:20])}" + (" ..." if len(missing) > 20 else ""), file=sys.stderr)
    else:
        print(f"  Brak dopasowanego pliku pick-and-place dla wariantu '{name}' — komponenty trzeba będzie pozycjonować ręcznie w raporcie.")

    return BomVariant(name=name, components=components, placements=placements, source_bom=bom_path, source_pnp=pnp_paths)


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    project_dir = Path(args.project)
    if not project_dir.is_dir():
        print(f"Błąd: katalog nie istnieje: {project_dir}", file=sys.stderr)
        return 1

    resolved = _resolve_inputs(args, project_dir)
    if resolved is None:
        return 1

    paths_to_check = [*resolved.gerber_paths]
    if resolved.bom_variants:
        paths_to_check += list(resolved.bom_variants.values())
        paths_to_check += [p for paths in resolved.pnp_variants.values() for p in paths]
    else:
        paths_to_check += [resolved.bom_path, *resolved.pnp_paths]
    for path in paths_to_check:
        if not Path(path).is_file():
            print(f"Błąd: plik nie istnieje: {path}", file=sys.stderr)
            return 1

    variants: dict[str, BomVariant] = {}
    if resolved.bom_variants:
        for name in sorted(resolved.bom_variants):
            variants[name] = _load_variant(
                name, resolved.bom_variants[name], resolved.pnp_variants.get(name, []), args.unit
            )
        default_variant = _pick_default_variant(list(variants))
    else:
        variants["Domyślny"] = _load_variant("Domyślny", resolved.bom_path, resolved.pnp_paths, args.unit)
        default_variant = "Domyślny"

    # Shape-matching (real silkscreen/courtyard outlines) is a property of
    # the physical board, not of which variant is being assembled, so it
    # runs once against every placement from every variant combined.
    merged_placements: dict[str, Placement] = {}
    for variant in variants.values():
        merged_placements.update(variant.placements)

    print(f"Renderowanie {len(resolved.gerber_paths)} plik(ów) Gerber...")
    gerber_result: GerberRenderResult = render_gerber_files(
        resolved.gerber_paths, all_layers=args.all_layers, placements=merged_placements
    )
    for warning in gerber_result.warnings:
        print(f"  ⚠ {warning}", file=sys.stderr)
    if gerber_result.component_shapes:
        print(f"  → dopasowano realny obrys silkscreen/courtyard dla {len(gerber_result.component_shapes)} komponentów")

    html = build_report_html(
        gerber_paths=resolved.gerber_paths,
        gerber_result=gerber_result,
        variants=variants,
        default_variant=default_variant,
        report_id=args.report_id,
    )

    output_path = Path(args.output) if args.output else project_dir / "report.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"\nGotowe: {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
