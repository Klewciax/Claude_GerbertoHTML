"""Command-line entry point.

    python -m pcb_report [PROJECT_DIR] [--gerber f1.gbr f2.gbr ...] [--bom bom.csv] [--pnp pnp.csv ...] [-o report.html]

Gerber/BOM/pick-and-place files are auto-detected in PROJECT_DIR (defaults to
the current directory) when the corresponding argument isn't given explicitly
-- see discovery.py.
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
        description="Generates a static, interactive HTML report (Assembly + Traceability) from Gerber, BOM and pick-and-place files.",
    )
    parser.add_argument(
        "project",
        nargs="?",
        default=".",
        metavar="DIR",
        help="Project directory to search (defaults to the current directory). Gerber/BOM/pick-and-place "
        "files not given explicitly below are auto-detected in it.",
    )
    parser.add_argument("--gerber", nargs="+", metavar="FILE", default=None, help="Gerber/Excellon files (RS-274X). Omit to auto-detect in DIR.")
    parser.add_argument("--bom", metavar="FILE", default=None, help="BOM file (.csv, .xml or .xlsx). Omit to auto-detect in DIR.")
    parser.add_argument("--pnp", nargs="+", metavar="FILE", default=None, help="Pick-and-place file(s) (.csv) — more than one for separate Top/Bottom reports (will be merged). Omit to auto-detect in DIR (also covers assembly-variant detection, see README).")
    parser.add_argument("--unit", choices=["mm", "inch"], default="mm", help="Coordinate units in the pick-and-place file (default mm).")
    parser.add_argument(
        "--all-layers",
        action="store_true",
        help="By default, only the layers needed for assembly (outline, silkscreen, paste, courtyard, "
        "drill holes) are checked in the report's 'Layers' panel — mask, copper (outer and inner) and "
        "other mechanical/unrecognized layers are loaded but left unchecked. This flag checks all of "
        "them right away, and also widens the set of files considered when auto-fitting the board view "
        "frame. Every layer can still be freely toggled directly in the report without this flag.",
    )
    parser.add_argument("-o", "--output", default=None, metavar="FILE", help="Output HTML file path (default <DIR>/report.html).")
    parser.add_argument("--report-id", default=None, help="Force a specific report ID (localStorage key) instead of the auto-computed one.")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Don't ask in the terminal about files whose purpose auto-detection couldn't recognize as "
        "BOM/pick-and-place (default: asks when run in an interactive terminal) — such files are then "
        "simply skipped, as before.",
    )
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
    discovered = discover_project_files(project_dir, interactive=not args.non_interactive) if need_discovery else None

    def _rel(p: str) -> str:
        try:
            return str(Path(p).relative_to(project_dir))
        except ValueError:
            return p

    gerber_paths = args.gerber
    if gerber_paths is None:
        gerber_paths = discovered.gerber_paths
        if gerber_paths:
            print(f"Auto-detected {len(gerber_paths)} Gerber file(s) in '{project_dir}' (searched all subfolders): " + ", ".join(_rel(p) for p in gerber_paths))

    bom_path = args.bom
    bom_variants: dict[str, str] = {}
    pnp_variants: dict[str, list[str]] = {}
    if bom_path is None:
        bom_path = discovered.bom_path
        if bom_path:
            print(f"Auto-detected BOM file: {_rel(bom_path)}")
        elif discovered.bom_variants:
            bom_variants = discovered.bom_variants
            pnp_variants = discovered.pnp_variants
            print(f"Auto-detected {len(bom_variants)} assembly variant(s): " + ", ".join(sorted(bom_variants)))

    pnp_paths = args.pnp
    if pnp_paths is None:
        pnp_paths = [] if bom_variants else discovered.pnp_paths
        if pnp_paths:
            print(f"Auto-detected pick-and-place file(s): " + ", ".join(_rel(p) for p in pnp_paths))

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
        errors.append("No Gerber files given. Use --gerber.")
    elif not bom_path:
        errors.append("No BOM file given. Use --bom.")

    if errors:
        for err in errors:
            print(f"Error: {err}", file=sys.stderr)
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
    print(f"Parsing BOM (variant '{name}'): {bom_path}")
    components, bom_warnings = parse_bom_file(bom_path)
    for warning in bom_warnings:
        print(f"  ⚠ {warning}", file=sys.stderr)
    print(f"  → {len(components)} BOM entries ({sum(len(c.designators) for c in components)} designators)")

    placements: dict[str, Placement] = {}
    if pnp_paths:
        for pnp_path in pnp_paths:
            print(f"Parsing pick-and-place (variant '{name}'): {pnp_path}")
            placement_list, pnp_warnings = parse_placement_file(pnp_path, unit=unit)
            for warning in pnp_warnings:
                print(f"  ⚠ {warning}", file=sys.stderr)
            for p in placement_list:
                placements[p.designator] = p
        print(f"  → {len(placements)} positions total")

        all_designators = {d for c in components for d in c.designators}
        missing = sorted(all_designators - set(placements.keys()))
        if missing:
            print(f"  ⚠ No position for {len(missing)} designators (can be set manually in the report): {', '.join(missing[:20])}" + (" ..." if len(missing) > 20 else ""), file=sys.stderr)
    else:
        print(f"  No matching pick-and-place file for variant '{name}' — components will need to be positioned manually in the report.")

    return BomVariant(name=name, components=components, placements=placements, source_bom=bom_path, source_pnp=pnp_paths)


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    project_dir = Path(args.project)
    if not project_dir.is_dir():
        print(f"Error: directory does not exist: {project_dir}", file=sys.stderr)
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
            print(f"Error: file does not exist: {path}", file=sys.stderr)
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

    print(f"Rendering {len(resolved.gerber_paths)} Gerber file(s)...")
    gerber_result: GerberRenderResult = render_gerber_files(
        resolved.gerber_paths, all_layers=args.all_layers, placements=merged_placements
    )
    for warning in gerber_result.warnings:
        print(f"  ⚠ {warning}", file=sys.stderr)
    if gerber_result.component_shapes:
        print(f"  → matched real silkscreen/courtyard outlines for {len(gerber_result.component_shapes)} components")

    html = build_report_html(
        gerber_paths=resolved.gerber_paths,
        gerber_result=gerber_result,
        variants=variants,
        default_variant=default_variant,
        report_id=args.report_id,
    )

    output_path = Path(args.output) if args.output else project_dir / "report.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"\nDone: {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
