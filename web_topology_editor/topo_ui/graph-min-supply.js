/**
 * 最小供水网络：完整拓扑半透明灰，选中的渠段和闸门保持原色。
 * GET /api/opt-milp/min-supply?case=&file=
 * 打开 /topo?data=<case>&minSupply=1 时自动套上。
 */
(function ocisMinSupply() {
	'use strict';

	var GRAY_NODE = [0.58, 0.6, 0.63, 0.22];
	var GRAY_EDGE = [0.5, 0.52, 0.55];
	var OVERLAY_ID = 'ocis-min-supply-overlay';

	var STORAGE_KEY = 'ocisMinSupplySelection';

	var showSeq = 0;

	var state = {
		active: false,
		snap: null,
		keep: null,
		labels: [],
		timer: 0,
		raf: 0,
		selection: null
	};

	function remember(caseName, body) {
		var poolSources = [];
		(body.selectedPools || []).forEach(function (pool) {
			if (pool && pool.source) poolSources.push(String(pool.source));
		});
		state.selection = {
			caseName: caseName,
			poolSources: poolSources,
			nodes: (body.selectedNodes || []).slice()
		};
		try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state.selection)); } catch (e) { /* ignore */ }
	}

	function forget() {
		state.selection = null;
		try { sessionStorage.removeItem(STORAGE_KEY); } catch (e) { /* ignore */ }
	}

	function gObj() {
		return window.g || null;
	}

	function graphOf() {
		var g = gObj();
		return g && typeof g.getGraph === 'function' ? g.getGraph() : null;
	}

	function realName(node) {
		if (!node) return '';
		var props = node.properties || {};
		if (props.__ocisSupplyName) return String(props.__ocisSupplyName).trim();
		var name = props.name || props.title || '';
		if (name === '\u200b') return '';
		return String(name).trim();
	}

	function isCanal(node) {
		if (!node) return false;
		var props = node.properties || {};
		var kind = String(props.kind || node.tag || '').trim();
		return kind === '渠段' || /^渠段-/.test(realName(node));
	}

	function nodeKept(node, selected) {
		if (isCanal(node)) {
			var props = node.properties || {};
			var source = String(props.source || '').trim();
			var target = String(props.target || '').trim();
			return !!(source && target && selected[source] && selected[target]);
		}
		var name = realName(node);
		return !!(name && selected[name]);
	}

	function syncButton(shown) {
		var btn = document.getElementById('ocisOptMinSupply');
		if (!btn) return;
		btn.classList.toggle('is-supply-on', !!shown);
		btn.setAttribute('aria-pressed', shown ? 'true' : 'false');
	}

	function chip(summary, bad) {
		var el = document.getElementById('ocisMinSupplyChip');
		if (!el) {
			el = document.createElement('div');
			el.id = 'ocisMinSupplyChip';
			el.className = 'ocis-min-supply-chip';
			el.innerHTML = '<span></span><button type="button">恢复</button>';
			document.body.appendChild(el);
			el.querySelector('button').addEventListener('click', function () { clear(); });
		}
		el.classList.toggle('is-bad', !!bad);
		el.querySelector('span').textContent = summary || '';
		el.hidden = false;
	}

	function hideChip() {
		var el = document.getElementById('ocisMinSupplyChip');
		if (el) el.hidden = true;
	}

	function markDirty() {
		var g = gObj();
		var graph = graphOf();
		if (!graph) return;
		graph.dirtyNodes = true;
		graph.dirtyEdges = true;
		if (g && typeof g.markDirty === 'function') g.markDirty();
	}

	function restore() {
		var graph = graphOf();
		var snap = state.snap;
		if (!graph || !snap) {
			state.snap = null;
			state.keep = null;
			state.labels = [];
			return;
		}
		Object.keys(snap.nodes).forEach(function (id) {
			var rec = snap.nodes[id];
			var i = Number(id);
			if (!graph.colors || i * 4 + 3 >= graph.colors.length) return;
			graph.colors[i * 4] = rec.color[0];
			graph.colors[i * 4 + 1] = rec.color[1];
			graph.colors[i * 4 + 2] = rec.color[2];
			graph.colors[i * 4 + 3] = rec.color[3];
			var node = graph.getNode(i);
			if (node && node.properties) {
				node.properties.name = rec.name;
				node.properties.title = rec.title;
				delete node.properties.__ocisSupplyName;
			}
		});
		Object.keys(snap.edges).forEach(function (id) {
			var rec = snap.edges[id];
			var i = Number(id);
			if (!graph.edgeColors || i * 3 + 2 >= graph.edgeColors.length) return;
			graph.edgeColors[i * 3] = rec[0];
			graph.edgeColors[i * 3 + 1] = rec[1];
			graph.edgeColors[i * 3 + 2] = rec[2];
		});
		state.snap = null;
		state.keep = null;
		state.labels = [];
		markDirty();
		var overlay = document.getElementById(OVERLAY_ID);
		if (overlay) overlay.remove();
	}

	function paint() {
		var graph = graphOf();
		var snap = state.snap;
		if (!graph || !snap || !state.keep) return;
		Object.keys(snap.nodes).forEach(function (id) {
			var i = Number(id);
			if (!graph.colors || i * 4 + 3 >= graph.colors.length) return;
			var color = state.keep[id] ? snap.nodes[id].color : GRAY_NODE;
			graph.colors[i * 4] = color[0];
			graph.colors[i * 4 + 1] = color[1];
			graph.colors[i * 4 + 2] = color[2];
			graph.colors[i * 4 + 3] = color[3];
		});
		if (graph.edgeIndices && graph.edgeColors) {
			Object.keys(snap.edges).forEach(function (id) {
				var i = Number(id);
				if (i * 3 + 2 >= graph.edgeColors.length) return;
				var a = graph.edgeIndices[i * 2];
				var b = graph.edgeIndices[i * 2 + 1];
				var on = !!(state.keep[a] && state.keep[b]);
				var color = on ? snap.edges[id] : GRAY_EDGE;
				graph.edgeColors[i * 3] = color[0];
				graph.edgeColors[i * 3 + 1] = color[1];
				graph.edgeColors[i * 3 + 2] = color[2];
			});
		}
		markDirty();
	}

	function apply(selectedList) {
		var graph = graphOf();
		if (!graph || typeof graph.activeNodeIds !== 'function') {
			throw new Error('拓扑图还没加载好');
		}
		restore();
		var selected = Object.create(null);
		(selectedList || []).forEach(function (name) {
			if (name) selected[String(name)] = true;
		});
		var snap = { nodes: {}, edges: {} };
		var keep = Object.create(null);
		var labels = [];
		graph.activeNodeIds().forEach(function (id) {
			var node = graph.getNode(id);
			if (!node) return;
			var props = node.properties || (node.properties = {});
			var name = realName(node);
			snap.nodes[id] = {
				color: [
					graph.colors[id * 4],
					graph.colors[id * 4 + 1],
					graph.colors[id * 4 + 2],
					graph.colors[id * 4 + 3]
				],
				name: props.name,
				title: props.title
			};
			var on = nodeKept(node, selected);
			keep[id] = on;
			if (!on && name && !isCanal(node)) {
				labels.push({ id: id, name: name });
				props.__ocisSupplyName = name;
				props.name = '\u200b';
				props.title = '';
			}
		});
		if (typeof graph.activeEdgeIds === 'function' && graph.edgeColors) {
			graph.activeEdgeIds().forEach(function (id) {
				snap.edges[id] = [
					graph.edgeColors[id * 3],
					graph.edgeColors[id * 3 + 1],
					graph.edgeColors[id * 3 + 2]
				];
			});
		}
		state.snap = snap;
		state.keep = keep;
		state.labels = labels;
		state.active = true;
		paint();
	}

	function worldToCss(g, x, y) {
		if (!g || !g.camera || typeof g.camera.worldToScreen !== 'function') return null;
		var s = g.camera.worldToScreen(x, y);
		var dpr = (g.renderer && g.renderer.pixelRatio > 0) ? Number(g.renderer.pixelRatio) : (window.devicePixelRatio || 1);
		var sx = s && s.length >= 2 ? s[0] : (s && s.x);
		var sy = s && s.length >= 2 ? s[1] : (s && s.y);
		if (!isFinite(sx) || !isFinite(sy)) return null;
		return [sx / dpr, sy / dpr];
	}

	function drawLabels() {
		var host = document.querySelector('.canvas-container');
		if (!host || !state.active) return;
		var overlay = document.getElementById(OVERLAY_ID);
		if (!overlay) {
			overlay = document.createElement('canvas');
			overlay.id = OVERLAY_ID;
			overlay.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:5;';
			var cs = window.getComputedStyle(host);
			if (cs.position === 'static') host.style.position = 'relative';
			host.appendChild(overlay);
		}
		var ctx = overlay.getContext('2d');
		var dpr = window.devicePixelRatio || 1;
		var w = overlay.clientWidth || host.clientWidth || 1;
		var h = overlay.clientHeight || host.clientHeight || 1;
		overlay.width = Math.max(1, Math.floor(w * dpr));
		overlay.height = Math.max(1, Math.floor(h * dpr));
		ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
		ctx.clearRect(0, 0, w, h);
		var g = gObj();
		var graph = graphOf();
		if (!g || !graph) return;
		var dark = document.body.classList.contains('dark');
		ctx.font = '12px "Source Sans 3","Microsoft YaHei",sans-serif';
		ctx.textAlign = 'center';
		ctx.textBaseline = 'bottom';
		ctx.fillStyle = dark ? 'rgba(186,190,204,0.38)' : 'rgba(90,94,110,0.40)';
		state.labels.forEach(function (item) {
			var x = graph.positions[item.id * 2];
			var y = graph.positions[item.id * 2 + 1];
			var pt = worldToCss(g, x, y);
			if (!pt) return;
			ctx.fillText(item.name, pt[0], pt[1] - 8);
		});
	}

	function loop() {
		if (!state.active) return;
		drawLabels();
		state.raf = requestAnimationFrame(loop);
	}

	function clear() {
		showSeq += 1;
		state.active = false;
		forget();
		if (state.timer) clearInterval(state.timer);
		state.timer = 0;
		if (state.raf) cancelAnimationFrame(state.raf);
		state.raf = 0;
		restore();
		hideChip();
		syncButton(false);
	}

	function show(opts) {
		opts = opts || {};
		var params = new URLSearchParams(window.location.search);
		var caseName = String(opts.caseName || params.get('data') || window.__ocisCurrentCaseName || '').trim();
		if (!caseName) return Promise.reject(new Error('请先打开工程'));
		var file = String(opts.file || params.get('demand') || '').trim();
		var url = '/api/opt-milp/min-supply?case=' + encodeURIComponent(caseName);
		if (file) url += '&file=' + encodeURIComponent(file);
		var seq = ++showSeq;
		return fetch(url).then(function (res) {
			return res.text().then(function (text) {
				var body = {};
				if (text) {
					try { body = JSON.parse(text); } catch (e) {
						throw new Error(text.replace(/\s+/g, ' ').slice(0, 180));
					}
				}
				if (!res.ok || body.ok === false) throw new Error(body.error || ('HTTP ' + res.status));
				return body;
			});
		}).then(function (body) {
			if (seq !== showSeq) return body;
			if (!body.selectedNodes || !body.selectedNodes.length) {
				throw new Error(body.summary || '没有可显示的最小供水网络');
			}
			apply(body.selectedNodes);
			remember(caseName, body);
			chip(body.summary || '最小供水网络', !body.capacityFeasible);
			syncButton(true);
			if (state.timer) clearInterval(state.timer);
			state.timer = setInterval(paint, 800);
			if (state.raf) cancelAnimationFrame(state.raf);
			state.raf = requestAnimationFrame(loop);
			return body;
		});
	}

	function toggle(opts) {
		if (state.active) {
			clear();
			return Promise.resolve(false);
		}
		return show(opts).then(function () { return true; });
	}

	function boot() {
		var flag = '';
		try { flag = new URLSearchParams(window.location.search).get('minSupply') || ''; } catch (e) { flag = ''; }
		if (flag !== '1') return;
		var tries = 0;
		var timer = setInterval(function () {
			tries += 1;
			var graph = graphOf();
			var ready = graph && typeof graph.activeNodeIds === 'function' && graph.numNodes > 0;
			if (ready) {
				clearInterval(timer);
				show({}).catch(function (err) {
					chip(err && err.message ? err.message : '最小供水网络失败', true);
				});
			} else if (tries > 80) {
				clearInterval(timer);
			}
		}, 250);
	}

	window.OcisMinSupply = {
		show: show,
		clear: clear,
		toggle: toggle,
		active: function () { return state.active; },
		selection: function () {
			if (!state.active || !state.selection) return null;
			if (!state.selection.poolSources || !state.selection.poolSources.length) return null;
			return state.selection;
		}
	};

	if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
	else boot();
})();
