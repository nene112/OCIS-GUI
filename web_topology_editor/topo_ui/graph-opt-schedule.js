/**
 * 调度计算（优化调度）面板 —— 拓扑页版本。
 *
 * 与 3D 界面工具栏的「优化调度」(js/nvOptMilp.js) 同一套后端：
 *   GET  /api/opt-milp/algorithms?case=   案例 / 算法 / 时段 / 需求 / 可预览文件
 *   POST /api/opt-milp/run                 提交计算（mac-win Node 扩展）
 *   GET  /api/opt-milp/job?id=             轮询进度与求解摘要
 *   GET  /api/opt-milp/params?case=        input.json 全局项 + 闸门表
 *   PUT  /api/opt-milp/params              写回案例
 *   GET  /api/schedule-plan?case=&file=    结果 / 需求的热图数据
 *
 * 拓扑页没有 jQuery / jQuery UI，所以对话框、表单、热图全部用原生 DOM + canvas 重写；
 * 案例默认取当前 ?data=，与 3D 的「当前工程」一致。
 */
(function ocisOptSchedule() {
	'use strict';

	var MASK_ID = 'ocisOptMask';
	var PREVIEW_ID = 'ocisOptPreviewMask';

	var RELAX_LABELS = {
		min_open_delivery_ratio: '最小开启供水比',
		W_task_gap_completion_floor: '任务完成量下限',
		max_delivery_duration_factor: '最大供水历时系数',
		max_flow_steps: '最大流量档位',
		turnout_max_flow_steps: '分水口最大流量档位'
	};

	var RELAX_META_FLAGS = [
		{ key: 'minimum_open_fallback_used', constraint: 'min_open_delivery_ratio', from: 'enforced', to: 'relaxed' },
		{ key: 'completion_floor_fallback_used', constraint: 'W_task_gap_completion_floor', from: 'enforced', to: 'disabled' },
		{ key: 'flow_step_fallback_used', constraint: 'max_flow_steps', from: 'enforced', to: 'relaxed' },
		{ key: 'duration_cap_fallback_used', constraint: 'max_delivery_duration_factor', from: 'enforced', to: 'relaxed' }
	];

	var st = {
		built: false,
		open: false,
		tab: 'calc',
		paramsTab: 'calc',
		busy: false,
		loadingMeta: false,
		userPickedAlgo: false,
		defaults: { start_time: '', T: '', step_dt: '', demandFile: '' },
		lastFile: '',
		lastCase: '',
		lastOutputs: [],
		lastResult: null,
		timer: 0,
		params: { file: 'input.json', schema: null, gates: [], gateSchema: [], loaded: false },
		preview: null,
		refs: Object.create(null)
	};

	/* ------------------------------------------------------------------ utils */

	function $(id) {
		return document.getElementById(id);
	}

	function clamp(v, lo, hi) {
		return Math.max(lo, Math.min(hi, v));
	}

	function escapeHtml(s) {
		return String(s == null ? '' : s)
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;')
			.replace(/"/g, '&quot;');
	}

	function trim(v) {
		return String(v == null ? '' : v).trim();
	}

	function num(v) {
		var n = Number(v);
		return isFinite(n) ? n : NaN;
	}

	function sameNum(a, b) {
		var x = Number(a);
		var y = Number(b);
		return isFinite(x) && isFinite(y) && x === y;
	}

	function normTimeText(s) {
		return trim(s).replace(/T/g, ' ').replace(/\s+/g, ' ');
	}

	function caseFromUrl() {
		try {
			return trim(new URLSearchParams(window.location.search).get('data'));
		} catch (e) {
			return '';
		}
	}

	function currentCase() {
		return caseFromUrl() || trim(window.__ocisCurrentCaseName) || trim(window.NVCurrentCaseName);
	}

	function jsonFetch(url, opts) {
		return fetch(url, opts || {}).then(function (res) {
			return res.text().then(function (text) {
				var body = null;
				if (text) {
					try {
						body = JSON.parse(text);
					} catch (e) {
						throw new Error((text.replace(/\s+/g, ' ') || ('HTTP ' + res.status)).slice(0, 220));
					}
				}
				return { res: res, body: body || {} };
			});
		});
	}

	function setStatus(text, kind) {
		var el = st.refs.status;
		if (!el) return;
		el.textContent = text || '';
		el.className = 'ocis-opt-status' + (kind ? ' is-' + kind : '');
	}

	function setMeta(text) {
		var el = st.refs.meta;
		if (el) el.textContent = text || '';
	}

	/* ---------------------------------------------------------- toolbar button */

	function ensureButton() {
		var bar = document.querySelector('.toolbar');
		if (!bar) return;
		var btn = $('ocisOptScheduleBtn');
		if (!btn) {
			btn = document.createElement('button');
			btn.type = 'button';
			btn.id = 'ocisOptScheduleBtn';
			btn.className = 'btn ocis-opt-trigger';
			btn.title = '优化调度计算（与 3D 界面同一套 /api/opt-milp）';
			btn.innerHTML = '<i class="ph-cpu-bold"></i> <span>调度计算</span>';
		}
		if (btn.parentElement === bar) return;
		var anchor = $('ocisExportPng');
		if (anchor && anchor.parentElement === bar) anchor.insertAdjacentElement('afterend', btn);
		else bar.appendChild(btn);
	}

	function watchToolbar() {
		ensureButton();
		var bar = document.querySelector('.toolbar');
		if (!bar || typeof MutationObserver !== 'function') return;
		var mo = new MutationObserver(function () {
			if (!$('ocisOptScheduleBtn')) ensureButton();
		});
		mo.observe(bar, { childList: true });
	}

	/* ------------------------------------------------------------------- dom */

	function buildDom() {
		if (st.built) return;

		var mask = document.createElement('div');
		mask.id = MASK_ID;
		mask.className = 'ocis-opt-mask';
		mask.innerHTML = '' +
			'<div class="ocis-opt-panel" role="dialog" aria-modal="true" aria-label="调度计算">' +
			'<span class="ocis-opt-top"></span>' +
			'<div class="ocis-opt-head">' +
			'<span class="ocis-opt-dot"></span>' +
			'<div class="ocis-opt-heading">' +
			'<div class="ocis-opt-title">调度计算</div>' +
			'<div class="ocis-opt-meta" id="ocisOptMeta">未加载案例</div>' +
			'</div>' +
			'<div class="ocis-opt-tabs" role="tablist">' +
			'<button type="button" data-tab="calc" class="is-active">计算</button>' +
			'<button type="button" data-tab="params">参数配置</button>' +
			'</div>' +
			'<button type="button" class="ocis-opt-x" id="ocisOptClose" aria-label="关闭">✕</button>' +
			'</div>' +
			'<div class="ocis-opt-body">' +
			'<div class="ocis-opt-pane" data-pane="calc">' +
			'<div class="ocis-opt-grid">' +
			'<label class="ocis-opt-field is-wide"><span>案例</span><select id="ocisOptCase"></select></label>' +
			'<label class="ocis-opt-field"><span>开始时间</span>' +
			'<input id="ocisOptStart" type="text" placeholder="YYYY-MM-DD HH:mm" autocomplete="off" spellcheck="false"></label>' +
			'<label class="ocis-opt-field"><span>时长 T（小时）</span><input id="ocisOptDuration" type="number" min="1" step="1"></label>' +
			'<label class="ocis-opt-field"><span>步长 step_dt（秒）</span><input id="ocisOptStepDt" type="number" min="1" step="1"></label>' +
			'<label class="ocis-opt-field is-wide"><span>需求文件</span><select id="ocisOptDemand"></select></label>' +
			'<label class="ocis-opt-field is-wide"><span>算法</span><select id="ocisOptAlgo"></select></label>' +
			'</div>' +
			'<div class="ocis-opt-actions">' +
			'<button type="button" class="ocis-opt-btn" id="ocisOptPreviewDemand">预览需求</button>' +
			'<span class="ocis-opt-hint" id="ocisOptHint">未修改时段/需求时按案例文件计算，与本地 SLN 一致</span>' +
			'</div>' +
			'<div class="ocis-opt-result" id="ocisOptResultBox" hidden>' +
			'<div class="ocis-opt-result-head">' +
			'<span class="ocis-opt-optimal" id="ocisOptOptimal"></span>' +
			'<button type="button" class="ocis-opt-btn is-mini" id="ocisOptRelaxBtn">放松约束</button>' +
			'</div>' +
			'<div class="ocis-opt-result-row">' +
			'<select id="ocisOptResultFile"></select>' +
			'<button type="button" class="ocis-opt-btn" id="ocisOptPreview">预览结果</button>' +
			'</div>' +
			'</div>' +
			'</div>' +
			'<div class="ocis-opt-pane" data-pane="params" hidden>' +
			'<div class="ocis-opt-subtabs">' +
			'<button type="button" data-ptab="calc" class="is-active">全局</button>' +
			'<button type="button" data-ptab="gates">闸门</button>' +
			'<button type="button" class="ocis-opt-btn is-mini" id="ocisOptParamsReload">重新加载</button>' +
			'<button type="button" class="ocis-opt-btn is-mini is-primary" id="ocisOptParamsSave">保存到案例</button>' +
			'</div>' +
			'<div class="ocis-opt-params-pane" id="ocisOptParamsCalc"></div>' +
			'<div class="ocis-opt-params-pane" id="ocisOptParamsGates" hidden>' +
			'<input type="search" id="ocisOptParamsFilter" placeholder="筛选闸门名称" autocomplete="off">' +
			'<div class="ocis-opt-gate-wrap" id="ocisOptGateWrap"></div>' +
			'</div>' +
			'<div class="ocis-opt-status is-flat" id="ocisOptParamsStatus"></div>' +
			'</div>' +
			'</div>' +
			'<div class="ocis-opt-foot">' +
			'<span class="ocis-opt-status" id="ocisOptStatus">未计算</span>' +
			'<span class="ocis-opt-grow"></span>' +
			'<button type="button" class="ocis-opt-btn is-primary" id="ocisOptRun">开始计算</button>' +
			'</div>' +
			'</div>';

		var preview = document.createElement('div');
		preview.id = PREVIEW_ID;
		preview.className = 'ocis-opt-mask is-preview';
		preview.innerHTML = '' +
			'<div class="ocis-opt-panel is-preview" role="dialog" aria-modal="true" aria-label="调度预览">' +
			'<span class="ocis-opt-top"></span>' +
			'<div class="ocis-opt-head">' +
			'<span class="ocis-opt-dot"></span>' +
			'<div class="ocis-opt-heading">' +
			'<div class="ocis-opt-title" id="ocisOptPreviewTitle">调度预览</div>' +
			'<div class="ocis-opt-meta" id="ocisOptPreviewMeta"></div>' +
			'</div>' +
			'<button type="button" class="ocis-opt-x" id="ocisOptPreviewClose" aria-label="关闭">✕</button>' +
			'</div>' +
			'<div class="ocis-opt-body is-preview">' +
			'<div class="ocis-opt-heat-wrap" id="ocisOptHeatWrap"><canvas id="ocisOptHeat"></canvas></div>' +
			'<div class="ocis-opt-legend"><span>低</span><i class="ocis-opt-ramp"></i><span>高</span>' +
			'<em id="ocisOptLegendNote"></em></div>' +
			'</div>' +
			'</div>';

		document.body.appendChild(mask);
		document.body.appendChild(preview);

		var r = st.refs;
		r.mask = mask;
		r.panel = mask.querySelector('.ocis-opt-panel');
		r.meta = $('ocisOptMeta');
		r.case = $('ocisOptCase');
		r.start = $('ocisOptStart');
		r.duration = $('ocisOptDuration');
		r.stepDt = $('ocisOptStepDt');
		r.demand = $('ocisOptDemand');
		r.algo = $('ocisOptAlgo');
		r.hint = $('ocisOptHint');
		r.status = $('ocisOptStatus');
		r.run = $('ocisOptRun');
		r.resultBox = $('ocisOptResultBox');
		r.optimal = $('ocisOptOptimal');
		r.relaxBtn = $('ocisOptRelaxBtn');
		r.resultFile = $('ocisOptResultFile');
		r.previewBtn = $('ocisOptPreview');
		r.demandPreviewBtn = $('ocisOptPreviewDemand');
		r.paramsCalc = $('ocisOptParamsCalc');
		r.paramsGates = $('ocisOptParamsGates');
		r.gateWrap = $('ocisOptGateWrap');
		r.paramsFilter = $('ocisOptParamsFilter');
		r.paramsStatus = $('ocisOptParamsStatus');
		r.paramsSave = $('ocisOptParamsSave');
		r.paramsReload = $('ocisOptParamsReload');
		r.foot = mask.querySelector('.ocis-opt-foot');

		r.previewMask = preview;
		r.previewTitle = $('ocisOptPreviewTitle');
		r.previewMeta = $('ocisOptPreviewMeta');
		r.heatWrap = $('ocisOptHeatWrap');
		r.heat = $('ocisOptHeat');
		r.legendNote = $('ocisOptLegendNote');

		wire();
		st.built = true;
	}

	function wire() {
		var r = st.refs;

		r.run.addEventListener('click', runSolve);
		r.previewBtn.addEventListener('click', previewResult);
		r.demandPreviewBtn.addEventListener('click', previewDemand);
		r.relaxBtn.addEventListener('click', showRelaxations);
		r.paramsReload.addEventListener('click', loadParams);
		r.paramsSave.addEventListener('click', saveParams);
		$('ocisOptClose').addEventListener('click', close);
		$('ocisOptPreviewClose').addEventListener('click', closePreview);

		r.mask.addEventListener('click', function (ev) {
			if (ev.target === r.mask) close();
		});
		r.previewMask.addEventListener('click', function (ev) {
			if (ev.target === r.previewMask) closePreview();
		});

		Array.prototype.forEach.call(r.mask.querySelectorAll('.ocis-opt-tabs button'), function (b) {
			b.addEventListener('click', function () {
				showTab(b.getAttribute('data-tab'));
			});
		});
		Array.prototype.forEach.call(r.mask.querySelectorAll('.ocis-opt-subtabs [data-ptab]'), function (b) {
			b.addEventListener('click', function () {
				showParamsTab(b.getAttribute('data-ptab'));
			});
		});

		r.case.addEventListener('change', function () {
			if (st.loadingMeta) return;
			loadMeta({ keepCase: true });
		});
		r.algo.addEventListener('change', function () {
			st.userPickedAlgo = true;
		});
		r.resultFile.addEventListener('change', function () {
			st.lastFile = trim(r.resultFile.value);
			r.previewBtn.disabled = !st.lastFile;
		});
		r.demand.addEventListener('change', function () {
			r.demandPreviewBtn.disabled = !trim(r.demand.value);
		});
		r.paramsFilter.addEventListener('input', function () {
			snapshotGateEdits();
			renderGateTable(st.params.gateSchema, st.params.gates);
		});
		[r.start, r.duration, r.stepDt].forEach(function (el) {
			el.addEventListener('input', refreshHint);
		});

		window.addEventListener('keydown', function (ev) {
			if (ev.key !== 'Escape') return;
			if (r.previewMask.classList.contains('is-open')) closePreview();
			else if (st.open) close();
		});
		window.addEventListener('resize', function () {
			if (r.previewMask.classList.contains('is-open')) drawHeatmap();
		});
	}

	/* --------------------------------------------------------------- open/close */

	function open() {
		buildDom();
		st.open = true;
		refreshHint();
		showTab('calc');
		st.refs.mask.classList.add('is-open');
		loadMeta({ keepCase: !!currentCase() });
	}

	function close() {
		if (!st.built) return;
		st.open = false;
		st.refs.mask.classList.remove('is-open');
	}

	function showTab(which) {
		st.tab = which === 'params' ? 'params' : 'calc';
		Array.prototype.forEach.call(st.refs.mask.querySelectorAll('.ocis-opt-tabs button'), function (b) {
			b.classList.toggle('is-active', b.getAttribute('data-tab') === st.tab);
		});
		Array.prototype.forEach.call(st.refs.mask.querySelectorAll('.ocis-opt-pane'), function (p) {
			p.hidden = p.getAttribute('data-pane') !== st.tab;
		});
		st.refs.foot.hidden = st.tab === 'params';
		if (st.tab === 'params' && !st.params.loaded) loadParams();
	}

	function showParamsTab(which) {
		st.paramsTab = which === 'gates' ? 'gates' : 'calc';
		Array.prototype.forEach.call(st.refs.mask.querySelectorAll('.ocis-opt-subtabs [data-ptab]'), function (b) {
			b.classList.toggle('is-active', b.getAttribute('data-ptab') === st.paramsTab);
		});
		st.refs.paramsCalc.hidden = st.paramsTab !== 'calc';
		st.refs.paramsGates.hidden = st.paramsTab !== 'gates';
	}

	/* ------------------------------------------------------------- form state */

	function selectedCase() {
		var fromSel = st.refs.case ? trim(st.refs.case.value) : '';
		return fromSel || currentCase();
	}

	function selectedDemand() {
		return st.refs.demand ? trim(st.refs.demand.value) : '';
	}

	function selectedType() {
		var sel = st.refs.algo;
		if (!sel) return 8;
		var n = num(sel.value);
		return isFinite(n) ? n : 8;
	}

	function readTimeFields() {
		return {
			start_time: st.refs.start ? trim(st.refs.start.value) : '',
			T: st.refs.duration ? num(st.refs.duration.value) : NaN,
			step_dt: st.refs.stepDt ? num(st.refs.stepDt.value) : NaN
		};
	}

	function timeMatchesCase() {
		var t = readTimeFields();
		return normTimeText(t.start_time) === normTimeText(st.defaults.start_time)
			&& sameNum(t.T, st.defaults.T)
			&& sameNum(t.step_dt, st.defaults.step_dt);
	}

	function demandMatchesCase() {
		var rel = selectedDemand();
		var def = trim(st.defaults.demandFile).replace(/^\/+/, '');
		return !!rel && rel === def;
	}

	function refreshHint() {
		if (!st.refs.hint) return;
		var t = readTimeFields();
		var over = !timeMatchesCase();
		var dOver = !!selectedDemand() && !demandMatchesCase();
		var bits = [];
		if (over) bits.push('时段将被覆盖');
		if (dOver) bits.push('需求将被覆盖');
		st.refs.hint.textContent = bits.length
			? ('提交时按面板参数覆盖案例：' + bits.join(' / '))
			: '未修改时段/需求时按案例文件计算，与本地 SLN 一致';
		st.refs.hint.className = 'ocis-opt-hint' + (bits.length ? ' is-override' : '');
		void t;
	}

	function setBusy(running) {
		st.busy = !!running;
		var r = st.refs;
		if (!r.run) return;
		r.run.disabled = st.busy;
		r.run.textContent = st.busy ? '计算中…' : '开始计算';
		if (r.case) r.case.disabled = st.busy;
		if (r.previewBtn) r.previewBtn.disabled = st.busy || !trim(r.resultFile.value);
		if (r.demandPreviewBtn) r.demandPreviewBtn.disabled = st.busy || !selectedDemand();
		if (r.paramsSave) r.paramsSave.disabled = st.busy;
		r.mask.classList.toggle('is-busy', st.busy);
	}

	/* -------------------------------------------------------------- meta load */

	function fillCases(list, preferred) {
		var sel = st.refs.case;
		if (!sel) return;
		var names = [];
		var seen = Object.create(null);
		(list || []).forEach(function (c) {
			var name = trim(c && (c.name || c.path));
			if (!name || seen[name]) return;
			seen[name] = true;
			names.push(name);
		});
		var want = trim(preferred);
		if (want && !seen[want]) names.unshift(want);
		sel.innerHTML = '';
		if (!names.length) {
			sel.appendChild(new Option('（未找到案例）', ''));
			return;
		}
		names.forEach(function (name) {
			sel.appendChild(new Option(name, name));
		});
		if (want && seen[want]) sel.value = want;
		else sel.selectedIndex = 0;
	}

	function fillAlgos(list) {
		var sel = st.refs.algo;
		if (!sel) return;
		var prev = sel.value;
		sel.innerHTML = '';
		(list || []).forEach(function (a) {
			var opt = document.createElement('option');
			opt.value = String(a.type);
			opt.textContent = a.name + '  (solver_type=' + a.type + ') ' + (a.runnable ? '' : '· 不可用');
			opt.disabled = !a.runnable;
			if (a.reason) opt.title = a.reason;
			sel.appendChild(opt);
		});
		if (st.userPickedAlgo && prev && sel.querySelector('option[value="' + prev + '"]')) sel.value = prev;
		else if (sel.querySelector('option[value="8"]')) sel.value = '8';
		else if (sel.querySelector('option[value="7"]')) sel.value = '7';
	}

	/**
	 * 需求文件只看 input/ 下的 csv。案例的 HDCM.boundary_flow_path 本来就在 input/，
	 * 顺带把 output/、opt_milp/ 那些结果文件挡在外面。
	 */
	function inputCsvFiles(files, preferred) {
		var out = [];
		var seen = Object.create(null);
		(files || []).forEach(function (f) {
			var rel = trim(f && f.rel);
			if (!rel || seen[rel]) return;
			if (!/\.csv$/i.test(rel)) return;
			if (rel.indexOf('input/') !== 0) return;
			seen[rel] = true;
			out.push(f);
		});
		// demand 相关文件排前面，其余 input csv 次之
		out.sort(function (a, b) {
			var score = function (f) {
				var rel = trim(f.rel).toLowerCase();
				var s = 0;
				if (/waterdemand|demand|需水/.test(rel)) s -= 2;
				if (/^input\/.*obs/.test(rel)) s -= 1;
				return s;
			};
			return score(a) - score(b);
		});
		var want = trim(preferred);
		if (want && !seen[want] && /\.csv$/i.test(want)) out.unshift({ rel: want, bytes: null });
		return out;
	}

	function fillDemand(files, preferred) {
		var sel = st.refs.demand;
		if (!sel) return;
		var prev = trim(preferred) || trim(sel.value);
		sel.innerHTML = '';
		var rows = inputCsvFiles(files, prev);
		if (!rows.length) {
			sel.appendChild(new Option('（案例 input/ 下未找到 csv）', ''));
			if (st.refs.demandPreviewBtn) st.refs.demandPreviewBtn.disabled = true;
			return;
		}
		rows.forEach(function (f) {
			var rel = trim(f && f.rel);
			var label = rel.replace(/^input\//, '') +
				(f.bytes != null ? ('  (' + Math.max(1, Math.round(f.bytes / 1024)) + ' KB)') : '');
			sel.appendChild(new Option(label, rel));
		});
		if (prev && sel.querySelector('option[value="' + prev + '"]')) sel.value = prev;
		if (st.refs.demandPreviewBtn) st.refs.demandPreviewBtn.disabled = !sel.value;
	}

	function fillTime(time) {
		var src = time && !time.error ? time : null;
		st.defaults.start_time = src && src.start_time ? String(src.start_time) : '';
		st.defaults.T = src && src.T != null && isFinite(Number(src.T)) ? String(src.T) : '';
		st.defaults.step_dt = '';
		if (src) {
			var dt0 = src.step_dt != null ? src.step_dt : src.MILP_dt;
			if (dt0 != null && isFinite(Number(dt0))) st.defaults.step_dt = String(dt0);
		}
		st.refs.start.value = st.defaults.start_time;
		st.refs.duration.value = st.defaults.T;
		st.refs.stepDt.value = st.defaults.step_dt;
		refreshHint();
	}

	function loadMeta(opts) {
		buildDom();
		var keepCase = !!(opts && opts.keepCase);
		var name = keepCase ? selectedCase() : currentCase();
		st.loadingMeta = true;
		var url = '/api/opt-milp/algorithms' + (name ? '?case=' + encodeURIComponent(name) : '');
		jsonFetch(url)
			.then(function (pack) {
				var data = pack.body || {};
				if (!pack.res.ok || data.error) throw new Error(data.error || ('HTTP ' + pack.res.status));
				fillCases(data.cases || [], name);
				fillAlgos(data.algorithms || []);
				fillTime(data.time);
				st.defaults.demandFile = trim(data.demand && data.demand.file).replace(/^\/+/, '');
				fillDemand(data.files || [], st.defaults.demandFile);

				var bits = [];
				if (data.casePath) bits.push(data.casePath);
				if (data.model) bits.push('模型 ' + data.model);
				if (data.demand && data.demand.file) {
					bits.push((data.demand.model || 'HDCM') + ' 需求 ' + data.demand.file +
						(data.demand.exists ? '' : '（缺失）'));
				}
				if (data.addon && data.addon.loaded) bits.push('mac-win Node 已加载');
				else if (data.addon && data.addon.error) bits.push(data.addon.error);
				if (data.configError) bits.push(data.configError);
				if (data.time && data.time.error) bits.push(data.time.error);
				if (data.demand && data.demand.error) bits.push(data.demand.error);
				setMeta(bits.join(' · ') || '案例：data/' + name);

				if (data.job && data.job.status === 'running') {
					st.lastFile = data.job.file || st.lastFile;
					st.lastCase = data.job.case || st.lastCase;
					setBusy(true);
					pollJob(data.job.id);
					setStatus('计算中… solver_type=' + data.job.solverType, 'live');
				} else if (data.job && data.job.status === 'done' && data.job.case === name) {
					applyDoneJob(data.job);
					setStatus(describeJob(data.job), 'done');
				} else if (data.lastResult && data.lastResult.result) {
					applyDoneJob({
						case: name,
						file: data.lastResult.file,
						outputs: data.lastResult.outputs || [],
						result: data.lastResult.result
					});
					setStatus('上次结果 · solver_type=' + data.lastResult.solverType +
						(data.lastResult.result.optimal ? ' · 最优解' : ' · 非最优解'), 'done');
				} else {
					fillResultFiles(st.lastOutputs, st.lastFile);
				}
				st.params.loaded = false;
			})
			.catch(function (err) {
				setMeta('');
				setStatus('读取案例失败：' + (err && err.message ? err.message : err), 'error');
			})
			.then(function () {
				st.loadingMeta = false;
			});
	}

	/* ------------------------------------------------------------- run / poll */

	function describeJob(job) {
		if (!job) return '';
		if (job.status === 'running') return '计算中… solver_type=' + job.solverType;
		if (job.status === 'error') return '失败：' + (job.error || '未知错误');
		if (job.status === 'done') {
			var bits = ['完成'];
			if (job.applyTimeOverride || job.applyDemandOverride) bits.push('已覆盖案例参数');
			else bits.push('按案例文件');
			if (job.result) bits.push(job.result.optimal ? '最优解' : '非最优解');
			if (job.file) bits.push(job.file);
			return bits.join(' · ');
		}
		return job.status || '';
	}

	function stopPoll() {
		if (st.timer) {
			clearInterval(st.timer);
			st.timer = 0;
		}
	}

	function pollJob(id) {
		stopPoll();
		st.timer = setInterval(function () {
			jsonFetch('/api/opt-milp/job?id=' + encodeURIComponent(id))
				.then(function (pack) {
					var job = pack.body && pack.body.job;
					if (!job) return;
					setStatus(describeJob(job), 'live');
					if (job.status === 'done' || job.status === 'error') {
						stopPoll();
						setBusy(false);
						if (job.status === 'done') {
							applyDoneJob(job);
							setStatus(describeJob(job), 'done');
						} else {
							setStatus(describeJob(job), 'error');
						}
					}
				})
				.catch(function () { /* keep polling */ });
		}, 1500);
	}

	function runSolve() {
		var name = selectedCase();
		if (!name) {
			setStatus('请先选择案例', 'error');
			return;
		}
		var time = readTimeFields();
		if (!time.start_time) {
			setStatus('请填写开始时间', 'error');
			st.refs.start.focus();
			return;
		}
		if (!isFinite(time.T) || time.T <= 0) {
			setStatus('请填写有效的时长 T（小时）', 'error');
			st.refs.duration.focus();
			return;
		}
		if (!isFinite(time.step_dt) || time.step_dt <= 0) {
			setStatus('请填写有效的步长 step_dt（秒）', 'error');
			st.refs.stepDt.focus();
			return;
		}
		if (!selectedDemand()) {
			setStatus('请选择需求文件', 'error');
			return;
		}

		var payload = { case: name, solverType: selectedType() };
		if (!timeMatchesCase()) {
			payload.applyTimeOverride = true;
			payload.start_time = time.start_time;
			payload.T = Math.round(time.T);
			payload.step_dt = Math.round(time.step_dt);
		}
		if (!demandMatchesCase()) payload.demandFile = selectedDemand();

		setBusy(true);
		setStatus(payload.applyTimeOverride || payload.demandFile
			? '提交计算（已覆盖案例时段/需求）…'
			: '提交计算（按案例文件，与本地 SLN 相同）…', 'live');

		jsonFetch('/api/opt-milp/run', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(payload)
		})
			.then(function (pack) {
				var body = pack.body || {};
				if (!pack.res.ok || body.ok === false) throw new Error(body.error || ('HTTP ' + pack.res.status));
				var job = body.job || {};
				st.lastCase = job.case || name;
				setStatus(describeJob(job) || '已提交', 'live');
				if (job.id) pollJob(job.id);
				else setBusy(false);
			})
			.catch(function (err) {
				setBusy(false);
				setStatus('失败：' + (err && err.message ? err.message : err), 'error');
			});
	}

	/* ------------------------------------------------------------- result view */

	function resultFileMeta(rel) {
		var want = trim(rel);
		for (var i = 0; i < st.lastOutputs.length; ++i) {
			if (trim(st.lastOutputs[i].rel) === want) return st.lastOutputs[i];
		}
		return null;
	}

	function fillResultFiles(outputs, preferred) {
		var sel = st.refs.resultFile;
		if (!sel) return;
		st.lastOutputs = outputs || [];
		var prev = trim(preferred) || trim(sel.value) || st.lastFile;
		sel.innerHTML = '';
		if (!st.lastOutputs.length) {
			sel.appendChild(new Option('（计算完成后列出本次写出的文件）', ''));
			st.refs.previewBtn.disabled = true;
			return;
		}
		st.lastOutputs.forEach(function (o) {
			var rel = trim(o && o.rel);
			if (!rel) return;
			var label = (o.label ? o.label + ' · ' : '') + rel;
			if (o.preview === false) label += '（不可热图）';
			sel.appendChild(new Option(label, rel));
		});
		if (prev && sel.querySelector('option[value="' + prev + '"]')) sel.value = prev;
		else {
			for (var i = 0; i < st.lastOutputs.length; ++i) {
				if (st.lastOutputs[i].preview !== false && st.lastOutputs[i].kind === 'action_td') {
					sel.value = st.lastOutputs[i].rel;
					break;
				}
			}
		}
		// a non-previewable primary output (result_*.json) must not become the
		// selected preview target — fall back to the first heatmap-able CSV
		var chosen = resultFileMeta(sel.value);
		if (chosen && chosen.preview === false) {
			for (var j = 0; j < st.lastOutputs.length; ++j) {
				var cand = st.lastOutputs[j];
				if (cand && cand.preview !== false && trim(cand.rel)) {
					sel.value = cand.rel;
					break;
				}
			}
		}
		st.lastFile = sel.value || st.lastFile;
		st.refs.previewBtn.disabled = !st.lastFile;
	}

	function relaxationsOf(result) {
		if (!result) return [];
		var list = Array.isArray(result.relaxations) ? result.relaxations.slice() : [];
		if (list.length) return list;
		var meta = result.meta || {};
		RELAX_META_FLAGS.forEach(function (flag) {
			if (!(Number(meta[flag.key]) >= 0.5)) return;
			list.push({ constraint: flag.constraint, from: flag.from, to: flag.to, reason: flag.key });
		});
		return list.filter(function (ev) {
			return ev && ev.constraint && ev.constraint !== 'none';
		});
	}

	function constraintLabel(raw) {
		var name = trim(raw);
		var key = name.split(':')[0];
		var zh = RELAX_LABELS[key];
		if (zh && name.indexOf(':') > 0) return zh + '（' + name.slice(name.indexOf(':') + 1) + '）';
		return zh || name || '约束';
	}

	function applyDoneJob(job) {
		if (!job) return;
		st.lastCase = job.case || st.lastCase;
		st.lastResult = job.result || null;
		st.lastFile = job.file || st.lastFile;
		fillResultFiles(job.outputs || [], job.file);
		st.refs.resultBox.hidden = !st.lastResult;
		if (st.lastResult) {
			st.refs.optimal.textContent = st.lastResult.optimal ? '最优解' : '非最优解';
			st.refs.optimal.className = 'ocis-opt-optimal' +
				(st.lastResult.optimal ? ' is-optimal' : ' is-not-optimal');
			st.refs.optimal.title = st.lastResult.optimality_proven ? 'SCIP/LBBD 已证明最优' : '未证明全局最优';
			var n = relaxationsOf(st.lastResult).length;
			st.refs.relaxBtn.textContent = n ? ('放松约束（' + n + '）') : '放松约束';
			st.refs.relaxBtn.disabled = false;
		} else {
			st.refs.relaxBtn.disabled = true;
		}
	}

	function showRelaxations() {
		var r = st.refs;
		if (!st.lastResult) {
			setStatus('还没有求解摘要', 'error');
			return;
		}
		var list = relaxationsOf(st.lastResult);
		var html = '<div class="ocis-opt-relax">';
		html += '<p class="ocis-opt-hint">' + (st.lastResult.optimal
			? '已证明最优。下列约束在求解过程中被自动放松。'
			: '未证明全局最优。非最优解不等于发生过放松：时限到点仍有可行解时，列表可以为空。') + '</p>';
		if (!list.length) {
			html += '<p class="ocis-opt-hint is-empty">本次没有自动放松约束的记录。' +
				(st.lastResult.optimal ? '' : ' 常见原因是 SCIP/LBBD 达到时限时已有可行解，求解器没有改最小开启比、完成量下限等约束。') +
				'</p>';
		} else {
			html += '<table class="ocis-opt-table"><thead><tr><th>#</th><th>约束</th><th>原值</th><th>放松为</th><th>原因</th></tr></thead><tbody>';
			list.forEach(function (ev, i) {
				html += '<tr><td>' + (ev.sequence != null ? ev.sequence : (i + 1)) + '</td><td>' +
					escapeHtml(constraintLabel(ev.constraint)) + '</td><td>' + escapeHtml(ev.from) +
					'</td><td>' + escapeHtml(ev.to) + '</td><td>' + escapeHtml(ev.reason) + '</td></tr>';
			});
			html += '</tbody></table>';
		}
		html += '</div>';
		openInfoMask('求解摘要 · 放松约束', html);
	}

	/** Small generic info overlay reusing the preview shell. */
	function openInfoMask(title, html) {
		var mask = st.refs.previewMask;
		st.refs.previewTitle.textContent = title;
		st.refs.previewMeta.textContent = '';
		st.refs.heatWrap.innerHTML = html;
		mask.classList.add('is-open', 'is-info');
	}

	/* ---------------------------------------------------------------- preview */

	function previewResult() {
		var name = st.lastCase || selectedCase();
		var rel = trim(st.refs.resultFile.value) || st.lastFile;
		if (!rel) {
			setStatus('还没有可预览的结果', 'error');
			return;
		}
		var meta = resultFileMeta(rel);
		if (meta && meta.preview === false) {
			setStatus('该文件不是调度热图（' + rel + '），请改选 action_td / Q_td 等 CSV', 'error');
			return;
		}
		previewPlan(name, rel, '调度结果 · ' + rel);
	}

	function previewDemand() {
		var name = selectedCase();
		var rel = selectedDemand();
		if (!rel) {
			setStatus('没有可预览的需求文件', 'error');
			return;
		}
		previewPlan(name, rel, '需求预览 · data/' + name + ' / ' + rel);
	}

	/**
	 * Ask the server for the heatmap plan. Embedded inside the 3D page? hand the
	 * plan to the parent so its existing 调度热图对话框 opens instead.
	 */
	function previewPlan(name, rel, title) {
		if (!name || !rel) {
			setStatus('没有可预览的文件', 'error');
			return;
		}
		jsonFetch('/api/schedule-plan?case=' + encodeURIComponent(name) + '&file=' + encodeURIComponent(rel))
			.then(function (pack) {
				var plan = pack.body || {};
				if (!pack.res.ok || plan.error) throw new Error(plan.error || ('HTTP ' + pack.res.status));
				if (window.parent && window.parent !== window) {
					try {
						window.parent.postMessage({ type: 'optSchedule', action: 'preview', plan: plan, title: title }, '*');
						return;
					} catch (e) { /* fall through to the built-in viewer */ }
				}
				openPreview(plan, title);
			})
			.catch(function (err) {
				setStatus('预览失败：' + (err && err.message ? err.message : err), 'error');
			});
	}

	/** 每屏最多画多少列：超出的时间点按桶聚合，避免 1.4 万列的巨型 canvas 直接画空。 */
	var MAX_COLS = 288;
	var MAX_ROWS = 320;

	function planMatrix(plan) {
		var names = (plan && plan.columns) ? plan.columns.slice() : Object.keys((plan && plan.series) || {});
		var labels = (plan && plan.timeLabels) || [];
		var n = labels.length || ((plan && plan.times) ? plan.times.length : 0);
		var series = (plan && plan.series) || {};

		// 只保留真的有数值的对象，全空的行画出来只是灰色噪音
		var rows = [];
		names.forEach(function (name) {
			var vals = series[name];
			if (!vals) return;
			var has = false;
			for (var i = 0; i < vals.length; ++i) {
				var v = Number(vals[i]);
				if (isFinite(v)) {
					has = true;
					break;
				}
			}
			if (has) rows.push({ name: name, values: vals });
		});

		if (!n || !rows.length) return { rows: [], labels: [], n: 0, bucket: 1, dropped: 0 };

		var cols = Math.min(n, MAX_COLS);
		var bucket = n > MAX_COLS ? n / MAX_COLS : 1;
		var outLabels = [];
		for (var c = 0; c < cols; ++c) {
			var idx = Math.min(n - 1, Math.floor(c * bucket));
			outLabels.push(labels[idx] || ('t' + idx));
		}

		var dropped = Math.max(0, rows.length - MAX_ROWS);
		var slice = dropped ? rows.slice(0, MAX_ROWS) : rows;

		// 稀疏观测文件（如 waterdemand_td_obs.csv）每个对象只有少量时刻，
		// 直接抽样会几乎全空；按桶取非空均值，桶里完全没有值就留空。
		var matrix = slice.map(function (row) {
			var vals = row.values;
			var sum = new Float64Array(cols);
			var cnt = new Int32Array(cols);
			for (var i = 0; i < vals.length; ++i) {
				var v = Number(vals[i]);
				if (!isFinite(v)) continue;
				var b = Math.min(cols - 1, Math.floor(i / bucket));
				sum[b] += v;
				cnt[b] += 1;
			}
			var out = new Array(cols);
			var min = Infinity;
			var max = -Infinity;
			for (var j = 0; j < cols; ++j) {
				if (!cnt[j]) {
					out[j] = null;
					continue;
				}
				var avg = sum[j] / cnt[j];
				out[j] = avg;
				if (avg < min) min = avg;
				if (avg > max) max = avg;
			}
			return { name: row.name, values: out, min: min, max: max };
		});

		return {
			rows: matrix,
			labels: outLabels,
			n: cols,
			bucket: bucket,
			dropped: dropped,
			sourceTimes: n,
			sourceRows: rows.length
		};
	}

	function openPreview(plan, title) {
		st.preview = plan;
		var mask = st.refs.previewMask;
		st.refs.heatWrap.innerHTML = '<canvas id="ocisOptHeat"></canvas>';
		st.refs.heat = $('ocisOptHeat');
		st.refs.previewTitle.textContent = title || ('预览 · ' + (plan.rel || plan.file || ''));

		var m = planMatrix(plan);
		var bits = [];
		if (m.n) {
			bits.push(m.rows.length + ' 个对象 × ' + m.n + ' 个时段');
			if (m.bucket > 1) bits.push('原 ' + m.sourceTimes + ' 个时间点已分箱');
			if (m.dropped) bits.push('只画前 ' + m.rows.length + ' 个对象');
			if (m.labels.length) bits.push(m.labels[0] + ' → ' + m.labels[m.labels.length - 1]);
		}
		st.refs.previewMeta.textContent = bits.join(' · ');
		mask.classList.add('is-open');
		mask.classList.remove('is-info');
		st.refs.legendNote.textContent = m.rows.length
			? '色值按每个对象自身的最小/最大值归一化 · 空格表示该时段没有记录'
			: '该文件没有可绘制的数值';
		drawHeatmap();
	}

	function closePreview() {
		if (!st.built) return;
		st.refs.previewMask.classList.remove('is-open', 'is-info');
	}

	function ramp(t) {
		// blue → cyan → green → amber → red（低位提亮，避免大面积深蓝看不出差别）
		var stops = [
			[59, 130, 246],
			[34, 211, 238],
			[34, 197, 94],
			[250, 204, 21],
			[239, 68, 68]
		];
		var x = clamp(Math.pow(clamp(t, 0, 1), 0.75), 0, 0.9999) * (stops.length - 1);
		var i = Math.floor(x);
		var f = x - i;
		var a = stops[i];
		var b = stops[i + 1] || stops[i];
		return 'rgb(' + Math.round(a[0] + (b[0] - a[0]) * f) + ',' +
			Math.round(a[1] + (b[1] - a[1]) * f) + ',' +
			Math.round(a[2] + (b[2] - a[2]) * f) + ')';
	}

	function drawHeatmap() {
		var plan = st.preview;
		var cv = $('ocisOptHeat');
		if (!plan || !cv) return;
		var wrap = st.refs.heatWrap;
		var m = planMatrix(plan);
		var rows = m.rows;
		var nT = m.n;
		var labels = m.labels;

		if (!rows.length || !nT) {
			cv.width = 1;
			cv.height = 1;
			cv.style.width = '0px';
			cv.style.height = '0px';
			return;
		}

		var gutter = 132;
		var avail = Math.max(240, (wrap.clientWidth || 620) - 40 - gutter);
		var cellW = clamp(Math.floor(avail / nT), 4, 40);
		var cellH = rows.length > 160 ? 10 : (rows.length <= 48 ? 16 : 14);
		var headH = 18;
		var cssW = gutter + nT * cellW;
		var cssH = headH + rows.length * cellH;
		var dpr = Math.min(2, window.devicePixelRatio || 1);

		cv.width = Math.floor(cssW * dpr);
		cv.height = Math.floor(cssH * dpr);
		cv.style.width = cssW + 'px';
		cv.style.height = cssH + 'px';

		var ctx = cv.getContext('2d');
		ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
		ctx.clearRect(0, 0, cssW, cssH);

		var dark = document.body.classList.contains('dark');
		var labelColor = dark ? 'rgba(226,224,236,.82)' : 'rgba(40,40,52,.82)';
		var muteColor = dark ? 'rgba(180,178,196,.55)' : 'rgba(90,90,110,.6)';
		var gridColor = dark ? 'rgba(255,255,255,.05)' : 'rgba(0,0,0,.045)';
		var emptyColor = dark ? 'rgba(255,255,255,.035)' : 'rgba(0,0,0,.028)';

		ctx.font = '10px "Source Sans 3","Microsoft YaHei",sans-serif';
		ctx.textBaseline = 'middle';

		// column tick labels (时间)
		var labelEvery = Math.max(1, Math.ceil(nT / Math.max(4, Math.floor(avail / 78))));
		ctx.fillStyle = muteColor;
		ctx.textAlign = 'left';
		for (var c = 0; c < nT; c += labelEvery) {
			var lbl = labels[c] ? String(labels[c]) : '';
			if (!lbl) continue;
			var short = lbl.length > 16 ? lbl.slice(5, 16) : lbl;
			ctx.fillText(short, gutter + c * cellW, headH / 2 + 1);
		}

		// cells
		for (var r = 0; r < rows.length; ++r) {
			var row = rows[r];
			var vals = row.values;
			var flat = !isFinite(row.min) || row.max - row.min < 1e-9;
			var y = headH + r * cellH;
			for (var cc = 0; cc < nT; ++cc) {
				var x = gutter + cc * cellW;
				var val = vals[cc];
				if (val === null || !isFinite(val)) {
					ctx.fillStyle = emptyColor;
				} else if (flat) {
					ctx.fillStyle = dark ? 'rgba(255,255,255,.20)' : 'rgba(60,60,80,.18)';
				} else {
					ctx.fillStyle = ramp((val - row.min) / (row.max - row.min));
				}
				ctx.fillRect(x, y, cellW - 1, cellH - 1);
			}
			ctx.fillStyle = labelColor;
			ctx.textAlign = 'right';
			ctx.fillText(fitText(ctx, row.name, gutter - 10), gutter - 10, y + cellH / 2);
			ctx.fillStyle = gridColor;
			ctx.fillRect(gutter - 6, y + cellH - 1, cssW - gutter + 6, 1);
		}

		cv.onmousemove = function (ev) {
			var box = cv.getBoundingClientRect();
			var col = Math.floor((ev.clientX - box.left - gutter) / cellW);
			var rw = Math.floor((ev.clientY - box.top - headH) / cellH);
			if (col < 0 || rw < 0 || col >= nT || rw >= rows.length) {
				st.refs.legendNote.textContent = '色值按每个对象自身的最小/最大值归一化 · 空格表示该时段没有记录';
				return;
			}
			var item = rows[rw];
			var vv = item.values[col];
			st.refs.legendNote.textContent = item.name + ' · ' + (labels[col] || ('t=' + col)) + ' · ' +
				(vv === null || !isFinite(vv) ? '无记录' : vv.toFixed(3));
		};
	}

	function fitText(ctx, text, maxW) {
		var s = String(text || '');
		if (ctx.measureText(s).width <= maxW) return s;
		var lo = 0;
		var hi = s.length;
		while (lo < hi) {
			var mid = Math.ceil((lo + hi) / 2);
			if (ctx.measureText(s.slice(0, mid) + '…').width <= maxW) lo = mid;
			else hi = mid - 1;
		}
		return s.slice(0, Math.max(1, lo)) + '…';
	}

	/* ----------------------------------------------------------------- params */

	function setParamsStatus(text) {
		if (st.refs.paramsStatus) st.refs.paramsStatus.textContent = text || '';
	}

	function fieldControl(field, value) {
		var v = value == null || value === '' ? '' : String(value);
		if (field.type === 'select') {
			var opts = '<option value="">（默认）</option>';
			(field.options || []).forEach(function (o) {
				var sel = String(o.v) === v ? ' selected' : '';
				opts += '<option value="' + escapeHtml(o.v) + '"' + sel + '>' + escapeHtml(o.t) + '</option>';
			});
			return '<select data-key="' + escapeHtml(field.key) + '" title="' +
				escapeHtml(field.hint || '') + '">' + opts + '</select>';
		}
		return '<input type="number" step="' + escapeHtml(field.step || 'any') +
			'" data-key="' + escapeHtml(field.key) + '" value="' + escapeHtml(v) +
			'" placeholder="默认" title="' + escapeHtml(field.hint || '') + '">';
	}

	function renderCalcForm(schema, values) {
		var host = st.refs.paramsCalc;
		if (!host) return;
		var groups = [];
		var seen = Object.create(null);
		(schema || []).forEach(function (f) {
			if (!seen[f.group]) {
				seen[f.group] = true;
				groups.push(f.group);
			}
		});
		var html = '';
		groups.forEach(function (g) {
			html += '<div class="ocis-opt-formgroup"><div class="ocis-opt-group-title">' + escapeHtml(g) + '</div>';
			(schema || []).forEach(function (f) {
				if (f.group !== g) return;
				html += '<label class="ocis-opt-field"><span title="' + escapeHtml(f.hint || '') + '">' +
					escapeHtml(f.label) + '</span>' + fieldControl(f, values && values[f.key]) + '</label>';
			});
			html += '</div>';
		});
		host.innerHTML = html || '<p class="ocis-opt-hint is-empty">没有可编辑的全局字段。</p>';
	}

	function renderGateTable(schema, gates) {
		var wrap = st.refs.gateWrap;
		if (!wrap) return;
		st.params.gates = gates || [];
		st.params.gateSchema = schema || [];
		var q = trim(st.refs.paramsFilter.value).toLowerCase();
		var cols = schema || [];
		var head = '<th>闸门</th>' + cols.map(function (f) {
			return '<th title="' + escapeHtml(f.hint || '') + '">' + escapeHtml(f.label) + '</th>';
		}).join('');
		var rows = (gates || []).filter(function (g) {
			if (!q) return true;
			return String(g.name || '').toLowerCase().indexOf(q) >= 0;
		}).map(function (g) {
			var cells = cols.map(function (f) {
				var val = g.values && g.values[f.key];
				return '<td>' + fieldControl(f, val) + '</td>';
			}).join('');
			return '<tr data-gate="' + escapeHtml(g.name) + '"><td class="ocis-opt-gate-name">' +
				escapeHtml(g.name) + '</td>' + cells + '</tr>';
		}).join('');
		wrap.innerHTML = '<table class="ocis-opt-table"><thead><tr>' + head +
			'</tr></thead><tbody>' + (rows || '<tr><td colspan="' + (cols.length + 1) +
			'">没有匹配的闸门</td></tr>') + '</tbody></table>';
	}

	function collectCalcValues() {
		var host = st.refs.paramsCalc;
		var out = {};
		if (!host) return out;
		Array.prototype.forEach.call(host.querySelectorAll('[data-key]'), function (el) {
			out[el.getAttribute('data-key')] = el.value;
		});
		return out;
	}

	function collectGateValues() {
		var wrap = st.refs.gateWrap;
		var rows = [];
		if (!wrap) return rows;
		Array.prototype.forEach.call(wrap.querySelectorAll('tr[data-gate]'), function (tr) {
			var values = {};
			Array.prototype.forEach.call(tr.querySelectorAll('[data-key]'), function (el) {
				values[el.getAttribute('data-key')] = el.value;
			});
			rows.push({ name: tr.getAttribute('data-gate'), values: values });
		});
		return rows;
	}

	function snapshotGateEdits() {
		var live = collectGateValues();
		if (!live.length) return;
		var byName = Object.create(null);
		live.forEach(function (g) {
			byName[g.name] = g.values;
		});
		st.params.gates = (st.params.gates || []).map(function (g) {
			return { name: g.name, values: byName[g.name] || g.values || {} };
		});
	}

	function loadParams() {
		var name = selectedCase();
		if (!name) {
			setParamsStatus('请先选择案例');
			return;
		}
		setParamsStatus('正在读取 ' + name + ' / input.json …');
		jsonFetch('/api/opt-milp/params?case=' + encodeURIComponent(name))
			.then(function (pack) {
				var body = pack.body || {};
				if (!pack.res.ok || body.ok === false) throw new Error(body.error || ('HTTP ' + pack.res.status));
				st.params.schema = body.schema || {};
				st.params.file = body.file || 'input.json';
				st.params.loaded = true;
				renderCalcForm(st.params.schema.calculation, body.calculation || {});
				renderGateTable(st.params.schema.gate, body.gates || []);
				setParamsStatus('已加载 ' + body.case + ' / ' + st.params.file + ' · 闸门 ' +
					((body.gates || []).length) + ' 座');
			})
			.catch(function (err) {
				st.params.loaded = false;
				setParamsStatus('读取失败：' + (err && err.message ? err.message : err));
			});
	}

	function saveParams() {
		var name = selectedCase();
		if (!name) {
			setParamsStatus('请先选择案例');
			return;
		}
		snapshotGateEdits();
		setParamsStatus('正在保存到案例文件…');
		jsonFetch('/api/opt-milp/params', {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				case: name,
				calculation: collectCalcValues(),
				gates: st.params.gates || []
			})
		})
			.then(function (pack) {
				var body = pack.body || {};
				if (!pack.res.ok || body.ok === false) throw new Error(body.error || ('HTTP ' + pack.res.status));
				renderCalcForm((body.schema && body.schema.calculation) ||
					(st.params.schema && st.params.schema.calculation), body.calculation || {});
				renderGateTable((body.schema && body.schema.gate) || st.params.gateSchema, body.gates || []);
				setParamsStatus('已写入 ' + (body.file || 'input.json') + '。下次开始计算按该文件。');
				loadMeta({ keepCase: true });
			})
			.catch(function (err) {
				setParamsStatus('保存失败：' + (err && err.message ? err.message : err));
			});
	}

	/* ------------------------------------------------------------------- boot */

	function boot() {
		watchToolbar();
		document.addEventListener('click', function (ev) {
			var t = ev.target;
			if (!t || !t.closest) return;
			if (!t.closest('#ocisOptScheduleBtn')) return;
			ev.preventDefault();
			open();
		});
	}

	window.OCISOptSchedule = {
		open: open,
		close: close,
		preview: function (name, rel, title) {
			previewPlan(name || selectedCase(), rel, title);
		}
	};

	if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
	else boot();
})();
