(function () {
  'use strict';

  var DATA = JSON.parse(document.getElementById('report-data').textContent);
  var STORAGE_KEY = 'pcb-report:' + DATA.reportId;
  var PX_PER_MM = 12;
  var MIN_SCALE = 0.3;
  var MAX_SCALE = 40;

  // ---------------------------------------------------------------------
  // Persisted state (localStorage) merged on top of the generated data
  // ---------------------------------------------------------------------
  function loadPersisted() {
    try {
      var raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return { componentOverrides: {}, manualPlacements: {}, reworks: [], samples: [] };
      var parsed = JSON.parse(raw);
      return {
        componentOverrides: parsed.componentOverrides || {},
        manualPlacements: parsed.manualPlacements || {},
        reworks: parsed.reworks || [],
        samples: parsed.samples || [],
      };
    } catch (e) {
      console.warn('Nie udalo sie odczytac zapisanego stanu:', e);
      return { componentOverrides: {}, manualPlacements: {}, reworks: [], samples: [] };
    }
  }

  var persisted = loadPersisted();

  function persist() {
    var componentOverrides = {};
    state.components.forEach(function (c) {
      componentOverrides[c.id] = { delivered: c.delivered, mounted: c.mounted };
    });
    var manualPlacements = {};
    Object.keys(state.placements).forEach(function (designator) {
      var p = state.placements[designator];
      if (p.manual) manualPlacements[designator] = p;
    });
    var payload = {
      componentOverrides: componentOverrides,
      manualPlacements: manualPlacements,
      reworks: state.reworks,
      samples: state.samples,
    };
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch (e) {
      console.warn('Nie udalo sie zapisac stanu (localStorage):', e);
    }
  }

  function uid(prefix) {
    return prefix + '_' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  }

  // ---------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------
  var state = {
    components: DATA.components.map(function (c) {
      var override = persisted.componentOverrides[c.id];
      return Object.assign({}, c, override || {});
    }),
    placements: Object.assign({}, DATA.placements, persisted.manualPlacements),
    selectedComponentId: null,
    mappingDesignator: null,
    activeSide: 'top',
    reworks: persisted.reworks,
    samples: persisted.samples,
  };

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
  var listEmpty = document.getElementById('componentListEmpty');
  var listTable = document.getElementById('componentListTable');

  function escapeHtml(str) {
    return String(str == null ? '' : str).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function renderComponentList() {
    if (state.components.length === 0) {
      listTable.style.display = 'none';
      listEmpty.style.display = 'block';
      return;
    }
    listTable.style.display = '';
    listEmpty.style.display = 'none';

    listBody.innerHTML = state.components.map(function (c) {
      var unplaced = c.designators.filter(function (d) { return !state.placements[d]; });
      var selected = c.id === state.selectedComponentId;
      var unplacedHtml = '';
      if (unplaced.length > 0) {
        var isMappingThis = state.mappingDesignator === unplaced[0];
        unplacedHtml =
          '<div class="component-list__unplaced">Brak pozycji: ' + escapeHtml(unplaced.join(', ')) +
          ' <button type="button" data-action="map" data-designator="' + escapeHtml(unplaced[0]) + '">' +
          (isMappingThis ? 'Anuluj' : 'Ustaw na płytce') + '</button></div>';
      }
      return (
        '<tr class="' + (selected ? 'is-selected' : '') + '" data-component-id="' + c.id + '">' +
        '<td><div class="component-list__designators">' + escapeHtml(c.designators.join(', ')) + '</div>' +
        (c.mpn ? '<div class="component-list__mpn">' + escapeHtml(c.mpn) + '</div>' : '') +
        unplacedHtml +
        '</td>' +
        '<td><div>' + escapeHtml(c.value || '—') + '</div><div class="component-list__footprint">' + escapeHtml(c.footprint || '') + '</div></td>' +
        '<td data-action="stop"><input type="checkbox" data-action="delivered" ' + (c.delivered ? 'checked' : '') + '/></td>' +
        '<td data-action="stop"><input type="checkbox" data-action="mounted" ' + (c.mounted ? 'checked' : '') + '/></td>' +
        '</tr>'
      );
    }).join('');
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
    if (e.target.closest('[data-action="stop"]')) return; // checkbox cell, handled by change listener
    var row = e.target.closest('tr[data-component-id]');
    if (!row) return;
    var id = row.dataset.componentId;
    selectComponent(state.selectedComponentId === id ? null : id);
  });

  listBody.addEventListener('change', function (e) {
    var row = e.target.closest('tr[data-component-id]');
    if (!row) return;
    var component = state.components.find(function (c) { return c.id === row.dataset.componentId; });
    if (!component) return;
    if (e.target.dataset.action === 'delivered') component.delivered = e.target.checked;
    if (e.target.dataset.action === 'mounted') component.mounted = e.target.checked;
    updateMarkerStatus(component);
    updateSummary();
    persist();
  });

  function selectComponent(id) {
    state.selectedComponentId = id;
    renderComponentList();
    document.querySelectorAll('.marker').forEach(function (m) {
      m.classList.toggle('is-selected', m.dataset.componentId === id);
    });
  }

  function updateSummary() {
    var total = 0, delivered = 0, mounted = 0;
    state.components.forEach(function (c) {
      total += c.designators.length;
      if (c.delivered) delivered += c.designators.length;
      if (c.mounted) mounted += c.designators.length;
    });
    document.getElementById('summaryTotal').textContent = total;
    document.getElementById('summaryDelivered').textContent = delivered + '/' + total;
    document.getElementById('summaryMounted').textContent = mounted + '/' + total;
  }

  function statusFill(component) {
    if (component.mounted) return 'var(--marker-mounted)';
    if (component.delivered) return 'var(--marker-delivered)';
    return 'var(--marker-pending)';
  }

  function updateMarkerStatus(component) {
    component.designators.forEach(function (designator) {
      var marker = document.querySelector('.marker[data-designator="' + cssEscape(designator) + '"]');
      if (!marker) return;
      var base = marker.querySelector('.marker__base');
      if (base) base.setAttribute('fill', statusFill(component));
    });
  }

  function cssEscape(value) {
    return window.CSS && CSS.escape ? CSS.escape(value) : value.replace(/["\\]/g, '\\$&');
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

  function buildMarkersSvg(vb) {
    var svgNs = 'http://www.w3.org/2000/svg';
    var g = document.createElementNS(svgNs, 'g');
    g.setAttribute('id', 'markersLayer');

    state.components.forEach(function (component) {
      component.designators.forEach(function (designator) {
        var placement = state.placements[designator];
        if (!placement) return;
        var x = placement.x;
        var y = -placement.y;
        var rad = (placement.rotation * Math.PI) / 180;
        var pinOffset = 1.6;
        var pinX = x + Math.sin(rad) * pinOffset;
        var pinY = y - Math.cos(rad) * pinOffset;

        var marker = document.createElementNS(svgNs, 'g');
        marker.setAttribute('class', 'marker');
        marker.dataset.componentId = component.id;
        marker.dataset.designator = designator;

        var halo = document.createElementNS(svgNs, 'circle');
        halo.setAttribute('class', 'marker__halo');
        halo.setAttribute('cx', x); halo.setAttribute('cy', y); halo.setAttribute('r', 2.2);
        halo.setAttribute('fill', 'none'); halo.setAttribute('stroke', '#ff6a00'); halo.setAttribute('stroke-width', 0.35);

        var base = document.createElementNS(svgNs, 'circle');
        base.setAttribute('class', 'marker__base');
        base.setAttribute('cx', x); base.setAttribute('cy', y); base.setAttribute('r', 0.95);
        base.setAttribute('fill', statusFill(component));

        var pin1 = document.createElementNS(svgNs, 'circle');
        pin1.setAttribute('class', 'marker__pin1');
        pin1.setAttribute('cx', pinX); pin1.setAttribute('cy', pinY); pin1.setAttribute('r', 0.32);

        var label = document.createElementNS(svgNs, 'text');
        label.setAttribute('x', x + 1.6); label.setAttribute('y', y - 1.6);
        label.textContent = designator;

        marker.appendChild(halo);
        marker.appendChild(base);
        marker.appendChild(pin1);
        marker.appendChild(label);
        marker.addEventListener('click', function (evt) {
          evt.stopPropagation();
          selectComponent(state.selectedComponentId === component.id ? null : component.id);
        });
        g.appendChild(marker);
      });
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

    svg.appendChild(buildMarkersSvg(vb));

    bg.addEventListener('click', function () {
      if (state.mappingDesignator) return;
      selectComponent(null);
    });

    stage.appendChild(svg);
    currentSvg = svg;
    document.querySelectorAll('.marker').forEach(function (m) {
      m.classList.toggle('is-selected', m.dataset.componentId === state.selectedComponentId);
    });
    fitToView();
  }

  function updateMappingHint() {
    var viewportEl = viewport;
    viewportEl.classList.toggle('is-mapping', !!state.mappingDesignator);
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
  // Init
  // ---------------------------------------------------------------------
  renderComponentList();
  updateSummary();
  renderBoard();
  updateMappingHint();
  renderReworkPool();
  renderSamples();
})();
