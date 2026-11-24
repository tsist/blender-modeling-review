"""Offline unit tests for commercial_qa_scorecard.py grading and gate logic."""
from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCORECARD_SCRIPT = ROOT / "scripts" / "commercial_qa_scorecard.py"
MESH_QA_SCRIPT = ROOT / "scripts" / "mesh_qa.py"


class ScorecardContractTests(unittest.TestCase):
    def test_scripts_parse_cleanly(self):
        for p in (SCORECARD_SCRIPT, MESH_QA_SCRIPT):
            self.assertTrue(p.is_file(), f"Missing {p}")
            ast.parse(p.read_text(encoding="utf-8"), filename=p.name)

    def test_score_subcommand_l2_pass_g1_veto_and_white_rescale(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            probe_pass = {
                "schema_version": "1.0",
                "stage": "final",
                "target_level": "L2",
                "blend_file": "sample.blend",
                "blend_sha256": "0" * 64,
                "blender_version": "5.3.0",
                "g1_gate_failures": [],
                "g2_gate_failures": [],
                "hard_gates_passed": True,
            }
            scores = {
                "task_id": "sample-l2-check",
                "target_level": "L2",
                "reviewer_role": "independent_readonly_subagent",
                "gradients": {
                    "G1_engineering": {"score": 15.0, "notes": "Clean cold reopen"},
                    "G2_structure_topology": {"score": 22.0, "notes": "Quad cage clean"},
                    "G3_reference_fidelity": {"score": 22.0, "notes": "Proportions verified"},
                    "G4_shading_continuity": {"score": 17.0, "notes": "Smooth highlights"},
                    "G5_delivery_polish": {"score": 13.0, "notes": "Calibrated PBR"},
                },
            }
            p_file = tmp / "probe.json"
            s_file = tmp / "scores.json"
            out_json = tmp / "scorecard.json"
            out_md = tmp / "scorecard.md"
            p_file.write_text(json.dumps(probe_pass), encoding="utf-8")
            s_file.write_text(json.dumps(scores), encoding="utf-8")

            r = subprocess.run(
                [sys.executable, "-B", str(SCORECARD_SCRIPT), "score",
                 "--probe", str(p_file), "--scores", str(s_file),
                 "--output", str(out_json), "--markdown", str(out_md)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            card = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertTrue(card["passed"])
            self.assertEqual(card["achieved_level"], "L2")
            self.assertEqual(card["total_score_100"], 89.0)
            self.assertTrue(out_md.is_file())

            # Inject a G1 hard gate failure -> automatic BLOCKED / passed=False
            probe_fail = dict(probe_pass, g1_gate_failures=["absolute_texture_path"], hard_gates_passed=False)
            p_file.write_text(json.dumps(probe_fail), encoding="utf-8")
            out_fail = tmp / "scorecard_fail.json"
            r2 = subprocess.run(
                [sys.executable, "-B", str(SCORECARD_SCRIPT), "score",
                 "--probe", str(p_file), "--scores", str(s_file),
                 "--output", str(out_fail)],
                capture_output=True, text=True, check=False,
            )
            self.assertIn(r2.returncode, (0, 2), r2.stderr)
            card2 = json.loads(out_fail.read_text(encoding="utf-8"))
            self.assertFalse(card2["passed"])
            self.assertEqual(card2["achieved_level"], "BLOCKED")

            # White-model stage rescales G1..G4 (85 pts) to 100
            probe_white = dict(probe_pass, stage="white")
            p_file.write_text(json.dumps(probe_white), encoding="utf-8")
            out_white = tmp / "scorecard_white.json"
            r3 = subprocess.run(
                [sys.executable, "-B", str(SCORECARD_SCRIPT), "score",
                 "--probe", str(p_file), "--scores", str(s_file),
                 "--output", str(out_white)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(r3.returncode, 0, r3.stderr)
            card3 = json.loads(out_white.read_text(encoding="utf-8"))
            self.assertTrue(card3["passed"])
            self.assertEqual(card3["applicable_max_points"], 85.0)
            self.assertAlmostEqual(card3["total_score_100"], round(76.0 / 85.0 * 100.0, 2), places=2)


if __name__ == "__main__":
    unittest.main()
