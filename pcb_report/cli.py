"""Command-line entry point.

    python -m pcb_report --gerber f1.gbr f2.gbr ... --bom bom.csv --pnp pnp.csv -o report.html
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .bom import parse_bom_file
from .gerber import render_gerber_files
from .models import GerberRenderResult
from .placement import parse_placement_file
from .report import build_report_html


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pcb_report",
        description="Generuje statyczny, interaktywny raport HTML (Assembly + Traceability) z plików Gerber, BOM i pick-and-place.",
    )
    parser.add_argument("--gerber", nargs="+", required=True, metavar="PLIK", help="Pliki Gerber/Excellon (RS-274X).")
    parser.add_argument("--bom", required=True, metavar="PLIK", help="Plik BOM (.csv lub .xml).")
    parser.add_argument("--pnp", metavar="PLIK", help="Plik pick-and-place (.csv), opcjonalny.")
    parser.add_argument("--unit", choices=["mm", "inch"], default="mm", help="Jednostki współrzędnych w pliku pick-and-place (domyślnie mm).")
    parser.add_argument("-o", "--output", default="report.html", metavar="PLIK", help="Ścieżka wyjściowego pliku HTML (domyślnie report.html).")
    parser.add_argument("--report-id", default=None, help="Wymuś konkretne ID raportu (klucz localStorage) zamiast wyliczonego automatycznie.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    for path in [*args.gerber, args.bom, *([args.pnp] if args.pnp else [])]:
        if not Path(path).is_file():
            print(f"Błąd: plik nie istnieje: {path}", file=sys.stderr)
            return 1

    print(f"Renderowanie {len(args.gerber)} plik(ów) Gerber...")
    gerber_result: GerberRenderResult = render_gerber_files(args.gerber)
    for warning in gerber_result.warnings:
        print(f"  ⚠ {warning}", file=sys.stderr)

    print(f"Parsowanie BOM: {args.bom}")
    components, bom_warnings = parse_bom_file(args.bom)
    for warning in bom_warnings:
        print(f"  ⚠ {warning}", file=sys.stderr)
    print(f"  → {len(components)} pozycji BOM ({sum(len(c.designators) for c in components)} oznaczeń)")

    placements = {}
    if args.pnp:
        print(f"Parsowanie pick-and-place: {args.pnp}")
        placement_list, pnp_warnings = parse_placement_file(args.pnp, unit=args.unit)
        for warning in pnp_warnings:
            print(f"  ⚠ {warning}", file=sys.stderr)
        placements = {p.designator: p for p in placement_list}
        print(f"  → {len(placements)} pozycji")

        all_designators = {d for c in components for d in c.designators}
        missing = sorted(all_designators - set(placements.keys()))
        if missing:
            print(f"  ⚠ Brak pozycji dla {len(missing)} oznaczeń (można ustawić ręcznie w raporcie): {', '.join(missing[:20])}" + (" ..." if len(missing) > 20 else ""), file=sys.stderr)
    else:
        print("Brak pliku pick-and-place — wszystkie komponenty trzeba będzie pozycjonować ręcznie w raporcie.")

    html = build_report_html(
        gerber_paths=args.gerber,
        gerber_result=gerber_result,
        components=components,
        placements=placements,
        report_id=args.report_id,
    )

    output_path = Path(args.output)
    output_path.write_text(html, encoding="utf-8")
    print(f"\nGotowe: {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
