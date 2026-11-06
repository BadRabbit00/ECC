"""Tests for validate.py. Run: python3 -I -B -m unittest discover -s tools -p test_*.py"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import validate

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

COPIED = (
    "agents", "rules", "skills", "commands", "core", "output-styles", "templates", "hooks", "tools",
    "agent-models.json", "settings.fragment.json",
)

GOOD_AGENT = """---
name: demo-agent
description: Reviews demo code when the orchestrator asks.
tools: Read, Grep
disallowedTools: Agent, Skill, mcp__*
omitClaudeMd: true
maxTurns: 20
model: sonnet
effort: medium
---

# Demo

## Examples

### R-DEMO-ONE — demo rule

Bad:
```python
x = eval(s)
```
Why: code injection.

Good:
```python
x = int(s)
```

## Output

```text
STATUS: done
```
"""

GOOD_RULE = """---
paths:
  - "**/*.py"
---

# Demo rules

### R-DEMO-TWO — demo

Bad:
```python
print(x)
```
Why: no structure.

Good:
```python
log.info("x", x=x)
```
"""


class ValidateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "br"
        self.root.mkdir()
        # Explicit allowlist (mirrors the payload.nix fileset): copying the repo root would follow
        # .direnv symlinks into /nix/store and fail to clean up read-only files.
        for name in COPIED:
            src = REPO / name
            if src.is_dir():
                shutil.copytree(src, self.root / name, symlinks=True, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy2(src, self.root / name)
        models = json.loads((self.root / "agent-models.json").read_text())
        models["agents"]["demo-agent"] = {"model": "claude-sonnet-5-5", "effort": "medium"}
        (self.root / "agent-models.json").write_text(json.dumps(models))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    def run_validator(self) -> list[str]:
        return validate.Validator(self.root).run()

    def write_agent(self, text: str) -> None:
        (self.root / "agents" / "demo-agent.md").write_text(text)

    def test_shipped_tree_is_clean(self) -> None:
        models = json.loads((self.root / "agent-models.json").read_text())
        del models["agents"]["demo-agent"]
        (self.root / "agent-models.json").write_text(json.dumps(models))
        self.assertEqual(self.run_validator(), [])

    def test_good_agent_and_rule_pass(self) -> None:
        self.write_agent(GOOD_AGENT)
        (self.root / "rules" / "demo.md").write_text(GOOD_RULE)
        self.assertEqual(self.run_validator(), [])

    def test_agent_without_omit_claude_md_fails(self) -> None:
        self.write_agent(GOOD_AGENT.replace("omitClaudeMd: true\n", ""))
        self.assertTrue(any("omitClaudeMd" in e for e in self.run_validator()))

    def test_agent_must_disallow_agent_tool(self) -> None:
        self.write_agent(GOOD_AGENT.replace("Agent, Skill, mcp__*", "Skill, mcp__*"))
        self.assertTrue(any("disallowedTools must include Agent" in e for e in self.run_validator()))

    def test_proactive_description_fails(self) -> None:
        self.write_agent(GOOD_AGENT.replace("Reviews demo code", "Use PROACTIVELY to review demo code"))
        self.assertTrue(any("auto-invoke" in e for e in self.run_validator()))

    def test_agent_without_examples_fails(self) -> None:
        self.write_agent(GOOD_AGENT.replace("Bad:", "Wrong:"))
        self.assertTrue(any("no example pair" in e for e in self.run_validator()))

    def test_rule_without_paths_fails(self) -> None:
        (self.root / "rules" / "demo.md").write_text(GOOD_RULE.replace('paths:\n  - "**/*.py"\n', "x: 1\n"))
        self.assertTrue(any("paths" in e for e in self.run_validator()))

    def test_duplicate_rule_id_fails(self) -> None:
        self.write_agent(GOOD_AGENT)
        (self.root / "rules" / "demo.md").write_text(GOOD_RULE.replace("R-DEMO-TWO", "R-DEMO-ONE"))
        self.assertTrue(any("duplicate rule id R-DEMO-ONE" in e for e in self.run_validator()))

    def test_agent_missing_from_models_fails(self) -> None:
        text = GOOD_AGENT.replace("name: demo-agent", "name: other-agent")
        (self.root / "agents" / "other-agent.md").write_text(text)
        self.assertTrue(any("not listed in agent-models.json" in e for e in self.run_validator()))

    def test_crlf_is_reported(self) -> None:
        (self.root / "agents" / "demo-agent.md").write_bytes(GOOD_AGENT.replace("\n", "\r\n").encode())
        self.assertTrue(any("CRLF" in e for e in self.run_validator()))

    def test_spawn_depth_setting_required(self) -> None:
        (self.root / "settings.fragment.json").write_text('{"env": {}}')
        self.assertTrue(any("SPAWN_DEPTH" in e for e in self.run_validator()))

    def test_hook_without_entry_fails(self) -> None:
        h = self.root / "hooks" / "hooks.json"
        data = json.loads(h.read_text())
        data["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = "@BR_HOOK@ guard_missing"
        h.write_text(json.dumps(data))
        errs = self.run_validator()
        self.assertTrue(any("guard_missing.py not found" in e for e in errs))
        self.assertTrue(any("guard_bash.py: entry point is not registered" in e for e in errs))

    def test_hook_raw_command_fails(self) -> None:
        h = self.root / "hooks" / "hooks.json"
        data = json.loads(h.read_text())
        data["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = "python3 hooks/guard_bash.py"
        h.write_text(json.dumps(data))
        self.assertTrue(any("@BR_HOOK@" in e for e in self.run_validator()))

    def test_duplicate_hook_id_fails(self) -> None:
        h = self.root / "hooks" / "hooks.json"
        data = json.loads(h.read_text())
        data["hooks"]["PreToolUse"][1]["id"] = data["hooks"]["PreToolUse"][0]["id"]
        h.write_text(json.dumps(data))
        self.assertTrue(any("duplicate hook id" in e for e in self.run_validator()))

    def test_style_marker_leak_fails(self) -> None:
        self.write_agent(GOOD_AGENT.replace("# Demo", "# Demo\nBR-ORCHESTRATOR-STYLE-ACTIVE"))
        self.assertTrue(any("leaks outside output-styles" in e for e in self.run_validator()))

    def test_style_needs_keep_coding_instructions(self) -> None:
        p = self.root / "output-styles" / "orchestrator.md"
        p.write_text(p.read_text().replace("keep-coding-instructions: true\n", ""))
        self.assertTrue(any("keep-coding-instructions" in e for e in self.run_validator()))

    def test_blank_slides_out_of_sync_fails(self) -> None:
        p = self.root / "templates" / "slides.blank.html"
        p.write_text(p.read_text().replace("--accent: #6A3FD6", "--accent: #000000"))
        self.assertTrue(any("out of sync" in e for e in self.run_validator()))

    def test_plan_template_fields_required(self) -> None:
        p = self.root / "templates" / "PLAN.md"
        p.write_text(p.read_text().replace("**Tests (test-writer):**", "**Test files:**"))
        self.assertTrue(any("Tests (test-writer)" in e for e in self.run_validator()))

    def test_missing_preloaded_skill_fails(self) -> None:
        self.write_agent(GOOD_AGENT.replace("effort: medium\n", "effort: medium\nskills: [no-such-skill]\n"))
        self.assertTrue(any("no-such-skill" in e for e in self.run_validator()))

    def test_command_without_description_fails(self) -> None:
        (self.root / "commands").mkdir(exist_ok=True)
        (self.root / "commands" / "demo.md").write_text("---\nargument-hint: x\n---\n# demo\n")
        self.assertTrue(any("command needs frontmatter" in e for e in self.run_validator()))

    # -- exemptions from tools/validate.json

    def patch_cfg(self, **extra: list[str]) -> None:
        path = self.root / "tools" / "validate.json"
        cfg = json.loads(path.read_text())
        for key, names in extra.items():
            cfg[key] = cfg.get(key, []) + names
        path.write_text(json.dumps(cfg))

    def test_build_isolated_agent_skips_isolation_fields(self) -> None:
        bare = GOOD_AGENT.replace("omitClaudeMd: true\n", "").replace("maxTurns: 20\n", "")
        bare = bare.replace("disallowedTools: Agent, Skill, mcp__*\n", "").replace("## Output", "## Result")
        self.write_agent(bare)
        self.assertTrue(any("omitClaudeMd" in e for e in self.run_validator()))
        self.patch_cfg(buildIsolated=["demo-agent"])
        self.assertEqual(self.run_validator(), [])

    def test_build_isolated_agent_still_checks_description_words(self) -> None:
        self.patch_cfg(buildIsolated=["demo-agent"])
        # The build strips this sentence, so it is allowed ...
        self.write_agent(GOOD_AGENT.replace("when the orchestrator asks.", "when asked. Use PROACTIVELY for demos."))
        self.assertEqual(self.run_validator(), [])
        # ... but a forbidden word elsewhere survives the build and must fail.
        self.write_agent(GOOD_AGENT.replace("when the orchestrator asks.", "and runs automatically."))
        self.assertTrue(any("auto-invoke" in e for e in self.run_validator()))

    def test_skill_description_needs_use_when_unless_exempt(self) -> None:
        d = self.root / "skills" / "demo-skill"
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: demo-skill\ndescription: Demo things.\n---\n\n# Demo\n")
        self.assertTrue(any("must start with 'Use when'" in e for e in self.run_validator()))
        self.patch_cfg(useWhenExempt=["demo-skill"])
        self.assertEqual([e for e in self.run_validator() if "demo-skill" in e], [])

    def test_agent_without_examples_passes_when_exempt(self) -> None:
        self.write_agent(GOOD_AGENT.replace("Bad:", "Wrong:"))
        self.assertTrue(any("no example pair" in e for e in self.run_validator()))
        self.patch_cfg(examplesExempt=["agent:demo-agent"])
        self.assertEqual(self.run_validator(), [])

    def test_stale_exemptions_fail(self) -> None:
        self.write_agent(GOOD_AGENT)
        self.patch_cfg(buildIsolated=["ghost"], examplesExempt=["agent:ghost2"], useWhenExempt=["ghost3"])
        errs = self.run_validator()
        for needle in ("buildIsolated: agent 'ghost'", "examplesExempt: agent 'ghost2'", "useWhenExempt: skill 'ghost3'"):
            self.assertTrue(any(needle in e for e in errs), needle)


if __name__ == "__main__":
    unittest.main()
