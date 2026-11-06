import tempfile
import unittest
from pathlib import Path

from helpers import call, denied, reason

PLAN = """# Plan

### T1 — order status filter
- **Status:** green
- **Writes (exclusive):** `src/orders/app/services/order_service.py`, `src/orders/app/repositories/order_repo.py`
- **Tests (test-writer):** `src/orders/test/services/test_order_service.py`

### T2 — order export
- **Status:** red
- **Writes (exclusive):** `src/orders/app/services/export_service.py`
- **Tests (test-writer):** `src/orders/test/services/test_export_*.py`

### T3 — notifications
- **Status:** todo
- **Writes (exclusive):** `src/notify/**`
- **Tests (test-writer):** `src/notify/test/**`
"""


def project(plan: str | None = PLAN) -> Path:
    d = Path(tempfile.mkdtemp(prefix="brhook-proj-"))
    if plan is not None:
        (d / ".plan").mkdir()
        (d / ".plan" / "PLAN.md").write_text(plan)
    return d


def write(path, agent=None, root=None, tool="Write"):
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    return call("guard_write", tool, {key: str(path), "content": "x"}, agent=agent, cwd=root, project=root)


class TestBoundaryWithoutPlan(unittest.TestCase):
    def setUp(self):
        self.root = project(None)

    def test_coder_never_writes_tests(self):
        for agent in ["coder", "refactorer", "build-fixer"]:
            for p in ["test/test_a.py", "src/api/test/conftest.py", "web/test/App.test.tsx"]:
                with self.subTest(agent=agent, p=p):
                    self.assertTrue(denied(write(self.root / p, agent, self.root)))

    def test_native_test_locations_are_tests(self):
        for p in ["crates/core/tests/api.rs", "app/integration_test/login_test.dart", "internal/order/order_service_test.go",
                  "web/src/OrderTable.test.tsx", "web/src/__tests__/x.ts", "pkg/test_utils_x.py", "src/orders/app/conftest.py",
                  "web/e2e/login.spec.ts", "internal/parse/testdata/in.json"]:
            with self.subTest(p=p):
                self.assertTrue(denied(write(self.root / p, "coder", self.root)), p)
                self.assertFalse(denied(write(self.root / p, "test-writer", self.root)), p)

    def test_coder_writes_code(self):
        self.assertFalse(denied(write(self.root / "src/api/app/main.py", "coder", self.root)))
        self.assertFalse(denied(write(self.root / "src/api/testing_utils.py", "coder", self.root)))

    def test_test_writer_only_tests(self):
        self.assertFalse(denied(write(self.root / "src/api/test/test_x.py", "test-writer", self.root)))
        self.assertTrue(denied(write(self.root / "src/api/app/x.py", "test-writer", self.root)))

    def test_main_thread_free_without_plan(self):
        self.assertFalse(denied(write(self.root / "src/app.py", None, self.root)))

    def test_subagent_outside_project(self):
        self.assertTrue(denied(write("/etc/hosts", "coder", self.root)))
        self.assertTrue(denied(write(Path.home() / ".claude/settings.json", "coder", self.root)))
        self.assertFalse(denied(write("/tmp/scratch.txt", "coder", self.root)))

    def test_quality_configs_protected(self):
        for p in [".eslintrc.json", "eslint.config.js", "ruff.toml", ".golangci.yml", "web/biome.json",
                  "mypy.ini", ".coveragerc", "rustfmt.toml", ".pre-commit-config.yaml"]:
            for agent in ["coder", "build-fixer", "test-writer"]:
                with self.subTest(p=p, agent=agent):
                    self.assertTrue(denied(write(self.root / p, agent, self.root)))
        self.assertFalse(denied(write(self.root / "ruff.toml", None, self.root)))      # the human session may
        self.assertFalse(denied(write(self.root / "tsconfig.json", "coder", self.root)))

    def test_notebook(self):
        self.assertTrue(denied(write(self.root / "test/nb.ipynb", "coder", self.root, tool="NotebookEdit")))


class TestPlanScopes(unittest.TestCase):
    def setUp(self):
        self.root = project()

    def test_coder_limited_to_green_tasks(self):
        r = self.root
        self.assertFalse(denied(write(r / "src/orders/app/services/order_service.py", "coder", r)))
        self.assertFalse(denied(write(r / "src/orders/app/repositories/order_repo.py", "coder", r, tool="Edit")))
        res = write(r / "src/orders/app/services/export_service.py", "coder", r)   # T2 is red, not green
        self.assertTrue(denied(res))
        self.assertIn("T1", reason(res))
        self.assertTrue(denied(write(r / "src/notify/x.py", "coder", r)))          # T3 todo

    def test_test_writer_limited_to_red_tasks(self):
        r = self.root
        self.assertFalse(denied(write(r / "src/orders/test/services/test_export_csv.py", "test-writer", r)))
        self.assertTrue(denied(write(r / "src/orders/test/services/test_order_service.py", "test-writer", r)))

    def test_refactorer_without_refactor_task(self):
        res = write(self.root / "src/orders/app/services/order_service.py", "refactorer", self.root)
        self.assertTrue(denied(res))
        self.assertIn("No task", reason(res))

    def test_build_fixer_not_limited_by_plan(self):
        self.assertFalse(denied(write(self.root / "flake.nix", "build-fixer", self.root)))

    def test_main_thread_docs_and_plan_only(self):
        r = self.root
        for p in ["docs/GENERAL.md", "docs/slides/arch.html", ".plan/PLAN.md", "README.md", "CLAUDE.md"]:
            with self.subTest(p=p):
                self.assertFalse(denied(write(r / p, None, r)))
        res = write(r / "src/orders/app/services/order_service.py", None, r)
        self.assertTrue(denied(res))
        self.assertIn("/output-style default", reason(res))

    def test_presenter_scope(self):
        self.assertFalse(denied(write(self.root / "docs/slides/a.html", "presenter", self.root)))
        self.assertTrue(denied(write(self.root / "docs/API.md", "presenter", self.root)))

    def test_ui_verifier_writes_only_tmp(self):
        self.assertTrue(denied(write(self.root / "src/web/check.mjs", "ui-verifier", self.root)))
        self.assertFalse(denied(write("/tmp/ui-verifier/T7/check.mjs", "ui-verifier", self.root)))

    def test_relative_path(self):
        self.assertTrue(denied(write("src/notify/x.py", "coder", self.root)))


if __name__ == "__main__":
    unittest.main()
