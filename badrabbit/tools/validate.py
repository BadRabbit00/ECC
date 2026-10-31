#!/usr/bin/env python3
"""Structural checks for badrabbit/ (BR-ECC).

Usage:
    python3 badrabbit/tools/validate.py badrabbit [--repo .]

--repo  repository root; when given, allowlisted fork files are checked to exist.

Exit code 0 = clean, 1 = violations (printed one per line).
Standard library only; runs inside the payload build.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FENCE = re.compile(r"^```", re.M)
RULE_HEADING = re.compile(r"^###\s+(R-[A-Z0-9]+(?:-[A-Z0-9]+)+)\b", re.M)
PAIR = re.compile(r"^Bad:\s*\n```[^\n]*\n.*?\n```.*?^Good:\s*\n```[^\n]*\n.*?\n```", re.M | re.S)


# ---------------------------------------------------------------- frontmatter

def split_frontmatter(text: str) -> tuple[dict[str, object], str] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    raw = text[4:end]
    body = text[end + 4:].lstrip("\n")
    return parse_yaml_subset(raw), body


def parse_yaml_subset(raw: str) -> dict[str, object]:
    """Parses the flat YAML we use: `key: value`, `key: [a, b]`, and `key:` + `  - item` lists.
    Lines starting with '#' are comments."""
    data: dict[str, object] = {}
    current_list: list[str] | None = None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith(("  - ", "- ")) and current_list is not None:
            current_list.append(unquote(line.split("- ", 1)[1].strip()))
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if value == "":
            current_list = []
            data[key] = current_list
            continue
        current_list = None
        if value.startswith("[") and value.endswith("]"):
            data[key] = [unquote(v.strip()) for v in value[1:-1].split(",") if v.strip()]
        elif value in ("true", "false"):
            data[key] = value == "true"
        elif re.fullmatch(r"-?\d+", value):
            data[key] = int(value)
        else:
            data[key] = unquote(value)
    return data


def unquote(v: str) -> str:
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


# ---------------------------------------------------------------- checks

class Validator:
    def __init__(self, root: Path, repo: Path | None) -> None:
        self.root = root
        self.repo = repo
        self.cfg = json.loads((root / "tools" / "validate.json").read_text(encoding="utf-8"))
        self.errors: list[str] = []
        self.rule_ids: dict[str, Path] = {}

    def err(self, path: Path, msg: str) -> None:
        self.errors.append(f"{path.relative_to(self.root.parent)}: {msg}")

    # -- helpers
    def lines(self, text: str) -> int:
        return text.count("\n") + 1

    def check_examples(self, path: Path, body: str, key: str) -> None:
        if key in self.cfg.get("examplesExempt", []):
            return
        if not PAIR.search(body):
            self.err(path, "no example pair (Bad: + code block, then Good: + code block)")
        for block in re.findall(r"^```([^\n]*)\n", body, re.M)[::2]:
            if not block.strip():
                self.err(path, "code block without a language tag")
                break

    def collect_rule_ids(self, path: Path, body: str) -> None:
        for rid in RULE_HEADING.findall(body):
            if rid in self.rule_ids:
                self.err(path, f"duplicate rule id {rid} (first in {self.rule_ids[rid].name})")
            else:
                self.rule_ids[rid] = path

    def check_encoding(self, path: Path, raw: bytes) -> None:
        if raw.startswith(b"\xef\xbb\xbf"):
            self.err(path, "UTF-8 BOM")
        if b"\r\n" in raw:
            self.err(path, "CRLF line endings")

    def read(self, path: Path) -> str:
        raw = path.read_bytes()
        self.check_encoding(path, raw)
        return raw.decode("utf-8")

    # -- sections
    def check_core(self) -> None:
        limits = self.cfg["limits"]
        for name, key in (("CLAUDE.md", "core"), ("subagent-contract.md", "contract")):
            p = self.root / "core" / name
            if not p.exists():
                self.err(p, "missing")
                continue
            n = self.lines(self.read(p))
            if n > limits[key]:
                self.err(p, f"{n} lines > limit {limits[key]}")

    def check_agents(self, models: dict[str, object]) -> list[str]:
        names = []
        for p in sorted((self.root / "agents").glob("*.md")):
            text = self.read(p)
            parsed = split_frontmatter(text)
            if parsed is None:
                self.err(p, "no YAML frontmatter")
                continue
            fm, body = parsed
            name = str(fm.get("name", ""))
            names.append(name)
            if name != p.stem:
                self.err(p, f"name '{name}' != file name '{p.stem}'")
            desc = str(fm.get("description", ""))
            if not desc:
                self.err(p, "description missing")
            for word in self.cfg["forbiddenDescriptionWords"]:
                if word in desc.lower():
                    self.err(p, f"description contains '{word}' (would make Claude auto-invoke)")
            if fm.get("omitClaudeMd") is not True:
                self.err(p, "omitClaudeMd: true is required")
            if not as_list(fm.get("tools")):
                self.err(p, "explicit tools allowlist is required")
            if "Agent" in as_list(fm.get("tools")):
                self.err(p, "tools must not include Agent")
            disallowed = as_list(fm.get("disallowedTools"))
            for t in self.cfg["requiredDisallowed"]:
                if t not in disallowed:
                    self.err(p, f"disallowedTools must include {t}")
            if not isinstance(fm.get("maxTurns"), int):
                self.err(p, "maxTurns (integer) is required")
            if str(fm.get("model", "")) not in self.cfg["allowedModels"]:
                self.err(p, f"model must be one of {self.cfg['allowedModels']}")
            if "effort" in fm and str(fm["effort"]) not in self.cfg["allowedEffort"]:
                self.err(p, f"effort must be one of {self.cfg['allowedEffort']}")
            n = self.lines(body)
            if n > self.cfg["limits"]["agent"]:
                self.err(p, f"body {n} lines > limit {self.cfg['limits']['agent']}")
            if "## Output" not in body:
                self.err(p, "missing '## Output' section")
            self.check_examples(p, body, f"agent:{name}")
            self.collect_rule_ids(p, body)
            if name not in models:
                self.err(p, "not listed in agent-models.json")
        return names

    def check_rules(self) -> None:
        for p in sorted((self.root / "rules").glob("*.md")):
            text = self.read(p)
            parsed = split_frontmatter(text)
            if parsed is None or not as_list(parsed[0].get("paths")):
                self.err(p, "path rule needs a non-empty 'paths:' list in frontmatter")
                continue
            body = parsed[1]
            n = self.lines(body)
            if n > self.cfg["limits"]["rule"]:
                self.err(p, f"{n} lines > limit {self.cfg['limits']['rule']}")
            self.check_examples(p, body, f"rule:{p.stem}")
            self.collect_rule_ids(p, body)

    def check_skills(self) -> None:
        for p in sorted((self.root / "skills").glob("*/SKILL.md")):
            parsed = split_frontmatter(self.read(p))
            if parsed is None:
                self.err(p, "no YAML frontmatter")
                continue
            fm, body = parsed
            if fm.get("name") != p.parent.name:
                self.err(p, f"name must equal directory '{p.parent.name}'")
            if not str(fm.get("description", "")).startswith("Use when"):
                self.err(p, "description must start with 'Use when'")
            self.collect_rule_ids(p, body)

    def check_output_styles(self) -> None:
        for p in sorted((self.root / "output-styles").glob("*.md")):
            text = self.read(p)
            parsed = split_frontmatter(text)
            if parsed is None or not parsed[0].get("name"):
                self.err(p, "output style needs frontmatter with name")
                continue
            fm, body = parsed
            if fm.get("keep-coding-instructions") is not True:
                self.err(p, "keep-coding-instructions: true is required")
            n = self.lines(body)
            if n > self.cfg["limits"]["outputStyle"]:
                self.err(p, f"body {n} lines > limit {self.cfg['limits']['outputStyle']}")
            if p.stem == "orchestrator" and self.cfg["styleMarker"] not in body:
                self.err(p, f"missing marker {self.cfg['styleMarker']}")
        marker = self.cfg["styleMarker"]
        for p in sorted(self.root.rglob("*")):
            if p.is_file() and p.suffix in {".md", ".html", ".json"} and p.parent.name != "output-styles" \
                    and p.parent.name != "tools" and marker in p.read_text(encoding="utf-8", errors="replace"):
                self.err(p, f"{marker} leaks outside output-styles/")

    def check_templates(self) -> None:
        t = self.root / "templates"
        slides, blank = t / "slides.html", t / "slides.blank.html"
        if slides.exists():
            full = self.read(slides)
            if full.count("<!-- SLIDES:BEGIN") != 1 or full.count("<!-- SLIDES:END -->") != 1:
                self.err(slides, "needs exactly one SLIDES:BEGIN … SLIDES:END block")
            elif not blank.exists():
                self.err(blank, "missing (generate it from slides.html)")
            else:
                expected = re.sub(r"<!-- SLIDES:BEGIN.*?<!-- SLIDES:END -->", "<!-- SLIDES -->", full, flags=re.S)
                if self.read(blank) != expected:
                    self.err(blank, "out of sync with slides.html (regenerate: block → <!-- SLIDES -->)")
        plan = t / "PLAN.md"
        if plan.exists():
            text = self.read(plan)
            if not re.search(r"^### T1 — ", text, re.M):
                self.err(plan, "needs a task card heading '### T1 — …' (hooks parse it)")
            for field in ("**Status:**", "**Writes (exclusive):**", "**Tests (test-writer):**"):
                if field not in text:
                    self.err(plan, f"task card field {field} missing (hooks parse it)")
        docs = self.root / "skills" / "project-docs" / "templates"
        if docs.parent.exists():
            for name in self.cfg["docTemplates"]:
                if not (docs / name).exists():
                    self.err(docs, f"template {name} missing")

    def check_json(self, agent_names: list[str], models: dict[str, object]) -> None:
        s = self.root / "settings.fragment.json"
        try:
            settings = json.loads(s.read_text(encoding="utf-8"))
            if settings.get("env", {}).get("CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH") != "1":
                self.err(s, "env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH must be \"1\"")
        except (OSError, json.JSONDecodeError) as e:
            self.err(s, f"invalid: {e}")
        allow = json.loads((self.root / "allowlist.json").read_text(encoding="utf-8"))
        m = self.root / "agent-models.json"
        for name in allow.get("agents", []):
            if name not in models:
                self.err(m, f"allowlisted agent '{name}' has no model")
        for name, spec in models.items():
            if name not in agent_names and name not in allow.get("agents", []):
                self.err(m, f"'{name}' is neither a br agent nor allowlisted")
            if not isinstance(spec, dict) or not str(spec.get("model", "")).startswith("claude-"):
                self.err(m, f"'{name}': model must be a full claude-* id")
            elif spec.get("effort") not in self.cfg["allowedEffort"]:
                self.err(m, f"'{name}': bad effort")
        if self.repo:
            for name in allow.get("agents", []):
                if not (self.repo / "agents" / f"{name}.md").exists():
                    self.err(self.root / "allowlist.json", f"agents/{name}.md not found in repo")
            for name in allow.get("skills", []) + allow.get("upstreamSkills", []):
                if not (self.repo / "skills" / name / "SKILL.md").exists():
                    self.err(self.root / "allowlist.json", f"skills/{name} not found in repo")
            for name in allow.get("commands", []):
                if not (self.repo / "commands" / f"{name}.md").exists():
                    self.err(self.root / "allowlist.json", f"commands/{name}.md not found in repo")

    def check_hooks(self) -> None:
        """hooks/hooks.json: unique br:* ids, descriptions, `@BR_HOOK@ <entry>` commands with existing entries."""
        hdir = self.root / "hooks"
        h = hdir / "hooks.json"
        if not h.exists():
            return
        try:
            data = json.loads(h.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            self.err(h, f"invalid: {e}")
            return
        seen: set[str] = set()
        used: set[str] = set()
        for event, entries in (data.get("hooks") or {}).items():
            if event not in self.cfg["hookEvents"]:
                self.err(h, f"unknown hook event {event}")
            for e in entries:
                hid = e.get("id", "")
                if not hid.startswith("br:"):
                    self.err(h, f"{event}: id must start with 'br:' ({hid or 'missing'})")
                if hid in seen:
                    self.err(h, f"duplicate hook id {hid}")
                seen.add(hid)
                if not e.get("description"):
                    self.err(h, f"{hid}: description required")
                for cmd in e.get("hooks", []):
                    m = re.fullmatch(r"@BR_HOOK@ ([a-z_]+)", cmd.get("command", ""))
                    if not m:
                        self.err(h, f"{hid}: command must be '@BR_HOOK@ <entry>'")
                        continue
                    used.add(m.group(1))
                    if not (hdir / f"{m.group(1)}.py").exists():
                        self.err(h, f"{hid}: hooks/{m.group(1)}.py not found")
                    if not isinstance(cmd.get("timeout"), int) or cmd["timeout"] > self.cfg["maxHookTimeout"]:
                        self.err(h, f"{hid}: timeout must be an int <= {self.cfg['maxHookTimeout']}")
        for py in sorted(hdir.glob("*.py")):
            if py.stem not in used:
                self.err(py, "entry point is not registered in hooks.json")
            if not re.fullmatch(r"(guard|check|fix)_[a-z_]+", py.stem):
                self.err(py, "hook entry names are guard_*/check_*/fix_*")

    def check_commands(self, allow: dict) -> None:
        names = set()
        for p in sorted((self.root / "commands").glob("*.md")):
            parsed = split_frontmatter(self.read(p))
            if parsed is None or not str(parsed[0].get("description", "")).strip():
                self.err(p, "command needs frontmatter with description")
            names.add(p.stem)
        for name in sorted(names & set(allow.get("commands", []))):
            self.err(self.root / "commands" / f"{name}.md", "same name as an allowlisted fork command")

    def check_agent_skills(self, agent_names: list[str]) -> None:
        allow = json.loads((self.root / "allowlist.json").read_text(encoding="utf-8"))
        available = {p.parent.name for p in (self.root / "skills").glob("*/SKILL.md")}
        available |= set(allow.get("skills", [])) | set(allow.get("upstreamSkills", []))
        for p in sorted((self.root / "agents").glob("*.md")):
            parsed = split_frontmatter(self.read(p))
            if parsed is None:
                continue
            for skill in as_list(parsed[0].get("skills")):
                if skill not in available:
                    self.err(p, f"preloaded skill '{skill}' is not installed by the br payload")
        for name in sorted(set(allow.get("upstreamSkills", [])) & {p.parent.name for p in (self.root / "skills").glob("*/SKILL.md")}):
            self.err(self.root / "allowlist.json", f"upstream skill '{name}' clashes with a br skill of the same name")

    def run(self) -> list[str]:
        models = json.loads((self.root / "agent-models.json").read_text(encoding="utf-8")).get("agents", {})
        self.check_core()
        names = self.check_agents(models)
        self.check_rules()
        self.check_skills()
        self.check_output_styles()
        self.check_json(names, models)
        self.check_hooks()
        self.check_templates()
        allow = json.loads((self.root / "allowlist.json").read_text(encoding="utf-8"))
        self.check_commands(allow)
        self.check_agent_skills(names)
        return self.errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--repo", type=Path)
    args = ap.parse_args()
    errors = Validator(args.root.resolve(), args.repo.resolve() if args.repo else None).run()
    for e in errors:
        print(e)
    print(f"validate: {len(errors)} problem(s)", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
