#!/usr/bin/env python3
"""Second half of the br payload build (nix/payload-br.nix): frontmatter edits and self-checks.

The shell part of the build has already copied files into $out. This script:
  1. pins model/effort from badrabbit/agent-models.json into every agent;
  2. isolates the allowlisted fork agents (omitClaudeMd, disallowedTools, maxTurns, preloaded skills,
     no "Use PROACTIVELY");
  3. injects core/subagent-contract.md after the frontmatter of every agent;
  4. writes hooks.json with the pinned br-hook path;
  5. runs the output self-checks. Any miss exits non-zero and fails the build.

Usage: payload-br.py <out> <badrabbit-dir> <br-hook-exe>
Stdlib only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Skills each allowlisted Nix agent is told to read in its body. The Skill tool is disabled for
# subagents, so preloading through `skills:` is the only way they get them.
FORK_AGENT_SKILLS = {
    "nix-architect": ["nix-toolkit", "nix-flake-patterns", "nixos-module-patterns"],
    "nix-engineer": ["nix-flake-patterns", "nixos-module-patterns", "nix-packaging"],
    "nix-build-resolver": ["nix-debugging"],
    "nix-test-runner": ["nix-testing"],
}
REQUIRED_DISALLOWED = ["Agent", "Skill", "mcp__*"]
CONTRACT_HEADING = "## Contract (all br subagents)"
STYLE_MARKER = "BR-ORCHESTRATOR-STYLE-ACTIVE"

errors: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


def split(text: str) -> tuple[list[str], str]:
    if not text.startswith("---\n"):
        raise ValueError("no frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("unterminated frontmatter")
    return text[4:end].split("\n"), text[end + 5:]


def join(fm: list[str], body: str) -> str:
    return "---\n" + "\n".join(fm) + "\n---\n" + body


def get(fm: list[str], key: str) -> str | None:
    for line in fm:
        if line.startswith(key + ":"):
            return line.split(":", 1)[1].strip()
    return None


def put(fm: list[str], key: str, value: str) -> list[str]:
    out = [l for l in fm if not l.startswith(key + ":")]
    out.append(f"{key}: {value}")
    return out


def as_list(value: str | None) -> list[str]:
    if not value:
        return []
    v = value.strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1]
    return [x.strip().strip("'\"") for x in v.split(",") if x.strip()]


def main() -> int:
    out, br, hook_exe = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    claude = out / "claude"
    agents_dir = claude / "agents"
    models = json.loads((br / "agent-models.json").read_text())["agents"]
    allow = json.loads((br / "allowlist.json").read_text())
    br_agents = {p.stem for p in (br / "agents").glob("*.md")}
    fork_agents = set(allow.get("agents", []))
    contract = (br / "core" / "subagent-contract.md").read_text().rstrip("\n") + "\n\n"

    # --- 1–3: agents -----------------------------------------------------------------------------
    dup = br_agents & fork_agents
    if dup:
        fail(f"agent names in both badrabbit/agents and allowlist.agents: {sorted(dup)}")
    for p in sorted(agents_dir.glob("*.md")):
        name = p.stem
        fm, body = split(p.read_text())
        if name not in models:
            fail(f"{name}: no entry in agent-models.json")
            continue
        fm = put(fm, "model", models[name]["model"])
        fm = put(fm, "effort", models[name]["effort"])
        if name in fork_agents:
            fm = put(fm, "omitClaudeMd", "true")
            dis = as_list(get(fm, "disallowedTools"))
            fm = put(fm, "disallowedTools", ", ".join(dis + [t for t in REQUIRED_DISALLOWED if t not in dis]))
            if get(fm, "maxTurns") is None:
                fm = put(fm, "maxTurns", "40")
            if get(fm, "tools") is None:
                fail(f"{name}: allowlisted agent without an explicit tools: line")
            skills = FORK_AGENT_SKILLS.get(name, [])
            if skills:
                fm = put(fm, "skills", "[" + ", ".join(skills) + "]")
            fm = [re.sub(r"\s*Use PROACTIVELY[^.]*\.", "", l) if l.startswith("description:") else l for l in fm]
        p.write_text(join(fm, "\n" + contract + body.lstrip("\n")))

    # --- 4: hooks.json ---------------------------------------------------------------------------
    hooks = json.loads((br / "hooks" / "hooks.json").read_text().replace("@BR_HOOK@", hook_exe))
    (out / "hooks.json").write_text(json.dumps(hooks, indent=2, ensure_ascii=False) + "\n")

    # --- 5: self-checks --------------------------------------------------------------------------
    names = set()
    for p in sorted(agents_dir.glob("*.md")):
        fm, body = split(p.read_text())
        names.add(get(fm, "name"))
        if get(fm, "omitClaudeMd") != "true":
            fail(f"{p.name}: omitClaudeMd is not true")
        if not (get(fm, "model") or "").startswith("claude-"):
            fail(f"{p.name}: model not pinned")
        if "Agent" not in as_list(get(fm, "disallowedTools")):
            fail(f"{p.name}: Agent not in disallowedTools")
        if CONTRACT_HEADING not in body:
            fail(f"{p.name}: contract not injected")
        if re.search(r"^# Core rules\b", body, re.M):
            fail(f"{p.name}: core rules leaked into an agent")
        if re.search(r"proactively", get(fm, "description") or "", re.I):
            fail(f"{p.name}: description still asks for proactive use")
        for s in as_list(get(fm, "skills")):
            if not (claude / "skills" / s / "SKILL.md").is_file():
                fail(f"{p.name}: preloaded skill '{s}' is not in the output")
    if "nix-reviewer" in names:
        text = (agents_dir / "nix-reviewer.md").read_text()
        if "MUST BE USED" in text:
            fail("nix-reviewer.md: the fork's version landed instead of the br one")

    hits = [str(f.relative_to(out)) for f in out.rglob("*") if f.is_file() and STYLE_MARKER in f.read_text(errors="ignore")]
    if hits != ["claude/output-styles/orchestrator.md"]:
        fail(f"style marker found in {hits}; expected only claude/output-styles/orchestrator.md")

    settings = json.loads((out / "settings.fragment.json").read_text())
    if settings.get("env", {}).get("CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH") != "1":
        fail("settings.fragment.json: CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH must be \"1\"")
    if settings.get("outputStyle") != "orchestrator":
        fail("settings.fragment.json: outputStyle must be orchestrator")

    for p in sorted((claude / "rules" / "br").glob("*.md")):
        try:
            fm, _ = split(p.read_text())
        except ValueError:
            fm = []
        if not any(l.startswith("paths:") for l in fm):
            fail(f"rules/br/{p.name}: no paths: frontmatter (would load into every session)")

    raw = (out / "hooks.json").read_text()
    if "@BR_HOOK@" in raw:
        fail("hooks.json: @BR_HOOK@ left")
    for event, entries in hooks["hooks"].items():
        for e in entries:
            if not str(e.get("id", "")).startswith("br:"):
                fail(f"hooks.json: id {e.get('id')} does not start with br:")
            for h in e["hooks"]:
                parts = h["command"].split()
                if len(parts) != 2 or parts[0] != hook_exe or not (br / "hooks" / f"{parts[1]}.py").is_file():
                    fail(f"hooks.json: bad command {h['command']!r}")

    for d, want in [("skills/architecture-guide/references/layers", 11), ("skills/security-review/references", 5)]:
        n = len(list((claude / d).glob("*.md")))
        if n != want:
            fail(f"{d}: {n} files, expected {want}")
    if not (claude / "skills/project-docs/templates/example_db.dbml").is_file():
        fail("skills/project-docs/templates/example_db.dbml missing")

    if errors:
        print("br payload self-check failed:", file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        return 1
    print(f"br payload: {len(list(agents_dir.glob('*.md')))} agents, "
          f"{len(list((claude / 'skills').iterdir()))} skills, "
          f"{len(list((claude / 'commands').glob('*.md')))} commands, "
          f"{len(list((claude / 'rules' / 'br').glob('*.md')))} rules — self-checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
