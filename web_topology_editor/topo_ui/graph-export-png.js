/**
 * Topology PNG export — WYSIWYG capture of the live view
 * (WebGPU canvas + GraphGPU label overlay + TopoLive overlay).
 * Resolution is selectable (1×–4× of CSS view size, or custom width).
 */
(function graphExportPng() {
	var MAX_EDGE = 8192;
	var STORAGE_KEY = 'ocisTopoExportScale';
	var PANEL_ID = 'ocisExportPngPanel';

	function caseName() {
		try {
			var q = new URLSearchParams(window.location.search).get('data');
			return (q && q.trim()) || 'topo';
		} catch (e) {
			return 'topo';
		}
	}

	function graphCanvas() {
		return document.getElementById('graph-canvas');
	}

	function fallbackCanvas() {
		return document.getElementById('fallback-canvas');
	}

	function labelCanvas(g) {
		if (g && g.renderer && g.renderer.labelCanvas) return g.renderer.labelCanvas;
		var host = document.querySelector('.canvas-container');
		if (!host) return null;
		var list = host.querySelectorAll('canvas');
		for (var i = 0; i < list.length; ++i) {
			var c = list[i];
			if (c.id === 'graph-canvas' || c.id === 'topo-live-overlay' || c.id === 'fallback-canvas') continue;
			var z = window.getComputedStyle(c).zIndex;
			if (c.style.pointerEvents === 'none' || Number(z) === 2 || z === '2') return c;
		}
		return null;
	}

	function liveOverlayCanvas() {
		if (window.TopoLive && typeof window.TopoLive.getOverlayCanvas === 'function') {
			return window.TopoLive.getOverlayCanvas();
		}
		return document.getElementById('topo-live-overlay');
	}

	function parseCssColor(str) {
		if (!str) return { r: 12, g: 12, b: 16, a: 1, css: '#0c0c10' };
		var c = document.createElement('canvas');
		c.width = c.height = 1;
		var x = c.getContext('2d');
		x.fillStyle = str;
		x.fillRect(0, 0, 1, 1);
		var p = x.getImageData(0, 0, 1, 1).data;
		return { r: p[0], g: p[1], b: p[2], a: p[3] / 255, css: 'rgba(' + p[0] + ',' + p[1] + ',' + p[2] + ',' + (p[3] / 255) + ')' };
	}

	function backgroundCss() {
		var el = document.querySelector('.canvas-container') || document.body;
		var bg = window.getComputedStyle(el).backgroundColor;
		if (!bg || bg === 'transparent' || bg === 'rgba(0, 0, 0, 0)') {
			bg = window.getComputedStyle(document.body).backgroundColor;
		}
		return parseCssColor(bg);
	}

	function downloadBlob(blob, filename) {
		var url = URL.createObjectURL(blob);
		var a = document.createElement('a');
		a.href = url;
		a.download = filename;
		a.rel = 'noopener';
		document.body.appendChild(a);
		a.click();
		a.remove();
		setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
	}

	function waitFrames(n) {
		return new Promise(function (resolve) {
			var left = Math.max(1, n | 0);
			function step() {
				left -= 1;
				if (left <= 0) resolve();
				else requestAnimationFrame(step);
			}
			requestAnimationFrame(step);
		});
	}

	function clampScale(scale, cssW, cssH) {
		var s = Number(scale);
		if (!isFinite(s) || s <= 0) s = 1;
		var maxByW = MAX_EDGE / Math.max(1, cssW);
		var maxByH = MAX_EDGE / Math.max(1, cssH);
		return Math.min(s, maxByW, maxByH);
	}

	function viewSize() {
		var canvas = graphCanvas();
		var fb = fallbackCanvas();
		var fbOn = document.getElementById('fallback') && document.getElementById('fallback').classList.contains('fallback-2d-on');
		var el = (fbOn && fb) ? fb : canvas;
		if (!el) el = document.querySelector('.canvas-container');
		var cssW = (el && (el.clientWidth || el.width)) || 800;
		var cssH = (el && (el.clientHeight || el.height)) || 600;
		return { cssW: cssW, cssH: cssH, el: el, fbOn: !!fbOn };
	}

	function savedScale() {
		try {
			var v = Number(localStorage.getItem(STORAGE_KEY));
			if (isFinite(v) && v > 0) return v;
		} catch (e) { /* ignore */ }
		return 2;
	}

	function saveScale(v) {
		try { localStorage.setItem(STORAGE_KEY, String(v)); } catch (e) { /* ignore */ }
	}

	function ensurePanel() {
		var panel = document.getElementById(PANEL_ID);
		if (panel) return panel;
		panel = document.createElement('div');
		panel.id = PANEL_ID;
		panel.setAttribute('role', 'dialog');
		panel.setAttribute('aria-label', '截图分辨率');
		panel.innerHTML =
			'<div class="ocis-export-title">截图分辨率</div>' +
			'<div class="ocis-export-hint">导出与当前布局/风格一致（含文字与实时叠加）。分辨率按视图 CSS 尺寸倍率。</div>' +
			'<div class="ocis-export-sizes" id="ocisExportSizePreview">—</div>' +
			'<label class="ocis-export-opt"><input type="radio" name="ocisExportScale" value="1"> 1× 当前视图</label>' +
			'<label class="ocis-export-opt"><input type="radio" name="ocisExportScale" value="2"> 2×</label>' +
			'<label class="ocis-export-opt"><input type="radio" name="ocisExportScale" value="3"> 3×</label>' +
			'<label class="ocis-export-opt"><input type="radio" name="ocisExportScale" value="4"> 4×</label>' +
			'<label class="ocis-export-opt ocis-export-custom">' +
			'<input type="radio" name="ocisExportScale" value="custom"> 自定义宽度 ' +
			'<input type="number" id="ocisExportCustomW" min="200" max="' + MAX_EDGE + '" step="10" value="1920"> px' +
			'</label>' +
			'<div class="ocis-export-actions">' +
			'<button type="button" class="ocis-export-cancel" id="ocisExportCancel">取消</button>' +
			'<button type="button" class="ocis-export-go" id="ocisExportGo">导出 PNG</button>' +
			'</div>';
		var style = document.createElement('style');
		style.textContent =
			'#' + PANEL_ID + '{' +
			'position:fixed;z-index:12000;min-width:260px;max-width:320px;padding:12px 14px;' +
			'background:var(--bg-surface,#1a1a1e);color:var(--text,#f4f4f5);' +
			'border:1px solid var(--border,#333);border-radius:10px;box-shadow:0 12px 40px rgba(0,0,0,.35);' +
			'font-family:"Source Sans 3",Source Sans Pro,"Microsoft YaHei",sans-serif;font-size:13px;' +
			'display:none;}' +
			'#' + PANEL_ID + '.open{display:block;}' +
			'#' + PANEL_ID + ' .ocis-export-title{font-weight:600;margin-bottom:4px;}' +
			'#' + PANEL_ID + ' .ocis-export-hint{font-size:11px;opacity:.75;line-height:1.35;margin-bottom:8px;}' +
			'#' + PANEL_ID + ' .ocis-export-sizes{font-size:11px;font-variant-numeric:tabular-nums;opacity:.9;margin-bottom:8px;}' +
			'#' + PANEL_ID + ' .ocis-export-opt{display:flex;align-items:center;gap:8px;padding:4px 0;cursor:pointer;}' +
			'#' + PANEL_ID + ' .ocis-export-custom input[type=number]{width:72px;margin:0 4px;padding:2px 6px;' +
			'border-radius:4px;border:1px solid var(--border,#444);background:transparent;color:inherit;}' +
			'#' + PANEL_ID + ' .ocis-export-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:10px;}' +
			'#' + PANEL_ID + ' .ocis-export-actions button{font:inherit;font-size:12px;font-weight:600;padding:6px 12px;' +
			'border-radius:6px;border:1px solid var(--border,#444);cursor:pointer;background:transparent;color:inherit;}' +
			'#' + PANEL_ID + ' .ocis-export-go{background:var(--accent,#4ea3ff);border-color:transparent;color:#0b1220;}';
		document.head.appendChild(style);
		document.body.appendChild(panel);

		panel.addEventListener('change', function () { updateSizePreview(); });
		panel.addEventListener('input', function (ev) {
			if (ev.target && ev.target.id === 'ocisExportCustomW') {
				var custom = panel.querySelector('input[name="ocisExportScale"][value="custom"]');
				if (custom) custom.checked = true;
				updateSizePreview();
			}
		});
		document.getElementById('ocisExportCancel').addEventListener('click', hidePanel);
		document.getElementById('ocisExportGo').addEventListener('click', function () {
			var choice = readScaleChoice();
			hidePanel();
			runExport(choice.scale, choice.label);
		});
		return panel;
	}

	function readScaleChoice() {
		var panel = ensurePanel();
		var checked = panel.querySelector('input[name="ocisExportScale"]:checked');
		var vs = viewSize();
		var val = checked ? checked.value : '2';
		if (val === 'custom') {
			var wIn = document.getElementById('ocisExportCustomW');
			var w = Number(wIn && wIn.value);
			if (!isFinite(w) || w < 200) w = Math.round(vs.cssW * 2);
			w = Math.min(MAX_EDGE, Math.max(200, Math.round(w)));
			var scale = clampScale(w / vs.cssW, vs.cssW, vs.cssH);
			saveScale(scale);
			return { scale: scale, label: Math.round(vs.cssW * scale) + '×' + Math.round(vs.cssH * scale) };
		}
		var scaleN = clampScale(Number(val) || 2, vs.cssW, vs.cssH);
		saveScale(scaleN);
		return { scale: scaleN, label: scaleN + '×' };
	}

	function updateSizePreview() {
		var panel = document.getElementById(PANEL_ID);
		if (!panel) return;
		var vs = viewSize();
		var choice = readScaleChoice();
		var w = Math.round(vs.cssW * choice.scale);
		var h = Math.round(vs.cssH * choice.scale);
		var el = document.getElementById('ocisExportSizePreview');
		if (el) el.textContent = '输出约 ' + w + ' × ' + h + ' px（视图 ' + Math.round(vs.cssW) + ' × ' + Math.round(vs.cssH) + '）';
	}

	function showPanel(anchor) {
		var panel = ensurePanel();
		var scale = savedScale();
		var radios = panel.querySelectorAll('input[name="ocisExportScale"]');
		var matched = false;
		for (var i = 0; i < radios.length; ++i) {
			var r = radios[i];
			if (r.value === 'custom') continue;
			if (Math.abs(Number(r.value) - scale) < 0.01) {
				r.checked = true;
				matched = true;
			}
		}
		if (!matched) {
			var custom = panel.querySelector('input[value="custom"]');
			if (custom) custom.checked = true;
			var vs = viewSize();
			var wIn = document.getElementById('ocisExportCustomW');
			if (wIn) wIn.value = String(Math.round(vs.cssW * scale));
		} else {
			var preset = panel.querySelector('input[name="ocisExportScale"]:checked');
			if (preset && preset.value !== 'custom') {
				var vs2 = viewSize();
				var wIn2 = document.getElementById('ocisExportCustomW');
				if (wIn2) wIn2.value = String(Math.round(vs2.cssW * Number(preset.value)));
			}
		}
		updateSizePreview();
		panel.classList.add('open');
		var rect = anchor && anchor.getBoundingClientRect ? anchor.getBoundingClientRect() : { left: 16, bottom: 48, right: 120 };
		var left = Math.min(window.innerWidth - 300, Math.max(8, rect.left));
		var top = rect.bottom + 8;
		if (top + 280 > window.innerHeight) top = Math.max(8, rect.top - 280);
		panel.style.left = left + 'px';
		panel.style.top = top + 'px';
	}

	function hidePanel() {
		var panel = document.getElementById(PANEL_ID);
		if (panel) panel.classList.remove('open');
	}

	function setBusy(btn, on, text) {
		if (!btn) return;
		btn.disabled = !!on;
		var span = btn.querySelector('.ocis-export-label');
		if (span && text != null) span.textContent = text;
	}

	function canvasLooksBlank(c) {
		if (!c || !(c.width > 2) || !(c.height > 2)) return true;
		try {
			var probe = document.createElement('canvas');
			probe.width = 16;
			probe.height = 16;
			var pctx = probe.getContext('2d');
			pctx.drawImage(c, 0, 0, c.width, c.height, 0, 0, 16, 16);
			var data = pctx.getImageData(0, 0, 16, 16).data;
			var nonzero = 0;
			for (var i = 0; i < data.length; i += 4) {
				if (data[i + 3] > 8 && (data[i] > 2 || data[i + 1] > 2 || data[i + 2] > 2)) nonzero += 1;
			}
			return nonzero < 3;
		} catch (e) {
			return false;
		}
	}

	function drawLayer(ctx, src, dw, dh) {
		if (!src) return false;
		var sw = src.width || 0;
		var sh = src.height || 0;
		if (!(sw > 1) || !(sh > 1)) return false;
		try {
			ctx.drawImage(src, 0, 0, sw, sh, 0, 0, dw, dh);
			return true;
		} catch (e) {
			return false;
		}
	}

	async function drawLayerAsync(ctx, src, dw, dh) {
		if (!src) return false;
		if (drawLayer(ctx, src, dw, dh) && !canvasLooksBlank(src)) return true;
		try {
			if (typeof createImageBitmap === 'function') {
				var bmp = await createImageBitmap(src);
				ctx.drawImage(bmp, 0, 0, bmp.width, bmp.height, 0, 0, dw, dh);
				if (bmp.close) bmp.close();
				return true;
			}
		} catch (e) { /* continue */ }
		return drawLayer(ctx, src, dw, dh);
	}

	function restorePixelRatio(g, oldPR) {
		if (!g || !g.renderer || oldPR == null) return;
		g.renderer.pixelRatio = oldPR;
		if (typeof g.renderer.resizeCanvas === 'function') g.renderer.resizeCanvas();
		else if (typeof g.resize === 'function') g.resize();
		if (window.TopoLive && typeof window.TopoLive.resizeOverlay === 'function') {
			window.TopoLive.resizeOverlay();
		}
	}

	async function boostPixelRatio(g, scale) {
		if (!g || !g.renderer) return null;
		var oldPR = g.renderer.pixelRatio || window.devicePixelRatio || 1;
		g.renderer.pixelRatio = scale;
		if (typeof g.renderer.resizeCanvas === 'function') g.renderer.resizeCanvas();
		else if (typeof g.resize === 'function') g.resize();
		if (window.TopoLive && typeof window.TopoLive.resizeOverlay === 'function') {
			window.TopoLive.resizeOverlay();
		}
		await waitFrames(3);
		return oldPR;
	}

	async function compositeLive(g, scale) {
		var canvas = graphCanvas();
		if (!canvas) throw new Error('找不到拓扑画布');
		var cssW = canvas.clientWidth || canvas.width;
		var cssH = canvas.clientHeight || canvas.height;
		if (!(cssW > 8) || !(cssH > 8)) throw new Error('画布尺寸无效');
		scale = clampScale(scale, cssW, cssH);

		var oldPR = await boostPixelRatio(g, scale);
		try {
			var outW = Math.round(cssW * scale);
			var outH = Math.round(cssH * scale);
			outW = Math.min(MAX_EDGE, Math.max(1, outW));
			outH = Math.min(MAX_EDGE, Math.max(1, outH));

			var out = document.createElement('canvas');
			out.width = outW;
			out.height = outH;
			var ctx = out.getContext('2d');
			var bg = backgroundCss();
			ctx.fillStyle = bg.css;
			ctx.fillRect(0, 0, outW, outH);
			ctx.imageSmoothingEnabled = true;
			ctx.imageSmoothingQuality = 'high';

			var gpuOk = await drawLayerAsync(ctx, canvas, outW, outH);
			if (!gpuOk || canvasLooksBlank(out)) {
				// One more frame then retry GPU layer only
				await waitFrames(2);
				ctx.fillStyle = bg.css;
				ctx.fillRect(0, 0, outW, outH);
				gpuOk = await drawLayerAsync(ctx, canvas, outW, outH);
			}
			if (!gpuOk) throw new Error('无法读取 WebGPU 画布，请用 Chrome/Edge 并确认拓扑已显示');

			var labels = labelCanvas(g);
			await drawLayerAsync(ctx, labels, outW, outH);

			var live = liveOverlayCanvas();
			await drawLayerAsync(ctx, live, outW, outH);

			return out;
		} finally {
			restorePixelRatio(g, oldPR);
			await waitFrames(1);
		}
	}

	function exportFrom2dCanvas(src, scale) {
		var cssW = src.clientWidth || src.width;
		var cssH = src.clientHeight || src.height;
		if (!(cssW > 1) || !(cssH > 1)) throw new Error('画布为空');
		scale = clampScale(scale, cssW, cssH);
		var out = document.createElement('canvas');
		out.width = Math.round(cssW * scale);
		out.height = Math.round(cssH * scale);
		var ctx = out.getContext('2d');
		ctx.imageSmoothingEnabled = true;
		ctx.imageSmoothingQuality = 'high';
		var bg = backgroundCss();
		ctx.fillStyle = bg.css;
		ctx.fillRect(0, 0, out.width, out.height);
		ctx.drawImage(src, 0, 0, src.width, src.height, 0, 0, out.width, out.height);
		return out;
	}

	async function runExport(scale, label) {
		var btn = document.getElementById('ocisExportPng');
		setBusy(btn, true, '导出中');
		var out;
		try {
			var fbOn = document.getElementById('fallback') && document.getElementById('fallback').classList.contains('fallback-2d-on');
			var fb = fallbackCanvas();
			var g = window.g;
			if (fbOn && fb && fb.width > 1 && window.getComputedStyle(fb).display !== 'none') {
				out = exportFrom2dCanvas(fb, scale);
			} else if (g && g.getGraph && graphCanvas()) {
				out = await compositeLive(g, scale);
			} else if (fb && fb.width > 1 && window.getComputedStyle(fb).display !== 'none') {
				out = exportFrom2dCanvas(fb, scale);
			} else {
				throw new Error('图尚未加载');
			}
		} catch (err) {
			setBusy(btn, false, '截图');
			window.alert('截图失败：' + (err && err.message ? err.message : err));
			return;
		}
		var name = 'topo-' + caseName().replace(/[\\/:*?"<>|]+/g, '_') + '-' + (label || '') + '-' + Date.now() + '.png';
		out.toBlob(function (blob) {
			setBusy(btn, false, '截图');
			if (!blob) {
				window.alert('截图失败：无法生成 PNG');
				return;
			}
			downloadBlob(blob, name);
		}, 'image/png');
	}

	document.addEventListener('click', function (ev) {
		var t = ev.target;
		if (!t || !t.closest) return;
		var panel = document.getElementById(PANEL_ID);
		if (panel && panel.classList.contains('open') && !t.closest('#' + PANEL_ID) && !t.closest('#ocisExportPng')) {
			hidePanel();
			return;
		}
		if (!t.closest('#ocisExportPng')) return;
		ev.preventDefault();
		ev.stopPropagation();
		showPanel(t.closest('#ocisExportPng'));
	});
})();
