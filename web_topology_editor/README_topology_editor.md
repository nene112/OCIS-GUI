# 通用拓扑编辑器

## 启动

在仓库根目录：

```bash
python web_topology_editor/web_topology_editor.py --host 127.0.0.1 --port 8510
```

未传 `--data` 时，优先使用旁边的 `ocismilpnet-mac-win/data`（与当前测试一致），否则用仓库内 `data/`。也可显式指定：

```bash
python web_topology_editor/web_topology_editor.py --host 127.0.0.1 --port 8510 --data ../ocismilpnet-mac-win/data
```

Windows 可用：

```powershell
.\web_topology_editor\restart_server.ps1
```

打开：

- 工作台：http://127.0.0.1:8510/
- GraphGPU 拓扑：http://127.0.0.1:8510/topo
- 经典拓扑：http://127.0.0.1:8510/classic

## GraphGPU 拓扑

- 左上角默认显示 `OcisMILPNet`，点击后选择 data 下案例，标题改为案例名并加载该图。
- 间接边生成渠段节点；`target=-1` 视为末端，不再生成连到 `-1` 的渠段。
- 拖动渠段时 target/斗口跟随，对应 source 保持不动。
- `type=0` 与 `type=4` 节点名称常显、加粗，字号随缩放与节点大小一致。

## 说明

- 编辑器默认以仓库根目录作为工作区。
- 如果未传 `--edges`，会从 `--data` 或子案例目录中选择可用的 `mesh/edges*.csv`。
- 保存路径支持相对工作区路径。

## 停止服务

```powershell
.\web_topology_editor\stop_server.ps1
```
