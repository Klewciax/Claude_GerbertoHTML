"""Assemble the final, self-contained HTML report."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .models import BomVariant, GerberRenderResult

_ASSETS_DIR = Path(__file__).parent / "assets"


def _make_report_id(gerber_paths: list[str], variants: dict[str, BomVariant]) -> str:
    """A stable-ish id derived from the input file names + designator set,
    used as the localStorage key so re-running the tool on the same project
    keeps prior checklist/traceability progress, while a different project
    gets its own separate state. Uses the union of every variant's
    designators so the id doesn't shift depending on which variant happens
    to be default.
    """
    basenames = sorted(Path(p).name for p in gerber_paths)
    designators = sorted({d for v in variants.values() for c in v.components for d in c.designators})
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
    variants: dict[str, BomVariant],
    default_variant: str,
    report_id: str | None = None,
    title: str = "GerbertoHTML — raport Assembly / Traceability",
) -> str:
    css = (_ASSETS_DIR / "report.css").read_text(encoding="utf-8")
    js = (_ASSETS_DIR / "report.js").read_text(encoding="utf-8")

    resolved_report_id = report_id or _make_report_id(gerber_paths, variants)

    data = {
        "reportId": resolved_report_id,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "viewBox": gerber_result.view_box.to_dict() if gerber_result.view_box else None,
        "gerberLayers": [layer.to_dict() for layer in gerber_result.layers],
        "warnings": gerber_result.warnings,
        "variants": {name: v.to_dict() for name, v in variants.items()},
        "defaultVariant": default_variant,
        "componentShapes": gerber_result.component_shapes,
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
        <p data-i18n="app_subtitle">Zarządzanie montażem i śledzenie przeróbek płytek PCB</p>
      </div>
    </div>
    <nav class="tabs">
      <button type="button" class="tabs__button is-active" data-tab="assembly">Assembly</button>
      <button type="button" class="tabs__button" data-tab="traceability">Traceability</button>
    </nav>
    <div class="lang-switch" id="langSwitch">
      <button type="button" data-lang="pl" class="is-active">PL</button>
      <button type="button" data-lang="de">DE</button>
    </div>
    <div class="theme-switch" id="themeSwitch">
      <button type="button" data-theme="light" class="is-active" data-i18n-title="theme_light_title" title="Jasny motyw">☀️</button>
      <button type="button" data-theme="dark" data-i18n-title="theme_dark_title" title="Ciemny motyw">🌙</button>
    </div>
    <div class="app__sync">
      <button type="button" id="exportStateBtn" data-i18n-title="export_btn_title" title="Zapisz plik ze stanem (do przekazania innej osobie/komputerowi)"><span data-i18n="export_btn">⭳ Eksportuj stan</span></button>
      <button type="button" id="importStateBtn" data-i18n-title="import_btn_title" title="Wczytaj wcześniej wyeksportowany plik stanu"><span data-i18n="import_btn">⭱ Importuj stan</span></button>
      <input type="file" id="importStateInput" accept=".json,application/json" style="display:none;" />
    </div>
    <div class="app__meta"><span data-i18n="meta_generated">Wygenerowano</span>: {generated_label}<br/><span data-i18n="meta_report_id">ID raportu</span>: {resolved_report_id}</div>
  </header>

  <main class="app__main">
    <section class="tab-panel is-active" data-tab="assembly">
      <div class="assembly-page">
      <div class="assembly-tab">
        <aside class="assembly-tab__sidebar">
          <div class="upload-panel">
            <div class="upload-panel__header">
              <h2 data-i18n="input_data_heading">Dane wejściowe</h2>
              <button type="button" id="uploadPanelToggleBtn" class="upload-panel__toggle" aria-expanded="false" data-i18n-title="input_data_toggle_title" title="Pokaż/ukryj">▸</button>
            </div>
            <div class="upload-panel__body" id="uploadPanelBody" style="display:none;">
              <p><span data-i18n="input_gerber_label">Plik(i) Gerber</span>: {_html_escape(', '.join(Path(p).name for p in gerber_paths) or '—')}</p>
              {warnings_html}
            </div>
          </div>

          <div class="variant-picker" id="variantPicker" style="display:none;">
            <label for="variantSelect" data-i18n="variant_label">Wariant montażu</label>
            <select id="variantSelect"></select>
          </div>

          <div class="production-panel">
            <div class="production-panel__field">
              <label for="projectNumberInput" data-i18n="project_number_label">Numer projektu</label>
              <input type="text" id="projectNumberInput" data-i18n-placeholder="project_number_placeholder" placeholder="np. P2024-118" />
            </div>
            <div class="production-panel__field">
              <label for="unitCountInput" data-i18n="unit_count_label">Ilość sztuk do montażu</label>
              <input type="number" id="unitCountInput" min="0" step="1" />
            </div>
            <div class="production-panel__field" id="unitPickerField" style="display:none;">
              <label for="unitSelect" data-i18n="unit_picker_label">Aktualnie montowana płytka</label>
              <select id="unitSelect"></select>
            </div>
          </div>

          <div class="assembly-tab__summary">
            <div><span data-i18n="summary_positions">Pozycje</span>: <strong id="summaryTotal">0</strong></div>
            <div><span data-i18n="summary_delivered">Dostarczono</span>: <strong id="summaryDelivered">0/0</strong></div>
            <div><span data-i18n="summary_mounted">Zamontowano</span>: <strong id="summaryMounted">0/0</strong></div>
          </div>

          <div class="component-list__controls">
            <label class="component-list__group-toggle">
              <input type="checkbox" id="groupByPartToggle" checked />
              <span data-i18n="group_by_part">Grupuj wg części (MPN)</span>
            </label>
          </div>

          <div class="component-list">
            <div class="component-list--empty" id="componentListEmpty" data-i18n="no_components" style="display:none;">Brak komponentów w BOM.</div>
            <table id="componentListTable">
              <colgroup id="componentListCols"></colgroup>
              <thead id="componentListHead"></thead>
              <tbody id="componentListBody"></tbody>
            </table>
          </div>
        </aside>

        <div class="assembly-tab__resize-handle" id="assemblySidebarResizer" title="Przeciągnij, aby zmienić szerokość panelu"></div>

        <section class="assembly-tab__viewer">
          <div class="assembly-tab__side-switch">
            <button type="button" id="sideTopBtn" class="is-active" data-i18n="side_top">Góra (Top)</button>
            <button type="button" id="sideBottomBtn" data-i18n="side_bottom">Dół (Bottom)</button>
            <button type="button" id="layerPanelToggleBtn" class="layer-panel-toggle" data-i18n="layers_btn">Warstwy</button>
          </div>
          <div class="pcb-viewer">
            <div class="pcb-viewer__toolbar">
              <button type="button" id="fitViewBtn" data-i18n="fit_view_btn">Dopasuj widok</button>
              <button type="button" id="zoomInBtn">+</button>
              <button type="button" id="zoomOutBtn">−</button>
              <span class="pcb-viewer__mapping-hint" id="mappingHint" style="display:none;"></span>
            </div>
            <div class="layer-panel" id="layerPanel" style="display:none;">
              <div class="layer-panel__header">
                <h3 data-i18n="layer_panel_heading">Warstwy Gerber</h3>
                <button type="button" id="layerPanelCloseBtn" data-i18n-title="close_title" title="Zamknij">✕</button>
              </div>
              <div class="layer-panel__list" id="layerPanelList"></div>
            </div>
            <div class="pcb-viewer__empty" id="boardEmpty" data-i18n="board_empty" style="display:none;">Brak wyrenderowanej płytki PCB (sprawdź ostrzeżenia po lewej).</div>
            <div class="board-viewport" id="boardViewport">
              <div class="board-stage" id="boardStage"></div>
            </div>
          </div>
        </section>
      </div>

      <div class="shortage-panel" id="shortagePanel">
        <div class="shortage-panel__resize-handle" id="shortagePanelResizer" data-i18n-title="shortage_resize_title" title="Przeciągnij, aby zmienić wysokość panelu"></div>
        <div class="shortage-panel__header">
          <h2 data-i18n="shortage_heading">Braki (dostawa / montaż)</h2>
          <button type="button" id="shortagePanelToggleBtn" class="shortage-panel__toggle" aria-expanded="true" data-i18n-title="shortage_toggle_title" title="Zwiń/rozwiń">▾</button>
        </div>
        <div class="shortage-panel__body" id="shortagePanelBody">
          <p class="shortage-panel__empty" id="shortageEmpty" data-i18n="shortage_empty">Brak braków — wszystko dostarczone i zamontowane w potrzebnej ilości.</p>
          <div class="shortage-panel__list" id="shortageList"></div>
        </div>
      </div>
      </div>
    </section>

    <section class="tab-panel" data-tab="traceability">
      <div class="traceability-tab">
        <aside class="traceability-tab__sidebar">
          <div class="rework-pool">
            <h2 data-i18n="rework_heading">Wspólna lista przeróbek (rework)</h2>
            <p class="rework-pool__hint" data-i18n="rework_hint">Przeróbki dodane tutaj są wspólne dla wszystkich sampli — dla każdego sampla zaznaczysz, które z nich wystąpiły.</p>
            <form id="reworkForm" class="rework-pool__form">
              <input type="text" id="reworkInput" data-i18n-placeholder="rework_input_placeholder" placeholder="np. Wymiana R12 na wartość 10k" />
              <button type="submit" data-i18n="rework_add_btn">Dodaj przeróbkę</button>
            </form>
            <ul class="rework-pool__list" id="reworkList"></ul>
          </div>
          <div class="software-pool">
            <h2 data-i18n="software_heading">Wersje oprogramowania</h2>
            <p class="software-pool__hint" data-i18n="software_hint">Wersje dodane tutaj są dostępne do wyboru dla każdego sampla z listy rozwijanej.</p>
            <form id="softwareForm" class="software-pool__form">
              <input type="text" id="softwareLabelInput" data-i18n-placeholder="software_label_placeholder" placeholder="np. Firmware v1.4.2" />
              <input type="url" id="softwareUrlInput" data-i18n-placeholder="software_url_placeholder" placeholder="Link do pobrania (opcjonalnie)" />
              <button type="submit" data-i18n="software_add_btn">Dodaj wersję</button>
            </form>
            <ul class="software-pool__list" id="softwareList"></ul>
          </div>
        </aside>
        <section class="traceability-tab__samples">
          <div class="traceability-tab__add-sample">
            <h2 data-i18n="sample_heading">Sample</h2>
            <form id="sampleForm">
              <input type="text" id="sampleInput" data-i18n-placeholder="sample_input_placeholder" placeholder="np. Sample #12 / SN-0042" />
              <button type="submit" data-i18n="sample_add_btn">Dodaj sampel</button>
            </form>
          </div>
          <p class="traceability-tab__empty" id="sampleEmpty" data-i18n="sample_empty">Brak sampli — dodaj pierwszy powyżej.</p>
          <div class="traceability-tab__grid" id="sampleGrid"></div>
        </section>
      </div>
    </section>
  </main>

  <div class="photo-lightbox" id="photoLightbox" style="display:none;">
    <button type="button" id="photoLightboxCloseBtn" class="photo-lightbox__close" data-i18n-title="close_title" title="Zamknij">✕</button>
    <img id="photoLightboxImg" src="" alt="" />
  </div>
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
