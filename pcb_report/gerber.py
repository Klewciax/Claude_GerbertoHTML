"""Render Gerber/Excellon files to a composite SVG, pure Python.

Uses `gerbonara <https://gitlab.com/gerbolyze/gerbonara>`_ to parse each
file's RS-274X/Excellon geometry individually (its per-file API handles
arbitrary filenames/subsets without complaint), then composites the
per-file SVG fragments onto one shared canvas ourselves. This sidesteps
gerbonara's higher-level ``LayerStack.from_files``, which only resolves
layer identities for a near-complete, conventionally-named fabrication
set (7+ files) — too strict for a tool that should render whatever subset
of Gerbers a user hands it.

Layer type/side (copper/mask/silk/paste/outline/drill, top/bottom) is
guessed from each filename via a small heuristic covering the common
KiCad/Altium/Eagle naming conventions. This is simpler than a dedicated
layer-identification library, so unusual naming schemes may be
misclassified — the file's geometry is still rendered either way (as an
"unknown" layer in a neutral color, shown on both sides), just without
the right color/side.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .models import GerberRenderResult, ViewBox

try:
    from gerbonara.excellon import ExcellonFile
    from gerbonara.rs274x import GerberFile

    _GERBONARA_IMPORT_ERROR: Optional[BaseException] = None
except Exception as _exc:  # pragma: no cover - exercised only when the dependency is missing
    ExcellonFile = GerberFile = None  # type: ignore[assignment]
    _GERBONARA_IMPORT_ERROR = _exc

LayerType = str  # 'copper' | 'mask' | 'silk' | 'paste' | 'outline' | 'drill' | 'unknown'
Side = str  # 'top' | 'bottom' | 'all'

_COLORS: dict[LayerType, str] = {
    "copper": "#c9a06a",
    "mask": "#1d5f3a",
    "silk": "#f2f2f2",
    "paste": "#9aa0a6",
    "drill": "#1a1a1a",
    "outline": "#f0c000",
    "unknown": "#8fa0b3",
}
_OPACITY: dict[LayerType, float] = {
    "copper": 0.92,
    "mask": 0.5,
    "silk": 0.9,
    "paste": 0.75,
    "drill": 1.0,
    "outline": 1.0,
    "unknown": 0.55,
}
# Draw order, bottom to top.
_Z_ORDER: list[LayerType] = ["unknown", "copper", "mask", "paste", "silk", "outline", "drill"]

_TOP_EXTENSIONS = {"gtl", "gts", "gto", "gtp"}
_BOTTOM_EXTENSIONS = {"gbl", "gbs", "gbo", "gbp"}
_DRILL_EXTENSIONS = {"drl", "xnc", "tho", "thd", "nc"}

_INNER_G_RE = re.compile(r"<g\s+transform=\"[^\"]*\">(.*)</g>\s*</svg>", re.DOTALL)


def _extension(name: str) -> str:
    return name.lower().rsplit(".", 1)[-1] if "." in name else ""


def _classify_type(name: str) -> LayerType:
    n = name.lower()
    ext = _extension(n)
    if ext in ("gtl", "gbl") or re.search(r"[-_.]cu\b", n) or "copper" in n:
        return "copper"
    if ext in ("gts", "gbs") or "mask" in n or "resist" in n:
        return "mask"
    if ext in ("gto", "gbo") or "silk" in n:
        return "silk"
    if ext in ("gtp", "gbp") or "paste" in n:
        return "paste"
    if ext in ("gko", "gm1") or "outline" in n or "edge" in n or "cuts" in n or "profile" in n:
        return "outline"
    if ext in _DRILL_EXTENSIONS or "drill" in n or "drl" in n:
        return "drill"
    return "unknown"


def _classify_side(name: str) -> Side:
    n = name.lower()
    ext = _extension(n)
    if ext in _TOP_EXTENSIONS:
        return "top"
    if ext in _BOTTOM_EXTENSIONS:
        return "bottom"
    if re.search(r"(^|[-_.])f([-_.]|$)", n) or "top" in n:
        return "top"
    if re.search(r"(^|[-_.])b([-_.]|$)", n) or "bot" in n:
        return "bottom"
    return "all"


def _recolor(svg_body: str) -> str:
    # Individual shapes hardcode fill/stroke="black" (drawn) or "white"
    # (cleared, from negative-polarity apertures). Swap "black" for
    # currentColor so our wrapping <g style="color:..."> controls the
    # palette, and treat "white" as fully transparent so a clear region in
    # one layer doesn't paint an opaque patch over layers beneath it in
    # the composite.
    svg_body = re.sub(r'(fill|stroke)="black"', r'\1="currentColor"', svg_body)
    svg_body = re.sub(r'(fill|stroke)="white"', r'\1="none"', svg_body)
    return svg_body


class _ParsedFile:
    def __init__(self, path: str, layer_type: LayerType, side: Side, bbox: tuple, body: str):
        self.path = path
        self.layer_type = layer_type
        self.side = side
        self.bbox = bbox  # ((minx, miny), (maxx, maxy))
        self.body = body


def _open_gerber_or_excellon(path: str):
    try:
        return GerberFile.open(path)
    except Exception:
        pass
    return ExcellonFile.open(path)


def _parse_file(path: str, warnings: list[str]) -> Optional[_ParsedFile]:
    name = Path(path).name
    try:
        parsed = _open_gerber_or_excellon(path)
    except Exception as exc:
        warnings.append(f"Nie udało się odczytać pliku {name}: {exc}")
        return None

    try:
        if parsed.is_empty:
            return None
        bbox = parsed.bounding_box()
        if bbox is None:
            return None
        svg = str(parsed.to_svg())
    except Exception as exc:
        warnings.append(f"Nie udało się wyrenderować pliku {name}: {exc}")
        return None

    match = _INNER_G_RE.search(svg)
    if not match:
        return None
    body = _recolor(match.group(1))

    layer_type = _classify_type(name)
    side = _classify_side(name)
    return _ParsedFile(path, layer_type, side, bbox, body)


def _union_bbox(files: list[_ParsedFile]) -> tuple[float, float, float, float]:
    (min_x, min_y), (max_x, max_y) = files[0].bbox
    for f in files[1:]:
        (fx0, fy0), (fx1, fy1) = f.bbox
        min_x, min_y = min(min_x, fx0), min(min_y, fy0)
        max_x, max_y = max(max_x, fx1), max(max_y, fy1)
    return min_x, min_y, max_x, max_y


def _composite(files: list[_ParsedFile], side: Side) -> Optional[str]:
    included = [f for f in files if f.side in (side, "all")]
    if not included:
        return None
    included.sort(key=lambda f: _Z_ORDER.index(f.layer_type) if f.layer_type in _Z_ORDER else 0)

    layers = []
    for f in included:
        color = _COLORS.get(f.layer_type, _COLORS["unknown"])
        opacity = _OPACITY.get(f.layer_type, _OPACITY["unknown"])
        layers.append(f'<g style="color:{color}" opacity="{opacity}">{f.body}</g>')

    return '<g transform="scale(1,-1)">' + "".join(layers) + "</g>"


def render_gerber_files(paths: list[str]) -> GerberRenderResult:
    if not paths:
        return GerberRenderResult(warnings=["Nie wskazano żadnych plików Gerber."])

    if _GERBONARA_IMPORT_ERROR is not None:
        return GerberRenderResult(
            warnings=[
                "Brak biblioteki 'gerbonara' — renderowanie plików Gerber jest niedostępne. "
                "Zainstaluj ją poleceniem 'pip install -e .' (z katalogu repozytorium) lub "
                f"'pip install gerbonara'. Szczegóły: {_GERBONARA_IMPORT_ERROR}"
            ]
        )

    warnings: list[str] = []
    parsed_files: list[_ParsedFile] = []
    for path in paths:
        result = _parse_file(path, warnings)
        if result:
            parsed_files.append(result)

    if not parsed_files:
        warnings.append("Żaden z wybranych plików nie został rozpoznany jako plik Gerber/Excellon z geometrią.")
        return GerberRenderResult(warnings=warnings)

    unknown = [f.path for f in parsed_files if f.layer_type == "unknown"]
    if unknown:
        warnings.append(
            "Nie rozpoznano typu warstwy dla: "
            + ", ".join(Path(p).name for p in unknown)
            + " — plik(i) wyrenderowano w neutralnym kolorze na obu stronach płytki."
        )

    min_x, min_y, max_x, max_y = _union_bbox(parsed_files)
    view_box = ViewBox(x=min_x, y=-max_y, width=max_x - min_x, height=max_y - min_y)

    top_svg = _composite(parsed_files, "top")
    bottom_svg = _composite(parsed_files, "bottom")

    if not top_svg and not bottom_svg:
        warnings.append("Renderowanie nie zwróciło żadnej grafiki dla żadnej ze stron płytki.")

    return GerberRenderResult(top_svg=top_svg, bottom_svg=bottom_svg, view_box=view_box, warnings=warnings)
