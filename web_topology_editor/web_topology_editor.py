from __future__ import annotations

import argparse
import base64
import csv
import errno
import heapq
import html
import json
import math
import os
import re
import shutil
import struct
import sys
from datetime import datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen


REQUIRED_EDGE_COLUMNS = [
    "source",
    "target",
    "end",
    "ConnectionType",
    "stake",
    "canal",
    "id",
    "delaytime",
    "pool_Width",
    "pool_Length",
    "pool_m",
    "pool_hTarget",
    "pool_h_ic",
    "max_h",
    "min_h",
    "type",
    "maxFlow",
    "minFlow",
    "Flow_ic",
    "seepageC",
    "forceFlow",
    "forceStage",
    "upstream_elevation",
    "mile_stage",
    "gate_bottom_elevation",
    "pool_slope",
    "pool_manning",
    "level1",
]

HTML_PAGE = r"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Edges 渠网拓扑建模工具</title>
  <style>
    :root { --bg:#f5f7fb; --card:#fff; --line:#d9dee8; --text:#1f2937; --muted:#6b7280; --primary:#2563eb; --danger:#dc2626; }
    * { box-sizing:border-box; }
    body { margin:0; font-family: "Microsoft YaHei", Arial, sans-serif; font-size:13px; color:var(--text); background:var(--bg); }
    .wrap { display:grid; grid-template-columns: 420px 1fr; height:100vh; gap:10px; padding:10px; }
    .panel { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:10px; overflow:auto; }
    .title { font-weight:700; margin:0 0 8px 0; }
    .sub { font-size:12px; color:var(--muted); margin-bottom:10px; }
    .row { display:flex; gap:8px; align-items:center; margin-bottom:8px; }
    .row label { width:84px; font-size:12px; color:var(--muted); }
    .row input, .row select, textarea { flex:1; border:1px solid var(--line); border-radius:6px; padding:5px 6px; font-size:12px; }
    .btns { display:flex; gap:6px; flex-wrap:wrap; margin:8px 0; }
    button { border:1px solid var(--line); background:#fff; padding:5px 9px; border-radius:6px; cursor:pointer; font-size:12px; }
    .btns button.active { background:var(--primary); color:#fff; border-color:var(--primary); }
    button.primary { background:var(--primary); color:#fff; border-color:var(--primary); }
    button.danger { color:#fff; background:var(--danger); border-color:var(--danger); }
    .list { border:1px solid var(--line); border-radius:8px; max-height:220px; overflow:auto; }
    table { width:100%; border-collapse:collapse; font-size:11px; }
    th, td { padding:6px; border-bottom:1px solid #eef1f6; text-align:left; white-space:nowrap; }
    tr.sel { background:#e8f0ff; }
    .hint { font-size:12px; color:var(--muted); margin:6px 0; }
    .startupWarn { display:none; font-size:12px; color:#b91c1c; background:#fee2e2; border:1px solid #fecaca; border-radius:8px; padding:8px 10px; margin:6px 0 10px; }
    .stat { font-size:12px; color:var(--muted); margin-left:auto; }
    .warnMark { color:#dc2626; font-weight:700; margin-left:4px; }
    #canvasWrap { height:100%; position:relative; }
    #graphSvg { width:100%; height:100%; background:#fff; border:1px solid var(--line); border-radius:10px; touch-action:none; }
    #canvasWrap, #graphSvg, #graphSvg * { user-select:none; -webkit-user-select:none; }
    .legend { position:absolute; right:12px; top:12px; background:#fff; border:1px solid var(--line); border-radius:8px; padding:6px 8px; font-size:12px; }
    .dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:5px; }
    .ln { display:inline-block; width:18px; height:0; border-top:2px solid; margin-right:5px; vertical-align:middle; }
    .muted { opacity:0.55; }
    .treeView { border:1px solid var(--line); border-radius:8px; background:#fff; max-height:180px; overflow:auto; padding:4px; }
    .treeRow { display:flex; align-items:center; gap:4px; height:22px; padding:0 4px; border-radius:4px; user-select:none; }
    .treeRow:hover { background:#f3f4f6; }
    .treeRow.file { cursor:pointer; }
    .treeRow.folder { cursor:pointer; }
    .treeTwist { width:14px; text-align:center; color:#64748b; font-size:11px; }
    .treeIcon { width:14px; text-align:center; }
    .treeName { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .treeError { color:#dc2626; font-size:12px; padding:6px; }
    .simStepLabel { font-size:12px; color:var(--muted); min-width:94px; text-align:right; }
    #layoutModeWrap { display:block; }
    .typeStyleBox { border:1px solid var(--line); border-radius:8px; padding:8px; background:#fafcff; max-height:220px; overflow:auto; }
    .typeStyleRow { display:grid; grid-template-columns:18px minmax(64px,1fr) minmax(72px,1fr) 64px 68px 64px 68px; gap:6px; align-items:center; margin-bottom:6px; }
    .typeStyleRow:last-child { margin-bottom:0; }
    .typeStyleRow input[type="number"] { width:100%; min-width:0; }
    .typeStyleRow input[type="color"] { width:100%; min-width:0; padding:1px; height:24px; }
    .typeStyleHead { font-size:11px; color:var(--muted); font-weight:600; margin-bottom:6px; display:grid; grid-template-columns:18px minmax(64px,1fr) minmax(72px,1fr) 64px 68px 64px 68px; gap:6px; }
    .typeBadge { font-size:11px; color:#374151; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .modalMask { position:fixed; inset:0; background:rgba(15,23,42,0.36); display:none; align-items:center; justify-content:center; z-index:200; }
    .modalCard { width:min(860px, 92vw); max-height:86vh; overflow:auto; background:#fff; border:1px solid var(--line); border-radius:10px; padding:10px; }
    .modalTitle { font-weight:700; margin:0 0 8px 0; }
    .compareRow { display:flex; gap:8px; align-items:center; margin-bottom:8px; }
    .compareRow .filePathInput { flex:1; min-width:260px; }
    .compareRow .labelInput { width:160px; flex:0 0 160px; }
    #comparePathTree.treeView { max-height:360px; }
    #analysisConfigText { display:none; }
    #analysisConfigTableWrap { width:100%; min-height:380px; max-height:58vh; overflow:auto; border:1px solid var(--line); border-radius:8px; }
    #analysisConfigTable { width:100%; border-collapse:collapse; font-size:12px; }
    #analysisConfigTable th, #analysisConfigTable td { border-bottom:1px solid #eef1f6; padding:6px; }
    #analysisConfigTable input { width:100%; border:1px solid var(--line); border-radius:4px; padding:4px 6px; font-size:12px; }
    #analysisConfigTable tr.sel { background:#eef4ff; }
    #analysisConfigTable td.cellSelected { background:#dbeafe; }
    #analysisConfigTable input.cellSelected { border-color:#3b82f6; background:#eff6ff; }
    #analysisConfigTable .chkCol { width:44px; text-align:center; }
    #analysisConfigTable .actCol { width:72px; text-align:center; }
    #analysisConfigAddCount { width:84px; }
    #analysisConfigModal .modalCard { border-radius:12px; padding:14px; box-shadow:0 14px 32px rgba(15,23,42,0.14); }
    #analysisConfigModal .modalTitle { font-size:16px; margin-bottom:10px; }
    #analysisConfigModal .toolPanel { border:1px solid #e6ebf3; border-radius:10px; background:#f8fafc; padding:10px; }
    #analysisConfigModal .toolSectionTitle { font-size:14px; font-weight:700; margin:0 0 8px 0; }
    #analysisConfigModal .toolHint { font-size:12px; color:var(--muted); margin:0 0 10px 0; }
    #analysisConfigModal .entryGrid { display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:10px; }
    #analysisConfigModal .dataToolEntryBtn {
      display:flex; flex-direction:column; align-items:flex-start; gap:4px;
      min-height:74px; padding:10px 12px; border-radius:10px;
      border:1px solid #dbe2ee; background:#fff;
    }
    #analysisConfigModal .dataToolEntryBtn:hover { border-color:#9ab3e6; background:#f6f9ff; }
    #analysisConfigModal .entryTitle { font-size:13px; font-weight:700; color:#1e3a8a; }
    #analysisConfigModal .entryDesc { font-size:12px; color:var(--muted); text-align:left; line-height:1.35; }
    #analysisConfigModal .toolActions { margin-top:10px; }
    #analysisConfigModal #analysisConfigToolPanel .row label,
    #analysisConfigModal #baselineToolPanel .row label,
    #analysisConfigModal #formatConvertToolPanel .row label { width:96px; }
    #analysisConfigModal .toolResult {
      margin-top:8px; padding:8px 10px; border-radius:8px;
      border:1px dashed #cbd5e1; background:#f8fafc; color:#475569;
      min-height:34px;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <h3 class="title">渠网拓扑建模工具</h3>
      <div class="sub">支持节点/边交互编辑、连接关系修改，默认保存为 edges_new.csv</div>
      <div id="startupWarn" class="startupWarn"></div>

      <div class="row"><label>案例目录</label><select id="caseSelect"><option value=".">.</option></select></div>
      <div class="btns"><button id="btnRefreshCases">刷新案例</button></div>

      <div class="row"><label>保存路径</label><input id="savePath" value="mesh/edges_new.csv" placeholder="默认写回 mesh/edges_new.csv" /></div>
      <div class="btns">
        <button id="btnLoad" class="primary">加载</button>
        <button id="btnSave">保存当前路径</button>
        <button id="btnSaveEdgesCsv">保存到 edges.csv</button>
      </div>
      <div class="btns">
        <button class="primary" id="btnOpenSimWindow">在线仿真</button>
        <button id="btnExportTopology">导出拓扑图</button>
        <button id="btnCurveCompare">曲线对比</button>
        <button id="btnAnalysisConfig">数据处理</button>
      </div>
      <div id="layoutModeWrap">
        <div class="row"><label>布局模式</label><span class="sub" style="margin:0">自动/手动刷新可切换</span></div>
        <div class="btns" id="layoutModeBtns">
          <button id="btnLayoutForce">重置力导(5秒)</button>
          <button id="btnForceAuto" class="active">自动刷新</button>
          <button id="btnForceManual">手动刷新</button>
          <button id="btnForceRefresh">手动刷新一次</button>
        </div>
      </div>
      <div class="row"><label>相机范围</label><input id="camRangeWidth" type="number" min="200" step="50" value="1200" /><input id="camRangeHeight" type="number" min="200" step="50" value="760" /></div>
      <div class="btns"><button id="btnApplyCameraRange">应用相机范围</button></div>
      <div class="row"><label>节点标签</label><input id="chkShowNodeLabels" type="checkbox" checked style="flex:0 0 auto;width:auto;" /><span class="sub" style="margin:0">显示节点名称</span></div>
      <div class="row"><label>Type样式</label><span class="sub" style="margin:0">勾选后显示该type关联节点与边</span></div>
      <div class="btns">
        <button id="btnTypeShowAll">全选</button>
        <button id="btnTypeShowNone">全不选</button>
        <button id="btnSaveTypeScheme">保存配色方案</button>
      </div>
      <div id="typeStyleBox" class="typeStyleBox"></div>
      <div class="row"><label>图例文案</label><span class="sub" style="margin:0">支持 {type} / {alias} / {count} 模板</span></div>
      <div class="row"><label>渠道边</label><input id="legendChannelText" value="渠道边" /></div>
      <div class="row"><label>分水边</label><input id="legendSplitText" value="分水边（虚拟节点->分汇水节点）" /></div>
      <div class="row"><label>节点模板</label><input id="legendNodeTemplate" value="节点 {alias} (type={type}, 数量={count})" /></div>
      <div class="btns"><button id="btnSaveLegendText">保存图例文案</button></div>
      <div class="row"><label>服务端文件</label><input id="serverEdgesPath" value="mesh/edges_new.csv" /></div>
      <div class="btns"><button id="btnLoadServerPath">加载指定路径</button></div>
      <div class="row"><label>路径层级</label><span class="sub" style="margin:0">点击文件可回填上方路径</span></div>
      <div class="btns"><button id="btnRefreshServerTree">刷新层级</button></div>
      <div id="serverPathTree" class="treeView"></div>

      <hr />
      <div class="row"><strong>节点编辑</strong><span class="stat" id="nodeStat"></span></div>
      <div class="row"><label>节点名</label><input id="nodeName" /></div>
      <div class="row"><label>重命名为</label><input id="nodeRename" /></div>
      <div class="btns">
        <button id="btnNodeAdd">新增节点</button>
        <button id="btnNodeRename">重命名节点</button>
        <button class="danger" id="btnNodeDel">删除节点</button>
      </div>

      <div class="list">
        <table id="nodeTable">
          <thead><tr><th>节点</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>

      <hr />
      <div class="row"><strong>边编辑</strong><span class="stat" id="edgeStat"></span></div>
      <div class="row"><label>source</label><input id="eSource" /></div>
      <div class="row"><label>target</label><input id="eTarget" /></div>
      <div class="row"><label>end</label><input id="eEnd" placeholder="可空" /></div>
      <div class="row"><label>类型</label>
        <select id="eConn"><option value="direct">direct</option><option value="indirect">indirect</option></select>
      </div>
      <div class="row"><label>id</label><input id="eId" /></div>
      <div class="row"><label>type</label><input id="eType" /></div>
      <div class="row"><label>maxFlow</label><input id="eMaxFlow" /></div>
      <div class="row"><label>力导类型</label>
        <select id="eForceType">
          <option value="attract" selected>attract(吸引)</option>
          <option value="repel">repel(排斥)</option>
          <option value="none">none(禁用)</option>
        </select>
      </div>
      <div class="row"><label>力导强调</label><input id="eForceWeight" type="number" min="0" max="5" step="0.1" value="1" /></div>
      <div class="btns">
        <button id="btnEdgeAdd">新增边</button>
        <button id="btnEdgeUpd">更新选中边</button>
        <button class="danger" id="btnEdgeDel">删除选中边</button>
        <button id="btnCheckDirectEnd">检查direct缺失end</button>
      </div>

      <div class="list">
        <table id="edgeTable">
          <thead><tr><th>#</th><th>source</th><th>target</th><th>end</th><th>ConnectionType</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
      <div class="hint">操作提示：支持拖拽节点；从节点悬浮连接点拖到另一个节点可连边（Shift 为 indirect）；若松开时未放到节点，预览线会自动消失；节点悬浮红色删除点可直接删节点。</div>
    </div>

    <div class="panel" style="padding:0;">
      <div id="canvasWrap">
        <svg id="graphSvg" viewBox="0 0 1200 760" preserveAspectRatio="xMidYMid meet">
          <defs>
            <marker id="arrowDirect" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L8,4 L0,8 z" fill="#f59e0b"></path>
            </marker>
            <marker id="arrowIndirect" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L8,4 L0,8 z" fill="#2563eb"></path>
            </marker>
            <marker id="arrowPreview" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L8,4 L0,8 z" fill="#60a5fa"></path>
            </marker>
          </defs>
          <g id="viewport">
            <g id="edgeLayer"></g>
            <g id="nodeLayer"></g>
            <g id="interactionLayer"></g>
          </g>
        </svg>
        <div class="legend" id="topologyLegend">
          <div><span class="ln" style="border-color:#2563eb;border-top-width:3px"></span><span id="legendChannelLabel">渠道边</span></div>
          <div><span class="ln" style="border-color:#f59e0b;border-top-style:dashed"></span><span id="legendSplitLabel">分水边（虚拟节点->分汇水节点）</span></div>
          <div id="topologyLegendNodeItems"></div>
        </div>
        <div id="nodeMenu" style="display:none;position:absolute;z-index:20;background:#fff;border:1px solid var(--line);border-radius:8px;padding:6px;box-shadow:0 6px 16px rgba(0,0,0,0.08)">
          <div style="font-size:12px;color:var(--muted);margin:2px 4px 6px;" id="nodeMenuTitle"></div>
          <div class="btns" style="margin:0;">
            <button id="menuNodeAdd">增加相连节点</button>
            <button id="menuNodeRename">编辑节点名</button>
            <button id="menuNodeDelete" class="danger">减少节点(删除)</button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div id="curveCompareModal" class="modalMask">
    <div class="modalCard">
      <div class="modalTitle">曲线对比配置</div>
      <div class="row"><label>Y列名(可选)</label><input id="compareYColumn" placeholder="留空时自动选第一列数值列" /></div>
      <div class="row"><label>图片DPI</label>
        <select id="compareDpi">
          <option value="100">100</option>
          <option value="200">200</option>
          <option value="300" selected>300</option>
          <option value="600">600</option>
        </select>
      </div>
      <div class="row"><label>画布宽度</label><input id="compareFigWidth" type="number" min="4" max="80" step="1" value="20" /></div>
      <div class="row"><label>画布高度</label><input id="compareFigHeight" type="number" min="4" max="80" step="1" value="10" /></div>
      <div class="row"><label>字号</label><input id="compareFontSize" type="number" min="8" max="48" step="1" value="16" /></div>
      <div id="curveCompareRows"></div>
      <div class="btns" style="margin-top:8px;">
        <button id="btnCompareAddRow">新增一行</button>
        <button id="btnCompareCancel">取消</button>
        <button id="btnCompareInteractive">交互式可视化</button>
        <button id="btnCompareConfirm" class="primary">确定并绘图</button>
      </div>
    </div>
  </div>

  <div id="comparePathModal" class="modalMask">
    <div class="modalCard" style="width:min(760px,90vw)">
      <div class="modalTitle">选择对比文件路径</div>
      <div class="btns" style="margin-bottom:8px;">
        <button id="btnComparePickRefresh">刷新路径</button>
        <button id="btnComparePickCancel">取消</button>
      </div>
      <div id="comparePathTree" class="treeView"></div>
      <div class="hint">点击文件即可回填到当前行</div>
    </div>
  </div>

  <div id="topologyExportModal" class="modalMask">
    <div class="modalCard" style="width:min(520px,90vw)">
      <div class="modalTitle">导出拓扑图</div>
      <div class="row"><label>文件类型</label>
        <select id="topologyExportType">
          <option value="png" selected>png</option>
          <option value="jpg">jpg</option>
          <option value="webp">webp</option>
          <option value="svg">svg</option>
        </select>
      </div>
      <div class="row"><label>DPI</label>
        <select id="topologyExportDpi">
          <option value="96">96</option>
          <option value="150">150</option>
          <option value="200">200</option>
          <option value="300" selected>300</option>
          <option value="600">600</option>
        </select>
      </div>
      <div class="row"><label>导出范围</label>
        <select id="topologyExportScope">
          <option value="graph" selected>整张拓扑图</option>
          <option value="legend">仅图例</option>
        </select>
      </div>
      <div class="hint">可导出整图或仅图例，位图类型会按 DPI 缩放分辨率。</div>
      <div class="btns" style="margin-top:8px;">
        <button id="btnTopologyExportCancel">取消</button>
        <button id="btnTopologyExportConfirm" class="primary">导出</button>
      </div>
    </div>
  </div>

  <div id="analysisConfigModal" class="modalMask">
    <div class="modalCard" style="width:min(980px,94vw)">
      <div class="modalTitle">数据处理</div>

      <div id="dataToolsEntryPanel" class="toolPanel">
        <div class="toolHint">请选择要使用的功能入口：</div>
        <div class="entryGrid">
          <button id="btnOpenAnalysisConfigTool" class="dataToolEntryBtn">
            <span class="entryTitle">分析对象配置</span>
            <span class="entryDesc">编辑并保存分析对象配置表</span>
          </button>
          <button id="btnOpenBaselineTool" class="dataToolEntryBtn">
            <span class="entryTitle">基准值处理</span>
            <span class="entryDesc">按首值或固定值对数值列做基准偏移</span>
          </button>
          <button id="btnOpenFormatConvertTool" class="dataToolEntryBtn">
            <span class="entryTitle">文件格式转换</span>
            <span class="entryDesc">支持宽表/长表/JSON互转</span>
          </button>
        </div>
        <div class="btns toolActions">
          <button id="btnDataToolsCloseEntry">关闭</button>
        </div>
      </div>

      <div id="analysisConfigToolPanel" class="toolPanel" style="display:none;">
        <div class="toolSectionTitle">分析对象配置</div>
        <div class="toolHint">用于维护分析对象CSV，支持批量新增、选择删除与保存。</div>
        <div class="row"><label>配置文件</label><input id="analysisConfigPath" value="mesh/Gates_param.csv" /></div>
        <div class="btns toolActions" style="margin-bottom:8px;">
          <button id="btnBackFromAnalysisConfig">返回功能列表</button>
          <button id="btnAnalysisConfigLoad">加载</button>
          <input id="analysisConfigAddCount" type="number" min="1" max="200" step="1" value="1" />
          <button id="btnAnalysisConfigAddRow">新增行</button>
          <button id="btnAnalysisConfigSelectAll">全选</button>
          <button id="btnAnalysisConfigClearSel">清空选择</button>
          <button id="btnAnalysisConfigDeleteSelected" class="danger">删除选中</button>
          <button id="btnAnalysisConfigSave" class="primary">保存</button>
          <button id="btnDataToolsCloseAnalysis">关闭</button>
        </div>
        <div id="analysisConfigTableWrap">
          <table id="analysisConfigTable">
            <thead></thead>
            <tbody></tbody>
          </table>
        </div>
        <textarea id="analysisConfigText" placeholder="加载后可直接编辑 CSV 内容"></textarea>
      </div>

      <div id="baselineToolPanel" class="toolPanel" style="display:none;">
        <div class="toolSectionTitle">基准值处理</div>
        <div class="toolHint">选择输入/输出路径后执行，结果会显示在下方。</div>
        <div class="row"><label>基准输入</label><input id="baselineInputPath" value="input/stage.csv" placeholder="待处理 CSV 路径" /></div>
        <div class="row"><label>基准输出</label><input id="baselineOutputPath" value="output/stage_baseline.csv" placeholder="留空自动生成" /></div>
        <div class="row"><label>基准模式</label>
          <select id="baselineMode">
            <option value="first_non_empty" selected>首行非空值</option>
            <option value="fixed">固定基准值</option>
          </select>
        </div>
        <div class="row"><label>固定基准值</label><input id="baselineValue" type="number" step="any" value="0" /></div>
        <div class="row"><label>处理列</label><input id="baselineColumns" placeholder="逗号分隔；留空处理全部数值列" /></div>
        <div class="btns" style="margin-bottom:8px;">
          <button id="btnBackFromBaseline">返回功能列表</button>
          <button id="btnRunBaseline">执行基准值处理</button>
          <button id="btnDataToolsCloseBaseline">关闭</button>
        </div>
        <div id="baselineResult" class="toolResult"></div>
      </div>

      <div id="formatConvertToolPanel" class="toolPanel" style="display:none;">
        <div class="toolSectionTitle">文件格式转换</div>
        <div class="toolHint">按模式执行表结构转换，支持输出到指定路径。</div>
        <div class="row"><label>转换输入</label><input id="convertInputPath" value="output/stage.csv" placeholder="待转换文件" /></div>
        <div class="row"><label>转换模式</label>
          <select id="convertMode">
            <option value="pivot_to_tidy" selected>宽表转长表 (pivot_to_tidy)</option>
            <option value="tidy_to_pivot">长表转宽表 (tidy_to_pivot)</option>
            <option value="pivot_to_json">宽表转 JSON (pivot_to_json)</option>
            <option value="json_to_pivot">JSON 转宽表 (json_to_pivot)</option>
          </select>
        </div>
        <div class="row"><label>转换输出</label><input id="convertOutputPath" value="output/stage_td.csv" placeholder="留空自动生成" /></div>
        <div class="btns" style="margin-bottom:8px;">
          <button id="btnBackFromFormatConvert">返回功能列表</button>
          <button id="btnRunFormatConvert">执行格式转换</button>
          <button id="btnDataToolsCloseConvert">关闭</button>
        </div>
        <div id="formatConvertResult" class="toolResult"></div>
      </div>
    </div>
  </div>

<script>
const state = {
  edges: [],
  nodes: [],
  selectedNode: null,
  selectedEdgeIndex: null,
  positions: {},
  fixedNodes: {},
  layoutLocked: false,
  layoutMode: 'force',
  layoutSource: {positions:{}, fixedPositions:{}},
  viewMode: 'select',
  connectFrom: null,
  connectHoverTarget: null,
  mouseView: {x: 0, y: 0},
  paletteDragType: null,
  fixedDragHintShown: false,
  directEndWarnIndices: [],
  pathTreeExpanded: {},
  scale: 1,
  tx: 0,
  ty: 0,
  curveCompareItems: [],
  comparePathTreeExpanded: {},
  comparePickRowIndex: null,
  analysisConfig: { headers: [], rows: [] },
  analysisConfigSelectedRows: new Set(),
  analysisConfigCellSelection: { anchor: null, focus: null, dragging: false, selected: new Set() },
  analysisConfigHistory: { undo: [], redo: [], maxDepth: 200, lastSnapshot: '' },
  currentCasePath: '.',
  casePathOptions: [],
  typeStyles: {},
  typeOrder: [],
  selectedTypeKeys: new Set(),
  forceRefreshMode: 'auto',
  showNodeLabels: true,
  cameraRange: {width: 1200, height: 760},
  legendConfig: {
    channelEdgeLabel: '渠道边',
    splitEdgeLabel: '分水边（虚拟节点->分汇水节点）',
    nodeTypeTemplate: '节点 {alias} (type={type}, 数量={count})',
  },
  lastLegendNodeItems: [],
};

const DEFAULT_CASE_PATH = '.';
const TYPE_STYLE_STORAGE_PREFIX = 'psh.topology.typeStyle.v1:';
const LEGEND_TEXT_STORAGE_KEY = 'psh.topology.legendText.v1';
const TYPE_STYLE_COLOR_PALETTE = ['#2563eb', '#f59e0b', '#10b981', '#8b5cf6', '#ef4444', '#0ea5e9', '#14b8a6', '#d946ef'];
const LARGE_GRAPH_NODE_THRESHOLD = 220;
const LARGE_GRAPH_RENDER_SKIP = 2;
const FORCE_LAYOUT_ACTIVE_MS = 5000;

const svg = document.getElementById('graphSvg');
const viewport = document.getElementById('viewport');
const edgeLayer = document.getElementById('edgeLayer');
const nodeLayer = document.getElementById('nodeLayer');
const interactionLayer = document.getElementById('interactionLayer');
const nodeMenu = document.getElementById('nodeMenu');
const nodeMenuTitle = document.getElementById('nodeMenuTitle');

let dragNode = null;
let panMode = false;
let panStart = null;
let dragOffsetVP = null;       // {x,y} where x = node.x - view.x, y = node.y - view.y
let dragMoved = false;
let suppressNodeClickUntil = 0;
let activePointerId = null;
let activeMode = 'none';
let activePointerCaptureEl = null;
let hoverNodeForConnect = null;
let connectDragFrom = null;
let connectDragHoverTarget = null;
let dragIndirectEdgeIndex = null;
let dragIndirectEdgeNodes = null;
let dragIndirectStartVP = null;
let dragFrameId = 0;
let pendingDragVP = null;
let pendingDragClient = null;
let pendingEdgePatchNode = null;
let edgePatchFrameId = 0;
let layoutTickCounter = 0;
let forceLayoutActiveUntil = 0;
let forceManualRefreshSteps = 0;
let _nodeTypeLookup = new Map();
let _sourceOccurrenceLookup = new Map();
let _indirectSourceLookup = new Set();
let _targetLookup = new Set();
let _sourceOrEndLookup = new Set();
let _promotedGateLookup = new Set();
let _promotedPrevEdgeIndexLookup = new Set();
let _filterPinnedNodeLookup = new Set();
let _directTargetOnlyGateLookup = new Set();

function isInteractionActive(){
  return !!dragNode || !!connectDragFrom || !!dragIndirectEdgeNodes;
}

function isLargeGraphMode(){
  return (state.nodes || []).length >= LARGE_GRAPH_NODE_THRESHOLD;
}

function applyCameraRangeFromState(){
  const width = Math.max(200, Number(state.cameraRange && state.cameraRange.width) || 1200);
  const height = Math.max(200, Number(state.cameraRange && state.cameraRange.height) || 760);
  state.cameraRange = {width, height};
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
}

function applyCameraRangeFromInputs(){
  const w = Number(document.getElementById('camRangeWidth').value || 1200);
  const h = Number(document.getElementById('camRangeHeight').value || 760);
  state.cameraRange = {
    width: Math.max(200, Number.isFinite(w) ? w : 1200),
    height: Math.max(200, Number.isFinite(h) ? h : 760),
  };
  applyCameraRangeFromState();
  renderGraph();
}

function rebuildNodeTypeLookup(){
  const lookup = new Map();
  const sourceOccurrence = new Map();
  const indirectSourceLookup = new Set();
  const directTargetLookup = new Set();
  const targetLookup = new Set();
  const sourceOrEndLookup = new Set();
  const promotedGateLookup = new Set();
  (state.edges || []).forEach((edge)=>{
    const src = normalizeName(edge.source);
    const tgt = normalizeName(edge.target);
    const end = normalizeName(edge.end);
    const conn = String((edge && edge.ConnectionType) || '').trim().toLowerCase();
    if(conn === 'indirect'){
      if(src) indirectSourceLookup.add(src);
    } else if(conn === 'direct'){
      if(tgt) directTargetLookup.add(tgt);
    }
    if(src) sourceOrEndLookup.add(src);
    if(end) sourceOrEndLookup.add(end);
    if(tgt) targetLookup.add(tgt);
    if(src) sourceOccurrence.set(src, (sourceOccurrence.get(src) || 0) + 1);
    const edgeType = String((edge && edge.type) || '').trim();
    if(!edgeType) return;
    const names = isTypeZeroValue(edgeType) ? [src] : [src, tgt, end];
    names.forEach((name)=>{
      if(name && !lookup.has(name)) lookup.set(name, edgeType);
    });
  });
  _nodeTypeLookup = lookup;
  _sourceOccurrenceLookup = sourceOccurrence;
  _indirectSourceLookup = indirectSourceLookup;
  _targetLookup = targetLookup;
  _sourceOrEndLookup = sourceOrEndLookup;

  (state.edges || []).forEach((edge)=>{
    const raw = String((edge && edge.type) || '').trim();
    const typeText = raw || '未分类';
    const rawNum = Number(typeText);
    const isType2 = (typeText === '2' || (Number.isFinite(rawNum) && rawNum === 2));
    if(!isType2) return;
    const src = normalizeName(edge.source);
    if(!src) return;
    const srcTargetOnly = !!(_targetLookup.has(src) && !_sourceOrEndLookup.has(src));
    if(srcTargetOnly) return;
    if(_indirectSourceLookup.has(src)){
      promotedGateLookup.add(src);
      return;
    }
    const srcOccurrence = Number(_sourceOccurrenceLookup.get(src) || 0);
    if(srcOccurrence >= 2){
      promotedGateLookup.add(src);
      return;
    }
    const srcType = String(_nodeTypeLookup.get(src) || '').trim();
    const srcNum = Number(srcType);
    if(srcType === '4' || (Number.isFinite(srcNum) && srcNum === 4)){
      promotedGateLookup.add(src);
    }
  });
  _promotedGateLookup = promotedGateLookup;

  const preferredByGate = new Map();
  const fallbackByGate = new Map();
  const sourceFallbackByGate = new Map();
  (state.edges || []).forEach((edge, idx)=>{
    const candidates = [normalizeName(edge && edge.target), normalizeName(edge && edge.end)].filter(Boolean);
    const gate = candidates.find((name)=>_promotedGateLookup.has(name));
    if(gate){
      if(!fallbackByGate.has(gate)) fallbackByGate.set(gate, idx);
      const conn = String((edge && edge.ConnectionType) || '').trim().toLowerCase();
      if(conn === 'indirect' && !preferredByGate.has(gate)){
        preferredByGate.set(gate, idx);
      }
    }
    const src = normalizeName(edge && edge.source);
    if(src && _promotedGateLookup.has(src) && !sourceFallbackByGate.has(src)){
      sourceFallbackByGate.set(src, idx);
    }
  });
  const promotedPrevEdgeIndexLookup = new Set();
  _promotedGateLookup.forEach((gate)=>{
    if(preferredByGate.has(gate)) promotedPrevEdgeIndexLookup.add(preferredByGate.get(gate));
    else if(fallbackByGate.has(gate)) promotedPrevEdgeIndexLookup.add(fallbackByGate.get(gate));
    else if(sourceFallbackByGate.has(gate)) promotedPrevEdgeIndexLookup.add(sourceFallbackByGate.get(gate));
  });
  _promotedPrevEdgeIndexLookup = promotedPrevEdgeIndexLookup;

  const pinnedNodeLookup = new Set();
  indirectSourceLookup.forEach((name)=>{
    if(directTargetLookup.has(name)) pinnedNodeLookup.add(name);
  });
  _filterPinnedNodeLookup = pinnedNodeLookup;

  const directTargetOnlyGateLookup = new Set();
  directTargetLookup.forEach((name)=>{
    if(name && !sourceOrEndLookup.has(name)) directTargetOnlyGateLookup.add(name);
  });
  _directTargetOnlyGateLookup = directTargetOnlyGateLookup;
}

function activateForceLayoutWindow(durationMs = FORCE_LAYOUT_ACTIVE_MS){
  forceLayoutActiveUntil = Date.now() + Math.max(300, Number(durationMs) || FORCE_LAYOUT_ACTIVE_MS);
  state.layoutLocked = false;
  state.layoutMode = 'force';
}

function setForceRefreshMode(mode){
  state.forceRefreshMode = mode === 'manual' ? 'manual' : 'auto';
  const autoBtn = document.getElementById('btnForceAuto');
  const manualBtn = document.getElementById('btnForceManual');
  if(autoBtn) autoBtn.classList.toggle('active', state.forceRefreshMode === 'auto');
  if(manualBtn) manualBtn.classList.toggle('active', state.forceRefreshMode === 'manual');
}

function requestManualForceRefresh(steps = 1){
  setForceRefreshMode('manual');
  forceManualRefreshSteps = Math.max(forceManualRefreshSteps, Math.max(1, Number(steps) || 1));
  activateForceLayoutWindow(FORCE_LAYOUT_ACTIVE_MS);
}

function isForceLayoutWindowExpired(){
  return forceLayoutActiveUntil > 0 && Date.now() > forceLayoutActiveUntil;
}

/* ---- DOM caches (rebuilt in renderGraph) ---- */
let _nodeCircleMap = new Map();   // nodeName -> {halo, hit, circle, text}
let _edgeDOMList  = [];           // [{mainLine, haloLine, dashLine, midNode, edgeIdx, src, tgt, end, midA, midB}]
let _edgeRefsByNode = new Map();  // nodeName -> [edgeRef,...]

function getEdgeTypeValue(edge, edgeIndex=null){
  const raw = String((edge && edge.type) || '').trim();
  const typeText = raw || '未分类';
  return typeText;
}

function isTypeZeroValue(rawType){
  const text = String(rawType == null ? '' : rawType).trim();
  if(!text) return false;
  if(text === '0') return true;
  const asNum = Number(text);
  return Number.isFinite(asNum) && asNum === 0;
}

function normalizeHexColor(raw, fallback){
  const text = String(raw || '').trim();
  if(/^#[0-9a-fA-F]{6}$/.test(text)) return text;
  if(/^#[0-9a-fA-F]{3}$/.test(text)){
    const c = text.slice(1);
    return `#${c[0]}${c[0]}${c[1]}${c[1]}${c[2]}${c[2]}`;
  }
  return fallback;
}

function buildDefaultTypeStyle(typeKey, idx){
  const color = TYPE_STYLE_COLOR_PALETTE[idx % TYPE_STYLE_COLOR_PALETTE.length];
  const typeNum = Number(typeKey);
  const isNum4 = Number.isFinite(typeNum) && typeNum === 4;
  return {
    alias: String(typeKey || '未分类'),
    nodeSize: isNum4 ? 8.4 : 6.8,
    nodeColor: color,
    edgeWidth: isNum4 ? 3.2 : 2.0,
    edgeColor: color,
  };
}

function getScopedTypeStyleStorageKey(casePath){
  return TYPE_STYLE_STORAGE_PREFIX + normalizeCasePath(casePath || state.currentCasePath || '.');
}

function safeStorageGet(key){
  try{
    return window.localStorage ? window.localStorage.getItem(String(key || '')) : null;
  }catch(_err){
    return null;
  }
}

function safeStorageSet(key, value){
  try{
    if(window.localStorage){
      window.localStorage.setItem(String(key || ''), String(value || ''));
      return true;
    }
  }catch(_err){
    return false;
  }
  return false;
}

function loadLegendConfigFromStorage(){
  const raw = safeStorageGet(LEGEND_TEXT_STORAGE_KEY);
  if(!raw) return;
  try{
    const parsed = JSON.parse(raw);
    if(!parsed || typeof parsed !== 'object') return;
    const cfg = state.legendConfig || {};
    cfg.channelEdgeLabel = String(parsed.channelEdgeLabel || cfg.channelEdgeLabel || '渠道边');
    cfg.splitEdgeLabel = String(parsed.splitEdgeLabel || cfg.splitEdgeLabel || '分水边（虚拟节点->分汇水节点）');
    cfg.nodeTypeTemplate = String(parsed.nodeTypeTemplate || cfg.nodeTypeTemplate || '节点 {alias} (type={type}, 数量={count})');
    state.legendConfig = cfg;
  }catch(_err){
    return;
  }
}

function saveLegendConfigToStorage(){
  const cfg = state.legendConfig || {};
  const payload = {
    channelEdgeLabel: String(cfg.channelEdgeLabel || '渠道边'),
    splitEdgeLabel: String(cfg.splitEdgeLabel || '分水边（虚拟节点->分汇水节点）'),
    nodeTypeTemplate: String(cfg.nodeTypeTemplate || '节点 {alias} (type={type}, 数量={count})'),
  };
  return safeStorageSet(LEGEND_TEXT_STORAGE_KEY, JSON.stringify(payload));
}

function updateLegendTextInputs(){
  const cfg = state.legendConfig || {};
  const channelInput = document.getElementById('legendChannelText');
  const splitInput = document.getElementById('legendSplitText');
  const nodeInput = document.getElementById('legendNodeTemplate');
  if(channelInput) channelInput.value = String(cfg.channelEdgeLabel || '渠道边');
  if(splitInput) splitInput.value = String(cfg.splitEdgeLabel || '分水边（虚拟节点->分汇水节点）');
  if(nodeInput) nodeInput.value = String(cfg.nodeTypeTemplate || '节点 {alias} (type={type}, 数量={count})');
}

function applyLegendTextFromState(){
  const cfg = state.legendConfig || {};
  const channelLabel = document.getElementById('legendChannelLabel');
  const splitLabel = document.getElementById('legendSplitLabel');
  if(channelLabel) channelLabel.textContent = String(cfg.channelEdgeLabel || '渠道边');
  if(splitLabel) splitLabel.textContent = String(cfg.splitEdgeLabel || '分水边（虚拟节点->分汇水节点）');
}

function getTypeAlias(typeKey){
  const style = state.typeStyles && state.typeStyles[typeKey];
  const alias = style ? String(style.alias || '').trim() : '';
  return alias || String(typeKey || '未分类');
}

function formatLegendNodeLabel(typeKey, count){
  const cfg = state.legendConfig || {};
  const template = String(cfg.nodeTypeTemplate || '节点 {alias} (type={type}, 数量={count})');
  return template
    .replace(/\{alias\}/g, getTypeAlias(typeKey))
    .replace(/\{type\}/g, String(typeKey || '未分类'))
    .replace(/\{count\}/g, String(Number(count || 0)));
}

function saveCurrentTypeStylePreset(){
  ensureTypeStyleState();
  const key = getScopedTypeStyleStorageKey(state.currentCasePath || '.');
  const selectedTypeKeys = Array.from(state.selectedTypeKeys || []);
  const selectedSet = new Set(selectedTypeKeys);
  const styleMap = {};
  (state.typeOrder || []).forEach((typeKey, idx)=>{
    const style = getTypeStyle(typeKey) || buildDefaultTypeStyle(typeKey, idx);
    styleMap[typeKey] = {
      alias: String(style.alias || typeKey),
      nodeSize: Math.max(3, Math.min(28, Number(style.nodeSize) || 6.8)),
      nodeColor: normalizeHexColor(style.nodeColor, '#2563eb'),
      edgeWidth: Math.max(0.6, Math.min(12, Number(style.edgeWidth) || 2.0)),
      edgeColor: normalizeHexColor(style.edgeColor, '#2563eb'),
      visible: selectedSet.has(typeKey),
    };
  });
  return safeStorageSet(key, JSON.stringify({styles: styleMap, savedAt: Date.now()}));
}

function loadTypeStylePresetForCurrentCase(){
  const key = getScopedTypeStyleStorageKey(state.currentCasePath || '.');
  const raw = safeStorageGet(key);
  if(!raw) return false;
  let parsed = null;
  try{
    parsed = JSON.parse(raw);
  }catch(_err){
    return false;
  }
  if(!parsed || typeof parsed !== 'object' || !parsed.styles || typeof parsed.styles !== 'object') return false;
  if(!state.typeStyles || typeof state.typeStyles !== 'object') state.typeStyles = {};
  const visibleKeys = [];
  Object.keys(parsed.styles).forEach((typeKey, idx)=>{
    const src = parsed.styles[typeKey] || {};
    const base = buildDefaultTypeStyle(typeKey, idx);
    state.typeStyles[typeKey] = {
      alias: String(src.alias || base.alias || typeKey),
      nodeSize: Math.max(3, Math.min(28, Number(src.nodeSize) || base.nodeSize)),
      nodeColor: normalizeHexColor(src.nodeColor, base.nodeColor),
      edgeWidth: Math.max(0.6, Math.min(12, Number(src.edgeWidth) || base.edgeWidth)),
      edgeColor: normalizeHexColor(src.edgeColor, base.edgeColor),
    };
    if(src.visible !== false) visibleKeys.push(typeKey);
  });
  if(visibleKeys.length){
    state.selectedTypeKeys = new Set(visibleKeys);
  }
  return true;
}

function ensureTypeStyleState(){
  rebuildNodeTypeLookup();
  const keys = Array.from(new Set((state.edges || []).map(getEdgeTypeValue))).sort((a,b)=>a.localeCompare(b, 'zh-CN', {numeric:true}));
  state.typeOrder = keys;
  if(!state.typeStyles || typeof state.typeStyles !== 'object') state.typeStyles = {};
  keys.forEach((key, idx)=>{
    if(!state.typeStyles[key]) state.typeStyles[key] = buildDefaultTypeStyle(key, idx);
    const style = state.typeStyles[key];
    style.alias = String(style.alias || key);
    style.nodeSize = Number.isFinite(Number(style.nodeSize)) ? Math.max(3, Math.min(28, Number(style.nodeSize))) : buildDefaultTypeStyle(key, idx).nodeSize;
    style.edgeWidth = Number.isFinite(Number(style.edgeWidth)) ? Math.max(0.6, Math.min(12, Number(style.edgeWidth))) : buildDefaultTypeStyle(key, idx).edgeWidth;
    style.nodeColor = normalizeHexColor(style.nodeColor, buildDefaultTypeStyle(key, idx).nodeColor);
    style.edgeColor = normalizeHexColor(style.edgeColor, buildDefaultTypeStyle(key, idx).edgeColor);
  });
  const keySet = new Set(keys);
  state.selectedTypeKeys = new Set(Array.from(state.selectedTypeKeys || []).filter(k=>keySet.has(k)));
  if(state.selectedTypeKeys.size === 0){
    keys.forEach(k=>state.selectedTypeKeys.add(k));
  }
}

function getTypeStyle(typeKey){
  ensureTypeStyleState();
  return state.typeStyles[typeKey] || buildDefaultTypeStyle(typeKey, 0);
}

function getEdgeForceType(edge){
  const raw = String((edge && edge.layoutForceType) || '').trim().toLowerCase();
  if(raw === 'repel' || raw === 'none' || raw === 'attract') return raw;
  return 'attract';
}

function getEdgeForceWeight(edge){
  const raw = Number((edge && edge.layoutForceWeight) || 1);
  if(!Number.isFinite(raw)) return 1;
  return Math.max(0, Math.min(5, raw));
}

function isTypeVisible(typeKey){
  if(!state.typeOrder || state.typeOrder.length === 0) return true;
  return state.selectedTypeKeys.has(typeKey);
}

function hasPinnedFilterNode(edge){
  const s = normalizeName(edge && edge.source);
  const t = normalizeName(edge && edge.target);
  const ed = normalizeName(edge && edge.end);
  const hasDirectTargetOnlyGate = !!((s && _directTargetOnlyGateLookup.has(s)) || (t && _directTargetOnlyGateLookup.has(t)) || (ed && _directTargetOnlyGateLookup.has(ed)));
  if(hasDirectTargetOnlyGate) return false;
  return !!((s && _filterPinnedNodeLookup.has(s)) || (t && _filterPinnedNodeLookup.has(t)) || (ed && _filterPinnedNodeLookup.has(ed)));
}

function getVisibleEdgeIndices(){
  ensureTypeStyleState();
  const out = [];
  (state.edges || []).forEach((e, idx)=>{
    if(hasPinnedFilterNode(e) || isTypeVisible(getEdgeTypeValue(e, idx))) out.push(idx);
  });
  return out;
}

function buildVisibleGraphNodeSet(edgeIndices){
  const set = new Set();
  edgeIndices.forEach((idx)=>{
    const e = state.edges[idx];
    if(!e) return;
    const s = normalizeName(e.source);
    const t = normalizeName(e.target);
    const ed = normalizeName(e.end);
    [s, t, ed].forEach(name=>{ if(name && state.positions[name]) set.add(name); });
    const pair = getDirectAnchorNames(e);
    if(pair){
      if(pair.a && state.positions[pair.a]) set.add(pair.a);
      if(pair.b && state.positions[pair.b]) set.add(pair.b);
    }
  });
  return set;
}

function renderTypeStyleBox(){
  const host = document.getElementById('typeStyleBox');
  if(!host) return;
  ensureTypeStyleState();
  host.innerHTML = '';
  if(!state.typeOrder.length){
    const empty = document.createElement('div');
    empty.className = 'hint';
    empty.textContent = '当前无 type 数据。';
    host.appendChild(empty);
    return;
  }

  const head = document.createElement('div');
  head.className = 'typeStyleHead';
  head.innerHTML = '<span></span><span>type</span><span>替代文本</span><span>节点大小</span><span>节点颜色</span><span>边粗细</span><span>边颜色</span>';
  host.appendChild(head);

  state.typeOrder.forEach((typeKey)=>{
    const style = getTypeStyle(typeKey);
    const row = document.createElement('div');
    row.className = 'typeStyleRow';

    const chk = document.createElement('input');
    chk.type = 'checkbox';
    chk.checked = state.selectedTypeKeys.has(typeKey);
    chk.onchange = ()=>{
      if(chk.checked) state.selectedTypeKeys.add(typeKey);
      else state.selectedTypeKeys.delete(typeKey);
      if(state.selectedTypeKeys.size === 0){
        state.selectedNode = null;
        state.selectedEdgeIndex = null;
      }
      saveCurrentTypeStylePreset();
      renderTables();
      renderGraph();
    };

    const badge = document.createElement('span');
    badge.className = 'typeBadge';
    badge.title = typeKey;
    badge.textContent = typeKey;

    const aliasInput = document.createElement('input');
    aliasInput.type = 'text';
    aliasInput.value = String(style.alias || typeKey);
    aliasInput.placeholder = '例如: 关键节点';
    aliasInput.oninput = ()=>{
      style.alias = String(aliasInput.value || '').trim() || String(typeKey);
      saveCurrentTypeStylePreset();
      renderGraph();
    };

    const nodeSize = document.createElement('input');
    nodeSize.type = 'number';
    nodeSize.min = '3';
    nodeSize.max = '28';
    nodeSize.step = '0.2';
    nodeSize.value = String(style.nodeSize);
    nodeSize.oninput = ()=>{
      style.nodeSize = Math.max(3, Math.min(28, Number(nodeSize.value) || 6.8));
      saveCurrentTypeStylePreset();
      renderGraph();
    };

    const nodeColor = document.createElement('input');
    nodeColor.type = 'color';
    nodeColor.value = normalizeHexColor(style.nodeColor, '#2563eb');
    nodeColor.oninput = ()=>{
      style.nodeColor = normalizeHexColor(nodeColor.value, '#2563eb');
      saveCurrentTypeStylePreset();
      renderGraph();
    };

    const edgeWidth = document.createElement('input');
    edgeWidth.type = 'number';
    edgeWidth.min = '0.6';
    edgeWidth.max = '12';
    edgeWidth.step = '0.2';
    edgeWidth.value = String(style.edgeWidth);
    edgeWidth.oninput = ()=>{
      style.edgeWidth = Math.max(0.6, Math.min(12, Number(edgeWidth.value) || 2.0));
      saveCurrentTypeStylePreset();
      renderGraph();
    };

    const edgeColor = document.createElement('input');
    edgeColor.type = 'color';
    edgeColor.value = normalizeHexColor(style.edgeColor, '#2563eb');
    edgeColor.oninput = ()=>{
      style.edgeColor = normalizeHexColor(edgeColor.value, '#2563eb');
      saveCurrentTypeStylePreset();
      renderGraph();
    };

    row.appendChild(chk);
    row.appendChild(badge);
    row.appendChild(aliasInput);
    row.appendChild(nodeSize);
    row.appendChild(nodeColor);
    row.appendChild(edgeWidth);
    row.appendChild(edgeColor);
    host.appendChild(row);
  });
}

function renderTopologyLegend(nodeTypeMap, visibleNodeSet){
  const host = document.getElementById('topologyLegendNodeItems');
  if(!host) return;
  host.innerHTML = '';
  applyLegendTextFromState();
  state.lastLegendNodeItems = [];

  const typeCounts = new Map();
  visibleNodeSet.forEach((name)=>{
    const typeKey = nodeTypeMap.get(name) || '未分类';
    typeCounts.set(typeKey, (typeCounts.get(typeKey) || 0) + 1);
  });

  if(typeCounts.size === 0){
    const empty = document.createElement('div');
    empty.className = 'muted';
    empty.textContent = '节点: 无';
    host.appendChild(empty);
    return;
  }

  const orderedTypes = [];
  const orderSet = new Set();
  (state.typeOrder || []).forEach((typeKey)=>{
    if(typeCounts.has(typeKey)){
      orderedTypes.push(typeKey);
      orderSet.add(typeKey);
    }
  });
  Array.from(typeCounts.keys())
    .sort((a, b)=>a.localeCompare(b, 'zh-CN', {numeric: true}))
    .forEach((typeKey)=>{
      if(!orderSet.has(typeKey)) orderedTypes.push(typeKey);
    });

  orderedTypes.forEach((typeKey)=>{
    const row = document.createElement('div');
    const dot = document.createElement('span');
    dot.className = 'dot';
    const orderIdx = Math.max(0, (state.typeOrder || []).indexOf(typeKey));
    const style = (state.typeStyles && state.typeStyles[typeKey]) || buildDefaultTypeStyle(typeKey, orderIdx);
    dot.style.background = normalizeHexColor(style.nodeColor, '#2563eb');
    row.appendChild(dot);
    const count = typeCounts.get(typeKey);
    row.appendChild(document.createTextNode(formatLegendNodeLabel(typeKey, count)));
    host.appendChild(row);
    state.lastLegendNodeItems.push({
      typeKey,
      count,
      color: normalizeHexColor(style.nodeColor, '#2563eb'),
      text: formatLegendNodeLabel(typeKey, count),
    });
  });
}

function resetPointerInteraction(){
  if(activePointerCaptureEl && activePointerId !== null && typeof activePointerCaptureEl.releasePointerCapture === 'function'){
    try{ activePointerCaptureEl.releasePointerCapture(activePointerId); }catch(_){ }
  }
  const wasDragging = !!dragNode;
  const wasConnectDragging = !!connectDragFrom;
  const wasIndirectEdgeDragging = activeMode === 'drag-indirect-edge' || activeMode === 'drag-indirect-edge-mouse';
  dragNode = null;
  connectDragFrom = null;
  connectDragHoverTarget = null;
  dragIndirectEdgeIndex = null;
  dragIndirectEdgeNodes = null;
  dragIndirectStartVP = null;
  panMode = false;
  panStart = null;
  dragOffsetVP = null;
  dragMoved = false;
  activeMode = 'none';
  activePointerId = null;
  activePointerCaptureEl = null;
  pendingDragVP = null;
  pendingDragClient = null;
  pendingEdgePatchNode = null;
  if(dragFrameId){
    cancelAnimationFrame(dragFrameId);
    dragFrameId = 0;
  }
  if(edgePatchFrameId){
    cancelAnimationFrame(edgePatchFrameId);
    edgePatchFrameId = 0;
  }
  /* 拖拽结束后做一次全量渲染，同步所有节点/边的位置 */
  if(wasDragging || wasConnectDragging || wasIndirectEdgeDragging){
    activateForceLayoutWindow(FORCE_LAYOUT_ACTIVE_MS);
    renderTables();
    renderGraph();
  }
}

function scheduleEdgePatch(nodeName){
  pendingEdgePatchNode = nodeName;
  if(edgePatchFrameId) return;
  edgePatchFrameId = requestAnimationFrame(()=>{
    edgePatchFrameId = 0;
    const n = pendingEdgePatchNode;
    pendingEdgePatchNode = null;
    if(n) patchEdgesForNode(n);
  });
}

function scheduleDragUpdate(clientX, clientY, vp){
  pendingDragClient = {x: clientX, y: clientY};
  pendingDragVP = vp;
  if(dragFrameId) return;
  dragFrameId = requestAnimationFrame(()=>{
    dragFrameId = 0;
    if(!pendingDragClient) return;
    const c = pendingDragClient;
    const p = pendingDragVP;
    pendingDragClient = null;
    pendingDragVP = null;
    if(activeMode === 'drag-indirect-edge' || activeMode === 'drag-indirect-edge-mouse'){
      updateDraggingIndirectEdge(c.x, c.y, p);
      return;
    }
    updateDraggingNode(c.x, c.y, p);
  });
}

function beginHoverConnectDrag(nodeName, ev){
  if(ev.button !== 0) return;
  if(activeMode !== 'none') resetPointerInteraction();
  if(!state.positions[nodeName]) return;
  ev.stopPropagation();
  ev.preventDefault();
  connectDragFrom = nodeName;
  connectDragHoverTarget = null;
  hoverNodeForConnect = null;
  activeMode = 'connect-drag';
  activePointerId = ev.pointerId;
  if(ev.target && typeof ev.target.setPointerCapture === 'function'){
    try{
      ev.target.setPointerCapture(ev.pointerId);
      activePointerCaptureEl = ev.target;
    }catch(_){
      activePointerCaptureEl = null;
    }
  }
  const vp = toViewPoint(ev.clientX, ev.clientY);
  state.mouseView = vp;
  renderGraph();
}

function updateHoverNodeFromPoint(vp){
  if(state.viewMode === 'connect' || activeMode !== 'none') return;
  const hit = findNearestNodeAt(vp.x, vp.y, 24);
  const next = hit ? hit.node : null;
  if(next !== hoverNodeForConnect){
    hoverNodeForConnect = next;
    renderGraph();
  }
}

function updateHoverConnectDrag(vp){
  if(activeMode !== 'connect-drag' || !connectDragFrom) return;
  const hit = findNearestNodeAt(vp.x, vp.y, 18);
  const next = hit && hit.node !== connectDragFrom ? hit.node : null;
  if(next !== connectDragHoverTarget){
    connectDragHoverTarget = next;
    renderGraph();
    return;
  }
  const temp = interactionLayer.querySelector('line[data-connect-drag-preview="1"]');
  if(temp){
    const src = state.positions[connectDragFrom];
    const t = connectDragHoverTarget && state.positions[connectDragHoverTarget] ? state.positions[connectDragHoverTarget] : null;
    const tx = t ? t.x : vp.x;
    const ty = t ? t.y : vp.y;
    temp.setAttribute('x1', src.x); temp.setAttribute('y1', src.y);
    temp.setAttribute('x2', tx); temp.setAttribute('y2', ty);
  } else {
    renderGraph();
  }
}

function finishHoverConnectDrag(ev){
  if(activeMode !== 'connect-drag' || !connectDragFrom) return;
  const src = connectDragFrom;
  const target = connectDragHoverTarget;
  if(target && target !== src){
    const connectionType = ev && ev.shiftKey ? 'indirect' : 'direct';
    createEdgeBetween(src, target, {connectionType});
  }
  suppressNodeClickUntil = Date.now() + 150;
  resetPointerInteraction();
}

function updateDraggingNode(clientX, clientY, vpInput){
  if(!dragNode) return;
  const p = state.positions[dragNode];
  if(!p){ resetPointerInteraction(); return; }
  // 单次 toViewPoint：每个事件只转换一次坐标，避免微小累计偏差
  const vp = vpInput || toViewPoint(clientX, clientY);
  if(!dragOffsetVP){
    // 兜底：理论上拖拽开始时已计算完成
    dragOffsetVP = { x: p.x - vp.x, y: p.y - vp.y };
  }
  p.x = vp.x + dragOffsetVP.x;
  p.y = vp.y + dragOffsetVP.y;
  p.vx = 0;
  p.vy = 0;
  fastDragUpdate(dragNode);
}

function beginIndirectEdgeDrag(edgeIdx, ev, usePointer){
  if(ev.button !== 0) return;
  const edge = state.edges[edgeIdx];
  if(!edge || String(edge.ConnectionType || '').toLowerCase() !== 'indirect') return;
  if(activeMode !== 'none'){
    resetPointerInteraction();
  }
  ev.stopPropagation();
  ev.preventDefault();
  selectEdge(edgeIdx);
  const s = normalizeName(edge.source);
  const t = normalizeName(edge.target);
  const ed = normalizeName(edge.end);
  const names = [s, t, ed].filter((n, i, arr)=> !!n && state.positions[n] && arr.indexOf(n) === i);
  if(!names.length) return;
  dragIndirectEdgeIndex = edgeIdx;
  dragIndirectStartVP = toViewPoint(ev.clientX, ev.clientY);
  dragIndirectEdgeNodes = names.map(name=>({
    name,
    x: state.positions[name].x,
    y: state.positions[name].y,
  }));
  if(usePointer){
    activeMode = 'drag-indirect-edge';
    activePointerId = ev.pointerId;
    if(ev.target && typeof ev.target.setPointerCapture === 'function'){
      try{
        ev.target.setPointerCapture(ev.pointerId);
        activePointerCaptureEl = ev.target;
      }catch(_){
        activePointerCaptureEl = null;
      }
    }
  } else {
    activeMode = 'drag-indirect-edge-mouse';
    activePointerId = null;
  }
}

function updateDraggingIndirectEdge(clientX, clientY, vpInput){
  if(!dragIndirectEdgeNodes || !dragIndirectStartVP) return;
  const vp = vpInput || toViewPoint(clientX, clientY);
  const dx = vp.x - dragIndirectStartVP.x;
  const dy = vp.y - dragIndirectStartVP.y;
  for(let i=0;i<dragIndirectEdgeNodes.length;i++){
    const n = dragIndirectEdgeNodes[i];
    const p = state.positions[n.name];
    if(!p) continue;
    p.x = n.x + dx;
    p.y = n.y + dy;
    p.vx = 0;
    p.vy = 0;
    fastDragUpdate(n.name);
  }
}

/* 快速拖动更新：使用 DOM 缓存直接 patch 属性，不做 querySelector 也不重建边 */
function fastDragUpdate(nodeName){
  const p = state.positions[nodeName];
  if(!p) return;
  /* 用缓存的 DOM 引用更新节点 circle / text */
  const refs = _nodeCircleMap.get(nodeName);
  if(refs){
    refs.halo.setAttribute('cx', p.x); refs.halo.setAttribute('cy', p.y);
    refs.hit.setAttribute('cx', p.x);  refs.hit.setAttribute('cy', p.y);
    refs.circle.setAttribute('cx', p.x); refs.circle.setAttribute('cy', p.y);
    if(refs.text){
      refs.text.setAttribute('x', p.x + 8); refs.text.setAttribute('y', p.y - 8);
    }
    if(refs.hint){
      refs.hint.setAttribute('cx', p.x); refs.hint.setAttribute('cy', p.y);
    }
    if(refs.warnBg){
      refs.warnBg.setAttribute('cx', p.x + 12);
      refs.warnBg.setAttribute('cy', p.y - 14);
    }
    if(refs.warnText){
      refs.warnText.setAttribute('x', p.x + 12);
      refs.warnText.setAttribute('y', p.y - 10.2);
    }
  }
  /* 仅 patch 与该节点相关的边，不销毁/重建任何 DOM；并且按帧节流 */
  scheduleEdgePatch(nodeName);
}

/* 就地更新与 nodeName 相关的边的 x1/y1/x2/y2 */
function patchEdgesForNode(nodeName){
  const refs = _edgeRefsByNode.get(nodeName);
  if(!refs || refs.length===0) return;
  for(let i=0;i<refs.length;i++){
    const ed = refs[i];
    const e = state.edges[ed.edgeIdx];
    if(!e) continue;
    const s = ed.src, t = ed.tgt, endN = ed.end;
    const ctype = String(e.ConnectionType||'').toLowerCase();
    if(ed.mainLine && t && state.positions[t]){
      let x0 = null, y0 = null;
      let x1 = state.positions[t].x, y1 = state.positions[t].y;
      if(ctype === 'direct'){
        const mid = getDirectMidpoint(e);
        if(mid){
          x0 = mid.x;
          y0 = mid.y;
          if(ed.midNode){
            ed.midNode.setAttribute('cx', x0);
            ed.midNode.setAttribute('cy', y0);
          }
        }
      } else if(s && state.positions[s]){
        x0 = state.positions[s].x;
        y0 = state.positions[s].y;
      }
      if(x0 !== null){
        ed.mainLine.setAttribute('x1', x0);  ed.mainLine.setAttribute('y1', y0);
        ed.mainLine.setAttribute('x2', x1); ed.mainLine.setAttribute('y2', y1);
        if(ed.haloLine){
          ed.haloLine.setAttribute('x1', x0);  ed.haloLine.setAttribute('y1', y0);
          ed.haloLine.setAttribute('x2', x1);  ed.haloLine.setAttribute('y2', y1);
        }
      }
    }
    if(ed.dashLine && s && endN && state.positions[s] && state.positions[endN]){
      ed.dashLine.setAttribute('x1', state.positions[s].x);    ed.dashLine.setAttribute('y1', state.positions[s].y);
      ed.dashLine.setAttribute('x2', state.positions[endN].x); ed.dashLine.setAttribute('y2', state.positions[endN].y);
    }
  }
}

function findConnectHoverCandidate(vp){
  let candidate = null;
  for(const n of state.nodes){
    if(n === state.connectFrom) continue;
    const np = state.positions[n];
    if(!np) continue;
    const dx = np.x - vp.x;
    const dy = np.y - vp.y;
    if((dx*dx + dy*dy) <= 16*16){
      candidate = n;
      break;
    }
  }
  return candidate;
}

function updateConnectPreviewLine(){
  if(state.viewMode !== 'connect' || !state.connectFrom || !state.positions[state.connectFrom]) return;
  const src = state.positions[state.connectFrom];
  const targetPos = state.connectHoverTarget && state.positions[state.connectHoverTarget] ? state.positions[state.connectHoverTarget] : null;
  const tx = targetPos ? targetPos.x : state.mouseView.x;
  const ty = targetPos ? targetPos.y : state.mouseView.y;
  const temp = interactionLayer.querySelector('line[data-connect-preview="1"]');
  if(!temp){
    renderGraph();
    return;
  }
  temp.setAttribute('x1', src.x); temp.setAttribute('y1', src.y);
  temp.setAttribute('x2', tx);    temp.setAttribute('y2', ty);
}

function updateConnectHoverAndPreview(vp){
  if(state.viewMode !== 'connect' || !state.connectFrom) return;
  const candidate = findConnectHoverCandidate(vp);
  if(candidate !== state.connectHoverTarget){
    state.connectHoverTarget = candidate;
    renderGraph();
    return;
  }
  updateConnectPreviewLine();
}

function isNodeElementTarget(target){
  if(!(target instanceof Node)) return false;
  return nodeLayer.contains(target);
}

function isBackgroundTarget(target){
  return target === svg || target === viewport || target === edgeLayer || target === nodeLayer || target === interactionLayer;
}

function normalizeName(v){
  if(v===null || v===undefined) return '';
  const t = String(v).trim();
  if(!t || t.toLowerCase()==='nan' || t==='-1') return '';
  return t;
}

function generateNodeName(){
  let i = 1;
  while(state.nodes.includes(`新节点_${i}`)){
    i += 1;
  }
  return `新节点_${i}`;
}

function findNearestNodeAt(viewX, viewY, radius){
  let hit = null;
  let minD2 = radius * radius;
  for(const n of state.nodes){
    const p = state.positions[n];
    if(!p) continue;
    const dx = p.x - viewX;
    const dy = p.y - viewY;
    const d2 = dx*dx + dy*dy;
    if(d2 <= minD2){
      minD2 = d2;
      hit = n;
    }
  }
  return hit;
}

function createNodeAtView(viewX, viewY){
  const nodeName = generateNodeName();
  ensureNode(nodeName);
  state.positions[nodeName].x = viewX;
  state.positions[nodeName].y = viewY;
  state.positions[nodeName].vx = 0;
  state.positions[nodeName].vy = 0;
  selectNode(nodeName, null, null, false);
  return nodeName;
}

function startEdgeFromDrop(viewX, viewY){
  const sourceNode = findNearestNodeAt(viewX, viewY, 18) || state.selectedNode;
  if(!sourceNode){
    alert('请先在节点附近释放“边组件”，或先选中一个节点');
    return;
  }
  setViewMode('connect');
  state.connectFrom = sourceNode;
  selectNode(sourceNode, null, null, false);
  nodeMenuTitle.textContent = `连边起点: ${sourceNode}，请点击目标节点`; 
}

function ensureNode(name){
  const n = normalizeName(name);
  if(!n) return;
  if(!state.nodes.includes(n)){
    state.nodes.push(n);
    const fixed = state.fixedNodes[n];
    if(fixed){
      state.positions[n] = {x:fixed.x, y:fixed.y, vx:0, vy:0, fixed:true};
    } else {
      const r = 90 + Math.random()*120;
      const a = Math.random()*Math.PI*2;
      state.positions[n] = {x:600 + r*Math.cos(a), y:380 + r*Math.sin(a), vx:0, vy:0};
    }
  }
}

function tryStartNodeDrag(nodeName, isFixed, ev){
  if(ev.button !== 0){
    return;
  }
  if(activeMode !== 'none'){
    resetPointerInteraction();
  }
  const p = state.positions[nodeName];
  if(!p) return;
  const vp = toViewPoint(ev.clientX, ev.clientY);
  dragOffsetVP = { x: p.x - vp.x, y: p.y - vp.y };
  dragMoved = false;
  hideNodeMenu();
  dragNode = nodeName;
  panMode = false;
  panStart = null;
  activeMode = 'drag-node';
  activePointerId = ev.pointerId;
  if(ev.target && typeof ev.target.setPointerCapture === 'function'){
    try{
      ev.target.setPointerCapture(ev.pointerId);
      activePointerCaptureEl = ev.target;
    }catch(_){
      activePointerCaptureEl = null;
    }
  }
}

function startMouseNodeDrag(nodeName, ev){
  if(ev.button !== 0){
    return;
  }
  const p = state.positions[nodeName];
  if(!p) return;
  if(activeMode !== 'none'){
    resetPointerInteraction();
  }
  const vp = toViewPoint(ev.clientX, ev.clientY);
  dragOffsetVP = { x: p.x - vp.x, y: p.y - vp.y };
  dragMoved = false;
  hideNodeMenu();
  dragNode = nodeName;
  panMode = false;
  panStart = null;
  activeMode = 'drag-node-mouse';
  activePointerId = null;
}

function rebuildNodesFromEdges(){
  const set = new Set();
  state.edges.forEach(e=>{
    ['source','target','end'].forEach(k=>{ const n=normalizeName(e[k]); if(n) set.add(n); });
  });
  state.nodes = Array.from(set).sort((a,b)=>a.localeCompare(b,'zh-CN'));
  state.nodes.forEach(n=>{ if(!state.positions[n]) ensureNode(n); });
  Object.keys(state.positions).forEach(k=>{ if(!set.has(k)) delete state.positions[k]; });
}

function normalizeRawPositions(raw){
  const keys = Object.keys(raw || {});
  if(keys.length===0) return {};
  const pts = keys.map(k=>raw[k]).filter(p=>p && Number.isFinite(Number(p.x)) && Number.isFinite(Number(p.y)));
  if(pts.length===0) return {};
  const minX = Math.min(...pts.map(p=>Number(p.x))), maxX = Math.max(...pts.map(p=>Number(p.x)));
  const minY = Math.min(...pts.map(p=>Number(p.y))), maxY = Math.max(...pts.map(p=>Number(p.y)));
  const spanX = Math.max(maxX-minX, 1);
  const spanY = Math.max(maxY-minY, 1);
  const scale = Math.min(900/spanX, 620/spanY);
  const out = {};
  keys.forEach(k=>{
    const p = raw[k];
    if(!p) return;
    const x = 140 + (Number(p.x)-minX)*scale;
    const y = 90 + (maxY-Number(p.y))*scale;
    out[k] = {x,y};
  });
  return out;
}

function initializePositionsFromData(data){
  state.positions = {};
  const normalizedAll = normalizeRawPositions(data.positions || {});
  const normalizedFixed = normalizeRawPositions(data.fixedPositions || {});
  state.fixedNodes = normalizedFixed;

  state.nodes.forEach((n,i)=>{
    if(normalizedAll[n]){
      const f = normalizedFixed[n];
      state.positions[n] = {x: normalizedAll[n].x, y: normalizedAll[n].y, vx:0, vy:0, fixed: !!f};
      return;
    }

    let anchors = [];
    state.edges.forEach(e=>{
      const s = normalizeName(e.source), t = normalizeName(e.target), ed = normalizeName(e.end);
      if(s===n && normalizedAll[t]) anchors.push(normalizedAll[t]);
      if(t===n && normalizedAll[s]) anchors.push(normalizedAll[s]);
      if(ed===n && normalizedAll[s]) anchors.push(normalizedAll[s]);
      if(s===n && normalizedAll[ed]) anchors.push(normalizedAll[ed]);
    });

    if(anchors.length){
      const cx = anchors.reduce((a,p)=>a+p.x,0)/anchors.length;
      const cy = anchors.reduce((a,p)=>a+p.y,0)/anchors.length;
      const a = (i+1) * 0.9;
      state.positions[n] = {x: cx + 50*Math.cos(a), y: cy + 50*Math.sin(a), vx:0, vy:0};
    } else {
      const a = Math.PI*2*i/Math.max(state.nodes.length,1);
      state.positions[n] = {x:600 + 120*Math.cos(a), y:380 + 120*Math.sin(a), vx:0, vy:0};
    }
  });

  Object.keys(normalizedFixed).forEach(k=>{
    if(state.positions[k]){
      state.positions[k].x = normalizedFixed[k].x;
      state.positions[k].y = normalizedFixed[k].y;
      state.positions[k].fixed = true;
      state.positions[k].vx = 0;
      state.positions[k].vy = 0;
    }
  });
}

function getLayoutBounds(){
  return {minX: 110, maxX: 1090, minY: 80, maxY: 700, centerX: 600, centerY: 390};
}

function clearLayoutFixedFlags(){
  Object.values(state.positions || {}).forEach(p=>{
    if(!p) return;
    p.fixed = false;
    p.vx = 0;
    p.vy = 0;
  });
}

function applyCircleLayout(){
  const b = getLayoutBounds();
  const count = Math.max(state.nodes.length, 1);
  const radius = Math.max(120, Math.min((b.maxX - b.minX), (b.maxY - b.minY)) * 0.35);
  state.nodes.forEach((n, i)=>{
    ensureNode(n);
    const a = (Math.PI * 2 * i) / count;
    state.positions[n].x = b.centerX + radius * Math.cos(a);
    state.positions[n].y = b.centerY + radius * Math.sin(a);
    state.positions[n].vx = 0;
    state.positions[n].vy = 0;
    state.positions[n].fixed = false;
  });
}

function applyGridLayout(){
  const b = getLayoutBounds();
  if(!state.nodes.length) return;

  const adjacency = new Map();
  state.nodes.forEach(n=>adjacency.set(n, new Set()));
  state.edges.forEach(e=>{
    if(String(e.ConnectionType || '').toLowerCase() !== 'indirect') return;
    const s = normalizeName(e.source);
    const t = normalizeName(e.target);
    if(!s || !t || !adjacency.has(s) || !adjacency.has(t) || s===t) return;
    adjacency.get(s).add(t);
    adjacency.get(t).add(s);
  });

  const visited = new Set();
  const components = [];
  state.nodes.forEach(start=>{
    if(visited.has(start)) return;
    const queue = [start];
    visited.add(start);
    const group = [];
    while(queue.length){
      const cur = queue.shift();
      group.push(cur);
      (adjacency.get(cur) || []).forEach(next=>{
        if(visited.has(next)) return;
        visited.add(next);
        queue.push(next);
      });
    }
    group.sort((a,b)=>a.localeCompare(b,'zh-CN'));
    components.push(group);
  });

  components.sort((a,b)=>b.length-a.length);
  const rowCount = Math.max(1, components.length);
  const rowStep = rowCount > 1 ? (b.maxY - b.minY) / (rowCount - 1) : 0;

  components.forEach((group, rowIdx)=>{
    const y = rowCount > 1 ? (b.minY + rowIdx * rowStep) : b.centerY;
    const stepX = group.length > 1 ? (b.maxX - b.minX) / (group.length - 1) : 0;
    group.forEach((name, colIdx)=>{
      ensureNode(name);
      state.positions[name].x = group.length > 1 ? (b.minX + colIdx * stepX) : b.centerX;
      state.positions[name].y = y;
      state.positions[name].vx = 0;
      state.positions[name].vy = 0;
      state.positions[name].fixed = false;
    });
  });
}

function applyLayeredLayout(){
  const b = getLayoutBounds();
  const nodes = [...state.nodes];
  if(!nodes.length) return;
  const outMap = new Map();
  const inDegree = new Map();
  nodes.forEach(n=>{ outMap.set(n, []); inDegree.set(n, 0); });

  state.edges.forEach(e=>{
    const s = normalizeName(e.source);
    const t = normalizeName(e.target);
    if(!s || !t || s===t) return;
    if(!outMap.has(s) || !outMap.has(t)) return;
    outMap.get(s).push(t);
    inDegree.set(t, (inDegree.get(t) || 0) + 1);
  });

  const level = new Map();
  const queue = [];
  nodes.forEach(n=>{
    if((inDegree.get(n) || 0) === 0){
      level.set(n, 0);
      queue.push(n);
    }
  });
  if(!queue.length){
    level.set(nodes[0], 0);
    queue.push(nodes[0]);
  }

  while(queue.length){
    const cur = queue.shift();
    const curLv = level.get(cur) || 0;
    (outMap.get(cur) || []).forEach(next=>{
      const nextLv = Math.max(level.get(next) ?? 0, curLv + 1);
      if(!level.has(next) || nextLv > (level.get(next) || 0)){
        level.set(next, nextLv);
      }
      inDegree.set(next, Math.max(0, (inDegree.get(next) || 0) - 1));
      if((inDegree.get(next) || 0) === 0){
        queue.push(next);
      }
    });
  }

  nodes.forEach(n=>{
    if(!level.has(n)) level.set(n, 0);
  });

  const maxLv = Math.max(...Array.from(level.values()));
  const colCount = Math.max(1, maxLv + 1);
  const colStep = colCount > 1 ? (b.maxX - b.minX) / (colCount - 1) : 0;

  const buckets = new Map();
  nodes.forEach(n=>{
    const lv = level.get(n) || 0;
    if(!buckets.has(lv)) buckets.set(lv, []);
    buckets.get(lv).push(n);
  });

  Array.from(buckets.keys()).sort((a,b)=>a-b).forEach(lv=>{
    const group = buckets.get(lv) || [];
    group.sort((a,b)=>a.localeCompare(b,'zh-CN'));
    const yStep = group.length > 1 ? (b.maxY - b.minY) / (group.length - 1) : 0;
    group.forEach((name, idx)=>{
      ensureNode(name);
      state.positions[name].x = b.minX + lv * colStep;
      state.positions[name].y = group.length > 1 ? (b.minY + idx * yStep) : b.centerY;
      state.positions[name].vx = 0;
      state.positions[name].vy = 0;
      state.positions[name].fixed = false;
    });
  });
}

function applyBackboneLayout(){
  const b = getLayoutBounds();
  const backbone = new Set();
  state.edges.forEach(e=>{
    const c = String(e.ConnectionType || '').toLowerCase();
    if(c !== 'indirect') return;
    const s = normalizeName(e.source);
    const t = normalizeName(e.target);
    if(s) backbone.add(s);
    if(t) backbone.add(t);
  });
  if(!backbone.size){
    applyLayeredLayout();
    return;
  }

  const spine = Array.from(backbone).filter(n=>state.nodes.includes(n)).sort((a,b)=>a.localeCompare(b,'zh-CN'));
  const followers = state.nodes.filter(n=>!backbone.has(n));

  const spanX = b.maxX - b.minX;
  const stepX = spine.length > 1 ? spanX / (spine.length - 1) : 0;
  spine.forEach((n, idx)=>{
    ensureNode(n);
    state.positions[n].x = spine.length > 1 ? (b.minX + idx * stepX) : b.centerX;
    state.positions[n].y = b.centerY;
    state.positions[n].vx = 0;
    state.positions[n].vy = 0;
    state.positions[n].fixed = false;
  });

  const groups = new Map();
  spine.forEach(n=>groups.set(n, []));
  const unbound = [];
  followers.forEach(n=>{
    let anchor = null;
    for(const e of state.edges){
      const c = String(e.ConnectionType || '').toLowerCase();
      if(c !== 'direct') continue;
      const s = normalizeName(e.source);
      const t = normalizeName(e.target);
      const ed = normalizeName(e.end);
      if((s===n && t && backbone.has(t)) || (ed===n && t && backbone.has(t))){
        anchor = t;
        break;
      }
      if(t===n && s && backbone.has(s)){
        anchor = s;
        break;
      }
    }
    if(anchor && groups.has(anchor)) groups.get(anchor).push(n);
    else unbound.push(n);
  });

  groups.forEach((arr, anchor)=>{
    const c = state.positions[anchor];
    const count = arr.length;
    arr.forEach((n, idx)=>{
      ensureNode(n);
      const a = (Math.PI * 2 * idx) / Math.max(count, 1);
      const r = 90 + (idx % 3) * 16;
      state.positions[n].x = c.x + Math.cos(a) * r;
      state.positions[n].y = c.y + Math.sin(a) * r;
      state.positions[n].vx = 0;
      state.positions[n].vy = 0;
      state.positions[n].fixed = false;
    });
  });

  if(unbound.length){
    const cols = Math.max(1, Math.ceil(Math.sqrt(unbound.length)));
    const rows = Math.max(1, Math.ceil(unbound.length / cols));
    const minY = Math.min(b.maxY - 120, b.centerY + 140);
    const maxY = b.maxY;
    const stepUX = cols > 1 ? (b.maxX - b.minX) / (cols - 1) : 0;
    const stepUY = rows > 1 ? (maxY - minY) / (rows - 1) : 0;
    unbound.forEach((n, idx)=>{
      ensureNode(n);
      const col = idx % cols;
      const row = Math.floor(idx / cols);
      state.positions[n].x = b.minX + col * stepUX;
      state.positions[n].y = minY + row * stepUY;
      state.positions[n].vx = 0;
      state.positions[n].vy = 0;
      state.positions[n].fixed = false;
    });
  }
}

function applyConcentricLayout(){
  const b = getLayoutBounds();
  const core = new Set();
  state.edges.forEach(e=>{
    if(String(e.ConnectionType || '').toLowerCase() !== 'indirect') return;
    const s = normalizeName(e.source);
    const t = normalizeName(e.target);
    if(s) core.add(s);
    if(t) core.add(t);
  });
  if(!core.size){
    applyCircleLayout();
    return;
  }

  const inner = state.nodes.filter(n=>core.has(n)).sort((a,b)=>a.localeCompare(b,'zh-CN'));
  const outer = state.nodes.filter(n=>!core.has(n)).sort((a,b)=>a.localeCompare(b,'zh-CN'));

  const innerR = Math.min((b.maxX - b.minX), (b.maxY - b.minY)) * 0.25;
  inner.forEach((n, idx)=>{
    ensureNode(n);
    const a = (Math.PI * 2 * idx) / Math.max(inner.length, 1);
    state.positions[n].x = b.centerX + innerR * Math.cos(a);
    state.positions[n].y = b.centerY + innerR * Math.sin(a);
    state.positions[n].vx = 0;
    state.positions[n].vy = 0;
    state.positions[n].fixed = false;
  });

  const outerR = Math.min((b.maxX - b.minX), (b.maxY - b.minY)) * 0.42;
  outer.forEach((n, idx)=>{
    ensureNode(n);
    const a = (Math.PI * 2 * idx) / Math.max(outer.length, 1);
    state.positions[n].x = b.centerX + outerR * Math.cos(a);
    state.positions[n].y = b.centerY + outerR * Math.sin(a);
    state.positions[n].vx = 0;
    state.positions[n].vy = 0;
    state.positions[n].fixed = false;
  });
}

function syncLayoutModeButtons(){
  const el = document.getElementById('btnLayoutForce');
  if(el){
    el.classList.toggle('active', state.layoutMode === 'force');
  }
  setForceRefreshMode(state.forceRefreshMode || 'auto');
}

function applyLayoutMode(mode){
  if(mode !== 'force'){
    mode = 'force';
  }
  if(!state.nodes.length){
    if(mode === 'force'){
      activateForceLayoutWindow(FORCE_LAYOUT_ACTIVE_MS);
      const lockBtn = document.getElementById('btnLockLayout');
      if(lockBtn){
        lockBtn.textContent = '锁定布局: 关';
      }
    }
    state.layoutMode = mode;
    syncLayoutModeButtons();
    return;
  }

  if(mode === 'force'){
    clearLayoutFixedFlags();
    activateForceLayoutWindow(FORCE_LAYOUT_ACTIVE_MS);
    layoutTickCounter = 0;
    const lockBtn = document.getElementById('btnLockLayout');
    if(lockBtn){
      lockBtn.textContent = '锁定布局: 关';
    }
    syncLayoutModeButtons();
    renderGraph();
    return;
  }

  syncLayoutModeButtons();
  renderGraph();
}

function setStatus(){
  const edgeIndices = getVisibleEdgeIndices();
  const visibleNodes = buildVisibleGraphNodeSet(edgeIndices);
  document.getElementById('nodeStat').textContent = `节点 ${visibleNodes.size}/${state.nodes.length}`;
  const direct = edgeIndices.filter(idx=>String(state.edges[idx].ConnectionType||'').toLowerCase()==='direct').length;
  const indirect = edgeIndices.filter(idx=>String(state.edges[idx].ConnectionType||'').toLowerCase()==='indirect').length;
  document.getElementById('edgeStat').textContent = `边 ${edgeIndices.length}/${state.edges.length} | direct ${direct} | indirect ${indirect}`;
}

function renderTables(){
  ensureTypeStyleState();
  renderTypeStyleBox();
  const visibleEdgeIndices = getVisibleEdgeIndices();
  const visibleEdgeSet = new Set(visibleEdgeIndices);
  const visibleNodeSet = buildVisibleGraphNodeSet(visibleEdgeIndices);
  if(state.selectedEdgeIndex !== null && !visibleEdgeSet.has(state.selectedEdgeIndex)){
    state.selectedEdgeIndex = null;
  }
  if(state.selectedNode && !visibleNodeSet.has(state.selectedNode)){
    state.selectedNode = null;
  }

  const ntb = document.querySelector('#nodeTable tbody');
  ntb.innerHTML = '';
  state.nodes.forEach(n=>{
    if(!visibleNodeSet.has(n)) return;
    const tr = document.createElement('tr');
    if(state.selectedNode===n) tr.className = 'sel';
    tr.innerHTML = `<td>${n}</td>`;
    tr.onclick = ()=>{
      selectNode(n, null, null, false);
    };
    ntb.appendChild(tr);
  });

  const etb = document.querySelector('#edgeTable tbody');
  etb.innerHTML = '';
  const warnSet = new Set(state.directEndWarnIndices || []);
  visibleEdgeIndices.forEach((idx)=>{
    const e = state.edges[idx];
    const tr = document.createElement('tr');
    if(state.selectedEdgeIndex===idx) tr.className = 'sel';
    const warn = warnSet.has(idx) ? '<span class="warnMark" title="direct 缺少 end">❗</span>' : '';
    tr.innerHTML = `<td>${idx+1}${warn}</td><td>${e.source||''}</td><td>${e.target||''}</td><td>${e.end||''}</td><td>${e.ConnectionType||''}</td>`;
    tr.onclick = ()=>{
      selectEdge(idx);
    };
    etb.appendChild(tr);
  });
  setStatus();
}

function checkDirectEndWarnings(showMessage=true){
  const warns = [];
  state.edges.forEach((e, idx)=>{
    const conn = String(e.ConnectionType || '').trim().toLowerCase();
    if(conn !== 'direct') return;
    const endName = normalizeName(e.end);
    const endRaw = String(e.end || '').trim().toLowerCase();
    if(!endName || endRaw === 'none' || endRaw === 'null') warns.push(idx);
  });
  state.directEndWarnIndices = warns;
  renderTables();
  renderGraph();
}

function edgeColor(e, edgeIndex=null){
  const style = getTypeStyle(getEdgeTypeValue(e, edgeIndex));
  return style.edgeColor;
}

function edgeMainRatio(e){
  return 1.0;
}

function getDirectAnchorNames(e){
  const s = normalizeName(e.source);
  const endN = normalizeName(e.end);
  if(s && endN && state.positions[s] && state.positions[endN]){
    return {a: s, b: endN};
  }
  const t = normalizeName(e.target);
  if(s && t && state.positions[s] && state.positions[t]){
    return {a: s, b: t};
  }
  return null;
}

function getDirectMidpoint(e){
  const pair = getDirectAnchorNames(e);
  if(!pair) return null;
  return {
    x: (state.positions[pair.a].x + state.positions[pair.b].x) / 2,
    y: (state.positions[pair.a].y + state.positions[pair.b].y) / 2,
    a: pair.a,
    b: pair.b,
    key: pair.a < pair.b ? `${pair.a}__${pair.b}` : `${pair.b}__${pair.a}`,
  };
}

function applyTransform(){
  state.tx = 0;
  state.ty = 0;
  state.scale = 1;
  viewport.setAttribute('transform', 'translate(0,0) scale(1)');
}

function toViewPoint(clientX, clientY){
  // 与 minimal_drag_test 完全一致：屏幕坐标 -> SVG viewBox 坐标
  const ctm = svg.getScreenCTM();
  if(!ctm){
    return {x: clientX, y: clientY};
  }
  const p = svg.createSVGPoint();
  p.x = clientX;
  p.y = clientY;
  return p.matrixTransform(ctm.inverse());
}

function renderGraph(){
  ensureTypeStyleState();
  edgeLayer.innerHTML = '';
  nodeLayer.innerHTML = '';
  interactionLayer.innerHTML = '';
  _nodeCircleMap.clear();
  _edgeDOMList = [];
  _edgeRefsByNode.clear();
  const visibleEdgeIndices = getVisibleEdgeIndices();
  const visibleEdgeSet = new Set(visibleEdgeIndices);
  const visibleNodeSet = buildVisibleGraphNodeSet(visibleEdgeIndices);
  const nodeTypeMap = new Map();
  if(state.selectedEdgeIndex !== null && !visibleEdgeSet.has(state.selectedEdgeIndex)){
    state.selectedEdgeIndex = null;
  }
  if(state.selectedNode && !visibleNodeSet.has(state.selectedNode)){
    state.selectedNode = null;
  }

  const midNodeByKey = new Map();
  const liveWarns = [];
  visibleEdgeIndices.forEach((idx)=>{
    const e = state.edges[idx];
    const conn = String(e.ConnectionType || '').trim().toLowerCase();
    if(conn !== 'direct') return;
    const endName = normalizeName(e.end);
    const endRaw = String(e.end || '').trim().toLowerCase();
    if(!endName || endRaw === 'none' || endRaw === 'null') liveWarns.push(idx);
  });
  state.directEndWarnIndices = liveWarns;
  const warnSet = new Set(liveWarns);
  const warnNodeSet = new Set();
  warnSet.forEach((idx)=>{
    const e = state.edges[idx];
    if(!e) return;
    const t = normalizeName(e.target);
    const s = normalizeName(e.source);
    const ed = normalizeName(e.end);
    [s, t, ed].forEach((name)=>{
      if(name && state.positions[name]) warnNodeSet.add(name);
    });
  });

  visibleEdgeIndices.forEach((idx)=>{
    const e = state.edges[idx];
    const s = normalizeName(e.source), t = normalizeName(e.target), ed = normalizeName(e.end);
    const ctype = String(e.ConnectionType||'').toLowerCase();
    const typeKey = getEdgeTypeValue(e, idx);
    const typeStyle = getTypeStyle(typeKey);
    const baseEdgeWidth = Math.max(0.6, Number(typeStyle.edgeWidth) || 2.0);
    const typeNodeNames = isTypeZeroValue(typeKey) ? [s] : [s, t, ed];
    typeNodeNames.forEach((name)=>{
      if(name && !nodeTypeMap.has(name)) nodeTypeMap.set(name, typeKey);
    });
    let line = null;
    let haloLine = null;
    let midNode = null;
    let midA = null;
    let midB = null;
    let warnX = null;
    let warnY = null;
    if(s && t && state.positions[t]){
      let x1 = state.positions[t].x;
      let y1 = state.positions[t].y;
      let x0 = null;
      let y0 = null;
      if(ctype === 'direct'){
        const mid = getDirectMidpoint(e);
        if(mid){
          x0 = mid.x;
          y0 = mid.y;
          midA = mid.a;
          midB = mid.b;
          if(midNodeByKey.has(mid.key)){
            midNode = midNodeByKey.get(mid.key);
          } else {
            const m = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            m.setAttribute('cx', mid.x);
            m.setAttribute('cy', mid.y);
            m.setAttribute('r', '5.2');
            m.setAttribute('fill', '#ffffff');
            m.setAttribute('stroke', '#475569');
            m.setAttribute('stroke-width', '1.6');
            m.setAttribute('opacity', '0.95');
            m.style.pointerEvents = 'none';
            edgeLayer.appendChild(m);
            midNode = m;
            midNodeByKey.set(mid.key, m);
          }
        }
      } else if(s && state.positions[s]){
        x0 = state.positions[s].x;
        y0 = state.positions[s].y;
      }
      if(x0 === null || y0 === null) return;

      const ratio = edgeMainRatio(e);
      if(ratio < 1){
        x1 = x0 + (x1 - x0) * ratio;
        y1 = y0 + (y1 - y0) * ratio;
      }
      warnX = x0 + (x1 - x0) * 0.62;
      warnY = y0 + (y1 - y0) * 0.62;

      if(ctype === 'indirect'){
        haloLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        haloLine.setAttribute('x1', x0); haloLine.setAttribute('y1', y0);
        haloLine.setAttribute('x2', x1); haloLine.setAttribute('y2', y1);
        haloLine.setAttribute('stroke', '#93c5fd');
        haloLine.setAttribute('stroke-width', state.selectedEdgeIndex===idx ? String(baseEdgeWidth + 3.0) : String(baseEdgeWidth + 1.8));
        haloLine.setAttribute('stroke-linecap', 'round');
        haloLine.setAttribute('opacity', state.selectedEdgeIndex===idx ? '0.6' : '0.38');
        edgeLayer.appendChild(haloLine);
      }

      line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', x0); line.setAttribute('y1', y0);
      line.setAttribute('x2', x1); line.setAttribute('y2', y1);
      line.setAttribute('stroke', warnSet.has(idx) ? '#dc2626' : edgeColor(e));
      line.setAttribute('stroke-width', state.selectedEdgeIndex===idx ? String(baseEdgeWidth + 1.2) : String(baseEdgeWidth));
      line.setAttribute('stroke-linecap', 'round');
      if(ctype === 'direct'){
        line.setAttribute('stroke-dasharray', state.selectedEdgeIndex===idx ? '6 4' : '7 4');
      }
      line.setAttribute('opacity', ctype==='indirect' ? (state.selectedEdgeIndex===idx ? '1' : '0.98') : (state.selectedEdgeIndex===idx ? '0.9' : '0.68'));
      line.setAttribute('marker-end', ctype==='direct' ? 'url(#arrowDirect)' : 'url(#arrowIndirect)');
      line.style.cursor = ctype === 'indirect' ? 'grab' : 'pointer';
      line.onpointerdown = (ev)=>{
        if(ctype === 'indirect'){
          beginIndirectEdgeDrag(idx, ev, true);
          return;
        }
        ev.stopPropagation();
        ev.preventDefault();
        selectEdge(idx);
      };
      line.onmousedown = (ev)=>{
        if(ev.button !== 0) return;
        if(ctype !== 'indirect') return;
        if(!!window.PointerEvent) return;
        beginIndirectEdgeDrag(idx, ev, false);
      };
      edgeLayer.appendChild(line);

      if(warnSet.has(idx)){
        const warnHalo = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        warnHalo.setAttribute('cx', warnX);
        warnHalo.setAttribute('cy', warnY);
        warnHalo.setAttribute('r', '11.5');
        warnHalo.setAttribute('fill', '#dc2626');
        warnHalo.setAttribute('stroke', '#ffffff');
        warnHalo.setAttribute('stroke-width', '2.2');
        warnHalo.setAttribute('opacity', '0.98');
        warnHalo.style.pointerEvents = 'none';
        edgeLayer.appendChild(warnHalo);

        const warnText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        warnText.setAttribute('x', warnX);
        warnText.setAttribute('y', warnY + 5.8);
        warnText.setAttribute('text-anchor', 'middle');
        warnText.setAttribute('font-size', '16');
        warnText.setAttribute('font-weight', '800');
        warnText.setAttribute('fill', '#ffffff');
        warnText.style.pointerEvents = 'none';
        warnText.textContent = '!';
        edgeLayer.appendChild(warnText);
      }
    }
    let dline = null;
    if(s && ed && state.positions[s] && state.positions[ed]){
      dline = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      dline.setAttribute('x1', state.positions[s].x); dline.setAttribute('y1', state.positions[s].y);
      dline.setAttribute('x2', state.positions[ed].x); dline.setAttribute('y2', state.positions[ed].y);
      dline.setAttribute('stroke', warnSet.has(idx) ? '#dc2626' : '#6b7280');
      dline.setAttribute('stroke-width', '1.2');
      dline.setAttribute('stroke-dasharray', '4 4');
      dline.setAttribute('opacity', '0.7');
      edgeLayer.appendChild(dline);
    }
    /* 缓存边 DOM 引用 */
    const edgeRef = {mainLine: line || null, haloLine: haloLine || null, dashLine: dline, midNode: midNode || null, edgeIdx: idx, src: s, tgt: t, end: ed, midA, midB};
    _edgeDOMList.push(edgeRef);
    [s,t,ed].forEach(name=>{
      if(!name) return;
      if(!_edgeRefsByNode.has(name)) _edgeRefsByNode.set(name, []);
      _edgeRefsByNode.get(name).push(edgeRef);
    });
    [midA, midB].forEach(name=>{
      if(!name) return;
      if(!_edgeRefsByNode.has(name)) _edgeRefsByNode.set(name, []);
      _edgeRefsByNode.get(name).push(edgeRef);
    });
  });

  state.nodes.forEach(n=>{
    if(!visibleNodeSet.has(n)) return;
    const p = state.positions[n];
    const isFixed = !!(p && p.fixed);
    const isWarnNode = warnNodeSet.has(n);
    const nodeType = nodeTypeMap.get(n) || '未分类';
    const nodeStyle = getTypeStyle(nodeType);
    const nodeRadius = (state.selectedNode===n) ? (Math.max(3, Number(nodeStyle.nodeSize) || 6.8) + 1.6) : Math.max(3, Number(nodeStyle.nodeSize) || 6.8);
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('data-node-el', '1');
    g.setAttribute('data-node-name', n);

    const halo = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    const isSelected = state.selectedNode===n;
    const isConnectSource = (state.viewMode==='connect' && state.connectFrom===n) || (activeMode==='connect-drag' && connectDragFrom===n);
    const isConnectTarget = (state.viewMode==='connect' && state.connectHoverTarget===n && state.connectFrom!==n) || (activeMode==='connect-drag' && connectDragHoverTarget===n && connectDragFrom!==n);
    halo.setAttribute('cx', p.x); halo.setAttribute('cy', p.y); halo.setAttribute('r', Math.max(10, nodeRadius + 4));
    halo.setAttribute('fill', isSelected ? 'rgba(59,130,246,0.22)' : 'rgba(16,185,129,0.12)');
    halo.style.pointerEvents = 'none';

    const hit = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    hit.setAttribute('cx', p.x); hit.setAttribute('cy', p.y); hit.setAttribute('r', '24');
    hit.setAttribute('fill', 'rgba(0,0,0,0.001)');
    hit.setAttribute('pointer-events', 'all');
    hit.style.cursor = 'grab';
    hit.setAttribute('data-node-el', '1');

    const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    c.setAttribute('cx', p.x); c.setAttribute('cy', p.y); c.setAttribute('r', nodeRadius);
    c.setAttribute('fill', isWarnNode ? '#dc2626' : (isFixed ? '#b91c1c' : nodeStyle.nodeColor));
    c.setAttribute('stroke', isWarnNode ? '#7f1d1d' : (isConnectTarget ? '#60a5fa' : '#ffffff'));
    c.setAttribute('stroke-width', isConnectTarget ? '2.2' : '1.4');
    c.style.cursor = 'grab';
    c.setAttribute('data-node-el', '1');
    c.style.pointerEvents = 'none';

    const beginNodeDrag = (ev)=>{
      if(ev.type === 'mousedown' && !!window.PointerEvent){
        return;
      }
      ev.stopPropagation();
      ev.preventDefault();
      state.selectedNode = n;
      fillNodeForm(n);
      fillRelatedEdgeByNode(n);
      if(ev.type === 'pointerdown'){
        tryStartNodeDrag(n, isFixed, ev);
      } else {
        startMouseNodeDrag(n, ev);
      }
    };

    hit.onpointerdown = beginNodeDrag;
    hit.onmousedown = beginNodeDrag;

    const useCompactText = isLargeGraphMode() && state.selectedNode !== n && hoverNodeForConnect !== n;
    const showText = !!state.showNodeLabels && !useCompactText;
    let text = null;
    if(showText){
      text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', p.x + 8); text.setAttribute('y', p.y - 8);
      text.setAttribute('font-size', '12');
      text.setAttribute('fill', '#111827');
      text.setAttribute('font-weight', state.selectedNode===n ? '700' : '500');
      text.style.cursor = 'grab';
      text.setAttribute('data-node-el', '1');
      text.textContent = n;
      text.style.pointerEvents = 'none';
    }

    g.onclick = (ev)=>{
      ev.stopPropagation();
      if(Date.now() < suppressNodeClickUntil){
        return;
      }
      if(state.viewMode === 'connect'){
        handleConnectClick(n, ev);
      } else {
        selectNode(n, null, null, false);
      }
    };

    g.oncontextmenu = (ev)=>{
      ev.preventDefault();
      ev.stopPropagation();
      selectNode(n, ev.clientX, ev.clientY, true);
    };

    g.appendChild(halo);
    g.appendChild(hit);
    g.appendChild(c);
    if(text) g.appendChild(text);

    let nodeWarnBg = null;
    let nodeWarnText = null;
    if(isWarnNode){
      nodeWarnBg = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      nodeWarnBg.setAttribute('cx', p.x + 12);
      nodeWarnBg.setAttribute('cy', p.y - 14);
      nodeWarnBg.setAttribute('r', '8.8');
      nodeWarnBg.setAttribute('fill', '#dc2626');
      nodeWarnBg.setAttribute('stroke', '#ffffff');
      nodeWarnBg.setAttribute('stroke-width', '2');
      nodeWarnBg.style.pointerEvents = 'none';

      nodeWarnText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      nodeWarnText.setAttribute('x', p.x + 12);
      nodeWarnText.setAttribute('y', p.y - 10.2);
      nodeWarnText.setAttribute('text-anchor', 'middle');
      nodeWarnText.setAttribute('font-size', '13');
      nodeWarnText.setAttribute('font-weight', '800');
      nodeWarnText.setAttribute('fill', '#ffffff');
      nodeWarnText.style.pointerEvents = 'none';
      nodeWarnText.textContent = '!';

      g.appendChild(nodeWarnBg);
      g.appendChild(nodeWarnText);
    }

    if(hoverNodeForConnect===n && activeMode==='none' && state.viewMode!=='connect'){
      const handle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      handle.setAttribute('cx', p.x + 14);
      handle.setAttribute('cy', p.y - 14);
      handle.setAttribute('r', '7');
      handle.setAttribute('fill', 'rgba(59,130,246,0.24)');
      handle.setAttribute('stroke', 'rgba(59,130,246,0.9)');
      handle.setAttribute('stroke-width', '1.4');
      handle.style.cursor = 'crosshair';
      handle.setAttribute('data-node-el', '1');
      handle.onpointerdown = (ev)=> beginHoverConnectDrag(n, ev);
      g.appendChild(handle);

      const delHandle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      delHandle.setAttribute('cx', p.x + 14);
      delHandle.setAttribute('cy', p.y + 14);
      delHandle.setAttribute('r', '7');
      delHandle.setAttribute('fill', 'rgba(220,38,38,0.22)');
      delHandle.setAttribute('stroke', 'rgba(220,38,38,0.9)');
      delHandle.setAttribute('stroke-width', '1.4');
      delHandle.style.cursor = 'pointer';
      delHandle.setAttribute('data-node-el', '1');
      delHandle.onpointerdown = (ev)=>{
        ev.stopPropagation();
        ev.preventDefault();
        deleteNode(n, {confirmDelete: false});
      };
      g.appendChild(delHandle);

      const delMark = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      delMark.setAttribute('x1', p.x + 10);
      delMark.setAttribute('y1', p.y + 14);
      delMark.setAttribute('x2', p.x + 18);
      delMark.setAttribute('y2', p.y + 14);
      delMark.setAttribute('stroke', 'rgba(220,38,38,0.95)');
      delMark.setAttribute('stroke-width', '1.6');
      delMark.setAttribute('stroke-linecap', 'round');
      delMark.style.pointerEvents = 'none';
      g.appendChild(delMark);
    }

    let hintEl = null;
    if(isConnectSource){
      const hint = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      hint.setAttribute('cx', p.x); hint.setAttribute('cy', p.y);
      hint.setAttribute('r', '12');
      hint.setAttribute('fill', 'rgba(245,158,11,0.16)');
      hint.setAttribute('stroke', 'rgba(245,158,11,0.9)');
      hint.setAttribute('stroke-width', '1.2');
      hint.setAttribute('data-node-el', '1');
      hint.style.pointerEvents = 'none';
      g.appendChild(hint);
      hintEl = hint;
    }

    /* 缓存节点 DOM 引用，拖拽时直接 patch */
    _nodeCircleMap.set(n, {halo, hit, circle: c, text, hint: hintEl, warnBg: nodeWarnBg, warnText: nodeWarnText});

    nodeLayer.appendChild(g);
  });

  if(state.viewMode === 'connect' && state.connectFrom && state.positions[state.connectFrom]){
    const src = state.positions[state.connectFrom];
    const targetPos = state.connectHoverTarget && state.positions[state.connectHoverTarget] ? state.positions[state.connectHoverTarget] : null;
    const tx = targetPos ? targetPos.x : state.mouseView.x;
    const ty = targetPos ? targetPos.y : state.mouseView.y;

    const temp = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    temp.setAttribute('x1', src.x); temp.setAttribute('y1', src.y);
    temp.setAttribute('x2', tx); temp.setAttribute('y2', ty);
    temp.setAttribute('stroke', 'rgba(59,130,246,0.85)');
    temp.setAttribute('stroke-width', '2.2');
    temp.setAttribute('stroke-dasharray', '6 5');
    temp.setAttribute('marker-end', 'url(#arrowPreview)');
    temp.setAttribute('data-connect-preview', '1');
    interactionLayer.appendChild(temp);
  }

  if(activeMode === 'connect-drag' && connectDragFrom && state.positions[connectDragFrom]){
    const src = state.positions[connectDragFrom];
    const targetPos = connectDragHoverTarget && state.positions[connectDragHoverTarget] ? state.positions[connectDragHoverTarget] : null;
    const tx = targetPos ? targetPos.x : state.mouseView.x;
    const ty = targetPos ? targetPos.y : state.mouseView.y;

    const temp2 = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    temp2.setAttribute('x1', src.x); temp2.setAttribute('y1', src.y);
    temp2.setAttribute('x2', tx); temp2.setAttribute('y2', ty);
    temp2.setAttribute('stroke', 'rgba(59,130,246,0.78)');
    temp2.setAttribute('stroke-width', '2.0');
    temp2.setAttribute('stroke-dasharray', '5 4');
    temp2.setAttribute('marker-end', 'url(#arrowPreview)');
    temp2.setAttribute('data-connect-drag-preview', '1');
    interactionLayer.appendChild(temp2);
  }

  renderTopologyLegend(nodeTypeMap, visibleNodeSet);

  applyTransform();
}

function tickLayout(){
  if(state.layoutLocked || isInteractionActive()){
    return;
  }
  if(state.forceRefreshMode === 'manual'){
    if(forceManualRefreshSteps <= 0){
      return;
    }
    forceManualRefreshSteps -= 1;
  }
  if(isForceLayoutWindowExpired()){
    state.layoutLocked = true;
    const lockBtn = document.getElementById('btnLockLayout');
    if(lockBtn){
      lockBtn.textContent = '锁定布局: 开';
    }
    return;
  }
  const bounds = getLayoutBounds();
  const repulsion = 12000;
  const spring = 0.010;
  const ideal = 64;
  const damping = 0.90;

  const autoFrozen = new Set();
  const directFollowers = new Set();
  const directAnchorMap = new Map();
  const directMidGroups = new Map();

  const edgeTypeIs4 = (edge)=>{
    const raw = String((edge && edge.type) || '').trim();
    if(!raw) return false;
    const asNum = Number(raw);
    if(Number.isFinite(asNum)) return asNum === 4;
    return raw === '4';
  };

  state.edges.forEach(e=>{
    const ctype = String(e.ConnectionType || '').toLowerCase();
    const s = normalizeName(e.source);
    const t = normalizeName(e.target);
    const ed = normalizeName(e.end);

    if(edgeTypeIs4(e)){
      if(s && state.positions[s]) autoFrozen.add(s);
      if(t && state.positions[t]) autoFrozen.add(t);
      if(ed && state.positions[ed]) autoFrozen.add(ed);
    }

    if(ctype === 'indirect'){
      if(s && state.positions[s]) autoFrozen.add(s);
      if(t && state.positions[t]) autoFrozen.add(t);
      return;
    }
    if(ctype === 'direct' && t && state.positions[t]){
      const mid = getDirectMidpoint(e);
      if(mid){
        directFollowers.add(t);
        if(!directAnchorMap.has(t)) directAnchorMap.set(t, []);
        directAnchorMap.get(t).push(mid);
        if(!directMidGroups.has(mid.key)){
          directMidGroups.set(mid.key, {mid, nodes: new Set()});
        }
        directMidGroups.get(mid.key).nodes.add(t);
      }
    }
  });

  const isFrozenNode = (name)=>{
    if(dragNode === name) return true;
    const p = state.positions[name];
    if(!p) return true;
    return !!p.fixed || autoFrozen.has(name);
  };

  const edgeIndices = getVisibleEdgeIndices();
  const visibleNodeSet = buildVisibleGraphNodeSet(edgeIndices);
  const activeNodes = state.nodes.filter(n=>visibleNodeSet.has(n) && state.positions[n]);

  for(const n of activeNodes){
    const p = state.positions[n];
    if(!p) continue;
    p.vx = p.vx || 0; p.vy = p.vy || 0;
  }

  if(activeNodes.length > LARGE_GRAPH_NODE_THRESHOLD){
    const sortedByX = activeNodes.slice().sort((na, nb)=>state.positions[na].x - state.positions[nb].x);
    const neighborLimit = 26;
    for(let i=0;i<sortedByX.length;i++){
      const ni = sortedByX[i];
      for(let j=i+1; j<sortedByX.length && j<=i + neighborLimit; j++){
        const nj = sortedByX[j];
        const a = state.positions[ni], b = state.positions[nj];
        const dx = a.x - b.x, dy = a.y - b.y;
        const d2 = Math.max(dx*dx + dy*dy, 90);
        const f = (repulsion * 0.82) / d2;
        const dist = Math.sqrt(d2);
        const fx = (dx/dist) * f, fy = (dy/dist) * f;
        if(!isFrozenNode(ni)){ a.vx += fx; a.vy += fy; }
        if(!isFrozenNode(nj)){ b.vx -= fx; b.vy -= fy; }
      }
    }
  } else {
    for(let i=0;i<activeNodes.length;i++){
      for(let j=i+1;j<activeNodes.length;j++){
        const ni = activeNodes[i], nj = activeNodes[j];
        const a = state.positions[ni], b = state.positions[nj];
        const dx = a.x - b.x, dy = a.y - b.y;
        const d2 = Math.max(dx*dx + dy*dy, 50);
        const f = repulsion / d2;
        const dist = Math.sqrt(d2);
        const fx = (dx/dist) * f, fy = (dy/dist) * f;
        if(!isFrozenNode(ni)){ a.vx += fx; a.vy += fy; }
        if(!isFrozenNode(nj)){ b.vx -= fx; b.vy -= fy; }
      }
    }
  }

  edgeIndices.forEach((edgeIdx)=>{
    const e = state.edges[edgeIdx];
    const s = normalizeName(e.source), t = normalizeName(e.target);
    if(!s || !t || !state.positions[s] || !state.positions[t]) return;
    const forceType = getEdgeForceType(e);
    const forceWeight = getEdgeForceWeight(e);
    if(forceType === 'none' || forceWeight <= 0) return;

    const a = state.positions[s], b = state.positions[t];
    const dx = b.x-a.x, dy = b.y-a.y;
    const dist = Math.max(Math.sqrt(dx*dx + dy*dy), 1);
    let f = 0;
    if(forceType === 'repel'){
      const repelTarget = ideal * 1.15;
      const repelStretch = repelTarget - dist;
      if(repelStretch <= 0) return;
      f = -spring * repelStretch * forceWeight;
    } else {
      const stretch = dist - ideal;
      f = spring * stretch * forceWeight;
    }
    const fx = (dx/dist)*f, fy = (dy/dist)*f;
    if(!isFrozenNode(s)){ a.vx += fx; a.vy += fy; }
    if(!isFrozenNode(t)){ b.vx -= fx; b.vy -= fy; }
  });

  directAnchorMap.forEach((anchors, node)=>{
    const p = state.positions[node];
    if(!p || isFrozenNode(node) || !anchors.length) return;
    const ax = anchors.reduce((sum, a)=>sum + a.x, 0) / anchors.length;
    const ay = anchors.reduce((sum, a)=>sum + a.y, 0) / anchors.length;
    p.vx += (ax - p.x) * 0.085;
    p.vy += (ay - p.y) * 0.085;
    const dx = p.x - ax;
    const dy = p.y - ay;
    const dist = Math.sqrt(dx*dx + dy*dy);
    const maxDist = 120;
    if(dist > maxDist && dist > 0){
      p.x = ax + (dx / dist) * maxDist;
      p.y = ay + (dy / dist) * maxDist;
      p.vx *= 0.5;
      p.vy *= 0.5;
    }
  });

  const desiredByNode = new Map();
  directMidGroups.forEach((group, key)=>{
    const candidates = Array.from(group.nodes)
      .filter(n=>state.positions[n] && !isFrozenNode(n))
      .sort((a,b)=>a.localeCompare(b, 'zh-CN'));
    if(!candidates.length) return;

    const count = candidates.length;
    const baseAngle = ((key.length % 23) / 23) * Math.PI * 2;
    const baseRadius = Math.min(92, 28 + count * 4);

    candidates.forEach((node, idx)=>{
      const angle = baseAngle + (Math.PI * 2 * idx) / Math.max(count, 1);
      const radius = baseRadius + (idx % 2) * 8;
      const tx = group.mid.x + Math.cos(angle) * radius;
      const ty = group.mid.y + Math.sin(angle) * radius;
      if(!desiredByNode.has(node)) desiredByNode.set(node, []);
      desiredByNode.get(node).push({x: tx, y: ty});
    });
  });

  desiredByNode.forEach((targets, node)=>{
    const p = state.positions[node];
    if(!p || isFrozenNode(node) || !targets.length) return;
    const tx = targets.reduce((sum, t)=>sum + t.x, 0) / targets.length;
    const ty = targets.reduce((sum, t)=>sum + t.y, 0) / targets.length;
    p.vx += (tx - p.x) * 0.12;
    p.vy += (ty - p.y) * 0.12;
  });

  const directAnchorCenter = new Map();
  directAnchorMap.forEach((anchors, node)=>{
    if(!anchors || !anchors.length) return;
    const ax = anchors.reduce((sum, a)=>sum + a.x, 0) / anchors.length;
    const ay = anchors.reduce((sum, a)=>sum + a.y, 0) / anchors.length;
    directAnchorCenter.set(node, {x: ax, y: ay});
  });

  const followerNodes = Array.from(directFollowers).filter(n=>state.positions[n] && !isFrozenNode(n));
  const followerMinGap = 44;
  for(let i=0;i<followerNodes.length;i++){
    for(let j=i+1;j<followerNodes.length;j++){
      const ni = followerNodes[i], nj = followerNodes[j];
      const ai = directAnchorCenter.get(ni), aj = directAnchorCenter.get(nj);
      if(ai && aj){
        const adx = ai.x - aj.x;
        const ady = ai.y - aj.y;
        if((adx*adx + ady*ady) > (180*180)) continue;
      }

      const a = state.positions[ni], b = state.positions[nj];
      const dx = a.x - b.x, dy = a.y - b.y;
      const d2 = Math.max(dx*dx + dy*dy, 1);
      const dist = Math.sqrt(d2);
      const ux = dx / dist, uy = dy / dist;

      const repel = 2400 / Math.max(d2, 90);
      a.vx += ux * repel;
      a.vy += uy * repel;
      b.vx -= ux * repel;
      b.vy -= uy * repel;

      const overlap = followerMinGap - dist;
      if(overlap > 0){
        const push = overlap * 0.22;
        a.vx += ux * push;
        a.vy += uy * push;
        b.vx -= ux * push;
        b.vy -= uy * push;
      }
    }
  }

  activeNodes.forEach(n=>{
    const p = state.positions[n];
    if(dragNode===n){
      p.vx = 0;
      p.vy = 0;
      return;
    }
    if(isFrozenNode(n)){
      p.vx = 0;
      p.vy = 0;
      return;
    }

    const anchor = directAnchorCenter.get(n);
    if(anchor){
      p.vx += (anchor.x - p.x) * 0.020;
      p.vy += (anchor.y - p.y) * 0.020;
      const dxA = p.x - anchor.x;
      const dyA = p.y - anchor.y;
      const dA = Math.sqrt(dxA*dxA + dyA*dyA);
      const maxAroundAnchor = 165;
      if(dA > maxAroundAnchor && dA > 0){
        p.x = anchor.x + (dxA / dA) * maxAroundAnchor;
        p.y = anchor.y + (dyA / dA) * maxAroundAnchor;
        p.vx *= 0.5;
        p.vy *= 0.5;
      }
    }

    p.vx *= damping; p.vy *= damping;
    p.x += Math.max(Math.min(p.vx, 5), -5);
    p.y += Math.max(Math.min(p.vy, 5), -5);

    p.x = Math.max(bounds.minX, Math.min(bounds.maxX, p.x));
    p.y = Math.max(bounds.minY, Math.min(bounds.maxY, p.y));
  });

  /* 如果正在拖拽节点，跳过全量渲染，仅由 pointermove 驱动快速更新 */
  if(!dragNode){
    layoutTickCounter += 1;
    if(!isLargeGraphMode() || (layoutTickCounter % LARGE_GRAPH_RENDER_SKIP) === 0){
      renderGraph();
    }
  }
}

function edgeFormToObj(){
  const e = {};
  e.source = document.getElementById('eSource').value.trim();
  e.target = document.getElementById('eTarget').value.trim();
  e.end = document.getElementById('eEnd').value.trim();
  e.ConnectionType = document.getElementById('eConn').value;
  e.id = document.getElementById('eId').value.trim();
  e.type = document.getElementById('eType').value.trim();
  e.maxFlow = document.getElementById('eMaxFlow').value.trim();
  e.layoutForceType = String(document.getElementById('eForceType').value || 'attract').trim().toLowerCase();
  e.layoutForceWeight = document.getElementById('eForceWeight').value.trim();
  return e;
}

function fillEdgeForm(e){
  document.getElementById('eSource').value = e.source || '';
  document.getElementById('eTarget').value = e.target || '';
  document.getElementById('eEnd').value = e.end || '';
  document.getElementById('eConn').value = (e.ConnectionType || 'direct').toLowerCase()==='indirect' ? 'indirect':'direct';
  document.getElementById('eId').value = e.id || '';
  document.getElementById('eType').value = e.type || '';
  document.getElementById('eMaxFlow').value = e.maxFlow || '';
  document.getElementById('eForceType').value = getEdgeForceType(e);
  document.getElementById('eForceWeight').value = String(getEdgeForceWeight(e));
}

function fillNodeForm(nodeName){
  document.getElementById('nodeName').value = nodeName || '';
  document.getElementById('nodeRename').value = nodeName || '';
}

function fillRelatedEdgeByNode(nodeName){
  const n = normalizeName(nodeName);
  if(!n){
    state.selectedEdgeIndex = null;
    return;
  }
  const idx = state.edges.findIndex(e => normalizeName(e.source)===n || normalizeName(e.target)===n || normalizeName(e.end)===n);
  if(idx >= 0){
    state.selectedEdgeIndex = idx;
    fillEdgeForm(state.edges[idx]);
  }
}

function setViewMode(mode){
  state.viewMode = mode;
  if(mode !== 'connect'){
    state.connectFrom = null;
    state.connectHoverTarget = null;
  }
  renderGraph();
}

function askEndNodeForDirect(defaultValue=''){
  return normalizeName(prompt('direct 连线必须填写 end 节点，请输入 end 节点名称:', defaultValue || '') || '');
}

function createEdgeBetween(sourceNode, targetNode, options={}){
  const connRaw = options.connectionType || document.getElementById('eConn').value || 'direct';
  const conn = String(connRaw).toLowerCase()==='indirect' ? 'indirect' : 'direct';
  let endNode = normalizeName(options.endNode || '') || '';
  if(conn === 'direct' && !endNode){
    endNode = askEndNodeForDirect('');
    if(!endNode){
      return;
    }
  }
  const newEdge = normalizeEdge({
    source: sourceNode,
    target: targetNode,
    end: endNode,
    ConnectionType: conn,
  });
  ensureNode(sourceNode);
  ensureNode(targetNode);
  if(endNode) ensureNode(endNode);
  state.edges.push(newEdge);
  rebuildNodesFromEdges();
  selectEdge(state.edges.length - 1);
}

function handleConnectClick(nodeName, ev){
  const node = normalizeName(nodeName);
  if(!node) return;
  if(!state.connectFrom){
    state.connectFrom = node;
    state.connectHoverTarget = null;
    selectNode(node, null, null, false);
    nodeMenuTitle.textContent = `连边起点: ${node}，请再点一个节点`;
    renderGraph();
    return;
  }
  if(state.connectFrom === node){
    state.connectFrom = null;
    state.connectHoverTarget = null;
    renderGraph();
    return;
  }
  const connectionType = ev && ev.shiftKey ? 'indirect' : 'direct';
  createEdgeBetween(state.connectFrom, node, {connectionType});
  state.connectFrom = null;
  state.connectHoverTarget = null;
}

function selectNode(nodeName, clientX, clientY, showMenu){
  state.selectedNode = nodeName;
  fillNodeForm(nodeName);
  fillRelatedEdgeByNode(nodeName);
  renderTables();
  renderGraph();
  if(showMenu && clientX!==null && clientY!==null){
    showNodeMenu(nodeName, clientX, clientY);
  }
}

function selectEdge(edgeIndex){
  if(edgeIndex===null || edgeIndex<0 || edgeIndex>=state.edges.length) return;
  state.selectedEdgeIndex = edgeIndex;
  const edge = state.edges[edgeIndex];
  fillEdgeForm(edge);
  const primaryNode = normalizeName(edge.source) || normalizeName(edge.target) || normalizeName(edge.end);
  if(primaryNode){
    state.selectedNode = primaryNode;
    fillNodeForm(primaryNode);
  }
  renderTables();
  renderGraph();
}

function normalizeEdge(raw){
  const base = {};
  const allCols = [
    'source','target','end','ConnectionType','stake','canal','id','delaytime','pool_Width','pool_Length','pool_m','pool_hTarget','pool_h_ic',
    'max_h','min_h','type','maxFlow','minFlow','Flow_ic','seepageC','forceFlow','forceStage','upstream_elevation','mile_stage','gate_bottom_elevation','pool_slope','pool_manning','level1',
    'layoutForceType','layoutForceWeight'
  ];
  allCols.forEach(k=>base[k]='');
  Object.keys(raw||{}).forEach(k=>{ if(k in base) base[k] = raw[k] ?? ''; });
  base.ConnectionType = (String(base.ConnectionType||'').toLowerCase()==='indirect') ? 'indirect' : 'direct';
  return base;
}

function normalizeCasePath(raw){
  const text = String(raw || '').trim().replace(/\\/g, '/');
  if(!text || text === '.') return '.';
  return text.replace(/^\/+|\/+$/g, '') || '.';
}

function casePathJoin(relPath){
  const rel = String(relPath || '').trim().replace(/^\/+/, '');
  const casePath = normalizeCasePath(state.currentCasePath || '.');
  if(casePath === '.') return rel;
  return casePath + '/' + rel;
}

function scopePathToCurrentCase(rawPath){
  const text = String(rawPath || '').trim().replace(/\\/g, '/');
  if(!text) return '';
  if(/^[a-zA-Z]+:\//.test(text) || text.startsWith('/')){
    return text;
  }
  const clean = text.replace(/^\.\/+/, '').replace(/^\/+/, '');
  const casePath = normalizeCasePath(state.currentCasePath || '.');
  if(casePath === '.') return clean;
  const caseOptions = Array.isArray(state.casePathOptions) ? state.casePathOptions : [];
  if(caseOptions.some(cp => cp && cp !== '.' && (clean === cp || clean.startsWith(cp + '/')))) return clean;
  if(clean === casePath || clean.startsWith(casePath + '/')) return clean;
  return casePath + '/' + clean;
}

function applyCaseDefaults(){
  const savePathEl = document.getElementById('savePath');
  const serverPathEl = document.getElementById('serverEdgesPath');
  const analyzePathEl = document.getElementById('analysisConfigPath');
  if(savePathEl){
    const current = String(savePathEl.value || '').trim();
    if(!current || current === 'mesh/edges_new.csv'){
      savePathEl.value = casePathJoin('mesh/edges_new.csv');
    }
  }
  if(serverPathEl){
    const current = String(serverPathEl.value || '').trim();
    if(!current || current === 'mesh/edges_new.csv'){
      serverPathEl.value = casePathJoin('mesh/edges_new.csv');
    }
  }
  if(analyzePathEl){
    const current = String(analyzePathEl.value || '').trim();
    if(!current || current === 'mesh/Gates_param.csv'){
      analyzePathEl.value = casePathJoin('mesh/Gates_param.csv');
    }
  }
}

async function inferCasesFromPathTree(){
  try{
    const resp = await fetch('/api/path-tree?root=.&depth=3&_=' + String(Date.now()), {cache:'no-store'});
    if(!resp.ok) return [];
    const data = await resp.json();
    const items = Array.isArray(data.items) ? data.items : [];
    const hasMesh = new Set();
    const hasEdges = new Set();
    items.forEach((item)=>{
      if(!item || typeof item !== 'object') return;
      const rel = String(item.path || '').trim().replace(/\\/g, '/');
      if(!rel || rel.startsWith('.')) return;
      const mMesh = rel.match(/^([^/]+)\/mesh$/i);
      if(mMesh && item.isDir){
        hasMesh.add(normalizeCasePath(mMesh[1] || '.'));
        return;
      }
      const mEdges = rel.match(/^([^/]+)\/mesh\/(edges_new\.csv|edges\.csv|edges_utf8\.csv)$/i);
      if(mEdges && !item.isDir){
        hasEdges.add(normalizeCasePath(mEdges[1] || '.'));
      }
    });
    const cases = Array.from(hasEdges)
      .filter((p)=>hasMesh.has(p))
      .sort((a,b)=>a.localeCompare(b, 'zh-CN', {numeric:true}))
      .map((p)=>({name:p, path:p}));
    return cases;
  }catch(err){
    console.warn('inferCasesFromPathTree failed:', err);
    return [];
  }
}

async function loadCaseList(preferredCasePath=''){
  const sel = document.getElementById('caseSelect');
  if(!sel) return;
  const bootstrap = (typeof window !== 'undefined' && window.__BOOTSTRAP_CASES__ && typeof window.__BOOTSTRAP_CASES__ === 'object') ? window.__BOOTSTRAP_CASES__ : null;
  let resp = null;
  let data = bootstrap || {};
  try{
    const sep = '/api/cases'.includes('?') ? '&' : '?';
    resp = await fetch('/api/cases' + sep + '_=' + String(Date.now()), {cache:'no-store'});
    data = await resp.json();
  }catch(err){
    console.warn('loadCaseList fetch failed:', err);
    data = {cases: [], currentCase: state.currentCasePath || DEFAULT_CASE_PATH || '.'};
  }
  if(!resp || !resp.ok){
    console.warn('loadCaseList response not ok:', resp && resp.status, data);
  }
  if(data && data.startupWarning){
    setStartupWarning(String(data.startupWarning || ''));
  }
  const casesRaw = Array.isArray(data.cases) ? data.cases : [];
  let cases = casesRaw.filter(item=> item && typeof item === 'object').map(item=>(
    {
      name: String(item.name || '').trim(),
      path: normalizeCasePath(String(item.path || '.').trim() || '.'),
    }
  ));
  if(cases.length === 0){
    const inferred = await inferCasesFromPathTree();
    if(inferred.length){
      cases = inferred;
      if(!data || typeof data !== 'object') data = {};
      if(!data.currentCase) data.currentCase = inferred[0].path;
    }
  }
  const preferredNorm = normalizeCasePath(preferredCasePath || state.currentCasePath || DEFAULT_CASE_PATH || '.');
  const fromApi = normalizeCasePath(data.currentCase || '.');
  const paths = cases.map(item=>item.path).filter(Boolean);
  state.casePathOptions = paths.slice();
  let currentPath = preferredNorm;
  if(!paths.includes(currentPath)){
    currentPath = paths.includes(fromApi) ? fromApi : (paths.includes(DEFAULT_CASE_PATH) ? DEFAULT_CASE_PATH : (paths[0] || '.'));
  }
  state.currentCasePath = currentPath;
  sel.innerHTML = '';
  cases.forEach(item=>{
    const op = document.createElement('option');
    op.value = item.path;
    op.textContent = item.name || item.path;
    sel.appendChild(op);
  });
  if(sel.options.length === 0){
    const op = document.createElement('option');
    op.value = state.currentCasePath;
    op.textContent = state.currentCasePath;
    sel.appendChild(op);
  }
  const hasCurrent = Array.from(sel.options).some(op=>op.value === currentPath);
  sel.value = hasCurrent ? currentPath : sel.options[0].value;
  state.currentCasePath = normalizeCasePath(sel.value || '.');
  applyCaseDefaults();
}

async function loadCaseGraph(casePathRaw=''){
  const casePath = normalizeCasePath(casePathRaw || '.');
  const resp = await fetch(`/api/graph-case?case=${encodeURIComponent(casePath)}`);
  const data = await resp.json();
  if(!resp.ok){
    setStartupWarning('案例加载失败: ' + String(data.error || 'unknown error'));
    return false;
  }
  state.layoutSource = {
    positions: data.positions || {},
    fixedPositions: data.fixedPositions || {},
  };
  state.edges = (data.edges||[]).map(normalizeEdge);
  state.nodes = data.nodes||[];
  initializePositionsFromData(data || {});
  state.selectedNode = null;
  state.selectedEdgeIndex = null;
  state.directEndWarnIndices = [];
  rebuildNodesFromEdges();
  state.currentCasePath = normalizeCasePath(data.casePath || casePath || '.');
  loadTypeStylePresetForCurrentCase();
  document.getElementById('serverEdgesPath').value = String(data.edgesPath || '').trim() || casePathJoin('mesh/edges_new.csv');
  applyLayoutMode('force');
  renderTables();
  applyCaseDefaults();
  await loadCaseList(state.currentCasePath);
  await loadServerPathTree();
  return true;
}

async function loadData(){
  await loadCaseList(DEFAULT_CASE_PATH);
  const targetCase = normalizeCasePath(state.currentCasePath || DEFAULT_CASE_PATH || '.');
  await loadCaseGraph(targetCase);
}

async function loadDataFromServerPath(){
  const path = scopePathToCurrentCase((document.getElementById('serverEdgesPath').value || '').trim());
  if(!path){
    alert('请输入服务端文件路径，如 mesh/edges_new.csv');
    return;
  }
  document.getElementById('serverEdgesPath').value = path;
  const resp = await fetch(`/api/graph-file?path=${encodeURIComponent(path)}`);
  const data = await resp.json();
  if(!resp.ok){
    setStartupWarning('加载失败: ' + String(data.error || 'unknown error'));
    return;
  }
  state.layoutSource = {
    positions: data.positions || {},
    fixedPositions: data.fixedPositions || {},
  };
  state.edges = (data.edges||[]).map(normalizeEdge);
  state.nodes = data.nodes||[];
  initializePositionsFromData(data || {});
  state.selectedNode = null;
  state.selectedEdgeIndex = null;
  state.directEndWarnIndices = [];
  rebuildNodesFromEdges();
  applyLayoutMode('force');
  renderTables();
  await loadServerPathTree();
  setStartupWarning('');
  alert(`已加载: ${path}（${state.edges.length} 条边）`);
}

async function loadServerPathTree(){
  const rootPath = normalizeCasePath(state.currentCasePath || '.');

  const resp = await fetch(`/api/path-tree?root=${encodeURIComponent(rootPath)}&depth=4`);
  const data = await resp.json();
  const host = document.getElementById('serverPathTree');
  host.innerHTML = '';
  if(!resp.ok){
    const err = document.createElement('div');
    err.className = 'treeError';
    err.textContent = data.error || '路径层级加载失败';
    host.appendChild(err);
    return;
  }

  const root = String(data.root || rootPath || '.').replace(/\\/g, '/');
  const nodesByPath = new Map();
  const rootName = root.split('/').filter(Boolean).pop() || root;
  const rootNode = {name: rootName, path: root, isDir: true, depth: 0, children: []};
  nodesByPath.set(root, rootNode);

  (data.items || []).forEach(item=>{
    const p = String(item.path || '').replace(/\\/g, '/');
    if(!p) return;
    nodesByPath.set(p, {
      name: item.name || p,
      path: p,
      isDir: !!item.isDir,
      depth: Number(item.depth || 0),
      children: []
    });
  });

  (data.items || []).forEach(item=>{
    const p = String(item.path || '').replace(/\\/g, '/');
    const cur = nodesByPath.get(p);
    if(!cur) return;
    const slash = p.lastIndexOf('/');
    const parentPath = slash >= 0 ? p.slice(0, slash) : root;
    const parent = nodesByPath.get(parentPath) || rootNode;
    parent.children.push(cur);
  });

  const sortChildren = (node)=>{
    node.children.sort((a,b)=>{
      if(a.isDir !== b.isDir) return a.isDir ? -1 : 1;
      return String(a.name).localeCompare(String(b.name), 'zh-CN');
    });
    node.children.forEach(sortChildren);
  };
  sortChildren(rootNode);

  if(state.pathTreeExpanded[root] === undefined){
    state.pathTreeExpanded[root] = true;
  }

  const renderNode = (node, level)=>{
    const row = document.createElement('div');
    row.className = `treeRow ${node.isDir ? 'folder' : 'file'}`;
    row.style.paddingLeft = `${Math.max(0, level) * 14}px`;

    const expanded = !!state.pathTreeExpanded[node.path];
    const twist = document.createElement('span');
    twist.className = 'treeTwist';
    twist.textContent = node.isDir ? (expanded ? '▾' : '▸') : '';

    const icon = document.createElement('span');
    icon.className = 'treeIcon';
    icon.textContent = node.isDir ? '📁' : '📄';

    const name = document.createElement('span');
    name.className = 'treeName';
    name.textContent = node.name;

    row.appendChild(twist);
    row.appendChild(icon);
    row.appendChild(name);

    if(node.isDir){
      row.onclick = ()=>{
        state.pathTreeExpanded[node.path] = !expanded;
        loadServerPathTree();
      };
    } else {
      row.onclick = ()=>{ document.getElementById('serverEdgesPath').value = node.path || ''; };
    }

    host.appendChild(row);

    if(node.isDir && expanded){
      node.children.forEach(child=>renderNode(child, level + 1));
    }
  };

  renderNode(rootNode, 0);
}

function openSimulationWindow(){
  const simRootDefault = casePathJoin('mesh');
  const simRootSafe = String(simRootDefault || 'mesh').replace(/"/g, '&quot;');
  const win = window.open('', '_blank', 'width=1220,height=780');
  if(!win){
    alert('弹窗被浏览器拦截，请允许弹窗后重试。');
    return;
  }
  const html = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>在线仿真可视化</title>
  <style>
    body{margin:0;font-family:"Microsoft YaHei",Arial,sans-serif;background:#f5f7fb;color:#1f2937;}
    .wrap{display:grid;grid-template-columns:minmax(320px,360px) 1fr;gap:10px;padding:12px;height:100vh;}
    .panel{background:#fff;border:1px solid #d9dee8;border-radius:10px;padding:10px;overflow:auto;}
    .title{font-size:16px;font-weight:700;margin:0 0 10px 0;}
    .row{display:flex;align-items:center;gap:8px;margin-bottom:8px;}
    .row label{width:92px;flex:0 0 92px;font-size:12px;color:#6b7280;}
    .row input,.row select{flex:1;border:1px solid #d9dee8;border-radius:6px;padding:6px;font-size:12px;}
    .btns{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px;}
    button{border:1px solid #d9dee8;background:#fff;padding:6px 10px;border-radius:6px;cursor:pointer;font-size:12px;}
    button.primary{background:#2563eb;color:#fff;border-color:#2563eb;}
    button.active{background:#0f766e;color:#fff;border-color:#0f766e;}
    .meta{font-size:12px;color:#6b7280;margin-top:8px;word-break:break-all;}
    .mapCurveStack{height:calc(100vh - 52px);display:grid;grid-template-rows:minmax(320px,1fr) 250px;gap:8px;}
    .canvasHost{display:flex;align-items:center;justify-content:center;overflow:auto;background:#fff;border:1px solid #d9dee8;border-radius:10px;}
    #simCanvas{background:#fff;}
    .curveHost{background:#fff;border:1px solid #d9dee8;border-radius:10px;padding:6px;display:flex;flex-direction:column;gap:4px;}
    .curveTitle{font-size:12px;color:#475569;}
    #curvePlot{width:100%;height:100%;background:#fff;}
  </style>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"><\/script>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <div class="title">在线仿真参数面板</div>
      <div class="row"><label>结果目录</label><input id="root" value="${simRootSafe}" /></div>
      <div class="row"><label>文件模式</label><input id="pattern" value="result*.dat" /></div>
      <div class="row"><label>播放间隔ms</label><input id="interval" type="number" min="50" max="10000" step="10" value="500" /></div>
      <div class="row"><label>网格尺寸</label><input id="cellSize" type="number" min="1" step="1" value="1000" /></div>
      <div class="row"><label>色标风格</label><select id="colorMap"><option value="viridis" selected>Viridis</option><option value="turbo">Turbo</option><option value="jet">Jet</option><option value="gray">Gray</option></select></div>
      <div class="row"><label>Z最小</label><input id="zMin" type="number" step="any" /></div>
      <div class="row"><label>Z最大</label><input id="zMax" type="number" step="any" /></div>
      <div class="row"><label>显示闸门</label><select id="showGates"><option value="1" selected>是</option><option value="0">否</option></select></div>
      <div class="row"><label>时间步</label><input id="step" type="range" min="0" max="0" step="1" value="0" /></div>
      <div class="meta" id="stepLabel">-/-</div>
      <div class="btns">
        <button id="btnLoadGrid">加载网格</button>
        <button id="btnLoadResult" class="primary">加载结果</button>
        <button id="btnPlay">播放</button>
        <button id="btnStop">停止</button>
      </div>
      <div class="btns">
        <button id="btnLoadCurve">加载曲线</button>
        <button id="btnPlayCurve">播放曲线</button>
        <button id="btnCurveLoop" class="active">曲线循环</button>
        <button id="btnApplyColor">应用色标</button>
        <button id="btnAutoColor">自动范围</button>
      </div>
      <div class="meta" id="curveInfo">未加载曲线数据</div>
      <div class="meta" id="info">页面已打开，正在加载网格...</div>
    </div>
    <div class="panel" style="padding:8px;">
      <div class="mapCurveStack">
        <div class="canvasHost">
          <canvas id="simCanvas" width="920" height="680"></canvas>
        </div>
        <div class="curveHost">
          <div class="curveTitle" id="curveStepLabel">曲线时间步: -/-</div>
          <div id="curvePlot"></div>
        </div>
      </div>
    </div>
  </div>
<script>
  const simState = {
    steps:[], bounds:null, points:[], frameIndex:0, timer:null, playing:false,
    pointsRaw:[],
    colorMap:'viridis', zMin:null, zMax:null, cellSize:1000, showGates:true,
    junctions:[],
    gates:[], stepCache:new Map(), stepLoading:new Map(),
    gateLabelOffsets:new Map(), gateLabelBoxes:[], gateLabelNodes:[], draggingLabel:null,
    dragPointerId:null,
    curve:{
      loaded:false,
      steps:[],
      series:[],
      frameIndex:0,
      timer:null,
      playing:false,
      loop:true,
      busy:false,
    }
  };
  const rootEl = document.getElementById('root');
  const patternEl = document.getElementById('pattern');
  const intervalEl = document.getElementById('interval');
  const cellSizeEl = document.getElementById('cellSize');
  const colorMapEl = document.getElementById('colorMap');
  const zMinEl = document.getElementById('zMin');
  const zMaxEl = document.getElementById('zMax');
  const showGatesEl = document.getElementById('showGates');
  const stepEl = document.getElementById('step');
  const infoEl = document.getElementById('info');
  const stepLabelEl = document.getElementById('stepLabel');
  const curveInfoEl = document.getElementById('curveInfo');
  const curveStepLabelEl = document.getElementById('curveStepLabel');
  const canvas = document.getElementById('simCanvas');
  const ctx = canvas.getContext('2d');
  const curvePlotEl = document.getElementById('curvePlot');
  const RESULT_FETCH_TIMEOUT_MS = 4500;

  async function fetchJsonWithTimeout(url, timeoutMs, label){
    const controller = new AbortController();
    const timer = setTimeout(()=>controller.abort(), Math.max(300, Number(timeoutMs) || 300));
    try{
      const resp = await fetch(url, {signal: controller.signal});
      let data = {};
      try{
        data = await resp.json();
      }catch(_e){
        data = {};
      }
      return {ok: !!resp.ok, data};
    }catch(err){
      if(err && err.name === 'AbortError'){
        throw new Error((label || '请求') + '超时（' + String(timeoutMs) + 'ms）');
      }
      throw err;
    }finally{
      clearTimeout(timer);
    }
  }

  function clamp01(v){ return Math.max(0, Math.min(1, Number(v) || 0)); }
  function canvasPointFromEvent(ev){
    const rect = canvas.getBoundingClientRect();
    const sx = canvas.width / Math.max(1, rect.width);
    const sy = canvas.height / Math.max(1, rect.height);
    return {
      x: (ev.clientX - rect.left) * sx,
      y: (ev.clientY - rect.top) * sy,
    };
  }
  function gateKey(gate, idx){
    const gid = String((gate && gate.id) || '').trim();
    if(gid) return 'id:' + gid;
    const gname = String((gate && gate.name) || '').trim();
    if(gname) return 'name:' + gname;
    return 'idx:' + String(idx);
  }
  function lerp(a,b,t){ return a + (b-a) * t; }
  function lerpColor(c1, c2, t){
    return [
      Math.round(lerp(c1[0], c2[0], t)),
      Math.round(lerp(c1[1], c2[1], t)),
      Math.round(lerp(c1[2], c2[2], t)),
    ];
  }
  function colorByStops(t, stops){
    const x = clamp01(t);
    for(let i=0;i<stops.length-1;i++){
      const s0 = stops[i];
      const s1 = stops[i+1];
      if(x <= s1[0]){
        const local = (x - s0[0]) / Math.max(1e-9, s1[0] - s0[0]);
        return lerpColor(s0[1], s1[1], local);
      }
    }
    return stops[stops.length-1][1];
  }
  function getColor(t, mapName){
    const palettes = {
      viridis: [[0,[68,1,84]],[0.25,[59,82,139]],[0.5,[33,145,140]],[0.75,[94,201,98]],[1,[253,231,37]]],
      turbo: [[0,[48,18,59]],[0.25,[50,102,255]],[0.5,[35,190,145]],[0.75,[243,170,30]],[1,[122,4,3]]],
      jet: [[0,[0,0,128]],[0.35,[0,170,255]],[0.5,[130,255,130]],[0.65,[255,220,0]],[1,[180,0,0]]],
      gray: [[0,[0,0,0]],[1,[255,255,255]]],
    };
    const stops = palettes[mapName] || palettes.viridis;
    return colorByStops(t, stops);
  }
  function applyAutoZFromBounds(){
    const b = simState.bounds;
    if(!b) return;
    const minVal = Number(b.zMin);
    const maxVal = Number(b.zMax);
    if(Number.isFinite(minVal) && Number.isFinite(maxVal) && maxVal > minVal){
      simState.zMin = minVal;
      simState.zMax = maxVal;
      zMinEl.value = String(minVal);
      zMaxEl.value = String(maxVal);
    }
  }
  function applyColorControls(){
    simState.colorMap = String(colorMapEl.value || 'viridis');
    const cellSizeVal = Number(cellSizeEl.value);
    if(Number.isFinite(cellSizeVal) && cellSizeVal > 0){
      simState.cellSize = cellSizeVal;
    }
    simState.showGates = String(showGatesEl.value || '1') === '1';
    const minVal = Number(zMinEl.value);
    const maxVal = Number(zMaxEl.value);
    if(Number.isFinite(minVal) && Number.isFinite(maxVal) && maxVal > minVal){
      simState.zMin = minVal;
      simState.zMax = maxVal;
      render();
      return;
    }
    alert('色标范围无效：请保证 Z最大 > Z最小。');
  }

  function stopPlay(){
    if(simState.timer){ clearInterval(simState.timer); simState.timer = null; }
    simState.playing = false;
    document.getElementById('btnPlay').textContent = '播放';
  }

  function updateCurveStepLabel(){
    const total = Array.isArray(simState.curve.steps) ? simState.curve.steps.length : 0;
    const cur = Number(simState.curve.frameIndex || 0);
    curveStepLabelEl.textContent = '曲线时间步: ' + (total ? (String(cur + 1) + '/' + String(total)) : '-/-');
  }

  function stopCurvePlay(){
    if(simState.curve.timer){ clearInterval(simState.curve.timer); simState.curve.timer = null; }
    simState.curve.playing = false;
    document.getElementById('btnPlayCurve').textContent = '播放曲线';
  }

  function renderCurve(){
    if(!curvePlotEl || typeof Plotly === 'undefined'){
      curveInfoEl.textContent = '曲线组件加载失败：Plotly 不可用';
      return;
    }
    const series = Array.isArray(simState.curve.series) ? simState.curve.series : [];
    const total = Array.isArray(simState.curve.steps) ? simState.curve.steps.length : 0;
    updateCurveStepLabel();
    if(!series.length || !total){
      Plotly.react(curvePlotEl, [], {
        margin:{l:56,r:20,t:26,b:46},
        xaxis:{title:'nindex'},
        yaxis:{title:'值'},
        annotations:[{text:'暂无曲线数据',xref:'paper',yref:'paper',x:0.5,y:0.5,showarrow:false,font:{size:13,color:'#94a3b8'}}],
      }, {displayModeBar:true,responsive:true});
      return;
    }
    const frameIndex = Math.max(0, Math.min(Number(simState.curve.frameIndex || 0), total - 1));

    let vMin = Number.POSITIVE_INFINITY;
    let vMax = Number.NEGATIVE_INFINITY;
    let xMax = 0;
    let xMin = Number.POSITIVE_INFINITY;
    const sourcePoints = Array.isArray(simState.pointsRaw) && simState.pointsRaw.length ? simState.pointsRaw : simState.points;
    const frameSeries = series.slice(0, 8).map((s)=>{
      const nodeIdx = Array.isArray(s.nodeIndices) ? s.nodeIndices : [];
      const pairs = [];
      for(let i = 0; i < nodeIdx.length; i++){
        const idx = Number(nodeIdx[i]);
        if(!Number.isFinite(idx)) continue;
        pairs.push({idx, order:i});
      }
      pairs.sort((a, b)=>{
        if(a.idx !== b.idx) return a.idx - b.idx;
        return a.order - b.order;
      });
      const xs = [];
      const ys = [];
      for(let i = 0; i < pairs.length; i++){
        const idx = pairs[i].idx;
        const p = sourcePoints[idx];
        if(!Array.isArray(p) || p.length < 3) continue;
        const v = Number(p[2]);
        if(!Number.isFinite(v)) continue;
        xs.push(idx);
        ys.push(v);
        if(idx > xMax) xMax = idx;
        if(idx < xMin) xMin = idx;
        vMin = Math.min(vMin, v);
        vMax = Math.max(vMax, v);
      }
      return {
        label: String(s.label || s.key || ''),
        xs,
        ys,
      };
    });

    if(!Number.isFinite(vMin) || !Number.isFinite(vMax)){
      Plotly.react(curvePlotEl, [], {
        margin:{l:56,r:20,t:26,b:46},
        xaxis:{title:'nindex'},
        yaxis:{title:'值'},
        annotations:[{text:'当前时刻无可用曲线点',xref:'paper',yref:'paper',x:0.5,y:0.5,showarrow:false,font:{size:13,color:'#94a3b8'}}],
      }, {displayModeBar:true,responsive:true});
      return;
    }
    if(!(vMax > vMin)){
      vMin -= 1;
      vMax += 1;
    }
    if(!Number.isFinite(xMin)) xMin = 0;
    if(!(xMax > 0)) xMax = 1;
    const palette = ['#2563eb','#dc2626','#16a34a','#d97706','#7c3aed','#0891b2','#be123c','#334155'];
    const traces = frameSeries.map((s, si)=>({
      x: s.xs,
      y: s.ys,
      mode: 'lines+markers',
      type: 'scattergl',
      name: s.label || ('series' + String(si + 1)),
      line: {width: 2, color: palette[si % palette.length]},
      marker: {size: 3, color: palette[si % palette.length]},
      hovertemplate: 'nindex=%{x}<br>值=%{y:.6f}<extra>' + (s.label || ('series' + String(si + 1))) + '</extra>',
    }));
    const layout = {
      margin:{l:56,r:20,t:26,b:46},
      legend:{orientation:'h',x:0,y:1.08},
      xaxis:{title:'nindex', range:[xMin, xMax]},
      yaxis:{title:'值', range:[vMin, vMax]},
      annotations:[
        {text:'t=' + String(frameIndex),xref:'paper',yref:'paper',x:0.01,y:1.12,showarrow:false,font:{size:12,color:'#64748b'}}
      ],
    };
    Plotly.react(curvePlotEl, traces, layout, {displayModeBar:true,responsive:true});
  }

  async function loadCurveData(){
    stopCurvePlay();
    if(!simState.steps.length){
      await loadMeta();
    }
    const root = rootEl.value.trim() || 'mesh';
    const pattern = patternEl.value.trim() || 'result*.dat';
    curveInfoEl.textContent = '正在加载曲线数据...';
    const url = '/api/sim-curve-series?root=' + encodeURIComponent(root) + '&pattern=' + encodeURIComponent(pattern);
    const result = await fetchJsonWithTimeout(url, 12000, '加载曲线数据');
    if(!result.ok) throw new Error((result.data && result.data.error) || '曲线数据加载失败');
    const data = result.data || {};
    const curve = simState.curve;
    curve.steps = Array.isArray(simState.steps) && simState.steps.length ? simState.steps.slice() : (Array.isArray(data.steps) ? data.steps : []);
    curve.series = Array.isArray(data.series) ? data.series : [];
    curve.frameIndex = Number(simState.frameIndex || 0);
    curve.loaded = curve.series.length > 0 && curve.steps.length > 0;
    if(!curve.loaded){
      curveInfoEl.textContent = '曲线未生成：' + String(data.error || '未匹配到可用 canal/public/property 节点');
      renderCurve();
      return;
    }
    const label = (curve.series[0] && (curve.series[0].label || curve.series[0].key)) ? String(curve.series[0].label || curve.series[0].key) : '';
    curveInfoEl.textContent = '曲线加载完成：x轴为距首点距离，时间动画逐帧播放。' + String(curve.series.length) + ' 条，时间步 ' + String(curve.steps.length) + (label ? ('；示例: ' + label) : '');
    renderCurve();
  }

  async function curveNextFrame(){
    if(!simState.curve.loaded) return;
    if(simState.curve.busy) return;
    const total = simState.curve.steps.length;
    if(!total) return;
    let idx = Number(simState.curve.frameIndex || 0) + 1;
    if(idx >= total){
      if(simState.curve.loop){ idx = 0; }
      else { idx = total - 1; stopCurvePlay(); }
    }
    simState.curve.busy = true;
    try{
      await loadStep(idx);
      simState.curve.frameIndex = Number(simState.frameIndex || idx);
      renderCurve();
    }finally{
      simState.curve.busy = false;
    }
  }

  async function toggleCurvePlay(){
    if(simState.curve.playing){ stopCurvePlay(); return; }
    if(!simState.curve.loaded){
      try{ await loadCurveData(); }
      catch(e){ curveInfoEl.textContent = '曲线加载失败：' + String(e && e.message ? e.message : e); return; }
    }
    if(!simState.curve.loaded) return;
    const interval = Math.max(50, Math.min(10000, Number(intervalEl.value || 500)));
    simState.curve.playing = true;
    document.getElementById('btnPlayCurve').textContent = '暂停曲线';
    simState.curve.timer = setInterval(()=>{ curveNextFrame().catch(()=>{}); }, interval);
  }

  function render(){
    ctx.clearRect(0,0,canvas.width,canvas.height);
    const b = simState.bounds;
    if(!b) return;
    const pts = simState.points || [];
    const margin = 18;
    const colorBarW = 14;
    const colorBarGap = 16;
    const xSpan = Math.max(1e-9, Number(b.xMax)-Number(b.xMin));
    const ySpan = Math.max(1e-9, Number(b.yMax)-Number(b.yMin));
    const plotAvailW = Math.max(1, canvas.width - margin*2 - colorBarGap - colorBarW);
    const plotAvailH = Math.max(1, canvas.height - margin*2);
    const scale = Math.max(1e-9, Math.min(plotAvailW / xSpan, plotAvailH / ySpan));
    const w = Math.max(1, xSpan * scale);
    const h = Math.max(1, ySpan * scale);
    const plotLeft = margin + (plotAvailW - w) * 0.5;
    const plotTop = margin + (plotAvailH - h) * 0.5;
    const plotRight = plotLeft + w;
    const plotBottom = plotTop + h;
    const colorBarLeft = plotRight + colorBarGap;

    const worldToCanvasX = (x)=> plotLeft + (x - Number(b.xMin)) * scale;
    const worldToCanvasY = (y)=> plotBottom - (y - Number(b.yMin)) * scale;

    const zMin = Number.isFinite(simState.zMin) ? Number(simState.zMin) : Number(b.zMin);
    const zMax = Number.isFinite(simState.zMax) ? Number(simState.zMax) : Number(b.zMax);
    const zSpan = Math.max(1e-9, zMax - zMin);
    const cellSize = Math.max(1e-6, Number(simState.cellSize) || 1000);
    const gridXCount = Math.max(1, Math.ceil((Number(b.xMax) - Number(b.xMin)) / cellSize));
    const gridYCount = Math.max(1, Math.ceil((Number(b.yMax) - Number(b.yMin)) / cellSize));

    ctx.strokeStyle = 'rgba(148,163,184,0.4)';
    ctx.lineWidth = 1;
    const maxGridLines = 220;
    if(gridXCount <= maxGridLines){
      for(let i=0;i<=gridXCount;i++){
        const worldX = Number(b.xMin) + i * cellSize;
        const px = worldToCanvasX(worldX);
        ctx.beginPath();
        ctx.moveTo(px, plotTop);
        ctx.lineTo(px, plotBottom);
        ctx.stroke();
      }
    }
    if(gridYCount <= maxGridLines){
      for(let i=0;i<=gridYCount;i++){
        const worldY = Number(b.yMin) + i * cellSize;
        const py = worldToCanvasY(worldY);
        ctx.beginPath();
        ctx.moveTo(plotLeft, py);
        ctx.lineTo(plotRight, py);
        ctx.stroke();
      }
    }

    const cellMap = new Map();
    for(let i=0;i<pts.length;i++){
      const p = pts[i];
      const x = Number(p[0]);
      const y = Number(p[1]);
      const z = Number(p[2]);
      if(!Number.isFinite(x)||!Number.isFinite(y)||!Number.isFinite(z)) continue;
      const col = Math.floor((x - Number(b.xMin)) / cellSize);
      const row = Math.floor((y - Number(b.yMin)) / cellSize);
      const key = row + ':' + col;
      const acc = cellMap.get(key) || {row:row, col:col, sum:0, count:0};
      acc.sum += z;
      acc.count += 1;
      cellMap.set(key, acc);
    }

    cellMap.forEach((acc)=>{
      const x0 = Number(b.xMin) + acc.col * cellSize;
      const x1 = x0 + cellSize;
      const y0 = Number(b.yMin) + acc.row * cellSize;
      const y1 = y0 + cellSize;
      const z = acc.sum / Math.max(1, acc.count);
      const nzCell = clamp01((z-zMin)/zSpan);
      const px0 = worldToCanvasX(x0);
      const px1 = worldToCanvasX(x1);
      const py0 = worldToCanvasY(y0);
      const py1 = worldToCanvasY(y1);
      const c = getColor(nzCell, simState.colorMap);
      ctx.fillStyle = 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
      ctx.globalAlpha = 0.88;
      ctx.fillRect(Math.min(px0,px1), Math.min(py0,py1), Math.max(1, Math.abs(px1-px0)), Math.max(1, Math.abs(py1-py0)));
    });

    ctx.globalAlpha = 1;
    ctx.strokeStyle = '#111827';
    ctx.lineWidth = 1.1;
    ctx.strokeRect(plotLeft, plotTop, w, h);

    simState.gateLabelBoxes = [];
    simState.gateLabelNodes = [];
    if(simState.showGates && Array.isArray(simState.gates) && simState.gates.length){
      simState.gates.forEach((gate, idx)=>{
        const gx = Number(gate.x);
        const gy = Number(gate.y);
        if(!Number.isFinite(gx) || !Number.isFinite(gy)) return;
        const px = worldToCanvasX(gx);
        const py = worldToCanvasY(gy);
        if(px < plotLeft || px > plotRight || py < plotTop || py > plotBottom) return;

        ctx.fillStyle = '#d946ef';
        ctx.beginPath();
        ctx.arc(px, py, 3.5, 0, Math.PI*2);
        ctx.fill();

        const dir = (idx % 2 === 0) ? 1 : -1;
        const defaultTx = px + dir * 42;
        const defaultTy = py + ((String(gate.name || '').includes('泄')) ? 16 : -10);
        const key = gateKey(gate, idx);
        if(!simState.gateLabelOffsets.has(key)){
          simState.gateLabelOffsets.set(key, {tx: defaultTx, ty: defaultTy});
        }
        const saved = simState.gateLabelOffsets.get(key) || {tx: defaultTx, ty: defaultTy};
        const tx = Number(saved.tx);
        const ty = Number(saved.ty);
        simState.gateLabelNodes.push({key, x: tx, y: ty, r: 11});
        ctx.strokeStyle = 'rgba(107,114,128,0.75)';
        ctx.lineWidth = 0.8;
        ctx.beginPath();
        ctx.moveTo(px, py);
        ctx.lineTo(tx, ty);
        ctx.stroke();

        ctx.fillStyle = 'rgba(59,130,246,0.75)';
        ctx.beginPath();
        ctx.arc(tx, ty, 4.2, 0, Math.PI*2);
        ctx.fill();

        ctx.fillStyle = '#111827';
        ctx.font = '11px Microsoft YaHei';
        ctx.textAlign = dir > 0 ? 'left' : 'right';
        const label = String(gate.label || gate.name || gate.id || '');
        const textX = tx + (dir > 0 ? 2 : -2);
        const textY = ty - 2;
        const textW = Math.max(6, ctx.measureText(label).width);
        const left = dir > 0 ? textX : (textX - textW);
        const top = textY - 11;
        ctx.fillStyle = 'rgba(255,255,255,0.78)';
        ctx.fillRect(left - 3, top - 2, textW + 6, 16);
        ctx.fillStyle = '#111827';
        ctx.fillText(label, textX, textY);

        simState.gateLabelBoxes.push({
          key,
          left: left - 5,
          top: top - 4,
          right: left + textW + 5,
          bottom: top + 16,
        });
      });
    }

    if(Array.isArray(simState.junctions) && simState.junctions.length){
      ctx.font = '10px Microsoft YaHei';
      ctx.textAlign = 'left';
      simState.junctions.forEach((junc)=>{
        const jx = Number(junc.x);
        const jy = Number(junc.y);
        if(!Number.isFinite(jx) || !Number.isFinite(jy)) return;
        const px = worldToCanvasX(jx);
        const py = worldToCanvasY(jy);
        if(px < plotLeft || px > plotRight || py < plotTop || py > plotBottom) return;
        ctx.fillStyle = '#f59e0b';
        ctx.fillRect(px - 3, py - 3, 6, 6);
        const label = String(junc.label || junc.id || '');
        if(label){
          ctx.fillStyle = 'rgba(255,255,255,0.82)';
          const textW = Math.max(6, ctx.measureText(label).width);
          ctx.fillRect(px + 5, py - 10, textW + 6, 14);
          ctx.fillStyle = '#92400e';
          ctx.fillText(label, px + 8, py + 1);
        }
      });
    }

    const yStart = Math.round(plotTop);
    const yEnd = Math.round(plotBottom);
    for(let y=yStart; y<=yEnd; y++){
      const t = 1 - ((y - plotTop) / Math.max(1, h));
      const c = getColor(t, simState.colorMap);
      ctx.strokeStyle = 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
      ctx.beginPath();
      ctx.moveTo(colorBarLeft, y);
      ctx.lineTo(colorBarLeft + colorBarW, y);
      ctx.stroke();
    }
    ctx.strokeStyle = '#94a3b8';
    ctx.strokeRect(colorBarLeft, plotTop, colorBarW, h);
    ctx.fillStyle = '#475569';
    ctx.font = '12px Microsoft YaHei';
    ctx.fillText(String(zMax.toFixed(3)), colorBarLeft - 2, plotTop - 2);
    ctx.fillText(String(zMin.toFixed(3)), colorBarLeft - 2, plotBottom + 14);
  }

  function updateStepLabel(){
    const total = simState.steps.length;
    stepLabelEl.textContent = total ? (String(simState.frameIndex+1) + '/' + String(total)) : '-/-';
  }

  async function prefetchStep(stepIndex){
    const total = simState.steps.length;
    if(!total) return;
    const idx = Math.max(0, Math.min(Number(stepIndex)||0, total-1));
    if(simState.stepCache.has(idx) || simState.stepLoading.has(idx)) return;
    const url = '/api/sim-result-step?root=' + encodeURIComponent(rootEl.value.trim() || 'mesh') + '&pattern=' + encodeURIComponent(patternEl.value.trim() || 'result*.dat') + '&step=' + idx;
    const p = fetchJsonWithTimeout(url, 2500, '预取时间步').then(({ok,data})=>{
      if(ok) simState.stepCache.set(idx, data);
    }).catch(()=>{}).finally(()=>{ simState.stepLoading.delete(idx); });
    simState.stepLoading.set(idx, p);
  }

  async function loadStep(stepIndex){
    const total = simState.steps.length;
    if(!total) return;
    const idx = Math.max(0, Math.min(Number(stepIndex)||0, total-1));
    if(simState.stepCache.has(idx)){
      const data = simState.stepCache.get(idx);
      simState.frameIndex = Number(data.step) || idx;
      simState.pointsRaw = Array.isArray(data.points) ? data.points.slice() : [];
      simState.points = Array.isArray(data.points) ? data.points : [];
      fitBoundsToData();
      stepEl.value = String(simState.frameIndex);
      infoEl.textContent = '文件: ' + String(data.file || '') + '，点数: ' + String(data.pointCount || 0) + '（缓存）';
      updateStepLabel();
      render();
      if(simState.curve.loaded){
        simState.curve.frameIndex = simState.frameIndex;
        renderCurve();
      }
      prefetchStep((idx + 1) % total);
      return;
    }
    if(simState.stepLoading.has(idx)){
      await simState.stepLoading.get(idx);
      if(simState.stepCache.has(idx)){
        return loadStep(idx);
      }
    }
    const url = '/api/sim-result-step?root=' + encodeURIComponent(rootEl.value.trim() || 'mesh') + '&pattern=' + encodeURIComponent(patternEl.value.trim() || 'result*.dat') + '&step=' + idx;
    const pending = fetchJsonWithTimeout(url, RESULT_FETCH_TIMEOUT_MS, '加载时间步').finally(()=>{ simState.stepLoading.delete(idx); });
    simState.stepLoading.set(idx, pending);
    const result = await pending;
    const respOk = !!result.ok;
    const data = result.data || {};
    if(!respOk) throw new Error(data.error || '加载时间步失败');
    simState.stepCache.set(idx, data);
    simState.frameIndex = Number(data.step) || 0;
    simState.pointsRaw = Array.isArray(data.points) ? data.points.slice() : [];
    simState.points = Array.isArray(data.points) ? data.points : [];
    fitBoundsToData();
    stepEl.value = String(simState.frameIndex);
    infoEl.textContent = '文件: ' + String(data.file || '') + '，点数: ' + String(data.pointCount || 0);
    updateStepLabel();
    render();
    if(simState.curve.loaded){
      simState.curve.frameIndex = simState.frameIndex;
      renderCurve();
    }
    prefetchStep((idx + 1) % total);
  }

  async function loadGates(){
    try{
      const root = rootEl.value.trim() || 'mesh';
      const resp = await fetch('/api/sim-gates?root=' + encodeURIComponent(root));
      const data = await resp.json();
      if(resp.ok && Array.isArray(data.gates)){
        simState.gates = data.gates;
      }else{
        simState.gates = [];
      }
    }catch(_e){
      simState.gates = [];
    }
  }

  async function loadJunctions(){
    simState.junctions = [];
    try{
      const root = rootEl.value.trim() || 'mesh';
      const resp = await fetch('/api/sim-junctions?root=' + encodeURIComponent(root));
      const data = await resp.json();
      if(resp.ok && Array.isArray(data.junctions)){
        simState.junctions = data.junctions;
      }
    }catch(_e){
      simState.junctions = [];
    }
  }

  function calcMarkerBounds(){
    const xs = [];
    const ys = [];
    (Array.isArray(simState.gates) ? simState.gates : []).forEach((g)=>{
      const x = Number(g && g.x);
      const y = Number(g && g.y);
      if(Number.isFinite(x) && Number.isFinite(y)){
        xs.push(x);
        ys.push(y);
      }
    });
    (Array.isArray(simState.junctions) ? simState.junctions : []).forEach((j)=>{
      const x = Number(j && j.x);
      const y = Number(j && j.y);
      if(Number.isFinite(x) && Number.isFinite(y)){
        xs.push(x);
        ys.push(y);
      }
    });
    if(!xs.length || !ys.length) return null;
    let xMin = Math.min.apply(null, xs);
    let xMax = Math.max.apply(null, xs);
    let yMin = Math.min.apply(null, ys);
    let yMax = Math.max.apply(null, ys);
    const xPad = Math.max(10, (xMax - xMin) * 0.06);
    const yPad = Math.max(10, (yMax - yMin) * 0.06);
    if(!(xMax > xMin)) { xMin -= 50; xMax += 50; }
    if(!(yMax > yMin)) { yMin -= 50; yMax += 50; }
    return {
      xMin: xMin - xPad,
      xMax: xMax + xPad,
      yMin: yMin - yPad,
      yMax: yMax + yPad,
      zMin: Number.isFinite(simState.zMin) ? Number(simState.zMin) : 0,
      zMax: Number.isFinite(simState.zMax) ? Number(simState.zMax) : 1,
    };
  }

  async function loadGridData(){
    const root = rootEl.value.trim() || 'mesh';
    infoEl.textContent = '正在加载网格...';
    try{
      await Promise.all([loadGates(), loadJunctions()]);
      if(!simState.bounds){
        simState.bounds = calcMarkerBounds();
      }else{
        fitBoundsToData();
      }

      if(!simState.bounds){
        // Fallback: derive bounds from result/input metadata when marker bounds are unavailable.
        const metaUrl = '/api/sim-result-meta?root=' + encodeURIComponent(root) + '&pattern=' + encodeURIComponent('input.txt;result*.dat');
        try{
          const metaResp = await fetchJsonWithTimeout(metaUrl, 3500, '网格边界兜底');
          if(metaResp.ok && metaResp.data && metaResp.data.bounds){
            simState.bounds = metaResp.data.bounds;
          }
        }catch(_e){
          // keep best-effort behavior; message will be shown below if bounds still missing
        }
      }

      if(!simState.bounds){
        infoEl.textContent = '网格加载完成，但缺少可视化坐标（闸门/节点为空，且未获取到边界）。root=' + root;
        try{ render(); }catch(_e){}
        return;
      }

      fitBoundsToData();
      try{
        render();
      }catch(renderErr){
        console.error('render grid failed', renderErr);
        infoEl.textContent = '网格加载完成，但渲染失败：' + String(renderErr && renderErr.message ? renderErr.message : renderErr);
        return;
      }
      infoEl.textContent = '网格加载完成：闸门 ' + String((simState.gates || []).length) + '，节点 ' + String((simState.junctions || []).length) + '。';
    }catch(e){
      console.error('loadGridData failed', e);
      throw e;
    }
  }

  function expandBoundsWithMarkers(baseBounds, markerGroups){
    if(!baseBounds) return baseBounds;
    let xMin = Number(baseBounds.xMin);
    let xMax = Number(baseBounds.xMax);
    let yMin = Number(baseBounds.yMin);
    let yMax = Number(baseBounds.yMax);
    if(!Number.isFinite(xMin) || !Number.isFinite(xMax) || !Number.isFinite(yMin) || !Number.isFinite(yMax)){
      return baseBounds;
    }
    (markerGroups || []).forEach(group=>{
      (Array.isArray(group) ? group : []).forEach(item=>{
        const x = Number(item && item.x);
        const y = Number(item && item.y);
        if(!Number.isFinite(x) || !Number.isFinite(y)) return;
        if(x < xMin) xMin = x;
        if(x > xMax) xMax = x;
        if(y < yMin) yMin = y;
        if(y > yMax) yMax = y;
      });
    });
    return Object.assign({}, baseBounds, {xMin, xMax, yMin, yMax});
  }

  function dropOutOfBoundsMarkers(){
    const b = simState.bounds;
    if(!b) return;
    const xMin = Number(b.xMin);
    const xMax = Number(b.xMax);
    const yMin = Number(b.yMin);
    const yMax = Number(b.yMax);
    const inBounds = (item)=>{
      const x = Number(item && item.x);
      const y = Number(item && item.y);
      return Number.isFinite(x) && Number.isFinite(y) && x >= xMin && x <= xMax && y >= yMin && y <= yMax;
    };
    simState.gates = (Array.isArray(simState.gates) ? simState.gates : []).filter(inBounds);
    simState.junctions = (Array.isArray(simState.junctions) ? simState.junctions : []).filter(inBounds);
    const validKeys = new Set(simState.gates.map((g, idx)=>gateKey(g, idx)));
    Array.from(simState.gateLabelOffsets.keys()).forEach((k)=>{ if(!validKeys.has(k)) simState.gateLabelOffsets.delete(k); });
    simState.gateLabelBoxes = [];
    simState.gateLabelNodes = [];
    simState.draggingLabel = null;
    simState.dragPointerId = null;
    canvas.style.cursor = 'default';
  }

  function fitBoundsToData(){
    simState.bounds = expandBoundsWithMarkers(simState.bounds, [simState.gates, simState.junctions]);
    dropOutOfBoundsMarkers();
    if(!simState.bounds) return;
    if(simState.points.length){
      simState.points = simState.points.filter((p)=>{
        const x = Number(p && p[0]);
        const y = Number(p && p[1]);
        if(!Number.isFinite(x) || !Number.isFinite(y)) return false;
        return x >= Number(simState.bounds.xMin) && x <= Number(simState.bounds.xMax) && y >= Number(simState.bounds.yMin) && y <= Number(simState.bounds.yMax);
      });
    }
  }

  async function loadMeta(){
    stopPlay();
    const root = rootEl.value.trim() || 'mesh';
    const pattern = patternEl.value.trim() || 'result*.dat';
    const url = '/api/sim-result-meta?root=' + encodeURIComponent(root) + '&pattern=' + encodeURIComponent(pattern);
    infoEl.textContent = '正在加载结果...';
    const result = await fetchJsonWithTimeout(url, RESULT_FETCH_TIMEOUT_MS, '加载结果元数据');
    const resp = {ok: !!result.ok};
    const data = result.data || {};
    if(!resp.ok) throw new Error(data.error || '元数据加载失败');
    simState.steps = Array.isArray(data.steps) ? data.steps : [];
    simState.bounds = data.bounds || null;
    simState.frameIndex = 0;
    simState.points = [];
    simState.pointsRaw = [];
    simState.gateLabelOffsets.clear();
    simState.gateLabelBoxes = [];
    simState.gateLabelNodes = [];
    simState.draggingLabel = null;
    simState.stepCache.clear();
    simState.stepLoading.clear();
    fitBoundsToData();
    applyAutoZFromBounds();
    stepEl.min = '0';
    stepEl.max = String(Math.max(0, simState.steps.length-1));
    stepEl.value = '0';
    stepEl.disabled = simState.steps.length === 0;
    updateStepLabel();
    if(!simState.steps.length){
      const samples = Array.isArray(data.sampleFiles) ? data.sampleFiles.slice(0, 8) : [];
      const sampleText = samples.length ? ('；目录样例: ' + samples.join(', ')) : '';
      infoEl.textContent = '未找到匹配文件。root=' + String(data.root || root) + '，pattern=' + String(data.pattern || pattern) + sampleText;
      render();
      return;
    }
    await loadStep(0);
  }

  async function playNext(){
    if(!simState.steps.length) return;
    const next = (simState.frameIndex + 1) % simState.steps.length;
    try{ await loadStep(next); }catch(e){ stopPlay(); alert(String(e && e.message ? e.message : e)); }
  }

  async function togglePlay(){
    if(simState.playing){ stopPlay(); return; }
    if(!simState.steps.length){
      try{ await loadMeta(); }catch(e){ infoEl.textContent = '结果加载失败：' + String(e && e.message ? e.message : e); return; }
    }
    if(!simState.steps.length) return;
    const interval = Math.max(50, Math.min(10000, Number(intervalEl.value || 500)));
    simState.playing = true;
    document.getElementById('btnPlay').textContent = '暂停';
    simState.timer = setInterval(playNext, interval);
  }

  document.getElementById('btnLoadGrid').onclick = async ()=>{
    try{ await loadGridData(); }
    catch(e){ infoEl.textContent = '网格加载失败：' + String(e && e.message ? e.message : e); }
  };
  document.getElementById('btnLoadResult').onclick = async ()=>{
    try{ await loadMeta(); }
    catch(e){ infoEl.textContent = '结果加载失败：' + String(e && e.message ? e.message : e); }
  };
  document.getElementById('btnLoadCurve').onclick = async ()=>{
    try{ await loadCurveData(); }
    catch(e){ curveInfoEl.textContent = '曲线加载失败：' + String(e && e.message ? e.message : e); }
  };
  document.getElementById('btnPlayCurve').onclick = toggleCurvePlay;
  document.getElementById('btnCurveLoop').onclick = ()=>{
    simState.curve.loop = !simState.curve.loop;
    const btn = document.getElementById('btnCurveLoop');
    if(simState.curve.loop) btn.classList.add('active');
    else btn.classList.remove('active');
    curveInfoEl.textContent = '曲线循环: ' + (simState.curve.loop ? '开启' : '关闭');
  };
  document.getElementById('btnPlay').onclick = togglePlay;
  document.getElementById('btnStop').onclick = stopPlay;
  document.getElementById('btnApplyColor').onclick = applyColorControls;
  document.getElementById('btnAutoColor').onclick = ()=>{ applyAutoZFromBounds(); render(); };
  colorMapEl.addEventListener('change', ()=>{ simState.colorMap = String(colorMapEl.value || 'viridis'); render(); });
  cellSizeEl.addEventListener('change', ()=>{ const v = Number(cellSizeEl.value); if(Number.isFinite(v) && v > 0){ simState.cellSize = v; render(); } });
  showGatesEl.addEventListener('change', ()=>{ simState.showGates = String(showGatesEl.value || '1') === '1'; render(); });
  stepEl.addEventListener('input', async ()=>{
    stopPlay();
    try{ await loadStep(Number(stepEl.value || 0)); }
    catch(e){ infoEl.textContent = '结果加载失败：' + String(e && e.message ? e.message : e); }
  });

  function beginLabelDrag(ev){
    if(!simState.showGates) return false;
    const pt = canvasPointFromEvent(ev);

    let bestNode = null;
    let bestDist2 = Infinity;
    for(let i = simState.gateLabelNodes.length - 1; i >= 0; i--){
      const node = simState.gateLabelNodes[i];
      const dx = pt.x - Number(node.x);
      const dy = pt.y - Number(node.y);
      const d2 = dx*dx + dy*dy;
      const rr = Math.max(14, Number(node.r) || 11);
      if(d2 <= rr*rr && d2 < bestDist2){
        bestDist2 = d2;
        bestNode = node;
      }
    }
    if(bestNode){
      const savedNode = simState.gateLabelOffsets.get(bestNode.key);
      if(!savedNode) return false;
      simState.draggingLabel = {
        key: bestNode.key,
        startX: pt.x,
        startY: pt.y,
        baseTx: Number(savedNode.tx),
        baseTy: Number(savedNode.ty),
      };
      simState.dragPointerId = ev.pointerId;
      canvas.style.cursor = 'grabbing';
      return true;
    }

    for(let i = simState.gateLabelBoxes.length - 1; i >= 0; i--){
      const box = simState.gateLabelBoxes[i];
      if(pt.x >= box.left && pt.x <= box.right && pt.y >= box.top && pt.y <= box.bottom){
        const saved = simState.gateLabelOffsets.get(box.key);
        if(!saved) return false;
        simState.draggingLabel = {
          key: box.key,
          startX: pt.x,
          startY: pt.y,
          baseTx: Number(saved.tx),
          baseTy: Number(saved.ty),
        };
        simState.dragPointerId = ev.pointerId;
        canvas.style.cursor = 'grabbing';
        return true;
      }
    }
    return false;
  }

  function updateLabelDrag(ev){
    const drag = simState.draggingLabel;
    if(!drag) return;
    if(simState.dragPointerId !== null && ev.pointerId !== simState.dragPointerId) return;
    const pt = canvasPointFromEvent(ev);
    const nextTx = drag.baseTx + (pt.x - drag.startX);
    const nextTy = drag.baseTy + (pt.y - drag.startY);
    simState.gateLabelOffsets.set(drag.key, {tx: nextTx, ty: nextTy});
    render();
  }

  function endLabelDrag(ev){
    if(simState.dragPointerId !== null && ev && ev.pointerId !== simState.dragPointerId) return;
    if(simState.draggingLabel){
      simState.draggingLabel = null;
      simState.dragPointerId = null;
      canvas.style.cursor = 'default';
    }
  }

  canvas.addEventListener('pointerdown', (ev)=>{
    const started = beginLabelDrag(ev);
    if(started){
      try { canvas.setPointerCapture(ev.pointerId); } catch(_e) {}
      ev.preventDefault();
    }
  });
  canvas.addEventListener('pointermove', (ev)=>{ updateLabelDrag(ev); });
  canvas.addEventListener('pointerup', (ev)=>{ endLabelDrag(ev); });
  canvas.addEventListener('pointercancel', (ev)=>{ endLabelDrag(ev); });
  renderCurve();
  loadGridData().catch((e)=>{ infoEl.textContent = '网格加载失败：' + String(e && e.message ? e.message : e); });
<\/script>
</body>
</html>`;
  win.document.open();
  win.document.write(html);
  win.document.close();
}

async function saveData(){
  const savePath = scopePathToCurrentCase(document.getElementById('savePath').value.trim() || 'mesh/edges_new.csv');
  const resp = await fetch('/api/save', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({edges: state.edges, outputPath: savePath, backup: true})
  });
  const data = await resp.json();
  if(!resp.ok){ alert('保存失败: ' + (data.error||'')); return; }
  alert('保存成功: ' + data.savedTo);
}

async function saveEdgesCsv(){
  const target = casePathJoin('mesh/edges.csv');
  const savePathEl = document.getElementById('savePath');
  if(savePathEl) savePathEl.value = target;
  await saveData();
}

function openTopologyExportPanel(){
  const modal = document.getElementById('topologyExportModal');
  if(modal) modal.style.display = 'flex';
}

function closeTopologyExportPanel(){
  const modal = document.getElementById('topologyExportModal');
  if(modal) modal.style.display = 'none';
}

function triggerBlobDownload(blob, fileName){
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(()=>URL.revokeObjectURL(url), 1000);
}

function getSvgExportSize(){
  const vb = svg && svg.viewBox && svg.viewBox.baseVal ? svg.viewBox.baseVal : null;
  let width = vb && vb.width ? Number(vb.width) : 0;
  let height = vb && vb.height ? Number(vb.height) : 0;
  if(!(width > 0) || !(height > 0)){
    const rect = svg.getBoundingClientRect();
    width = Number(rect.width) || 1200;
    height = Number(rect.height) || 760;
  }
  return {width, height};
}

function makeSvgTextForExport(){
  const serializer = new XMLSerializer();
  const cloned = svg.cloneNode(true);
  if(!cloned.getAttribute('xmlns')) cloned.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  if(!cloned.getAttribute('xmlns:xlink')) cloned.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');
  const size = getSvgExportSize();
  if(!cloned.getAttribute('viewBox')) cloned.setAttribute('viewBox', `0 0 ${size.width} ${size.height}`);
  if(!cloned.getAttribute('width')) cloned.setAttribute('width', String(size.width));
  if(!cloned.getAttribute('height')) cloned.setAttribute('height', String(size.height));
  return '<?xml version="1.0" encoding="UTF-8"?>\n' + serializer.serializeToString(cloned);
}

function escapeXmlText(raw){
  return String(raw == null ? '' : raw)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function getLegendRowsForExport(){
  const cfg = state.legendConfig || {};
  const rows = [
    {kind: 'line', color: '#2563eb', dashed: false, text: String(cfg.channelEdgeLabel || '渠道边')},
    {kind: 'line', color: '#f59e0b', dashed: true, text: String(cfg.splitEdgeLabel || '分水边（虚拟节点->分汇水节点）')},
  ];
  const nodes = Array.isArray(state.lastLegendNodeItems) ? state.lastLegendNodeItems : [];
  nodes.forEach((it)=>{
    rows.push({
      kind: 'dot',
      color: normalizeHexColor(it && it.color, '#2563eb'),
      dashed: false,
      text: String((it && it.text) || ''),
    });
  });
  return rows;
}

function makeLegendSvgTextForExport(){
  const rows = getLegendRowsForExport();
  const lineHeight = 24;
  const pad = 14;
  const width = 640;
  const height = Math.max(84, pad * 2 + rows.length * lineHeight);
  const body = [];
  body.push(`<rect x="0.5" y="0.5" width="${width - 1}" height="${height - 1}" rx="10" ry="10" fill="#ffffff" stroke="#d9dee8" stroke-width="1" />`);
  rows.forEach((row, idx)=>{
    const y = pad + idx * lineHeight + 12;
    if(row.kind === 'line'){
      const dash = row.dashed ? ' stroke-dasharray="7 5"' : '';
      body.push(`<line x1="${pad}" y1="${y}" x2="${pad + 20}" y2="${y}" stroke="${escapeXmlText(row.color)}" stroke-width="3"${dash} />`);
    } else {
      body.push(`<circle cx="${pad + 10}" cy="${y}" r="5" fill="${escapeXmlText(row.color)}" />`);
    }
    body.push(`<text x="${pad + 30}" y="${y + 4}" font-size="14" fill="#1f2937" font-family="Microsoft YaHei, Arial, sans-serif">${escapeXmlText(row.text)}</text>`);
  });
  const svgText = `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">${body.join('')}</svg>`;
  return {svgText, width, height};
}

function canvasToBlobAsync(canvas, mimeType, quality){
  return new Promise((resolve, reject)=>{
    canvas.toBlob((blob)=>{
      if(blob) resolve(blob);
      else reject(new Error('canvas export failed'));
    }, mimeType, quality);
  });
}

function loadImageAsync(src){
  return new Promise((resolve, reject)=>{
    const image = new Image();
    image.onload = ()=>resolve(image);
    image.onerror = ()=>reject(new Error('image load failed'));
    image.src = src;
  });
}

async function exportTopologyImage(){
  const type = (document.getElementById('topologyExportType').value || 'png').toLowerCase();
  const scope = (document.getElementById('topologyExportScope').value || 'graph').toLowerCase();
  const dpiRaw = Number(document.getElementById('topologyExportDpi').value || 300);
  const dpi = Number.isFinite(dpiRaw) && dpiRaw > 0 ? dpiRaw : 300;
  const safeCase = String(state.currentCasePath || 'case').replace(/[^\w\-]+/g, '_');
  const exportName = scope === 'legend' ? 'legend' : 'topology';
  const fileName = `${exportName}_${safeCase}_${Date.now()}.${type}`;
  const legendSvg = scope === 'legend' ? makeLegendSvgTextForExport() : null;
  const svgText = scope === 'legend' ? legendSvg.svgText : makeSvgTextForExport();

  if(type === 'svg'){
    triggerBlobDownload(new Blob([svgText], {type: 'image/svg+xml;charset=utf-8'}), fileName);
    closeTopologyExportPanel();
    return;
  }

  const mimeMap = {
    png: 'image/png',
    jpg: 'image/jpeg',
    webp: 'image/webp',
  };
  const mimeType = mimeMap[type];
  if(!mimeType){
    alert('不支持的导出类型: ' + type);
    return;
  }

  const size = scope === 'legend'
    ? {width: legendSvg.width, height: legendSvg.height}
    : getSvgExportSize();
  const scale = Math.max(1, dpi / 96);
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(size.width * scale));
  canvas.height = Math.max(1, Math.round(size.height * scale));
  const ctx = canvas.getContext('2d');
  if(!ctx){
    alert('导出失败: 无法创建画布上下文');
    return;
  }

  if(type === 'jpg'){
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }

  const svgBlob = new Blob([svgText], {type: 'image/svg+xml;charset=utf-8'});
  const svgUrl = URL.createObjectURL(svgBlob);
  try{
    const image = await loadImageAsync(svgUrl);
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    const quality = type === 'jpg' || type === 'webp' ? 0.95 : undefined;
    const outBlob = await canvasToBlobAsync(canvas, mimeType, quality);
    triggerBlobDownload(outBlob, fileName);
    closeTopologyExportPanel();
  }catch(err){
    alert('导出失败: ' + (err && err.message ? err.message : err));
  }finally{
    URL.revokeObjectURL(svgUrl);
  }
}

function renderCurveCompareRows(){
  const host = document.getElementById('curveCompareRows');
  host.innerHTML = '';
  if(!Array.isArray(state.curveCompareItems) || state.curveCompareItems.length === 0){
    state.curveCompareItems = [{path:'', label:''}];
  }
  state.curveCompareItems.forEach((item, idx)=>{
    const row = document.createElement('div');
    row.className = 'compareRow';

    const pathInput = document.createElement('input');
    pathInput.className = 'filePathInput';
    pathInput.placeholder = '文件路径，如 output/stage.csv';
    pathInput.value = item.path || '';
    pathInput.oninput = ()=>{ state.curveCompareItems[idx].path = pathInput.value || ''; };

    const labelInput = document.createElement('input');
    labelInput.className = 'labelInput';
    labelInput.placeholder = 'label';
    labelInput.value = item.label || '';
    labelInput.oninput = ()=>{ state.curveCompareItems[idx].label = labelInput.value || ''; };

    const pickBtn = document.createElement('button');
    pickBtn.textContent = '路径选择';
    pickBtn.onclick = ()=> openComparePathPicker(idx);

    const delBtn = document.createElement('button');
    delBtn.textContent = '删';
    delBtn.className = 'danger';
    delBtn.onclick = ()=>{
      state.curveCompareItems.splice(idx, 1);
      if(state.curveCompareItems.length === 0){
        state.curveCompareItems.push({path:'', label:''});
      }
      renderCurveCompareRows();
    };

    row.appendChild(pathInput);
    row.appendChild(labelInput);
    row.appendChild(pickBtn);
    row.appendChild(delBtn);
    host.appendChild(row);
  });
}

function openCurveComparePanel(){
  const panel = document.getElementById('curveCompareModal');
  panel.style.display = 'flex';
  if(!Array.isArray(state.curveCompareItems) || state.curveCompareItems.length === 0){
    state.curveCompareItems = [
      {path: 'input/action_obs.csv', label: 'obs'},
      {path: 'input/action.csv', label: 'sim'},
    ];
  }
  renderCurveCompareRows();
}

function closeCurveComparePanel(){
  document.getElementById('curveCompareModal').style.display = 'none';
}

async function loadComparePathTree(){
  const rootPath = normalizeCasePath(state.currentCasePath || '.');
  const resp = await fetch(`/api/path-tree?root=${encodeURIComponent(rootPath)}&depth=4`);
  const data = await resp.json();
  const host = document.getElementById('comparePathTree');
  host.innerHTML = '';
  if(!resp.ok){
    const err = document.createElement('div');
    err.className = 'treeError';
    err.textContent = data.error || '路径层级加载失败';
    host.appendChild(err);
    return;
  }

  const root = String(data.root || rootPath || '.').replace(/\\/g, '/');
  const nodesByPath = new Map();
  const rootName = root.split('/').filter(Boolean).pop() || root;
  const rootNode = {name: rootName, path: root, isDir: true, children: []};
  nodesByPath.set(root, rootNode);

  (data.items || []).forEach(item=>{
    const p = String(item.path || '').replace(/\\/g, '/');
    if(!p) return;
    nodesByPath.set(p, {
      name: item.name || p,
      path: p,
      isDir: !!item.isDir,
      children: []
    });
  });

  (data.items || []).forEach(item=>{
    const p = String(item.path || '').replace(/\\/g, '/');
    const cur = nodesByPath.get(p);
    if(!cur) return;
    const slash = p.lastIndexOf('/');
    const parentPath = slash >= 0 ? p.slice(0, slash) : root;
    const parent = nodesByPath.get(parentPath) || rootNode;
    parent.children.push(cur);
  });

  const sortChildren = (node)=>{
    node.children.sort((a,b)=>{
      if(a.isDir !== b.isDir) return a.isDir ? -1 : 1;
      return String(a.name).localeCompare(String(b.name), 'zh-CN');
    });
    node.children.forEach(sortChildren);
  };
  sortChildren(rootNode);

  if(state.comparePathTreeExpanded[root] === undefined){
    state.comparePathTreeExpanded[root] = true;
  }

  const renderNode = (node, level)=>{
    const row = document.createElement('div');
    row.className = `treeRow ${node.isDir ? 'folder' : 'file'}`;
    row.style.paddingLeft = `${Math.max(0, level) * 14}px`;
    const expanded = !!state.comparePathTreeExpanded[node.path];

    const twist = document.createElement('span');
    twist.className = 'treeTwist';
    twist.textContent = node.isDir ? (expanded ? '▾' : '▸') : '';

    const icon = document.createElement('span');
    icon.className = 'treeIcon';
    icon.textContent = node.isDir ? '📁' : '📄';

    const name = document.createElement('span');
    name.className = 'treeName';
    name.textContent = node.name;

    row.appendChild(twist);
    row.appendChild(icon);
    row.appendChild(name);

    if(node.isDir){
      row.onclick = ()=>{
        state.comparePathTreeExpanded[node.path] = !expanded;
        loadComparePathTree();
      };
    } else {
      row.onclick = ()=>{
        const idx = state.comparePickRowIndex;
        if(idx !== null && idx >= 0 && idx < state.curveCompareItems.length){
          state.curveCompareItems[idx].path = node.path || '';
          renderCurveCompareRows();
        }
        closeComparePathPicker();
      };
    }

    host.appendChild(row);
    if(node.isDir && expanded){
      node.children.forEach(child=>renderNode(child, level + 1));
    }
  };
  renderNode(rootNode, 0);
}

function openComparePathPicker(rowIndex){
  state.comparePickRowIndex = rowIndex;
  document.getElementById('comparePathModal').style.display = 'flex';
  loadComparePathTree();
}

function closeComparePathPicker(){
  document.getElementById('comparePathModal').style.display = 'none';
  state.comparePickRowIndex = null;
}

function showDataToolsView(viewName){
  const views = {
    entry: document.getElementById('dataToolsEntryPanel'),
    analysis: document.getElementById('analysisConfigToolPanel'),
    baseline: document.getElementById('baselineToolPanel'),
    convert: document.getElementById('formatConvertToolPanel'),
  };
  Object.values(views).forEach(el=>{
    if(el) el.style.display = 'none';
  });
  const target = views[viewName] || views.entry;
  if(target) target.style.display = 'block';
}

function openDataToolsEntry(){
  showDataToolsView('entry');
}

function openAnalysisConfigTool(){
  showDataToolsView('analysis');
  loadAnalysisConfig();
}

function openBaselineTool(){
  showDataToolsView('baseline');
}

function openFormatConvertTool(){
  showDataToolsView('convert');
}

function openAnalysisConfigPanel(){
  document.getElementById('analysisConfigModal').style.display = 'flex';
  openDataToolsEntry();
}

function closeAnalysisConfigPanel(){
  openDataToolsEntry();
  document.getElementById('analysisConfigModal').style.display = 'none';
}

async function loadAnalysisConfig(){
  const path = scopePathToCurrentCase((document.getElementById('analysisConfigPath').value || 'mesh/Gates_param.csv').trim());
  const resp = await fetch(`/api/analyze-config?path=${encodeURIComponent(path)}`);
  const data = await resp.json();
  if(!resp.ok){
    alert('配置加载失败: ' + (data.error || 'unknown error'));
    return;
  }
  document.getElementById('analysisConfigPath').value = String(data.path || path);
  const content = String(data.content || '');
  document.getElementById('analysisConfigText').value = content;
  state.analysisConfig = parseCsvToTable(content);
  state.analysisConfigSelectedRows = new Set();
  resetAnalysisConfigHistory();
  renderAnalysisConfigTable();
}

function parseCsvToTable(content){
  const text = String(content || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  const lines = text.split('\n');
  while(lines.length && lines[lines.length - 1] === '') lines.pop();
  if(lines.length === 0){
    return {headers: ['region'], rows: [['']]};
  }

  function parseLine(line){
    const out = [];
    let current = '';
    let inQuote = false;
    for(let i = 0; i < line.length; i++){
      const ch = line[i];
      if(ch === '"'){
        if(inQuote && line[i + 1] === '"'){
          current += '"';
          i += 1;
        } else {
          inQuote = !inQuote;
        }
      } else if(ch === ',' && !inQuote){
        out.push(current);
        current = '';
      } else {
        current += ch;
      }
    }
    out.push(current);
    return out;
  }

  const matrix = lines.map(parseLine);
  const maxCols = matrix.reduce((acc, row)=>Math.max(acc, row.length), 0) || 1;
  matrix.forEach(row=>{
    while(row.length < maxCols) row.push('');
  });
  const headers = matrix[0].map((h, idx)=> String(h || `col${idx + 1}`));
  const rows = matrix.slice(1);
  if(rows.length === 0){
    rows.push(Array(headers.length).fill(''));
  }
  return {headers, rows};
}

function cloneAnalysisConfig(cfg){
  const safeCfg = cfg || {headers: [], rows: []};
  const headers = Array.isArray(safeCfg.headers) ? safeCfg.headers.map(v=>String(v || '')) : [];
  const rows = Array.isArray(safeCfg.rows)
    ? safeCfg.rows.map(row=> (Array.isArray(row) ? row.map(v=>String(v || '')) : []))
    : [];
  return {headers, rows};
}

function getAnalysisConfigSnapshot(){
  return JSON.stringify(cloneAnalysisConfig(state.analysisConfig || {headers: [], rows: []}));
}

function ensureAnalysisConfigHistoryState(){
  const h = state.analysisConfigHistory;
  if(!h || !Array.isArray(h.undo) || !Array.isArray(h.redo)){
    state.analysisConfigHistory = { undo: [], redo: [], maxDepth: 200, lastSnapshot: '' };
  }
}

function resetAnalysisConfigHistory(){
  ensureAnalysisConfigHistoryState();
  state.analysisConfigHistory.undo = [];
  state.analysisConfigHistory.redo = [];
  state.analysisConfigHistory.lastSnapshot = getAnalysisConfigSnapshot();
}

function recordAnalysisConfigBeforeChange(){
  ensureAnalysisConfigHistoryState();
  const h = state.analysisConfigHistory;
  const current = getAnalysisConfigSnapshot();
  if(current !== h.lastSnapshot){
    h.lastSnapshot = current;
  }
  h.undo.push(current);
  if(h.undo.length > h.maxDepth){
    h.undo.splice(0, h.undo.length - h.maxDepth);
  }
  h.redo = [];
}

function markAnalysisConfigChanged(){
  ensureAnalysisConfigHistoryState();
  state.analysisConfigHistory.lastSnapshot = getAnalysisConfigSnapshot();
}

function restoreAnalysisConfigFromSnapshot(snapshot){
  try {
    const parsed = JSON.parse(String(snapshot || '{}'));
    state.analysisConfig = cloneAnalysisConfig(parsed);
  } catch(_err){
    return false;
  }
  state.analysisConfigSelectedRows = new Set();
  ensureAnalysisConfigCellSelectionState();
  state.analysisConfigCellSelection = { anchor: null, focus: null, dragging: false, selected: new Set() };
  renderAnalysisConfigTable();
  return true;
}

function undoAnalysisConfigChange(){
  ensureAnalysisConfigHistoryState();
  const h = state.analysisConfigHistory;
  if(!h.undo.length) return;
  const current = getAnalysisConfigSnapshot();
  const previous = h.undo.pop();
  h.redo.push(current);
  if(restoreAnalysisConfigFromSnapshot(previous)){
    h.lastSnapshot = getAnalysisConfigSnapshot();
  }
}

function redoAnalysisConfigChange(){
  ensureAnalysisConfigHistoryState();
  const h = state.analysisConfigHistory;
  if(!h.redo.length) return;
  const current = getAnalysisConfigSnapshot();
  const next = h.redo.pop();
  h.undo.push(current);
  if(restoreAnalysisConfigFromSnapshot(next)){
    h.lastSnapshot = getAnalysisConfigSnapshot();
  }
}

function ensureAnalysisConfigCellSelectionState(){
  const sel = state.analysisConfigCellSelection;
  if(!sel || !(sel.selected instanceof Set)){
    state.analysisConfigCellSelection = { anchor: null, focus: null, dragging: false, selected: new Set() };
  }
}

function analysisConfigCellKey(row, col){
  return `${row}:${col}`;
}

function setAnalysisConfigCellSelectionRange(anchor, focus){
  ensureAnalysisConfigCellSelectionState();
  const sel = state.analysisConfigCellSelection;
  if(!anchor || !focus){
    sel.anchor = null;
    sel.focus = null;
    sel.selected = new Set();
    return;
  }
  const minRow = Math.min(anchor.row, focus.row);
  const maxRow = Math.max(anchor.row, focus.row);
  const minCol = Math.min(anchor.col, focus.col);
  const maxCol = Math.max(anchor.col, focus.col);
  const selected = new Set();
  for(let r = minRow; r <= maxRow; r++){
    for(let c = minCol; c <= maxCol; c++){
      selected.add(analysisConfigCellKey(r, c));
    }
  }
  sel.anchor = {row: anchor.row, col: anchor.col};
  sel.focus = {row: focus.row, col: focus.col};
  sel.selected = selected;
}

function applyAnalysisConfigCellSelectionVisual(){
  ensureAnalysisConfigCellSelectionState();
  const table = document.getElementById('analysisConfigTable');
  if(!table) return;
  const selected = state.analysisConfigCellSelection.selected;
  table.querySelectorAll('td[data-cell-key]').forEach(td=>{
    const key = String(td.getAttribute('data-cell-key') || '');
    const active = selected.has(key);
    td.classList.toggle('cellSelected', active);
    const inp = td.querySelector('input');
    if(inp) inp.classList.toggle('cellSelected', active);
  });
}

function beginAnalysisConfigCellSelection(row, col, event){
  if(event && event.button !== 0) return;
  ensureAnalysisConfigCellSelectionState();
  state.analysisConfigCellSelection.dragging = true;
  setAnalysisConfigCellSelectionRange({row, col}, {row, col});
  applyAnalysisConfigCellSelectionVisual();
}

function updateAnalysisConfigCellSelection(row, col){
  ensureAnalysisConfigCellSelectionState();
  const sel = state.analysisConfigCellSelection;
  if(!sel.dragging || !sel.anchor) return;
  setAnalysisConfigCellSelectionRange(sel.anchor, {row, col});
  applyAnalysisConfigCellSelectionVisual();
}

function endAnalysisConfigCellSelection(){
  ensureAnalysisConfigCellSelectionState();
  state.analysisConfigCellSelection.dragging = false;
}

function clearSelectedAnalysisConfigCells(){
  ensureAnalysisConfigCellSelectionState();
  const selected = state.analysisConfigCellSelection.selected;
  if(!(selected instanceof Set) || selected.size === 0) return;
  const cfg = state.analysisConfig || {headers: [], rows: []};
  const rows = Array.isArray(cfg.rows) ? cfg.rows : [];
  const targets = Array.from(selected);
  let changed = false;
  for(const key of targets){
    const parts = String(key).split(':');
    const r = Number.parseInt(parts[0], 10);
    const c = Number.parseInt(parts[1], 10);
    if(!Number.isInteger(r) || !Number.isInteger(c)) continue;
    if(r < 0 || c < 0) continue;
    if(r >= rows.length) continue;
    if(!Array.isArray(rows[r])) continue;
    if(c >= rows[r].length) continue;
    if(String(rows[r][c] || '') !== '') changed = true;
  }
  if(!changed) return;
  recordAnalysisConfigBeforeChange();
  for(const key of targets){
    const parts = String(key).split(':');
    const r = Number.parseInt(parts[0], 10);
    const c = Number.parseInt(parts[1], 10);
    if(!Number.isInteger(r) || !Number.isInteger(c)) continue;
    if(r < 0 || c < 0) continue;
    if(r >= rows.length) continue;
    if(!Array.isArray(rows[r])) continue;
    if(c >= rows[r].length) continue;
    rows[r][c] = '';
  }
  state.analysisConfig = cfg;
  markAnalysisConfigChanged();
  renderAnalysisConfigTable();
}

function handleAnalysisConfigHotkeys(event){
  const modal = document.getElementById('analysisConfigModal');
  if(!modal || modal.style.display !== 'flex') return;
  const panel = document.getElementById('analysisConfigToolPanel');
  if(!panel || panel.style.display === 'none') return;
  const target = event.target;
  if(target && target.tagName === 'TEXTAREA') return;
  const key = String(event.key || '').toLowerCase();
  const ctrlOrMeta = !!(event.ctrlKey || event.metaKey);

  if(ctrlOrMeta && key === 'z'){
    event.preventDefault();
    undoAnalysisConfigChange();
    return;
  }
  if(ctrlOrMeta && key === 'y'){
    event.preventDefault();
    redoAnalysisConfigChange();
    return;
  }
  if(!ctrlOrMeta && !event.altKey && key === 'delete'){
    event.preventDefault();
    clearSelectedAnalysisConfigCells();
  }
}

function renderAnalysisConfigTable(){
  const table = document.getElementById('analysisConfigTable');
  const thead = table.querySelector('thead');
  const tbody = table.querySelector('tbody');
  const cfg = state.analysisConfig || {headers: [], rows: []};
  if(!(state.analysisConfigSelectedRows instanceof Set)){
    state.analysisConfigSelectedRows = new Set();
  }
  const headers = Array.isArray(cfg.headers) ? cfg.headers : [];
  const rows = Array.isArray(cfg.rows) ? cfg.rows : [];

  thead.innerHTML = '';
  tbody.innerHTML = '';

  const trHead = document.createElement('tr');
  const thSel = document.createElement('th');
  thSel.className = 'chkCol';
  const chkAll = document.createElement('input');
  chkAll.type = 'checkbox';
  chkAll.checked = rows.length > 0 && state.analysisConfigSelectedRows.size === rows.length;
  chkAll.onchange = ()=>{
    if(chkAll.checked) selectAllAnalysisConfigRows();
    else clearAnalysisConfigSelection();
  };
  thSel.appendChild(chkAll);
  trHead.appendChild(thSel);
  headers.forEach(h=>{
    const th = document.createElement('th');
    th.textContent = String(h || '');
    trHead.appendChild(th);
  });
  const thAct = document.createElement('th');
  thAct.className = 'actCol';
  thAct.textContent = '操作';
  trHead.appendChild(thAct);
  thead.appendChild(trHead);

  rows.forEach((row, rIdx)=>{
    const tr = document.createElement('tr');
    if(state.analysisConfigSelectedRows.has(rIdx)) tr.classList.add('sel');
    const tdSel = document.createElement('td');
    tdSel.className = 'chkCol';
    const chk = document.createElement('input');
    chk.type = 'checkbox';
    chk.checked = state.analysisConfigSelectedRows.has(rIdx);
    chk.onchange = ()=>{
      if(chk.checked) state.analysisConfigSelectedRows.add(rIdx);
      else state.analysisConfigSelectedRows.delete(rIdx);
      renderAnalysisConfigTable();
    };
    tdSel.appendChild(chk);
    tr.appendChild(tdSel);
    headers.forEach((_, cIdx)=>{
      const td = document.createElement('td');
      td.setAttribute('data-cell-key', analysisConfigCellKey(rIdx, cIdx));
      const inp = document.createElement('input');
      inp.value = String((row && row[cIdx]) || '');
      inp.onmousedown = (event)=> beginAnalysisConfigCellSelection(rIdx, cIdx, event);
      inp.onmouseenter = ()=> updateAnalysisConfigCellSelection(rIdx, cIdx);
      inp.oninput = ()=>{
        recordAnalysisConfigBeforeChange();
        state.analysisConfig.rows[rIdx][cIdx] = inp.value;
        markAnalysisConfigChanged();
      };
      td.appendChild(inp);
      tr.appendChild(td);
    });
    const tdAct = document.createElement('td');
    tdAct.className = 'actCol';
    const btnDel = document.createElement('button');
    btnDel.className = 'danger';
    btnDel.textContent = '删行';
    btnDel.onclick = ()=>{
      recordAnalysisConfigBeforeChange();
      state.analysisConfig.rows.splice(rIdx, 1);
      state.analysisConfigSelectedRows = new Set();
      if(state.analysisConfig.rows.length === 0){
        state.analysisConfig.rows.push(Array(headers.length).fill(''));
      }
      markAnalysisConfigChanged();
      renderAnalysisConfigTable();
      syncAnalysisConfigText();
    };
    tdAct.appendChild(btnDel);
    tr.appendChild(tdAct);
    tbody.appendChild(tr);
  });
  applyAnalysisConfigCellSelectionVisual();
  syncAnalysisConfigText();
}

function selectAllAnalysisConfigRows(){
  const rows = (((state.analysisConfig || {}).rows) || []);
  state.analysisConfigSelectedRows = new Set(rows.map((_, idx)=>idx));
  renderAnalysisConfigTable();
}

function clearAnalysisConfigSelection(){
  state.analysisConfigSelectedRows = new Set();
  renderAnalysisConfigTable();
}

function deleteSelectedAnalysisConfigRows(){
  const cfg = state.analysisConfig || {headers: ['region'], rows: []};
  const rows = Array.isArray(cfg.rows) ? cfg.rows : [];
  const selected = state.analysisConfigSelectedRows instanceof Set
    ? new Set(state.analysisConfigSelectedRows)
    : new Set();
  if(selected.size === 0){
    alert('请先选择要删除的行。');
    return;
  }
  recordAnalysisConfigBeforeChange();
  cfg.rows = rows.filter((_, idx)=> !selected.has(idx));
  if(cfg.rows.length === 0){
    cfg.rows.push(Array(Math.max(1, (cfg.headers || []).length)).fill(''));
  }
  state.analysisConfig = cfg;
  state.analysisConfigSelectedRows = new Set();
  markAnalysisConfigChanged();
  renderAnalysisConfigTable();
}

function csvEscapeCell(v){
  const s = String(v == null ? '' : v);
  if(/[",\n]/.test(s)){
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

function syncAnalysisConfigText(){
  const cfg = state.analysisConfig || {headers: [], rows: []};
  const headers = Array.isArray(cfg.headers) ? cfg.headers : [];
  const rows = Array.isArray(cfg.rows) ? cfg.rows : [];
  const lines = [];
  lines.push(headers.map(csvEscapeCell).join(','));
  rows.forEach(row=>{
    lines.push(headers.map((_, idx)=> csvEscapeCell((row && row[idx]) || '')).join(','));
  });
  document.getElementById('analysisConfigText').value = lines.join('\n');
}

function addAnalysisConfigRow(){
  const cfg = state.analysisConfig || {headers: ['region'], rows: []};
  const width = Math.max(1, (cfg.headers || []).length);
  const countRaw = Number.parseInt((document.getElementById('analysisConfigAddCount').value || '1'), 10);
  const count = Math.max(1, Math.min(200, Number.isFinite(countRaw) ? countRaw : 1));
  if(!Array.isArray(cfg.rows)) cfg.rows = [];
  recordAnalysisConfigBeforeChange();
  for(let i = 0; i < count; i++){
    cfg.rows.push(Array(width).fill(''));
  }
  state.analysisConfig = cfg;
  state.analysisConfigSelectedRows = new Set();
  markAnalysisConfigChanged();
  renderAnalysisConfigTable();
}

async function saveAnalysisConfig(){
  const path = (document.getElementById('analysisConfigPath').value || 'mesh/Gates_param.csv').trim();
  syncAnalysisConfigText();
  const content = String(document.getElementById('analysisConfigText').value || '');
  const resp = await fetch('/api/analyze-config', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({path, content})
  });
  const data = await resp.json();
  if(!resp.ok){
    alert('配置保存失败: ' + (data.error || 'unknown error'));
    return;
  }
  alert('配置保存成功: ' + (data.savedTo || path));
}

async function runBaselineProcess(){
  const inputPath = scopePathToCurrentCase((document.getElementById('baselineInputPath').value || '').trim());
  const outputPathRaw = (document.getElementById('baselineOutputPath').value || '').trim();
  const outputPath = outputPathRaw ? scopePathToCurrentCase(outputPathRaw) : '';
  const baselineMode = String(document.getElementById('baselineMode').value || 'first_non_empty').trim() || 'first_non_empty';
  const baselineValueRaw = (document.getElementById('baselineValue').value || '').trim();
  const baselineColumnsRaw = String(document.getElementById('baselineColumns').value || '').trim();
  const columns = baselineColumnsRaw
    ? baselineColumnsRaw.split(',').map(v=>String(v || '').trim()).filter(Boolean)
    : [];
  if(!inputPath){
    alert('请输入基准处理输入文件。');
    return;
  }
  let baselineValue = null;
  if(baselineMode === 'fixed'){
    const parsed = Number(baselineValueRaw);
    if(!Number.isFinite(parsed)){
      alert('固定基准值必须是数值。');
      return;
    }
    baselineValue = parsed;
  }
  const resultEl = document.getElementById('baselineResult');
  if(resultEl) resultEl.textContent = '正在执行基准值处理...';
  const resp = await fetch('/api/data-tools', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({
      action: 'baseline_adjust',
      inputPath,
      outputPath,
      baselineMode,
      baselineValue,
      columns,
    })
  });
  const data = await resp.json();
  if(!resp.ok){
    if(resultEl) resultEl.textContent = '基准值处理失败: ' + (data.error || 'unknown error');
    alert('基准值处理失败: ' + (data.error || 'unknown error'));
    return;
  }
  if(resultEl){
    resultEl.textContent = `基准值处理完成：${data.outputPath || ''}；处理列数 ${data.columnCount || 0}；处理行数 ${data.rowCount || 0}`;
  }
}

async function runFormatConvert(){
  const inputPath = scopePathToCurrentCase((document.getElementById('convertInputPath').value || '').trim());
  const mode = String(document.getElementById('convertMode').value || 'pivot_to_tidy').trim() || 'pivot_to_tidy';
  const outputPathRaw = (document.getElementById('convertOutputPath').value || '').trim();
  const outputPath = outputPathRaw ? scopePathToCurrentCase(outputPathRaw) : '';
  if(!inputPath){
    alert('请输入格式转换输入文件。');
    return;
  }
  const resultEl = document.getElementById('formatConvertResult');
  if(resultEl) resultEl.textContent = '正在执行格式转换...';
  const resp = await fetch('/api/data-tools', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({
      action: 'format_convert',
      inputPath,
      outputPath,
      mode,
      timeColumn: 'tm',
      objColumn: 'obj',
      valueColumn: 'value',
    })
  });
  const data = await resp.json();
  if(!resp.ok){
    if(resultEl) resultEl.textContent = '格式转换失败: ' + (data.error || 'unknown error');
    alert('格式转换失败: ' + (data.error || 'unknown error'));
    return;
  }
  if(resultEl){
    resultEl.textContent = `格式转换完成：${data.outputPath || ''}；模式 ${data.mode || mode}`;
  }
}

function openCurveCompareWindow(data){
  const win = window.open('', '_blank', 'width=1080,height=700');
  if(!win){
    alert('弹窗被浏览器拦截，请允许弹窗后重试。');
    return;
  }
  const payload = JSON.stringify(data || {});
  const html = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>曲线对比结果</title>
  <style>
    body{margin:0;font-family:"Microsoft YaHei",Arial,sans-serif;background:#f5f7fb;color:#1f2937;}
    .wrap{padding:12px;display:grid;grid-template-columns:minmax(320px,380px) 1fr;gap:10px;height:100vh;}
    .panel{background:#fff;border:1px solid #d9dee8;border-radius:10px;padding:10px;overflow:auto;}
    .title{font-size:16px;font-weight:700;margin:0 0 8px 0;}
    .row{display:flex;align-items:center;gap:8px;margin-bottom:8px;}
    .row label{width:90px;flex:0 0 90px;font-size:12px;color:#6b7280;}
    .row input,.row select{flex:1;border:1px solid #d9dee8;border-radius:6px;padding:6px;font-size:12px;}
    .items{border:1px solid #e5e7eb;border-radius:8px;padding:8px;max-height:280px;overflow:auto;background:#fafafa;}
    .itemRow{display:grid;grid-template-columns:1fr 120px 44px;gap:6px;margin-bottom:6px;}
    .btns{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;}
    button{border:1px solid #d9dee8;background:#fff;padding:6px 10px;border-radius:6px;cursor:pointer;font-size:12px;}
    button.primary{background:#2563eb;color:#fff;border-color:#2563eb;}
    button.danger{background:#dc2626;color:#fff;border-color:#dc2626;}
    .meta{font-size:12px;color:#6b7280;margin:6px 0;word-break:break-all;}
    .err{font-size:12px;color:#dc2626;min-height:18px;}
    .typeFilterBox{border:1px solid #e5e7eb;border-radius:8px;padding:8px;max-height:120px;overflow:auto;background:#fafafa;}
    .typeItem{display:flex;align-items:center;gap:6px;font-size:12px;margin-bottom:4px;}
    .typeItem:last-child{margin-bottom:0;}
    .typeTools{display:flex;gap:8px;margin-top:6px;}
    .typeTools button{padding:4px 8px;font-size:11px;}
    .gateFilterBox{border:1px solid #e5e7eb;border-radius:8px;padding:8px;max-height:140px;overflow:auto;background:#fafafa;}
    .gateItem{display:flex;align-items:center;gap:6px;font-size:12px;margin-bottom:4px;}
    .gateItem:last-child{margin-bottom:0;}
    .gateTools{display:flex;gap:8px;margin-top:6px;}
    .gateTools button{padding:4px 8px;font-size:11px;}
    .imgWrap{height:calc(100vh - 48px);display:flex;align-items:flex-start;justify-content:center;overflow:auto;}
    #img{max-width:100%;border:1px solid #d9dee8;border-radius:8px;background:#fff;}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <div class="title">曲线对比参数（实时更新）</div>
      <div class="row"><label>Y列名</label><input id="yColumn" placeholder="留空自动" /></div>
      <div class="row"><label>X下限</label><input id="xMin" type="number" step="any" placeholder="留空自动" /></div>
      <div class="row"><label>X上限</label><input id="xMax" type="number" step="any" placeholder="留空自动" /></div>
      <div class="row"><label>Y下限</label><input id="yMin" type="number" step="any" placeholder="留空自动" /></div>
      <div class="row"><label>Y上限</label><input id="yMax" type="number" step="any" placeholder="留空自动" /></div>
      <div class="row"><label>DPI</label>
        <select id="dpi">
          <option value="100">100</option>
          <option value="200">200</option>
          <option value="300">300</option>
          <option value="600">600</option>
        </select>
      </div>
      <div class="row"><label>画布宽度</label><input id="figW" type="number" min="4" max="80" step="1" /></div>
      <div class="row"><label>画布高度</label><input id="figH" type="number" min="4" max="80" step="1" /></div>
      <div class="row"><label>字号</label><input id="fontSize" type="number" min="8" max="48" step="1" /></div>
      <div class="row"><label>图例X</label><input id="legendX" type="number" min="0" max="1.2" step="0.01" /></div>
      <div class="row"><label>图例Y</label><input id="legendY" type="number" min="0" max="1.4" step="0.01" /></div>
      <div class="row" style="align-items:flex-start;"><label style="margin-top:6px;">节点类型</label>
        <div style="flex:1;">
          <div id="typeFilterBox" class="typeFilterBox"></div>
          <div class="typeTools">
            <button id="btnTypeAll" type="button">全选</button>
            <button id="btnTypeNone" type="button">清空</button>
          </div>
        </div>
      </div>
      <div class="row" style="align-items:flex-start;"><label style="margin-top:6px;">闸门</label>
        <div style="flex:1;">
          <div id="gateFilterBox" class="gateFilterBox"></div>
          <div class="gateTools">
            <button id="btnGateAll" type="button">全选</button>
            <button id="btnGateNone" type="button">清空</button>
          </div>
        </div>
      </div>
      <div class="row"><label style="align-self:flex-start;margin-top:6px;">对比文件</label>
        <div style="flex:1;">
          <div class="items" id="items"></div>
          <div class="btns"><button id="addRow">新增一行</button></div>
        </div>
      </div>
      <div class="btns">
        <button id="applyNow" class="primary">立即更新</button>
        <button id="download">下载图片</button>
      </div>
      <div class="meta" id="meta"></div>
      <div class="err" id="err"></div>
    </div>
    <div class="panel" style="padding:8px;">
      <div class="imgWrap"><img id="img" alt="curve-compare" /></div>
    </div>
  </div>
<script>
  const data = ${payload};
  const imgEl = document.getElementById('img');
  const metaEl = document.getElementById('meta');
  const errEl = document.getElementById('err');
  const yColumnEl = document.getElementById('yColumn');
  const xMinEl = document.getElementById('xMin');
  const xMaxEl = document.getElementById('xMax');
  const yMinEl = document.getElementById('yMin');
  const yMaxEl = document.getElementById('yMax');
  const dpiEl = document.getElementById('dpi');
  const figWEl = document.getElementById('figW');
  const figHEl = document.getElementById('figH');
  const fontSizeEl = document.getElementById('fontSize');
  const legendXEl = document.getElementById('legendX');
  const legendYEl = document.getElementById('legendY');
  const typeFilterBox = document.getElementById('typeFilterBox');
  const gateFilterBox = document.getElementById('gateFilterBox');
  const itemsHost = document.getElementById('items');

  let updateTimer = null;
  let latestImage = String(data.imageDataUrl || '');
  let initialItems = [];
  if(data && data.request && Array.isArray(data.request.items)){
    initialItems = data.request.items.map(it=>({path:String((it && it.path) || ''), label:String((it && it.label) || '')}));
  }
  if(initialItems.length === 0){
    initialItems = [{path:'', label:''}];
  }

  const state = {
    items: initialItems,
    nodeTypes: (Array.isArray(data.nodeTypes) ? data.nodeTypes : []).map(v=>String(v || '').trim()).filter(Boolean),
    selectedNodeTypes: new Set(),
    gateOptions: (Array.isArray(data.gateOptions) ? data.gateOptions : []).map(g=>({
      name: String((g && g.name) || '').trim(),
      nodeType: String((g && g.nodeType) || '未分类').trim() || '未分类',
    })).filter(g=>g.name),
    selectedGates: new Set(),
  };
  if(state.nodeTypes.length === 0){
    state.nodeTypes = ['未分类'];
  }
  const initSelected = (data && data.request && Array.isArray(data.request.selectedNodeTypes))
    ? data.request.selectedNodeTypes
    : (Array.isArray(data.selectedNodeTypes) ? data.selectedNodeTypes : state.nodeTypes);
  initSelected.forEach(v=>{
    const t = String(v || '').trim();
    if(t) state.selectedNodeTypes.add(t);
  });
  if(state.selectedNodeTypes.size === 0){
    state.nodeTypes.forEach(t=>state.selectedNodeTypes.add(t));
  }

  if(state.gateOptions.length === 0 && Array.isArray(data.selectedGates)){
    state.gateOptions = data.selectedGates.map(n=>({name:String(n || '').trim(), nodeType:'未分类'})).filter(g=>g.name);
  }
  const initSelectedGates = (data && data.request && Array.isArray(data.request.selectedGates))
    ? data.request.selectedGates
    : (Array.isArray(data.selectedGates) ? data.selectedGates : state.gateOptions.map(g=>g.name));
  initSelectedGates.forEach(v=>{
    const name = String(v || '').trim();
    if(name) state.selectedGates.add(name);
  });

  function allowedGateOptions(){
    return state.gateOptions.filter(g=> state.selectedNodeTypes.has(g.nodeType));
  }

  function normalizeGateSelection(autoFill=true){
    const allowed = allowedGateOptions();
    const allowedSet = new Set(allowed.map(g=>g.name));
    state.selectedGates = new Set(Array.from(state.selectedGates).filter(name=>allowedSet.has(name)));
    if(autoFill && state.selectedGates.size === 0){
      allowed.forEach(g=>state.selectedGates.add(g.name));
    }
  }

  function renderTypeFilters(){
    typeFilterBox.innerHTML = '';
    state.nodeTypes.forEach(tp=>{
      const row = document.createElement('label');
      row.className = 'typeItem';
      const chk = document.createElement('input');
      chk.type = 'checkbox';
      chk.checked = state.selectedNodeTypes.has(tp);
      chk.onchange = ()=>{
        if(chk.checked) state.selectedNodeTypes.add(tp);
        else state.selectedNodeTypes.delete(tp);
        normalizeGateSelection(true);
        renderGateFilters();
        scheduleUpdate();
      };
      const txt = document.createElement('span');
      txt.textContent = tp;
      row.appendChild(chk);
      row.appendChild(txt);
      typeFilterBox.appendChild(row);
    });
  }

  function renderGateFilters(){
    gateFilterBox.innerHTML = '';
    const options = allowedGateOptions();
    if(options.length === 0){
      const empty = document.createElement('div');
      empty.className = 'meta';
      empty.textContent = '当前类型下无可选闸门';
      gateFilterBox.appendChild(empty);
      return;
    }
    options.forEach(g=>{
      const row = document.createElement('label');
      row.className = 'gateItem';
      const chk = document.createElement('input');
      chk.type = 'checkbox';
      chk.checked = state.selectedGates.has(g.name);
      chk.onchange = ()=>{
        if(chk.checked) state.selectedGates.add(g.name);
        else state.selectedGates.delete(g.name);
        scheduleUpdate();
      };
      const txt = document.createElement('span');
      txt.textContent = g.name;
      row.appendChild(chk);
      row.appendChild(txt);
      gateFilterBox.appendChild(row);
    });
  }

  function renderItems(){
    itemsHost.innerHTML = '';
    state.items.forEach((it, idx)=>{
      const row = document.createElement('div');
      row.className = 'itemRow';
      const p = document.createElement('input');
      p.placeholder = '文件路径';
      p.value = it.path || '';
      p.oninput = ()=>{ state.items[idx].path = p.value || ''; scheduleUpdate(); };
      const l = document.createElement('input');
      l.placeholder = 'label';
      l.value = it.label || '';
      l.oninput = ()=>{ state.items[idx].label = l.value || ''; scheduleUpdate(); };
      const del = document.createElement('button');
      del.className = 'danger';
      del.textContent = '删';
      del.onclick = ()=>{
        state.items.splice(idx, 1);
        if(state.items.length === 0) state.items.push({path:'', label:''});
        renderItems();
        scheduleUpdate();
      };
      row.appendChild(p);
      row.appendChild(l);
      row.appendChild(del);
      itemsHost.appendChild(row);
    });
  }

  function parseOptionalNumber(inputEl){
    const raw = String((inputEl && inputEl.value) || '').trim();
    if(!raw) return null;
    const val = Number(raw);
    return Number.isFinite(val) ? val : null;
  }

  function setOptionalInputValue(inputEl, value){
    if(value === null || value === undefined || value === ''){
      inputEl.value = '';
      return;
    }
    inputEl.value = String(value);
  }

  function formatRangeValue(v){
    return (v === null || v === undefined || v === '') ? '自动' : String(v);
  }

  function collectPayload(){
    const dpi = Number.parseInt(dpiEl.value || '300', 10) || 300;
    const figSizeX = Number.parseFloat(figWEl.value || '20') || 20;
    const figSizeY = Number.parseFloat(figHEl.value || '10') || 10;
    const fontSize = Number.parseInt(fontSizeEl.value || '16', 10) || 16;
    const legendX = Number.parseFloat(legendXEl.value || '0.52');
    const legendY = Number.parseFloat(legendYEl.value || '1.00');
    const yColumn = String(yColumnEl.value || '').trim();
    const items = state.items
      .map(it=>({path:String((it && it.path) || '').trim(), label:String((it && it.label) || '').trim()}))
      .filter(it=>it.path);
    const selectedNodeTypes = Array.from(state.selectedNodeTypes);
    const selectedGates = Array.from(state.selectedGates);
    const xMin = parseOptionalNumber(xMinEl);
    const xMax = parseOptionalNumber(xMaxEl);
    const yMin = parseOptionalNumber(yMinEl);
    const yMax = parseOptionalNumber(yMaxEl);
    return {items, yColumn, xMin, xMax, yMin, yMax, dpi, figSizeX, figSizeY, fontSize, legendX, legendY, selectedNodeTypes, selectedGates};
  }

  function setMeta(result){
    metaEl.textContent = (result.title || 'MultipleWaterLevelContrast_error') +
      '，对比文件数: ' + String(result.lineCount || 0) +
      '，输出: ' + String(result.outputPath || '') +
      '，DPI: ' + String(result.dpi || 300) +
        '，画布: ' + String(result.figSizeX || 20) + '×' + String(result.figSizeY || 10) +
        '，字号: ' + String(result.fontSize || 16) +
          '，图例: (' + String(result.legendX || 0.52) + ', ' + String(result.legendY || 1.0) + ')' +
          '，节点类型: ' + String((result.selectedNodeTypes || []).join(', ') || '全部') +
          '，闸门数: ' + String((result.selectedGates || []).length || 0) +
          '，X范围: [' + formatRangeValue(result.xMin) + ', ' + formatRangeValue(result.xMax) + ']' +
          '，Y范围: [' + formatRangeValue(result.yMin) + ', ' + formatRangeValue(result.yMax) + ']';
  }

  async function refreshImage(){
    const req = collectPayload();
    if(!req.items.length){
      errEl.textContent = '请至少填写一个有效文件路径。';
      return;
    }
    errEl.textContent = '更新中...';
    try{
      const resp = await fetch('/api/curve-compare', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(req)
      });
      const result = await resp.json();
      if(!resp.ok){
        throw new Error(result.error || 'unknown error');
      }
      latestImage = String(result.imageDataUrl || '');
      imgEl.src = latestImage;
      if(Array.isArray(result.nodeTypes) && result.nodeTypes.length){
        state.nodeTypes = result.nodeTypes.map(v=>String(v || '').trim()).filter(Boolean);
      }
      if(Array.isArray(result.selectedNodeTypes)){
        state.selectedNodeTypes = new Set(result.selectedNodeTypes.map(v=>String(v || '').trim()).filter(Boolean));
      }
      if(Array.isArray(result.gateOptions)){
        state.gateOptions = result.gateOptions.map(g=>({
          name: String((g && g.name) || '').trim(),
          nodeType: String((g && g.nodeType) || '未分类').trim() || '未分类',
        })).filter(g=>g.name);
      }
      if(Array.isArray(result.selectedGates)){
        state.selectedGates = new Set(result.selectedGates.map(v=>String(v || '').trim()).filter(Boolean));
      }
      if(state.selectedNodeTypes.size === 0){
        state.nodeTypes.forEach(t=>state.selectedNodeTypes.add(t));
      }
      normalizeGateSelection(true);
      renderTypeFilters();
      renderGateFilters();
      setMeta(result);
      errEl.textContent = '';
    }catch(e){
      errEl.textContent = '更新失败: ' + String(e && e.message ? e.message : e);
    }
  }

  function scheduleUpdate(){
    if(updateTimer){ clearTimeout(updateTimer); }
    updateTimer = setTimeout(refreshImage, 500);
  }

  document.getElementById('addRow').onclick = ()=>{
    state.items.push({path:'', label:'line' + String(state.items.length + 1)});
    renderItems();
  };
  document.getElementById('btnTypeAll').onclick = ()=>{ state.selectedNodeTypes = new Set(state.nodeTypes); normalizeGateSelection(true); renderTypeFilters(); renderGateFilters(); scheduleUpdate(); };
  document.getElementById('btnTypeNone').onclick = ()=>{ state.selectedNodeTypes = new Set(); normalizeGateSelection(true); renderTypeFilters(); renderGateFilters(); scheduleUpdate(); };
  document.getElementById('btnGateAll').onclick = ()=>{ state.selectedGates = new Set(allowedGateOptions().map(g=>g.name)); renderGateFilters(); scheduleUpdate(); };
  document.getElementById('btnGateNone').onclick = ()=>{ state.selectedGates = new Set(); renderGateFilters(); scheduleUpdate(); };
  document.getElementById('applyNow').onclick = refreshImage;
  document.getElementById('download').onclick = ()=>{
    if(!latestImage) return;
    const a = document.createElement('a');
    a.href = latestImage;
    const dpi = String(dpiEl.value || 300);
    a.download = 'curve_compare_' + dpi + 'dpi.png';
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  [yColumnEl, xMinEl, xMaxEl, yMinEl, yMaxEl, dpiEl, figWEl, figHEl, fontSizeEl, legendXEl, legendYEl].forEach(el=>{
    el.addEventListener('input', scheduleUpdate);
    el.addEventListener('change', scheduleUpdate);
  });

  yColumnEl.value = String((data.request && data.request.yColumn) || '');
  setOptionalInputValue(xMinEl, (data.request && data.request.xMin) ?? data.xMin);
  setOptionalInputValue(xMaxEl, (data.request && data.request.xMax) ?? data.xMax);
  setOptionalInputValue(yMinEl, (data.request && data.request.yMin) ?? data.yMin);
  setOptionalInputValue(yMaxEl, (data.request && data.request.yMax) ?? data.yMax);
  dpiEl.value = String((data.request && data.request.dpi) || data.dpi || 300);
  figWEl.value = String((data.request && data.request.figSizeX) || data.figSizeX || 20);
  figHEl.value = String((data.request && data.request.figSizeY) || data.figSizeY || 10);
  fontSizeEl.value = String((data.request && data.request.fontSize) || data.fontSize || 16);
  legendXEl.value = String((data.request && data.request.legendX) || data.legendX || 0.52);
  legendYEl.value = String((data.request && data.request.legendY) || data.legendY || 1.00);
  normalizeGateSelection(true);
  renderTypeFilters();
  renderGateFilters();
  renderItems();
  if(latestImage){ imgEl.src = latestImage; }
  setMeta(data || {});
<\/script>
</body>
</html>`;
  win.document.open();
  win.document.write(html);
  win.document.close();
}

async function submitCurveCompare(){
  const yColumn = (document.getElementById('compareYColumn').value || '').trim();
  const dpi = Number.parseInt((document.getElementById('compareDpi').value || '300'), 10) || 300;
  const figSizeX = Number.parseFloat((document.getElementById('compareFigWidth').value || '20')) || 20;
  const figSizeY = Number.parseFloat((document.getElementById('compareFigHeight').value || '10')) || 10;
  const fontSize = Number.parseInt((document.getElementById('compareFontSize').value || '16'), 10) || 16;
  const items = (state.curveCompareItems || [])
    .map(it=>({
      path: scopePathToCurrentCase(String((it && it.path) || '').trim()),
      label: String((it && it.label) || '').trim()
    }))
    .filter(it=>it.path);
  if(items.length === 0){
    alert('请至少选择一个文件。');
    return;
  }
  const resp = await fetch('/api/curve-compare', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({items, yColumn, dpi, figSizeX, figSizeY, fontSize})
  });
  const data = await resp.json();
  if(!resp.ok){
    alert('曲线对比失败: ' + (data.error || 'unknown error'));
    return;
  }
  closeCurveComparePanel();
  openCurveCompareWindow(data);
}

function openCurveInteractiveWindow(data){
  const win = window.open('', '_blank', 'width=1200,height=760');
  if(!win){
    alert('弹窗被浏览器拦截，请允许弹窗后重试。');
    return;
  }
  const payload = JSON.stringify(data || {});
  const html = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>交互式曲线可视化</title>
  <style>
    body{margin:0;font-family:"Microsoft YaHei",Arial,sans-serif;background:#f5f7fb;color:#1f2937;}
    .wrap{padding:12px;display:grid;grid-template-columns:minmax(300px,340px) 1fr;gap:10px;height:100vh;}
    .panel{background:#fff;border:1px solid #d9dee8;border-radius:10px;padding:10px;overflow:auto;}
    .title{font-size:16px;font-weight:700;margin:0 0 10px 0;}
    .row{display:flex;align-items:center;gap:8px;margin-bottom:8px;}
    .row label{width:92px;font-size:12px;color:#6b7280;flex:0 0 92px;}
    .row input,.row select{flex:1;border:1px solid #d9dee8;border-radius:6px;padding:6px;font-size:12px;}
    .btns{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;}
    button{border:1px solid #d9dee8;background:#fff;padding:6px 10px;border-radius:6px;cursor:pointer;font-size:12px;}
    button.primary{background:#2563eb;color:#fff;border-color:#2563eb;}
    .meta{font-size:12px;color:#6b7280;margin-top:8px;word-break:break-all;}
    .typeFilterBox{border:1px solid #e5e7eb;border-radius:8px;padding:6px;max-height:150px;overflow:auto;background:#fafafa;}
    .typeItem{display:flex;align-items:center;gap:6px;font-size:12px;margin-bottom:4px;}
    .typeItem:last-child{margin-bottom:0;}
    .typeTools{display:flex;gap:6px;margin-top:6px;}
    .typeTools button{padding:4px 8px;font-size:11px;}
    .gateFilterBox{border:1px solid #e5e7eb;border-radius:8px;padding:6px;max-height:150px;overflow:auto;background:#fafafa;}
    .gateItem{display:flex;align-items:center;gap:6px;font-size:12px;margin-bottom:4px;}
    .gateItem:last-child{margin-bottom:0;}
    .gateTools{display:flex;gap:6px;margin-top:6px;}
    .gateTools button{padding:4px 8px;font-size:11px;}
    #plot{width:100%;height:calc(100vh - 70px);}
  </style>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"><\/script>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <div class="title">交互式曲线参数</div>
      <div class="row"><label>图标题</label><input id="iptTitle" /></div>
      <div class="row"><label>X轴标签</label><input id="iptXLabel" /></div>
      <div class="row"><label>Y轴标签</label><input id="iptYLabel" /></div>
      <div class="row"><label>X下限</label><input id="iptXMin" type="number" step="any" placeholder="留空自动" /></div>
      <div class="row"><label>X上限</label><input id="iptXMax" type="number" step="any" placeholder="留空自动" /></div>
      <div class="row"><label>Y下限</label><input id="iptYMin" type="number" step="any" placeholder="留空自动" /></div>
      <div class="row"><label>Y上限</label><input id="iptYMax" type="number" step="any" placeholder="留空自动" /></div>
      <div class="row"><label>图宽(px)</label><input id="iptWidth" type="number" min="600" max="3600" step="10" /></div>
      <div class="row"><label>图高(px)</label><input id="iptHeight" type="number" min="360" max="2400" step="10" /></div>
      <div class="row"><label>线宽</label><input id="iptLineWidth" type="number" min="1" max="12" step="0.5" value="2" /></div>
      <div class="row"><label>点大小</label><input id="iptMarkerSize" type="number" min="2" max="20" step="1" value="5" /></div>
      <div class="row"><label>字号</label><input id="iptFontSize" type="number" min="8" max="48" step="1" value="16" /></div>
      <div class="row"><label>显示点</label>
        <select id="iptShowMarker">
          <option value="0" selected>否</option>
          <option value="1">是</option>
        </select>
      </div>
      <div class="row"><label>显示图例</label>
        <select id="iptShowLegend">
          <option value="1" selected>是</option>
          <option value="0">否</option>
        </select>
      </div>
      <div class="row"><label>子图列数</label><input id="iptSubplotCols" type="number" min="1" max="6" step="1" /></div>
      <div class="row"><label>子图标题Y</label><input id="iptSubTitleY" type="number" min="0" max="1.5" step="0.005" value="0.012" /></div>
      <div class="row"><label>图例X</label><input id="iptLegendX" type="number" min="0" max="1" step="0.01" value="0.5" /></div>
      <div class="row"><label>图例Y</label><input id="iptLegendY" type="number" min="0" max="1.6" step="0.01" value="1.12" /></div>
      <div class="row" style="align-items:flex-start;"><label style="margin-top:6px;">节点类型</label>
        <div style="flex:1;">
          <div id="typeFilterBox" class="typeFilterBox"></div>
          <div class="typeTools">
            <button id="btnTypeAll" type="button">全选</button>
            <button id="btnTypeNone" type="button">清空</button>
          </div>
        </div>
      </div>
      <div class="row" style="align-items:flex-start;"><label style="margin-top:6px;">闸门</label>
        <div style="flex:1;">
          <div id="gateFilterBox" class="gateFilterBox"></div>
          <div class="gateTools">
            <button id="btnGateAll" type="button">全选</button>
            <button id="btnGateNone" type="button">清空</button>
          </div>
        </div>
      </div>
      <div class="row"><label>下载DPI</label>
        <select id="iptDpi">
          <option value="100">100</option>
          <option value="200">200</option>
          <option value="300" selected>300</option>
          <option value="600">600</option>
        </select>
      </div>
      <div class="btns">
        <button id="btnApply" class="primary">应用参数</button>
        <button id="btnDownload">下载PNG</button>
      </div>
      <div class="meta" id="meta"></div>
    </div>
    <div class="panel" style="padding:6px;">
      <div id="plot"></div>
    </div>
  </div>
<script>
  const payload = ${payload};
  const fallbackSeries = Array.isArray(payload.series) ? payload.series : [];
  const allSubplots = (Array.isArray(payload.subplots) && payload.subplots.length)
    ? payload.subplots
    : [{column: String(payload.column || 'series'), title: String(payload.column || 'series'), traces: fallbackSeries}];
  const typeList = (Array.isArray(payload.nodeTypes) && payload.nodeTypes.length)
    ? payload.nodeTypes.map(v=>String(v || '未分类'))
    : Array.from(new Set(allSubplots.map(sp=>String((sp && sp.nodeType) || '未分类'))));
  let selectedTypes = new Set(typeList);
  const allGateOptions = allSubplots.map(sp=>({
    name: String((sp && sp.column) || ''),
    nodeType: String((sp && sp.nodeType) || '未分类'),
  })).filter(g=>g.name);
  let selectedGates = new Set(allGateOptions.map(g=>g.name));
  const palette = ['#2563eb','#f59e0b','#16a34a','#dc2626','#7c3aed','#0891b2','#ea580c','#be185d'];
  const dashes = ['solid','dash','dot','dashdot','longdash','longdashdot'];

  const titleEl = document.getElementById('iptTitle');
  const xEl = document.getElementById('iptXLabel');
  const yEl = document.getElementById('iptYLabel');
  const fontSizeEl = document.getElementById('iptFontSize');
  const xMinEl = document.getElementById('iptXMin');
  const xMaxEl = document.getElementById('iptXMax');
  const yMinEl = document.getElementById('iptYMin');
  const yMaxEl = document.getElementById('iptYMax');
  const wEl = document.getElementById('iptWidth');
  const hEl = document.getElementById('iptHeight');
  const subplotColsEl = document.getElementById('iptSubplotCols');
  const subTitleYEl = document.getElementById('iptSubTitleY');
  const legendXEl = document.getElementById('iptLegendX');
  const legendYEl = document.getElementById('iptLegendY');

  titleEl.value = String(payload.title || '交互式曲线对比');
  xEl.value = String(payload.xLabel || 'index');
  yEl.value = String(payload.yLabel || 'value');
  xMinEl.value = payload.xMin === null || payload.xMin === undefined ? '' : String(payload.xMin);
  xMaxEl.value = payload.xMax === null || payload.xMax === undefined ? '' : String(payload.xMax);
  yMinEl.value = payload.yMin === null || payload.yMin === undefined ? '' : String(payload.yMin);
  yMaxEl.value = payload.yMax === null || payload.yMax === undefined ? '' : String(payload.yMax);
  fontSizeEl.value = String(payload.fontSize || 16);
  wEl.value = String(payload.widthPx || 1200);
  hEl.value = String(payload.heightPx || 620);
  subplotColsEl.value = String(payload.subplotCols || 2);
  subTitleYEl.value = '0.012';
  legendXEl.value = '0.5';
  legendYEl.value = '1.12';

  function subplotType(sp){
    return String((sp && sp.nodeType) || '未分类');
  }

  function allowedGateOptions(){
    return allGateOptions.filter(g=> selectedTypes.has(g.nodeType));
  }

  function normalizeGateSelection(autoFill=true){
    const allowed = allowedGateOptions();
    const allowedSet = new Set(allowed.map(g=>g.name));
    selectedGates = new Set(Array.from(selectedGates).filter(name=>allowedSet.has(name)));
    if(autoFill && selectedGates.size === 0){
      allowed.forEach(g=>selectedGates.add(g.name));
    }
  }

  function getFilteredSubplots(){
    return allSubplots.filter(sp=> selectedTypes.has(subplotType(sp)) && selectedGates.has(String((sp && sp.column) || '')));
  }

  function renderTypeFilters(){
    const box = document.getElementById('typeFilterBox');
    if(!box) return;
    box.innerHTML = '';
    typeList.forEach(tp=>{
      const row = document.createElement('label');
      row.className = 'typeItem';
      const chk = document.createElement('input');
      chk.type = 'checkbox';
      chk.checked = selectedTypes.has(tp);
      chk.onchange = ()=>{
        if(chk.checked) selectedTypes.add(tp);
        else selectedTypes.delete(tp);
        normalizeGateSelection(true);
        renderGateFilters();
        render();
      };
      const text = document.createElement('span');
      text.textContent = tp;
      row.appendChild(chk);
      row.appendChild(text);
      box.appendChild(row);
    });
  }

  function renderGateFilters(){
    const box = document.getElementById('gateFilterBox');
    if(!box) return;
    box.innerHTML = '';
    const options = allowedGateOptions();
    if(options.length === 0){
      const empty = document.createElement('div');
      empty.className = 'meta';
      empty.textContent = '当前类型下无可选闸门';
      box.appendChild(empty);
      return;
    }
    options.forEach(g=>{
      const row = document.createElement('label');
      row.className = 'gateItem';
      const chk = document.createElement('input');
      chk.type = 'checkbox';
      chk.checked = selectedGates.has(g.name);
      chk.onchange = ()=>{
        if(chk.checked) selectedGates.add(g.name);
        else selectedGates.delete(g.name);
        render();
      };
      const text = document.createElement('span');
      text.textContent = g.name;
      row.appendChild(chk);
      row.appendChild(text);
      box.appendChild(row);
    });
  }

  function safeNum(v, d){
    const n = Number(v);
    return Number.isFinite(n) ? n : d;
  }

  function parseAxisLimit(v){
    const raw = String(v ?? '').trim();
    if(!raw) return null;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }

  function numericExtent(values){
    let minVal = Infinity;
    let maxVal = -Infinity;
    (Array.isArray(values) ? values : []).forEach(v=>{
      const num = Number(v);
      if(Number.isFinite(num)){
        if(num < minVal) minVal = num;
        if(num > maxVal) maxVal = num;
      }
    });
    if(!Number.isFinite(minVal) || !Number.isFinite(maxVal)) return null;
    return {min: minVal, max: maxVal};
  }

  function linesExtent(lines, key){
    let minVal = Infinity;
    let maxVal = -Infinity;
    (Array.isArray(lines) ? lines : []).forEach(line=>{
      const ext = numericExtent(line && line[key]);
      if(ext){
        if(ext.min < minVal) minVal = ext.min;
        if(ext.max > maxVal) maxVal = ext.max;
      }
    });
    if(!Number.isFinite(minVal) || !Number.isFinite(maxVal)) return null;
    return {min: minVal, max: maxVal};
  }

  function axisRef(prefix, idx){
    return idx === 1 ? prefix : (prefix + String(idx));
  }

  function axisLayoutKey(prefix, idx){
    return prefix + 'axis' + (idx === 1 ? '' : String(idx));
  }

  function buildPlotData(){
    const activeSubplots = getFilteredSubplots();
    const lineWidth = Math.max(1, Math.min(12, safeNum(document.getElementById('iptLineWidth').value, 2)));
    const markerSize = Math.max(2, Math.min(20, safeNum(document.getElementById('iptMarkerSize').value, 5)));
    const showMarker = String(document.getElementById('iptShowMarker').value) === '1';
    const showLegend = String(document.getElementById('iptShowLegend').value) === '1';
    const fontSize = Math.max(8, Math.min(48, Math.round(safeNum(fontSizeEl.value, payload.fontSize || 16))));
    const subplotCols = Math.max(1, Math.min(6, Math.round(safeNum(subplotColsEl.value, payload.subplotCols || 2))));
    const subplotRows = Math.max(1, Math.ceil(activeSubplots.length / subplotCols));
    const subtitleYOffset = Math.max(0, Math.min(1.5, safeNum(subTitleYEl.value, 0.012)));
    const xMinInput = parseAxisLimit(xMinEl.value);
    const xMaxInput = parseAxisLimit(xMaxEl.value);
    const yMinInput = parseAxisLimit(yMinEl.value);
    const yMaxInput = parseAxisLimit(yMaxEl.value);
    const xGap = 0.06;
    const yGap = 0.02;
    const mode = showMarker ? 'lines+markers' : 'lines';
    const traces = [];
    const axisLayouts = {};
    const annotations = [];
    const panelWidth = (1 - (subplotCols - 1) * xGap) / subplotCols;
    const panelHeight = (1 - (subplotRows - 1) * yGap) / subplotRows;

    activeSubplots.forEach((subplot, subplotIndex)=>{
      const axisIndex = subplotIndex + 1;
      const rowIndex = Math.floor(subplotIndex / subplotCols);
      const colIndex = subplotIndex % subplotCols;
      const xRef = axisRef('x', axisIndex);
      const yRef = axisRef('y', axisIndex);
      const xKey = axisLayoutKey('x', axisIndex);
      const yKey = axisLayoutKey('y', axisIndex);
      const lines = Array.isArray(subplot.traces) ? subplot.traces : [];
      const xExtent = linesExtent(lines, 'x');
      const yExtent = linesExtent(lines, 'y');

      const xStart = colIndex * (panelWidth + xGap);
      const xCenter = xStart + panelWidth / 2;
      const yTop = 1 - rowIndex * (panelHeight + yGap);
      annotations.push({
        xref: 'paper',
        yref: 'paper',
        x: xCenter,
        y: yTop + subtitleYOffset,
        text: String(subplot.title || subplot.column || ('subplot' + axisIndex)),
        showarrow: false,
        xanchor: 'center',
        yanchor: 'bottom',
        font: {size: fontSize, color: '#111827'},
      });

      axisLayouts[xKey] = {
        title: {text: String(xEl.value || 'index'), font: {size: fontSize}},
        showgrid: true,
        zeroline: false,
        showticklabels: true,
        tickfont: {size: fontSize},
        matches: axisIndex === 1 ? undefined : 'x',
      };
      axisLayouts[yKey] = {
        title: {text: String(yEl.value || 'value'), font: {size: fontSize}},
        showgrid: true,
        zeroline: false,
        tickfont: {size: fontSize},
      };

      const xLower = xMinInput !== null ? xMinInput : (xExtent ? xExtent.min : null);
      const xUpperRaw = xMaxInput !== null ? xMaxInput : (xExtent ? xExtent.max : null);
      if(xLower !== null && xUpperRaw !== null){
        const xUpper = xUpperRaw <= xLower ? (xLower + 1e-6) : xUpperRaw;
        axisLayouts[xKey].range = [xLower, xUpper];
      }
      const yLower = yMinInput !== null ? yMinInput : (yExtent ? yExtent.min : null);
      const yUpperRaw = yMaxInput !== null ? yMaxInput : (yExtent ? yExtent.max : null);
      if(yLower !== null && yUpperRaw !== null){
        const yUpper = yUpperRaw <= yLower ? (yLower + 1e-6) : yUpperRaw;
        axisLayouts[yKey].range = [yLower, yUpper];
      }

      lines.forEach((s, lineIndex)=>{
        traces.push({
          x: Array.isArray(s.x) ? s.x : [],
          y: Array.isArray(s.y) ? s.y : [],
          text: Array.isArray(s.xLabels) ? s.xLabels : [],
          type: 'scattergl',
          mode,
          xaxis: xRef,
          yaxis: yRef,
          name: String(s.label || ('line' + (lineIndex + 1))),
          line: {width: lineWidth, color: palette[lineIndex % palette.length], dash: dashes[lineIndex % dashes.length]},
          marker: {size: markerSize, color: palette[lineIndex % palette.length]},
          showlegend: showLegend && subplotIndex === 0,
          hovertemplate: 'time=%{text}<br>value=%{y}<extra>%{fullData.name}</extra>',
        });
      });
    });

    return {
      traces,
      axisLayouts,
      annotations,
      subplotCols,
      subplotRows,
      xGap,
      yGap,
      activeSubplotCount: activeSubplots.length,
      totalSubplotCount: allSubplots.length,
    };
  }

  function render(){
    const width = Math.max(600, Math.min(3600, safeNum(wEl.value, 1200)));
    const built = buildPlotData();
    const fontSize = Math.max(8, Math.min(48, Math.round(safeNum(fontSizeEl.value, payload.fontSize || 16))));
    const minHeight = Math.max(360, 240 * built.subplotRows + 120);
    const height = Math.max(minHeight, Math.min(3200, safeNum(hEl.value, 620)));
    const showLegend = String(document.getElementById('iptShowLegend').value) === '1';
    const legendX = Math.max(0, Math.min(1, safeNum(legendXEl.value, 0.5)));
    const legendY = Math.max(0, Math.min(1.6, safeNum(legendYEl.value, 1.12)));
    const layout = {
      title: {text: String(titleEl.value || '交互式曲线对比'), font: {size: fontSize}},
      width,
      height,
      showlegend: showLegend,
      legend: {orientation: 'h', x: legendX, xanchor: 'center', y: legendY, yanchor: 'bottom', font: {size: fontSize}},
      margin: {l: 70, r: 20, t: 110, b: 70},
      hovermode: 'x unified',
      template: 'plotly_white',
      grid: {
        rows: built.subplotRows,
        columns: built.subplotCols,
        pattern: 'independent',
        xgap: built.xGap,
        ygap: built.yGap,
      },
      ...built.axisLayouts,
      annotations: built.annotations,
    };
    Plotly.react('plot', built.traces, layout, {responsive: true, displaylogo: false});
    document.getElementById('meta').textContent =
      '文件数: ' + String(payload.lineCount || 0) +
      '，子图数: ' + String(built.activeSubplotCount) + '/' + String(built.totalSubplotCount) +
      '，已选类型: ' + String(Array.from(selectedTypes).join(', ') || '无') +
      '，闸门数: ' + String(selectedGates.size) +
      '，对象列: ' + String((payload.columns || []).join(', ')) +
      '，路径: ' + String(payload.paths || []);
  }

  document.getElementById('btnApply').onclick = render;
  document.getElementById('btnTypeAll').onclick = ()=>{ selectedTypes = new Set(typeList); normalizeGateSelection(true); renderTypeFilters(); renderGateFilters(); render(); };
  document.getElementById('btnTypeNone').onclick = ()=>{ selectedTypes = new Set(); normalizeGateSelection(true); renderTypeFilters(); renderGateFilters(); render(); };
  document.getElementById('btnGateAll').onclick = ()=>{ selectedGates = new Set(allowedGateOptions().map(g=>g.name)); renderGateFilters(); render(); };
  document.getElementById('btnGateNone').onclick = ()=>{ selectedGates = new Set(); renderGateFilters(); render(); };
  document.getElementById('btnDownload').onclick = ()=>{
    const width = Math.max(600, Math.min(3600, safeNum(wEl.value, 1200)));
    const height = Math.max(360, Math.min(2400, safeNum(hEl.value, 620)));
    const dpi = Math.max(72, Math.min(1200, safeNum(document.getElementById('iptDpi').value, 300)));
    const scale = Math.max(1, Math.min(8, dpi / 100));
    Plotly.downloadImage('plot', {
      format: 'png',
      filename: 'curve_interactive_' + String(dpi) + 'dpi',
      width,
      height,
      scale,
    });
  };

  if(!allSubplots.length){
    document.getElementById('meta').textContent = '无可绘制数据';
  }
  normalizeGateSelection(true);
  renderTypeFilters();
  renderGateFilters();
  render();
<\/script>
</body>
</html>`;
  win.document.open();
  win.document.write(html);
  win.document.close();
}

async function submitCurveInteractiveCompare(){
  const yColumn = (document.getElementById('compareYColumn').value || '').trim();
  const dpi = Number.parseInt((document.getElementById('compareDpi').value || '300'), 10) || 300;
  const figSizeX = Number.parseFloat((document.getElementById('compareFigWidth').value || '20')) || 20;
  const figSizeY = Number.parseFloat((document.getElementById('compareFigHeight').value || '10')) || 10;
  const fontSize = Number.parseInt((document.getElementById('compareFontSize').value || '16'), 10) || 16;
  const items = (state.curveCompareItems || [])
    .map(it=>({
      path: scopePathToCurrentCase(String((it && it.path) || '').trim()),
      label: String((it && it.label) || '').trim()
    }))
    .filter(it=>it.path);
  if(items.length === 0){
    alert('请至少选择一个文件。');
    return;
  }
  const resp = await fetch('/api/curve-compare-interactive', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({items, yColumn, dpi, figSizeX, figSizeY, fontSize})
  });
  const data = await resp.json();
  if(!resp.ok){
    alert('交互式曲线可视化失败: ' + (data.error || 'unknown error'));
    return;
  }
  closeCurveComparePanel();
  openCurveInteractiveWindow(data);
}

function bindActions(){
  const byId = (id)=>document.getElementById(id);
  const bindClick = (id, handler)=>{
    const el = byId(id);
    if(el) el.onclick = handler;
  };

  bindClick('btnLoad', loadData);
  bindClick('btnLoadServerPath', loadDataFromServerPath);
  bindClick('btnRefreshServerTree', loadServerPathTree);
  bindClick('btnRefreshCases', ()=> loadCaseList(state.currentCasePath));
  bindClick('btnSave', saveData);
  bindClick('btnSaveEdgesCsv', saveEdgesCsv);
  bindClick('btnExportTopology', openTopologyExportPanel);
  bindClick('btnCurveCompare', openCurveComparePanel);
  bindClick('btnAnalysisConfig', openAnalysisConfigPanel);
  bindClick('btnAnalysisConfigLoad', loadAnalysisConfig);
  bindClick('btnAnalysisConfigAddRow', addAnalysisConfigRow);
  bindClick('btnAnalysisConfigSelectAll', selectAllAnalysisConfigRows);
  bindClick('btnAnalysisConfigClearSel', clearAnalysisConfigSelection);
  bindClick('btnAnalysisConfigDeleteSelected', deleteSelectedAnalysisConfigRows);
  bindClick('btnAnalysisConfigSave', saveAnalysisConfig);
  bindClick('btnOpenAnalysisConfigTool', openAnalysisConfigTool);
  bindClick('btnOpenBaselineTool', openBaselineTool);
  bindClick('btnOpenFormatConvertTool', openFormatConvertTool);
  bindClick('btnBackFromAnalysisConfig', openDataToolsEntry);
  bindClick('btnBackFromBaseline', openDataToolsEntry);
  bindClick('btnBackFromFormatConvert', openDataToolsEntry);
  bindClick('btnDataToolsCloseEntry', closeAnalysisConfigPanel);
  bindClick('btnDataToolsCloseAnalysis', closeAnalysisConfigPanel);
  bindClick('btnDataToolsCloseBaseline', closeAnalysisConfigPanel);
  bindClick('btnDataToolsCloseConvert', closeAnalysisConfigPanel);
  bindClick('btnRunBaseline', runBaselineProcess);
  bindClick('btnRunFormatConvert', runFormatConvert);
  bindClick('btnOpenSimWindow', openSimulationWindow);
  bindClick('btnTypeShowAll', ()=>{
    ensureTypeStyleState();
    state.selectedTypeKeys = new Set(state.typeOrder);
    saveCurrentTypeStylePreset();
    renderTables();
    renderGraph();
  });
  bindClick('btnTypeShowNone', ()=>{
    state.selectedTypeKeys = new Set();
    state.selectedNode = null;
    state.selectedEdgeIndex = null;
    saveCurrentTypeStylePreset();
    renderTables();
    renderGraph();
  });
  bindClick('btnSaveTypeScheme', ()=>{
    const ok = saveCurrentTypeStylePreset();
    alert(ok ? '配色方案已保存（按案例目录隔离）' : '配色方案保存失败（浏览器存储不可用）');
  });
  bindClick('btnSaveLegendText', ()=>{
    const channelInput = byId('legendChannelText');
    const splitInput = byId('legendSplitText');
    const nodeInput = byId('legendNodeTemplate');
    if(channelInput) state.legendConfig.channelEdgeLabel = String(channelInput.value || '').trim() || '渠道边';
    if(splitInput) state.legendConfig.splitEdgeLabel = String(splitInput.value || '').trim() || '分水边（虚拟节点->分汇水节点）';
    if(nodeInput) state.legendConfig.nodeTypeTemplate = String(nodeInput.value || '').trim() || '节点 {alias} (type={type}, 数量={count})';
    const ok = saveLegendConfigToStorage();
    renderGraph();
    alert(ok ? '图例文案已保存' : '图例文案保存失败（浏览器存储不可用）');
  });

  const caseSelectEl = byId('caseSelect');
  if(caseSelectEl){
    caseSelectEl.onchange = ()=>{ loadCaseGraph(caseSelectEl.value || '.'); };
  }

  document.addEventListener('mouseup', endAnalysisConfigCellSelection);
  document.addEventListener('keydown', handleAnalysisConfigHotkeys, true);
  bindClick('btnCompareAddRow', ()=>{
    state.curveCompareItems.push({path: '', label: `line${state.curveCompareItems.length + 1}`});
    renderCurveCompareRows();
  });
  bindClick('btnCompareCancel', closeCurveComparePanel);
  bindClick('btnCompareInteractive', submitCurveInteractiveCompare);
  bindClick('btnCompareConfirm', submitCurveCompare);
  bindClick('btnComparePickRefresh', ()=> loadComparePathTree());
  bindClick('btnComparePickCancel', closeComparePathPicker);
  bindClick('btnTopologyExportCancel', closeTopologyExportPanel);
  bindClick('btnTopologyExportConfirm', exportTopologyImage);

  const topologyExportModal = byId('topologyExportModal');
  if(topologyExportModal){
    topologyExportModal.addEventListener('click', (ev)=>{
      if(ev.target === topologyExportModal) closeTopologyExportPanel();
    });
  }

  bindClick('btnLockLayout', ()=>{
    state.layoutLocked = !state.layoutLocked;
    if(!state.layoutLocked){
      state.layoutMode = 'force';
    }
    const btnLock = byId('btnLockLayout');
    if(btnLock) btnLock.textContent = `锁定布局: ${state.layoutLocked ? '开' : '关'}`;
    syncLayoutModeButtons();
  });
  bindClick('btnLayoutForce', ()=> applyLayoutMode('force'));
  bindClick('btnForceAuto', ()=>{
    setForceRefreshMode('auto');
    activateForceLayoutWindow(FORCE_LAYOUT_ACTIVE_MS);
  });
  bindClick('btnForceManual', ()=>{
    setForceRefreshMode('manual');
  });
  bindClick('btnForceRefresh', ()=>{
    requestManualForceRefresh(isLargeGraphMode() ? 3 : 1);
  });
  bindClick('btnApplyCameraRange', applyCameraRangeFromInputs);

  const labelToggle = byId('chkShowNodeLabels');
  if(labelToggle){
    labelToggle.checked = !!state.showNodeLabels;
    labelToggle.onchange = ()=>{
      state.showNodeLabels = !!labelToggle.checked;
      renderGraph();
    };
  }
  const camW = byId('camRangeWidth');
  const camH = byId('camRangeHeight');
  if(camW) camW.value = String(state.cameraRange.width);
  if(camH) camH.value = String(state.cameraRange.height);

  const bindLegendTextInput = (id, field, fallback)=>{
    const el = byId(id);
    if(!el) return;
    el.addEventListener('input', ()=>{
      state.legendConfig[field] = String(el.value || '').trim() || fallback;
      saveLegendConfigToStorage();
      renderGraph();
    });
  };
  bindLegendTextInput('legendChannelText', 'channelEdgeLabel', '渠道边');
  bindLegendTextInput('legendSplitText', 'splitEdgeLabel', '分水边（虚拟节点->分汇水节点）');
  bindLegendTextInput('legendNodeTemplate', 'nodeTypeTemplate', '节点 {alias} (type={type}, 数量={count})');

  document.querySelectorAll('.componentItem').forEach(item => {
    item.addEventListener('dragstart', (e)=>{
      const comp = item.getAttribute('data-comp');
      state.paletteDragType = comp;
      if(e.dataTransfer){
        e.dataTransfer.setData('text/plain', comp || '');
        e.dataTransfer.effectAllowed = 'copy';
      }
    });
  });

  const canvasWrap = document.getElementById('canvasWrap');
  canvasWrap.addEventListener('dragover', (e)=>{
    e.preventDefault();
    if(e.dataTransfer){
      e.dataTransfer.dropEffect = 'copy';
    }
  });

  canvasWrap.addEventListener('drop', (e)=>{
    e.preventDefault();
    const comp = (e.dataTransfer && e.dataTransfer.getData('text/plain')) || state.paletteDragType;
    state.paletteDragType = null;
    const vp = toViewPoint(e.clientX, e.clientY);
    if(comp === 'node'){
      createNodeAtView(vp.x, vp.y);
      return;
    }
    if(comp === 'edge'){
      startEdgeFromDrop(vp.x, vp.y);
      return;
    }
  });

  document.getElementById('btnNodeAdd').onclick = ()=>{
    const name = document.getElementById('nodeName').value.trim();
    addNode(name);
  };

  document.getElementById('btnNodeRename').onclick = ()=>{
    const oldName = document.getElementById('nodeName').value.trim();
    const newName = document.getElementById('nodeRename').value.trim();
    renameNode(oldName, newName);
  };

  document.getElementById('btnNodeDel').onclick = ()=>{
    const name = document.getElementById('nodeName').value.trim();
    deleteNode(name);
  };

  document.getElementById('btnEdgeAdd').onclick = ()=>{
    const e = normalizeEdge(edgeFormToObj());
    if(String(e.ConnectionType||'').toLowerCase()==='direct' && !normalizeName(e.end)){
      const endNode = askEndNodeForDirect('');
      if(!endNode) return;
      e.end = endNode;
      document.getElementById('eEnd').value = endNode;
    }
    if(!e.source || !e.target) return alert('source 和 target 必填');
    ensureNode(e.source); ensureNode(e.target); if(e.end) ensureNode(e.end);
    state.edges.push(e);
    rebuildNodesFromEdges();
    state.directEndWarnIndices = [];
    state.selectedEdgeIndex = state.edges.length-1;
    activateForceLayoutWindow(FORCE_LAYOUT_ACTIVE_MS);
    renderTables();
    renderGraph();
  };

  document.getElementById('btnEdgeUpd').onclick = ()=>{
    if(state.selectedEdgeIndex===null) return alert('请先选择一条边');
    const e = normalizeEdge(edgeFormToObj());
    if(String(e.ConnectionType||'').toLowerCase()==='direct' && !normalizeName(e.end)){
      const endNode = askEndNodeForDirect(normalizeName(state.edges[state.selectedEdgeIndex].end || ''));
      if(!endNode) return;
      e.end = endNode;
      document.getElementById('eEnd').value = endNode;
    }
    if(!e.source || !e.target) return alert('source 和 target 必填');
    state.edges[state.selectedEdgeIndex] = {...state.edges[state.selectedEdgeIndex], ...e};
    ensureNode(e.source); ensureNode(e.target); if(e.end) ensureNode(e.end);
    rebuildNodesFromEdges();
    state.directEndWarnIndices = [];
    activateForceLayoutWindow(FORCE_LAYOUT_ACTIVE_MS);
    renderTables();
    renderGraph();
  };

  document.getElementById('btnEdgeDel').onclick = ()=>{
    if(state.selectedEdgeIndex===null) return alert('请先选择一条边');
    state.edges.splice(state.selectedEdgeIndex,1);
    state.selectedEdgeIndex = null;
    rebuildNodesFromEdges();
    state.directEndWarnIndices = [];
    renderTables();
    renderGraph();
  };

  document.getElementById('btnCheckDirectEnd').onclick = ()=>{
    checkDirectEndWarnings(true);
  };

  const handlePointerMoveEvent = (e, allowHover)=>{
    if(activePointerId !== null && e.buttons === 0){
      resetPointerInteraction();
      return;
    }
    if(activePointerId !== null && e.pointerId !== activePointerId) return;
    const vp = toViewPoint(e.clientX, e.clientY);
    state.mouseView = vp;

    if(activeMode === 'connect-drag' && connectDragFrom){
      e.preventDefault();
      updateHoverConnectDrag(vp);
      return;
    }

    if(activeMode === 'drag-node' && dragNode){
      e.preventDefault();
      if(!dragMoved){
        dragMoved = true;
        suppressNodeClickUntil = Date.now() + 140;
      }
      scheduleDragUpdate(e.clientX, e.clientY, vp);
      return;
    }

    if(activeMode === 'drag-indirect-edge' && dragIndirectEdgeNodes){
      e.preventDefault();
      if(!dragMoved){
        dragMoved = true;
        suppressNodeClickUntil = Date.now() + 140;
      }
      scheduleDragUpdate(e.clientX, e.clientY, vp);
      return;
    }

    if(state.viewMode === 'connect' && state.connectFrom){
      updateConnectHoverAndPreview(vp);
      return;
    }

    if(allowHover){
      updateHoverNodeFromPoint(vp);
    }
  };

  window.addEventListener('pointermove', (e)=>{
    handlePointerMoveEvent(e, true);
  });

  if('onpointerrawupdate' in window){
    window.addEventListener('pointerrawupdate', (e)=>{
      if(activeMode !== 'drag-node' && activeMode !== 'connect-drag' && activeMode !== 'drag-indirect-edge') return;
      handlePointerMoveEvent(e, false);
    });
  }

  const endPointer = (e)=>{
    if(activePointerId !== null && e.pointerId !== activePointerId) return;
    if(activeMode === 'connect-drag' && connectDragFrom){
      finishHoverConnectDrag(e);
      return;
    }
    if(dragMoved){
      suppressNodeClickUntil = Date.now() + 170;
    }
    resetPointerInteraction();
  };

  window.addEventListener('pointerup', endPointer);
  window.addEventListener('pointercancel', endPointer);
  window.addEventListener('blur', ()=>{
    resetPointerInteraction();
  });

  window.addEventListener('mousemove', (e)=>{
    const vp = toViewPoint(e.clientX, e.clientY);
    state.mouseView = vp;

    if(activeMode === 'connect-drag' && connectDragFrom){
      updateHoverConnectDrag(vp);
      return;
    }

    if(activeMode === 'drag-node-mouse' && dragNode){
      if(e.buttons === 0){
        resetPointerInteraction();
        return;
      }
      e.preventDefault();
      if(!dragMoved){
        dragMoved = true;
        suppressNodeClickUntil = Date.now() + 140;
      }
      scheduleDragUpdate(e.clientX, e.clientY, vp);
      return;
    }

    if(activeMode === 'drag-indirect-edge-mouse' && dragIndirectEdgeNodes){
      if(e.buttons === 0){
        resetPointerInteraction();
        return;
      }
      e.preventDefault();
      if(!dragMoved){
        dragMoved = true;
        suppressNodeClickUntil = Date.now() + 140;
      }
      scheduleDragUpdate(e.clientX, e.clientY, vp);
      return;
    }

    if(state.viewMode === 'connect' && state.connectFrom){
      updateConnectHoverAndPreview(vp);
      return;
    }

    updateHoverNodeFromPoint(vp);
  });

  window.addEventListener('mouseup', ()=>{
    if(activeMode === 'connect-drag' && connectDragFrom){
      finishHoverConnectDrag(null);
      return;
    }
    if(activeMode === 'drag-node-mouse' || activeMode === 'drag-indirect-edge-mouse'){
      if(dragMoved){
        suppressNodeClickUntil = Date.now() + 170;
      }
      resetPointerInteraction();
    }
  });

  svg.addEventListener('wheel', (e)=>{
    e.preventDefault();
    return;
  }, {passive:false});

  svg.addEventListener('click', (e)=>{
    if(Date.now() < suppressNodeClickUntil){
      return;
    }
    const isBackground = (e.target === svg || e.target === viewport || e.target === edgeLayer || e.target === nodeLayer || e.target === interactionLayer);
    if(isBackground){
      if(state.viewMode === 'add-node'){
        const vp = toViewPoint(e.clientX, e.clientY);
        const nodeName = (prompt('新节点名称:') || '').trim();
        if(nodeName){
          if(state.nodes.includes(nodeName)){
            alert('节点已存在');
          } else {
            ensureNode(nodeName);
            state.positions[nodeName].x = vp.x;
            state.positions[nodeName].y = vp.y;
            state.positions[nodeName].vx = 0;
            state.positions[nodeName].vy = 0;
            selectNode(nodeName, null, null, false);
          }
        }
      } else {
        state.selectedNode = null;
        state.selectedEdgeIndex = null;
        renderTables();
        renderGraph();
      }
      hideNodeMenu();
    }
  });

  document.addEventListener('click', (e)=>{
    if(nodeMenu.style.display !== 'none' && !nodeMenu.contains(e.target)){
      if(!(e.target instanceof SVGElement)){
        hideNodeMenu();
      }
    }
  });

  document.getElementById('menuNodeAdd').onclick = ()=>{
    const base = state.selectedNode;
    if(!base) return;
    const newNode = (prompt('新增相连节点名:') || '').trim();
    if(!newNode) return;
    if(state.nodes.includes(newNode)) return alert('节点已存在');
    const conn = (prompt('连接类型 direct / indirect:', 'direct') || 'direct').trim().toLowerCase()==='indirect' ? 'indirect' : 'direct';
    addNode(newNode);
    createEdgeBetween(base, newNode, {connectionType: conn});
  };

  document.getElementById('menuNodeRename').onclick = ()=>{
    const oldName = state.selectedNode;
    if(!oldName) return;
    const newName = (prompt('节点重命名为:', oldName) || '').trim();
    if(!newName || newName===oldName) return;
    renameNode(oldName, newName);
    hideNodeMenu();
  };

  document.getElementById('menuNodeDelete').onclick = ()=>{
    const name = state.selectedNode;
    if(!name) return;
    deleteNode(name);
    hideNodeMenu();
  };

  window.addEventListener('keydown', (e)=>{
    if(e.key !== 'Delete') return;
    const target = e.target;
    if(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement){
      return;
    }
    if(target && target.isContentEditable){
      return;
    }
    const name = state.selectedNode;
    if(!name) return;
    e.preventDefault();
    deleteNode(name, {confirmDelete:false});
  });
}

function addNode(name){
  let n = normalizeName(name);
  if(!n){
    n = normalizeName(prompt('请输入新节点名称:') || '');
  }
  if(!n) return;
  if(state.nodes.includes(n)) return alert('节点已存在');
  ensureNode(n);
  state.nodes.sort((a,b)=>a.localeCompare(b,'zh-CN'));
  state.selectedNode = n;
  document.getElementById('nodeName').value = n;
  renderTables();
  renderGraph();
}

function renameNode(oldName, newName){
  const oldN = normalizeName(oldName);
  const newN = normalizeName(newName);
  if(!oldN || !newN) return alert('请填写原节点名和新节点名');
  if(!state.nodes.includes(oldN)) return alert('原节点不存在');
  if(state.nodes.includes(newN)) return alert('新节点名已存在');
  state.edges.forEach(e=>{
    if(normalizeName(e.source)===oldN) e.source=newN;
    if(normalizeName(e.target)===oldN) e.target=newN;
    if(normalizeName(e.end)===oldN) e.end=newN;
  });
  if(state.positions[oldN]){ state.positions[newN]=state.positions[oldN]; delete state.positions[oldN]; }
  if(state.fixedNodes[oldN]){ state.fixedNodes[newN]=state.fixedNodes[oldN]; delete state.fixedNodes[oldN]; }
  rebuildNodesFromEdges();
  state.selectedNode = newN;
  document.getElementById('nodeName').value = newN;
  document.getElementById('nodeRename').value = '';
  renderTables();
  renderGraph();
}

function deleteNode(name, options={}){
  const n = normalizeName(name);
  if(!n) return alert('请输入节点名');
  const needConfirm = options.confirmDelete !== false;
  if(needConfirm && !confirm(`删除节点 ${n} 及相关边？`)) return;
  state.edges = state.edges.filter(e=> normalizeName(e.source)!==n && normalizeName(e.target)!==n && normalizeName(e.end)!==n);
  delete state.positions[n];
  delete state.fixedNodes[n];
  state.selectedNode = null;
  rebuildNodesFromEdges();
  renderTables();
  renderGraph();
}

function showNodeMenu(nodeName, clientX, clientY){
  nodeMenuTitle.textContent = `节点: ${nodeName}`;
  const hostRect = document.getElementById('canvasWrap').getBoundingClientRect();
  const left = Math.min(hostRect.width - 220, Math.max(8, clientX - hostRect.left + 8));
  const top = Math.min(hostRect.height - 110, Math.max(8, clientY - hostRect.top + 8));
  nodeMenu.style.left = `${left}px`;
  nodeMenu.style.top = `${top}px`;
  nodeMenu.style.display = 'block';
}

function hideNodeMenu(){
  nodeMenu.style.display = 'none';
}

function setStartupWarning(text){
  const el = document.getElementById('startupWarn');
  if(!el) return;
  const msg = String(text || '').trim();
  el.textContent = msg;
  el.style.display = msg ? 'block' : 'none';
}

bindActions();
setStartupWarning((typeof window !== 'undefined' && window.__BOOTSTRAP_WARNING__) ? String(window.__BOOTSTRAP_WARNING__) : '');
loadLegendConfigFromStorage();
updateLegendTextInputs();
applyLegendTextFromState();
setForceRefreshMode('auto');
applyCameraRangeFromState();
loadData();
setInterval(tickLayout, 28);
</script>
</body>
</html>
"""


MINIMAL_DRAG_TEST_HTML = r"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Minimal Drag Test</title>
  <style>
    body { margin: 0; font-family: "Microsoft YaHei", Arial, sans-serif; background: #f3f6fb; }
    .wrap { display: grid; grid-template-rows: auto 1fr; height: 100vh; gap: 8px; padding: 8px; }
    .tools { background: #fff; border: 1px solid #d7deea; border-radius: 8px; padding: 8px; display: flex; gap: 8px; align-items: center; }
    button { border: 1px solid #c7d3e6; border-radius: 6px; background: #fff; padding: 6px 10px; cursor: pointer; }
    .ok { color: #166534; font-weight: 600; }
    .bad { color: #991b1b; font-weight: 600; }
    .main { display: grid; grid-template-columns: 1fr 340px; gap: 8px; min-height: 0; }
    #host { background: #fff; border: 1px solid #d7deea; border-radius: 8px; overflow: hidden; }
    #svg { width: 100%; height: 100%; touch-action: none; user-select: none; }
    .side { background: #fff; border: 1px solid #d7deea; border-radius: 8px; padding: 8px; overflow: auto; }
    #log { font-size: 12px; line-height: 1.4; white-space: pre-wrap; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="tools">
      <button id="btnSimMouse">模拟鼠标拖动</button>
      <button id="btnSimPointer">模拟指针拖动</button>
      <button id="btnClear">清空日志</button>
      <span>状态: <span id="status" class="bad">idle</span></span>
      <span>坐标: <span id="pos">(360,220)</span></span>
    </div>
    <div class="main">
      <div id="host">
        <svg id="svg" viewBox="0 0 1000 620" preserveAspectRatio="xMidYMid meet">
          <rect x="0" y="0" width="1000" height="620" fill="#ffffff"></rect>
          <g id="nodeGroup">
            <circle id="hit" cx="360" cy="220" r="34" fill="rgba(0,0,0,0.001)" stroke="none"></circle>
            <circle id="node" cx="360" cy="220" r="11" fill="#2563eb" stroke="#ffffff" stroke-width="2" pointer-events="none"></circle>
            <text id="label" x="378" y="214" font-size="14" fill="#111827" pointer-events="none">Node_A</text>
          </g>
        </svg>
      </div>
      <div class="side">
        <div style="font-weight:700;margin-bottom:6px;">最小测试说明</div>
        <div style="font-size:12px;color:#4b5563;margin-bottom:8px;">仅保留“节点拖动”这一件事，不包含画布平移/缩放。用于复现并验证拖动链路。</div>
        <div id="log"></div>
      </div>
    </div>
  </div>
<script>
const svg = document.getElementById('svg');
const hit = document.getElementById('hit');
const node = document.getElementById('node');
const label = document.getElementById('label');
const statusEl = document.getElementById('status');
const posEl = document.getElementById('pos');
const logEl = document.getElementById('log');

let dragging = false;
let dragBy = 'none';
let offsetX = 0;
let offsetY = 0;
let x = 360;
let y = 220;

function log(msg){
  const now = new Date();
  const t = `${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}.${String(now.getMilliseconds()).padStart(3,'0')}`;
  logEl.textContent = `[${t}] ${msg}\n` + logEl.textContent;
}

function setStatus(text, ok){
  statusEl.textContent = text;
  statusEl.className = ok ? 'ok' : 'bad';
}

function applyNode(){
  hit.setAttribute('cx', String(x));
  hit.setAttribute('cy', String(y));
  node.setAttribute('cx', String(x));
  node.setAttribute('cy', String(y));
  label.setAttribute('x', String(x + 18));
  label.setAttribute('y', String(y - 6));
  posEl.textContent = `(${Math.round(x)},${Math.round(y)})`;
}

function toView(clientX, clientY){
  const ctm = svg.getScreenCTM();
  if(!ctm){
    return {x: clientX, y: clientY};
  }
  const p = svg.createSVGPoint();
  p.x = clientX;
  p.y = clientY;
  return p.matrixTransform(ctm.inverse());
}

function startDrag(clientX, clientY, by){
  const p = toView(clientX, clientY);
  offsetX = x - p.x;
  offsetY = y - p.y;
  dragging = true;
  dragBy = by;
  setStatus(`dragging(${by})`, true);
  log(`start ${by} @ client(${Math.round(clientX)},${Math.round(clientY)}) view(${Math.round(p.x)},${Math.round(p.y)})`);
}

function moveDrag(clientX, clientY){
  if(!dragging) return;
  const p = toView(clientX, clientY);
  x = p.x + offsetX;
  y = p.y + offsetY;
  applyNode();
}

function endDrag(by){
  if(!dragging) return;
  dragging = false;
  log(`end ${by} -> (${Math.round(x)},${Math.round(y)})`);
  setStatus('idle', false);
}

hit.addEventListener('pointerdown', (e)=>{
  if(e.button !== 0) return;
  e.preventDefault();
  e.stopPropagation();
  startDrag(e.clientX, e.clientY, 'pointer');
});

hit.addEventListener('mousedown', (e)=>{
  if(e.button !== 0) return;
  if(window.PointerEvent) return;
  e.preventDefault();
  e.stopPropagation();
  startDrag(e.clientX, e.clientY, 'mouse');
});

window.addEventListener('pointermove', (e)=>{
  moveDrag(e.clientX, e.clientY);
});

window.addEventListener('pointerup', ()=>{
  endDrag('pointer');
});

window.addEventListener('mousemove', (e)=>{
  if(!window.PointerEvent){
    moveDrag(e.clientX, e.clientY);
  }
});

window.addEventListener('mouseup', ()=>{
  if(!window.PointerEvent){
    endDrag('mouse');
  }
});

window.addEventListener('blur', ()=>{
  endDrag('blur');
});

document.getElementById('btnClear').onclick = ()=>{ logEl.textContent = ''; };

document.getElementById('btnSimMouse').onclick = ()=>{
  const r = svg.getBoundingClientRect();
  const sx = r.left + 360;
  const sy = r.top + 220;
  const ex = sx + 140;
  const ey = sy + 80;
  startDrag(sx, sy, 'sim-mouse');
  for(let i=1;i<=18;i++){
    const t = i/18;
    moveDrag(sx + (ex - sx)*t, sy + (ey - sy)*t);
  }
  endDrag('sim-mouse');
  const ok = x > 440 && y > 260;
  log(ok ? 'SIM_MOUSE PASS' : 'SIM_MOUSE FAIL');
};

document.getElementById('btnSimPointer').onclick = ()=>{
  const r = svg.getBoundingClientRect();
  const sx = r.left + x;
  const sy = r.top + y;
  const ex = sx - 120;
  const ey = sy + 60;
  startDrag(sx, sy, 'sim-pointer');
  for(let i=1;i<=16;i++){
    const t = i/16;
    moveDrag(sx + (ex - sx)*t, sy + (ey - sy)*t);
  }
  endDrag('sim-pointer');
  const ok = x < 420 && y > 240;
  log(ok ? 'SIM_POINTER PASS' : 'SIM_POINTER FAIL');
};

applyNode();
log('ready');
</script>
</body>
</html>
"""


PLAYGROUND_STYLE_HTML = r"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Playground 风格网络拓扑（非官方）</title>
  <style>
    :root{
      --bg:#f3f2ef;
      --panel:#ffffff;
      --line:#d9d9d9;
      --text:#1f2937;
      --muted:#6b7280;
      --accent:#ef6c00;
      --blue:#1e88e5;
    }
    *{ box-sizing:border-box; }
    body{ margin:0; font-family:"Segoe UI","Microsoft YaHei",Arial,sans-serif; background:var(--bg); color:var(--text); }
    .wrap{ display:grid; grid-template-columns:300px 1fr; height:100vh; }
    .side{ background:var(--panel); border-right:1px solid var(--line); padding:14px; overflow:auto; }
    .title{ font-size:15px; font-weight:700; margin-bottom:6px; }
    .sub{ font-size:12px; color:var(--muted); margin-bottom:10px; }
    .row{ display:flex; align-items:center; gap:8px; margin-bottom:8px; }
    .row label{ width:92px; font-size:12px; color:var(--muted); }
    .row select,.row input{ flex:1; border:1px solid var(--line); border-radius:6px; padding:5px 7px; font-size:12px; }
    .btns{ display:flex; gap:6px; flex-wrap:wrap; margin:10px 0 4px; }
    button{ border:1px solid var(--line); background:#fff; border-radius:6px; padding:6px 10px; font-size:12px; cursor:pointer; }
    button.primary{ background:var(--accent); border-color:var(--accent); color:#fff; }
    .main{ position:relative; }
    #svg{ width:100%; height:100%; display:block; touch-action:none; user-select:none; }
    .toolbar{ position:absolute; left:14px; top:14px; z-index:5; background:#fff; border:1px solid var(--line); border-radius:8px; padding:6px; display:flex; gap:6px; }
    .badge{ position:absolute; right:14px; top:14px; z-index:5; background:#fff; border:1px solid var(--line); border-radius:8px; padding:7px 10px; font-size:12px; color:var(--muted); }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="side">
      <div class="title">Playground 风格网络拓扑</div>
      <div class="sub">已融合 edges.csv 图结构，交互风格保持 playground 手感。</div>
      <div class="row"><label>图数据来源</label><input value="/api/graph" readonly /></div>
      <div class="row"><label>节点数量</label><input id="nodeCount" value="0" readonly /></div>
      <div class="row"><label>边数量</label><input id="edgeCount" value="0" readonly /></div>
      <div class="row"><label>连线样式</label>
        <select id="edgeMode">
          <option value="curve">曲线</option>
          <option value="line">直线</option>
        </select>
      </div>
      <div class="btns">
        <button class="primary" id="btnReload">重新加载</button>
        <button id="btnLegacy">旧版编辑器</button>
      </div>
      <div class="sub">操作：拖动任意节点，连线实时更新。</div>
    </div>
    <div class="main">
      <div class="toolbar">
        <button id="btnReset">重置布局</button>
        <button id="btnRandom">随机扰动</button>
      </div>
      <div class="badge" id="badge">nodes: 0, edges: 0</div>
      <svg id="svg" viewBox="0 0 1200 760" preserveAspectRatio="xMidYMid meet">
        <rect x="0" y="0" width="1200" height="760" fill="#fbfbfa"></rect>
        <g id="edgeLayer"></g>
        <g id="nodeLayer"></g>
      </svg>
    </div>
  </div>

<script>
const svg = document.getElementById('svg');
const edgeLayer = document.getElementById('edgeLayer');
const nodeLayer = document.getElementById('nodeLayer');
const badge = document.getElementById('badge');
const nodeCountInput = document.getElementById('nodeCount');
const edgeCountInput = document.getElementById('edgeCount');

let nodeMap = new Map();
let edgeRefs = [];
let graphEdges = [];
let dragNodeId = null;
let dragOffset = {x:0,y:0};
let pointerId = null;
let edgeFrame = 0;
let pendingNode = null;

function toView(clientX, clientY){
  const ctm = svg.getScreenCTM();
  if(!ctm) return {x:clientX, y:clientY};
  const p = svg.createSVGPoint();
  p.x = clientX; p.y = clientY;
  return p.matrixTransform(ctm.inverse());
}

function normalizeName(v){
  const s = String(v ?? '').trim();
  if(!s || s.toLowerCase() === 'nan' || s === '-1') return null;
  return s;
}

function edgeColor(edge){
  const c = String(edge.ConnectionType || '').toLowerCase();
  return c === 'indirect' ? 'rgba(30,136,229,0.30)' : 'rgba(239,108,0,0.28)';
}

function buildFallbackLayout(nodes){
  const arr = Array.from(nodes);
  const cols = Math.max(3, Math.ceil(Math.sqrt(arr.length)));
  const rows = Math.max(1, Math.ceil(arr.length / cols));
  const xGap = 1040 / Math.max(1, cols - 1);
  const yGap = 620 / Math.max(1, rows - 1);
  const out = new Map();
  arr.forEach((id, i)=>{
    const col = i % cols;
    const row = Math.floor(i / cols);
    out.set(id, {x: 80 + col * xGap, y: 70 + row * yGap});
  });
  return out;
}

async function loadGraphFromApi(){
  const resp = await fetch('/api/graph');
  if(!resp.ok) throw new Error(`加载失败: ${resp.status}`);
  const data = await resp.json();
  const nodes = Array.isArray(data.nodes) ? data.nodes : [];
  const positions = data.positions && typeof data.positions === 'object' ? data.positions : {};
  const edges = Array.isArray(data.edges) ? data.edges : [];

  nodeMap.clear();
  graphEdges = [];

  const fallback = buildFallbackLayout(nodes);
  for(const rawId of nodes){
    const id = normalizeName(rawId);
    if(!id) continue;
    const p = positions[id];
    const x = p && Number.isFinite(Number(p.x)) ? Number(p.x) : fallback.get(id).x;
    const y = p && Number.isFinite(Number(p.y)) ? Number(p.y) : fallback.get(id).y;
    nodeMap.set(id, {id, x, y});
  }

  for(const e of edges){
    const s = normalizeName(e.source);
    const t = normalizeName(e.target);
    if(!s || !t) continue;
    if(!nodeMap.has(s) || !nodeMap.has(t)) continue;
    graphEdges.push(e);
  }

  renderAll();
}

function buildLayout(){
  nodeMap.clear();
  graphEdges = [];
  renderAll();
}

function scheduleEdgePatch(nodeId){
  pendingNode = nodeId;
  if(edgeFrame) return;
  edgeFrame = requestAnimationFrame(()=>{
    edgeFrame = 0;
    const n = pendingNode; pendingNode = null;
    if(n) patchEdgesForNode(n);
  });
}

function makeEdgePath(a,b){
  const mode = document.getElementById('edgeMode').value;
  if(mode === 'line') return `M ${a.x} ${a.y} L ${b.x} ${b.y}`;
  const dx = (b.x - a.x) * 0.45;
  return `M ${a.x} ${a.y} C ${a.x+dx} ${a.y}, ${b.x-dx} ${b.y}, ${b.x} ${b.y}`;
}

function renderAll(){
  edgeLayer.innerHTML = '';
  nodeLayer.innerHTML = '';
  edgeRefs = [];

  for(const edge of graphEdges){
    const s = normalizeName(edge.source);
    const t = normalizeName(edge.target);
    const a = s ? nodeMap.get(s) : null;
    const b = t ? nodeMap.get(t) : null;
    if(!a || !b) continue;
    const path = document.createElementNS('http://www.w3.org/2000/svg','path');
    path.setAttribute('d', makeEdgePath(a,b));
    path.setAttribute('fill','none');
    path.setAttribute('stroke', edgeColor(edge));
    path.setAttribute('stroke-width','1.6');
    edgeLayer.appendChild(path);
    edgeRefs.push({a:s, b:t, el:path});
  }

  for(const [id,n] of nodeMap.entries()){
    const g = document.createElementNS('http://www.w3.org/2000/svg','g');
    const ring = document.createElementNS('http://www.w3.org/2000/svg','circle');
    ring.setAttribute('cx', n.x); ring.setAttribute('cy', n.y); ring.setAttribute('r', '16');
    ring.setAttribute('fill', 'rgba(0,0,0,0.02)');
    ring.setAttribute('stroke', '#d6d6d6');
    ring.setAttribute('stroke-width', '1');

    const hit = document.createElementNS('http://www.w3.org/2000/svg','circle');
    hit.setAttribute('cx', n.x); hit.setAttribute('cy', n.y); hit.setAttribute('r', '22');
    hit.setAttribute('fill', 'rgba(0,0,0,0.001)');
    hit.style.cursor = 'grab';

    const core = document.createElementNS('http://www.w3.org/2000/svg','circle');
    core.setAttribute('cx', n.x); core.setAttribute('cy', n.y); core.setAttribute('r', '10');
    core.setAttribute('fill', '#f8f8f8');
    core.setAttribute('stroke', '#9a9a9a');
    core.setAttribute('stroke-width', '1.4');
    core.style.pointerEvents = 'none';

    hit.addEventListener('pointerdown', (e)=>{
      if(e.button !== 0) return;
      e.preventDefault(); e.stopPropagation();
      dragNodeId = id;
      pointerId = e.pointerId;
      const p = toView(e.clientX, e.clientY);
      dragOffset = {x:n.x - p.x, y:n.y - p.y};
      try{ hit.setPointerCapture(e.pointerId); }catch(_){ }
    });

    g.appendChild(ring); g.appendChild(hit); g.appendChild(core);
    nodeLayer.appendChild(g);
    n._refs = {ring, hit, core};
  }

  nodeCountInput.value = String(nodeMap.size);
  edgeCountInput.value = String(edgeRefs.length);
  badge.textContent = `nodes: ${nodeMap.size}, edges: ${edgeRefs.length}`;
}

function patchEdgesForNode(nodeId){
  for(const e of edgeRefs){
    if(e.a !== nodeId && e.b !== nodeId) continue;
    const a = nodeMap.get(e.a), b = nodeMap.get(e.b);
    e.el.setAttribute('d', makeEdgePath(a,b));
  }
}

window.addEventListener('pointermove', (e)=>{
  if(!dragNodeId) return;
  if(pointerId !== null && e.pointerId !== pointerId) return;
  const n = nodeMap.get(dragNodeId);
  if(!n) return;
  const p = toView(e.clientX, e.clientY);
  n.x = p.x + dragOffset.x;
  n.y = p.y + dragOffset.y;
  n._refs.ring.setAttribute('cx', n.x); n._refs.ring.setAttribute('cy', n.y);
  n._refs.hit.setAttribute('cx', n.x);  n._refs.hit.setAttribute('cy', n.y);
  n._refs.core.setAttribute('cx', n.x); n._refs.core.setAttribute('cy', n.y);
  scheduleEdgePatch(dragNodeId);
});

window.addEventListener('pointerup', (e)=>{
  if(pointerId !== null && e.pointerId !== pointerId) return;
  dragNodeId = null; pointerId = null;
});
window.addEventListener('pointercancel', ()=>{ dragNodeId = null; pointerId = null; });
window.addEventListener('blur', ()=>{ dragNodeId = null; pointerId = null; });

document.getElementById('btnReload').onclick = ()=>{
  loadGraphFromApi().catch((err)=>alert(err.message || String(err)));
};
document.getElementById('btnLegacy').onclick = ()=>{
  window.location.href = '/classic';
};
document.getElementById('btnReset').onclick = ()=>{
  loadGraphFromApi().catch((err)=>alert(err.message || String(err)));
};
document.getElementById('btnRandom').onclick = ()=>{
  for(const n of nodeMap.values()){
    n.y += (Math.random()-0.5) * 40;
    n.x += (Math.random()-0.5) * 20;
    n._refs.ring.setAttribute('cx', n.x); n._refs.ring.setAttribute('cy', n.y);
    n._refs.hit.setAttribute('cx', n.x);  n._refs.hit.setAttribute('cy', n.y);
    n._refs.core.setAttribute('cx', n.x); n._refs.core.setAttribute('cy', n.y);
  }
  for(const e of edgeRefs){
    const a = nodeMap.get(e.a), b = nodeMap.get(e.b);
    e.el.setAttribute('d', makeEdgePath(a,b));
  }
};

document.getElementById('edgeMode').addEventListener('change', ()=>{
  for(const e of edgeRefs){
    const a = nodeMap.get(e.a), b = nodeMap.get(e.b);
    e.el.setAttribute('d', makeEdgePath(a,b));
  }
});

loadGraphFromApi().catch((err)=>{
  badge.textContent = `加载失败: ${err.message || err}`;
  buildLayout();
});
</script>
</body>
</html>
"""


def normalize_name(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan" or text == "-1":
        return None
    return text


def read_rows_auto(path: Path) -> List[Dict[str, str]]:
    last_error: Optional[Exception] = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            with path.open("r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                return [dict(row) for row in reader]
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return []


def read_text_auto(path: Path) -> str:
    last_error: Optional[Exception] = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return ""


def with_required_columns(row: Dict[str, str]) -> Dict[str, str]:
    out = {key: "" for key in REQUIRED_EDGE_COLUMNS}
    for key in REQUIRED_EDGE_COLUMNS:
        if key in row and row[key] is not None:
            out[key] = str(row[key])
    ctype = out["ConnectionType"].strip().lower()
    out["ConnectionType"] = "indirect" if ctype == "indirect" else "direct"
    return out


def read_polyline_endpoints(shp_path: Path) -> List[Optional[Dict[str, float]]]:
    if not shp_path.exists():
        return []

    records: List[Optional[Dict[str, float]]] = []
    with shp_path.open("rb") as f:
        header = f.read(100)
        if len(header) < 100:
            return []

        while True:
            rec_header = f.read(8)
            if not rec_header or len(rec_header) < 8:
                break
            _, content_len_words = struct.unpack(">2i", rec_header)
            content_len_bytes = content_len_words * 2
            content = f.read(content_len_bytes)
            if len(content) < 4:
                records.append(None)
                continue

            shape_type = struct.unpack("<i", content[0:4])[0]
            if shape_type == 1:
              if len(content) >= 20:
                px, py = struct.unpack("<2d", content[4:20])
                records.append({"x": px, "y": py})
              else:
                records.append(None)
              continue

            if shape_type not in (3, 5, 13, 15, 23, 25):
                records.append(None)
                continue

            if len(content) < 44:
                records.append(None)
                continue

            num_parts = struct.unpack("<i", content[36:40])[0]
            num_points = struct.unpack("<i", content[40:44])[0]
            if num_points <= 0:
                records.append(None)
                continue

            parts_off = 44
            points_off = parts_off + num_parts * 4
            if len(content) < points_off + num_points * 16:
                records.append(None)
                continue

            first_x, first_y = struct.unpack("<2d", content[points_off:points_off + 16])
            last_off = points_off + (num_points - 1) * 16
            last_x, last_y = struct.unpack("<2d", content[last_off:last_off + 16])
            records.append({"sx": first_x, "sy": first_y, "tx": last_x, "ty": last_y})

    return records


def read_dbf_records(dbf_path: Path, encoding: str = "utf-8") -> List[Dict[str, str]]:
      if not dbf_path.exists():
          return []

      with dbf_path.open("rb") as f:
          header = f.read(32)
          if len(header) < 32:
              return []

          num_records = struct.unpack("<I", header[4:8])[0]
          header_len = struct.unpack("<H", header[8:10])[0]
          record_len = struct.unpack("<H", header[10:12])[0]

          fields: List[Dict[str, object]] = []
          while True:
              desc = f.read(32)
              if not desc or desc[0] == 0x0D:
                  break
              name = desc[0:11].split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
              ftype = chr(desc[11])
              flen = desc[16]
              fields.append({"name": name, "type": ftype, "len": flen})

          f.seek(header_len)
          rows: List[Dict[str, str]] = []
          for _ in range(num_records):
              rec = f.read(record_len)
              if not rec or len(rec) < record_len:
                  break
              if rec[0:1] == b"*":
                  continue

              pos = 1
              row: Dict[str, str] = {}
              for fld in fields:
                  size = int(fld["len"])
                  raw = rec[pos:pos + size]
                  pos += size
                  try:
                      text = raw.decode(encoding, errors="ignore").strip()
                  except Exception:
                      text = raw.decode("latin1", errors="ignore").strip()
                  row[str(fld["name"])] = text
              rows.append(row)

      return rows


def build_node_positions_from_shp(edges: List[Dict[str, str]], shp_path: Path) -> Dict[str, Dict[str, float]]:
      endpoints = read_polyline_endpoints(shp_path)
      if not endpoints:
          return {}

      first_non_none = next((item for item in endpoints if item is not None), None)
      if first_non_none and "x" in first_non_none and "y" in first_non_none:
          dbf_rows = read_dbf_records(shp_path.with_suffix(".dbf"), encoding="utf-8")
          if not dbf_rows:
              return {}

          edge_nodes = set()
          for edge in edges:
              for key in ("source", "target", "end"):
                  n = normalize_name(edge.get(key))
                  if n:
                      edge_nodes.add(n)

          candidate_fields = list(dbf_rows[0].keys())
          best_field = None
          best_score = -1
          for field in candidate_fields:
              score = 0
              for row in dbf_rows:
                  name = normalize_name(row.get(field, ""))
                  if name and name in edge_nodes:
                      score += 1
              if score > best_score:
                  best_score = score
                  best_field = field

          if best_field is None or best_score <= 0:
              return {}

          out: Dict[str, Dict[str, float]] = {}
          for idx, row in enumerate(dbf_rows):
              if idx >= len(endpoints):
                  break
              ep = endpoints[idx]
              if ep is None:
                  continue
              name = normalize_name(row.get(best_field, ""))
              if not name:
                  continue
              out[name] = {"x": float(ep["x"]), "y": float(ep["y"])}
          return out

      acc: Dict[str, List[List[float]]] = {}
      for idx, edge in enumerate(edges):
          if idx >= len(endpoints):
              break
          ep = endpoints[idx]
          if ep is None:
              continue

          source = normalize_name(edge.get("source"))
          target = normalize_name(edge.get("target"))
          if source and "sx" in ep and "sy" in ep:
              acc.setdefault(source, []).append([ep["sx"], ep["sy"]])
          if target and "tx" in ep and "ty" in ep:
              acc.setdefault(target, []).append([ep["tx"], ep["ty"]])

      out: Dict[str, Dict[str, float]] = {}
      for node, pts in acc.items():
          if not pts:
              continue
          x = sum(p[0] for p in pts) / len(pts)
          y = sum(p[1] for p in pts) / len(pts)
          out[node] = {"x": x, "y": y}
      return out


def load_graph(edges_path: Path, shp_path: Path) -> Dict[str, object]:
    rows = read_rows_auto(edges_path)
    edges = [with_required_columns(row) for row in rows]

    nodes = set()
    for edge in edges:
        for key in ("source", "target", "end"):
            name = normalize_name(edge.get(key))
            if name:
                nodes.add(name)

    positions = build_node_positions_from_shp(edges, shp_path)

    direct_main_nodes = set()
    for edge in edges:
        if str(edge.get("ConnectionType", "")).strip().lower() == "direct":
            source = normalize_name(edge.get("source"))
            end = normalize_name(edge.get("end"))
            if source:
                direct_main_nodes.add(source)
            if end:
                direct_main_nodes.add(end)

    fixed_positions = {
        node: positions[node]
        for node in direct_main_nodes
        if node in positions
    }

    return {
        "edges": edges,
        "nodes": sorted(nodes),
        "positions": positions,
        "fixedPositions": fixed_positions,
    }


def save_edges(edges: List[Dict[str, object]], output_path: Path, backup: bool) -> Path:
    normalized = [with_required_columns({k: "" if v is None else str(v) for k, v in edge.items()}) for edge in edges]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if backup and output_path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = output_path.with_suffix(f".bak_{ts}.csv")
        shutil.copy2(output_path, backup_path)

    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REQUIRED_EDGE_COLUMNS)
        writer.writeheader()
        writer.writerows(normalized)

    return output_path


def _parse_float_text(value: object) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _format_float_text(value: float) -> str:
    try:
        if not math.isfinite(value):
            return ""
    except Exception:
        return ""
    return f"{value:.12g}"


def _run_data_processing_tool(base_dir: Path, payload: Dict[str, object]) -> Dict[str, object]:
    action = str(payload.get("action", "")).strip().lower()
    if action == "format_convert":
        input_raw = str(payload.get("inputPath", "")).strip()
        if not input_raw:
            raise ValueError("inputPath 不能为空")
        input_path = _resolve_workspace_path(base_dir, input_raw)
        if not input_path.exists() or input_path.is_dir():
            raise FileNotFoundError(f"输入文件不存在: {input_raw}")

        output_raw = str(payload.get("outputPath", "")).strip()
        output_path = _resolve_workspace_path(base_dir, output_raw) if output_raw else None
        mode = str(payload.get("mode", "pivot_to_tidy")).strip() or "pivot_to_tidy"
        time_column = str(payload.get("timeColumn", "tm")).strip() or "tm"
        obj_column = str(payload.get("objColumn", "obj")).strip() or "obj"
        value_column = str(payload.get("valueColumn", "value")).strip() or "value"

        src_dir = (base_dir / "src").resolve()
        plot_dir = (src_dir / "plot").resolve()
        for p in (str(base_dir), str(src_dir), str(plot_dir)):
            if p not in sys.path:
                sys.path.insert(0, p)

        try:
            from src.plot.csvtm2td import convert_file_format
        except Exception as exc:
            raise RuntimeError(f"导入格式转换模块失败: {exc}")

        out_path = convert_file_format(
            input_path=input_path,
            mode=mode,
            output_path=output_path,
            time_column=time_column,
            obj_column=obj_column,
            value_column=value_column,
        )
        out_path = Path(out_path).resolve()
        try:
            rel_out = out_path.relative_to(base_dir).as_posix()
        except Exception:
            rel_out = str(out_path)
        return {
            "action": "format_convert",
            "mode": mode,
            "inputPath": input_path.relative_to(base_dir).as_posix(),
            "outputPath": rel_out,
        }

    if action == "baseline_adjust":
        input_raw = str(payload.get("inputPath", "")).strip()
        if not input_raw:
            raise ValueError("inputPath 不能为空")
        input_path = _resolve_workspace_path(base_dir, input_raw)
        if not input_path.exists() or input_path.is_dir():
            raise FileNotFoundError(f"输入文件不存在: {input_raw}")

        output_raw = str(payload.get("outputPath", "")).strip()
        if output_raw:
            output_path = _resolve_workspace_path(base_dir, output_raw)
        else:
            output_path = input_path.with_name(f"{input_path.stem}_baseline{input_path.suffix or '.csv'}")

        rows = read_rows_auto(input_path)
        if not rows:
            raise ValueError("输入文件无数据")

        headers = [str(h) for h in rows[0].keys()]
        if not headers:
            raise ValueError("输入文件缺少表头")

        baseline_mode = str(payload.get("baselineMode", "first_non_empty")).strip().lower() or "first_non_empty"
        baseline_value = _parse_float_text(payload.get("baselineValue"))

        columns_raw = payload.get("columns", [])
        selected_columns: List[str] = []
        if isinstance(columns_raw, list):
            selected_columns = [str(v).strip() for v in columns_raw if str(v).strip()]

        time_col = _detect_time_column(rows) or ""
        if selected_columns:
            target_columns = [col for col in selected_columns if col in headers and col != time_col]
        else:
            target_columns = [col for col in headers if col != time_col]

        numeric_columns: List[str] = []
        for col in target_columns:
            has_numeric = False
            for row in rows:
                if _parse_float_text(row.get(col)) is not None:
                    has_numeric = True
                    break
            if has_numeric:
                numeric_columns.append(col)
        if not numeric_columns:
            raise ValueError("未识别到可进行基准值处理的数值列")

        baseline_map: Dict[str, float] = {}
        if baseline_mode == "fixed":
            if baseline_value is None:
                raise ValueError("baselineMode=fixed 时 baselineValue 必须为数值")
            for col in numeric_columns:
                baseline_map[col] = float(baseline_value)
        else:
            for col in numeric_columns:
                base_val: Optional[float] = None
                for row in rows:
                    parsed_val = _parse_float_text(row.get(col))
                    if parsed_val is not None:
                        base_val = float(parsed_val)
                        break
                baseline_map[col] = 0.0 if base_val is None else base_val

        output_path.parent.mkdir(parents=True, exist_ok=True)
        row_count = 0
        with output_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                out_row: Dict[str, str] = {h: str(row.get(h, "")) for h in headers}
                for col in numeric_columns:
                    parsed_val = _parse_float_text(row.get(col))
                    if parsed_val is None:
                        continue
                    out_row[col] = _format_float_text(float(parsed_val) - baseline_map[col])
                writer.writerow(out_row)
                row_count += 1

        try:
            rel_out = output_path.relative_to(base_dir).as_posix()
        except Exception:
            rel_out = str(output_path)
        return {
            "action": "baseline_adjust",
            "inputPath": input_path.relative_to(base_dir).as_posix(),
            "outputPath": rel_out,
            "baselineMode": baseline_mode,
            "columnCount": len(numeric_columns),
            "rowCount": row_count,
            "columns": numeric_columns,
        }

    raise ValueError(f"不支持的数据处理动作: {action}")


def _result_step_index(path: Path) -> int:
    stem = path.stem.strip()
    lower = stem.lower()
    if lower.startswith("result"):
        suffix = stem[len("result"):]
    else:
        suffix = stem
    digits = "".join(ch for ch in suffix if ch.isdigit())
    if digits:
        try:
            return int(digits)
        except Exception:
            pass
    return 10**12


def _read_result_dat_points(path: Path) -> List[Tuple[float, float, float]]:
    points: List[Tuple[float, float, float]] = []
    last_error: Optional[Exception] = None
    use_input_fallback_columns = path.name.lower() == "input.txt"
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
      try:
        with path.open("r", encoding=encoding, errors="strict") as f:
          for line in f:
            text = line.strip()
            if not text:
              continue
            parts = text.replace(",", " ").split()
            if len(parts) < 3:
              continue
            x_idx = 0
            y_idx = 1
            z_idx = 2
            if use_input_fallback_columns and len(parts) >= 4:
              # input.txt often stores: index x y z ...
              x_idx = 1
              y_idx = 2
              z_idx = 3
            x_val = _parse_float_text(parts[x_idx])
            y_val = _parse_float_text(parts[y_idx])
            z_val = _parse_float_text(parts[z_idx])
            if x_val is None or y_val is None or z_val is None:
              continue
            points.append((x_val, y_val, z_val))
        return points
      except UnicodeDecodeError as exc:
        last_error = exc
    if last_error is not None:
        raise last_error
    return points


def _list_result_dat_files(base_dir: Path, root_raw: str, pattern_raw: str) -> Tuple[Path, List[Path], str]:
    root_value = root_raw.strip() or "mesh"
    pattern = pattern_raw.strip() or "result*.dat"
    root_path = _resolve_workspace_path(base_dir, root_value)
    if not root_path.exists() or not root_path.is_dir():
        raise FileNotFoundError(f"目录不存在: {root_value}")
    pattern_list = [x.strip() for x in re.split(r"[;,|]", pattern) if x.strip()]
    if not pattern_list:
        pattern_list = ["result*.dat"]
    file_map: Dict[Path, bool] = {}
    for pat in pattern_list:
        for p in root_path.glob(pat):
            if p.is_file():
                file_map[p] = True
    files = list(file_map.keys())
    if not files:
      # Fallback for mesh-only viewing without result files.
      fallback_input = root_path / "input.txt"
      if fallback_input.exists() and fallback_input.is_file():
        files = [fallback_input]
        pattern = ";".join(pattern_list + ["input.txt"])
    files.sort(key=lambda p: (_result_step_index(p), p.name.lower()))
    return root_path, files, pattern


def load_simulation_meta(base_dir: Path, root_raw: str = "mesh", pattern_raw: str = "result*.dat") -> Dict[str, object]:
    root_path, files, pattern = _list_result_dat_files(base_dir, root_raw, pattern_raw)
    if not files:
        sample_files = [
            child.name
            for child in sorted(root_path.iterdir(), key=lambda x: x.name.lower())
            if child.is_file()
        ][:30]
        return {
            "root": root_path.relative_to(base_dir).as_posix(),
            "pattern": pattern,
            "frameCount": 0,
            "steps": [],
            "bounds": None,
            "sampleFiles": sample_files,
        }

    x_min = float("inf")
    y_min = float("inf")
    z_min = float("inf")
    x_max = float("-inf")
    y_max = float("-inf")
    z_max = float("-inf")
    steps: List[Dict[str, object]] = []

    for order_idx, path in enumerate(files):
        points = _read_result_dat_points(path)
        for x_val, y_val, z_val in points:
            x_min = min(x_min, x_val)
            y_min = min(y_min, y_val)
            z_min = min(z_min, z_val)
            x_max = max(x_max, x_val)
            y_max = max(y_max, y_val)
            z_max = max(z_max, z_val)
        steps.append(
            {
                "step": order_idx,
                "index": _result_step_index(path),
                "name": path.name,
                "path": path.relative_to(base_dir).as_posix(),
                "pointCount": len(points),
            }
        )

    bounds = None
    if x_min != float("inf"):
        bounds = {
            "xMin": x_min,
            "xMax": x_max,
            "yMin": y_min,
            "yMax": y_max,
            "zMin": z_min,
            "zMax": z_max,
        }

    return {
        "root": root_path.relative_to(base_dir).as_posix(),
        "pattern": pattern,
        "frameCount": len(files),
        "steps": steps,
        "bounds": bounds,
    }


def load_simulation_step(base_dir: Path, root_raw: str = "mesh", pattern_raw: str = "result*.dat", step_raw: int = 0) -> Dict[str, object]:
    root_path, files, pattern = _list_result_dat_files(base_dir, root_raw, pattern_raw)
    if not files:
        raise ValueError(f"未找到匹配文件: root={root_path.relative_to(base_dir).as_posix()}, pattern={pattern}")
    try:
        step_index = int(step_raw)
    except Exception:
        step_index = 0
    step_index = max(0, min(step_index, len(files) - 1))
    target = files[step_index]
    points = _read_result_dat_points(target)
    return {
        "root": root_path.relative_to(base_dir).as_posix(),
        "pattern": pattern,
        "step": step_index,
        "file": target.name,
        "path": target.relative_to(base_dir).as_posix(),
        "pointCount": len(points),
        "points": [[x_val, y_val, z_val] for (x_val, y_val, z_val) in points],
    }


def _load_lineparam_pt1_by_type(root_path: Path) -> Dict[str, List[int]]:
    relate_path = root_path / "lineParamRelate.txt"
    if not relate_path.exists() or not relate_path.is_file():
        return {}

    text = read_text_auto(relate_path)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return {}

    header_parts = re.split(r"\s+", lines[0].lstrip("\ufeff"))
    header_parts = [h.lstrip(";") for h in header_parts]
    try:
        idx_pt1 = header_parts.index("pt1")
        idx_type = header_parts.index("type")
    except ValueError:
        return {}

    type_map: Dict[str, Set[int]] = {}
    for raw in lines[1:]:
        parts = re.split(r"\s+", raw)
        if idx_pt1 >= len(parts) or idx_type >= len(parts):
            continue
        type_key = str(parts[idx_type]).strip()
        if not type_key:
            continue
        try:
            pt1 = int(float(parts[idx_pt1]))
        except Exception:
            continue
        if pt1 < 0:
            continue
        bucket = type_map.setdefault(type_key, set())
        bucket.add(pt1)

    return {k: sorted(v) for k, v in type_map.items()}


def _load_lineparam_edges_by_type(root_path: Path) -> Dict[str, List[Tuple[int, int, float]]]:
    relate_path = root_path / "lineParamRelate.txt"
    if not relate_path.exists() or not relate_path.is_file():
        return {}

    text = read_text_auto(relate_path)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return {}

    header_parts = re.split(r"\s+", lines[0].lstrip("\ufeff"))
    header_parts = [h.lstrip(";") for h in header_parts]
    try:
        idx_pt1 = header_parts.index("pt1")
        idx_pt2 = header_parts.index("pt2")
        idx_distance = header_parts.index("distance")
        idx_type = header_parts.index("type")
    except ValueError:
        return {}

    edges_by_type: Dict[str, List[Tuple[int, int, float]]] = {}
    for raw in lines[1:]:
        parts = re.split(r"\s+", raw)
        if max(idx_pt1, idx_pt2, idx_distance, idx_type) >= len(parts):
            continue
        edge_type = str(parts[idx_type]).strip()
        if not edge_type:
            continue
        try:
            p1 = int(float(parts[idx_pt1]))
            p2 = int(float(parts[idx_pt2]))
        except Exception:
            continue
        dist_val = _parse_float_text(parts[idx_distance])
        if dist_val is None or dist_val <= 0:
            dist_val = 1.0
        edges_by_type.setdefault(edge_type, []).append((p1, p2, float(dist_val)))
    return edges_by_type


def _shortest_distances(start: int, adjacency: Dict[int, List[Tuple[int, float]]]) -> Dict[int, float]:
    if start not in adjacency:
        return {start: 0.0}
    dist: Dict[int, float] = {start: 0.0}
    heap: List[Tuple[float, int]] = [(0.0, start)]
    while heap:
        cur_d, u = heapq.heappop(heap)
        if cur_d > dist.get(u, float("inf")):
            continue
        for v, w in adjacency.get(u, []):
            nd = cur_d + float(w)
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return dist


def _load_canal_public_specs(root_path: Path) -> List[Dict[str, object]]:
    canal_path = root_path / "canal_parameter.json"
    if not canal_path.exists() or not canal_path.is_file():
        return []

    try:
        payload = json.loads(read_text_auto(canal_path))
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []

    out: List[Dict[str, object]] = []
    for canal_key, canal_obj in payload.items():
        if not isinstance(canal_obj, dict):
            continue
        public_obj = canal_obj.get("public")
        if not isinstance(public_obj, dict):
            continue
        prop = public_obj.get("property")
        prop_list: List[str] = []
        if isinstance(prop, list):
            prop_list = [str(x).strip() for x in prop if str(x).strip()]
        head_idx: Optional[int] = None
        head_raw = public_obj.get("head wnindex")
        try:
            if head_raw is not None:
                head_idx = int(float(str(head_raw).strip()))
        except Exception:
            head_idx = None
        out.append(
            {
                "key": str(canal_key),
                "properties": prop_list,
                "headWnindex": head_idx,
            }
        )
    return out


def _read_result_values_by_node_indices(path: Path, node_indices: Set[int]) -> Dict[int, float]:
    out: Dict[int, float] = {}
    if not node_indices:
        return out
    max_idx = max(node_indices)
    last_error: Optional[Exception] = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            with path.open("r", encoding=encoding, errors="strict") as f:
                for line_idx, line in enumerate(f):
                    if line_idx > max_idx:
                        break
                    if line_idx not in node_indices:
                        continue
                    text = line.strip()
                    if not text:
                        continue
                    parts = text.replace(",", " ").split()
                    if len(parts) < 3:
                        continue
                    value = _parse_float_text(parts[2])
                    if value is None and len(parts) >= 4:
                        value = _parse_float_text(parts[3])
                    if value is None:
                        continue
                    out[line_idx] = value
            return out
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return out


def load_simulation_curve_series(base_dir: Path, root_raw: str = "mesh", pattern_raw: str = "result*.dat") -> Dict[str, object]:
    root_path, files, pattern = _list_result_dat_files(base_dir, root_raw, pattern_raw)
    if not files:
        return {
            "root": root_path.relative_to(base_dir).as_posix(),
            "pattern": pattern,
            "frameCount": 0,
            "steps": [],
            "series": [],
        }

    type_to_nodes = _load_lineparam_pt1_by_type(root_path)
    type_to_edges = _load_lineparam_edges_by_type(root_path)
    canal_specs = _load_canal_public_specs(root_path)
    all_discrete_nodes: Set[int] = set()
    for vals in type_to_nodes.values():
      all_discrete_nodes.update(vals)

    series_specs: List[Dict[str, object]] = []
    for spec in canal_specs:
        prop_list = spec.get("properties") or []
        node_set: Set[int] = set()
        for prop in prop_list:
            node_set.update(type_to_nodes.get(str(prop), []))
        head_idx = spec.get("headWnindex")
        if isinstance(head_idx, int) and head_idx >= 0:
            node_set.add(head_idx)
        if not node_set:
          node_set.update(all_discrete_nodes)
        if not node_set:
          continue

        adjacency: Dict[int, List[Tuple[int, float]]] = {}
        for prop in prop_list:
            for p1, p2, edge_d in type_to_edges.get(str(prop), []):
                adjacency.setdefault(p1, []).append((p2, edge_d))
                adjacency.setdefault(p2, []).append((p1, edge_d))

        start_node = head_idx if isinstance(head_idx, int) and head_idx in node_set else min(node_set)
        dist_map = _shortest_distances(start_node, adjacency) if adjacency else {start_node: 0.0}

        ordered_pairs: List[Tuple[int, float]] = []
        for nidx in node_set:
            if nidx in dist_map:
                ordered_pairs.append((nidx, float(dist_map[nidx])))
        if not ordered_pairs:
            ordered = sorted(node_set)
            ordered_pairs = [(n, float(i)) for i, n in enumerate(ordered)]
        else:
            ordered_pairs.sort(key=lambda item: (item[1], item[0]))

        node_indices = [p[0] for p in ordered_pairs]
        node_distances = [p[1] for p in ordered_pairs]
        series_specs.append(
            {
                "key": str(spec.get("key") or ""),
                "properties": [str(x) for x in prop_list],
                "nodeIndices": node_indices,
                "nodeDistances": node_distances,
                "startNode": start_node,
            }
        )

    if not series_specs and all_discrete_nodes:
        ordered = sorted(all_discrete_nodes)
        series_specs.append(
            {
                "key": "全部离散节点",
                "properties": [],
                "nodeIndices": ordered,
                "nodeDistances": [float(i) for i in range(len(ordered))],
                "startNode": ordered[0],
            }
        )

    if not series_specs:
        return {
            "root": root_path.relative_to(base_dir).as_posix(),
            "pattern": pattern,
            "frameCount": len(files),
            "steps": [p.name for p in files],
            "series": [],
            "error": "未从 canal_parameter.json/public 与 lineParamRelate.txt 解析到可用节点编号",
        }

    series_payload: List[Dict[str, object]] = []
    for spec in series_specs:
        series_payload.append(
            {
                "key": spec["key"],
                "label": spec["key"],
                "properties": spec["properties"],
                "nodeCount": len(spec["nodeIndices"]),
                "nodeIndices": spec["nodeIndices"],
                "nodeDistances": spec["nodeDistances"],
                "startNode": spec["startNode"],
            }
        )

    return {
        "root": root_path.relative_to(base_dir).as_posix(),
        "pattern": pattern,
        "frameCount": len(files),
        "steps": [p.name for p in files],
        "series": series_payload,
    }


def load_simulation_gates(base_dir: Path, root_raw: str = "mesh", gate_file_raw: str = "gates_mesh.csv") -> Dict[str, object]:
    root_path = _resolve_workspace_path(base_dir, root_raw.strip() or "mesh")
    gate_file = gate_file_raw.strip() or "gates_mesh.csv"
    if not root_path.exists() or not root_path.is_dir():
        raise FileNotFoundError(f"目录不存在: {root_raw}")

    candidates = [
        root_path / gate_file,
        base_dir / "mesh" / gate_file,
    ]
    target_path: Optional[Path] = None
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            target_path = candidate
            break

    if target_path is None:
        return {
            "root": root_path.relative_to(base_dir).as_posix(),
            "file": gate_file,
            "count": 0,
            "gates": [],
        }

    rows: List[Dict[str, str]] = []
    last_error: Optional[Exception] = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            with target_path.open("r", encoding=encoding, errors="strict", newline="") as f:
                reader = csv.DictReader(f)
                rows = [dict(row) for row in reader]
            break
        except UnicodeDecodeError as exc:
            last_error = exc
    if not rows and last_error is not None:
        raise last_error

    out_gates: List[Dict[str, object]] = []
    for row in rows:
        x_val = _parse_float_text(row.get("x") or row.get("X"))
        y_val = _parse_float_text(row.get("y") or row.get("Y"))
        if x_val is None or y_val is None:
            continue
        gate_id = str(row.get("id") or "").strip()
        gate_name = str(row.get("gate_name") or row.get("name") or gate_id).strip()
        label = gate_name if not gate_id else f"{gate_name}_{gate_id}"
        out_gates.append(
            {
                "id": gate_id,
                "name": gate_name,
                "label": label,
                "x": x_val,
                "y": y_val,
            }
        )

    out_gates.sort(key=lambda g: str(g.get("name") or ""))
    return {
        "root": root_path.relative_to(base_dir).as_posix(),
        "file": target_path.relative_to(base_dir).as_posix(),
        "count": len(out_gates),
        "gates": out_gates,
    }


def load_simulation_junctions(
    base_dir: Path,
    root_raw: str = "mesh",
    neighbor_file_raw: str = "neighborId.txt",
    gate_file_raw: str = "gates_mesh.csv",
) -> Dict[str, object]:
    root_path = _resolve_workspace_path(base_dir, root_raw.strip() or "mesh")
    if not root_path.exists() or not root_path.is_dir():
        raise FileNotFoundError(f"目录不存在: {root_raw}")

    neighbor_file = neighbor_file_raw.strip() or "neighborId.txt"
    gate_file = gate_file_raw.strip() or "gates_mesh.csv"

    neighbor_candidates = [
        root_path / neighbor_file,
        base_dir / "mesh" / neighbor_file,
    ]
    gates_candidates = [
        root_path / gate_file,
        base_dir / "mesh" / gate_file,
    ]

    neighbor_path: Optional[Path] = None
    for candidate in neighbor_candidates:
        if candidate.exists() and candidate.is_file():
            neighbor_path = candidate
            break

    gates_path: Optional[Path] = None
    for candidate in gates_candidates:
        if candidate.exists() and candidate.is_file():
            gates_path = candidate
            break

    if neighbor_path is None or gates_path is None:
        return {
            "root": root_path.relative_to(base_dir).as_posix(),
            "neighborFile": neighbor_file,
            "gateFile": gate_file,
            "count": 0,
            "junctions": [],
        }

    coord_lookup: Dict[str, Tuple[float, float]] = {}
    rows: List[Dict[str, str]] = []
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            with gates_path.open("r", encoding=encoding, errors="strict", newline="") as f:
                rows = [dict(r) for r in csv.DictReader(f)]
            break
        except UnicodeDecodeError:
            continue
    for row in rows:
        node_id = str(row.get("id") or "").strip()
        x_val = _parse_float_text(row.get("x") or row.get("X"))
        y_val = _parse_float_text(row.get("y") or row.get("Y"))
        if not node_id or x_val is None or y_val is None:
            continue
        coord_lookup[node_id] = (x_val, y_val)

    lines: List[str] = []
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            lines = [line.strip() for line in neighbor_path.read_text(encoding=encoding, errors="strict").splitlines() if line.strip()]
            break
        except UnicodeDecodeError:
            continue

    if not lines:
        return {
            "root": root_path.relative_to(base_dir).as_posix(),
            "neighborFile": neighbor_path.relative_to(base_dir).as_posix(),
            "gateFile": gates_path.relative_to(base_dir).as_posix(),
            "count": 0,
            "junctions": [],
        }

    header = re.split(r"\s+", lines[0].replace("\ufeff", "").strip())
    header = [h.lstrip(";") for h in header]
    idx_id = header.index("id") if "id" in header else 0
    idx_nb = header.index("neighborNumber") if "neighborNumber" in header else -1
    idx_pre = header.index("preid") if "preid" in header else -1
    idx_next = header.index("nextid") if "nextid" in header else -1

    selected_ids: Set[str] = set()
    for line in lines[1:]:
        parts = re.split(r"\s+", line.strip())
        if len(parts) <= idx_id:
            continue
        node_id = str(parts[idx_id]).strip()
        if not node_id:
            continue

        def _int_at(index: int) -> Optional[int]:
            if index < 0 or index >= len(parts):
                return None
            try:
                return int(float(parts[index]))
            except Exception:
                return None

        neighbor_n = _int_at(idx_nb)
        pre_id = _int_at(idx_pre)
        next_id = _int_at(idx_next)
        if (neighbor_n is not None and neighbor_n >= 3) or pre_id == -1 or next_id == -1:
            selected_ids.add(node_id)

    out: List[Dict[str, object]] = []
    for node_id in selected_ids:
        xy = coord_lookup.get(node_id)
        if xy is None:
            continue
        out.append({"id": node_id, "label": node_id, "x": xy[0], "y": xy[1]})

    def _sort_key(item: Dict[str, object]) -> Tuple[int, str]:
        text = str(item.get("id") or "")
        try:
            return (0, f"{int(text):012d}")
        except Exception:
            return (1, text)

    out.sort(key=_sort_key)
    return {
        "root": root_path.relative_to(base_dir).as_posix(),
        "neighborFile": neighbor_path.relative_to(base_dir).as_posix(),
        "gateFile": gates_path.relative_to(base_dir).as_posix(),
        "count": len(out),
        "junctions": out,
    }


def load_simulation_meshcheck(base_dir: Path, root_raw: str = "mesh") -> Dict[str, object]:
    root_path = _resolve_workspace_path(base_dir, root_raw.strip() or "mesh")
    if not root_path.exists() or not root_path.is_dir():
        raise FileNotFoundError(f"目录不存在: {root_raw}")

    def _pick_image(file_name: str) -> Optional[Path]:
        candidates = [
            root_path / file_name,
            base_dir / "mesh" / file_name,
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    def _to_data_url(path: Optional[Path]) -> Optional[str]:
        if path is None:
            return None
        suffix = path.suffix.lower()
        mime = "image/png"
        if suffix in (".jpg", ".jpeg"):
            mime = "image/jpeg"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{data}"

    mesh_check_path = _pick_image("MeshCheck.png")
    mesh_grid_check_path = _pick_image("MeshGridCheck.png")

    return {
        "root": root_path.relative_to(base_dir).as_posix(),
        "meshCheckPath": mesh_check_path.relative_to(base_dir).as_posix() if mesh_check_path else None,
        "meshGridCheckPath": mesh_grid_check_path.relative_to(base_dir).as_posix() if mesh_grid_check_path else None,
        "meshCheckDataUrl": _to_data_url(mesh_check_path),
        "meshGridCheckDataUrl": _to_data_url(mesh_grid_check_path),
    }


def _resolve_workspace_path(base_dir: Path, raw_path: str) -> Path:
    target_path = Path(raw_path)
    if not target_path.is_absolute():
        target_path = (base_dir / target_path).resolve()
    else:
        target_path = target_path.resolve()
    target_path.relative_to(base_dir)
    return target_path


def _path_to_base_posix(path: Path, base_dir: Path) -> str:
    return path.resolve().relative_to(base_dir.resolve()).as_posix()


def _resolve_in_allowed_roots(base_dir: Path, raw_path: str, allowed_roots: List[Path]) -> Path:
    target_path = Path(raw_path)
    if not target_path.is_absolute():
        target_path = (base_dir / target_path).resolve()
    else:
        target_path = target_path.resolve()
    for root in allowed_roots:
        try:
            target_path.relative_to(root.resolve())
            return target_path
        except Exception:
            continue
    raise ValueError("path out of workspace")


def _choose_case_edges_path(case_dir: Path) -> Optional[Path]:
    candidates = [
        (case_dir / "mesh" / "edges_new.csv").resolve(),
        (case_dir / "mesh" / "edges.csv").resolve(),
        (case_dir / "mesh" / "edges_utf8.csv").resolve(),
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _is_case_dir(path: Path) -> bool:
    return _choose_case_edges_path(path) is not None


def detect_cases_root(base_dir: Path) -> Path:
  base = base_dir.resolve()
  if not _is_case_dir(base):
    return base
  parent = base.parent.resolve()
  siblings = []
  for child in parent.iterdir():
    if not child.is_dir():
      continue
    if child.resolve() == base:
      continue
    if _is_case_dir(child):
      siblings.append(child)
  if siblings:
    return parent
  return base


def _iter_case_dirs(cases_root: Path) -> List[Path]:
    root = cases_root.resolve()
    cases: List[Path] = []

    child_cases: List[Path] = []
    if root.exists() and root.is_dir():
        for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if child.is_dir() and _is_case_dir(child):
                child_cases.append(child.resolve())

    if child_cases:
        cases.extend(child_cases)
    elif _is_case_dir(root):
        cases.append(root)

    seen: Set[str] = set()
    deduped: List[Path] = []
    for case_dir in cases:
        key = str(case_dir.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(case_dir)
    return deduped


def list_case_dirs(base_dir: Path, cases_root: Optional[Path] = None, current_case_dir: Optional[Path] = None) -> Dict[str, object]:
    data_root = (cases_root or detect_cases_root(base_dir)).resolve()
    cases: List[Dict[str, str]] = []
    case_dirs = _iter_case_dirs(data_root)
    for case_dir in case_dirs:
        edges_path = _choose_case_edges_path(case_dir)
        cases.append(
            {
                "name": case_dir.name,
                "path": _path_to_base_posix(case_dir, base_dir),
                "edgesPath": _path_to_base_posix(edges_path, base_dir) if edges_path else "",
            }
        )

    current_case = "."
    if current_case_dir is not None:
        try:
            current_case = _path_to_base_posix(current_case_dir.resolve(), base_dir)
        except Exception:
            current_case = "."
    available_paths = {item["path"] for item in cases}
    if current_case not in available_paths and cases:
        current_case = cases[0]["path"]

    return {
        "root": _path_to_base_posix(data_root, base_dir),
        "currentCase": current_case,
        "cases": cases,
    }


def build_classic_html(base_dir: Path, cases_root: Path, edges_path: Optional[Path], startup_warning: str = "") -> str:
  current_case_dir = None
  if edges_path is not None:
    candidate = edges_path.parent.parent
    if candidate.exists():
      current_case_dir = candidate
    try:
        case_payload = list_case_dirs(base_dir, cases_root, current_case_dir)
    except Exception:
        case_payload = {"root": ".", "currentCase": ".", "cases": []}

    current_case = str(case_payload.get("currentCase") or ".")
    case_items = case_payload.get("cases") if isinstance(case_payload, dict) else []
    case_items = case_items if isinstance(case_items, list) else []

    options: List[str] = []
    for item in case_items:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or ".").strip() or "."
        name = str(item.get("name") or path).strip() or path
        selected = " selected" if path == current_case else ""
        options.append(
            f'<option value="{html.escape(path, quote=True)}"{selected}>{html.escape(name)}</option>'
        )
    if not options:
      options = ['<option value=".">.</option>']

    select_placeholder = '<select id="caseSelect"><option value=".">.</option></select>'
    select_html = '<select id="caseSelect">' + ''.join(options) + '</select>'

    page = HTML_PAGE.replace(select_placeholder, select_html, 1)
    bootstrap_json = json.dumps(case_payload, ensure_ascii=False)
    startup_warning_json = json.dumps(str(startup_warning or ""), ensure_ascii=False)
    page = page.replace(
      '<script>',
      '<script>\nwindow.__BOOTSTRAP_CASES__ = ' + bootstrap_json + ';\nwindow.__BOOTSTRAP_WARNING__ = ' + startup_warning_json + ';\n',
      1,
    )
    return page


def _choose_numeric_column(rows: List[Dict[str, str]], required: str = "") -> Optional[str]:
    if not rows:
        return None
    headers = list(rows[0].keys())
    if required:
        return required if required in headers else None

    best_col: Optional[str] = None
    best_count = 0
    for col in headers:
        count = 0
        sample_len = min(len(rows), 200)
        for idx in range(sample_len):
            if _parse_float_text(rows[idx].get(col)) is not None:
                count += 1
        if count > best_count:
            best_count = count
            best_col = col
    if best_count <= 0:
        return None
    return best_col


def build_curve_compare_payload(base_dir: Path, items: List[Dict[str, object]], y_column: str = "") -> Dict[str, object]:
    series: List[Dict[str, object]] = []
    for idx, item in enumerate(items):
        raw_path = str(item.get("path", "")).strip()
        if not raw_path:
            continue
        label = str(item.get("label", "")).strip() or f"line{idx + 1}"

        target_path = _resolve_workspace_path(base_dir, raw_path)
        if not target_path.exists() or target_path.is_dir():
            raise FileNotFoundError(f"文件不存在: {raw_path}")

        rows = read_rows_auto(target_path)
        if not rows:
            raise ValueError(f"文件无数据: {raw_path}")

        col = _choose_numeric_column(rows, y_column)
        if not col:
            if y_column:
                raise ValueError(f"文件 {raw_path} 不包含列: {y_column}")
            raise ValueError(f"文件 {raw_path} 未找到可用数值列")

        x_values: List[float] = []
        y_values: List[float] = []
        for row_idx, row in enumerate(rows):
            yv = _parse_float_text(row.get(col))
            if yv is None:
                continue
            x_values.append(float(row_idx))
            y_values.append(yv)

        if not y_values:
            raise ValueError(f"文件 {raw_path} 列 {col} 无有效数值")

        series.append(
            {
                "path": raw_path,
                "label": label,
                "column": col,
                "x": x_values,
                "y": y_values,
            }
        )

    if not series:
        raise ValueError("未提供有效对比文件")

    return {
        "xLabel": "index",
        "yLabel": y_column or "auto",
        "series": series,
    }


def _first_existing_path(candidates: List[Path]) -> Optional[Path]:
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _extract_timeseries_columns(csv_path: Path) -> List[str]:
    rows = read_rows_auto(csv_path)
    if not rows:
        return []
    time_cols = {"point/time", "tm", "Timestamp", "timestamp"}
    cols: List[str] = []
    sample_len = min(len(rows), 300)
    for key in rows[0].keys():
        name = str(key).strip()
        if not name or name in time_cols:
            continue
        numeric_count = 0
        for idx in range(sample_len):
          value = _parse_float_text(rows[idx].get(name))
          if value is not None and value != 0:
                numeric_count += 1
        if numeric_count > 0:
            cols.append(name)
    return cols


def _detect_time_column(rows: List[Dict[str, str]]) -> Optional[str]:
    if not rows:
        return None
    preferred = ["point/time", "tm", "Timestamp", "timestamp", "time", "Time"]
    headers = list(rows[0].keys())
    for key in preferred:
        if key in headers:
            return key
    if headers:
        return headers[0]
    return None


def _has_non_zero_value_in_column(rows: List[Dict[str, str]], column: str) -> bool:
    for row in rows:
        value = _parse_float_text(row.get(column))
        if value is not None and value != 0:
            return True
    return False


def _try_parse_timestamp_text(value: object) -> Optional[datetime]:
  if value is None:
    return None
  text = str(value).strip()
  if not text:
    return None

  iso_text = text.replace("Z", "+00:00")
  try:
    parsed = datetime.fromisoformat(iso_text)
    if parsed.tzinfo is not None:
      parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed
  except Exception:
    pass

  formats = [
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%d %H",
    "%Y/%m/%d %H",
    "%Y%m%d%H%M%S",
    "%Y%m%d%H%M",
    "%m/%d/%H:%M",
    "%m/%d %H:%M",
  ]
  for fmt in formats:
    try:
      return datetime.strptime(text, fmt)
    except Exception:
      continue
  return None


def _build_discrete_time_anchors(
  all_rows: List[List[Dict[str, str]]],
  time_columns: List[Optional[str]],
  value_columns: List[str],
) -> List[Dict[str, object]]:
  anchors: Dict[str, Dict[str, object]] = {}
  first_seen_order = 0

  for rows_idx, rows in enumerate(all_rows):
    time_col = time_columns[rows_idx] if rows_idx < len(time_columns) else None
    for row_idx, row in enumerate(rows):
      has_value = False
      for col in value_columns:
        parsed_val = _parse_float_text(row.get(col))
        if parsed_val is not None and parsed_val != 0:
          has_value = True
          break
      if not has_value:
        continue

      raw_time = str(row.get(time_col, "") if time_col else "").strip()
      if not raw_time:
        raw_time = str(row_idx)

      parsed_time = _try_parse_timestamp_text(raw_time)
      if parsed_time is not None:
        key = f"dt:{parsed_time.strftime('%Y-%m-%d %H:%M:%S')}"
        sort_group = 0
        sort_value: object = parsed_time
        tm_value = parsed_time.strftime("%Y-%m-%d %H:%M:%S")
      else:
        key = f"raw:{raw_time}"
        sort_group = 1
        sort_value = first_seen_order
        synthetic_dt = datetime(2000, 1, 1) + timedelta(hours=first_seen_order)
        tm_value = synthetic_dt.strftime("%Y-%m-%d %H:%M:%S")

      if key not in anchors:
        anchors[key] = {
          "key": key,
          "tm": tm_value,
          "sortGroup": sort_group,
          "sortValue": sort_value,
          "firstSeen": first_seen_order,
        }
        first_seen_order += 1

  out = list(anchors.values())
  out.sort(key=lambda item: (int(item.get("sortGroup", 1)), item.get("sortValue"), int(item.get("firstSeen", 0))))
  return out


def _collect_values_by_anchor(
  rows: List[Dict[str, str]],
  time_col: Optional[str],
  keep_columns: List[str],
  valid_anchor_keys: Set[str],
) -> Dict[str, Dict[str, str]]:
  value_map: Dict[str, Dict[str, str]] = {}
  for row_idx, row in enumerate(rows):
    raw_time = str(row.get(time_col, "") if time_col else "").strip()
    if not raw_time:
      raw_time = str(row_idx)

    parsed_time = _try_parse_timestamp_text(raw_time)
    if parsed_time is not None:
      key = f"dt:{parsed_time.strftime('%Y-%m-%d %H:%M:%S')}"
    else:
      key = f"raw:{raw_time}"
    if key not in valid_anchor_keys:
      continue

    target = value_map.setdefault(key, {})
    for col in keep_columns:
      raw_val = str(row.get(col, "")).strip()
      if raw_val:
        target[col] = raw_val
  return value_map


def _create_sanitized_compare_csv_aligned(
  base_dir: Path,
  rows: List[Dict[str, str]],
  time_col: Optional[str],
  keep_columns: List[str],
  index: int,
  anchors: List[Dict[str, object]],
) -> Path:
  out_dir = (base_dir / "output").resolve()
  out_dir.mkdir(parents=True, exist_ok=True)
  out_path = out_dir / f"_curve_compare_input_{index}.csv"

  valid_anchor_keys = {str(item.get("key", "")) for item in anchors}
  value_map = _collect_values_by_anchor(rows, time_col, keep_columns, valid_anchor_keys)

  with out_path.open("w", encoding="utf-8-sig", newline="") as f:
    fieldnames = ["tm"] + keep_columns
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for anchor in anchors:
      anchor_key = str(anchor.get("key", ""))
      tm_value = str(anchor.get("tm", "")).strip()
      out_row: Dict[str, str] = {"tm": tm_value}
      row_values = value_map.get(anchor_key, {})
      for col in keep_columns:
        out_row[col] = str(row_values.get(col, ""))
      writer.writerow(out_row)
  return out_path


def _create_sanitized_compare_csv(base_dir: Path, source_path: Path, keep_columns: List[str], index: int) -> Path:
    rows = read_rows_auto(source_path)
    if not rows:
        raise ValueError(f"文件无数据: {source_path}")
    time_col = _detect_time_column(rows)
    if not time_col:
        raise ValueError(f"文件 {source_path.name} 未找到时间列")

    out_dir = (base_dir / "output").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"_curve_compare_input_{index}.csv"
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = ["tm"] + keep_columns
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row_idx, row in enumerate(rows):
            tm = str(row.get(time_col, "")).strip()
            if not tm:
                tm = str(row_idx)
            out_row: Dict[str, str] = {"tm": tm}
            for col in keep_columns:
                out_row[col] = str(row.get(col, "")).strip()
            writer.writerow(out_row)
    return out_path


def _build_temp_gate_params(base_dir: Path, columns: List[str]) -> Path:
    out_dir = (base_dir / "output").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "_curve_compare_gates_params.csv"
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["region"])
        writer.writeheader()
        for col in columns:
            writer.writerow({"region": col})
    return out_path


def _load_node_type_lookup(base_dir: Path) -> Dict[str, str]:
  candidates = [
    (base_dir / "mesh" / "edges.csv").resolve(),
    (base_dir / "mesh" / "edges_utf8.csv").resolve(),
  ]
  edge_path = _first_existing_path(candidates)
  if edge_path is None:
    return {}

  def _is_type_zero(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
      return False
    if raw == "0":
      return True
    try:
      return float(raw) == 0.0
    except Exception:
      return False

  lookup: Dict[str, str] = {}
  rows = read_rows_auto(edge_path)
  for row in rows:
    edge = with_required_columns(row)
    node_type = str(edge.get("type", "")).strip()
    if not node_type:
      continue
    keys = ("source",) if _is_type_zero(node_type) else ("source", "target", "end")
    for key in keys:
      name = normalize_name(edge.get(key))
      if name and name not in lookup:
        lookup[name] = node_type
  return lookup


def run_curve_compare_plot(
  base_dir: Path,
  items: List[Dict[str, object]],
  y_column: str = "",
  x_min: Optional[float] = None,
  x_max: Optional[float] = None,
  y_min: Optional[float] = None,
  y_max: Optional[float] = None,
  dpi: int = 300,
  fig_size_x: float = 20,
  fig_size_y: float = 10,
  font_size: int = 16,
  legend_x: float = 0.52,
  legend_y: float = 1.00,
  selected_node_types: Optional[List[str]] = None,
  selected_gates: Optional[List[str]] = None,
) -> Dict[str, object]:
  raw_linepaths: List[Path] = []
  linelabels: List[str] = []
  for idx, item in enumerate(items):
    raw_path = str(item.get("path", "")).strip()
    if not raw_path:
      continue
    label = str(item.get("label", "")).strip() or f"line{idx + 1}"
    target_path = _resolve_workspace_path(base_dir, raw_path)
    if not target_path.exists() or target_path.is_dir():
      raise FileNotFoundError(f"文件不存在: {raw_path}")
    raw_linepaths.append(target_path)
    linelabels.append(label)

  if not raw_linepaths:
    raise ValueError("未提供有效对比文件")

  first_series_path = raw_linepaths[0]
  series_columns = _extract_timeseries_columns(first_series_path)
  for path in raw_linepaths[1:]:
    cols = set(_extract_timeseries_columns(path))
    series_columns = [c for c in series_columns if c in cols]
  all_rows: List[List[Dict[str, str]]] = [read_rows_auto(path) for path in raw_linepaths]
  if all_rows:
    series_columns = [
      c
      for c in series_columns
      if all(_has_non_zero_value_in_column(rows, c) for rows in all_rows)
    ]
  if not series_columns:
    raise ValueError(f"文件 {first_series_path.name} 未识别到可用于对象对比的列")

  all_common_columns = list(series_columns)
  node_type_lookup = _load_node_type_lookup(base_dir)
  all_node_types = sorted({node_type_lookup.get(normalize_name(col) or str(col), "未分类") for col in all_common_columns})
  gate_options = [
    {
      "name": col,
      "nodeType": node_type_lookup.get(normalize_name(col) or str(col), "未分类"),
    }
    for col in all_common_columns
  ]
  selected_set = {
    str(v).strip() for v in (selected_node_types or []) if str(v).strip()
  }
  if selected_set:
    filtered_columns: List[str] = []
    for col in series_columns:
      col_name = normalize_name(col) or str(col)
      node_type = node_type_lookup.get(col_name, "未分类")
      if node_type in selected_set:
        filtered_columns.append(col)
    series_columns = filtered_columns
    if not series_columns:
      raise ValueError("按节点类型过滤后无可绘制对象列")

  selected_gate_set = {
    str(v).strip() for v in (selected_gates or []) if str(v).strip()
  }
  if selected_gate_set:
    series_columns = [c for c in series_columns if c in selected_gate_set]
    if not series_columns:
      raise ValueError("按闸门过滤后无可绘制对象列")

  linepaths: List[str] = []
  time_columns = [_detect_time_column(rows) for rows in all_rows]
  anchors = _build_discrete_time_anchors(all_rows, time_columns, series_columns)
  if not anchors:
    raise ValueError("未识别到可用于时间轴锚定的有效时间戳")

  for idx, rows in enumerate(all_rows):
    time_col = time_columns[idx] if idx < len(time_columns) else None
    sanitized = _create_sanitized_compare_csv_aligned(
      base_dir=base_dir,
      rows=rows,
      time_col=time_col,
      keep_columns=series_columns,
      index=idx,
      anchors=anchors,
    )
    linepaths.append(str(sanitized))

  gate_param_path = _first_existing_path(
    [
      (first_series_path.parent / "Gates_params.csv").resolve(),
      (base_dir / "output" / "Gates_params.csv").resolve(),
      (base_dir / "Gates_params.csv").resolve(),
    ]
  )
  if gate_param_path is None:
    gate_param_path = _build_temp_gate_params(base_dir, series_columns)

  config_path = _first_existing_path(
    [
      (first_series_path.parent / "config.dat").resolve(),
      (base_dir / "output" / "config.dat").resolve(),
      (base_dir / "config.dat").resolve(),
    ]
  )
  if config_path is None:
    config_path = first_series_path

  edges_path = _first_existing_path(
    [
      (base_dir / "mesh" / "edges.csv").resolve(),
      (base_dir / "mesh" / "edges_utf8.csv").resolve(),
    ]
  )
  if edges_path is None:
    edges_path = first_series_path

  datatype = "stage"
  low = y_column.lower()
  if "flow" in low or low == "q":
    datatype = "Flow"

  out_dir = (base_dir / "output").resolve()
  out_dir.mkdir(parents=True, exist_ok=True)
  out_path = out_dir / f"curve_compare_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

  plot_dir = (base_dir / "src" / "plot").resolve()
  src_dir = (base_dir / "src").resolve()
  for p in [str(plot_dir), str(src_dir), str(base_dir)]:
    if p not in sys.path:
      sys.path.insert(0, p)

  try:
    from src.plot.dataProcess import MultipleWaterLevelContrast_error
  except Exception as exc:
    raise RuntimeError(f"导入 MultipleWaterLevelContrast_error 失败: {exc}")

  try:
    MultipleWaterLevelContrast_error(
      linepaths=linepaths,
      linelabels=linelabels,
      pathconfig=str(config_path),
      outpath=str(out_path),
      Gate_param_path=str(gate_param_path),
      edges_path=str(edges_path),
      datatype=datatype,
      obj_num_s=0,
      obj_num=len(series_columns),
      time_num=1000,
      plotData=1,
      plot_x_time=False,
      ncols=2,
      legend_ncol=max(2, len(linelabels)),
      fig_size_x=fig_size_x,
      fig_size_y=fig_size_y,
      font_size=font_size,
      legend_x=legend_x,
      legend_y=legend_y,
      save_dpi=dpi,
      x_min=x_min,
      x_max=x_max,
      y_min=y_min,
      y_max=y_max,
    )
  except Exception as exc:
    raise RuntimeError(f"MultipleWaterLevelContrast_error 执行失败: {exc}")

  if not out_path.exists() or out_path.stat().st_size <= 0:
    raise RuntimeError("曲线图生成失败，未输出图片")

  image_b64 = base64.b64encode(out_path.read_bytes()).decode("ascii")
  return {
    "mode": "image",
    "title": "MultipleWaterLevelContrast_error",
    "imageDataUrl": f"data:image/png;base64,{image_b64}",
    "outputPath": out_path.relative_to(base_dir).as_posix(),
    "lineCount": len(linepaths),
    "dpi": dpi,
    "figSizeX": fig_size_x,
    "figSizeY": fig_size_y,
    "fontSize": font_size,
    "legendX": legend_x,
    "legendY": legend_y,
    "xMin": x_min,
    "xMax": x_max,
    "yMin": y_min,
    "yMax": y_max,
    "nodeTypes": all_node_types,
    "selectedNodeTypes": sorted({node_type_lookup.get(normalize_name(col) or str(col), "未分类") for col in series_columns}),
    "gateOptions": gate_options,
    "selectedGates": list(series_columns),
    "timeAnchorCount": len(anchors),
  }


def run_curve_compare_interactive_payload(
  base_dir: Path,
  items: List[Dict[str, object]],
  y_column: str = "",
  dpi: int = 300,
  fig_size_x: float = 20,
  fig_size_y: float = 10,
  font_size: int = 16,
) -> Dict[str, object]:
  raw_linepaths: List[Path] = []
  linelabels: List[str] = []
  raw_paths: List[str] = []
  for idx, item in enumerate(items):
    raw_path = str(item.get("path", "")).strip()
    if not raw_path:
      continue
    label = str(item.get("label", "")).strip() or f"line{idx + 1}"
    target_path = _resolve_workspace_path(base_dir, raw_path)
    if not target_path.exists() or target_path.is_dir():
      raise FileNotFoundError(f"文件不存在: {raw_path}")
    raw_linepaths.append(target_path)
    linelabels.append(label)
    raw_paths.append(raw_path)

  if not raw_linepaths:
    raise ValueError("未提供有效对比文件")

  if y_column:
    series_columns = [y_column]
  else:
    series_columns = _extract_timeseries_columns(raw_linepaths[0])
    for path in raw_linepaths[1:]:
      cols = set(_extract_timeseries_columns(path))
      series_columns = [c for c in series_columns if c in cols]

  if not series_columns:
    raise ValueError("未找到可用于多子图对比的公共数值列")

  node_type_lookup = _load_node_type_lookup(base_dir)
  all_rows: List[List[Dict[str, str]]] = [read_rows_auto(path) for path in raw_linepaths]
  if all_rows:
    series_columns = [
      c
      for c in series_columns
      if all(_has_non_zero_value_in_column(rows, c) for rows in all_rows)
    ]
  if not series_columns:
    raise ValueError("所有数据源同时有非零值的对象列为空")
  subplots: List[Dict[str, object]] = []
  node_types_set: Set[str] = set()
  time_columns = [_detect_time_column(rows) for rows in all_rows]
  for col in series_columns:
    anchors = _build_discrete_time_anchors(all_rows, time_columns, [col])
    if not anchors:
      continue
    anchor_keys = [str(item.get("key", "")) for item in anchors]
    anchor_index = {key: idx for idx, key in enumerate(anchor_keys)}
    anchor_labels = [str(item.get("tm", "")) for item in anchors]

    col_name = normalize_name(col) or str(col)
    node_type = node_type_lookup.get(col_name, "未分类")
    subplot_traces: List[Dict[str, object]] = []
    for path_idx, rows in enumerate(all_rows):
      x_values: List[float] = []
      y_values: List[float] = []
      x_labels: List[str] = []
      row_time_col = time_columns[path_idx] if path_idx < len(time_columns) else None
      value_by_anchor: Dict[str, float] = {}
      for row_idx, row in enumerate(rows):
        yv = _parse_float_text(row.get(col))
        if yv is None or yv == 0:
          continue
        raw_time = str(row.get(row_time_col, "") if row_time_col else "").strip()
        if not raw_time:
          raw_time = str(row_idx)
        parsed_time = _try_parse_timestamp_text(raw_time)
        if parsed_time is not None:
          key = f"dt:{parsed_time.strftime('%Y-%m-%d %H:%M:%S')}"
        else:
          key = f"raw:{raw_time}"
        if key not in anchor_index:
          continue
        value_by_anchor[key] = yv

      for key in anchor_keys:
        if key not in value_by_anchor:
          continue
        x_idx = anchor_index[key]
        x_values.append(float(x_idx))
        y_values.append(value_by_anchor[key])
        x_labels.append(anchor_labels[x_idx])

      if y_values:
        subplot_traces.append(
          {
            "path": raw_paths[path_idx],
            "label": linelabels[path_idx],
            "column": col,
            "x": x_values,
            "y": y_values,
            "xLabels": x_labels,
          }
        )
    if len(subplot_traces) == len(all_rows):
      subplots.append(
        {
          "column": col,
          "title": col,
          "nodeType": node_type,
          "xTicks": anchor_labels,
          "traces": subplot_traces,
        }
      )
      node_types_set.add(node_type)

  if not subplots:
    raise ValueError("没有可绘制的子图数据")

  subplot_cols = 2
  subplot_rows = max(1, int(math.ceil(len(subplots) / subplot_cols)))
  width_px = int(round(max(4.0, min(80.0, fig_size_x)) * 60))
  min_height_px = subplot_rows * 260 + 120
  height_px = max(int(round(max(4.0, min(80.0, fig_size_y)) * 62)), min_height_px)

  return {
    "mode": "interactive",
    "title": "交互式曲线对比",
    "xLabel": "timestamp_index",
    "yLabel": y_column or "auto",
    "lineCount": len(raw_linepaths),
    "dpi": dpi,
    "figSizeX": fig_size_x,
    "figSizeY": fig_size_y,
    "fontSize": font_size,
    "widthPx": width_px,
    "heightPx": height_px,
    "subplotCols": subplot_cols,
    "subplotRows": subplot_rows,
    "columns": series_columns,
    "nodeTypes": sorted(node_types_set),
    "paths": raw_paths,
    "subplots": subplots,
  }


def build_path_tree_items(base_dir: Path, root_path: Path, max_depth: int = 4) -> List[Dict[str, object]]:
    items: List[Dict[str, object]] = []

    def _walk(path: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            children = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except Exception:
            return

        for child in children:
            rel = child.relative_to(base_dir).as_posix()
            is_dir = child.is_dir()
            items.append(
                {
                    "name": child.name,
                    "path": rel,
                    "isDir": is_dir,
                    "depth": depth,
                }
            )
            if is_dir:
                _walk(child, depth + 1)

    _walk(root_path, 0)
    return items


class AppHandler(BaseHTTPRequestHandler):
    edges_path: Optional[Path] = Path("mesh/edges.csv")
    shp_path: Path = Path("mesh/shp/edges.shp")
    base_dir: Path = Path.cwd()
    cases_root: Path = Path.cwd()
    startup_warning: str = ""

    def _json_response(self, payload: Dict[str, object], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html_response(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._html_response(PLAYGROUND_STYLE_HTML)
            return

        if parsed.path == "/api/health":
            self._json_response(
                {
                    "ok": True,
                    "app": "web_topology_editor",
                    "pid": os.getpid(),
                    "cwd": str(Path.cwd()),
                    "edgesPath": str(self.edges_path) if self.edges_path is not None else None,
                    "startupWarning": self.startup_warning,
                }
            )
            return

        if parsed.path == "/classic":
            self._html_response(build_classic_html(self.base_dir, self.cases_root, self.edges_path, self.startup_warning))
            return

        if parsed.path == "/minimal-drag-test":
            self._html_response(MINIMAL_DRAG_TEST_HTML)
            return

        if parsed.path == "/playground-style":
            self._html_response(PLAYGROUND_STYLE_HTML)
            return

        if parsed.path == "/api/graph":
            if self.edges_path is None:
                self._json_response({"error": self.startup_warning or "默认 edges 文件不存在，请在页面中指定有效路径"}, status=404)
                return
            if not self.edges_path.exists():
                self._json_response({"error": f"默认 edges 文件不存在: {self.edges_path}"}, status=404)
                return
            graph = load_graph(self.edges_path, self.shp_path)
            self._json_response(graph)
            return

        if parsed.path == "/api/cases":
            try:
                current_case_dir = None
                if self.edges_path is not None:
                    candidate = self.edges_path.parent.parent
                    if candidate.exists():
                        current_case_dir = candidate
                self._json_response(list_case_dirs(self.base_dir, self.cases_root, current_case_dir))
            except Exception as exc:
                self._json_response({"error": str(exc)}, status=500)
            return

        if parsed.path == "/api/graph-case":
          query = parse_qs(parsed.query)
          raw_case = str((query.get("case") or ["."])[0]).strip() or "."
          allowed_roots = [self.base_dir.resolve(), self.cases_root.resolve()]
          try:
            case_dir = _resolve_in_allowed_roots(self.base_dir, raw_case, allowed_roots)
          except Exception:
            self._json_response({"error": "case out of workspace"}, status=400)
            return
          if not case_dir.exists() or not case_dir.is_dir():
            self._json_response({"error": f"case not found: {raw_case}"}, status=404)
            return
          edges_path = _choose_case_edges_path(case_dir)
          if edges_path is None:
            self._json_response({"error": f"案例缺少 edges 文件: {case_dir}"}, status=404)
            return
          shp_path = (edges_path.parent / "shp" / "edges.shp").resolve()
          graph = load_graph(edges_path, shp_path)
          graph["casePath"] = _path_to_base_posix(case_dir, self.base_dir)
          graph["edgesPath"] = _path_to_base_posix(edges_path, self.base_dir)
          self._json_response(graph)
          return

        if parsed.path == "/api/graph-file":
          query = parse_qs(parsed.query)
          raw_path = str((query.get("path") or [""])[0]).strip()
          if not raw_path:
            self._json_response({"error": "path is required"}, status=400)
            return
          try:
            target_path = _resolve_in_allowed_roots(self.base_dir, raw_path, [self.base_dir.resolve(), self.cases_root.resolve()])
          except Exception:
            self._json_response({"error": "path out of workspace"}, status=400)
            return
          if not target_path.exists():
            self._json_response({"error": f"file not found: {target_path}"}, status=404)
            return
          shp_guess = (target_path.parent / "shp" / "edges.shp").resolve()
          graph = load_graph(target_path, shp_guess)
          self._json_response(graph)
          return

        if parsed.path == "/api/path-tree":
            query = parse_qs(parsed.query)
            raw_root = str((query.get("root") or ["."])[0]).strip() or "."
            raw_depth = str((query.get("depth") or ["4"])[0]).strip()
            try:
                depth = max(1, min(6, int(raw_depth)))
            except Exception:
                depth = 4

            try:
              root = _resolve_in_allowed_roots(self.base_dir, raw_root, [self.base_dir.resolve(), self.cases_root.resolve()])
            except Exception:
                self._json_response({"error": "root out of workspace"}, status=400)
                return

            if not root.exists():
                self._json_response({"error": f"path not found: {root}"}, status=404)
                return
            if root.is_file():
                root = root.parent

            items = build_path_tree_items(self.base_dir, root, max_depth=depth)
            self._json_response({"root": _path_to_base_posix(root, self.base_dir), "items": items})
            return

        if parsed.path == "/api/sim-result-meta":
            query = parse_qs(parsed.query)
            root = str((query.get("root") or ["mesh"])[0]).strip() or "mesh"
            pattern = str((query.get("pattern") or ["result*.dat"])[0]).strip() or "result*.dat"
            try:
                payload = load_simulation_meta(self.base_dir, root_raw=root, pattern_raw=pattern)
                self._json_response(payload)
            except Exception as exc:
                self._json_response({"error": str(exc)}, status=400)
            return

        if parsed.path == "/api/sim-result-step":
            query = parse_qs(parsed.query)
            root = str((query.get("root") or ["mesh"])[0]).strip() or "mesh"
            pattern = str((query.get("pattern") or ["result*.dat"])[0]).strip() or "result*.dat"
            step_raw = str((query.get("step") or ["0"])[0]).strip() or "0"
            try:
                payload = load_simulation_step(self.base_dir, root_raw=root, pattern_raw=pattern, step_raw=int(step_raw))
                self._json_response(payload)
            except Exception as exc:
                self._json_response({"error": str(exc)}, status=400)
            return

        if parsed.path == "/api/sim-curve-series":
          query = parse_qs(parsed.query)
          root = str((query.get("root") or ["mesh"])[0]).strip() or "mesh"
          pattern = str((query.get("pattern") or ["result*.dat"])[0]).strip() or "result*.dat"
          try:
            payload = load_simulation_curve_series(self.base_dir, root_raw=root, pattern_raw=pattern)
            self._json_response(payload)
          except Exception as exc:
            self._json_response({"error": str(exc)}, status=400)
          return

        if parsed.path == "/api/sim-gates":
            query = parse_qs(parsed.query)
            root = str((query.get("root") or ["mesh"])[0]).strip() or "mesh"
            gate_file = str((query.get("gateFile") or ["gates_mesh.csv"])[0]).strip() or "gates_mesh.csv"
            try:
                payload = load_simulation_gates(self.base_dir, root_raw=root, gate_file_raw=gate_file)
                self._json_response(payload)
            except Exception as exc:
                self._json_response({"error": str(exc)}, status=400)
            return

        if parsed.path == "/api/sim-junctions":
          query = parse_qs(parsed.query)
          root = str((query.get("root") or ["mesh"])[0]).strip() or "mesh"
          try:
            payload = load_simulation_junctions(self.base_dir, root_raw=root)
            self._json_response(payload)
          except Exception as exc:
            self._json_response({"error": str(exc)}, status=400)
          return

        if parsed.path == "/api/sim-meshcheck":
          query = parse_qs(parsed.query)
          root = str((query.get("root") or ["mesh"])[0]).strip() or "mesh"
          try:
            payload = load_simulation_meshcheck(self.base_dir, root_raw=root)
            self._json_response(payload)
          except Exception as exc:
            self._json_response({"error": str(exc)}, status=400)
          return

        if parsed.path == "/api/health":
            self._json_response({"ok": True, "edgesPath": str(self.edges_path)})
            return

        if parsed.path == "/api/analyze-config":
          query = parse_qs(parsed.query)
          raw_path = str((query.get("path") or ["mesh/Gates_param.csv"])[0]).strip() or "mesh/Gates_param.csv"
          try:
            target_path = _resolve_workspace_path(self.base_dir, raw_path)
            if not target_path.exists() or target_path.is_dir():
              if target_path.name == "Gates_param.csv":
                fallback_path = target_path.parent / "Gates_params.csv"
                if fallback_path.exists() and fallback_path.is_file():
                  content = read_text_auto(fallback_path)
                  self._json_response({"path": target_path.relative_to(self.base_dir).as_posix(), "content": content})
                  return
              self._json_response({"error": f"file not found: {raw_path}"}, status=404)
              return
            content = read_text_auto(target_path)
            self._json_response({"path": target_path.relative_to(self.base_dir).as_posix(), "content": content})
          except Exception as exc:
            self._json_response({"error": str(exc)}, status=400)
          return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/analyze-config":
          length = int(self.headers.get("Content-Length", "0"))
          raw = self.rfile.read(length)
          try:
            payload = json.loads(raw.decode("utf-8"))
          except Exception:
            self._json_response({"error": "invalid json"}, status=400)
            return

          raw_path = str(payload.get("path", "mesh/Gates_param.csv")).strip() or "mesh/Gates_param.csv"
          content = str(payload.get("content", ""))
          try:
            target_path = _resolve_workspace_path(self.base_dir, raw_path)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8-sig")
            self._json_response({"savedTo": target_path.relative_to(self.base_dir).as_posix()})
          except Exception as exc:
            self._json_response({"error": str(exc)}, status=400)
          return

        if parsed.path == "/api/data-tools":
          length = int(self.headers.get("Content-Length", "0"))
          raw = self.rfile.read(length)
          try:
            payload = json.loads(raw.decode("utf-8"))
          except Exception:
            self._json_response({"error": "invalid json"}, status=400)
            return
          if not isinstance(payload, dict):
            self._json_response({"error": "payload must be object"}, status=400)
            return
          try:
            result = _run_data_processing_tool(self.base_dir, payload)
            self._json_response(result)
          except Exception as exc:
            self._json_response({"error": str(exc)}, status=400)
          return

        if parsed.path == "/api/curve-compare":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                self._json_response({"error": "invalid json"}, status=400)
                return

            items = payload.get("items", [])
            y_column = str(payload.get("yColumn", "")).strip()
            selected_node_types_raw = payload.get("selectedNodeTypes", [])
            if isinstance(selected_node_types_raw, list):
              selected_node_types = [str(v).strip() for v in selected_node_types_raw if str(v).strip()]
            else:
              selected_node_types = []
            selected_gates_raw = payload.get("selectedGates", [])
            if isinstance(selected_gates_raw, list):
              selected_gates = [str(v).strip() for v in selected_gates_raw if str(v).strip()]
            else:
              selected_gates = []
            def parse_optional_float(value):
              if value is None:
                return None
              if isinstance(value, str) and not value.strip():
                return None
              try:
                parsed_val = float(value)
              except Exception:
                return None
              if not math.isfinite(parsed_val):
                return None
              return parsed_val
            x_min = parse_optional_float(payload.get("xMin"))
            x_max = parse_optional_float(payload.get("xMax"))
            y_min = parse_optional_float(payload.get("yMin"))
            y_max = parse_optional_float(payload.get("yMax"))
            dpi_raw = payload.get("dpi", 300)
            fig_size_x_raw = payload.get("figSizeX", 20)
            fig_size_y_raw = payload.get("figSizeY", 10)
            font_size_raw = payload.get("fontSize", 16)
            legend_x_raw = payload.get("legendX", 0.52)
            legend_y_raw = payload.get("legendY", 1.0)
            try:
                dpi = int(dpi_raw)
            except Exception:
                dpi = 300
            dpi = max(72, min(1200, dpi))
            try:
                fig_size_x = float(fig_size_x_raw)
            except Exception:
                fig_size_x = 20.0
            try:
                fig_size_y = float(fig_size_y_raw)
            except Exception:
                fig_size_y = 10.0
            try:
                font_size = int(font_size_raw)
            except Exception:
                font_size = 16
            try:
                legend_x = float(legend_x_raw)
            except Exception:
                legend_x = 0.52
            try:
                legend_y = float(legend_y_raw)
            except Exception:
                legend_y = 1.0
            fig_size_x = max(4.0, min(80.0, fig_size_x))
            fig_size_y = max(4.0, min(80.0, fig_size_y))
            font_size = max(8, min(48, font_size))
            legend_x = max(0.0, min(1.2, legend_x))
            legend_y = max(0.0, min(1.4, legend_y))
            if not isinstance(items, list):
                self._json_response({"error": "items must be list"}, status=400)
                return
            try:
                normalized_items = [item for item in items if isinstance(item, dict)]
                result = run_curve_compare_plot(
                    self.base_dir,
                    normalized_items,
                    y_column,
                    x_min,
                    x_max,
                    y_min,
                    y_max,
                    dpi,
                    fig_size_x,
                    fig_size_y,
                    font_size,
                    legend_x,
                    legend_y,
                    selected_node_types,
                    selected_gates,
                )
                result["request"] = {
                    "items": [
                        {
                            "path": str(item.get("path", "")).strip(),
                            "label": str(item.get("label", "")).strip(),
                        }
                        for item in normalized_items
                        if str(item.get("path", "")).strip()
                    ],
                    "yColumn": y_column,
                    "xMin": x_min,
                    "xMax": x_max,
                    "yMin": y_min,
                    "yMax": y_max,
                    "dpi": dpi,
                    "figSizeX": fig_size_x,
                    "figSizeY": fig_size_y,
                    "fontSize": font_size,
                    "legendX": legend_x,
                    "legendY": legend_y,
                    "selectedNodeTypes": selected_node_types,
                    "selectedGates": selected_gates,
                }
                self._json_response(result)
            except Exception as exc:
                self._json_response({"error": str(exc)}, status=400)
            return

        if parsed.path == "/api/curve-compare-interactive":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                self._json_response({"error": "invalid json"}, status=400)
                return

            items = payload.get("items", [])
            y_column = str(payload.get("yColumn", "")).strip()
            dpi_raw = payload.get("dpi", 300)
            fig_size_x_raw = payload.get("figSizeX", 20)
            fig_size_y_raw = payload.get("figSizeY", 10)
            font_size_raw = payload.get("fontSize", 16)
            try:
                dpi = int(dpi_raw)
            except Exception:
                dpi = 300
            dpi = max(72, min(1200, dpi))
            try:
                fig_size_x = float(fig_size_x_raw)
            except Exception:
                fig_size_x = 20.0
            try:
                fig_size_y = float(fig_size_y_raw)
            except Exception:
                fig_size_y = 10.0
            try:
              font_size = int(font_size_raw)
            except Exception:
              font_size = 16
            fig_size_x = max(4.0, min(80.0, fig_size_x))
            fig_size_y = max(4.0, min(80.0, fig_size_y))
            font_size = max(8, min(48, font_size))
            if not isinstance(items, list):
                self._json_response({"error": "items must be list"}, status=400)
                return
            try:
                normalized_items = [item for item in items if isinstance(item, dict)]
                result = run_curve_compare_interactive_payload(
                    self.base_dir,
                    normalized_items,
                    y_column,
                    dpi,
                    fig_size_x,
                    fig_size_y,
                    font_size,
                )
                self._json_response(result)
            except Exception as exc:
                self._json_response({"error": str(exc)}, status=400)
            return

        if parsed.path != "/api/save":
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._json_response({"error": "invalid json"}, status=400)
            return

        edges = payload.get("edges", [])
        if not isinstance(edges, list):
            self._json_response({"error": "edges must be list"}, status=400)
            return

        output_path_raw = str(payload.get("outputPath", "")).strip()
        backup = bool(payload.get("backup", True))

        if output_path_raw:
            output_path = Path(output_path_raw)
            if not output_path.is_absolute():
                output_path = (self.base_dir / output_path).resolve()
        else:
          output_path = (self.base_dir / "mesh" / "edges_new.csv").resolve()

        try:
            saved = save_edges(edges, output_path, backup)
            self._json_response({"savedTo": str(saved), "rows": len(edges)})
        except Exception as exc:
            self._json_response({"error": str(exc)}, status=500)


def run_server(host: str, port: int, edges_path: Optional[Path], startup_warning: str = "") -> None:
    class _Handler(AppHandler):
        pass

    _Handler.base_dir = Path(__file__).resolve().parent
    _Handler.cases_root = _Handler.base_dir
    _Handler.startup_warning = str(startup_warning or "")
    if edges_path is not None:
        _Handler.edges_path = edges_path.resolve()
        _Handler.shp_path = (edges_path.parent / "shp" / "edges.shp").resolve()
    else:
        _Handler.edges_path = None
        _Handler.shp_path = (_Handler.base_dir / "mesh" / "shp" / "edges.shp").resolve()

    server = ThreadingHTTPServer((host, port), _Handler)
    print(f"渠网拓扑建模工具已启动: http://{host}:{port}")
    if _Handler.edges_path is not None:
        print(f"edges 文件: {_Handler.edges_path}")
    else:
        print("edges 文件: 未找到默认路径，请在页面红字提示下手动选择")
    server.serve_forever()


def _query_running_server(host: str, port: int, timeout: float = 0.6) -> Optional[Dict[str, object]]:
    url = f"http://{host}:{port}/api/health"
    try:
        with urlopen(url, timeout=timeout) as resp:
            raw = resp.read()
        data = json.loads(raw.decode("utf-8", errors="ignore"))
        if isinstance(data, dict) and bool(data.get("ok")) and str(data.get("app", "")) == "web_topology_editor":
            return data
    except Exception:
        return None
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Edges 渠网拓扑建模工具")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址，默认 127.0.0.1")
    parser.add_argument("--port", type=int, default=8510, help="端口，默认 8510")
    parser.add_argument("--edges", default="mesh/edges.csv", help="edges.csv 路径")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    edges_path = Path(args.edges)
    startup_warning = ""
    if not edges_path.is_absolute():
        edges_path = (Path.cwd() / edges_path).resolve()
    if not edges_path.exists():
        candidates = [
            (Path.cwd() / "mesh" / "edges.csv").resolve(),
            (Path.cwd() / "mesh" / "edges_new.csv").resolve(),
            (Path.cwd() / "ph" / "mesh" / "edges.csv").resolve(),
            (Path.cwd() / "ph" / "mesh" / "edges_new.csv").resolve(),
        ]
        fallback = next((p for p in candidates if p.exists()), None)
        if fallback is None:
            startup_warning = f"默认路径不存在: {edges_path}。服务已启动，请在页面中选择有效 edges 文件。"
            edges_path = None
        else:
            edges_path = fallback

    existing = _query_running_server(args.host, args.port)
    if existing is not None:
        print(
            f"检测到已有服务运行: http://{args.host}:{args.port} "
            f"(pid={existing.get('pid', '?')})"
        )
        print("为保证单实例，本次不再重复启动。")
        return

    try:
        run_server(args.host, args.port, edges_path, startup_warning=startup_warning)
    except OSError as exc:
        if getattr(exc, "errno", None) in (errno.EADDRINUSE, 10048):
            existing = _query_running_server(args.host, args.port)
            if existing is not None:
                print(
                    f"检测到已有服务运行: http://{args.host}:{args.port} "
                    f"(pid={existing.get('pid', '?')})"
                )
                print("为保证单实例，本次不再重复启动。")
                return
        raise


if __name__ == "__main__":
    main()
