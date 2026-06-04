# 通用拓扑编辑器（当前目录启动）

## 启动方式
在 `data` 目录执行：

```bash
python web_topology_editor.py --host 127.0.0.1 --port 8510
```

或使用 PowerShell：

```powershell
.\restart_server.ps1
```

## 说明
- 编辑器默认以当前目录作为工作区根目录。
- 如果未传 `--edges`，会自动从当前目录或子案例目录（如 `ph`、`sh`）中选择可用的 `mesh/edges*.csv`。
- 页面左侧“案例目录”下拉框可切换 `ph`、`sh` 等案例进行通用编辑。
- 保存路径支持相对工作区路径，例如：`ph/mesh/edges_new.csv`、`sh/mesh/edges_new.csv`。

## 停止服务

```powershell
.\stop_server.ps1
```
