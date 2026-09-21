(function () {
  'use strict';

  var DATA = JSON.parse(document.getElementById('report-data').textContent);
  var STORAGE_KEY = 'pcb-report:' + DATA.reportId;
  var PX_PER_MM = 12;
  var MIN_SCALE = 0.3;
  var MAX_SCALE = 40;

  function escapeHtml(str) {
    return String(str == null ? '' : str).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function uid(prefix) {
    return prefix + '_' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  }

  // ---------------------------------------------------------------------
  // Natural reference-designator sort (R1, R2, R10 instead of R1, R10, R2)
  // ---------------------------------------------------------------------
  function naturalRefParts(ref) {
    var m = /^([A-Za-z_]*)(\d+)?(.*)$/.exec(ref || '');
    if (!m) return ['', 0, ref || ''];
    return [m[1].toUpperCase(), m[2] ? parseInt(m[2], 10) : 0, m[3] || ''];
  }
  function compareRefs(a, b) {
    var pa = naturalRefParts(a), pb = naturalRefParts(b);
    if (pa[0] !== pb[0]) return pa[0] < pb[0] ? -1 : 1;
    if (pa[1] !== pb[1]) return pa[1] - pb[1];
    return pa[2] < pb[2] ? -1 : pa[2] > pb[2] ? 1 : 0;
  }

  // ---------------------------------------------------------------------
  // Part grouping: same MPN (or Value+Footprint when MPN is missing) are
  // treated as one "part" for quantity tracking, regardless of how the
  // BOM file itself grouped its rows.
  // ---------------------------------------------------------------------
  function buildPartKey(component) {
    if (component.mpn && component.mpn.trim()) return 'mpn:' + component.mpn.trim().toLowerCase();
    if (component.value && component.footprint) {
      return 'vf:' + component.value.trim().toLowerCase() + '|' + component.footprint.trim().toLowerCase();
    }
    return 'row:' + component.id;
  }

  function buildPartGroups() {
    var map = {};
    DATA.components.forEach(function (c) {
      var key = buildPartKey(c);
      if (!map[key]) {
        map[key] = { key: key, designators: [], value: c.value, footprint: c.footprint, mpn: c.mpn, description: c.description, bomNeeded: 0 };
      }
      var g = map[key];
      g.designators = g.designators.concat(c.designators);
      g.bomNeeded += c.quantity || c.designators.length;
    });
    var rows = Object.keys(map).map(function (k) { return map[k]; });
    rows.forEach(function (r) { r.designators.sort(compareRefs); });
    rows.sort(function (a, b) { return compareRefs(a.designators[0], b.designators[0]); });
    return rows;
  }

  function buildFlatRows() {
    var rows = [];
    DATA.components.forEach(function (c) {
      var key = buildPartKey(c);
      c.designators.forEach(function (d) {
        rows.push({ key: key, designator: d, value: c.value, footprint: c.footprint, mpn: c.mpn });
      });
    });
    rows.sort(function (a, b) { return compareRefs(a.designator, b.designator); });
    return rows;
  }

  var partGroups = buildPartGroups();
  var partGroupsByKey = {};
  partGroups.forEach(function (r) { partGroupsByKey[r.key] = r; });
  var flatRows = buildFlatRows();

  // ---------------------------------------------------------------------
  // Persisted state (localStorage) merged on top of the generated data
  // ---------------------------------------------------------------------
  function defaultPersisted() {
    return { manualPlacements: {}, reworks: [], samples: [], stock: {}, groupByPart: true, lastModified: null };
  }

  function loadPersisted() {
    try {
      var raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return defaultPersisted();
      var parsed = JSON.parse(raw);
      return {
        manualPlacements: parsed.manualPlacements || {},
        reworks: parsed.reworks || [],
        samples: parsed.samples || [],
        stock: parsed.stock || {},
        groupByPart: parsed.groupByPart != null ? parsed.groupByPart : true,
        lastModified: parsed.lastModified || null,
      };
    } catch (e) {
      console.warn('Nie udalo sie odczytac zapisanego stanu:', e);
      return defaultPersisted();
    }
  }

  var persisted = loadPersisted();

  // Builds the full transferable state payload — used both for the
  // localStorage write and for the exported "state file" (multi-user sync
  // without a server: export on one machine, import on another).
  function buildStatePayload() {
    var manualPlacements = {};
    Object.keys(state.placements).forEach(function (designator) {
      var p = state.placements[designator];
      if (p.manual) manualPlacements[designator] = p;
    });
    return {
      manualPlacements: manualPlacements,
      reworks: state.reworks,
      samples: state.samples,
      stock: state.stock,
      groupByPart: state.groupByPart,
      lastModified: state.lastModified,
    };
  }

  function persist() {
    state.lastModified = new Date().toISOString();
    var payload = buildStatePayload();
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch (e) {
      console.warn('Nie udalo sie zapisac stanu (localStorage):', e);
    }
  }

  // ---------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------
  var state = {
    placements: Object.assign({}, DATA.placements, persisted.manualPlacements),
    selection: { key: null, designator: null },
    mappingDesignator: null,
    activeSide: 'top',
    reworks: persisted.reworks,
    samples: persisted.samples,
    stock: persisted.stock,
    groupByPart: persisted.groupByPart,
    lastModified: persisted.lastModified,
  };

  function getStock(key) {
    if (!state.stock[key]) state.stock[key] = { neededOverride: null, delivered: 0, mounted: 0 };
    return state.stock[key];
  }

  function neededFor(key) {
    var stock = getStock(key);
    if (stock.neededOverride != null) return stock.neededOverride;
    var group = partGroupsByKey[key];
    return group ? group.bomNeeded : 1;
  }

  function tierFor(value, needed) {
    if (needed <= 0 || value <= 0) return 'none';
    return value >= needed ? 'full' : 'partial';
  }

  function statusFillForKey(key) {
    var needed = neededFor(key);
    var stock = getStock(key);
    var mountedTier = tierFor(stock.mounted, needed);
    if (mountedTier === 'full') return 'var(--marker-mounted-full)';
    if (mountedTier === 'partial') return 'var(--marker-mounted-partial)';
    var deliveredTier = tierFor(stock.delivered, needed);
    if (deliveredTier === 'full') return 'var(--marker-delivered-full)';
    if (deliveredTier === 'partial') return 'var(--marker-delivered-partial)';
    return 'var(--marker-pending)';
  }

  // ---------------------------------------------------------------------
  // Tabs
  // ---------------------------------------------------------------------
  document.querySelectorAll('.tabs__button').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var tab = btn.dataset.tab;
      document.querySelectorAll('.tabs__button').forEach(function (b) { b.classList.toggle('is-active', b === btn); });
      document.querySelectorAll('.tab-panel').forEach(function (p) { p.classList.toggle('is-active', p.dataset.tab === tab); });
    });
  });

  // ---------------------------------------------------------------------
  // Assembly: side switch (top/bottom)
  // ---------------------------------------------------------------------
  var topBtn = document.getElementById('sideTopBtn');
  var bottomBtn = document.getElementById('sideBottomBtn');

  function setSide(side) {
    state.activeSide = side;
    topBtn.classList.toggle('is-active', side === 'top');
    bottomBtn.classList.toggle('is-active', side === 'bottom');
    renderBoard();
  }
  topBtn.addEventListener('click', function () { setSide('top'); });
  bottomBtn.addEventListener('click', function () { setSide('bottom'); });

  // ---------------------------------------------------------------------
  // Component list
  // ---------------------------------------------------------------------
  var listBody = document.getElementById('componentListBody');
  var listHead = document.getElementById('componentListHead');
  var listEmpty = document.getElementById('componentListEmpty');
  var listTable = document.getElementById('componentListTable');
  var groupToggle = document.getElementById('groupByPartToggle');

  function qtyCellHtml(key, kind, value, needed) {
    var shortage = Math.max(0, needed - value);
    var statusHtml = shortage > 0
      ? '<span class="qty-cell__shortage">brakuje ' + shortage + '</span>'
      : '<span class="qty-cell__ok">OK</span>';
    return (
      '<div class="qty-cell">' +
        '<div class="qty-cell__row">' +
          '<input type="number" min="0" step="1" value="' + value + '" data-qty="' + kind + '" data-key="' + escapeHtml(key) + '" />' +
          '<button type="button" class="qty-cell__all" data-qty-all="' + kind + '" data-key="' + escapeHtml(key) + '">Wszystko</button>' +
        '</div>' +
        statusHtml +
      '</div>'
    );
  }

  function neededCellHtml(key, needed) {
    return '<input type="number" min="0" step="1" value="' + needed + '" data-qty="needed" data-key="' + escapeHtml(key) + '" style="width:60px" />';
  }

  function unplacedHtmlFor(designators) {
    var unplaced = designators.filter(function (d) { return !state.placements[d]; });
    if (unplaced.length === 0) return '';
    var isMappingThis = state.mappingDesignator === unplaced[0];
    return (
      '<div class="component-list__unplaced">Brak pozycji: ' + escapeHtml(unplaced.join(', ')) +
      ' <button type="button" data-action="map" data-designator="' + escapeHtml(unplaced[0]) + '">' +
      (isMappingThis ? 'Anuluj' : 'Ustaw na płytce') + '</button></div>'
    );
  }

  function groupedRowHtml(row) {
    var needed = neededFor(row.key);
    var stock = getStock(row.key);
    var selected = state.selection.key === row.key && !state.selection.designator;
    return (
      '<tr class="' + (selected ? 'is-selected' : '') + '" data-row-key="' + escapeHtml(row.key) + '">' +
      '<td><div class="component-list__designators">' + escapeHtml(row.designators.join(', ')) + '</div>' +
      (row.mpn ? '<div class="component-list__mpn">' + escapeHtml(row.mpn) + '</div>' : '') +
      unplacedHtmlFor(row.designators) +
      '</td>' +
      '<td><div>' + escapeHtml(row.value || '—') + '</div><div class="component-list__footprint">' + escapeHtml(row.footprint || '') + '</div></td>' +
      '<td data-action="stop">' + neededCellHtml(row.key, needed) + '</td>' +
      '<td data-action="stop">' + qtyCellHtml(row.key, 'delivered', stock.delivered, needed) + '</td>' +
      '<td data-action="stop">' + qtyCellHtml(row.key, 'mounted', stock.mounted, needed) + '</td>' +
      '</tr>'
    );
  }

  function flatRowHtml(entry) {
    var needed = neededFor(entry.key);
    var stock = getStock(entry.key);
    var selected = state.selection.designator === entry.designator;
    return (
      '<tr class="' + (selected ? 'is-selected' : '') + '" data-row-key="' + escapeHtml(entry.key) + '" data-designator="' + escapeHtml(entry.designator) + '">' +
      '<td><div class="component-list__designators">' + escapeHtml(entry.designator) + '</div>' +
      (entry.mpn ? '<div class="component-list__mpn">' + escapeHtml(entry.mpn) + '</div>' : '') +
      unplacedHtmlFor([entry.designator]) +
      '</td>' +
      '<td><div>' + escapeHtml(entry.value || '—') + '</div><div class="component-list__footprint">' + escapeHtml(entry.footprint || '') + '</div></td>' +
      '<td><div class="component-list__flat-status">Dostarczono (część): ' + stock.delivered + '/' + needed + '</div>' +
      '<div class="component-list__flat-status">Zamontowano (część): ' + stock.mounted + '/' + needed + '</div></td>' +
      '</tr>'
    );
  }

  function updateListHead() {
    listHead.innerHTML = state.groupByPart
      ? '<tr><th>Oznaczenia</th><th>Wartość / Footprint</th><th>Potrzeba</th><th>Dostarczono</th><th>Zamontowano</th></tr>'
      : '<tr><th>Oznaczenie</th><th>Wartość / Footprint</th><th>Status części</th></tr>';
  }

  function renderComponentList() {
    var rows = state.groupByPart ? partGroups : flatRows;
    if (rows.length === 0) {
      listTable.style.display = 'none';
      listEmpty.style.display = 'block';
      return;
    }
    listTable.style.display = '';
    listEmpty.style.display = 'none';
    listBody.innerHTML = rows.map(state.groupByPart ? groupedRowHtml : flatRowHtml).join('');
  }

  listBody.addEventListener('click', function (e) {
    var mapBtn = e.target.closest('[data-action="map"]');
    if (mapBtn) {
      e.stopPropagation();
      var designator = mapBtn.dataset.designator;
      state.mappingDesignator = state.mappingDesignator === designator ? null : designator;
      renderComponentList();
      updateMappingHint();
      return;
    }
    var allBtn = e.target.closest('[data-qty-all]');
    if (allBtn) {
      e.stopPropagation();
      var key = allBtn.dataset.key;
      getStock(key)[allBtn.dataset.qtyAll] = neededFor(key);
      afterStockChange();
      return;
    }
    if (e.target.closest('[data-action="stop"]')) return;
    var row = e.target.closest('tr[data-row-key]');
    if (!row) return;
    if (state.groupByPart) {
      selectGroup(row.dataset.rowKey);
    } else {
      selectSingle(row.dataset.rowKey, row.dataset.designator);
    }
  });

  listBody.addEventListener('change', function (e) {
    var input = e.target.closest('input[data-qty]');
    if (!input) return;
    var key = input.dataset.key;
    var kind = input.dataset.qty;
    var value = Math.max(0, parseInt(input.value, 10) || 0);
    if (kind === 'needed') {
      getStock(key).neededOverride = value;
    } else {
      getStock(key)[kind] = value;
    }
    afterStockChange();
  });

  groupToggle.addEventListener('change', function (e) {
    state.groupByPart = e.target.checked;
    state.selection = { key: null, designator: null };
    updateListHead();
    renderComponentList();
    updateMarkerSelectionClasses();
    persist();
  });

  function selectGroup(key) {
    if (state.selection.key === key && !state.selection.designator) {
      state.selection = { key: null, designator: null };
    } else {
      state.selection = { key: key, designator: null };
    }
    afterSelectionChange();
  }

  function selectSingle(key, designator) {
    if (state.selection.designator === designator) {
      state.selection = { key: null, designator: null };
    } else {
      state.selection = { key: key, designator: designator };
    }
    afterSelectionChange();
  }

  function afterSelectionChange() {
    renderComponentList();
    updateMarkerSelectionClasses();
  }

  function afterStockChange() {
    renderComponentList();
    refreshAllMarkerFills();
    updateSummary();
    renderShortagePanel();
    persist();
  }

  function updateSummary() {
    var totalNeeded = 0, totalDelivered = 0, totalMounted = 0;
    partGroups.forEach(function (row) {
      var needed = neededFor(row.key);
      var stock = getStock(row.key);
      totalNeeded += needed;
      totalDelivered += Math.min(stock.delivered, needed);
      totalMounted += Math.min(stock.mounted, needed);
    });
    document.getElementById('summaryTotal').textContent = totalNeeded;
    document.getElementById('summaryDelivered').textContent = totalDelivered + '/' + totalNeeded;
    document.getElementById('summaryMounted').textContent = totalMounted + '/' + totalNeeded;
  }

  function renderShortagePanel() {
    var listEl = document.getElementById('shortageList');
    var emptyEl = document.getElementById('shortageEmpty');
    var items = [];
    partGroups.forEach(function (row) {
      var needed = neededFor(row.key);
      var stock = getStock(row.key);
      var missingDelivery = Math.max(0, needed - stock.delivered);
      var missingMount = Math.max(0, needed - stock.mounted);
      if (missingDelivery > 0 || missingMount > 0) {
        items.push({ row: row, needed: needed, missingDelivery: missingDelivery, missingMount: missingMount });
      }
    });
    if (items.length === 0) {
      emptyEl.style.display = 'block';
      listEl.innerHTML = '';
      return;
    }
    emptyEl.style.display = 'none';
    listEl.innerHTML = items.map(function (it) {
      var badges = '';
      if (it.missingDelivery > 0) badges += '<span class="shortage-panel__missing">brakuje dostawy: ' + it.missingDelivery + '</span>';
      if (it.missingMount > 0) badges += '<span class="shortage-panel__missing">brakuje montażu: ' + it.missingMount + '</span>';
      return (
        '<div class="shortage-panel__item">' +
        '<strong>' + escapeHtml(it.row.designators.join(', ')) + '</strong>' +
        '<span>' + escapeHtml(it.row.value || '—') + (it.row.footprint ? ' / ' + escapeHtml(it.row.footprint) : '') + '</span>' +
        (it.row.mpn ? '<span>MPN: ' + escapeHtml(it.row.mpn) + '</span>' : '') +
        '<span>potrzeba: ' + it.needed + '</span>' +
        badges +
        '</div>'
      );
    }).join('');
  }

  function refreshAllMarkerFills() {
    document.querySelectorAll('.marker').forEach(function (m) {
      var base = m.querySelector('.marker__base');
      if (base) base.setAttribute('fill', statusFillForKey(m.dataset.partKey));
    });
  }

  function markerMatchesSelection(partKey, designator) {
    if (!state.selection.key && !state.selection.designator) return false;
    if (state.selection.designator) return designator === state.selection.designator;
    return partKey === state.selection.key;
  }

  function updateMarkerSelectionClasses() {
    document.querySelectorAll('.marker').forEach(function (m) {
      m.classList.toggle('is-selected', markerMatchesSelection(m.dataset.partKey, m.dataset.designator));
    });
  }

  // ---------------------------------------------------------------------
  // PCB viewer (SVG-based zoom/pan)
  // ---------------------------------------------------------------------
  var viewport = document.getElementById('boardViewport');
  var stage = document.getElementById('boardStage');
  var emptyNotice = document.getElementById('boardEmpty');
  var mappingHint = document.getElementById('mappingHint');
  var transform = { scale: 1, x: 0, y: 0 };
  var currentSvg = null;

  function applyTransform() {
    stage.style.transform = 'translate(' + transform.x + 'px, ' + transform.y + 'px) scale(' + transform.scale + ')';
  }

  function fitToView() {
    if (!currentSvg) return;
    var vb = getActiveViewBox();
    if (!vb) return;
    var boardW = vb.width * PX_PER_MM;
    var boardH = vb.height * PX_PER_MM;
    var pad = 40;
    var scaleX = (viewport.clientWidth - pad * 2) / boardW;
    var scaleY = (viewport.clientHeight - pad * 2) / boardH;
    var scale = Math.max(MIN_SCALE, Math.min(scaleX, scaleY, MAX_SCALE));
    transform.scale = scale;
    transform.x = (viewport.clientWidth - boardW * scale) / 2;
    transform.y = (viewport.clientHeight - boardH * scale) / 2;
    applyTransform();
  }

  function getActiveViewBox() {
    return DATA.viewBox;
  }

  function buildMarkersSvg() {
    var svgNs = 'http://www.w3.org/2000/svg';
    var g = document.createElementNS(svgNs, 'g');
    g.setAttribute('id', 'markersLayer');

    flatRows.forEach(function (entry) {
      var placement = state.placements[entry.designator];
      if (!placement) return;
      var x = placement.x;
      var y = -placement.y;
      var rad = (placement.rotation * Math.PI) / 180;
      var pinOffset = 1.6;
      var pinX = x + Math.sin(rad) * pinOffset;
      var pinY = y - Math.cos(rad) * pinOffset;

      var marker = document.createElementNS(svgNs, 'g');
      marker.setAttribute('class', 'marker');
      marker.dataset.partKey = entry.key;
      marker.dataset.designator = entry.designator;

      var halo = document.createElementNS(svgNs, 'circle');
      halo.setAttribute('class', 'marker__halo');
      halo.setAttribute('cx', x); halo.setAttribute('cy', y); halo.setAttribute('r', 2.2);
      halo.setAttribute('fill', 'none'); halo.setAttribute('stroke', '#ff6a00'); halo.setAttribute('stroke-width', 0.35);

      var base = document.createElementNS(svgNs, 'circle');
      base.setAttribute('class', 'marker__base');
      base.setAttribute('cx', x); base.setAttribute('cy', y); base.setAttribute('r', 0.95);
      base.setAttribute('fill', statusFillForKey(entry.key));

      var pin1 = document.createElementNS(svgNs, 'circle');
      pin1.setAttribute('class', 'marker__pin1');
      pin1.setAttribute('cx', pinX); pin1.setAttribute('cy', pinY); pin1.setAttribute('r', 0.32);

      var label = document.createElementNS(svgNs, 'text');
      label.setAttribute('x', x + 1.6); label.setAttribute('y', y - 1.6);
      label.textContent = entry.designator;

      marker.appendChild(halo);
      marker.appendChild(base);
      marker.appendChild(pin1);
      marker.appendChild(label);
      marker.addEventListener('click', function (evt) {
        evt.stopPropagation();
        if (state.groupByPart) {
          selectGroup(entry.key);
        } else {
          selectSingle(entry.key, entry.designator);
        }
      });
      g.appendChild(marker);
    });

    return g;
  }

  function renderBoard() {
    var vb = getActiveViewBox();
    var svgInner = state.activeSide === 'top' ? DATA.topSvgInner : DATA.bottomSvgInner;

    stage.innerHTML = '';
    if (!svgInner || !vb) {
      currentSvg = null;
      emptyNotice.style.display = 'flex';
      return;
    }
    emptyNotice.style.display = 'none';

    var svgNs = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(svgNs, 'svg');
    svg.setAttribute('viewBox', vb.x + ' ' + vb.y + ' ' + vb.width + ' ' + vb.height);
    svg.setAttribute('width', vb.width * PX_PER_MM);
    svg.setAttribute('height', vb.height * PX_PER_MM);
    svg.style.display = 'block';

    var bg = document.createElementNS(svgNs, 'rect');
    bg.setAttribute('x', vb.x); bg.setAttribute('y', vb.y);
    bg.setAttribute('width', vb.width); bg.setAttribute('height', vb.height);
    bg.setAttribute('fill', '#0a1f33');
    svg.appendChild(bg);

    var gerberGroup = document.createElementNS(svgNs, 'g');
    gerberGroup.innerHTML = svgInner;
    svg.appendChild(gerberGroup);

    svg.appendChild(buildMarkersSvg());

    bg.addEventListener('click', function () {
      if (state.mappingDesignator) return;
      state.selection = { key: null, designator: null };
      afterSelectionChange();
    });

    stage.appendChild(svg);
    currentSvg = svg;
    updateMarkerSelectionClasses();
    fitToView();
  }

  function updateMappingHint() {
    viewport.classList.toggle('is-mapping', !!state.mappingDesignator);
    if (state.mappingDesignator) {
      mappingHint.style.display = 'inline';
      mappingHint.textContent = 'Kliknij na płytce, aby ustawić pozycję ' + state.mappingDesignator;
    } else {
      mappingHint.style.display = 'none';
    }
  }

  // Pan + zoom
  var dragState = null;
  viewport.addEventListener('pointerdown', function (e) {
    if (e.button !== 0) return;
    dragState = { startX: e.clientX, startY: e.clientY, origX: transform.x, origY: transform.y, moved: false };
    viewport.setPointerCapture(e.pointerId);
  });
  viewport.addEventListener('pointermove', function (e) {
    if (!dragState || state.mappingDesignator) return;
    var dx = e.clientX - dragState.startX;
    var dy = e.clientY - dragState.startY;
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
      dragState.moved = true;
      viewport.classList.add('is-panning');
    }
    if (dragState.moved) {
      transform.x = dragState.origX + dx;
      transform.y = dragState.origY + dy;
      applyTransform();
    }
  });
  viewport.addEventListener('pointerup', function (e) {
    if (dragState && !dragState.moved && state.mappingDesignator && currentSvg) {
      placeAtClientPoint(e.clientX, e.clientY);
    }
    dragState = null;
    viewport.classList.remove('is-panning');
  });

  viewport.addEventListener('wheel', function (e) {
    if (!currentSvg) return;
    e.preventDefault();
    var rect = viewport.getBoundingClientRect();
    var pointer = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    var direction = e.deltaY > 0 ? -1 : 1;
    var factor = 1.08;
    var oldScale = transform.scale;
    var newScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, direction > 0 ? oldScale * factor : oldScale / factor));
    var worldPoint = { x: (pointer.x - transform.x) / oldScale, y: (pointer.y - transform.y) / oldScale };
    transform.scale = newScale;
    transform.x = pointer.x - worldPoint.x * newScale;
    transform.y = pointer.y - worldPoint.y * newScale;
    applyTransform();
  }, { passive: false });

  function placeAtClientPoint(clientX, clientY) {
    var pt = currentSvg.createSVGPoint();
    pt.x = clientX; pt.y = clientY;
    var ctm = currentSvg.getScreenCTM();
    if (!ctm) return;
    var local = pt.matrixTransform(ctm.inverse());
    var designator = state.mappingDesignator;
    state.placements[designator] = {
      designator: designator,
      x: local.x,
      y: -local.y,
      rotation: (state.placements[designator] && state.placements[designator].rotation) || 0,
      side: (state.placements[designator] && state.placements[designator].side) || 'top',
      manual: true,
    };
    state.mappingDesignator = null;
    updateMappingHint();
    renderComponentList();
    renderBoard();
    persist();
  }

  document.getElementById('fitViewBtn').addEventListener('click', fitToView);
  document.getElementById('zoomInBtn').addEventListener('click', function () {
    transform.scale = Math.min(MAX_SCALE, transform.scale * 1.3);
    applyTransform();
  });
  document.getElementById('zoomOutBtn').addEventListener('click', function () {
    transform.scale = Math.max(MIN_SCALE, transform.scale / 1.3);
    applyTransform();
  });

  window.addEventListener('resize', function () {
    if (currentSvg) fitToView();
  });

  // ---------------------------------------------------------------------
  // Traceability
  // ---------------------------------------------------------------------
  var reworkForm = document.getElementById('reworkForm');
  var reworkInput = document.getElementById('reworkInput');
  var reworkList = document.getElementById('reworkList');
  var sampleForm = document.getElementById('sampleForm');
  var sampleInput = document.getElementById('sampleInput');
  var sampleGrid = document.getElementById('sampleGrid');
  var sampleEmpty = document.getElementById('sampleEmpty');

  function renderReworkPool() {
    if (state.reworks.length === 0) {
      reworkList.innerHTML = '<li class="rework-pool__empty">Brak przeróbek na liście.</li>';
    } else {
      reworkList.innerHTML = state.reworks.map(function (r) {
        return '<li><span>' + escapeHtml(r.label) + '</span><button type="button" data-id="' + r.id + '" title="Usuń przeróbkę z wspólnej listy">✕</button></li>';
      }).join('');
    }
  }

  reworkForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var label = reworkInput.value.trim();
    if (!label) return;
    state.reworks.push({ id: uid('rw'), label: label });
    reworkInput.value = '';
    renderReworkPool();
    renderSamples();
    persist();
  });

  reworkList.addEventListener('click', function (e) {
    var btn = e.target.closest('button[data-id]');
    if (!btn) return;
    var id = btn.dataset.id;
    state.reworks = state.reworks.filter(function (r) { return r.id !== id; });
    state.samples.forEach(function (s) { s.reworkIds = s.reworkIds.filter(function (rid) { return rid !== id; }); });
    renderReworkPool();
    renderSamples();
    persist();
  });

  function renderSamples() {
    if (state.samples.length === 0) {
      sampleEmpty.style.display = 'block';
      sampleGrid.innerHTML = '';
      return;
    }
    sampleEmpty.style.display = 'none';
    sampleGrid.innerHTML = state.samples.map(function (sample) {
      var reworksHtml = state.reworks.length === 0
        ? '<p class="sample-card__empty">Dodaj przeróbki do wspólnej listy.</p>'
        : state.reworks.map(function (r) {
            var checked = sample.reworkIds.indexOf(r.id) !== -1;
            return '<label class="sample-card__rework-item"><input type="checkbox" data-sample="' + sample.id + '" data-rework="' + r.id + '" ' + (checked ? 'checked' : '') + '/><span>' + escapeHtml(r.label) + '</span></label>';
          }).join('');
      return (
        '<div class="sample-card">' +
        '<div class="sample-card__header"><h3>' + escapeHtml(sample.name) + '</h3>' +
        '<button type="button" data-remove-sample="' + sample.id + '" title="Usuń sampel">✕</button></div>' +
        '<div class="sample-card__reworks">' + reworksHtml + '</div>' +
        '<textarea class="sample-card__notes" data-notes="' + sample.id + '" placeholder="Uwagi dotyczące tego sampla…">' + escapeHtml(sample.notes) + '</textarea>' +
        '</div>'
      );
    }).join('');
  }

  sampleForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var name = sampleInput.value.trim();
    if (!name) return;
    state.samples.push({ id: uid('smp'), name: name, reworkIds: [], notes: '' });
    sampleInput.value = '';
    renderSamples();
    persist();
  });

  sampleGrid.addEventListener('click', function (e) {
    var removeBtn = e.target.closest('[data-remove-sample]');
    if (removeBtn) {
      var id = removeBtn.dataset.removeSample;
      state.samples = state.samples.filter(function (s) { return s.id !== id; });
      renderSamples();
      persist();
    }
  });

  sampleGrid.addEventListener('change', function (e) {
    if (e.target.matches('input[data-sample][data-rework]')) {
      var sample = state.samples.find(function (s) { return s.id === e.target.dataset.sample; });
      if (!sample) return;
      var reworkId = e.target.dataset.rework;
      var idx = sample.reworkIds.indexOf(reworkId);
      if (e.target.checked && idx === -1) sample.reworkIds.push(reworkId);
      if (!e.target.checked && idx !== -1) sample.reworkIds.splice(idx, 1);
      persist();
    }
  });

  sampleGrid.addEventListener('input', function (e) {
    if (e.target.matches('textarea[data-notes]')) {
      var sample = state.samples.find(function (s) { return s.id === e.target.dataset.notes; });
      if (!sample) return;
      sample.notes = e.target.value;
      persist();
    }
  });

  // ---------------------------------------------------------------------
  // Eksport / import stanu — synchronizacja bez serwera. Kilka osob na
  // roznych komputerach moze przekazywac sobie maly plik .json (mail, dysk
  // sieciowy, USB) zamiast polegac wylacznie na localStorage przegladarki,
  // ktory znika po wyczyszczeniu cache albo nie jest widoczny na innym
  // urzadzeniu.
  // ---------------------------------------------------------------------
  var exportBtn = document.getElementById('exportStateBtn');
  var importBtn = document.getElementById('importStateBtn');
  var importInput = document.getElementById('importStateInput');

  function exportState() {
    state.lastModified = new Date().toISOString();
    var payload = buildStatePayload();
    payload.reportId = DATA.reportId;
    payload.exportedAt = state.lastModified;
    var blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    var stamp = payload.exportedAt.replace(/[:.]/g, '-');
    a.href = url;
    a.download = 'pcb-report-stan-' + DATA.reportId + '-' + stamp + '.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    persist();
  }

  function refreshAllViews() {
    updateListHead();
    renderComponentList();
    updateSummary();
    renderBoard();
    renderShortagePanel();
    renderReworkPool();
    renderSamples();
  }

  function importStateFromFile(file) {
    var reader = new FileReader();
    reader.onload = function () {
      var parsed;
      try {
        parsed = JSON.parse(reader.result);
      } catch (e) {
        window.alert('Nie udało się odczytać pliku stanu: to nie jest poprawny plik JSON.');
        return;
      }

      if (parsed.reportId && parsed.reportId !== DATA.reportId) {
        var proceedDifferent = window.confirm(
          'Ten plik stanu pochodzi z innego raportu (inne pliki Gerber/BOM) — oznaczenia mogą się nie zgadzać. ' +
          'Zaimportować mimo to?'
        );
        if (!proceedDifferent) return;
      } else if (state.lastModified && parsed.lastModified && parsed.lastModified < state.lastModified) {
        var proceedOlder = window.confirm(
          'Importowany plik jest STARSZY niż obecny stan w tej przeglądarce (obecny: ' +
          new Date(state.lastModified).toLocaleString() + ', w pliku: ' +
          new Date(parsed.lastModified).toLocaleString() + '). Import nadpisze bieżące dane starszymi. Kontynuować?'
        );
        if (!proceedOlder) return;
      } else if (!window.confirm('Zaimportować stan z pliku? Nadpisze to bieżące dane w tej przeglądarce.')) {
        return;
      }

      state.placements = Object.assign({}, DATA.placements, parsed.manualPlacements || {});
      state.reworks = parsed.reworks || [];
      state.samples = parsed.samples || [];
      state.stock = parsed.stock || {};
      state.groupByPart = parsed.groupByPart != null ? parsed.groupByPart : true;
      state.lastModified = parsed.lastModified || new Date().toISOString();
      state.selection = { key: null, designator: null };
      state.mappingDesignator = null;

      groupToggle.checked = state.groupByPart;
      refreshAllViews();
      updateMappingHint();
      persist();
      window.alert('Zaimportowano stan z pliku.');
    };
    reader.onerror = function () {
      window.alert('Nie udało się odczytać pliku.');
    };
    reader.readAsText(file);
  }

  exportBtn.addEventListener('click', exportState);
  importBtn.addEventListener('click', function () { importInput.click(); });
  importInput.addEventListener('change', function (e) {
    var file = e.target.files && e.target.files[0];
    if (file) importStateFromFile(file);
    importInput.value = '';
  });

  // ---------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------
  groupToggle.checked = state.groupByPart;
  updateListHead();
  renderComponentList();
  updateSummary();
  renderBoard();
  updateMappingHint();
  renderShortagePanel();
  renderReworkPool();
  renderSamples();
})();
