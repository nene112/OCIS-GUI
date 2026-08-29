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


if __name__ == "__main__":
    unittest.main()
