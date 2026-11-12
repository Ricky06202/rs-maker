"""Crash breadcrumbs must survive a failed CAD process without leaking files."""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from freecad.RSMaker import crash_diagnostics as diag


class CrashDiagnosticsTests(unittest.TestCase):
    def test_checkpoints_persist_without_private_paths_or_text(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ,{"XDG_CACHE_HOME":temp}):
                cfg=SimpleNamespace(quality_mode="high",
                                    compute_backend="cpu",
                                    lamp_mode=True,width=180,height=225,
                                    svg_path="/home/user/private-cat.jpg",
                                    text="PRIVATE NAME")
                log=diag.start_generation(cfg)
                self.assertTrue(Path(log).is_file())
                diag.checkpoint("worker:vector-tracing",front_rings=16)
                content=Path(log).read_text()
                self.assertIn("generate:start",content)
                self.assertIn("worker:vector-tracing",content)
                self.assertIn("quality=high",content)
                self.assertNotIn("private-cat",content)
                self.assertNotIn("PRIVATE NAME",content)

    def test_logging_errors_do_not_break_geometry(self):
        with patch.object(diag,"log_path",side_effect=OSError("read-only")):
            self.assertEqual(diag.checkpoint("cad:face-attempt"),"")


if __name__=="__main__":
    unittest.main()
