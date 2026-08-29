import importlib.util
import tempfile
import unittest
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parent / "web_topology_editor.py"
_SPEC = importlib.util.spec_from_file_location("web_topology_editor_mod", _MODULE_PATH)
_MOD = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_MOD)
resolve_graph_case_dir = _MOD.resolve_graph_case_dir
detect_default_data_root = _MOD.detect_default_data_root
sanitize_layout_name = _MOD.sanitize_layout_name
save_graph_layout = _MOD.save_graph_layout
list_graph_layouts = _MOD.list_graph_layouts
load_graph_layout = _MOD.load_graph_layout


def _write_case(root: Path, name: str) -> Path:
    case_dir = root / name
    mesh = case_dir / "mesh"
    mesh.mkdir(parents=True)
    (mesh / "edges.csv").write_text("source,target\nA,B\n", encoding="utf-8")
    return case_dir


class ResolveGraphCaseDirTest(unittest.TestCase):
    def test_resolves_case_name_under_external_data_root(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw) / "repo"
            data = Path(raw) / "data"
            repo.mkdir()
            data.mkdir()
            _write_case(data, "dayudu")
            found = resolve_graph_case_dir(repo, data, "dayudu")
            self.assertEqual(found, (data / "dayudu").resolve())

    def test_resolves_legacy_relative_data_prefix(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw) / "repo"
            data = Path(raw) / "data"
            repo.mkdir()
            data.mkdir()
            _write_case(data, "ph")
            found = resolve_graph_case_dir(repo, data, "../data/ph")
            self.assertEqual(found, (data / "ph").resolve())


class DetectDefaultDataRootTest(unittest.TestCase):
    def test_prefers_sibling_ocismilpnet_data(self):
        with tempfile.TemporaryDirectory() as raw:
            parent = Path(raw)
            repo = parent / "OCIS-GUI-master"
            sibling = parent / "ocismilpnet-mac-win" / "data"
            repo_data = repo / "data"
            repo.mkdir()
            _write_case(sibling, "dayudu")
            _write_case(repo_data, "ph")
            found = detect_default_data_root(repo, repo)
            self.assertEqual(found, sibling.resolve())


class GraphLayoutStoreTest(unittest.TestCase):
    def test_sanitize_rejects_empty_and_path_chars(self):
        self.assertEqual(sanitize_layout_name("  布局 A  "), "布局 A")
        with self.assertRaises(ValueError):
            sanitize_layout_name("  ")
        self.assertEqual(sanitize_layout_name("a/b"), "ab")

    def test_save_list_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as raw:
            case_dir = _write_case(Path(raw), "demo")
            saved = save_graph_layout(
                case_dir,
                {"name": "主渠", "positions": {"闸1": {"x": 1.5, "y": -0.25}}, "camera": {"x": 0, "y": 0, "zoom": 2}},
            )
            self.assertTrue(saved["ok"])
            listed = list_graph_layouts(case_dir)
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["name"], "主渠")
            loaded = load_graph_layout(case_dir, "主渠")
            self.assertEqual(loaded["positions"]["闸1"]["x"], 1.5)
            self.assertEqual(loaded["camera"]["zoom"], 2)


if __name__ == "__main__":
    unittest.main()
