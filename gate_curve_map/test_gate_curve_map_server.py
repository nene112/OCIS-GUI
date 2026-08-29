import unittest
from pathlib import Path

from gate_curve_map_server import DEFAULT_DATA_ROOT, GateCurveHandler


class GateCurveHandlerTest(unittest.TestCase):
    def test_only_configured_data_root_is_served_as_an_absolute_path(self):
        handler = object.__new__(GateCurveHandler)
        self.assertEqual(handler.translate_path(str(DEFAULT_DATA_ROOT / "mesh/input.txt")), str(DEFAULT_DATA_ROOT / "mesh/input.txt"))
        self.assertNotEqual(handler.translate_path(str(DEFAULT_DATA_ROOT / "../secret.txt")), str((DEFAULT_DATA_ROOT / "../secret.txt").resolve()))


if __name__ == "__main__":
    unittest.main()
