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
import warnings as _py_warnings
from pathlib import Path
from typing import Optional

from .models import GerberRenderResult, Placement, ViewBox

try:
    from gerbonara.excellon import ExcellonFile
    from gerbonara.rs274x import GerberFile

    _GERBONARA_IMPORT_ERROR: Optional[BaseException] = None
except Exception as _exc:  # pragma: no cover - exercised only when the dependency is missing
    ExcellonFile = GerberFile = None  # type: ignore[assignment]
    _GERBONARA_IMPORT_ERROR = _exc

LayerType = str  # 'copper' | 'mask' | 'silk' | 'paste' | 'courtyard' | 'outline' | 'drill' | 'unknown'
Side = str  # 'top' | 'bottom' | 'all'

_COLORS: dict[LayerType, str] = {
    "copper": "#c9a06a",
    "mask": "#1d5f3a",
    "silk": "#f2f2f2",
    "paste": "#9aa0a6",
    "courtyard": "#5fb8d6",
    "drill": "#1a1a1a",
    "outline": "#f0c000",
    "mechanical": "#b46fc9",
    "unknown": "#8fa0b3",
}
_OPACITY: dict[LayerType, float] = {
    "copper": 0.92,
    "mask": 0.5,
    "silk": 0.9,
    "paste": 0.75,
    "courtyard": 0.8,
    "drill": 1.0,
    "outline": 1.0,
    "mechanical": 0.5,
    "unknown": 0.55,
}
# Draw order, bottom to top.
_Z_ORDER: list[LayerType] = ["unknown", "mechanical", "copper", "mask", "paste", "courtyard", "silk", "outline", "drill"]

# Layers actually useful for placing/checking components by hand. Copper
# and solder mask are fab/electrical detail that only clutters an assembly
# reference view, so they're left out unless --all-layers is passed.
# "mechanical" (see _classify_type) is excluded for the same reason: it's a
# positively-identified Altium GM<n> layer whose specific purpose (fab
# notes, dimensions, height restrictions, ...) is defined per-project and
# can't be inferred from the extension. "unknown" — a filename that doesn't
# match any recognized convention at all — stays included, since it might
# be someone's unconventionally-named board outline.
ASSEMBLY_RELEVANT_TYPES = {"outline", "silk", "paste", "courtyard", "drill", "unknown"}

_TOP_EXTENSIONS = {"gtl", "gts", "gto", "gtp"}
_BOTTOM_EXTENSIONS = {"gbl", "gbs", "gbo", "gbp"}
_DRILL_EXTENSIONS = {"drl", "xnc", "tho", "thd", "nc"}
# Altium mechanical layers: GM1 (and the GML extension some templates use
# instead) is conventionally the board outline; GM13/14 are top/bottom
# courtyard, GM15/16 top/bottom assembly (fabrication) — grouped with
# courtyard here since both serve the same "assembly reference outline"
# purpose. Any other GMxx is a real Altium mechanical layer but with
# unknown, project-specific purpose — see "mechanical" in _classify_type.
_COURTYARD_MECHANICAL_EXTENSIONS = {"gm13", "gm14", "gm15", "gm16"}
_GENERIC_MECHANICAL_RE = re.compile(r"gm\d+")
# Bare "G<n>" (no "M") is Altium's convention for internal copper signal
# layers (G1, G2, ...), distinct from "GM<n>" mechanical layers above.
_INNER_COPPER_RE = re.compile(r"g\d+")

_INNER_G_RE = re.compile(r"<g\s+transform=\"[^\"]*\">(.*)</g>\s*</svg>", re.DOTALL)


def _extension(name: str) -> str:
    return name.lower().rsplit(".", 1)[-1] if "." in name else ""


def _classify_type(name: str) -> LayerType:
    n = name.lower()
    ext = _extension(n)
    if ext in ("gko", "gm1", "gml") or "outline" in n or "edge" in n or "cuts" in n or "profile" in n:
        return "outline"
    if ext in _COURTYARD_MECHANICAL_EXTENSIONS or "courtyard" in n or "crtyd" in n:
        return "courtyard"
    if ext in ("gto", "gbo") or "silk" in n:
        return "silk"
    if ext in ("gtp", "gbp") or "paste" in n:
        return "paste"
    if ext in ("gts", "gbs") or "mask" in n or "resist" in n:
        return "mask"
    if (
        ext in ("gtl", "gbl")
        or _INNER_COPPER_RE.fullmatch(ext)
        or re.search(r"[-_.]cu\b", n)
        or "copper" in n
    ):
        return "copper"
    if ext in _DRILL_EXTENSIONS or "drill" in n or "drl" in n:
        return "drill"
    if _GENERIC_MECHANICAL_RE.fullmatch(ext):
        # A recognized Altium mechanical layer, but not one of the known
        # roles above (outline/courtyard) — its actual purpose (dimensions,
        # fab notes, height restrictions, ...) is defined per-project and
        # can't be guessed from the extension, so it's treated like
        # copper/mask: excluded from the default Assembly view (see
        # ASSEMBLY_RELEVANT_TYPES), shown only with --all-layers.
        return "mechanical"
    return "unknown"


_FILE_FUNCTION_TYPE_MAP: dict[str, LayerType] = {
    "copper": "copper",
    "soldermask": "mask",
    "legend": "silk",
    "paste": "paste",
    "courtyard": "courtyard",
    "assemblydrawing": "courtyard",
    "profile": "outline",
    "drill": "drill",
}


def _classify_from_attrs(file_attrs: dict) -> Optional[tuple[LayerType, Side]]:
    """Classify layer type/side from the Gerber X2 ``%TF.FileFunction,...*%``
    file attribute when present, instead of guessing from the filename.

    This is the standard, tool-independent way fab-export software (Altium,
    KiCad, ...) declares what a layer actually is, so it's far more
    reliable than filename heuristics — which can misclassify a layer as
    "unknown" (rendered by default, since an unrecognized file might be an
    unusually-named board outline) when it's actually copper/mask that
    should be excluded from the Assembly view.
    """
    values = file_attrs.get(".FileFunction")
    if not values:
        return None
    layer_type = _FILE_FUNCTION_TYPE_MAP.get(str(values[0]).strip().lower())
    if layer_type is None:
        return None
    side: Side = "all"
    for token in values[1:]:
        t = str(token).strip().lower()
        if t == "top":
            side = "top"
        elif t in ("bot", "bottom"):
            side = "bottom"
    return layer_type, side


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
    def __init__(self, path: str, layer_type: LayerType, side: Side, bbox: tuple, body: str, objects=None):
        self.path = path
        self.layer_type = layer_type
        self.side = side
        self.bbox = bbox  # ((minx, miny), (maxx, maxy))
        self.body = body
        self.objects = objects  # raw gerbonara GraphicObject list, only kept for silk/courtyard


def _try_open(opener, path: str):
    """Returns (parsed_or_None, warnings, exception_or_None)."""
    with _py_warnings.catch_warnings(record=True) as caught:
        _py_warnings.simplefilter("always")
        try:
            return opener(path), list(caught), None
        except Exception as exc:
            return None, list(caught), exc


def _open_gerber_or_excellon(path: str):
    """Returns (parsed, warnings). Tries RS-274X first, then Excellon.

    A file of the "wrong" kind often doesn't raise at all — e.g. an
    Excellon drill file can parse as a syntactically-empty Gerber (no
    recognized Gerber commands) instead of failing outright — so success
    alone isn't enough to pick a parser; whichever one yields real
    (non-empty) content wins.
    """
    gerber, gerber_warnings, gerber_exc = _try_open(GerberFile.open, path)
    if gerber is not None and not gerber.is_empty:
        return gerber, gerber_warnings

    excellon, excellon_warnings, excellon_exc = _try_open(ExcellonFile.open, path)
    if excellon is not None and not excellon.is_empty:
        return excellon, excellon_warnings

    if gerber is not None:
        return gerber, gerber_warnings
    if excellon is not None:
        return excellon, excellon_warnings
    raise gerber_exc or excellon_exc


def _parse_file(path: str, warnings: list[str]) -> Optional[_ParsedFile]:
    name = Path(path).name
    try:
        parsed, parse_warnings = _open_gerber_or_excellon(path)
    except Exception as exc:
        warnings.append(f"Nie udało się odczytać pliku {name}: {exc}")
        return None

    with _py_warnings.catch_warnings(record=True) as caught:
        _py_warnings.simplefilter("always")
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
        parse_warnings = parse_warnings + list(caught)

    for w in parse_warnings:
        warnings.append(f"{name}: {w.message}")

    match = _INNER_G_RE.search(svg)
    if not match:
        return None
    body = _recolor(match.group(1))

    from_attrs = _classify_from_attrs(getattr(parsed, "file_attrs", None) or {})
    if from_attrs is not None:
        layer_type, side = from_attrs
        if side == "all":
            # FileFunction declared a type but no top/bottom (e.g. an inner
            # copper layer, or a board-wide Profile) — filename may still
            # narrow the side down.
            side = _classify_side(name)
    else:
        layer_type = _classify_type(name)
        side = _classify_side(name)
    objects = getattr(parsed, "objects", None) if layer_type in ("silk", "courtyard") else None
    return _ParsedFile(path, layer_type, side, bbox, body, objects=objects)


def _union_bbox(files: list[_ParsedFile]) -> tuple[float, float, float, float]:
    (min_x, min_y), (max_x, max_y) = files[0].bbox
    for f in files[1:]:
        (fx0, fy0), (fx1, fy1) = f.bbox
        min_x, min_y = min(min_x, fx0), min(min_y, fy0)
        max_x, max_y = max(max_x, fx1), max(max_y, fy1)
    return min_x, min_y, max_x, max_y


# ---------------------------------------------------------------------
# Component outline matching: cluster individual silkscreen/courtyard
# primitives into per-component shapes, then match each to the nearest
# pick-and-place position, so the report can highlight a component's real
# drawn outline instead of a generic circle where possible.
# ---------------------------------------------------------------------
_CLUSTER_PAD_MM = 0.15
_MAX_CLUSTER_SIZE_MM = 60.0
_MAX_CLUSTER_OBJECTS = 3000


def _cluster_layer_objects(objects: list) -> list[dict]:
    items = []
    for o in objects:
        try:
            (x0, y0), (x1, y1) = o.bounding_box()
        except Exception:
            continue
        items.append((o, (x0, y0, x1, y1)))

    n = len(items)
    if n == 0 or n > _MAX_CLUSTER_OBJECTS:
        return []

    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    pad = _CLUSTER_PAD_MM
    for i in range(n):
        bi = items[i][1]
        for j in range(i + 1, n):
            bj = items[j][1]
            if not (bi[2] + pad < bj[0] or bj[2] + pad < bi[0] or bi[3] + pad < bj[1] or bj[3] + pad < bi[1]):
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    clusters = []
    for idxs in groups.values():
        b = items[idxs[0]][1]
        for k in idxs[1:]:
            ob = items[k][1]
            b = (min(b[0], ob[0]), min(b[1], ob[1]), max(b[2], ob[2]), max(b[3], ob[3]))
        w, h = b[2] - b[0], b[3] - b[1]
        if max(w, h) > _MAX_CLUSTER_SIZE_MM or max(w, h) <= 0:
            continue

        svg_parts = []
        for k in idxs:
            obj = items[k][0]
            try:
                for prim in obj.to_primitives():
                    svg_parts.append(str(prim.to_svg()))
            except Exception:
                continue
        if not svg_parts:
            continue

        clusters.append({
            "bbox": b,
            "center": ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2),
            "svg": _recolor("".join(svg_parts)),
        })
    return clusters


def _shape_candidates_by_side(parsed_files: list[_ParsedFile]) -> dict[Side, list[dict]]:
    def objects_for(layer_type: LayerType, side: Side) -> list:
        combined = []
        for f in parsed_files:
            if f.layer_type == layer_type and f.side in (side, "all") and f.objects:
                combined.extend(f.objects)
        return combined

    result: dict[Side, list[dict]] = {}
    for side in ("top", "bottom"):
        # Courtyard is preferred: it's normally just one clean outline per
        # component, whereas silkscreen also mixes in reference-designator
        # text and polarity marks that would otherwise pollute clustering.
        objs = objects_for("courtyard", side) or objects_for("silk", side)
        result[side] = _cluster_layer_objects(objs) if objs else []
    return result


def match_component_shapes(
    parsed_files: list[_ParsedFile], placements: dict[str, Placement]
) -> dict[str, str]:
    if not placements:
        return {}

    shapes_by_side = _shape_candidates_by_side(parsed_files)
    matches: dict[str, str] = {}

    for side, clusters in shapes_by_side.items():
        if not clusters:
            continue
        candidates = [p for p in placements.values() if p.side == side]
        if not candidates:
            continue

        triples = []
        for p in candidates:
            for ci, c in enumerate(clusters):
                dx = p.x - c["center"][0]
                dy = p.y - c["center"][1]
                dist = (dx * dx + dy * dy) ** 0.5
                diag = ((c["bbox"][2] - c["bbox"][0]) ** 2 + (c["bbox"][3] - c["bbox"][1]) ** 2) ** 0.5
                if dist <= max(diag, 1.0):
                    triples.append((dist, p.designator, ci))
        triples.sort(key=lambda t: t[0])

        claimed_clusters: set[int] = set()
        claimed_designators: set[str] = set()
        for _dist, designator, ci in triples:
            if designator in claimed_designators or ci in claimed_clusters:
                continue
            matches[designator] = clusters[ci]["svg"]
            claimed_clusters.add(ci)
            claimed_designators.add(designator)

    return matches


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


def render_gerber_files(
    paths: list[str],
    all_layers: bool = False,
    placements: Optional[dict[str, Placement]] = None,
) -> GerberRenderResult:
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

    if not all_layers:
        skipped_copper_mask = [f for f in parsed_files if f.layer_type in ("copper", "mask")]
        if skipped_copper_mask:
            warnings.append(
                "Pominięto w widoku Assembly warstwy miedzi/maski (nieistotne do rozmieszczania komponentów): "
                + ", ".join(Path(f.path).name for f in skipped_copper_mask)
                + ". Użyj --all-layers, aby jednak je pokazać."
            )
        skipped_mechanical = [f for f in parsed_files if f.layer_type == "mechanical"]
        if skipped_mechanical:
            warnings.append(
                "Pominięto inne warstwy mechaniczne Altium (przeznaczenie zależy od konkretnego projektu — "
                "wymiary, notatki fabrykacyjne itp.): "
                + ", ".join(Path(f.path).name for f in skipped_mechanical)
                + ". Użyj --all-layers, aby jednak je pokazać."
            )
        parsed_files = [f for f in parsed_files if f.layer_type in ASSEMBLY_RELEVANT_TYPES]

    if not parsed_files:
        warnings.append(
            "Po odfiltrowaniu warstw miedzi/maski nie zostały żadne pliki do wyrenderowania "
            "(brak obrysu/silkscreenu/courtyard) — użyj --all-layers albo dodaj plik obrysu płytki."
        )
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

    component_shapes: dict[str, str] = {}
    if placements:
        try:
            component_shapes = match_component_shapes(parsed_files, placements)
        except Exception as exc:
            warnings.append(f"Nie udało się dopasować realnych obrysów komponentów, użyto znaczników zastępczych: {exc}")

    return GerberRenderResult(
        top_svg=top_svg,
        bottom_svg=bottom_svg,
        view_box=view_box,
        warnings=warnings,
        component_shapes=component_shapes,
    )
