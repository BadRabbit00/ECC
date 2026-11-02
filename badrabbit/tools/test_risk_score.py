"""Tests for risk_score.py. Run from badrabbit/tools: python3 -m unittest test_risk_score"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import risk_score as rs

HERE = Path(__file__).resolve().parent
WHY = 'why = { C = "c", I = "i", A = "a", R = "r" }'


def proc(pid, c, i, a, r, uses, scope="one", exp=5, access="rw", extra=""):
    u = ", ".join(f'{{ data = "{d}", access = "{access}"{extra} }}' for d in uses)
    return (f'[[process]]\nid = "{pid}"\nname = "proc {pid}"\nscope = "{scope}"\n'
            f'C = {c}\nI = {i}\nA = {a}\nR = {r}\nexposure = {exp}\nexposure_why = "e"\n{WHY}\nuses = [{u}]\n')


def data(did, c, i, a, r, scope="one", exp=5, kind="data"):
    return (f'[[data]]\nid = "{did}"\nname = "data {did}"\nkind = "{kind}"\nscope = "{scope}"\n'
            f'C = {c}\nI = {i}\nA = {a}\nR = {r}\nexposure = {exp}\nexposure_why = "e"\n{WHY}\n')


class RiskScore(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def run_on(self, text, *extra):
        p = self.dir / "RISK.toml"
        p.write_text('[project]\nname = "t"\n' + text, encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = rs.main([str(p), *extra])
        return rc, out.getvalue(), err.getvalue()

    def assets(self):
        return {a["id"]: a for a in json.loads((self.dir / "RISK.json").read_text())["assets"]}

    def test_formula_examples_from_the_spec(self):
        # C8 I6 A4 R5 on several processes → (8 + 0.1×15) × 1.1 = 10.45 → capped at 10
        # C8 only, one process → 8
        rc, _, err = self.run_on(proc("P-01", 0, 0, 0, 0, ["D-01", "D-02"]) +
                                 data("D-01", 8, 6, 4, 5, scope="several", exp=7) + data("D-02", 8, 0, 0, 0, exp=5))
        self.assertEqual(rc, 0, err)
        a = self.assets()
        self.assertEqual(a["D-01"]["magnitude"], 10.0)
        self.assertEqual(a["D-01"]["risk"], 7.0)
        self.assertEqual(a["D-01"]["level"], "high")
        self.assertEqual(a["D-02"]["magnitude"], 8.0)
        self.assertEqual(a["D-02"]["risk"], 4.0)
        self.assertEqual(a["D-02"]["level"], "medium")

    def test_bonus_and_scope_without_cap(self):
        # max 5, rest 3+2+0 → 5.5 × 1.2 = 6.6
        rc, _, err = self.run_on(proc("P-01", 0, 0, 0, 0, ["D-01"]) + data("D-01", 5, 3, 2, 0, scope="all", exp=10))
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.assets()["D-01"]["magnitude"], 6.6)
        self.assertEqual(self.assets()["D-01"]["risk"], 6.6)

    def test_inheritance_down_and_up(self):
        # process needs A9 and I7 → data gets them; data has C8 R6 → process gets them
        rc, _, err = self.run_on(proc("P-01", 1, 7, 9, 0, ["D-01"]) + data("D-01", 8, 2, 3, 6))
        self.assertEqual(rc, 0, err)
        a = self.assets()
        self.assertEqual(a["D-01"]["final"], {"C": 8, "I": 7, "A": 9, "R": 6})
        self.assertEqual(a["P-01"]["final"], {"C": 8, "I": 7, "A": 9, "R": 6})
        self.assertEqual(a["D-01"]["given"]["A"], 3)
        self.assertTrue(any("A 3 → 9 from P-01" in r for r in a["D-01"]["raised"]))
        md = (self.dir / "RISK.md").read_text()
        self.assertIn("9↑", md)

    def test_inheritance_chains_through_shared_data(self):
        # P-01 (A9) → D-01; D-01 has R8 → P-02 gets R8 too
        rc, _, err = self.run_on(proc("P-01", 0, 0, 9, 0, ["D-01"]) + proc("P-02", 0, 0, 0, 0, ["D-01"]) +
                                 data("D-01", 0, 0, 0, 8))
        self.assertEqual(rc, 0, err)
        a = self.assets()
        self.assertEqual(a["D-01"]["final"]["A"], 9)
        self.assertEqual(a["P-02"]["final"]["R"], 8)
        self.assertEqual(a["P-02"]["final"]["A"], 0)   # A flows down only

    def test_read_only_use_passes_A_but_not_I(self):
        rc, _, err = self.run_on(proc("P-01", 0, 9, 8, 0, ["D-01"], access="r") + data("D-01", 0, 1, 1, 0))
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.assets()["D-01"]["final"], {"C": 0, "I": 1, "A": 8, "R": 0})

    def test_need_overrides_inherited_values(self):
        rc, _, err = self.run_on(proc("P-01", 0, 9, 9, 0, ["D-01"], extra=", need = { A = 3 }") +
                                 data("D-01", 0, 0, 0, 0))
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.assets()["D-01"]["final"], {"C": 0, "I": 9, "A": 3, "R": 0})

    def test_secret_does_not_raise_process_C_or_R(self):
        rc, _, err = self.run_on(proc("P-01", 2, 0, 0, 1, ["D-01"], access="r") + data("D-01", 10, 0, 0, 9, kind="secret"))
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.assets()["P-01"]["final"]["C"], 2)
        self.assertEqual(self.assets()["P-01"]["final"]["R"], 1)

    def test_bad_access_and_need_rejected(self):
        rc, _, err = self.run_on(proc("P-01", 0, 0, 0, 0, ["D-01"], access="x", extra=", need = { C = 3 }") +
                                 data("D-01", 0, 0, 0, 0), "--check")
        self.assertEqual(rc, 1)
        self.assertIn("access for D-01 must be r, w or rw", err)
        self.assertIn("need for D-01 must be", err)

    def test_validation_errors(self):
        bad = (proc("P-1", 0, 11, 0, 0, ["D-09"]) + data("D-01", 0, 0, 0, 0, scope="huge")
               .replace('why = { C = "c", I = "i", A = "a", R = "r" }', 'why = { C = "c" }'))
        rc, _, err = self.run_on(bad, "--check")
        self.assertEqual(rc, 1)
        for needle in ["id must look like P-01", "I must be an integer 0–10", "unknown data asset 'D-09'",
                       "scope must be one of", "why.I is empty", "D-01: no process uses it"]:
            self.assertIn(needle, err)

    def test_check_writes_nothing(self):
        rc, out, _ = self.run_on(proc("P-01", 1, 1, 1, 1, ["D-01"]) + data("D-01", 1, 1, 1, 1), "--check")
        self.assertEqual(rc, 0)
        self.assertIn("2 assets ok", out)
        self.assertFalse((self.dir / "RISK.md").exists())

    def test_levels_and_controls_rendered(self):
        text = (proc("P-01", 0, 0, 0, 0, ["D-01"], exp=10) + data("D-01", 9, 9, 9, 9, scope="all", exp=10) +
                '[controls]\ncritical = ["encrypt at rest"]\n')
        rc, _, err = self.run_on(text)
        self.assertEqual(rc, 0, err)
        md = (self.dir / "RISK.md").read_text()
        self.assertIn("| critical | 2 |", md)
        self.assertIn("encrypt at rest", md)
        self.assertIn("flowchart LR", md)
        self.assertIn("P01 -- rw --> D01", md)

    def test_template_parses(self):
        tpl = HERE.parent / "templates" / "RISK.toml"
        p = self.dir / "RISK.toml"
        p.write_text(tpl.read_text(encoding="utf-8"), encoding="utf-8")
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            rc = rs.main([str(p), "--check"])
        self.assertEqual(rc, 0, err.getvalue())


if __name__ == "__main__":
    unittest.main()
