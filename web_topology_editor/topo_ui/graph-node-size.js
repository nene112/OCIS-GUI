/**
 * Per-tag node size (writes graph.sizes[id]; global Settings "Node size" stays nodeScale).
 * Also scales force-layout springLength / repulsion with mean node size so denser visuals pack closer.
 * Tags match legend: type-0…6, boundary, 渠段.
 */
(function graphNodeSizeByTag() {
	var STORAGE_KEY = 'ocisTopoNodeSizesByTag';
	var DEFAULT_SIZE = 8;
	var MIN = 2;
	var MAX = 20;
	var STEP = 0.5;

	/** Fallback only when positions are not ready; live rest length comes from node positions. */
	var BASE_SPRING = 24;
	var BASE_GRAV = -0.25;
	/** Spatial soften baselines at size=8 (see graph-spatial-layer softenPhysicsForSpatial). */
	var SPATIAL_SPRING = 14;
	var SPATIAL_GRAV = -0.015;

	var TAGS = [
		{ tag: 'type-0', label: 'type-0 水源' },
		{ tag: 'type-1', label: 'type-1' },
		{ tag: 'type-2', label: 'type-2' },
		{ tag: 'type-3', label: 'type-3' },
		{ tag: 'type-4', label: 'type-4 节制' },
		{ tag: 'type-5', label: 'type-5' },
		{ tag: 'type-6', label: 'type-6' },
		{ tag: 'boundary', label: 'boundary' },
		{ tag: '渠段', label: '渠段' }
	];

	/** @type {Record<string,number>} */
	var sizeByTag = Object.create(null);

	function defaultMap() {
		var m = Object.create(null);
		TAGS.forEach(function (t) { m[t.tag] = DEFAULT_SIZE; });
		return m;
	}

	function clamp(v) {
		v = Number(v);
		if (!isFinite(v)) return DEFAULT_SIZE;
		v = Math.round(v / STEP) * STEP;
		return Math.max(MIN, Math.min(MAX, v));
	}

	function load() {
		sizeByTag = defaultMap();
		try {
			var raw = localStorage.getItem(STORAGE_KEY);
			if (!raw) return;
			var obj = JSON.parse(raw);
			if (!obj || typeof obj !== 'object') return;
			TAGS.forEach(function (t) {
				if (obj[t.tag] != null) sizeByTag[t.tag] = clamp(obj[t.tag]);
			});
		} catch (e) { /* ignore */ }
	}

	function persist() {
		try {
			localStorage.setItem(STORAGE_KEY, JSON.stringify(sizeByTag));
		} catch (e) { /* ignore */ }
	}

	function gObj() {
		return window.g || null;
	}

	function graphOf(g) {
		return g && typeof g.getGraph === 'function' ? g.getGraph() : null;
	}

	function sizeForTag(tag) {
		if (tag && sizeByTag[tag] != null) return sizeByTag[tag];
		return DEFAULT_SIZE;
	}

	function meanActiveSize(graph) {
		if (!graph || typeof graph.activeNodeIds !== 'function') return DEFAULT_SIZE;
		var sum = 0;
		var n = 0;
		graph.activeNodeIds().forEach(function (id) {
			var node = graph.getNode(id);
			if (!node) return;
			sum += sizeForTag(node.tag);
			n += 1;
		});
		return n ? sum / n : DEFAULT_SIZE;
	}

	/** Relative to DEFAULT_SIZE=8; clamps so layout stays stable. */
	function sizeScaleFactor(graph) {
		var mean = meanActiveSize(graph || graphOf(gObj()));
		var f = mean / DEFAULT_SIZE;
		if (!isFinite(f) || f <= 0) return 1;
		return Math.max(0.25, Math.min(2.5, f));
	}

	function spatialActive() {
		return !!(window.__ocisSpatial && typeof window.__ocisSpatial.isActive === 'function' && window.__ocisSpatial.isActive());
	}

	/**
	 * Shrink/grow force rest-length & repulsion with node sizes.
	 * When spatial mode is on, scale its softened baselines instead.
	 */
	function syncForceSpacing() {
		var g = gObj();
		if (!g || !g.layout || !g.layout.config) return;
		var factor = sizeScaleFactor();
		var c = g.layout.config;
		if (spatialActive()) {
			c.springConstant = 0;
			return;
		} else {
			var baseGrav = Number(window.__ocisBaseGrav);
			if (!isFinite(baseGrav)) baseGrav = BASE_GRAV;
			c.gravitationalConstant = baseGrav * factor;
			c.springConstant = 0;
			var posL = 0;
			if (window.__ocisSpatial && typeof window.__ocisSpatial.springLengthFromPositions === 'function') {
				posL = Number(window.__ocisSpatial.springLengthFromPositions());
			}
			if (isFinite(posL) && posL > 0) {
				c.springLength = posL;
			} else {
				var baseSpring = Number(window.__ocisBaseSpringLength);
				if (!isFinite(baseSpring) || baseSpring <= 0) baseSpring = BASE_SPRING;
				c.springLength = baseSpring * factor;
			}
		}
	}

	function applyAll() {
		var g = gObj();
		var graph = graphOf(g);
		if (!graph || typeof graph.activeNodeIds !== 'function') return 0;
		var n = 0;
		graph.activeNodeIds().forEach(function (id) {
			var node = graph.getNode(id);
			if (!node) return;
			var sz = sizeForTag(node.tag);
			if (typeof graph.setNodeSize === 'function') graph.setNodeSize(id, sz);
			else {
				graph.sizes[id] = sz;
				graph.dirtyNodes = true;
			}
			n += 1;
		});
		syncForceSpacing();
		return n;
	}

	function syncSliderUi() {
		TAGS.forEach(function (t) {
			var inp = document.querySelector('input[data-node-size-tag="' + t.tag + '"]');
			var val = sizeByTag[t.tag];
			if (inp) inp.value = String(val);
			var lab = document.querySelector('[data-node-size-val="' + t.tag + '"]');
			if (lab) lab.textContent = String(val);
		});
	}

	function setTagSize(tag, value, doPersist) {
		if (!tag || (!(tag in sizeByTag) && !TAGS.some(function (t) { return t.tag === tag; }))) return;
		sizeByTag[tag] = clamp(value);
		if (doPersist !== false) persist();
		syncSliderUi();
		applyAll();
	}

	function resetAll() {
		sizeByTag = defaultMap();
		persist();
		syncSliderUi();
		applyAll();
	}

	function onSettingsLikelyOpen() {
		setTimeout(function () {
			syncSliderUi();
		}, 50);
	}

	function wireUi() {
		document.addEventListener('input', function (ev) {
			var el = ev.target;
			if (!el || !el.getAttribute) return;
			var tag = el.getAttribute('data-node-size-tag');
			if (!tag) return;
			setTagSize(tag, el.value, true);
		});
		document.addEventListener('change', function (ev) {
			var el = ev.target;
			if (!el || !el.getAttribute) return;
			var tag = el.getAttribute('data-node-size-tag');
			if (!tag) return;
			setTagSize(tag, el.value, true);
		});
		document.addEventListener('click', function (ev) {
			var t = ev.target;
			if (!t || !t.closest) return;
			if (t.closest('#ocisResetNodeSizes')) {
				ev.preventDefault();
				resetAll();
				return;
			}
			if (t.closest('.toolbar .btn') && /settings/i.test(t.closest('.toolbar .btn').textContent || '')) {
				onSettingsLikelyOpen();
			}
		});
	}

	load();
	wireUi();

	var tries = 0;
	var lastNodeCount = -1;
	var timer = setInterval(function () {
		tries += 1;
		var graph = graphOf(gObj());
		if (!graph) {
			if (tries > 120) clearInterval(timer);
			return;
		}
		var count = typeof graph.numNodes === 'number' ? graph.numNodes : -1;
		if (count !== lastNodeCount) {
			lastNodeCount = count;
			applyAll();
			syncSliderUi();
		}
	}, 500);

	window.__ocisNodeSizeByTag = {
		apply: applyAll,
		reset: resetAll,
		syncSpacing: syncForceSpacing,
		sizeScaleFactor: sizeScaleFactor,
		getMap: function () { return Object.assign({}, sizeByTag); },
		setTagSize: setTagSize,
		tags: TAGS.slice()
	};
})();
