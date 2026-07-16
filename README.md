# OCIS-GUI

OCIS-GUI is a local visualization and editing workspace for OCIS-related canal and gate datasets.  
The repository currently focuses on two browser tools:

- `gate_curve_map`: gate map, water level, and flow chart viewer
- `web_topology_editor`: topology and edges editing tool

The project is designed to run against local case data under the repository `data/` directory.

## Repository layout

```text
OCIS-GUI/
|- data/                     Case data directories
|- gate_curve_map/           Gate map and chart viewer
|- web_topology_editor/      Topology editor
|- vendor/                   Frontend vendor assets
|- ui-main/                  Additional UI workspace assets
```

## Main features

### 1. Gate curve map

The gate curve map page provides:

- gate point visualization on a local 2D map
- channel line rendering from mesh and edges data
- water level charts
- gate flow charts
- standalone full-case chart pages opened in a new tab
- refresh support for full-case gate flow charts

Key files:

- `gate_curve_map/gate_curve_map.html`
- `gate_curve_map/standalone_charts.html`
- `gate_curve_map/gate_curve_map_server.py`

### 2. Topology editor

The topology editor is used to inspect and edit graph-like case files and edge relationships.

Key file:

- `web_topology_editor/web_topology_editor.py`

There is also an existing module-specific note at:

- `web_topology_editor/README_topology_editor.md`

## Requirements

- Python 3.9 or newer recommended
- A modern browser such as Chrome or Edge
- Local case data stored under `data/`

No separate database or backend service is required for the gate map viewer.  
It is served by a lightweight local Python HTTP server.

## Quick start

### Start the gate curve map viewer

From the repository root:

```powershell
python gate_curve_map/gate_curve_map_server.py
```

Default address:

```text
http://127.0.0.1:8610/gate_curve_map/gate_curve_map.html
```

Optional host and port:

```powershell
python gate_curve_map/gate_curve_map_server.py --host 127.0.0.1 --port 8610
```

### Start the topology editor

From the repository root:

```powershell
python web_topology_editor/web_topology_editor.py --host 127.0.0.1 --port 8510
```

If you prefer the helper script:

```powershell
.\web_topology_editor\restart_server.ps1
```

## Data conventions

Case data is expected under:

```text
data/<case-name>/
```

Typical subfolders and files include:

```text
data/<case-name>/
|- mesh/
|  |- input.txt
|  |- neighborId.txt
|  |- gates_mesh.csv
|  |- edges.csv
|  |- Gates.ini
|- input/
|  |- input.json
|  |- stage_obs_*.csv
|  |- action_*.csv
|- output/
|  |- channel_Gates_Stastic_h1.csv
|  |- channel_Gates_Stastic.csv
|  |- action.csv
|  |- Q.csv
```

## Path behavior in the gate curve map page

The gate curve map page now follows these rules:

- configured paths are used as-is
- missing configured files are reported beside the corresponding input field
- the page continues loading even if some files are missing
- missing datasets only leave the related chart or map layer empty
- the page does not silently switch to a different configured file path

This is useful when testing cases with incomplete datasets.

## Common workflow

1. Start `gate_curve_map_server.py`
2. Open the gate curve map page in the browser
3. Set the case root, for example `data/sj-huilin-2024` or `../data/sj-huilin-2024`
4. Adjust file paths in the left panel if needed
5. Click `重新加载`
6. Open `全部图表(新标签)` for full-case chart inspection
7. Use `刷新数据` in the standalone full-case flow page after backend files are updated

## Notes

- The gate curve viewer serves text-like files as UTF-8 and handles common GBK/GB18030 encoded files.
- The repository may contain large local data directories that are environment-specific.
- Some subdirectories such as `ui-main/` include their own internal documentation and are not required for the basic gate map workflow.

## Current default local URLs

- Gate curve map: `http://127.0.0.1:8610/gate_curve_map/gate_curve_map.html`
- Topology editor: `http://127.0.0.1:8510/`

