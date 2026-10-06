(function canvas2dFallback() {
	var TYPE_COLOR = {
		'0': '#7c6ff7',
		'1': '#4ea3ff',
		'2': '#34a853',
		'3': '#f4b400',
		'4': '#e85d4c',
		'5': '#c084fc',
		'6': '#fb923c',
		boundary: '#94a3b8',
		'渠段': '#22c55e'
	};
	var started = false;
	var nodes = [];
	var links = [];
	var cam = { x: 0, y: 0, k: 1 };
	var drag = null;
	var hover = -1;
	var canvas;
	var ctx;

	function caseName() {
		var q = new URLSearchParams(window.location.search).get('data');
		return (q && q.trim()) || '';
	}

	function hostIsLoopback() {
		var h = (location.hostname || '').toLowerCase();
		return h === 'localhost' || h === '127.0.0.1' || h === '::1';
	}

	function shouldStart() {
		if (started || window.g) return false;
		return /(?:^|[?&])force2d=1(?:&|$)/.test(location.search);
	}

	function unavailableHintHtml() {
		var origin = (location.origin || '') + '/';
		if (!navigator.gpu) {
			return '当前浏览器没有 WebGPU（Safari 通常如此）。请用 <strong>Chrome 或 Edge</strong> 打开 <strong>' + origin + '</strong>，才能显示完整拓扑图。';
		}
		if (!window.isSecureContext && !hostIsLoopback()) {
			return '局域网 HTTP 不是安全上下文，Chrome 会关闭 WebGPU。请用 Tailscale HTTPS 打开（同一台机器的 <strong>https://&lt;名称&gt;.ts.net/</strong>）。';
		}
		return 'WebGPU 初始化失败。请用 Chrome / Edge 打开 <strong>' + origin + '</strong>。';
	}

	function showUnavailableHint() {
		if (started || window.g) return;
		var fb = document.getElementById('fallback');
		if (!fb || fb.classList.contains('fallback-2d-on')) return;
		fb.classList.add('visible');
		fb.setAttribute('aria-hidden', 'false');
		var msg = document.getElementById('fallbackMsg');
		if (msg) msg.style.display = '';
		var p = document.querySelector('#fallbackMsg p');
		if (p) p.innerHTML = unavailableHintHtml();
	}

	function reasonText() {
		if (!navigator.gpu && !window.isSecureContext && !hostIsLoopback()) {
			return '当前是局域网 HTTP，Chrome 会关闭 WebGPU。已用 Canvas 2D 显示拓扑。本机请打开 http://127.0.0.1:3000/';
		}
		if (!navigator.gpu) return '浏览器没有 WebGPU。已用 Canvas 2D 显示拓扑。请用 Chrome / Edge 打开当前 HTTPS 地址。';
		if (!window.isSecureContext && !hostIsLoopback()) {
			return '非安全上下文（局域网 HTTP）下 WebGPU 不可用。已用 Canvas 2D 显示拓扑。';
		}
		return 'WebGPU 初始化失败。已用 Canvas 2D 显示拓扑。';
	}

	function build(data) {
		var nameToI = {};
		nodes = [];
		(data.nodes || []).forEach(function (name) {
			var n = String(name || '').trim();
			if (!n || nameToI[n] != null) return;
			nameToI[n] = nodes.length;
			nodes.push({
				name: n,
				x: (Math.random() - 0.5) * 80,
				y: (Math.random() - 0.5) * 80,
				vx: 0,
				vy: 0,
				type: '0'
			});
		});
		links = [];
		(data.edges || []).forEach(function (e) {
			var a = nameToI[String(e.source || '').trim()];
			var b = nameToI[String(e.target || '').trim()];
			if (a == null || b == null || a === b) return;
			var t = String(e.type != null ? e.type : '0');
			var conn = String(e.ConnectionType || e.connectionType || 'indirect').toLowerCase();
			links.push({
				a: a,
				b: b,
				type: t,
				conn: conn,
				max_h: e.max_h,
				min_h: e.min_h,
				targetName: String(e.target || '').trim(),
				overflow: false,
				low: false
			});
			if (t) nodes[b].type = t;
		});
		var extra = nameToI[String((data.edges && data.edges[0] && data.edges[0].end) || '')];
		void extra;
		layout();
		fit();
	}

	function layout() {
		var i;
		var n = nodes.length;
		if (!n) return;
		for (var iter = 0; iter < 260; iter++) {
			for (i = 0; i < n; i++) {
				nodes[i].vx *= 0.62;
				nodes[i].vy *= 0.62;
			}
			for (i = 0; i < n; i++) {
				for (var j = i + 1; j < n; j++) {
					var dx = nodes[j].x - nodes[i].x;
					var dy = nodes[j].y - nodes[i].y;
					var d2 = dx * dx + dy * dy + 0.08;
					var f = 420 / d2;
					var d = Math.sqrt(d2);
					dx /= d;
					dy /= d;
					nodes[i].vx -= dx * f;
					nodes[i].vy -= dy * f;
					nodes[j].vx += dx * f;
					nodes[j].vy += dy * f;
				}
			}
			for (i = 0; i < links.length; i++) {
				var L = links[i];
				var na = nodes[L.a];
				var nb = nodes[L.b];
				var sx = nb.x - na.x;
				var sy = nb.y - na.y;
				var sl = Math.sqrt(sx * sx + sy * sy) || 1;
				var pull = (sl - 46) * 0.045;
				sx = (sx / sl) * pull;
				sy = (sy / sl) * pull;
				na.vx += sx;
				na.vy += sy;
				nb.vx -= sx;
				nb.vy -= sy;
			}
			for (i = 0; i < n; i++) {
				nodes[i].x += nodes[i].vx;
				nodes[i].y += nodes[i].vy;
			}
		}
	}

	function fit() {
		if (!nodes.length || !canvas) return;
		var minx = Infinity;
		var maxx = -Infinity;
		var miny = Infinity;
		var maxy = -Infinity;
		for (var i = 0; i < nodes.length; i++) {
			if (nodes[i].x < minx) minx = nodes[i].x;
			if (nodes[i].x > maxx) maxx = nodes[i].x;
			if (nodes[i].y < miny) miny = nodes[i].y;
			if (nodes[i].y > maxy) maxy = nodes[i].y;
		}
		var bw = Math.max(8, maxx - minx);
		var bh = Math.max(8, maxy - miny);
		var w = canvas.clientWidth || 800;
		var h = canvas.clientHeight || 600;
		cam.k = Math.min(w / (bw * 1.35), h / (bh * 1.35));
		cam.x = (minx + maxx) / 2;
		cam.y = (miny + maxy) / 2;
	}

	function toScreen(x, y) {
		var w = canvas.clientWidth;
		var h = canvas.clientHeight;
		return [(x - cam.x) * cam.k + w / 2, (y - cam.y) * cam.k + h / 2];
	}

	function toWorld(sx, sy) {
		var w = canvas.clientWidth;
		var h = canvas.clientHeight;
		return [(sx - w / 2) / cam.k + cam.x, (sy - h / 2) / cam.k + cam.y];
	}

	function hit(sx, sy) {
		var r = Math.max(8, 6 * Math.min(2.2, cam.k / 4));
		var best = -1;
		var bestD = r * r;
		for (var i = 0; i < nodes.length; i++) {
			var p = toScreen(nodes[i].x, nodes[i].y);
			var dx = p[0] - sx;
			var dy = p[1] - sy;
			var d2 = dx * dx + dy * dy;
			if (d2 < bestD) {
				bestD = d2;
				best = i;
			}
		}
		return best;
	}

	function resize() {
		if (!canvas) return;
		var dpr = window.devicePixelRatio || 1;
		var w = canvas.clientWidth || canvas.parentElement.clientWidth || 800;
		var h = canvas.clientHeight || canvas.parentElement.clientHeight || 600;
		canvas.width = Math.max(1, Math.floor(w * dpr));
		canvas.height = Math.max(1, Math.floor(h * dpr));
		ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
		draw();
	}

	function nodeColor(t) {
		return TYPE_COLOR[String(t)] || '#7c6ff7';
	}

	function draw() {
		if (!ctx || !canvas) return;
		var w = canvas.clientWidth;
		var h = canvas.clientHeight;
		var dark = document.body.classList.contains('dark');
		ctx.clearRect(0, 0, w, h);
		ctx.fillStyle = dark ? '#1e1f26' : '#f5f5f7';
		ctx.fillRect(0, 0, w, h);
		ctx.lineWidth = Math.max(1, 1.2 * Math.min(2, cam.k / 8));
		for (var i = 0; i < links.length; i++) {
			var L = links[i];
			var a = toScreen(nodes[L.a].x, nodes[L.a].y);
			var b = toScreen(nodes[L.b].x, nodes[L.b].y);
			var isIndirect = String(L.conn || L.connectionType || '').toLowerCase() === 'indirect';
			var overflow = !!(L.overflow);
			var low = !!(L.low) && !overflow;
			ctx.strokeStyle = overflow ? '#dc2626' : (low ? '#eab308' : nodeColor(L.type));
			ctx.globalAlpha = overflow || low ? 0.92 : (isIndirect ? 0.7 : 0.45);
			ctx.lineWidth = overflow
				? Math.max(3.5, 3.2 * Math.min(2.5, cam.k / 8))
				: (low
					? Math.max(3.2, 3.0 * Math.min(2.4, cam.k / 8))
					: (isIndirect
						? Math.max(2.8, 2.6 * Math.min(2.2, cam.k / 8))
						: Math.max(1, 1.2 * Math.min(2, cam.k / 8))));
			ctx.beginPath();
			ctx.moveTo(a[0], a[1]);
			ctx.lineTo(b[0], b[1]);
			ctx.stroke();
		}
		ctx.globalAlpha = 1;
		var r = Math.max(5, Math.min(14, 5.5 + cam.k * 0.08));
		var fontScale = 1;
		try {
			var fsSaved = Number(localStorage.getItem('ocisTopoLabelFontScale'));
			if (isFinite(fsSaved) && fsSaved > 0) fontScale = fsSaved;
		} catch (e) { /* ignore */ }
		var fontPx = Math.max(8, Math.round(12 * fontScale));
		ctx.font = fontPx + 'px "Source Sans 3", "Microsoft YaHei", sans-serif';
		ctx.textAlign = 'center';
		ctx.textBaseline = 'top';
		for (i = 0; i < nodes.length; i++) {
			var p = toScreen(nodes[i].x, nodes[i].y);
			var irr = nodes[i].irrigation;
			if (irr && isFinite(Number(irr.ratio))) {
				var ratio = Math.max(0, Math.min(1, Number(irr.ratio)));
				var pr = Math.max(r + 4, 12);
				ctx.beginPath();
				ctx.moveTo(p[0], p[1]);
				ctx.arc(p[0], p[1], pr, -Math.PI / 2, -Math.PI / 2 + ratio * Math.PI * 2, false);
				ctx.closePath();
				ctx.fillStyle = '#22c55e';
				ctx.fill();
				if (ratio < 0.999) {
					ctx.beginPath();
					ctx.moveTo(p[0], p[1]);
					ctx.arc(p[0], p[1], pr, -Math.PI / 2 + ratio * Math.PI * 2, -Math.PI / 2 + Math.PI * 2, false);
					ctx.closePath();
					ctx.fillStyle = dark ? '#475569' : '#cbd5e1';
					ctx.fill();
				}
				ctx.lineWidth = 1.5;
				ctx.strokeStyle = dark ? '#111' : '#fff';
				ctx.beginPath();
				ctx.arc(p[0], p[1], pr, 0, Math.PI * 2);
				ctx.stroke();
				ctx.fillStyle = dark ? '#f8fafc' : '#0f172a';
				ctx.textBaseline = 'middle';
				ctx.fillText(Math.round(ratio * 100) + '%', p[0], p[1]);
				ctx.textBaseline = 'top';
			} else {
				ctx.beginPath();
				ctx.fillStyle = nodeColor(nodes[i].type);
				ctx.arc(p[0], p[1], r, 0, Math.PI * 2);
				ctx.fill();
				ctx.lineWidth = 1.5;
				ctx.strokeStyle = dark ? '#111' : '#fff';
				ctx.stroke();
			}
			if (cam.k > 3 || nodes.length < 80 || i === hover) {
				ctx.fillStyle = dark ? '#d8d6e0' : '#1d1d1f';
				ctx.fillText(nodes[i].name, p[0], p[1] + r + 3);
			}
		}
		var hint = document.getElementById('fallback2dHint');
		if (hint) {
			hint.textContent = reasonText() + '  ·  ' + nodes.length + ' 节点 · ' + links.length + ' 边 · 滚轮缩放，拖动画布';
		}
		var idle = document.querySelector('.statusbar .idle-text');
		if (idle) idle.textContent = nodes.length + ' nodes · ' + links.length + ' edges · Canvas 2D';
	}

	function bindCanvas() {
		canvas.addEventListener('mousedown', function (ev) {
			if (ev.button !== 0) return;
			drag = { x: ev.clientX, y: ev.clientY, cx: cam.x, cy: cam.y };
		});
		window.addEventListener('mousemove', function (ev) {
			var rect = canvas.getBoundingClientRect();
			var sx = ev.clientX - rect.left;
			var sy = ev.clientY - rect.top;
			hover = hit(sx, sy);
			if (drag) {
				cam.x = drag.cx - (ev.clientX - drag.x) / cam.k;
				cam.y = drag.cy - (ev.clientY - drag.y) / cam.k;
			}
			draw();
		});
		window.addEventListener('mouseup', function () {
			drag = null;
		});
		canvas.addEventListener('wheel', function (ev) {
			ev.preventDefault();
			var rect = canvas.getBoundingClientRect();
			var sx = ev.clientX - rect.left;
			var sy = ev.clientY - rect.top;
			var w0 = toWorld(sx, sy);
			var factor = ev.deltaY > 0 ? 0.9 : 1.12;
			cam.k = Math.max(0.15, Math.min(40, cam.k * factor));
			var w1 = toWorld(sx, sy);
			cam.x += w0[0] - w1[0];
			cam.y += w0[1] - w1[1];
			draw();
		}, { passive: false });
		window.addEventListener('resize', resize);
		document.addEventListener('click', function (ev) {
			var btn = ev.target.closest && ev.target.closest('.toolbar .btn');
			if (!btn || !started) return;
			var t = (btn.textContent || '').toLowerCase();
			if (t.indexOf('fit') >= 0) {
				fit();
				draw();
			} else if (t.indexOf('reset') >= 0) {
				layout();
				fit();
				draw();
			}
		});
	}

	async function boot() {
		if (started || window.g) return;
		started = true;
		var fb = document.getElementById('fallback');
		if (fb) {
			fb.classList.add('visible', 'fallback-2d-on');
			fb.setAttribute('aria-hidden', 'false');
		}
		var msg = document.getElementById('fallbackMsg');
		if (msg) msg.style.display = 'none';
		canvas = document.getElementById('fallback-canvas');
		if (!canvas) return;
		canvas.style.display = 'block';
		ctx = canvas.getContext('2d');
		bindCanvas();
		resize();
		install2dTopoLive();
		var name = caseName();
		var url = name
			? '/api/graph-case?case=' + encodeURIComponent(name) + '&_=' + Date.now()
			: '/api/graph?_=' + Date.now();
		try {
			var resp = await fetch(url, { cache: 'no-store' });
			var data = await resp.json();
			if (!resp.ok) throw new Error(data.error || ('HTTP ' + resp.status));
			build(data);
			resize();
		} catch (err) {
			var hint = document.getElementById('fallback2dHint');
			if (hint) hint.textContent = '无法加载拓扑：' + (err.message || err);
		}
	}

	function install2dTopoLive() {
		function applyDepths(payload) {
			var map = Object.create(null);
			if (Array.isArray(payload)) {
				payload.forEach(function (row) {
					if (!row) return;
					var n = String(row.name || row.gate || '').trim();
					var h = row.depth != null ? row.depth : row.h1;
					if (n && isFinite(Number(h))) map[n] = Number(h);
				});
			} else if (payload) {
				Object.keys(payload).forEach(function (k) {
					var v = payload[k];
					var h = (v && typeof v === 'object') ? (v.depth != null ? v.depth : v.h1) : v;
					if (isFinite(Number(h))) map[String(k).trim()] = Number(h);
				});
			}
			links.forEach(function (L) {
				// direct / leakage 等内边界不参与超限/过低着色
				if (String(L.conn || '').toLowerCase() !== 'indirect') {
					L.overflow = false;
					L.low = false;
					return;
				}
				var h = map[L.targetName];
				var maxH = (L.max_h === '' || L.max_h == null) ? NaN : Number(L.max_h);
				L.overflow = isFinite(h) && isFinite(maxH) && maxH > 0 && h > maxH;
				L.low = !L.overflow && isFinite(h) && isFinite(maxH) && maxH > 0 && h < maxH * 0.2;
			});
			draw();
			return { ok: true };
		}
		function applyIrrigation(payload) {
			var byName = Object.create(null);
			nodes.forEach(function (n) { byName[n.name] = n; n.irrigation = null; });
			function add(name, row) {
				var n = byName[String(name || '').trim()];
				if (!n || !row) return;
				var ratio = row.ratio;
				var volume = Number(row.volume != null ? row.volume : row.cumulative);
				var target = Number(row.target != null ? row.target : row.demand);
				if (!isFinite(Number(ratio))) {
					if (isFinite(volume) && isFinite(target) && target > 0) ratio = volume / target;
					else ratio = isFinite(volume) ? volume : 0;
				}
				n.irrigation = { ratio: Math.max(0, Math.min(1, Number(ratio) || 0)) };
			}
			if (Array.isArray(payload)) {
				payload.forEach(function (row) {
					if (row) add(row.name || row.gate, row);
				});
			} else if (payload) {
				Object.keys(payload).forEach(function (k) {
					var v = payload[k];
					add(k, typeof v === 'number' ? { ratio: v } : v);
				});
			}
			draw();
			return { ok: true };
		}
		window.TopoLive = {
			setGateUpstreamDepths: applyDepths,
			setDiversionIrrigation: applyIrrigation,
			clearOverflow: function () {
				links.forEach(function (L) { L.overflow = false; L.low = false; });
				draw();
				return { ok: true };
			},
			clearIrrigation: function () {
				nodes.forEach(function (n) { n.irrigation = null; });
				draw();
				return { ok: true };
			},
			refresh: function () { draw(); return { ok: true }; },
			getState: function () { return { mode: 'canvas2d' }; }
		};
	}

	function watch() {
		if (shouldStart()) {
			boot();
			return;
		}
		if (!navigator.gpu || (!window.isSecureContext && !hostIsLoopback())) {
			showUnavailableHint();
		}
		var fb = document.getElementById('fallback');
		if (fb && window.MutationObserver) {
			new MutationObserver(function () {
				if (shouldStart()) boot();
			}).observe(fb, { attributes: true, attributeFilter: ['class'] });
		}
		var t0 = Date.now();
		var timer = setInterval(function () {
			if (window.g) {
				clearInterval(timer);
				var hide = document.getElementById('fallback');
				if (hide && !hide.classList.contains('fallback-2d-on')) {
					hide.classList.remove('visible');
					hide.setAttribute('aria-hidden', 'true');
				}
				return;
			}
			if (shouldStart()) {
				clearInterval(timer);
				boot();
				return;
			}
			if (Date.now() - t0 > 8000) {
				clearInterval(timer);
				showUnavailableHint();
			}
		}, 80);
	}

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', watch);
	} else {
		watch();
	}
})();
