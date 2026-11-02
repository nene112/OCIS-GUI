/**
 * Node hover card (拓扑图节点悬停卡片).
 *
 * On hover a node morphs into a slightly larger rounded square (canvas overlay,
 * animated with an ease-out-back grow + ripple), then a glass telemetry card
 * slides in with three design-focused metric rows:
 *
 *   1. 流量 / 设计流量      Q (m³/s) vs edges.csv maxFlow → 百分比
 *   2. 已灌溉 / 需水量      delivered m³ vs demand → 百分比
 *   3. 闸前 / 闸后 实测水位  stage1 / stage2 (m) + 水位差
 *
 * Data: `/api/node-kpi?case=` snapshot (Q_td / W_completed_ratio_td / W_td /
 * stage1_td / stage2_td / edges.csv:maxFlow) overlaid by live pushes
 * (`TopoLive.setGateHydro`, optional) and `TopoLive.getState().irrigation`.
 *
 * GraphGPU itself is untouched: the square and the card are overlays, so the
 * WebGPU node never has to be rebuilt on hover.
 */
(function graphNodeHoverCard() {
	'use strict';

	var OVERLAY_ID = 'nv-node-hover-overlay';
	var CARD_W = 276;
	var MORPH_MS = 260;
	var RIPPLE_MS = 520;
	var EXIT_MS = 150;
	var CONTENT_REFRESH_MS = 700;
	var SNAPSHOT_TTL_MS = 15000;
	var LIVE_TTL_MS = 12000;
	var SKIP_KINDS = { '渠段': true };

	var KIND_TEXT = {
		'type-0': '水源',
		'type-1': '入流',
		'type-2': '出流',
		'type-3': '泄水',
		'type-4': '节制',
		'type-5': '地表径流',
		'type-6': '损失'
	};

	var state = {
		hoverId: null,
		hoverName: '',
		hoverAt: 0,
		leavingAt: 0,
		leavingGeom: null,
		geom: null,
		card: null,
		cardRows: null,
		cardH: 0,
		contentAt: 0,
		numbers: Object.create(null),
		snapshot: null,
		snapshotAt: 0,
		snapshotPending: false,
		live: Object.create(null),
		liveAt: 0,
		raf: 0,
		overlay: null,
		ctx: null,
		lastPointer: null,
		open: false
	};

	/* ------------------------------------------------------------------ utils */

	function gObj() {
		return window.g || null;
	}

	function graphOf(g) {
		return g && typeof g.getGraph === 'function' ? g.getGraph() : null;
	}

	function dpr() {
		var g = gObj();
		if (g && g.renderer && g.renderer.pixelRatio > 0) return Number(g.renderer.pixelRatio);
		return window.devicePixelRatio || 1;
	}

	function isDark() {
		return document.body.classList.contains('dark');
	}

	function clamp(v, lo, hi) {
		return Math.max(lo, Math.min(hi, v));
	}

	function easeOutCubic(t) {
		var u = 1 - t;
		return 1 - u * u * u;
	}

	/** Slight overshoot so the square "pops" then settles. */
	function easeOutBack(t) {
		var c1 = 1.22;
		var c3 = c1 + 1;
		var u = t - 1;
		return 1 + c3 * u * u * u + c1 * u * u;
	}

	function fmtFlow(v) {
		if (v === null || v === undefined || !isFinite(v)) return '—';
		var a = Math.abs(v);
		if (a >= 100) return v.toFixed(0);
		if (a >= 10) return v.toFixed(1);
		return v.toFixed(2);
	}

	function fmtStage(v) {
		if (v === null || v === undefined || !isFinite(v)) return '—';
		return v.toFixed(2);
	}

	function fmtVolume(v) {
		if (v === null || v === undefined || !isFinite(v)) return '—';
		var a = Math.abs(v);
		if (a >= 1e8) return (v / 1e8).toFixed(2) + ' 亿m³';
		if (a >= 1e4) return (v / 1e4).toFixed(1) + ' 万m³';
		if (a >= 100) return Math.round(v) + ' m³';
		return v.toFixed(1) + ' m³';
	}

	/** Same unit for both numbers, so "已供 / 需水" reads as a ratio pair. */
	function fmtVolumePair(a, b) {
		var scale = Math.max(Math.abs(a || 0), Math.abs(b || 0));
		if (scale >= 1e8) return [(a / 1e8).toFixed(2) + ' 亿m³', (b / 1e8).toFixed(2) + ' 亿m³'];
		if (scale >= 1e4) return [(a / 1e4).toFixed(2) + ' 万m³', (b / 1e4).toFixed(2) + ' 万m³'];
		return [Math.round(a) + ' m³', Math.round(b) + ' m³'];
	}

	function pctText(ratio) {
		if (ratio === null || ratio === undefined || !isFinite(ratio)) return '—';
		return String(Math.round(ratio * 100));
	}

	function flowColor(ratio) {
		if (ratio === null || ratio === undefined || !isFinite(ratio)) return null;
		if (ratio > 1.0) return '#ef4444';
		if (ratio >= 0.85) return '#f59e0b';
		if (ratio >= 0.35) return '#22c55e';
		return '#38bdf8';
	}

	/** Irrigation completion: cold when far from target, emerald near it, amber when over. */
	function irrColor(ratio) {
		if (ratio === null || ratio === undefined || !isFinite(ratio)) return null;
		if (ratio > 1.02) return '#f59e0b';
		if (ratio >= 0.85) return '#10b981';
		if (ratio >= 0.45) return '#22c55e';
		return '#38bdf8';
	}

	function rgbCss(r, g, b, alpha) {
		var R = Math.round(clamp(r, 0, 1) * 255);
		var G = Math.round(clamp(g, 0, 1) * 255);
		var B = Math.round(clamp(b, 0, 1) * 255);
		if (alpha === undefined) return 'rgb(' + R + ',' + G + ',' + B + ')';
		return 'rgba(' + R + ',' + G + ',' + B + ',' + alpha + ')';
	}

	function rgba(hexOrRgb, alpha) {
		var m = String(hexOrRgb).match(/^rgba?\(([^)]+)\)$/);
		if (m) {
			var parts = m[1].split(',').map(function (s) { return Number(s.trim()); });
			return 'rgba(' + parts[0] + ',' + parts[1] + ',' + parts[2] + ',' + alpha + ')';
		}
		var h = String(hexOrRgb).replace('#', '');
		if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
		if (h.length !== 6) return String(hexOrRgb);
		var r = parseInt(h.slice(0, 2), 16);
		var g = parseInt(h.slice(2, 4), 16);
		var b = parseInt(h.slice(4, 6), 16);
		return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
	}

	function caseName() {
		var q = new URLSearchParams(window.location.search).get('data');
		return (q && q.trim()) || '';
	}

	/* --------------------------------------------------------------- overlay */

	function ensureOverlay() {
		var host = document.querySelector('.canvas-container') ||
			(document.getElementById('graph-canvas') && document.getElementById('graph-canvas').parentElement);
		if (!host) return null;
		state.overlay = document.getElementById(OVERLAY_ID);
		if (!state.overlay) {
			state.overlay = document.createElement('canvas');
			state.overlay.id = OVERLAY_ID;
			state.overlay.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:7;';
			var cs = window.getComputedStyle(host);
			if (cs.position === 'static') host.style.position = 'relative';
			host.appendChild(state.overlay);
		}
		state.ctx = state.overlay.getContext('2d');
		return state.overlay;
	}

	function resizeOverlay() {
		if (!ensureOverlay()) return;
		var d = dpr();
		var w = state.overlay.clientWidth || state.overlay.parentElement.clientWidth || 800;
		var h = state.overlay.clientHeight || state.overlay.parentElement.clientHeight || 600;
		state.overlay.width = Math.max(1, Math.floor(w * d));
		state.overlay.height = Math.max(1, Math.floor(h * d));
		state.ctx.setTransform(d, 0, 0, d, 0, 0);
	}

	/* ------------------------------------------------------------- node geom */

	function nodeWorldRadius(g, graph, id) {
		var node = graph.getNode(id);
		var size = node && isFinite(node.size) && node.size > 0 ? node.size : (graph.defaultNodeSize || 6);
		var scale = (g.renderer && isFinite(g.renderer.nodeScale) && g.renderer.nodeScale > 0) ? g.renderer.nodeScale : 8;
		return size * scale * 0.01;
	}

	/** CSS-px geometry of a node: { x, y, r } relative to the overlay. */
	function nodeGeom(g, graph, id) {
		if (!g || !graph || !g.camera || typeof g.camera.worldToScreen !== 'function') return null;
		var wx = graph.positions[id * 2];
		var wy = graph.positions[id * 2 + 1];
		if (!isFinite(wx) || !isFinite(wy)) return null;
		var p = g.camera.worldToScreen(wx, wy);
		var ws = nodeWorldRadius(g, graph, id);
		var px = g.camera.worldToScreen(wx + ws, wy);
		var py = g.camera.worldToScreen(wx, wy + ws);
		var rx = Math.abs(px[0] - p[0]);
		var ry = Math.abs(py[1] - p[1]);
		var d = dpr();
		var canvas = document.getElementById('graph-canvas');
		var rect = canvas ? canvas.getBoundingClientRect() : null;
		var overlayRect = state.overlay ? state.overlay.getBoundingClientRect() : null;
		var offX = (rect && overlayRect) ? (rect.left - overlayRect.left) : 0;
		var offY = (rect && overlayRect) ? (rect.top - overlayRect.top) : 0;
		return {
			x: p[0] / d + offX,
			y: p[1] / d + offY,
			r: Math.max(3.2, Math.max(rx, ry) / d),
			clientX: (rect ? rect.left : 0) + p[0] / d,
			clientY: (rect ? rect.top : 0) + p[1] / d
		};
	}

	function nodeInfo(g, graph, id) {
		var node = graph.getNode(id);
		if (!node) return null;
		var props = node.properties || {};
		var name = String(props.name || props.title || '').trim();
		if (!name) return null;
		var kind = String(props.kind || '').trim();
		if (SKIP_KINDS[kind] || /^渠段/.test(name)) return null;
		return {
			id: id,
			name: name,
			kind: kind,
			tag: node.tag || '',
			canal: String(props.canal || '').trim(),
			accent: rgbCss(node.r, node.g, node.b)
		};
	}

	function pickNode(clientX, clientY) {
		var g = gObj();
		var graph = graphOf(g);
		if (!g || !graph || !g.controls || typeof g.controls.hitTest !== 'function') return null;
		var canvas = document.getElementById('graph-canvas');
		if (!canvas) return null;
		var rect = canvas.getBoundingClientRect();
		if (clientX < rect.left || clientY < rect.top || clientX > rect.right || clientY > rect.bottom) return null;
		var d = dpr();
		var id = g.controls.hitTest((clientX - rect.left) * d, (clientY - rect.top) * d);
		if (id === null || id === undefined) return null;
		return nodeInfo(g, graph, id);
	}

	/* ------------------------------------------------------------- data feed */

	function refreshSnapshot(force) {
		var name = caseName();
		if (!name) return;
		if (state.snapshotPending) return;
		if (!force && state.snapshot && Date.now() - state.snapshotAt < SNAPSHOT_TTL_MS) return;
		state.snapshotPending = true;
		fetch('/api/node-kpi?case=' + encodeURIComponent(name) + '&_=' + Date.now(), { cache: 'no-store' })
			.then(function (resp) {
				if (!resp.ok) throw new Error('HTTP ' + resp.status);
				return resp.json();
			})
			.then(function (data) {
				state.snapshot = data || null;
				state.snapshotAt = Date.now();
			})
			.catch(function () { /* keep previous snapshot */ })
			.then(function () {
				state.snapshotPending = false;
				updateCardContent(true);
			});
	}

	function liveFor(name) {
		var row = state.live[name];
		if (!row) return null;
		if (Date.now() - state.liveAt > LIVE_TTL_MS) return null;
		return row;
	}

	function irrigationFor(name) {
		try {
			if (typeof window.TopoLive === 'undefined' || typeof window.TopoLive.getState !== 'function') return null;
			var all = window.TopoLive.getState();
			var irr = all && all.irrigation;
			return (irr && irr[name]) ? irr[name] : null;
		} catch (e) {
			return null;
		}
	}

	/** Merged view of one node: live values win over the case snapshot. */
	function metricsFor(name) {
		var snap = state.snapshot && state.snapshot.nodes ? state.snapshot.nodes[name] : null;
		var live = liveFor(name);
		var irr = irrigationFor(name);
		var q = snap ? snap.q : null;
		var qDesign = snap ? snap.qDesign : null;
		var wRatio = snap ? snap.wRatio : null;
		var wDelivered = snap ? snap.wDelivered : null;
		var wDemand = snap ? snap.wDemand : null;
		var wScope = snap ? snap.wScope : null;
		var wUnits = snap ? snap.wUnits : 0;
		var stageUp = snap ? snap.stageUp : null;
		var stageDown = snap ? snap.stageDown : null;
		var depthUp = null;
		var depthDown = null;
		var isLive = false;

		if (live) {
			isLive = true;
			if (live.q != null && isFinite(live.q)) q = Math.abs(live.q);
			if (live.z1 != null && isFinite(live.z1)) stageUp = live.z1;
			if (live.z2 != null && isFinite(live.z2)) stageDown = live.z2;
			if (live.h1 != null && isFinite(live.h1)) depthUp = live.h1;
			if (live.h2 != null && isFinite(live.h2)) depthDown = live.h2;
		}
		if (irr) {
			if (irr.ratio != null && isFinite(irr.ratio)) wRatio = irr.ratio;
			if (irr.volume != null && isFinite(irr.volume)) wDelivered = irr.volume;
			if (irr.target != null && isFinite(irr.target)) wDemand = irr.target;
		}

		return {
			q: q,
			qDesign: qDesign,
			qRatio: (q != null && qDesign != null && qDesign > 0) ? Math.abs(q) / qDesign : null,
			wRatio: wRatio,
			wDelivered: wDelivered,
			wDemand: wDemand,
			wScope: wScope,
			wUnits: wUnits,
			stageUp: stageUp,
			stageDown: stageDown,
			depthUp: depthUp,
			depthDown: depthDown,
			live: isLive
		};
	}

	/* ------------------------------------------------------------------- card */

	function ensureCard() {
		if (state.card) return state.card;
		var el = document.createElement('div');
		el.className = 'nv-node-card';
		el.setAttribute('role', 'dialog');
		el.innerHTML = '' +
			'<span class="nvc-accent"></span>' +
			'<div class="nvc-head">' +
			'<span class="nvc-dot"></span>' +
			'<span class="nvc-name"></span>' +
			'<span class="nvc-chip"></span>' +
			'</div>' +
			'<div class="nvc-sep"></div>' +
			'<div class="nvc-row" data-k="flow" style="--d:40ms">' +
			'<div class="nvc-line"><span class="nvc-k">流量 / 设计流量</span>' +
			'<span class="nvc-v"><b class="nvc-pct">—</b><i class="nvc-unit">%</i></span></div>' +
			'<div class="nvc-track"><i class="nvc-fill"></i></div>' +
			'<div class="nvc-sub"></div>' +
			'</div>' +
			'<div class="nvc-row" data-k="irr" style="--d:90ms">' +
			'<div class="nvc-line"><span class="nvc-k">已灌溉 / 需水量</span>' +
			'<span class="nvc-v"><b class="nvc-pct">—</b><i class="nvc-unit">%</i></span></div>' +
			'<div class="nvc-track"><i class="nvc-fill"></i></div>' +
			'<div class="nvc-sub"></div>' +
			'</div>' +
			'<div class="nvc-row nvc-row-stage" data-k="stage" style="--d:140ms">' +
			'<div class="nvc-line"><span class="nvc-k">闸前 / 闸后实测水位</span>' +
			'<span class="nvc-delta"></span></div>' +
			'<div class="nvc-stage">' +
			'<div class="nvc-cell"><i>闸前</i><b>—</b><span>m</span></div>' +
			'<span class="nvc-arrow"></span>' +
			'<div class="nvc-cell"><i>闸后</i><b>—</b><span>m</span></div>' +
			'</div>' +
			'<div class="nvc-sub"></div>' +
			'</div>' +
			'<div class="nvc-foot"><span class="nvc-live"></span><span class="nvc-foot-text"></span></div>';
		document.body.appendChild(el);
		state.card = el;
		state.cardRows = {
			name: el.querySelector('.nvc-name'),
			chip: el.querySelector('.nvc-chip'),
			dot: el.querySelector('.nvc-dot'),
			accent: el.querySelector('.nvc-accent'),
			flowPct: el.querySelector('[data-k="flow"] .nvc-pct'),
			flowFill: el.querySelector('[data-k="flow"] .nvc-fill'),
			flowSub: el.querySelector('[data-k="flow"] .nvc-sub'),
			irrK: el.querySelector('[data-k="irr"] .nvc-k'),
			irrPct: el.querySelector('[data-k="irr"] .nvc-pct'),
			irrFill: el.querySelector('[data-k="irr"] .nvc-fill'),
			irrSub: el.querySelector('[data-k="irr"] .nvc-sub'),
			up: el.querySelector('[data-k="stage"] .nvc-cell:nth-of-type(1) b'),
			down: el.querySelector('[data-k="stage"] .nvc-cell:nth-of-type(2) b'),
			delta: el.querySelector('[data-k="stage"] .nvc-delta'),
			stageSub: el.querySelector('[data-k="stage"] .nvc-sub'),
			foot: el.querySelector('.nvc-foot-text'),
			liveDot: el.querySelector('.nvc-live')
		};
		return el;
	}

	function animateNumber(el, to) {
		if (!el) return;
		var target = (to === null || to === undefined) ? NaN : Number(to);
		var from = Number(el.__nvcFrom);
		if (!isFinite(from)) from = 0;
		el.__nvcFrom = target;
		if (!isFinite(target)) {
			el.textContent = '—';
			return;
		}
		var t0 = performance.now();
		var token = (el.__nvcToken || 0) + 1;
		el.__nvcToken = token;
		var dur = 380;
		function step(now) {
			if (el.__nvcToken !== token) return;
			var k = clamp((now - t0) / dur, 0, 1);
			var e = easeOutCubic(k);
			var v = from + (target - from) * e;
			el.textContent = String(Math.round(v));
			if (k < 1) requestAnimationFrame(step);
		}
		requestAnimationFrame(step);
	}

	function setFill(el, ratio, color) {
		if (!el) return;
		var r = (ratio === null || ratio === undefined || !isFinite(ratio)) ? 0 : clamp(ratio, 0, 1);
		el.style.background = color || '';
		el.style.width = (r * 100).toFixed(2) + '%';
	}

	function updateCardContent(force) {
		var now = performance.now();
		if (!state.open) return;
		if (!force && now - state.contentAt < CONTENT_REFRESH_MS) return;
		state.contentAt = now;

		var g = gObj();
		var graph = graphOf(g);
		if (!g || !graph || state.hoverId === null) return;
		var info = nodeInfo(g, graph, state.hoverId);
		if (!info) return;
		var m = metricsFor(info.name);
		ensureCard();

		var rows = state.cardRows;
		var kindText = KIND_TEXT[info.tag] || info.kind || '节点';

		if (state.card.__nvcName !== info.name) {
			state.card.__nvcName = info.name;
			rows.name.textContent = info.name;
			rows.name.title = info.name;
			rows.chip.textContent = kindText;
			rows.dot.style.background = info.accent;
			rows.dot.style.boxShadow = '0 0 10px ' + rgba(info.accent, 0.75);
			rows.chip.style.color = info.accent;
			rows.chip.style.background = rgba(info.accent, 0.13);
			rows.accent.style.background = 'linear-gradient(90deg,' + info.accent + ',transparent)';
			state.card.style.setProperty('--nvc-accent', info.accent);
			// reset bars so the fill animates from 0 on a fresh node
			rows.flowFill.style.width = '0%';
			rows.irrFill.style.width = '0%';
			requestAnimationFrame(function () {
				if (state.cardRows) applyBars(m, info);
			});
		} else {
			applyBars(m, info);
		}

		// numbers (count-up only when the value actually moves)
		var flowPct = (m.qRatio === null || !isFinite(m.qRatio)) ? null : m.qRatio * 100;
		var flowKey = flowPct === null ? 'x' : Math.round(flowPct);
		if (rows.flowPct.__nvcTarget !== flowKey) {
			rows.flowPct.__nvcTarget = flowKey;
			animateNumber(rows.flowPct, flowPct);
		}
		var irrPct = (m.wRatio === null || !isFinite(m.wRatio)) ? null : m.wRatio * 100;
		var irrKey = irrPct === null ? 'x' : Math.round(irrPct);
		if (rows.irrPct.__nvcTarget !== irrKey) {
			rows.irrPct.__nvcTarget = irrKey;
			animateNumber(rows.irrPct, irrPct);
		}

		// flow sub-line
		if (m.q === null && m.qDesign === null) {
			rows.flowSub.textContent = '无流量记录';
			rows.flowSub.classList.add('is-empty');
		} else {
			rows.flowSub.classList.remove('is-empty');
			var parts = [];
			parts.push('实测 ' + fmtFlow(m.q) + ' m³/s');
			parts.push('设计 ' + fmtFlow(m.qDesign) + ' m³/s');
			rows.flowSub.textContent = parts.join(' · ');
		}

		// irrigation sub-line
		rows.irrK.textContent = m.wScope === 'downstream' ? '已灌溉 / 下游需水' : '已灌溉 / 需水量';
		if (m.wRatio === null && m.wDelivered === null) {
			rows.irrSub.textContent = '该节点无配水任务';
			rows.irrSub.classList.add('is-empty');
			rows.irrSub.classList.remove('nvc-sub-wrap');
		} else if (m.wRatio === null) {
			rows.irrSub.classList.remove('is-empty');
			rows.irrSub.textContent = '已供 ' + fmtVolume(m.wDelivered) + ' · 无需求记录';
			rows.irrSub.classList.remove('nvc-sub-wrap');
		} else {
			rows.irrSub.classList.remove('is-empty');
			var s = [];
			if (m.wDelivered !== null && m.wDemand !== null) {
				var pair = fmtVolumePair(m.wDelivered, m.wDemand);
				s.push('已供 ' + pair[0]);
				s.push('需水 ' + pair[1]);
			} else if (m.wDelivered !== null) {
				s.push('已供 ' + fmtVolume(m.wDelivered));
			} else if (m.wDemand !== null) {
				s.push('需水 ' + fmtVolume(m.wDemand));
			} else {
				s.push('调度完成度 ' + Math.round(m.wRatio * 100) + '%');
			}
			if (m.wScope === 'downstream' && m.wUnits > 0) s.push('下游 ' + m.wUnits + ' 个配水单元');
			rows.irrSub.textContent = s.join(' · ');
			rows.irrSub.classList.toggle('nvc-sub-wrap', m.wScope === 'downstream');
		}

		// stage block
		rows.up.textContent = fmtStage(m.stageUp);
		rows.down.textContent = fmtStage(m.stageDown);
		var delta = (m.stageUp != null && m.stageDown != null) ? (m.stageDown - m.stageUp) : null;
		if (delta === null) {
			rows.delta.textContent = '';
			rows.delta.className = 'nvc-delta';
		} else {
			rows.delta.textContent = (delta >= 0 ? '+' : '') + delta.toFixed(2) + ' m';
			rows.delta.className = 'nvc-delta ' + (delta >= 0 ? 'is-up' : 'is-down');
		}
		if (m.stageUp === null && m.stageDown === null) {
			rows.stageSub.textContent = '无实测水位记录';
			rows.stageSub.classList.add('is-empty');
		} else {
			rows.stageSub.classList.remove('is-empty');
			var ds = [];
			if (m.depthUp != null) ds.push('闸前水深 ' + fmtStage(m.depthUp) + ' m');
			if (m.depthDown != null) ds.push('闸后水深 ' + fmtStage(m.depthDown) + ' m');
			if (!ds.length) {
				if (delta !== null) {
					ds.push('闸前 − 闸后 ' + Math.abs(delta).toFixed(2) + ' m');
				} else {
					ds.push('缺' + (m.stageUp === null ? '闸前' : '闸后') + '实测水位');
				}
			}
			rows.stageSub.textContent = ds.join(' · ');
		}

		// footer
		var when = state.snapshot && state.snapshot.time ? String(state.snapshot.time) : '';
		var bits = [];
		bits.push(m.live ? '实时仿真' : '案例记录');
		if (when) bits.push(when);
		if (info.canal) bits.push(info.canal);
		rows.foot.textContent = bits.join(' · ');
		rows.liveDot.classList.toggle('is-live', !!m.live);
	}

	function applyBars(m, info) {
		var rows = state.cardRows;
		if (!rows) return;
		var fc = flowColor(m.qRatio);
		setFill(rows.flowFill, m.qRatio, fc ? 'linear-gradient(90deg,' + rgba(fc, 0.55) + ',' + fc + ')' : '');
		rows.flowPct.style.color = fc || '';
		var ic = irrColor(m.wRatio);
		setFill(rows.irrFill, m.wRatio, ic ? 'linear-gradient(90deg,' + rgba(ic, 0.5) + ',' + ic + ')' : '');
		rows.irrPct.style.color = ic || '';
		rows.flowFill.parentElement.classList.toggle('is-over', m.qRatio !== null && m.qRatio > 1.005);
		rows.irrFill.parentElement.classList.toggle('is-over', m.wRatio !== null && m.wRatio > 1.005);
		void info;
	}

	/* --------------------------------------------------------------- position */

	function placeCard(geom) {
		var card = state.card;
		if (!card || !geom) return;
		var vw = window.innerWidth;
		var vh = window.innerHeight;
		var w = card.offsetWidth || CARD_W;
		var h = state.cardH || card.offsetHeight || 210;
		if (card.offsetHeight && card.offsetHeight !== state.cardH) state.cardH = card.offsetHeight;
		var gap = Math.max(12, geom.r * 1.62 + 14);
		var left = geom.clientX + gap;
		if (left + w > vw - 10) left = geom.clientX - gap - w;
		if (left < 10) left = Math.min(vw - w - 10, geom.clientX + gap);
		var top = geom.clientY - h / 2;
		top = clamp(top, 52, vh - 46 - h);
		card.style.left = Math.round(left) + 'px';
		card.style.top = Math.round(top) + 'px';
	}

	/* ------------------------------------------------------------------ paint */

	function paintSquare(ctx, geom, text, e, ripple, accent, dark) {
		var side = geom.r * 2 * (1 + 0.56 * e);
		var radius = geom.r + (side * 0.27 - geom.r) * e;
		var hx = geom.x - side / 2;
		var hy = geom.y - side / 2;

		// expanding ripple: reads as "the node wakes up"
		if (ripple < 1) {
			var rs = side * (1 + 0.5 * ripple);
			var rr = radius * (1 + 0.55 * ripple);
			ctx.beginPath();
			roundRect(ctx, geom.x - rs / 2, geom.y - rs / 2, rs, rs, rr);
			ctx.strokeStyle = rgba(accent, 0.42 * (1 - ripple));
			ctx.lineWidth = 1.6;
			ctx.stroke();
		}

		// soft glow behind the square
		ctx.save();
		ctx.shadowColor = rgba(accent, dark ? 0.5 : 0.34);
		ctx.shadowBlur = (10 + 12 * e);
		ctx.beginPath();
		roundRect(ctx, hx, hy, side, side, radius);
		var fill = ctx.createLinearGradient(hx, hy, hx + side, hy + side);
		if (dark) {
			fill.addColorStop(0, 'rgba(43,45,58,0.97)');
			fill.addColorStop(1, 'rgba(22,23,30,0.97)');
		} else {
			fill.addColorStop(0, 'rgba(255,255,255,0.98)');
			fill.addColorStop(1, 'rgba(246,246,250,0.98)');
		}
		ctx.fillStyle = fill;
		ctx.fill();
		ctx.restore();

		// accent border + inner hairline
		ctx.beginPath();
		roundRect(ctx, hx, hy, side, side, radius);
		ctx.strokeStyle = rgba(accent, 0.9 * e);
		ctx.lineWidth = 1.8;
		ctx.stroke();

		ctx.beginPath();
		roundRect(ctx, hx + 3, hy + 3, side - 6, side - 6, Math.max(1, radius - 3));
		ctx.strokeStyle = dark ? 'rgba(255,255,255,0.10)' : 'rgba(0,0,0,0.06)';
		ctx.lineWidth = 1;
		ctx.stroke();

		// name tag under the square (replaces the GPU label hidden by the square)
		if (text && e > 0.55) {
			var a = (e - 0.55) / 0.45;
			ctx.save();
			ctx.globalAlpha = clamp(a, 0, 1);
			ctx.font = '600 11px "Source Sans 3","Microsoft YaHei",sans-serif';
			ctx.textAlign = 'center';
			ctx.textBaseline = 'top';
			var label = text;
			var tw = ctx.measureText(label).width;
			var padX = 7;
			var boxW = tw + padX * 2;
			var boxH = 17;
			var bx = geom.x - boxW / 2;
			var by = geom.y + side / 2 + 6;
			ctx.beginPath();
			roundRect(ctx, bx, by, boxW, boxH, 5);
			ctx.fillStyle = dark ? 'rgba(20,21,28,0.92)' : 'rgba(255,255,255,0.95)';
			ctx.fill();
			ctx.strokeStyle = rgba(accent, 0.35);
			ctx.lineWidth = 1;
			ctx.stroke();
			ctx.fillStyle = dark ? '#e8e6f0' : '#1d1d1f';
			ctx.fillText(label, geom.x, by + 3.5);
			ctx.restore();
		}
	}

	function roundRect(ctx, x, y, w, h, r) {
		var rr = Math.max(0, Math.min(r, Math.min(w, h) / 2));
		ctx.moveTo(x + rr, y);
		ctx.lineTo(x + w - rr, y);
		ctx.arcTo(x + w, y, x + w, y + rr, rr);
		ctx.lineTo(x + w, y + h - rr);
		ctx.arcTo(x + w, y + h, x + w - rr, y + h, rr);
		ctx.lineTo(x + rr, y + h);
		ctx.arcTo(x, y + h, x, y + h - rr, rr);
		ctx.lineTo(x, y + rr);
		ctx.arcTo(x, y, x + rr, y, rr);
		ctx.closePath();
	}

	function clearOverlay() {
		if (!state.ctx || !state.overlay) return;
		state.ctx.clearRect(0, 0, state.overlay.clientWidth || 1, state.overlay.clientHeight || 1);
	}

	function frame() {
		state.raf = 0;
		var g = gObj();
		var graph = graphOf(g);
		if (!ensureOverlay()) return;

		if (state.overlay.width < 2 || Math.abs(state.overlay.clientWidth * dpr() - state.overlay.width) > 2) {
			resizeOverlay();
		}
		clearOverlay();
		if (!g || !graph) return;

		var now = performance.now();
		var dark = isDark();
		var hovering = state.hoverId !== null;

		if (hovering) {
			var geom = nodeGeom(g, graph, state.hoverId);
			if (geom) {
				state.geom = geom;
				var info = nodeInfo(g, graph, state.hoverId);
				var accent = info ? info.accent : (dark ? '#7c6ff7' : '#6850d8');
				var dt = now - state.hoverAt;
				var e = dt >= MORPH_MS ? 1 : easeOutBack(clamp(dt / MORPH_MS, 0, 1));
				var ripple = clamp(dt / RIPPLE_MS, 0, 1) < 1 ? clamp(dt / RIPPLE_MS, 0, 1) : 1;
				paintSquare(state.ctx, geom, info ? info.name : '', e, ripple, accent, dark);
				placeCard(geom);
				if (state.open) updateCardContent(false);
			}
		} else if (state.leavingGeom && now < state.leavingAt + EXIT_MS) {
			var ge = state.leavingGeom;
			var k = clamp((now - state.leavingAt) / EXIT_MS, 0, 1);
			var ef = 1 - easeOutCubic(k);
			paintSquare(state.ctx, ge, '', ef, 1, ge.accent || (dark ? '#7c6ff7' : '#6850d8'), dark);
		} else {
			state.leavingGeom = null;
		}

		// keep painting while the card is open (node may be dragged / camera eased)
		if (state.hoverId !== null || (state.leavingGeom && now < state.leavingAt + EXIT_MS)) {
			if (!state.raf) state.raf = requestAnimationFrame(frame);
		}
	}

	function kick() {
		if (!state.raf) state.raf = requestAnimationFrame(frame);
	}

	/* ------------------------------------------------------------- hover flow */

	function openFor(info) {
		if (!info) return;
		if (state.hoverId === info.id) return;
		ensureCard();
		state.hoverId = info.id;
		state.hoverName = info.name;
		state.hoverAt = performance.now();
		state.leavingGeom = null;
		var g = gObj();
		var graph = graphOf(g);
		var geom = graph ? nodeGeom(g, graph, info.id) : null;
		if (geom) state.geom = geom;
		state.open = true;
		state.card.style.setProperty('--nvc-accent', info.accent);
		state.card.classList.add('is-open');
		document.body.classList.add('nv-node-card-open');
		state.contentAt = 0;
		updateCardContent(true);
		refreshSnapshot(false);
		kick();
	}

	function closeHover() {
		if (state.hoverId === null) return;
		var g = gObj();
		var graph = graphOf(g);
		var geom = null;
		if (graph) {
			var info = nodeInfo(g, graph, state.hoverId);
			var accent = info ? info.accent : null;
			geom = nodeGeom(g, graph, state.hoverId);
			if (geom) geom.accent = accent;
		}
		state.leavingGeom = geom;
		state.leavingAt = performance.now();
		state.hoverId = null;
		state.hoverName = '';
		state.open = false;
		if (state.card) state.card.classList.remove('is-open');
		document.body.classList.remove('nv-node-card-open');
		kick();
	}

	/* -------------------------------------------------------------------- boot */

	function onPointerMove(ev) {
		var g = gObj();
		// dragging a node / panning: drop the card so it never fights the gesture
		if (g && g.controls && g.controls.drag && g.controls.drag.active) {
			closeHover();
			return;
		}
		state.lastPointer = { x: ev.clientX, y: ev.clientY };
		var info = pickNode(ev.clientX, ev.clientY);
		if (!info) {
			// tiny grace period: pointer jitter on the node edge must not flicker
			if (state.hoverId !== null && performance.now() - state.hoverAt < 180) return;
			closeHover();
			return;
		}
		if (state.hoverId === info.id) {
			kick();
			return;
		}
		openFor(info);
	}

	function onPointerLeave() {
		closeHover();
	}

	function boot() {
		var canvas = document.getElementById('graph-canvas');
		if (!canvas) return false;
		ensureCard();
		if (!ensureOverlay()) return false;
		resizeOverlay();
		kick();
		canvas.addEventListener('pointermove', onPointerMove);
		canvas.addEventListener('pointerdown', function () { closeHover(); }, true);
		canvas.addEventListener('pointerleave', onPointerLeave);
		canvas.addEventListener('wheel', function () {
			if (state.hoverId !== null) kick();
		}, { passive: true });
		window.addEventListener('resize', function () {
			resizeOverlay();
			if (state.hoverId !== null) kick();
		});
		window.addEventListener('scroll', function () {
			if (state.hoverId !== null) kick();
		}, true);
		document.addEventListener('keydown', function (ev) {
			if (ev.key === 'Escape') closeHover();
		});
		refreshSnapshot(true);
		setInterval(function () {
			if (document.hidden) return;
			if (state.hoverId !== null) refreshSnapshot(false);
		}, 10000);
		return true;
	}

	/* live bridge: TopoLive.setGateHydro({ name: {q,h1,h2,z1,z2} }) */
	function setGateHydro(payload) {
		if (!payload || typeof payload !== 'object') return { ok: false };
		var map = payload;
		if (Array.isArray(payload)) {
			map = Object.create(null);
			payload.forEach(function (row) {
				if (!row) return;
				var n = String(row.name || row.gate || '').trim();
				if (n) map[n] = row;
			});
		}
		var names = Object.keys(map);
		for (var i = 0; i < names.length; ++i) {
			var n = String(names[i] || '').trim();
			var row = map[names[i]];
			if (!n || !row || typeof row !== 'object') continue;
			var cur = state.live[n] || {};
			['q', 'h1', 'h2', 'z1', 'z2', 't'].forEach(function (k) {
				var v = row[k];
				if (v !== undefined && v !== null && isFinite(Number(v))) cur[k] = Number(v);
			});
			cur.at = Date.now();
			state.live[n] = cur;
		}
		state.liveAt = Date.now();
		if (state.hoverId !== null) {
			state.contentAt = 0;
			if (state.open) updateCardContent(true);
		}
		return { ok: true, count: names.length };
	}

	window.addEventListener('message', function (ev) {
		var data = ev && ev.data;
		if (!data || data.type !== 'topoLive') return;
		if (String(data.action || '') === 'setGateHydro') setGateHydro(data.payload);
	});

	function waitForGraph() {
		var started = Date.now();
		var timer = setInterval(function () {
			if (window.g && typeof window.g.getGraph === 'function' && window.g.getGraph()) {
				clearInterval(timer);
				if (boot()) return;
			}
			if (Date.now() - started > 25000) clearInterval(timer);
		}, 60);
	}

	// Extend the existing TopoLive bridge (graph-live-api.js) instead of replacing it.
	function patchTopoLive() {
		if (typeof window.TopoLive !== 'object' || !window.TopoLive) return false;
		window.TopoLive.setGateHydro = setGateHydro;
		return true;
	}
	if (!patchTopoLive()) {
		var timer = setInterval(function () {
			if (patchTopoLive()) clearInterval(timer);
		}, 120);
		setTimeout(function () { clearInterval(timer); }, 20000);
	}

	window.NVNodeCard = {
		open: function () { if (state.hoverId !== null) kick(); },
		close: closeHover,
		reload: function () { refreshSnapshot(true); },
		setGateHydro: setGateHydro,
		getState: function () {
			return {
				hover: state.hoverName || null,
				open: state.open,
				snapshotAt: state.snapshotAt,
				live: Object.keys(state.live)
			};
		}
	};

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', waitForGraph);
	} else {
		waitForGraph();
	}
})();
