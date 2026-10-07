/**
 * Spatial attractors + SHP overlay for GraphGPU topo.
 *
 * - Map raw GIS coords into the *initial* topo bounding box (shrink xy).
 * - Scale about initial-box center (draggable; Settings toggle show).
 * - Velocity attractors only for type=4 节制 nodes; others follow springs.
 * - Optional SHP layer draws mapped shp positions.
 */
(function graphSpatialLayer() {
	console.log('[topo-spatial BUILD] 20261007-1340 default-layers-on');
	var SCALE_KEY = 'ocisSpatialScale';
	var STRENGTH_KEY = 'ocisSpatialStrength';
	var STRENGTH_BY_TYPE_KEY = 'ocisSpatialStrengthByType';
	var STRENGTH_TYPE_SEL_KEY = 'ocisSpatialStrengthTypeSel';
	var STUB_RADIUS_KEY = 'ocisStubRadius';
	var STUB_SNAP_KEY = 'ocisStubSnap';
	var STUB_PULL_KEY = 'ocisStubPull';
	var SPATIAL_REPULSE_KEY = 'ocisSpatialRepulse';
	var SHOW_CENTER_KEY = 'ocisShowScaleCenter';
	var SHOW_SHP_KEY = 'ocisShowShpLayer';
	var SHOW_ATTRACT_KEY = 'ocisShowAttractLayer';
	var ATTRACT_K_KEY = 'ocisAttractK';
	var FORCE_KIND_KEY = 'ocisForceKinds';
	var OVERLAY_ID = 'ocis-spatial-overlay';
	var FORCE_KINDS = ['shp', 'canal', 'stub'];
	var FORCE_KIND_COLOR = {
		shp: 'rgba(245, 158, 11, 0.9)',
		canal: 'rgba(34, 211, 238, 0.9)',
		stub: 'rgba(192, 132, 252, 0.45)'
	};

	var STRENGTH_TYPES = ['type-4', 'type-0', 'canal', 'stub', 'other'];
	/** @type {Record<string,number>} */
	var strengthByType = Object.create(null);
	var selectedStrengthType = 'type-4';

	var busy = false;
	/** @type {{minX:number,maxX:number,minY:number,maxY:number,cx:number,cy:number,w:number,h:number}|null} */
	var initialBBox = null;
	/** Frozen force-layout AABB — only used for default scaleCenter. */
	/** @type {{minX:number,maxX:number,minY:number,maxY:number,cx:number,cy:number,w:number,h:number}|null} */
	var layoutBBox = null;
	/** Dashed frame = AABB of displayed SHP after 缩放 (attract targets live inside). */
	/** @type {{minX:number,maxX:number,minY:number,maxY:number,cx:number,cy:number,w:number,h:number}|null} */
	var spatialFrame = null;
	/** @type {{x:number,y:number}|null} */
	var scaleCenter = null;
	/** @type {Record<string,{x:number,y:number}>|null} raw GIS for type=4 gates */
	var rawGateGis = null;
	/** @type {Array<{name:string,x:number,y:number}>} raw GIS for shp layer */
	var rawShpAll = [];
	/** @type {Record<string,{x:number,y:number}>|null} mapped attractor targets */
	var forceTargets = null;
	/** @type {Array<{name:string,x:number,y:number}>} mapped shp layer points */
	var mappedShp = [];

	var showScaleCenter = false;
	// SHP 图层 / 吸引虚线默认开启：新域名（如 Tailscale）首次打开即与已有域名一致，
	// 不依赖按域名隔离的 localStorage 才能看到橙色 SHP 目标点与虚线吸引关系。
	var showShpLayer = true;
	var showAttractLayer = true;
	/** @type {Set<string>} */
	var forceKinds = new Set(FORCE_KINDS);
	var overlay = null;
	var octx = null;
	var raf = 0;
	var dragCenter = null;

	try {
		if (localStorage.getItem(SHOW_CENTER_KEY) === '1') showScaleCenter = true;
		if (localStorage.getItem(SHOW_SHP_KEY) === '0') showShpLayer = false;
		if (localStorage.getItem(SHOW_ATTRACT_KEY) === '0') showAttractLayer = false;
	} catch (e0) { /* ignore */ }

	function caseName() {
		if (typeof window.__ocisCurrentCaseName === 'function') {
			return window.__ocisCurrentCaseName() || '';
		}
		var q = new URLSearchParams(window.location.search).get('data');
		return q ? String(q).trim() : '';
	}

	function gObj() {
		return window.g || null;
	}

	function graphOf(g) {
		return g && typeof g.getGraph === 'function' ? g.getGraph() : null;
	}

	function viewDpr() {
		var g = gObj();
		if (g && g.renderer && g.renderer.pixelRatio > 0) return Number(g.renderer.pixelRatio);
		return window.devicePixelRatio || 1;
	}

	function readScale() {
		var el = document.getElementById('ocisSpatialScale');
		var v = el ? Number(el.value) : Number(localStorage.getItem(SCALE_KEY));
		if (!isFinite(v) || v <= 0) v = 1;
		return Math.max(0.2, Math.min(5, v));
	}

	function readAttractK() {
		var el = document.getElementById('ocisAttractK');
		var v = el ? Number(el.value) : Number(localStorage.getItem(ATTRACT_K_KEY));
		if (!isFinite(v) || v <= 0) v = 1;
		return Math.max(0.05, Math.min(5, v));
	}

	function writeAttractK(v, persist) {
		if (!isFinite(v)) return readAttractK();
		v = Math.round(Math.max(0.05, Math.min(5, v)) * 100) / 100;
		var el = document.getElementById('ocisAttractK');
		if (el) el.value = String(v);
		var lab = document.getElementById('ocisAttractKVal');
		if (lab) lab.textContent = v.toFixed(2);
		if (persist !== false) {
			try { localStorage.setItem(ATTRACT_K_KEY, String(v)); } catch (e) { /* ignore */ }
		}
		return v;
	}

	/** Mix toward target: far = close the gap this frame; near = hold. k is 吸引力度. */
	function approachMix(dist, k) {
		var kk = isFinite(k) && k > 0 ? k : 1;
		if (!(dist > 0) || !isFinite(dist)) return 0.2;
		if (dist > 12) return Math.min(0.95, 0.4 + kk * 0.2);
		if (dist > 4) return Math.min(0.8, 0.22 + kk * 0.14);
		return Math.min(0.5, 0.1 + kk * 0.08);
	}

	function disableGlobalSprings() {
		var g = gObj();
		if (!g || !g.layout || !g.layout.config) return;
		var c = g.layout.config;
		c.springConstant = 0;
		// N-body repulsion is what turns direct laterals into a starburst.
		if (spatialActive && !(freeForceTypes && freeForceTypes.size > 0)) {
			c.gravitationalConstant = 0;
			c.centralGravity = 0;
		}
	}

	function writeScale(v, persist) {
		if (!isFinite(v)) return readScale();
		v = Math.round(Math.max(0.2, Math.min(5, v)) * 100) / 100;
		var el = document.getElementById('ocisSpatialScale');
		if (el) el.value = String(v);
		var lab = document.getElementById('ocisSpatialScaleVal');
		if (lab) lab.textContent = v.toFixed(2) + '×';
		if (persist !== false) {
			try { localStorage.setItem(SCALE_KEY, String(v)); } catch (e) { /* ignore */ }
		}
		return v;
	}

	function readStrength() {
		return readStrengthFor(selectedStrengthType);
	}
	function writeStrength(v, persist) {
		return writeStrengthFor(selectedStrengthType, v, persist);
	}

	function defaultStrengthMap() {
		var legacy = Number(localStorage.getItem(STRENGTH_KEY));
		if (!isFinite(legacy) || legacy <= 0) legacy = 0.8;
		var m = Object.create(null);
		STRENGTH_TYPES.forEach(function (t) { m[t] = legacy; });
		return m;
	}

	function loadStrengthByType() {
		strengthByType = defaultStrengthMap();
		try {
			var raw = localStorage.getItem(STRENGTH_BY_TYPE_KEY);
			if (raw) {
				var obj = JSON.parse(raw);
				if (obj && typeof obj === 'object') {
					STRENGTH_TYPES.forEach(function (t) {
						if (obj[t] != null && isFinite(Number(obj[t]))) {
							strengthByType[t] = Number(obj[t]);
						}
					});
				}
			}
			var sel = localStorage.getItem(STRENGTH_TYPE_SEL_KEY);
			if (sel && STRENGTH_TYPES.indexOf(sel) >= 0) selectedStrengthType = sel;
		} catch (e) { /* ignore */ }
	}

	function persistStrengthByType() {
		try {
			localStorage.setItem(STRENGTH_BY_TYPE_KEY, JSON.stringify(strengthByType));
			localStorage.setItem(STRENGTH_TYPE_SEL_KEY, selectedStrengthType);
		} catch (e) { /* ignore */ }
	}

	function clampStrengthValue(v) {
		var max = readParamMax('strength');
		var p = SPATIAL_PARAMS.strength;
		if (!isFinite(v)) v = p.def;
		return roundTo(Math.max(p.min, Math.min(max, v)), p.step);
	}

	function readStrengthFor(type) {
		if (!type || STRENGTH_TYPES.indexOf(type) < 0) type = 'other';
		if (strengthByType[type] == null || !isFinite(strengthByType[type])) {
			strengthByType[type] = SPATIAL_PARAMS.strength.def;
		}
		return clampStrengthValue(strengthByType[type]);
	}

	function writeStrengthFor(type, v, persist) {
		if (!type || STRENGTH_TYPES.indexOf(type) < 0) type = selectedStrengthType;
		v = clampStrengthValue(v);
		strengthByType[type] = v;
		if (type === selectedStrengthType) {
			// Keep shared strength slider UI in sync for the selected type.
			var p = SPATIAL_PARAMS.strength;
			var el = document.getElementById(p.id);
			if (el) {
				el.max = String(readParamMax('strength'));
				el.value = String(v);
			}
			var lab = document.getElementById(p.valId);
			if (lab) lab.textContent = formatParam(p, v);
		}
		if (persist !== false) {
			persistStrengthByType();
			try { localStorage.setItem(STRENGTH_KEY, String(v)); } catch (e) { /* ignore */ }
		}
		return v;
	}

	function readSelectedStrengthType() {
		var el = document.getElementById('ocisStrengthType');
		if (el && el.value && STRENGTH_TYPES.indexOf(el.value) >= 0) {
			selectedStrengthType = el.value;
		}
		return selectedStrengthType;
	}

	function writeSelectedStrengthType(type, persist) {
		if (!type || STRENGTH_TYPES.indexOf(type) < 0) type = 'type-4';
		selectedStrengthType = type;
		var el = document.getElementById('ocisStrengthType');
		if (el) el.value = type;
		// Load that type's strength into the shared slider.
		writeStrengthFor(type, readStrengthFor(type), false);
		if (persist !== false) persistStrengthByType();
		return type;
	}

	function strengthKeyForNode(node) {
		if (!node) return 'other';
		if (isCanalNode(node)) return 'canal';
		var props = node.properties || {};
		var t = props.type;
		if (t == null || t === '') {
			var tag = String(node.tag || '');
			var m = tag.match(/type-?(\d+)/i);
			if (m) t = m[1];
		}
		if (t != null && String(t).trim() !== '' && isFinite(Number(t))) {
			var key = 'type-' + String(Number(t));
			if (key === 'type-0' || key === 'type-4') return key;
		}
		return 'other';
	}

	function readStubRadius() {
		return readParam('stubRadius');
	}
	function writeStubRadius(v, persist) {
		return writeParam('stubRadius', v, persist);
	}
	function readStubSnap() {
		return readParam('stubSnap');
	}
	function writeStubSnap(v, persist) {
		return writeParam('stubSnap', v, persist);
	}
	function readStubPull() {
		return readParam('stubPull');
	}
	function writeStubPull(v, persist) {
		return writeParam('stubPull', v, persist);
	}
	function readSpatialRepulse() {
		return readParam('spatialRepulse');
	}
	function writeSpatialRepulse(v, persist) {
		return writeParam('spatialRepulse', v, persist);
	}

	/**
	 * Tunable force params. Each has value + configurable slider ceiling (上限).
	 * Hard absoluteMax prevents absurd inputs; slider max is user-editable below that.
	 */
	var SPATIAL_PARAMS = {
		strength: {
			id: 'ocisSpatialStrength', valId: 'ocisSpatialStrengthVal', maxId: 'ocisSpatialStrengthMax',
			key: STRENGTH_KEY, maxKey: STRENGTH_KEY + 'Max',
			min: 0.05, def: 0.8, defMax: 5, absoluteMax: 100, step: 0.05, digits: 2
		},
		stubRadius: {
			id: 'ocisStubRadius', valId: 'ocisStubRadiusVal', maxId: 'ocisStubRadiusMax',
			key: STUB_RADIUS_KEY, maxKey: STUB_RADIUS_KEY + 'Max',
			min: 0, def: 2, defMax: 40, absoluteMax: 500, step: 0.5, digits: 1
		},
		stubSnap: {
			id: 'ocisStubSnap', valId: 'ocisStubSnapVal', maxId: 'ocisStubSnapMax',
			key: STUB_SNAP_KEY, maxKey: STUB_SNAP_KEY + 'Max',
			min: 0, def: 0.75, defMax: 1, absoluteMax: 1, step: 0.01, digits: 2
		},
		stubPull: {
			id: 'ocisStubPull', valId: 'ocisStubPullVal', maxId: 'ocisStubPullMax',
			key: STUB_PULL_KEY, maxKey: STUB_PULL_KEY + 'Max',
			min: 1, def: 6, defMax: 20, absoluteMax: 500, step: 0.5, digits: 1
		},
		spatialRepulse: {
			id: 'ocisSpatialRepulse', valId: 'ocisSpatialRepulseVal', maxId: 'ocisSpatialRepulseMax',
			key: SPATIAL_REPULSE_KEY, maxKey: SPATIAL_REPULSE_KEY + 'Max',
			min: 0, def: 0.004, defMax: 0.08, absoluteMax: 5, step: 0.001, digits: 3
		}
	};

	function roundTo(v, step) {
		if (!step || step <= 0) return v;
		return Math.round(v / step) * step;
	}

	function formatParam(p, v) {
		if (p.digits === 0) return String(Math.round(v));
		return Number(v).toFixed(p.digits);
	}

	function readParamMax(name) {
		var p = SPATIAL_PARAMS[name];
		if (!p) return 1;
		var el = document.getElementById(p.maxId);
		var v = el ? Number(el.value) : Number(localStorage.getItem(p.maxKey));
		if (!isFinite(v) || v <= 0) v = p.defMax;
		v = Math.max(p.min + p.step, Math.min(p.absoluteMax, v));
		return v;
	}

	function writeParamMax(name, v, persist) {
		var p = SPATIAL_PARAMS[name];
		if (!p) return 1;
		if (!isFinite(v)) v = readParamMax(name);
		v = Math.max(p.min + p.step, Math.min(p.absoluteMax, v));
		v = roundTo(v, p.step);
		var maxEl = document.getElementById(p.maxId);
		if (maxEl) maxEl.value = String(v);
		var range = document.getElementById(p.id);
		if (range) {
			range.max = String(v);
			var cur = Number(range.value);
			if (isFinite(cur) && cur > v) {
				range.value = String(v);
				writeParam(name, v, persist !== false);
			}
		}
		if (persist !== false) {
			try { localStorage.setItem(p.maxKey, String(v)); } catch (e) { /* ignore */ }
		}
		return v;
	}

	function readParam(name) {
		if (name === 'strength') return readStrength();
		var p = SPATIAL_PARAMS[name];
		if (!p) return 0;
		var max = readParamMax(name);
		var el = document.getElementById(p.id);
		var v = el ? Number(el.value) : Number(localStorage.getItem(p.key));
		if (!isFinite(v)) v = p.def;
		return Math.max(p.min, Math.min(max, v));
	}

	function writeParam(name, v, persist) {
		if (name === 'strength') return writeStrength(v, persist);
		var p = SPATIAL_PARAMS[name];
		if (!p) return 0;
		var max = readParamMax(name);
		if (!isFinite(v)) v = readParam(name);
		v = roundTo(Math.max(p.min, Math.min(max, v)), p.step);
		var el = document.getElementById(p.id);
		if (el) {
			el.max = String(max);
			el.value = String(v);
		}
		var lab = document.getElementById(p.valId);
		if (lab) lab.textContent = formatParam(p, v);
		if (persist !== false) {
			try { localStorage.setItem(p.key, String(v)); } catch (e) { /* ignore */ }
		}
		return v;
	}

	function syncSpatialForceUi() {
		Object.keys(SPATIAL_PARAMS).forEach(function (name) {
			writeParamMax(name, readParamMax(name), false);
		});
		writeSelectedStrengthType(selectedStrengthType, false);
		writeParam('stubRadius', readParam('stubRadius'), false);
		writeParam('stubSnap', readParam('stubSnap'), false);
		writeParam('stubPull', readParam('stubPull'), false);
		writeParam('spatialRepulse', readParam('spatialRepulse'), false);
	}

	function setBusy(on, text) {
		busy = !!on;
		var btn = document.getElementById('ocisSpatialLayout');
		if (!btn) return;
		btn.disabled = busy;
		btn.classList.toggle('active', busy || spatialActive);
		var label = btn.querySelector('.ocis-spatial-label');
		if (label) {
			if (busy) label.textContent = text || '布局中…';
			else label.textContent = spatialActive ? '空间分布中' : '空间分布';
		}
	}

	function persistFlags() {
		try {
			localStorage.setItem(SHOW_CENTER_KEY, showScaleCenter ? '1' : '0');
			localStorage.setItem(SHOW_SHP_KEY, showShpLayer ? '1' : '0');
			localStorage.setItem(SHOW_ATTRACT_KEY, showAttractLayer ? '1' : '0');
		} catch (e) { /* ignore */ }
		syncToggleUi();
	}

	function overlayWanted() {
		return showShpLayer || showScaleCenter || showAttractLayer;
	}

	function forceKindOn(kind) {
		return forceKinds.has(kind);
	}

	function persistForceKinds() {
		try {
			localStorage.setItem(FORCE_KIND_KEY, JSON.stringify(Array.from(forceKinds)));
		} catch (e) { /* ignore */ }
		syncForceKindUi();
	}

	function loadForceKinds() {
		forceKinds = new Set(FORCE_KINDS);
		try {
			var raw = localStorage.getItem(FORCE_KIND_KEY);
			if (raw) {
				var arr = JSON.parse(raw);
				if (Array.isArray(arr)) {
					forceKinds = new Set();
					arr.forEach(function (k) {
						if (FORCE_KINDS.indexOf(k) >= 0) forceKinds.add(k);
					});
				}
			}
		} catch (e) { /* ignore */ }
		syncForceKindUi();
	}

	function syncForceKindUi() {
		var menu = document.getElementById('ocisForceKindMenu');
		if (menu) {
			menu.querySelectorAll('input[data-force-kind]').forEach(function (inp) {
				inp.checked = forceKinds.has(inp.getAttribute('data-force-kind'));
			});
		}
		var sum = document.getElementById('ocisForceKindSummary');
		if (sum) {
			var n = forceKinds.size;
			sum.classList.toggle('active', n > 0 && n < FORCE_KINDS.length);
			sum.innerHTML = n === FORCE_KINDS.length
				? '<i class="ph-graph-bold"></i> 力导类型'
				: ('<i class="ph-graph-bold"></i> 力导类型·' + n);
		}
	}

	function syncToggleUi() {
		var c = document.getElementById('ocisToggleScaleCenter');
		if (c) {
			c.classList.toggle('active', showScaleCenter);
			c.textContent = showScaleCenter ? 'On' : 'Off';
		}
		var s = document.getElementById('ocisToggleShpLayer');
		if (s) {
			s.classList.toggle('active', showShpLayer);
			s.textContent = showShpLayer ? 'On' : 'Off';
		}
		var tb = document.getElementById('ocisShpLayerBtn');
		if (tb) {
			tb.classList.toggle('active', showShpLayer);
			tb.title = showShpLayer
				? ('SHP 图层开 · ' + (mappedShp.length || 0) + ' 点')
				: '显示/隐藏 SHP 映射位置图层';
		}
		var a = document.getElementById('ocisToggleAttractLayer');
		if (a) {
			a.classList.toggle('active', showAttractLayer);
			a.textContent = showAttractLayer ? 'On' : 'Off';
		}
		var ab = document.getElementById('ocisAttractLayerBtn');
		if (ab) {
			ab.classList.toggle('active', showAttractLayer);
			ab.title = showAttractLayer
				? '吸引虚线开 · 再点关闭'
				: '用虚线显示吸引关系（SHP / 渠段 / 内边界）';
		}
		if (overlay) {
			overlay.style.pointerEvents = showScaleCenter ? 'auto' : 'none';
			overlay.style.display = overlayWanted() ? 'block' : 'none';
		}
	}

	/**
	 * Load shp points from API if needed, map into initial topo bbox.
	 * SHP layer can be shown independently of「空间分布」attractors.
	 */
	var shpLoadPromise = null;
	function ensureShpData() {
		if (mappedShp.length) return Promise.resolve(true);
		if (rawShpAll.length && initialBBox) {
			rebuildMapped();
			return Promise.resolve(mappedShp.length > 0);
		}
		if (shpLoadPromise) return shpLoadPromise;
		var name = caseName();
		if (!name) return Promise.resolve(false);
		shpLoadPromise = (async function () {
			try {
				if (!captureInitialBBox(false)) {
					// Wait briefly for graph positions
					await new Promise(function (r) { setTimeout(r, 300); });
					if (!captureInitialBBox(false)) return false;
				}
				if (!scaleCenter && initialBBox) {
					scaleCenter = { x: initialBBox.cx, y: initialBBox.cy };
				}
				var resp = await fetch(
					'/api/graph-spatial-layout?case=' + encodeURIComponent(name) + '&_=' + Date.now(),
					{ cache: 'no-store' }
				);
				var data = await resp.json();
				if (!resp.ok || !data || data.error) {
					console.warn('SHP layer load failed', data && data.error);
					return false;
				}
				rawShpAll = [];
				var layer = data.shpLayer || data.shpPoints || [];
				if (Array.isArray(layer) && layer.length) {
					layer.forEach(function (p) {
						if (!p) return;
						var x = Number(p.x), y = Number(p.y);
						if (!isFinite(x) || !isFinite(y)) return;
						rawShpAll.push({ name: String(p.name || ''), x: x, y: y });
					});
				}
				// Fallback: matched gate targets
				if (!rawShpAll.length && data.targets) {
					Object.keys(data.targets).forEach(function (nm) {
						var p = data.targets[nm];
						if (!p) return;
						var x = Number(p.x), y = Number(p.y);
						if (!isFinite(x) || !isFinite(y)) return;
						rawShpAll.push({ name: nm, x: x, y: y });
					});
				}
				if (!rawGateGis && data.targets) {
					rawGateGis = {};
					Object.keys(data.targets).forEach(function (nm) {
						var p = data.targets[nm];
						if (!p) return;
						var x = Number(p.x), y = Number(p.y);
						if (!isFinite(x) || !isFinite(y)) return;
						rawGateGis[nm] = {
							x: x,
							y: y,
							shpName: String(p.shpName || nm).trim()
						};
					});
				}
				rebuildMapped();
				console.log('SHP layer ready', mappedShp.length, 'pts', initialBBox);
				return mappedShp.length > 0;
			} catch (err) {
				console.warn('SHP layer load error', err);
				return false;
			} finally {
				shpLoadPromise = null;
			}
		})();
		return shpLoadPromise;
	}

	function setShpVisible(on) {
		showShpLayer = !!on;
		persistFlags();
		if (showShpLayer) {
			startPaintLoop();
			ensureShpData().then(function (ok) {
				syncToggleUi();
				if (!ok) console.warn('SHP layer: no points to show');
			});
		} else {
			syncToggleUi();
		}
	}

	function setAttractVisible(on) {
		showAttractLayer = !!on;
		persistFlags();
		if (showAttractLayer) {
			startPaintLoop();
			if (forceKindOn('shp')) ensureShpData();
		} else {
			syncToggleUi();
		}
	}

	function collectAttractLinks() {
		var links = [];
		var g = gObj();
		var graph = graphOf(g);
		if (!g || !graph) return links;
		if (forceKindOn('shp') && !forceTargets && (rawShpAll.length || rawGateGis) && initialBBox) {
			rebuildMapped();
		}
		var byName = Object.create(null);
		graph.activeNodeIds().forEach(function (id) {
			var node = graph.getNode(id);
			if (!node) return;
			var name = nodeDisplayName(node);
			if (name) byName[name] = node;
		});
		function posOf(id) {
			var x = graph.positions[id * 2];
			var y = graph.positions[id * 2 + 1];
			if (!isFinite(x) || !isFinite(y)) return null;
			return { x: x, y: y };
		}
		if (forceKindOn('shp')) {
			var shpSrc = shpTargetMap();
			if (!Object.keys(shpSrc).length) shpSrc = null;
			if (shpSrc) {
				Object.keys(shpSrc).forEach(function (name) {
					var node = byName[name];
					var tgt = shpSrc[name];
					if (!node || !tgt || isCanalNode(node)) return;
					var p = posOf(node.id);
					if (!p) return;
					links.push({ kind: 'shp', x0: p.x, y0: p.y, x1: tgt.x, y1: tgt.y });
				});
			}
		}
		if (forceKindOn('canal')) {
			graph.activeNodeIds().forEach(function (id) {
				var node = graph.getNode(id);
				if (!isCanalNode(node)) return;
				var props = node.properties || {};
				var sNode = byName[String(props.source || '').trim()];
				var tNode = byName[String(props.target || '').trim()];
				var p = posOf(id);
				if (!p) return;
				if (sNode) {
					var sp = posOf(sNode.id);
					if (sp) links.push({ kind: 'canal', x0: p.x, y0: p.y, x1: sp.x, y1: sp.y });
				}
				if (tNode) {
					var tp = posOf(tNode.id);
					if (tp) links.push({ kind: 'canal', x0: p.x, y0: p.y, x1: tp.x, y1: tp.y });
				}
			});
		}
		if (forceKindOn('stub')) {
			var parentOf = buildStubParents(graph);
			Object.keys(parentOf).forEach(function (stubIdStr) {
				var stubId = Number(stubIdStr);
				var parentId = parentOf[stubId];
				var stub = graph.getNode(stubId);
				if (!stub || isCanalNode(stub)) return;
				if (forceTargets && forceTargets[nodeDisplayName(stub)]) return;
				var attractId = resolveStubAttractId(g, graph, stubId, parentId);
				var a = posOf(attractId);
				var s = posOf(stubId);
				if (!a || !s) return;
				links.push({ kind: 'stub', x0: s.x, y0: s.y, x1: a.x, y1: a.y });
			});
		}
		return links;
	}

	function makeBox(minX, maxX, minY, maxY, padFrac) {
		var w = Math.max(maxX - minX, 1);
		var h = Math.max(maxY - minY, 1);
		var pad = padFrac == null ? 0.05 : padFrac;
		return {
			minX: minX + w * pad,
			maxX: maxX - w * pad,
			minY: minY + h * pad,
			maxY: maxY - h * pad,
			cx: (minX + maxX) / 2,
			cy: (minY + maxY) / 2,
			w: w * (1 - 2 * pad),
			h: h * (1 - 2 * pad)
		};
	}

	/** Capture force-layout AABB once = 初始框. SHP always maps into this box. */
	function captureInitialBBox(force) {
		if (layoutBBox && !force) {
			initialBBox = layoutBBox;
			window.__ocisInitialBBox = initialBBox;
			return layoutBBox;
		}
		var g = gObj();
		var graph = graphOf(g);
		if (!graph) return null;
		var minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
		var n = 0;
		graph.activeNodeIds().forEach(function (id) {
			var x = graph.positions[id * 2];
			var y = graph.positions[id * 2 + 1];
			if (!isFinite(x) || !isFinite(y)) return;
			if (x < minX) minX = x;
			if (x > maxX) maxX = x;
			if (y < minY) minY = y;
			if (y > maxY) maxY = y;
			n += 1;
		});
		if (!n || !isFinite(minX)) return null;
		layoutBBox = makeBox(minX, maxX, minY, maxY, 0.05);
		initialBBox = layoutBBox;
		spatialFrame = null;
		if (!scaleCenter) {
			scaleCenter = { x: layoutBBox.cx, y: layoutBBox.cy };
		}
		window.__ocisInitialBBox = initialBBox;
		return layoutBBox;
	}

	function resetScaleCenter() {
		if (!layoutBBox) captureInitialBBox(false);
		if (!layoutBBox) return;
		scaleCenter = { x: layoutBBox.cx, y: layoutBBox.cy };
		rebuildMapped();
	}

	/**
	 * GIS → 初始框: uniform shrink into layoutBBox about scaleCenter.
	 * 缩放=1 → every SHP marker inside the dashed 初始框.
	 * 缩放 multiplies about center (may leave box if >1).
	 * Attract targets = these displayed marker positions.
	 */
	function buildMapper() {
		var box = layoutBBox || initialBBox;
		var center = scaleCenter;
		if (!center && box) center = { x: box.cx, y: box.cy };
		if (!box || !center) return null;
		var pts = [];
		if (rawGateGis) {
			Object.keys(rawGateGis).forEach(function (nm) {
				var p = rawGateGis[nm];
				if (!p) return;
				var x = Number(p.x), y = Number(p.y);
				if (!isFinite(x) || !isFinite(y)) return;
				pts.push({ x: x, y: y });
			});
		}
		rawShpAll.forEach(function (p) {
			var x = Number(p.x), y = Number(p.y);
			if (!isFinite(x) || !isFinite(y)) return;
			pts.push({ x: x, y: y });
		});
		if (!pts.length) return null;

		var gMinX = Infinity, gMaxX = -Infinity, gMinY = Infinity, gMaxY = -Infinity;
		pts.forEach(function (p) {
			if (p.x < gMinX) gMinX = p.x;
			if (p.x > gMaxX) gMaxX = p.x;
			if (p.y < gMinY) gMinY = p.y;
			if (p.y > gMaxY) gMaxY = p.y;
		});
		var gdx = Math.max(gMaxX - gMinX, 1e-9);
		var gdy = Math.max(gMaxY - gMinY, 1e-9);
		var gcx = (gMinX + gMaxX) / 2;
		var gcy = (gMinY + gMaxY) / 2;
		var sUni = Math.min(box.w / gdx, box.h / gdy);
		var s = sUni * readScale();
		return {
			map: function (gx, gy) {
				return {
					x: center.x + (gx - gcx) * s,
					y: center.y + (gy - gcy) * s
				};
			},
			sUni: sUni,
			s: s,
			gcx: gcx,
			gcy: gcy
		};
	}

	function rebuildMapped() {
		var mapper = buildMapper();
		forceTargets = null;
		mappedShp = [];
		if (!mapper) return;
		// 缩放后图层上画出来的点 = 吸引目标
		var byShpName = Object.create(null);
		rawShpAll.forEach(function (p) {
			var m = mapper.map(Number(p.x), Number(p.y));
			var entry = { name: p.name, x: m.x, y: m.y };
			mappedShp.push(entry);
			if (p.name) byShpName[p.name] = entry;
		});
		if (rawGateGis) {
			forceTargets = {};
			Object.keys(rawGateGis).forEach(function (nm) {
				var p = rawGateGis[nm];
				if (!p) return;
				var shpNm = String(p.shpName || nm).trim();
				var shown = (shpNm && byShpName[shpNm]) || byShpName[nm];
				if (shown) {
					forceTargets[nm] = { x: shown.x, y: shown.y, shpName: shown.name };
					return;
				}
				var m = mapper.map(Number(p.x), Number(p.y));
				forceTargets[nm] = { x: m.x, y: m.y, shpName: shpNm || nm };
			});
		}
		// 初始框 never replaced by SHP extent
		if (layoutBBox) {
			initialBBox = layoutBBox;
			window.__ocisInitialBBox = initialBBox;
		}
		spatialFrame = null;
		window.__ocisSpatialTargets = forceTargets;
		window.__ocisMappedShp = mappedShp;
	}

	/** Stamp type=4 onto node.properties from edge CSV type (GraphGPU nodes lack type by default). */
	function stampType4FromEdges() {
		var g = gObj();
		var graph = graphOf(g);
		if (!graph || typeof graph.activeEdgeIds !== 'function') return 0;
		var byName = Object.create(null);
		graph.activeNodeIds().forEach(function (id) {
			var node = graph.getNode(id);
			if (!node) return;
			var props = node.properties || (node.properties = {});
			var name = String(props.name || props.title || '').trim();
			if (name) byName[name] = node;
		});
		var marked = Object.create(null);
		function mark(name) {
			if (!name || marked[name]) return;
			var node = byName[name];
			if (!node) return;
			if (!node.properties) node.properties = {};
			node.properties.type = 4;
			marked[name] = true;
		}
		graph.activeEdgeIds().forEach(function (eid) {
			var e = graph.getEdge(eid);
			if (!e) return;
			var p = e.properties || {};
			var typ = Number(p.type != null ? p.type : e.tag);
			if (typ !== 4) return;
			var ctype = String(p.ConnectionType || e.tag || '').trim().toLowerCase();
			var s = String(p.source || '').trim();
			var t = String(p.target || '').trim();
			if (ctype === 'indirect') {
				mark(s);
				if (t && /节制/.test(t)) mark(t);
			} else {
				mark(t || s);
			}
		});
		return Object.keys(marked).length;
	}

	function nodeIsType4(node) {
		if (!node) return false;
		var props = node.properties || {};
		var t = props.type != null ? props.type : null;
		if (t != null && t !== '') {
			if (String(t).trim() === '4' || Number(t) === 4) return true;
		}
		var tag = String(node.tag || '').trim();
		if (tag === '4' || tag === 'type-4' || /type-?4$/i.test(tag)) return true;
		return false;
	}

	var spatialActive = false;
	var savedPhysics = null;
	var FREE_FORCE_KEY = 'ocisSpatialFreeForceTypes';
	/** @type {Record<number,{x:number,y:number}>} frozen positions for non-free unmatched nodes */
	var frozenPos = Object.create(null);
	/** @type {Set<string>} */
	var freeForceTypes = new Set();

	function loadFreeForceTypes() {
		freeForceTypes = new Set();
		try {
			var raw = localStorage.getItem(FREE_FORCE_KEY);
			if (raw) {
				JSON.parse(raw).forEach(function (k) {
					if (k) freeForceTypes.add(String(k));
				});
			}
		} catch (e) { /* ignore */ }
		syncFreeForceUi();
	}

	function persistFreeForceTypes() {
		try {
			localStorage.setItem(FREE_FORCE_KEY, JSON.stringify(Array.from(freeForceTypes)));
		} catch (e) { /* ignore */ }
		syncFreeForceUi();
	}

	function syncFreeForceUi() {
		var menu = document.getElementById('ocisFreeForceMenu');
		if (!menu) return;
		menu.querySelectorAll('input[data-free]').forEach(function (inp) {
			var key = inp.getAttribute('data-free');
			inp.checked = freeForceTypes.has(key);
		});
		var sum = document.querySelector('#ocisFreeForceWrap > summary');
		if (sum) {
			var n = freeForceTypes.size;
			sum.innerHTML = n
				? ('<i class="ph-faders-bold"></i> 自由力导·' + n)
				: '<i class="ph-faders-bold"></i> 自由力导';
		}
	}

	function nodeTypeKey(node) {
		if (!node) return 'other';
		if (isCanalNode(node)) return 'canal';
		var props = node.properties || {};
		var t = props.type;
		if (t == null || t === '') {
			var tag = String(node.tag || '');
			var m = tag.match(/type-?(\d+)/i);
			if (m) t = m[1];
		}
		if (t != null && String(t).trim() !== '' && isFinite(Number(t))) {
			return 'type-' + String(Number(t));
		}
		return 'other';
	}

	function isShpAnchorName(name) {
		return !!(forceTargets && name && forceTargets[name]);
	}

	function allowFreeForce(category) {
		return freeForceTypes.has(category);
	}

	/** Rebuild freeze set: unmatched + not in free-force allowlist stay put. */
	function rebuildFrozenNodes() {
		frozenPos = Object.create(null);
		var g = gObj();
		var graph = graphOf(g);
		if (!g || !graph) return;
		var stubParents = buildStubParents(graph);
		var namedFree = { canal: 1, stub: 1, 'type-0': 1, 'type-2': 1, 'type-4': 1, 'type-6': 1 };
		graph.activeNodeIds().forEach(function (id) {
			var node = graph.getNode(id);
			if (!node) return;
			var name = nodeDisplayName(node);
			// SHP-matched anchors always move toward shp (unless that type is free-force)
			if (isShpAnchorName(name)) {
				var shpCat = nodeTypeKey(node);
				if (allowFreeForce(shpCat) || allowFreeForce('other')) {
					if (typeof g.unpinNode === 'function') g.unpinNode(id);
					else if (g.layout && g.layout.pinned) g.layout.pinned.delete(id);
					return;
				}
				if (typeof g.unpinNode === 'function') g.unpinNode(id);
				return;
			}
			var isStub = stubParents[id] != null && !isCanalNode(node);
			var cat = isStub ? 'stub' : nodeTypeKey(node);

			// Hierarchy followers (when not marked free): move via attractors, not frozen
			if (cat === 'canal' && !allowFreeForce('canal')) {
				if (typeof g.unpinNode === 'function') g.unpinNode(id);
				else if (g.layout && g.layout.pinned) g.layout.pinned.delete(id);
				return;
			}
			if (cat === 'stub' && !allowFreeForce('stub')) {
				if (typeof g.unpinNode === 'function') g.unpinNode(id);
				else if (g.layout && g.layout.pinned) g.layout.pinned.delete(id);
				return;
			}

			// User-allowed free force
			if (allowFreeForce(cat)) {
				if (typeof g.unpinNode === 'function') g.unpinNode(id);
				else if (g.layout && g.layout.pinned) g.layout.pinned.delete(id);
				return;
			}
			if (allowFreeForce('other') && !namedFree[cat]) {
				if (typeof g.unpinNode === 'function') g.unpinNode(id);
				else if (g.layout && g.layout.pinned) g.layout.pinned.delete(id);
				return;
			}

			// Default: freeze unmatched (一干渠尾 / 出口节制闸 without shp, etc.)
			var x = graph.positions[id * 2];
			var y = graph.positions[id * 2 + 1];
			if (!isFinite(x) || !isFinite(y)) return;
			frozenPos[id] = { x: x, y: y };
			if (typeof g.pinNode === 'function') g.pinNode(id);
			else if (g.layout && g.layout.pinned) g.layout.pinned.add(id);
		});
	}

	function applyFrozenNodes() {
		var g = gObj();
		var graph = graphOf(g);
		if (!g || !graph || !g.layout) return;
		var vel = g.layout.velocities;
		Object.keys(frozenPos).forEach(function (idStr) {
			var id = Number(idStr);
			var p = frozenPos[id];
			if (!p) return;
			graph.positions[id * 2] = p.x;
			graph.positions[id * 2 + 1] = p.y;
			if (vel) {
				vel[id * 2] = 0;
				vel[id * 2 + 1] = 0;
			}
			if (g.layout.pinned) g.layout.pinned.add(id);
		});
		graph.dirtyNodes = true;
		graph.dirtyEdges = true;
	}

	function clearFrozenNodes() {
		var g = gObj();
		Object.keys(frozenPos).forEach(function (idStr) {
			var id = Number(idStr);
			if (g && typeof g.unpinNode === 'function') g.unpinNode(id);
		});
		frozenPos = Object.create(null);
	}

	function setSpatialButtonActive(on) {
		var btn = document.getElementById('ocisSpatialLayout');
		if (!btn) return;
		btn.classList.toggle('active', !!on);
		btn.setAttribute('aria-pressed', on ? 'true' : 'false');
		var label = btn.querySelector('.ocis-spatial-label');
		if (label && !busy) label.textContent = on ? '空间分布中' : '空间分布';
	}

	function softenPhysicsForSpatial() {
		var g = gObj();
		if (!g || !g.layout || !g.layout.config) return;
		var c = g.layout.config;
		if (!savedPhysics) {
			savedPhysics = {
				gravitationalConstant: c.gravitationalConstant,
				springLength: c.springLength,
				springConstant: c.springConstant,
				centralGravity: c.centralGravity,
				damping: c.damping,
				maxVelocity: c.maxVelocity,
				timestep: c.timestep
			};
		}
		var stubR = readStubRadius();
		var sizeF = 1;
		if (window.__ocisNodeSizeByTag && typeof window.__ocisNodeSizeByTag.sizeScaleFactor === 'function') {
			sizeF = window.__ocisNodeSizeByTag.sizeScaleFactor() || 1;
		}
		var posL = springLengthFromPositions();
		var freeOn = freeForceTypes && freeForceTypes.size > 0;
		if (freeOn) {
			// Free-force needs real springs/repulsion; ultra-soft profile makes “自由力导” look dead.
			var rep = Math.max(readSpatialRepulse(), 0.025);
			c.gravitationalConstant = -rep * sizeF;
			c.springLength = posL > 0 ? posL : Math.max(12, stubR * 3 + 8) * sizeF;
			c.springConstant = 0;
			c.centralGravity = 0.004;
			c.damping = 0.72;
			c.maxVelocity = 22;
			c.timestep = 0.4;
		} else {
			c.gravitationalConstant = 0;
			c.springLength = posL > 0 ? posL : Math.max(1, stubR * 1.02 + 0.5) * sizeF;
			c.springConstant = 0;
			c.centralGravity = 0;
			c.damping = 0.85;
			c.maxVelocity = 28;
			c.timestep = 0.5;
		}
	}

	function restorePhysics() {
		var g = gObj();
		if (!g || !g.layout || !g.layout.config || !savedPhysics) return;
		Object.keys(savedPhysics).forEach(function (k) {
			g.layout.config[k] = savedPhysics[k];
		});
		syncGpuSpringFromPositions();
		disableGlobalSprings();
		if (window.__ocisNodeSizeByTag && typeof window.__ocisNodeSizeByTag.syncSpacing === 'function') {
			window.__ocisNodeSizeByTag.syncSpacing();
		}
	}

	function isCanalNode(node) {
		if (!node) return false;
		var props = node.properties || {};
		var kind = String(props.kind || node.tag || '').trim();
		var name = String(props.name || props.title || '').trim();
		return kind === '渠段' || node.tag === '渠段' || /^渠段-/.test(name);
	}

	function nodeDisplayName(node) {
		if (!node) return '';
		var props = node.properties || {};
		return String(props.name || props.title || '').trim();
	}

	function nodePosOf(graph, id) {
		var x = graph.positions[id * 2];
		var y = graph.positions[id * 2 + 1];
		if (!isFinite(x) || !isFinite(y)) return null;
		return { x: x, y: y };
	}

	function writePos(graph, id, x, y) {
		if (!graph || !isFinite(x) || !isFinite(y)) return;
		if (typeof graph.setNodePosition === 'function') graph.setNodePosition(id, x, y);
		else {
			graph.positions[id * 2] = x;
			graph.positions[id * 2 + 1] = y;
			graph.dirtyNodes = true;
			graph.dirtyEdges = true;
		}
	}

	var savedZoomMin = null;

	function allowCameraForShp() {
		var g = gObj();
		if (!g || !g.camera || !forceTargets) return;
		var names = Object.keys(forceTargets);
		if (names.length < 2) return;
		var minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
		names.forEach(function (nm) {
			var p = forceTargets[nm];
			if (!p) return;
			if (p.x < minX) minX = p.x;
			if (p.x > maxX) maxX = p.x;
			if (p.y < minY) minY = p.y;
			if (p.y > maxY) maxY = p.y;
		});
		var w = Math.max(maxX - minX, 1) * 1.3;
		var h = Math.max(maxY - minY, 1) * 1.3;
		var cam = g.camera;
		var need = Math.min(
			2 * 0.85 * (cam.aspectRatio || 1) / w,
			2 * 0.85 / h
		);
		if (!(need > 0) || !isFinite(need)) return;
		if (savedZoomMin == null) savedZoomMin = cam.zoomMin;
		cam.zoomMin = Math.min(cam.zoomMin, need * 0.45);
	}

	function restoreCameraZoomMin() {
		var g = gObj();
		if (g && g.camera && savedZoomMin != null) g.camera.zoomMin = savedZoomMin;
		savedZoomMin = null;
	}

	function fitGraphView() {
		var g = gObj();
		if (!g) return;
		// 初始框尺度下默认相机足够；缩放>1 才放宽 zoomMin
		if (readScale() > 1.05) allowCameraForShp();
		if (typeof g.fitView === 'function') g.fitView(0.15);
	}

	function gisMinPair(pts) {
		var minD = Infinity;
		var i, j, d;
		for (i = 0; i < pts.length; i++) {
			for (j = i + 1; j < pts.length; j++) {
				d = Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y);
				if (d > 1e-6 && d < minD) minD = d;
			}
		}
		return minD;
	}

	function distPts(a, b) {
		var dx = a.x - b.x;
		var dy = a.y - b.y;
		return Math.sqrt(dx * dx + dy * dy);
	}

	function edgeIsIndirect(e) {
		if (!e) return false;
		var tag = String(e.tag || '').toLowerCase();
		var ctype = String((e.properties && e.properties.ConnectionType) || tag || '').toLowerCase();
		return ctype === 'indirect' || tag === 'indirect';
	}

	function nameIndex(graph) {
		var byName = Object.create(null);
		graph.activeNodeIds().forEach(function (id) {
			var node = graph.getNode(id);
			var name = nodeDisplayName(node);
			if (name) byName[name] = node;
		});
		return byName;
	}

	/** Attract targets = currently displayed SHP markers (after 缩放/scaleCenter). */
	function shpTargetMap() {
		var map = Object.create(null);
		if (forceTargets) {
			Object.keys(forceTargets).forEach(function (name) {
				var p = forceTargets[name];
				if (p && isFinite(p.x) && isFinite(p.y)) map[name] = p;
			});
		}
		return map;
	}

	function isShpAnchorNode(node) {
		if (!node || isCanalNode(node)) return false;
		var name = nodeDisplayName(node);
		if (!name) return false;
		if (forceTargets && forceTargets[name]) return true;
		if (!mappedShp || !mappedShp.length) return false;
		for (var i = 0; i < mappedShp.length; i++) {
			if (mappedShp[i] && mappedShp[i].name === name) return true;
		}
		return false;
	}

	function unpinNodeId(g, id) {
		if (!g) return;
		if (typeof g.unpinNode === 'function') g.unpinNode(id);
		else if (g.layout && g.layout.pinned && g.layout.pinned.delete) g.layout.pinned.delete(id);
	}

	function pinNodeId(g, id) {
		if (!g) return;
		if (typeof g.pinNode === 'function') g.pinNode(id);
		else if (g.layout && g.layout.pinned && g.layout.pinned.add) g.layout.pinned.add(id);
	}

	function unpinAllNodes() {
		var g = gObj();
		var graph = graphOf(g);
		if (!g || !graph) return;
		graph.activeNodeIds().forEach(function (id) { unpinNodeId(g, id); });
		frozenPos = Object.create(null);
	}

	/** Mean SHP displacement this frame — followers use this so the graph moves with GIS. */
	var lastShpDelta = { x: 0, y: 0 };

	/**
	 * SHP is the root constraint. Write matched 节制/水源 onto mapped GIS after (and
	 * before) GPU tick — otherwise origTick restores force-layout positions.
	 */
	function placeShpAnchors() {
		if (!spatialActive || !forceKindOn('shp')) {
			lastShpDelta = { x: 0, y: 0 };
			return 0;
		}
		var g = gObj();
		var graph = graphOf(g);
		if (!g || !graph) {
			lastShpDelta = { x: 0, y: 0 };
			return 0;
		}
		var vel = g.layout && g.layout.velocities;
		var anchors = shpTargetMap();
		var byName = nameIndex(graph);
		var gain = readAttractK();
		// 吸引线有力：每帧按剩余距离拉近（力度越大越快），贴到 0.05 内直接吸附到显示点。
		var alpha = Math.min(0.6, 0.02 + gain * 0.08);
		var n = 0;
		var sx = 0, sy = 0;
		Object.keys(anchors).forEach(function (name) {
			var node = byName[name];
			if (!node || isCanalNode(node)) return;
			var sk = strengthKeyForNode(node);
			if (allowFreeForce(sk) || allowFreeForce('other')) return;
			var tgt = anchors[name];
			var x = graph.positions[node.id * 2];
			var y = graph.positions[node.id * 2 + 1];
			if (!isFinite(x) || !isFinite(y) || !tgt || !isFinite(tgt.x) || !isFinite(tgt.y)) return;
			var dx = tgt.x - x;
			var dy = tgt.y - y;
			var dist = Math.sqrt(dx * dx + dy * dy);
			var nx, ny;
			if (dist < 0.05) {
				nx = tgt.x;
				ny = tgt.y;
			} else {
				nx = x + dx * alpha;
				ny = y + dy * alpha;
			}
			sx += nx - x;
			sy += ny - y;
			writePos(graph, node.id, nx, ny);
			if (vel) {
				vel[node.id * 2] = 0;
				vel[node.id * 2 + 1] = 0;
			}
			pinNodeId(g, node.id);
			n += 1;
		});
		lastShpDelta = n ? { x: sx / n, y: sy / n } : { x: 0, y: 0 };
		if (n) {
			graph.dirtyNodes = true;
			graph.dirtyEdges = true;
			if (typeof g.markDirty === 'function') g.markDirty();
		}
		return n;
	}

	/** Everyone except SHP anchors follows the mean SHP move, then canals snap to ends. */
	function applyFollowShp() {
		if (!spatialActive) return 0;
		var dx = lastShpDelta.x;
		var dy = lastShpDelta.y;
		if (!isFinite(dx) || !isFinite(dy)) return 0;
		if (Math.abs(dx) < 1e-8 && Math.abs(dy) < 1e-8) return 0;
		var g = gObj();
		var graph = graphOf(g);
		if (!g || !graph) return 0;
		var vel = g.layout && g.layout.velocities;
		var stubParents = forceKindOn('stub') && !allowFreeForce('stub') ? buildStubParents(graph) : Object.create(null);
		var n = 0;
		graph.activeNodeIds().forEach(function (id) {
			var node = graph.getNode(id);
			if (!node) return;
			if (isShpAnchorNode(node)) return;
			if (stubParents[id] != null && !isCanalNode(node)) return;
			writePos(graph, id, graph.positions[id * 2] + dx, graph.positions[id * 2 + 1] + dy);
			if (vel) {
				vel[id * 2] = 0;
				vel[id * 2 + 1] = 0;
			}
			unpinNodeId(g, id);
			n += 1;
		});
		if (n) {
			graph.dirtyNodes = true;
			graph.dirtyEdges = true;
		}
		return n;
	}

	function placeCanalFollowers() {
		if (!spatialActive || !forceKindOn('canal') || allowFreeForce('canal')) return 0;
		var g = gObj();
		var graph = graphOf(g);
		if (!g || !graph) return 0;
		var vel = g.layout && g.layout.velocities;
		var byName = nameIndex(graph);
		var n = 0;
		graph.activeNodeIds().forEach(function (id) {
			var node = graph.getNode(id);
			if (!isCanalNode(node)) return;
			var props = node.properties || {};
			var sNode = byName[String(props.source || '').trim()];
			var tNode = byName[String(props.target || '').trim()];
			if (!sNode || !tNode) return;
			var sx = graph.positions[sNode.id * 2];
			var sy = graph.positions[sNode.id * 2 + 1];
			var tx = graph.positions[tNode.id * 2];
			var ty = graph.positions[tNode.id * 2 + 1];
			if (![sx, sy, tx, ty].every(isFinite)) return;
			writePos(graph, id, (sx + tx) * 0.5, (sy + ty) * 0.5);
			if (vel) {
				vel[id * 2] = 0;
				vel[id * 2 + 1] = 0;
			}
			unpinNodeId(g, id);
			n += 1;
		});
		if (n) {
			graph.dirtyNodes = true;
			graph.dirtyEdges = true;
		}
		return n;
	}

	function canalEndSpan(graph, canalNode, byName) {
		if (!canalNode) return 0;
		var props = canalNode.properties || {};
		var a = byName[String(props.source || '').trim()];
		var b = byName[String(props.target || '').trim()];
		if (!a || !b) return 0;
		var pa = nodePosOf(graph, a.id);
		var pb = nodePosOf(graph, b.id);
		if (!pa || !pb) return 0;
		return distPts(pa, pb);
	}

	/**
	 * Per-edge rest length from current node positions.
	 * 渠段: half the distance between its two end nodes (updates as gates move).
	 * direct: stub ring when 内边界吸引 is on, else current length.
	 */
	function restLengthForEdge(graph, e, byName) {
		var sNode = graph.getNode(e.source);
		var tNode = graph.getNode(e.target);
		var ps = nodePosOf(graph, e.source);
		var pt = nodePosOf(graph, e.target);
		var cur = ps && pt ? distPts(ps, pt) : 0;
		if (edgeIsIndirect(e) || isCanalNode(sNode) || isCanalNode(tNode)) {
			var canal = isCanalNode(sNode) ? sNode : (isCanalNode(tNode) ? tNode : null);
			if (canal) {
				var span = canalEndSpan(graph, canal, byName);
				if (span > 1) return span * 0.5;
			}
			return cur > 0 ? cur : 0;
		}
		if (forceKindOn('stub') && !allowFreeForce('stub')) {
			return Math.max(readStubRadius(), 1.5);
		}
		return cur > 0 ? cur : 0;
	}

	function medianOf(values) {
		if (!values.length) return 0;
		values.sort(function (a, b) { return a - b; });
		var m = Math.floor(values.length / 2);
		if (values.length % 2) return values[m];
		return (values[m - 1] + values[m]) * 0.5;
	}

	/** GPU has one springLength; drive it from current 渠段/indirect spacing (never a fixed 55). */
	function springLengthFromPositions() {
		var g = gObj();
		var graph = graphOf(g);
		if (!graph || typeof graph.activeEdgeIds !== 'function') return 0;
		var byName = nameIndex(graph);
		var canalRests = [];
		var allRests = [];
		graph.activeEdgeIds().forEach(function (eid) {
			var e = graph.getEdge(eid);
			if (!e) return;
			var L = restLengthForEdge(graph, e, byName);
			if (!(L > 0) || !isFinite(L)) return;
			allRests.push(L);
			if (edgeIsIndirect(e) || isCanalNode(graph.getNode(e.source)) || isCanalNode(graph.getNode(e.target))) {
				canalRests.push(L);
			}
		});
		var med = medianOf(canalRests.length ? canalRests : allRests);
		if (!(med > 0) || !isFinite(med)) return 0;
		return Math.max(2, Math.min(800, med));
	}

	function syncGpuSpringFromPositions() {
		var g = gObj();
		if (!g || !g.layout || !g.layout.config) return 0;
		var L = springLengthFromPositions();
		if (!(L > 0)) return 0;
		g.layout.config.springLength = L;
		window.__ocisBaseSpringLength = L;
		return L;
	}

	/** CPU Hooke springs with per-edge rest from node positions (GPU cannot). */
	function applyPerEdgeSprings() {
		var g = gObj();
		var graph = graphOf(g);
		if (!g || !graph || !g.layout) return 0;
		var vel = g.layout.velocities;
		var byName = nameIndex(graph);
		var k = 0.07;
		var n = 0;
		graph.activeEdgeIds().forEach(function (eid) {
			var e = graph.getEdge(eid);
			if (!e) return;
			if (!edgeIsIndirect(e) && forceKindOn('stub') && !allowFreeForce('stub')) return;
			var rest = restLengthForEdge(graph, e, byName);
			if (!(rest > 0)) return;
			var ps = nodePosOf(graph, e.source);
			var pt = nodePosOf(graph, e.target);
			if (!ps || !pt) return;
			var d = distPts(ps, pt);
			if (!(d > 1e-4)) return;
			var stretch = d - rest;
			if (Math.abs(stretch) < 0.15) return;
			var ux = (pt.x - ps.x) / d;
			var uy = (pt.y - ps.y) / d;
			var mag = stretch * k;
			var sNode = graph.getNode(e.source);
			var tNode = graph.getNode(e.target);
			var srcShp = spatialActive && isShpAnchorNode(sNode);
			var tgtShp = spatialActive && isShpAnchorNode(tNode);
			if (srcShp && tgtShp) return;
			var ws = 0.5;
			var wt = 0.5;
			if (srcShp) {
				ws = 0;
				wt = 1;
			} else if (tgtShp) {
				ws = 1;
				wt = 0;
			} else if (isCanalNode(sNode) && !isCanalNode(tNode)) {
				ws = 0.85;
				wt = 0.15;
			} else if (isCanalNode(tNode) && !isCanalNode(sNode)) {
				ws = 0.15;
				wt = 0.85;
			}
			graph.positions[e.source * 2] = ps.x + ux * mag * ws;
			graph.positions[e.source * 2 + 1] = ps.y + uy * mag * ws;
			graph.positions[e.target * 2] = pt.x - ux * mag * wt;
			graph.positions[e.target * 2 + 1] = pt.y - uy * mag * wt;
			if (vel) {
				vel[e.source * 2] *= 0.7;
				vel[e.source * 2 + 1] *= 0.7;
				vel[e.target * 2] *= 0.7;
				vel[e.target * 2 + 1] *= 0.7;
			}
			n += 1;
		});
		if (n) {
			graph.dirtyNodes = true;
			graph.dirtyEdges = true;
		}
		return n;
	}

	/**
	 * direct 边：渠段(或闸) → 内边界(分水/入流/…)。
	 * return Map stubId → parentId
	 */
	function buildStubParents(graph) {
		var parentOf = Object.create(null);
		if (!graph || typeof graph.activeEdgeIds !== 'function') return parentOf;
		graph.activeEdgeIds().forEach(function (eid) {
			var e = graph.getEdge(eid);
			if (!e) return;
			var tag = String(e.tag || '').toLowerCase();
			var ctype = String((e.properties && e.properties.ConnectionType) || tag || '').toLowerCase();
			if (ctype === 'indirect' || tag === 'indirect') return;
			var src = e.source;
			var tgt = e.target;
			if (src == null || tgt == null) return;
			// Prefer 渠段 as parent when present
			var sNode = graph.getNode(src);
			var tNode = graph.getNode(tgt);
			if (isCanalNode(sNode) && !isCanalNode(tNode) && !nodeIsType4(tNode)) {
				parentOf[tgt] = src;
			} else if (isCanalNode(tNode) && !isCanalNode(sNode) && !nodeIsType4(sNode)) {
				parentOf[src] = tgt;
			} else if (!nodeIsType4(tNode) && !isCanalNode(tNode)) {
				parentOf[tgt] = src;
			}
		});
		return parentOf;
	}

	function resolveStubAttractId(g, graph, stubId, parentId) {
		var attractId = parentId;
		if (!isCanalNode(graph.getNode(attractId))) {
			var related = typeof g.related === 'function' ? g.related(attractId) : [];
			for (var ri = 0; ri < (related || []).length; ri++) {
				if (isCanalNode(related[ri])) {
					attractId = related[ri].id;
					break;
				}
			}
		}
		if (!isCanalNode(graph.getNode(attractId))) {
			var stubRel = typeof g.related === 'function' ? g.related(stubId) : [];
			for (var rj = 0; rj < (stubRel || []).length; rj++) {
				if (isCanalNode(stubRel[rj])) {
					attractId = stubRel[rj].id;
					break;
				}
			}
		}
		return attractId;
	}

	/**
	 * After GPU springs (global rest-length ~55 on every edge, including direct),
	 * snap 内边界 back onto a short ring around their canal/gate. Runs even when
	 * 空间分布 is off — otherwise laterals starburst along direct edges forever.
	 */
	function applyStubAttraction() {
		if (!forceKindOn('stub') || allowFreeForce('stub')) return 0;
		var g = gObj();
		var graph = graphOf(g);
		if (!g || !graph || !g.layout) return 0;
		var vel = g.layout.velocities;
		var parentOf = buildStubParents(graph);
		var rad = Math.max(readStubRadius(), 1.5);
		var maxLen = Math.max(rad * 1.35, 3);
		var n = 0;
		Object.keys(parentOf).forEach(function (stubIdStr) {
			var stubId = Number(stubIdStr);
			var stub = graph.getNode(stubId);
			if (!stub || isCanalNode(stub)) return;
			if (forceTargets && forceTargets[nodeDisplayName(stub)]) return;
			var attractId = resolveStubAttractId(g, graph, stubId, parentOf[stubId]);
			var ax = graph.positions[attractId * 2];
			var ay = graph.positions[attractId * 2 + 1];
			var sx0 = graph.positions[stubId * 2];
			var sy0 = graph.positions[stubId * 2 + 1];
			if (![ax, ay, sx0, sy0].every(isFinite)) return;
			var name = nodeDisplayName(stub) || String(stubId);
			var ang = ((name.length * 37 + stubId * 17) % 360) * Math.PI / 180;
			var tx = ax + Math.cos(ang) * rad;
			var ty = ay + Math.sin(ang) * rad;
			var dx = tx - sx0;
			var dy = ty - sy0;
			var dist = Math.sqrt(dx * dx + dy * dy);
			if (!isFinite(dist) || dist < 1e-6) return;
			writePos(graph, stubId, tx, ty);
			if (vel) {
				vel[stubId * 2] = 0;
				vel[stubId * 2 + 1] = 0;
			}
			n += 1;
		});
		if (n) {
			graph.dirtyNodes = true;
			graph.dirtyEdges = true;
			if (typeof g.markDirty === 'function') g.markDirty();
		}
		return n;
	}

	function pullToward(vel, pinned, g, node, tx, ty, k, softPos) {
		if (!node || !isFinite(tx) || !isFinite(ty)) return false;
		if (pinned && pinned.has(node.id)) {
			if (typeof g.unpinNode === 'function') g.unpinNode(node.id);
			else if (pinned.delete) pinned.delete(node.id);
		}
		var graph = g.getGraph();
		var x = graph.positions[node.id * 2];
		var y = graph.positions[node.id * 2 + 1];
		if (!isFinite(x) || !isFinite(y)) return false;
		var i2 = node.id * 2;
		var dx = tx - x;
		var dy = ty - y;
		vel[i2] += dx * k;
		vel[i2 + 1] += dy * k;
		// Soft position nudge so motion is visible even when damping fights velocity.
		if (softPos && softPos > 0) {
			graph.positions[i2] = x + dx * softPos;
			graph.positions[i2 + 1] = y + dy * softPos;
			graph.dirtyNodes = true;
			graph.dirtyEdges = true;
		}
		return true;
	}

	/**
	 * 吸引虚线对应的力：把 link 起点拉向终点（与 collectAttractLinks 同一套）。
	 * SHP 线：闸 → 缩放后显示的 SHP 点。
	 */
	function applyAttractLinkForces() {
		if (!spatialActive) return 0;
		var g = gObj();
		var graph = graphOf(g);
		if (!g || !graph || !g.layout || !g.layout.velocities) return 0;
		var vel = g.layout.velocities;
		var pinned = g.layout.pinned;
		var gain = readAttractK();
		var links = collectAttractLinks();
		var n = 0;
		links.forEach(function (link) {
			if (link.kind === 'shp') {
				// endpoint is displayed SHP marker; find node at x0,y0 by nearest name via forceTargets
				return;
			}
			if (link.kind === 'canal' && !allowFreeForce('canal')) {
				// canal node at (x0,y0) already handled by placeCanalFollowers
				return;
			}
			if (link.kind === 'stub' && !allowFreeForce('stub')) {
				return;
			}
		});
		// SHP: explicit strong pull (虚线有力)
		if (forceKindOn('shp')) {
			var anchors = shpTargetMap();
			var byName = nameIndex(graph);
			var k = Math.max(0.8, readStrengthFor('type-4') * gain);
			var soft = Math.min(0.6, 0.02 + gain * 0.08);
			Object.keys(anchors).forEach(function (name) {
				var node = byName[name];
				var tgt = anchors[name];
				if (!node || !tgt || isCanalNode(node)) return;
				var sk = strengthKeyForNode(node);
				if (allowFreeForce(sk) || allowFreeForce('other')) return;
				if (pullToward(vel, pinned, g, node, tgt.x, tgt.y, k, soft)) n += 1;
			});
		}
		return n;
	}

	/**
	 * Hierarchy after GPU tick (SHP first; everyone follows):
	 *   1. 闸 → 缩放后显示的 SHP 点（吸引线有力）
	 *   2. 其余随 SHP 平移
	 *   3. 渠段 → 两端中点
	 *   4. 内边界 → 渠段短环
	 */
	function applyHierarchicalAttractors() {
		if (!spatialActive) return 0;
		var g = gObj();
		var graph = graphOf(g);
		if (!g || !graph) return 0;
		disableGlobalSprings();
		softenPhysicsForSpatial();
		var n = applyAttractLinkForces();
		n += placeShpAnchors();
		n += applyFollowShp();
		n += placeCanalFollowers();
		applyPerEdgeSprings();
		n += placeCanalFollowers();
		n += applyStubAttraction();
		if (forceKindOn('shp') && n === 0) {
			var anchors = shpTargetMap();
			if (anchors && Object.keys(anchors).length && !applyHierarchicalAttractors._warned) {
				console.warn('spatial attract: no SHP hits', {
					targets: Object.keys(anchors).slice(0, 8),
					sampleNodeNames: Object.keys(nameIndex(graph)).slice(0, 8)
				});
				applyHierarchicalAttractors._warned = true;
			}
		}
		return n;
	}

	function hookAttractorTick() {
		var g = gObj();
		if (!g || !g.layout || typeof g.layout.tick !== 'function') return;
		var layout = g.layout;
		if (!layout.__ocisAttractorWrapped) {
			var origTick = layout.tick.bind(layout);
			layout.tick = function () {
				disableGlobalSprings();
				syncGpuSpringFromPositions();
				if (spatialActive) placeShpAnchors();
				var ret = origTick();
				disableGlobalSprings();
				if (spatialActive) applyHierarchicalAttractors();
				else {
					applyPerEdgeSprings();
					applyStubAttraction();
				}
				return ret;
			};
			layout.__ocisAttractorWrapped = true;
		}
		// RAF backup: startLayout may replace Sr; keep wrapping + stub clamp.
		if (!window.__ocisSpatialAttractRaf) {
			var loop = function () {
				window.__ocisSpatialAttractRaf = 0;
				var gg = gObj();
				if (gg && gg.layout && !gg.layout.__ocisAttractorWrapped) {
					hookAttractorTick();
				}
				disableGlobalSprings();
				syncGpuSpringFromPositions();
				if (spatialActive) applyHierarchicalAttractors();
				else {
					applyPerEdgeSprings();
					applyStubAttraction();
				}
				if (gg && gg.markDirty) gg.markDirty();
				window.__ocisSpatialAttractRaf = requestAnimationFrame(loop);
			};
			window.__ocisSpatialAttractRaf = requestAnimationFrame(loop);
		}
	}

	function stopSpatialAttract() {
		spatialActive = false;
		restorePhysics();
		unpinAllNodes();
		clearFrozenNodes();
		setSpatialButtonActive(false);
		applyHierarchicalAttractors._warned = false;
		lastShpDelta = { x: 0, y: 0 };
		restoreCameraZoomMin();
		// Keep tick wrap + stub clamp; only GIS hierarchy stops.
	}

	function startSpatialAttract() {
		spatialActive = true;
		applyHierarchicalAttractors._warned = false;
		disableGlobalSprings();
		softenPhysicsForSpatial();
		unpinAllNodes();
		setSpatialButtonActive(true);
		showAttractLayer = true;
		persistFlags();
		startPaintLoop();
		hookAttractorTick();
		applyHierarchicalAttractors();
		setTimeout(fitGraphView, 80);
		setTimeout(fitGraphView, 280);
	}

	function ensureOverlay() {
		var host = document.querySelector('.canvas-container') ||
			(document.getElementById('graph-canvas') && document.getElementById('graph-canvas').parentElement);
		if (!host) return null;
		overlay = document.getElementById(OVERLAY_ID);
		if (!overlay) {
			overlay = document.createElement('canvas');
			overlay.id = OVERLAY_ID;
			overlay.addEventListener('pointerdown', onOverlayPointerDown);
			overlay.addEventListener('pointermove', onOverlayPointerMove);
			overlay.addEventListener('pointerup', onOverlayPointerUp);
			overlay.addEventListener('pointercancel', onOverlayPointerUp);
		}
		// Keep above topo-live-overlay (z=6) and graph canvas.
		overlay.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;z-index:12;display:' +
			(overlayWanted() ? 'block' : 'none');
		overlay.style.pointerEvents = showScaleCenter ? 'auto' : 'none';
		if (overlay.parentElement !== host) host.appendChild(overlay);
		else if (host.lastElementChild !== overlay) host.appendChild(overlay); // restack on top
		octx = overlay.getContext('2d');
		return overlay;
	}

	function resizeOverlay() {
		if (!ensureOverlay()) return;
		var dpr = viewDpr();
		var w = overlay.clientWidth || overlay.parentElement.clientWidth || 800;
		var h = overlay.clientHeight || overlay.parentElement.clientHeight || 600;
		overlay.width = Math.max(1, Math.floor(w * dpr));
		overlay.height = Math.max(1, Math.floor(h * dpr));
		octx.setTransform(dpr, 0, 0, dpr, 0, 0);
	}

	function worldToCss(wx, wy) {
		var g = gObj();
		if (!g || !g.camera || typeof g.camera.worldToScreen !== 'function') return null;
		var s = g.camera.worldToScreen(wx, wy);
		var dpr = viewDpr();
		var sx = s && s.length >= 2 ? s[0] : s && s.x;
		var sy = s && s.length >= 2 ? s[1] : s && s.y;
		return [Number(sx) / dpr, Number(sy) / dpr];
	}

	function cssToWorld(cssX, cssY) {
		var g = gObj();
		var canvas = document.getElementById('graph-canvas');
		if (!g || !g.camera || !canvas || typeof g.camera.screenToWorld !== 'function') return null;
		var dpr = viewDpr();
		var rect = canvas.getBoundingClientRect();
		var overlayRect = overlay.getBoundingClientRect();
		var clientX = overlayRect.left + cssX;
		var clientY = overlayRect.top + cssY;
		var sx = (clientX - rect.left) * dpr;
		var sy = (clientY - rect.top) * dpr;
		var w = g.camera.screenToWorld(sx, sy);
		if (!w || w.length < 2) return null;
		return { x: w[0], y: w[1] };
	}

	function paintOverlay() {
		if (!overlayWanted()) {
			if (overlay) overlay.style.display = 'none';
			return;
		}
		if (!ensureOverlay()) return;
		resizeOverlay();
		var cssW = overlay.clientWidth || 1;
		var cssH = overlay.clientHeight || 1;
		octx.clearRect(0, 0, cssW, cssH);

		if (showShpLayer) {
			var drawn = 0;
			mappedShp.forEach(function (p) {
				var scr = worldToCss(p.x, p.y);
				if (!scr || !isFinite(scr[0]) || !isFinite(scr[1])) return;
				var x = scr[0], y = scr[1];
				if (x < -40 || y < -40 || x > cssW + 40 || y > cssH + 40) return;
				drawn += 1;
				octx.beginPath();
				octx.arc(x, y, 6, 0, Math.PI * 2);
				octx.fillStyle = 'rgba(245, 158, 11, 0.9)';
				octx.fill();
				octx.strokeStyle = 'rgba(120, 53, 15, 0.95)';
				octx.lineWidth = 1.5;
				octx.stroke();
				octx.beginPath();
				octx.moveTo(x - 9, y);
				octx.lineTo(x + 9, y);
				octx.moveTo(x, y - 9);
				octx.lineTo(x, y + 9);
				octx.strokeStyle = 'rgba(253, 224, 71, 0.95)';
				octx.lineWidth = 1.25;
				octx.stroke();
				if (p.name) {
					octx.fillStyle = 'rgba(254, 243, 199, 0.95)';
					octx.strokeStyle = 'rgba(0,0,0,0.35)';
					octx.lineWidth = 3;
					octx.font = '11px "Microsoft YaHei", sans-serif';
					octx.strokeText(p.name, x + 10, y - 8);
					octx.fillText(p.name, x + 10, y - 8);
				}
			});
			// HUD so user always knows the layer is on
			octx.fillStyle = 'rgba(15, 23, 42, 0.72)';
			octx.fillRect(8, 8, 168, 28);
			octx.fillStyle = '#fbbf24';
			octx.font = '12px "Microsoft YaHei", sans-serif';
			octx.fillText(
				mappedShp.length
					? ('SHP 图层 · ' + drawn + '/' + mappedShp.length)
					: 'SHP 加载中…',
				16,
				26
			);
		}

		if (showScaleCenter && scaleCenter) {
			var sc = worldToCss(scaleCenter.x, scaleCenter.y);
			if (sc) {
				var cx = sc[0], cy = sc[1];
				octx.save();
				octx.strokeStyle = 'rgba(59, 130, 246, 0.95)';
				octx.fillStyle = 'rgba(59, 130, 246, 0.35)';
				octx.lineWidth = 2;
				octx.beginPath();
				octx.arc(cx, cy, 10, 0, Math.PI * 2);
				octx.fill();
				octx.stroke();
				octx.beginPath();
				octx.moveTo(cx - 18, cy);
				octx.lineTo(cx + 18, cy);
				octx.moveTo(cx, cy - 18);
				octx.lineTo(cx, cy + 18);
				octx.stroke();
				octx.fillStyle = 'rgba(59, 130, 246, 0.95)';
				octx.font = '12px sans-serif';
				octx.fillText('缩放中心', cx + 14, cy - 10);
				octx.restore();
			}
		}

		if (showAttractLayer) {
			var links = collectAttractLinks();
			var drawnA = 0;
			var counts = { shp: 0, canal: 0, stub: 0 };
			octx.save();
			links.forEach(function (link) {
				var a0 = worldToCss(link.x0, link.y0);
				var a1 = worldToCss(link.x1, link.y1);
				if (!a0 || !a1) return;
				if (!isFinite(a0[0]) || !isFinite(a0[1]) || !isFinite(a1[0]) || !isFinite(a1[1])) return;
				var off =
					(a0[0] < -40 && a1[0] < -40) ||
					(a0[1] < -40 && a1[1] < -40) ||
					(a0[0] > cssW + 40 && a1[0] > cssW + 40) ||
					(a0[1] > cssH + 40 && a1[1] > cssH + 40);
				if (off) return;
				drawnA += 1;
				if (counts[link.kind] != null) counts[link.kind] += 1;
				octx.beginPath();
				octx.moveTo(a0[0], a0[1]);
				octx.lineTo(a1[0], a1[1]);
				octx.strokeStyle = FORCE_KIND_COLOR[link.kind] || 'rgba(255,255,255,0.7)';
				octx.lineWidth = link.kind === 'stub' ? 1.1 : 1.6;
				octx.setLineDash(link.kind === 'canal' ? [8, 5] : link.kind === 'shp' ? [5, 4] : [3, 4]);
				octx.stroke();
			});
			octx.setLineDash([]);
			octx.restore();
			var hudY = showShpLayer ? 40 : 8;
			octx.fillStyle = 'rgba(15, 23, 42, 0.72)';
			octx.fillRect(8, hudY, 220, 28);
			octx.fillStyle = '#a5b4fc';
			octx.font = '12px "Microsoft YaHei", sans-serif';
			octx.fillText(
				'吸引 · ' + drawnA + '  SHP ' + counts.shp + '  渠 ' + counts.canal + '  内 ' + counts.stub,
				16,
				hudY + 18
			);
		}

		var frameBox = layoutBBox || initialBBox;
		if (frameBox && (showShpLayer || showScaleCenter)) {
			var a = worldToCss(frameBox.minX, frameBox.minY);
			var b = worldToCss(frameBox.maxX, frameBox.maxY);
			if (a && b) {
				octx.strokeStyle = 'rgba(148, 163, 184, 0.55)';
				octx.setLineDash([6, 4]);
				octx.lineWidth = 1;
				octx.strokeRect(
					Math.min(a[0], b[0]),
					Math.min(a[1], b[1]),
					Math.abs(b[0] - a[0]),
					Math.abs(b[1] - a[1])
				);
				octx.setLineDash([]);
			}
		}
	}

	function loopPaint() {
		paintOverlay();
		raf = requestAnimationFrame(loopPaint);
	}

	function startPaintLoop() {
		if (raf) return;
		ensureOverlay();
		raf = requestAnimationFrame(loopPaint);
	}

	function onOverlayPointerDown(ev) {
		if (!showScaleCenter || !scaleCenter) return;
		var rect = overlay.getBoundingClientRect();
		var cssX = ev.clientX - rect.left;
		var cssY = ev.clientY - rect.top;
		var sc = worldToCss(scaleCenter.x, scaleCenter.y);
		if (!sc) return;
		var dx = cssX - sc[0], dy = cssY - sc[1];
		if (dx * dx + dy * dy > 20 * 20) return;
		dragCenter = { ox: cssX, oy: cssY };
		overlay.setPointerCapture(ev.pointerId);
		ev.preventDefault();
		ev.stopPropagation();
	}

	function onOverlayPointerMove(ev) {
		if (!dragCenter || !scaleCenter) return;
		var rect = overlay.getBoundingClientRect();
		var cssX = ev.clientX - rect.left;
		var cssY = ev.clientY - rect.top;
		var w = cssToWorld(cssX, cssY);
		if (!w) return;
		scaleCenter = { x: w.x, y: w.y };
		rebuildMapped();
		ev.preventDefault();
	}

	function onOverlayPointerUp(ev) {
		if (!dragCenter) return;
		dragCenter = null;
		try { overlay.releasePointerCapture(ev.pointerId); } catch (e) { /* ignore */ }
	}

	async function runSpatial() {
		if (busy) return;
		// Toggle off if already attracting
		if (spatialActive) {
			stopSpatialAttract();
			return;
		}
		var name = caseName();
		if (!name) {
			alert('请先选择案例');
			return;
		}
		if (!gObj() || !graphOf(gObj())) {
			alert('拓扑图尚未加载完成');
			return;
		}
		setBusy(true, '布局中…');
		try {
			// Freeze initial topo bbox once (第一次有效包围盒).
			if (!captureInitialBBox(false)) {
				throw new Error('当前拓扑图区域无效');
			}
			if (!scaleCenter) {
				scaleCenter = { x: initialBBox.cx, y: initialBBox.cy };
			}

			var typed = stampType4FromEdges();

			var resp = await fetch(
				'/api/graph-spatial-layout?case=' + encodeURIComponent(name) + '&_=' + Date.now(),
				{ cache: 'no-store' }
			);
			var data = await resp.json();
			if (!resp.ok || !data || data.error) {
				throw new Error((data && data.error) || ('HTTP ' + resp.status));
			}
			var raw = data.targets || data.positions;
			if (!raw || typeof raw !== 'object' || !Object.keys(raw).length) {
				throw new Error('未返回节制闸目标坐标');
			}

			rawGateGis = {};
			Object.keys(raw).forEach(function (nm) {
				var p = raw[nm];
				if (!p) return;
				var x = Number(p.x), y = Number(p.y);
				if (!isFinite(x) || !isFinite(y)) return;
				rawGateGis[nm] = {
					x: x,
					y: y,
					shpName: String(p.shpName || nm).trim()
				};
			});

			rawShpAll = [];
			var layer = data.shpLayer || data.shpPoints || [];
			if (Array.isArray(layer) && layer.length) {
				layer.forEach(function (p) {
					if (!p) return;
					var x = Number(p.x), y = Number(p.y);
					if (!isFinite(x) || !isFinite(y)) return;
					rawShpAll.push({ name: String(p.name || ''), x: x, y: y });
				});
			} else {
				Object.keys(rawGateGis).forEach(function (nm) {
					rawShpAll.push({ name: nm, x: rawGateGis[nm].x, y: rawGateGis[nm].y });
				});
			}

			var scale = writeScale(readScale(), true);
			rebuildMapped();

			if (!forceTargets || !Object.keys(forceTargets).length) {
				throw new Error('映射后无节制闸目标（请检查初始包围盒）');
			}

			if (typeof window.__ocisStartForceLayout === 'function') {
				window.__ocisStartForceLayout();
			}
			startSpatialAttract();
			// Ensure hook on the *current* layout instance after startLayout.
			setTimeout(function () {
				if (!spatialActive) return;
				softenPhysicsForSpatial();
				hookAttractorTick();
				applyHierarchicalAttractors();
			}, 0);
			setTimeout(function () {
				if (!spatialActive) return;
				hookAttractorTick();
				applyHierarchicalAttractors();
			}, 100);

			showShpLayer = true;
			persistFlags();
			startPaintLoop();
			rebuildMapped();
			syncToggleUi();

			var tip =
				'层级吸引中：SHP→节制→渠段→内边界 · 闸 ' + Object.keys(forceTargets || {}).length +
				' · type4=' + typed +
				' · 缩放 ' + scale.toFixed(2) + '×';
			console.log(tip, {
				bbox: initialBBox,
				center: scaleCenter,
				sampleTarget: forceTargets && forceTargets[Object.keys(forceTargets)[0]],
				data: data
			});
			var btn = document.getElementById('ocisSpatialLayout');
			if (btn) btn.title = tip + '（再点一次停止吸引）';
		} catch (err) {
			console.warn('spatial layout failed', err);
			stopSpatialAttract();
			alert('空间分布布局失败：' + (err && err.message ? err.message : String(err)));
		} finally {
			setBusy(false);
			if (spatialActive) setSpatialButtonActive(true);
		}
	}

	function onScaleUserChange() {
		writeScale(readScale(), true);
		rebuildMapped();
		applyHierarchicalAttractors();
		fitGraphView();
	}

	function onStrengthUserChange() {
		readSelectedStrengthType();
		writeStrengthFor(selectedStrengthType, readStrength(), true);
		applyHierarchicalAttractors();
	}

	function onStubRadiusUserChange() {
		writeStubRadius(readStubRadius(), true);
		applyHierarchicalAttractors();
	}

	function onStubSnapUserChange() {
		writeStubSnap(readStubSnap(), true);
		applyHierarchicalAttractors();
	}

	function onStubPullUserChange() {
		writeStubPull(readStubPull(), true);
		applyHierarchicalAttractors();
	}

	function onSpatialRepulseUserChange() {
		writeSpatialRepulse(readSpatialRepulse(), true);
		softenPhysicsForSpatial();
		applyHierarchicalAttractors();
	}

	function onParamUserChange(name) {
		if (name === 'strength') onStrengthUserChange();
		else if (name === 'stubRadius') onStubRadiusUserChange();
		else if (name === 'stubSnap') onStubSnapUserChange();
		else if (name === 'stubPull') onStubPullUserChange();
		else if (name === 'spatialRepulse') onSpatialRepulseUserChange();
	}

	function onParamMaxUserChange(name) {
		var p = SPATIAL_PARAMS[name];
		if (!p) return;
		var el = document.getElementById(p.maxId);
		var v = el ? Number(el.value) : readParamMax(name);
		writeParamMax(name, v, true);
		onParamUserChange(name);
	}

	function wireUi() {
		try {
			var saved = Number(localStorage.getItem(SCALE_KEY));
			writeScale(isFinite(saved) && saved > 0 ? saved : 1, false);
		} catch (eInit) {
			writeScale(1, false);
		}
		loadStrengthByType();
		syncSpatialForceUi();
		loadFreeForceTypes();
		loadForceKinds();
		try {
			var savedK = Number(localStorage.getItem(ATTRACT_K_KEY));
			writeAttractK(isFinite(savedK) && savedK > 0 ? savedK : 1, false);
		} catch (eK) {
			writeAttractK(1, false);
		}
		syncToggleUi();

		document.addEventListener('click', function (ev) {
			var t = ev.target;
			if (!t || !t.closest) return;
			if (t.closest('#ocisSpatialLayout')) {
				ev.preventDefault();
				ev.stopPropagation();
				runSpatial();
				return;
			}
			if (t.closest('#ocisShpLayerBtn') || t.closest('#ocisToggleShpLayer')) {
				ev.preventDefault();
				ev.stopPropagation();
				setShpVisible(!showShpLayer);
				return;
			}
			if (t.closest('#ocisAttractLayerBtn') || t.closest('#ocisToggleAttractLayer')) {
				ev.preventDefault();
				ev.stopPropagation();
				setAttractVisible(!showAttractLayer);
				return;
			}
			if (t.closest('#ocisToggleScaleCenter')) {
				ev.preventDefault();
				showScaleCenter = !showScaleCenter;
				persistFlags();
				if (showScaleCenter) startPaintLoop();
				return;
			}
			if (t.closest('#ocisResetScaleCenter')) {
				ev.preventDefault();
				resetScaleCenter();
				return;
			}
			var freeWrap = document.getElementById('ocisFreeForceWrap');
			if (freeWrap && freeWrap.open && !t.closest('#ocisFreeForceWrap')) {
				freeWrap.open = false;
			}
			var kindWrap = document.getElementById('ocisForceKindWrap');
			if (kindWrap && kindWrap.open && !t.closest('#ocisForceKindWrap')) {
				kindWrap.open = false;
			}
			if (t.closest('.toolbar .btn') && /settings/i.test(t.closest('.toolbar .btn').textContent || '')) {
				setTimeout(function () {
					syncToggleUi();
					syncSpatialForceUi();
				}, 50);
			}
		});

		document.addEventListener('change', function (ev) {
			var inp = ev.target;
			if (!inp || !inp.getAttribute) return;
			if (inp.id === 'ocisSpatialScale') {
				onScaleUserChange();
				return;
			}
			if (inp.id === 'ocisAttractK') {
				writeAttractK(Number(inp.value), true);
				applyHierarchicalAttractors();
				return;
			}
			if (inp.id === 'ocisStrengthType') {
				writeSelectedStrengthType(inp.value, true);
				applyHierarchicalAttractors();
				return;
			}
			var maxName = inp.getAttribute('data-spatial-max');
			if (maxName && SPATIAL_PARAMS[maxName]) {
				onParamMaxUserChange(maxName);
				return;
			}
			var paramName = inp.getAttribute('data-spatial-param');
			if (paramName && SPATIAL_PARAMS[paramName]) {
				onParamUserChange(paramName);
				return;
			}
			var forceKind = inp.getAttribute('data-force-kind');
			if (forceKind && inp.closest('#ocisForceKindMenu')) {
				if (inp.checked) forceKinds.add(forceKind);
				else forceKinds.delete(forceKind);
				persistForceKinds();
				if (showAttractLayer) startPaintLoop();
				hookAttractorTick();
				applyStubAttraction();
				if (spatialActive) applyHierarchicalAttractors();
				return;
			}
			var key = inp.getAttribute('data-free');
			if (!key || !inp.closest('#ocisFreeForceMenu')) return;
			if (inp.checked) freeForceTypes.add(key);
			else freeForceTypes.delete(key);
			persistFreeForceTypes();
			if (spatialActive) {
				unpinAllNodes();
				softenPhysicsForSpatial();
				applyHierarchicalAttractors();
				// Ensure layout loop is running so free nodes can actually move.
				var gg = gObj();
				if (gg && gg.layout) {
					gg.layout.animated = true;
					if (!gg.layout.running && typeof gg.layout.start === 'function') gg.layout.start();
				}
			}
		});

		document.addEventListener('input', function (ev) {
			if (!ev.target || !ev.target.getAttribute) return;
			if (ev.target.id === 'ocisSpatialScale') {
				onScaleUserChange();
				return;
			}
			if (ev.target.id === 'ocisAttractK') {
				writeAttractK(Number(ev.target.value), true);
				applyHierarchicalAttractors();
				return;
			}
			var maxName = ev.target.getAttribute('data-spatial-max');
			if (maxName && SPATIAL_PARAMS[maxName]) {
				onParamMaxUserChange(maxName);
				return;
			}
			var paramName = ev.target.getAttribute('data-spatial-param');
			if (paramName && SPATIAL_PARAMS[paramName]) onParamUserChange(paramName);
		});
		document.addEventListener('wheel', function (ev) {
			var kWrap = ev.target && ev.target.closest && ev.target.closest('#ocisAttractKWrap');
			if (kWrap) {
				ev.preventDefault();
				ev.stopPropagation();
				var kStep = ev.shiftKey ? 0.2 : 0.05;
				writeAttractK(readAttractK() + (ev.deltaY < 0 ? kStep : -kStep), true);
				applyHierarchicalAttractors();
				return;
			}
			var wrap = ev.target && ev.target.closest && ev.target.closest('#ocisSpatialScaleWrap');
			if (!wrap) return;
			ev.preventDefault();
			ev.stopPropagation();
			var cur = readScale();
			var step = ev.shiftKey ? 0.2 : 0.05;
			writeScale(cur + (ev.deltaY < 0 ? step : -step), true);
			rebuildMapped();
			applyHierarchicalAttractors();
		}, { passive: false });

		var tries = 0;
		var timer = setInterval(function () {
			tries += 1;
			captureInitialBBox(false);
			hookAttractorTick();
			applyStubAttraction();
			if (tries > 80) clearInterval(timer);
		}, 250);

		var kindWrapEl = document.getElementById('ocisForceKindWrap');
		if (kindWrapEl) {
			kindWrapEl.addEventListener('toggle', function () {
				if (kindWrapEl.open) syncForceKindUi();
			});
		}
		[0, 200, 800].forEach(function (ms) {
			setTimeout(function () {
				syncForceKindUi();
				syncToggleUi();
				hookAttractorTick();
				applyStubAttraction();
			}, ms);
		});
	}

	wireUi();
	if (overlayWanted()) {
		startPaintLoop();
		if (showShpLayer || (showAttractLayer && forceKindOn('shp'))) ensureShpData();
	}

	window.__ocisSpatial = {
		run: runSpatial,
		rebuild: rebuildMapped,
		rehook: function () {
			hookAttractorTick();
			disableGlobalSprings();
			syncGpuSpringFromPositions();
			if (spatialActive) {
				softenPhysicsForSpatial();
				applyHierarchicalAttractors();
			}
			applyPerEdgeSprings();
			applyStubAttraction();
		},
		springLengthFromPositions: springLengthFromPositions,
		syncGpuSpringFromPositions: syncGpuSpringFromPositions,
		stop: stopSpatialAttract,
		isActive: function () { return spatialActive; },
		resetScaleCenter: resetScaleCenter,
		captureInitialBBox: captureInitialBBox,
		getInitialBBox: function () { return initialBBox; },
		getScaleCenter: function () { return scaleCenter; },
		setShowShpLayer: function (on) {
			setShpVisible(!!on);
		},
		setShowAttractLayer: function (on) {
			setAttractVisible(!!on);
		},
		ensureShpData: ensureShpData,
		setShowScaleCenter: function (on) {
			showScaleCenter = !!on;
			persistFlags();
			if (showScaleCenter) startPaintLoop();
		}
	};
})();
