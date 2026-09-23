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

from .models import GerberLayer, GerberRenderResult, Placement, ViewBox

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
    "inner_copper": "#8a6b45",
    "mask": "#1d5f3a",
    "silk": "#f2f2f2",
    "paste": "#c9a878",
    "courtyard": "#5fb8d6",
    "drill": "#1a1a1a",
    "outline": "#f0c000",
    "mechanical": "#b46fc9",
    "unknown": "#8fa0b3",
}
# With every layer now visible by default (see ASSEMBLY_RELEVANT_TYPES),
# silk and courtyard need a top/bottom-distinct color each -- otherwise a
# top and a bottom file of the same type render identically and are only
# tellable apart by reading their name in the layer panel.
_SIDE_COLOR_OVERRIDES: dict[tuple[str, str], str] = {
    ("silk", "top"): "#f2f2f2",
    ("silk", "bottom"): "#f2d9a8",
    ("courtyard", "top"): "#5fb8d6",
    ("courtyard", "bottom"): "#d65fb8",
}


def _layer_color(layer_type: str, side: str) -> str:
    return _SIDE_COLOR_OVERRIDES.get((layer_type, side), _COLORS.get(layer_type, _COLORS["unknown"]))
_OPACITY: dict[LayerType, float] = {
    "copper": 0.92,
    "inner_copper": 0.5,
    "mask": 0.5,
    "silk": 1.0,
    "paste": 0.75,
    "courtyard": 0.8,
    "drill": 1.0,
    "outline": 1.0,
    "mechanical": 0.5,
    "unknown": 0.55,
}
# Draw order, bottom to top.
_Z_ORDER: list[LayerType] = [
    "unknown", "mechanical", "inner_copper", "copper", "mask", "paste", "courtyard", "silk", "outline", "drill",
]

# Layers actually useful for placing/checking components by hand. The outer
# copper layer (top/bottom) is included: its pads are literally the
# component footprints, which is the clearest visual cue for "where does
# this part go" — confirmed by comparing against a manual KiCad layer
# selection. Only *inner* (buried) copper is left out, since it's not
# visible on either surface and irrelevant to placement; solder mask is
# also left out (just a tint, adds nothing here). "mechanical" (see
# _classify_type) is excluded too: it's a positively-identified Altium
# GM<n> layer whose specific purpose (fab notes, dimensions, height
# restrictions, ...) is defined per-project and can't be inferred from the
# extension. "unknown" — a filename that doesn't match any recognized
# convention at all — stays included, since it might be someone's
# unconventionally-named board outline. All of the above are still
# available via --all-layers.
ASSEMBLY_RELEVANT_TYPES = {"outline", "silk", "paste", "copper", "courtyard", "drill", "unknown"}

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
# Bare "G<n>" (no "M") is Altium's convention for internal (buried) copper
# signal layers (G1, G2, ...), distinct from outer .GTL/.GBL and from
# "GM<n>" mechanical layers above.
_INNER_COPPER_RE = re.compile(r"g\d+")
# KiCad's convention for an inner copper layer, e.g. "board-In1-Cu.gbr" /
# "board-In2_Cu.gbr" — as opposed to "-F.Cu"/"-B.Cu" for the outer layers.
_KICAD_INNER_COPPER_RE = re.compile(r"in\d+[-_.]?cu")

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
    if _INNER_COPPER_RE.fullmatch(ext) or _KICAD_INNER_COPPER_RE.search(n) or "inner" in n:
        return "inner_copper"
    if ext in ("gtl", "gbl") or re.search(r"[-_.]cu\b", n) or "copper" in n:
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
    is_inner = False
    for token in values[1:]:
        t = str(token).strip().lower()
        if t == "top":
            side = "top"
        elif t in ("bot", "bottom"):
            side = "bottom"
        elif t in ("inr", "inner"):
            is_inner = True
    if layer_type == "copper" and is_inner:
        # A buried signal layer (Gerber X2's "Inr" token) — not visible on
        # either surface, so it's a different, always-excluded-by-default
        # category from the outer copper layer (see ASSEMBLY_RELEVANT_TYPES).
        layer_type = "inner_copper"
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


_CLEAR_POLARITY_RE = re.compile(r'(?:fill|stroke)="white"')


def _recolor(svg_body: str) -> str:
    # Individual shapes hardcode fill/stroke="black" (drawn, "dark" gerber
    # polarity) or "white" (drawn, "clear" polarity -- gerber's own
    # mechanism for punching a hole in geometry already drawn earlier in
    # the same file, e.g. the counter of a "0" or the bowl of an "R" when
    # a font is exported as filled vector-outline regions rather than pen
    # strokes, which is how Altium/KiCad export a TrueType-derived
    # silkscreen font). Swap "black" for currentColor so our wrapping
    # <g style="color:..."> controls the palette. "white" is turned into
    # "none" here -- fine for a file with no clear-polarity shapes at all,
    # but for one that actually has them, _build_layers takes the mask
    # path below instead of calling this, since "none" only makes the
    # clear shape invisible, it doesn't erase what's underneath it.
    svg_body = re.sub(r'(fill|stroke)="black"', r'\1="currentColor"', svg_body)
    svg_body = re.sub(r'(fill|stroke)="white"', r'\1="none"', svg_body)
    return svg_body


def _mask_luminance_recolor(svg_body: str) -> str:
    """Prepares svg_body to be used as the content of an SVG <mask>, where
    luminance decides visibility (white = shown, black = hidden). Gerber's
    "dark" polarity (black in gerbonara's own SVG) should end up visible in
    the mask, so it becomes white; "clear" polarity (white) should
    genuinely hide whatever came before it, so it becomes black. Element
    order is unchanged, so a clear shape correctly punches through only
    the dark shapes already drawn earlier in the same file -- exactly
    gerber's own polarity semantics, just expressed as a mask instead of
    (incorrectly) as plain painter's-algorithm opacity."""

    def _swap(match: re.Match) -> str:
        attr, value = match.group(1), match.group(2)
        return f'{attr}="{"white" if value == "black" else "black"}"'

    return re.sub(r'(fill|stroke)="(black|white)"', _swap, svg_body)


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
    # Kept raw (not yet recolored) -- _build_layers needs to see the real
    # black/white fills to decide whether this file needs the mask-based
    # render path (see _mask_luminance_recolor).
    body = match.group(1)

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


def _build_layers(files: list[_ParsedFile], all_layers: bool) -> list[GerberLayer]:
    """One GerberLayer per input file, in draw (z-)order, each independently
    shown/hidden client-side — see GerberLayer's docstring for why this
    isn't pre-filtered/merged server-side any more."""
    ordered = sorted(files, key=lambda f: _Z_ORDER.index(f.layer_type) if f.layer_type in _Z_ORDER else 0)
    layers = []
    for i, f in enumerate(ordered):
        color = _layer_color(f.layer_type, f.side)
        opacity = _OPACITY.get(f.layer_type, _OPACITY["unknown"])
        if _CLEAR_POLARITY_RE.search(f.body):
            # This file actually uses clear polarity somewhere (common for
            # silkscreen text exported as filled vector-outline regions,
            # and for some copper/mask clearance regions) -- render it as a
            # single solid rect of the layer's color, masked by its own
            # geometry, so a clear shape genuinely punches a hole instead
            # of just becoming invisible. Skipped for files without any
            # clear-polarity shapes (the overwhelming majority) since it
            # roughly doubles this layer's SVG size.
            (min_x, min_y), (max_x, max_y) = f.bbox
            pad = 0.5  # mm -- stroke width extends past the raw bbox
            mx, my = min_x - pad, min_y - pad
            mw, mh = (max_x - min_x) + 2 * pad, (max_y - min_y) + 2 * pad
            mask_id = f"gmask{i}"
            mask_body = _mask_luminance_recolor(f.body)
            svg = (
                f'<g transform="scale(1,-1)">'
                f'<mask id="{mask_id}" maskUnits="userSpaceOnUse" '
                f'x="{mx:.4f}" y="{my:.4f}" width="{mw:.4f}" height="{mh:.4f}">{mask_body}</mask>'
                f'<rect x="{mx:.4f}" y="{my:.4f}" width="{mw:.4f}" height="{mh:.4f}" '
                f'fill="{color}" opacity="{opacity}" mask="url(#{mask_id})" />'
                f'</g>'
            )
        else:
            body = _recolor(f.body)
            svg = f'<g transform="scale(1,-1)"><g style="color:{color}" opacity="{opacity}">{body}</g></g>'
        layers.append(
            GerberLayer(
                name=Path(f.path).name,
                layer_type=f.layer_type,
                side=f.side,
                svg=svg,
                # Every parsed layer is visible by default now -- the color
                # (see _layer_color) is what tells them apart instead of
                # hiding the less commonly needed ones (mask, inner copper,
                # mechanical/margin). `all_layers` is kept only so
                # --all-layers stays a harmless no-op for anyone still
                # passing it.
                default_visible=True,
            )
        )
    return layers


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

    # Every layer is visible by default in the report now (see
    # GerberLayer.default_visible in _build_layers) -- this set is only
    # used to decide which files anchor the auto-fit view frame, so a
    # handful of outsized/oddly-placed mechanical or mask files (a real
    # thing in practical Altium projects) can't distort the initial zoom
    # of the *whole* board. --all-layers widens that anchor set to
    # everything too, for a project where those actually matter for framing.
    bbox_anchor_files = parsed_files if all_layers else [f for f in parsed_files if f.layer_type in ASSEMBLY_RELEVANT_TYPES]

    unknown = [f.path for f in parsed_files if f.layer_type == "unknown"]
    if unknown:
        warnings.append(
            "Nie rozpoznano typu warstwy dla: "
            + ", ".join(Path(p).name for p in unknown)
            + " — plik(i) wyrenderowano w neutralnym kolorze na obu stronach płytki."
        )

    bbox_source = bbox_anchor_files or parsed_files
    min_x, min_y, max_x, max_y = _union_bbox(bbox_source)
    view_box = ViewBox(x=min_x, y=-max_y, width=max_x - min_x, height=max_y - min_y)

    layers = _build_layers(parsed_files, all_layers)

    component_shapes: dict[str, str] = {}
    if placements:
        try:
            component_shapes = match_component_shapes(parsed_files, placements)
        except Exception as exc:
            warnings.append(f"Nie udało się dopasować realnych obrysów komponentów, użyto znaczników zastępczych: {exc}")

    return GerberRenderResult(
        layers=layers,
        view_box=view_box,
        warnings=warnings,
        component_shapes=component_shapes,
    )
