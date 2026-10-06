/**
 * Topo live styles + host APIs (overlay on GraphGPU).
 *
 * - Indirect edges: thicker stroke
 * - setGateUpstreamDepths: depth > max_h → bold red; depth < max_h*0.2 → bold yellow (渠段)
 * - setDiversionIrrigation: diversion nodes → pie chart of task completion
 *
 * window.TopoLive / postMessage { type:'topoLive', action, payload }
 */
(function graphLiveApi() {
	var OVERLAY_ID = 'topo-live-overlay';
	var INDIRECT_WIDTH = 4.2;
	var DIRECT_WIDTH = 1.4;
	var OVERFLOW_WIDTH = 5.5;
	var LOW_WIDTH = 5.0;
	var OVERFLOW_COLOR = 'rgba(220, 38, 38, 0.92)';
	var LOW_COLOR = 'rgba(234, 179, 8, 0.95)';
	var INDIRECT_COLOR_LIGHT = 'rgba(56, 189, 248, 0.55)';
	var INDIRECT_COLOR_DARK = 'rgba(56, 189, 248, 0.7)';
	var PIE_DONE = '#22c55e';
	var PIE_REST = '#cbd5e1';

	var state = {
		depths: Object.create(null), // name -> depth (m)
		irrigation: Object.create(null), // name -> { volume, target, ratio }
		overflowEdgeIds: Object.create(null),
		lowEdgeIds: Object.create(null),
		ready: false
	};

	var overlay = null;
	var ctx = null;
	var raf = 0;

	function normName(v) {
		if (v == null) return '';
		var s = String(v).trim();
		if (!s || s.toLowerCase() === 'nan' || s === '-1') return '';
		return s;
	}

	function gObj() {
		return window.g || null;
	}

	function graphOf(g) {
		return g && typeof g.getGraph === 'function' ? g.getGraph() : null;
	}

	function isDark() {
		return document.body.classList.contains('dark');
	}

	function viewDpr() {
		var g = gObj();
		if (g && g.renderer && g.renderer.pixelRatio > 0) return Number(g.renderer.pixelRatio);
		return window.devicePixelRatio || 1;
	}

	function ensureOverlay() {
		var host = document.querySelector('.canvas-container') || document.getElementById('graph-canvas') && document.getElementById('graph-canvas').parentElement;
		if (!host) return null;
		overlay = document.getElementById(OVERLAY_ID);
		if (!overlay) {
			overlay = document.createElement('canvas');
			overlay.id = OVERLAY_ID;
			overlay.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:6;';
			var cs = window.getComputedStyle(host);
			if (cs.position === 'static') host.style.position = 'relative';
			host.appendChild(overlay);
		}
		ctx = overlay.getContext('2d');
		return overlay;
	}

	function resizeOverlay() {
		if (!ensureOverlay()) return;
		var dpr = viewDpr();
		var w = overlay.clientWidth || overlay.parentElement.clientWidth || 800;
		var h = overlay.clientHeight || overlay.parentElement.clientHeight || 600;
		overlay.width = Math.max(1, Math.floor(w * dpr));
		overlay.height = Math.max(1, Math.floor(h * dpr));
		ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
	}

	function worldToCss(g, wx, wy) {
		var s = g.camera.worldToScreen(wx, wy);
		var dpr = viewDpr();
		var sx = s && s.length >= 2 ? s[0] : (s && s.x);
		var sy = s && s.length >= 2 ? s[1] : (s && s.y);
		return [Number(sx) / dpr, Number(sy) / dpr];
	}

	function nodeLabel(node) {
		if (!node) return '';
		var p = node.properties || {};
		return normName(p.name || p.title || '');
	}

	function collectActiveEdges(graph) {
		var out = [];
		if (!graph || typeof graph.activeEdgeIds !== 'function') return out;
		graph.activeEdgeIds().forEach(function (id) {
			var e = graph.getEdge(id);
			if (e) out.push(e);
		});
		return out;
	}

	function recomputeDepthAlerts(graph) {
		state.overflowEdgeIds = Object.create(null);
		state.lowEdgeIds = Object.create(null);
		var edges = collectActiveEdges(graph);
		var byGate = Object.create(null);
		edges.forEach(function (e) {
			// Only mainstem pool edges (indirect → 渠段). Direct laterals
			// (leakage/损失, 分水, 泄水, …) are 内边界 stubs — never alert-colored.
			if (String(e.tag || '').toLowerCase() !== 'indirect') return;
			var p = e.properties || {};
			var tgt = normName(p.target);
			if (!tgt) return;
			if (!byGate[tgt]) byGate[tgt] = [];
			byGate[tgt].push(e);
		});
		Object.keys(state.depths).forEach(function (gateName) {
			var h = Number(state.depths[gateName]);
			if (!isFinite(h)) return;
			var list = byGate[gateName] || [];
			list.forEach(function (e) {
				var p = e.properties || {};
				var rawMax = p.max_h;
				var maxH = (rawMax === '' || rawMax == null) ? NaN : Number(rawMax);
				if (!isFinite(maxH) || maxH <= 0) return;
				if (h > maxH) {
					state.overflowEdgeIds[e.id] = true;
					return;
				}
				if (h < maxH * 0.2) {
					state.lowEdgeIds[e.id] = true;
				}
			});
		});
	}

	function applyGpuEdgeColors(g, graph) {
		// Soft tint: overflow red / low yellow in GraphGPU buffer; others keep tag color.
		if (!graph || !graph.edgeColors) return;
		var tagColors = graph.tagColors;
		graph.activeEdgeIds().forEach(function (id) {
			var e = graph.getEdge(id);
			if (!e) return;
			if (state.overflowEdgeIds[id]) {
				graph.edgeColors[id * 3] = 0.86;
				graph.edgeColors[id * 3 + 1] = 0.15;
				graph.edgeColors[id * 3 + 2] = 0.15;
			} else if (state.lowEdgeIds[id]) {
				graph.edgeColors[id * 3] = 0.92;
				graph.edgeColors[id * 3 + 1] = 0.70;
				graph.edgeColors[id * 3 + 2] = 0.03;
			} else if (e.tag && tagColors && typeof tagColors.getColor === 'function') {
				var c = tagColors.getColor(e.tag);
				if (c && c.bg) {
					graph.edgeColors[id * 3] = c.bg[0];
					graph.edgeColors[id * 3 + 1] = c.bg[1];
					graph.edgeColors[id * 3 + 2] = c.bg[2];
				}
			}
		});
		graph.dirtyEdges = true;
		if (typeof g.markDirty === 'function') g.markDirty();
	}

	function labelFontScale() {
		var g = gObj();
		var s = g && g.renderer && g.renderer.labelFontScale;
		s = Number(s);
		return isFinite(s) && s > 0 ? s : 1;
	}

	function drawPie(x, y, r, ratio, label) {
		var done = Math.max(0, Math.min(1, ratio));
		var fs = labelFontScale();
		ctx.beginPath();
		ctx.moveTo(x, y);
		ctx.arc(x, y, r, -Math.PI / 2, -Math.PI / 2 + done * Math.PI * 2, false);
		ctx.closePath();
		ctx.fillStyle = PIE_DONE;
		ctx.fill();
		if (done < 0.999) {
			ctx.beginPath();
			ctx.moveTo(x, y);
			ctx.arc(x, y, r, -Math.PI / 2 + done * Math.PI * 2, -Math.PI / 2 + Math.PI * 2, false);
			ctx.closePath();
			ctx.fillStyle = isDark() ? '#475569' : PIE_REST;
			ctx.fill();
		}
		ctx.beginPath();
		ctx.arc(x, y, r, 0, Math.PI * 2);
		ctx.strokeStyle = isDark() ? 'rgba(255,255,255,0.35)' : 'rgba(0,0,0,0.28)';
		ctx.lineWidth = 1.5;
		ctx.stroke();
		ctx.fillStyle = isDark() ? '#f8fafc' : '#0f172a';
		ctx.font = '600 ' + Math.round(11 * fs) + 'px "Source Sans 3", "Microsoft YaHei", sans-serif';
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText(Math.round(done * 100) + '%', x, y);
		if (label) {
			ctx.font = '500 ' + Math.round(10 * fs) + 'px "Source Sans 3", "Microsoft YaHei", sans-serif';
			ctx.textBaseline = 'top';
			ctx.fillStyle = isDark() ? '#cbd5e1' : '#334155';
			ctx.fillText(label, x, y + r + 3);
		}
	}

	function paint() {
		var g = gObj();
		var graph = graphOf(g);
		if (!ensureOverlay() || !ctx || !g || !graph || !g.camera || typeof g.camera.worldToScreen !== 'function') {
			raf = requestAnimationFrame(paint);
			return;
		}
		if (overlay.width < 2) resizeOverlay();
		var cssW = overlay.clientWidth || 1;
		var cssH = overlay.clientHeight || 1;
		ctx.clearRect(0, 0, cssW, cssH);

		var pos = graph.positions;
		var edges = collectActiveEdges(graph);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		// Indirect edges: thicker overlay stroke
		var indirectCol = isDark() ? INDIRECT_COLOR_DARK : INDIRECT_COLOR_LIGHT;
		edges.forEach(function (e) {
			if (String(e.tag || '') !== 'indirect') return;
			if (state.overflowEdgeIds[e.id] || state.lowEdgeIds[e.id]) return;
			var ax = pos[e.source * 2];
			var ay = pos[e.source * 2 + 1];
			var bx = pos[e.target * 2];
			var by = pos[e.target * 2 + 1];
			var A = worldToCss(g, ax, ay);
			var B = worldToCss(g, bx, by);
			ctx.strokeStyle = indirectCol;
			ctx.lineWidth = INDIRECT_WIDTH;
			ctx.beginPath();
			ctx.moveTo(A[0], A[1]);
			ctx.lineTo(B[0], B[1]);
			ctx.stroke();
		});

		// Low depth: bold yellow (below max_h * 0.2)
		edges.forEach(function (e) {
			if (!state.lowEdgeIds[e.id] || state.overflowEdgeIds[e.id]) return;
			var ax = pos[e.source * 2];
			var ay = pos[e.source * 2 + 1];
			var bx = pos[e.target * 2];
			var by = pos[e.target * 2 + 1];
			var A = worldToCss(g, ax, ay);
			var B = worldToCss(g, bx, by);
			ctx.strokeStyle = LOW_COLOR;
			ctx.lineWidth = LOW_WIDTH;
			ctx.beginPath();
			ctx.moveTo(A[0], A[1]);
			ctx.lineTo(B[0], B[1]);
			ctx.stroke();
		});

		// Overflow: bold red (above max_h)
		edges.forEach(function (e) {
			if (!state.overflowEdgeIds[e.id]) return;
			var ax = pos[e.source * 2];
			var ay = pos[e.source * 2 + 1];
			var bx = pos[e.target * 2];
			var by = pos[e.target * 2 + 1];
			var A = worldToCss(g, ax, ay);
			var B = worldToCss(g, bx, by);
			ctx.strokeStyle = OVERFLOW_COLOR;
			ctx.lineWidth = OVERFLOW_WIDTH;
			ctx.beginPath();
			ctx.moveTo(A[0], A[1]);
			ctx.lineTo(B[0], B[1]);
			ctx.stroke();
		});

		// Irrigation pies
		var nameToId = Object.create(null);
		if (typeof graph.activeNodeIds === 'function') {
			graph.activeNodeIds().forEach(function (id) {
				var node = graph.getNode(id);
				var nm = nodeLabel(node);
				if (nm) nameToId[nm] = id;
			});
		}
		Object.keys(state.irrigation).forEach(function (name) {
			var id = nameToId[name];
			if (id == null) return;
			var info = state.irrigation[name];
			var p = worldToCss(g, pos[id * 2], pos[id * 2 + 1]);
			var base = (g.renderer && g.renderer.nodeScale > 0) ? g.renderer.nodeScale : 8;
			var r = Math.max(14, base * 1.6);
			drawPie(p[0], p[1], r, info.ratio, null);
		});

		raf = requestAnimationFrame(paint);
	}

	function normalizeDepthPayload(payload) {
		var map = Object.create(null);
		if (!payload) return map;
		if (Array.isArray(payload)) {
			payload.forEach(function (row) {
				if (!row) return;
				var n = normName(row.name || row.gate || row.id);
				var h = row.depth != null ? row.depth : row.h != null ? row.h : row.h1;
				if (n && isFinite(Number(h))) map[n] = Number(h);
			});
			return map;
		}
		Object.keys(payload).forEach(function (k) {
			var n = normName(k);
			var v = payload[k];
			var h = (v && typeof v === 'object') ? (v.depth != null ? v.depth : v.h1) : v;
			if (n && isFinite(Number(h))) map[n] = Number(h);
		});
		return map;
	}

	function normalizeIrrigationPayload(payload) {
		var map = Object.create(null);
		if (!payload) return map;
		function add(name, row) {
			var n = normName(name);
			if (!n || !row) return;
			var ratio = row.ratio;
			var volume = row.volume != null ? Number(row.volume) : (row.cumulative != null ? Number(row.cumulative) : NaN);
			var target = row.target != null ? Number(row.target) : (row.demand != null ? Number(row.demand) : NaN);
			if (!isFinite(Number(ratio))) {
				if (isFinite(volume) && isFinite(target) && target > 0) ratio = volume / target;
				else if (isFinite(volume) && volume >= 0 && volume <= 1 && !isFinite(target)) ratio = volume;
				else ratio = 0;
			}
			ratio = Math.max(0, Math.min(1, Number(ratio)));
			map[n] = {
				volume: isFinite(volume) ? volume : null,
				target: isFinite(target) ? target : null,
				ratio: ratio
			};
		}
		if (Array.isArray(payload)) {
			payload.forEach(function (row) {
				if (!row) return;
				add(row.name || row.gate || row.id, row);
			});
			return map;
		}
		Object.keys(payload).forEach(function (k) {
			var v = payload[k];
			if (typeof v === 'number') add(k, { ratio: v });
			else add(k, v || {});
		});
		return map;
	}

	function refreshStyles() {
		var g = gObj();
		var graph = graphOf(g);
		if (!graph) return { ok: false, reason: 'no-graph' };
		recomputeDepthAlerts(graph);
		applyGpuEdgeColors(g, graph);
		return {
			ok: true,
			overflowEdges: Object.keys(state.overflowEdgeIds).length,
			lowEdges: Object.keys(state.lowEdgeIds).length,
			depths: Object.keys(state.depths).length,
			irrigation: Object.keys(state.irrigation).length
		};
	}

	function setGateUpstreamDepths(payload) {
		state.depths = normalizeDepthPayload(payload);
		return refreshStyles();
	}

	function setDiversionIrrigation(payload) {
		state.irrigation = normalizeIrrigationPayload(payload);
		return {
			ok: true,
			count: Object.keys(state.irrigation).length,
			nodes: Object.keys(state.irrigation)
		};
	}

	function clearOverflow() {
		state.depths = Object.create(null);
		return refreshStyles();
	}

	function clearIrrigation() {
		state.irrigation = Object.create(null);
		return { ok: true };
	}

	function getState() {
		return {
			depths: state.depths,
			irrigation: state.irrigation,
			overflowEdgeCount: Object.keys(state.overflowEdgeIds).length,
			lowEdgeCount: Object.keys(state.lowEdgeIds).length
		};
	}

	function onMessage(ev) {
		var data = ev && ev.data;
		if (!data || data.type !== 'topoLive') return;
		var action = String(data.action || '');
		var payload = data.payload;
		var result = null;
		if (action === 'setGateUpstreamDepths') result = setGateUpstreamDepths(payload);
		else if (action === 'setDiversionIrrigation') result = setDiversionIrrigation(payload);
		else if (action === 'clearOverflow') result = clearOverflow();
		else if (action === 'clearIrrigation') result = clearIrrigation();
		else if (action === 'getState') result = getState();
		else if (action === 'refresh') result = refreshStyles();
		if (data.reqId != null && ev.source) {
			try {
				ev.source.postMessage({ type: 'topoLiveResult', reqId: data.reqId, result: result }, '*');
			} catch (e) { /* ignore */ }
		}
	}

	function bootWhenReady() {
		var started = Date.now();
		var timer = setInterval(function () {
			if (gObj() && graphOf(gObj())) {
				clearInterval(timer);
				state.ready = true;
				ensureOverlay();
				resizeOverlay();
				refreshStyles();
				if (!raf) raf = requestAnimationFrame(paint);
				window.addEventListener('resize', resizeOverlay);
			} else if (Date.now() - started > 30000) {
				clearInterval(timer);
			}
		}, 60);
	}

	window.TopoLive = {
		setGateUpstreamDepths: setGateUpstreamDepths,
		setDiversionIrrigation: setDiversionIrrigation,
		clearOverflow: clearOverflow,
		clearIrrigation: clearIrrigation,
		refresh: refreshStyles,
		getState: getState,
		getOverlayCanvas: function () {
			ensureOverlay();
			return overlay;
		},
		resizeOverlay: resizeOverlay,
		DIRECT_WIDTH: DIRECT_WIDTH,
		INDIRECT_WIDTH: INDIRECT_WIDTH
	};
	window.addEventListener('message', onMessage);
	bootWhenReady();
})();
