"""Assemble the final, self-contained HTML report."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .models import BomComponent, GerberRenderResult, Placement

_ASSETS_DIR = Path(__file__).parent / "assets"


def _make_report_id(gerber_paths: list[str], components: list[BomComponent]) -> str:
    """A stable-ish id derived from the input file names + designator set,
    used as the localStorage key so re-running the tool on the same project
    keeps prior checklist/traceability progress, while a different project
    gets its own separate state.
    """
    basenames = sorted(Path(p).name for p in gerber_paths)
    designators = sorted(d for c in components for d in c.designators)
    digest_input = "|".join(basenames) + "::" + ",".join(designators)
    return hashlib.sha1(digest_input.encode("utf-8")).hexdigest()[:16]


def _escape_for_script_tag(json_text: str) -> str:
    # Prevent a literal "</script>" inside embedded data (e.g. inside SVG
    # text content) from prematurely closing the <script> element.
    return json_text.replace("</", "<\\/")


def build_report_html(
    *,
    gerber_paths: list[str],
    gerber_result: GerberRenderResult,
    components: list[BomComponent],
    placements: dict[str, Placement],
    report_id: str | None = None,
    title: str = "GerbertoHTML — raport Assembly / Traceability",
) -> str:
    css = (_ASSETS_DIR / "report.css").read_text(encoding="utf-8")
    js = (_ASSETS_DIR / "report.js").read_text(encoding="utf-8")

    resolved_report_id = report_id or _make_report_id(gerber_paths, components)

    data = {
        "reportId": resolved_report_id,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "viewBox": gerber_result.view_box.to_dict() if gerber_result.view_box else None,
        "topSvgInner": gerber_result.top_svg,
        "bottomSvgInner": gerber_result.bottom_svg,
        "warnings": gerber_result.warnings,
        "components": [c.to_dict() for c in components],
        "placements": {designator: p.to_dict() for designator, p in placements.items()},
    }
    data_json = _escape_for_script_tag(json.dumps(data, ensure_ascii=False))

    warnings_html = ""
    if gerber_result.warnings:
        items = "".join(f"<li>{_html_escape(w)}</li>" for w in gerber_result.warnings)
        warnings_html = f'<ul>{items}</ul>'

    generated_label = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{_html_escape(title)}</title>
<style>
{css}
</style>
</head>
<body>
<div class="app">
  <header class="app__header">
    <div class="app__brand">
      <span class="app__brand-mark">PCB</span>
      <div>
        <h1>GerbertoHTML — raport</h1>
        <p>Zarządzanie montażem i śledzenie przeróbek płytek PCB</p>
      </div>
    </div>
    <nav class="tabs">
      <button type="button" class="tabs__button is-active" data-tab="assembly">Assembly</button>
      <button type="button" class="tabs__button" data-tab="traceability">Traceability</button>
    </nav>
    <div class="app__meta">Wygenerowano: {generated_label}<br/>ID raportu: {resolved_report_id}</div>
  </header>

  <main class="app__main">
    <section class="tab-panel is-active" data-tab="assembly">
      <div class="assembly-tab">
        <aside class="assembly-tab__sidebar">
          <div class="upload-panel">
            <h2>Dane wejściowe</h2>
            <p>Plik(i) Gerber: {_html_escape(', '.join(Path(p).name for p in gerber_paths) or '—')}</p>
            {warnings_html}
          </div>

          <div class="assembly-tab__summary">
            <div>Elementy: <strong id="summaryTotal">0</strong></div>
            <div>Dostarczone: <strong id="summaryDelivered">0/0</strong></div>
            <div>Zamontowane: <strong id="summaryMounted">0/0</strong></div>
          </div>

          <div class="component-list">
            <div class="component-list--empty" id="componentListEmpty" style="display:none;">Brak komponentów w BOM.</div>
            <table id="componentListTable">
              <thead>
                <tr><th>Oznaczenie</th><th>Wartość / Footprint</th><th title="Dostarczono">Dost.</th><th title="Zamontowano">Mont.</th></tr>
              </thead>
              <tbody id="componentListBody"></tbody>
            </table>
          </div>
        </aside>

        <section class="assembly-tab__viewer">
          <div class="assembly-tab__side-switch">
            <button type="button" id="sideTopBtn" class="is-active">Góra (Top)</button>
            <button type="button" id="sideBottomBtn">Dół (Bottom)</button>
          </div>
          <div class="pcb-viewer">
            <div class="pcb-viewer__toolbar">
              <button type="button" id="fitViewBtn">Dopasuj widok</button>
              <button type="button" id="zoomInBtn">+</button>
              <button type="button" id="zoomOutBtn">−</button>
              <span class="pcb-viewer__mapping-hint" id="mappingHint" style="display:none;"></span>
            </div>
            <div class="pcb-viewer__empty" id="boardEmpty" style="display:none;">Brak wyrenderowanej płytki PCB (sprawdź ostrzeżenia po lewej).</div>
            <div class="board-viewport" id="boardViewport">
              <div class="board-stage" id="boardStage"></div>
            </div>
          </div>
        </section>
      </div>
    </section>

    <section class="tab-panel" data-tab="traceability">
      <div class="traceability-tab">
        <aside class="traceability-tab__sidebar">
          <div class="rework-pool">
            <h2>Wspólna lista przeróbek (rework)</h2>
            <p class="rework-pool__hint">Przeróbki dodane tutaj są wspólne dla wszystkich sampli — dla każdego sampla zaznaczysz, które z nich wystąpiły.</p>
            <form id="reworkForm" class="rework-pool__form">
              <input type="text" id="reworkInput" placeholder="np. Wymiana R12 na wartość 10k" />
              <button type="submit">Dodaj przeróbkę</button>
            </form>
            <ul class="rework-pool__list" id="reworkList"></ul>
          </div>
        </aside>
        <section class="traceability-tab__samples">
          <div class="traceability-tab__add-sample">
            <h2>Sample</h2>
            <form id="sampleForm">
              <input type="text" id="sampleInput" placeholder="np. Sample #12 / SN-0042" />
              <button type="submit">Dodaj sampel</button>
            </form>
          </div>
          <p class="traceability-tab__empty" id="sampleEmpty">Brak sampli — dodaj pierwszy powyżej.</p>
          <div class="traceability-tab__grid" id="sampleGrid"></div>
        </section>
      </div>
    </section>
  </main>
</div>

<script type="application/json" id="report-data">{data_json}</script>
<script>
{js}
</script>
</body>
</html>
"""


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
