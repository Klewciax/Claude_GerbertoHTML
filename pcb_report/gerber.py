"""Render Gerber/Excellon files to SVG.

Parsing RS-274X Gerber (arcs, apertures, macros) correctly from scratch is a
substantial undertaking. Rather than reimplementing it, this module shells
out to a vendored, self-contained Node.js bundle (`assets/tracespace-bundle.mjs`)
built from `@tracespace/core` — the same well-tested library used by
tracespace.io. This is the one place in the tool that requires a `node`
executable on PATH; everything else is pure Python.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .models import GerberRenderResult, ViewBox

_ASSETS_DIR = Path(__file__).parent / "assets"
_BUNDLE_PATH = _ASSETS_DIR / "tracespace-bundle.mjs"


class NodeNotFoundError(RuntimeError):
    pass


def _find_node() -> str:
    node = shutil.which("node")
    if not node:
        raise NodeNotFoundError(
            "Nie znaleziono polecenia 'node' w PATH. Renderowanie plików Gerber wymaga "
            "zainstalowanego Node.js (>= 18) — https://nodejs.org/. Reszta narzędzia "
            "(parsowanie BOM/pick-and-place, generowanie raportu) nie wymaga Node.js."
        )
    return node


def render_gerber_files(paths: list[str]) -> GerberRenderResult:
    if not paths:
        return GerberRenderResult(warnings=["Nie wskazano żadnych plików Gerber."])

    try:
        node = _find_node()
    except NodeNotFoundError as exc:
        return GerberRenderResult(warnings=[str(exc)])

    try:
        proc = subprocess.run(
            [node, str(_BUNDLE_PATH), *paths],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return GerberRenderResult(warnings=["Renderowanie plików Gerber przekroczyło limit czasu (120s)."])

    if proc.returncode != 0 or not proc.stdout.strip():
        stderr = proc.stderr.strip()
        return GerberRenderResult(
            warnings=[f"Błąd procesu renderowania Gerber (kod {proc.returncode}): {stderr or 'brak szczegółów'}"]
        )

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return GerberRenderResult(warnings=[f"Nie udało się odczytać wyniku renderowania: {exc}"])

    view_box: Optional[ViewBox] = None
    raw_view_box = data.get("viewBox")
    if raw_view_box:
        view_box = ViewBox(
            x=raw_view_box["x"], y=raw_view_box["y"], width=raw_view_box["width"], height=raw_view_box["height"]
        )

    return GerberRenderResult(
        top_svg=data.get("topSvg"),
        bottom_svg=data.get("bottomSvg"),
        view_box=view_box,
        warnings=list(data.get("warnings", [])),
    )
