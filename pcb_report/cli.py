"""Command-line entry point.

    python -m pcb_report [KATALOG_PROJEKTU] [--gerber f1.gbr f2.gbr ...] [--bom bom.csv] [--pnp pnp.csv ...] [-o report.html]

Gerber/BOM/pick-and-place są auto-wykrywane w KATALOGU_PROJEKTU (domyślnie
bieżący katalog) kiedy odpowiedni argument nie jest podany jawnie — patrz
discovery.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .bom import parse_bom_file
from .discovery import discover_project_files
from .gerber import render_gerber_files
from .models import GerberRenderResult, Placement
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
    parser.add_argument("--pnp", nargs="+", metavar="PLIK", default=None, help="Plik(i) pick-and-place (.csv) — więcej niż jeden dla oddzielnych raportów Top/Bottom. Pominięcie = auto-wykrywanie w KATALOGU.")
    parser.add_argument("--unit", choices=["mm", "inch"], default="mm", help="Jednostki współrzędnych w pliku pick-and-place (domyślnie mm).")
    parser.add_argument(
        "--all-layers",
        action="store_true",
        help="Renderuj też miedź i maskę lutowniczą (domyślnie pomijane w widoku Assembly jako nieistotne "
        "do rozmieszczania komponentów — zostaje obrys, silkscreen, pasta, courtyard i wiertła).",
    )
    parser.add_argument("-o", "--output", default=None, metavar="PLIK", help="Ścieżka wyjściowego pliku HTML (domyślnie <KATALOG>/report.html).")
    parser.add_argument("--report-id", default=None, help="Wymuś konkretne ID raportu (klucz localStorage) zamiast wyliczonego automatycznie.")
    return parser


def _resolve_inputs(args: argparse.Namespace, project_dir: Path) -> tuple[list[str], str, list[str]] | None:
    """Fills in --gerber/--bom/--pnp from auto-discovery where omitted.
    Returns None (after printing an error) if something required is
    still missing or ambiguous.
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
    if bom_path is None:
        bom_path = discovered.bom_path
        if bom_path:
            print(f"Auto-wykryto plik BOM: {_rel(bom_path)}")

    pnp_paths = args.pnp
    if pnp_paths is None:
        pnp_paths = discovered.pnp_paths
        if pnp_paths:
            print(f"Auto-wykryto plik(i) pick-and-place: " + ", ".join(_rel(p) for p in pnp_paths))

    if need_discovery:
        for warning in discovered.warnings:
            print(f"  ⚠ {warning}", file=sys.stderr)

    errors = []
    if need_discovery:
        # Discovery's own errors already explain a missing/ambiguous BOM or
        # Gerber set; only surface the ones for pieces that weren't given
        # explicitly (an explicit --bom/--gerber can't itself be "missing").
        for err in discovered.errors:
            if "BOM" in err and args.bom is not None:
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

    return gerber_paths, bom_path, (pnp_paths or [])


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    project_dir = Path(args.project)
    if not project_dir.is_dir():
        print(f"Błąd: katalog nie istnieje: {project_dir}", file=sys.stderr)
        return 1

    resolved = _resolve_inputs(args, project_dir)
    if resolved is None:
        return 1
    gerber_paths, bom_path, pnp_paths = resolved

    for path in [*gerber_paths, bom_path, *pnp_paths]:
        if not Path(path).is_file():
            print(f"Błąd: plik nie istnieje: {path}", file=sys.stderr)
            return 1

    print(f"Parsowanie BOM: {bom_path}")
    components, bom_warnings = parse_bom_file(bom_path)
    for warning in bom_warnings:
        print(f"  ⚠ {warning}", file=sys.stderr)
    print(f"  → {len(components)} pozycji BOM ({sum(len(c.designators) for c in components)} oznaczeń)")

    placements: dict[str, Placement] = {}
    if pnp_paths:
        for pnp_path in pnp_paths:
            print(f"Parsowanie pick-and-place: {pnp_path}")
            placement_list, pnp_warnings = parse_placement_file(pnp_path, unit=args.unit)
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
        print("Brak pliku pick-and-place — wszystkie komponenty trzeba będzie pozycjonować ręcznie w raporcie.")

    print(f"Renderowanie {len(gerber_paths)} plik(ów) Gerber...")
    gerber_result: GerberRenderResult = render_gerber_files(gerber_paths, all_layers=args.all_layers, placements=placements)
    for warning in gerber_result.warnings:
        print(f"  ⚠ {warning}", file=sys.stderr)
    if gerber_result.component_shapes:
        print(f"  → dopasowano realny obrys silkscreen/courtyard dla {len(gerber_result.component_shapes)} komponentów")

    html = build_report_html(
        gerber_paths=gerber_paths,
        gerber_result=gerber_result,
        components=components,
        placements=placements,
        report_id=args.report_id,
    )

    output_path = Path(args.output) if args.output else project_dir / "report.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"\nGotowe: {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
