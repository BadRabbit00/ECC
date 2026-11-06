#!/usr/bin/env python3
"""Second half of the br payload build (nix/payload.nix): frontmatter edits and self-checks.

The shell part of the build has already copied files into $out. This script:
  1. pins model/effort from agent-models.json into every agent;
  2. isolates every agent (omitClaudeMd, disallowedTools, maxTurns, preloaded skills for the Nix
     agents, no "Use PROACTIVELY"); a no-op for fields an agent already has;
  3. injects core/subagent-contract.md after the frontmatter of every agent;
  4. writes hooks.json with the pinned br-hook path;
  5. runs the output self-checks. Any miss exits non-zero and fails the build.

Usage: payload.py <out> <repo-root> <br-hook-exe>
Stdlib only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Skills each Nix agent is told to read in its body. The Skill tool is disabled for
# subagents, so preloading through `skills:` is the only way they get them.
NIX_AGENT_SKILLS = {
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


def block_list_keys(fm: list[str]) -> list[str]:
    """Keys written as `key:` + indented or `- ` lines. get/put/as_list only understand one-line
    values, so editing such a list would leave orphaned items behind: refuse instead."""
    keys = []
    for i, line in enumerate(fm[:-1]):
        m = re.fullmatch(r"([A-Za-z_][\w-]*):\s*", line)
        if m and fm[i + 1].startswith((" ", "\t", "- ")):
            keys.append(m.group(1))
    return keys


def join(fm: list[str], body: str) -> str:
    return "---\n" + "\n".join(fm) + "\n---\n" + body


def get(fm: list[str], key: str) -> str | None:
    for line in fm:
        if line.startswith(key + ":"):
            return line.split(":", 1)[1].strip()
    return None


def put(fm: list[str], key: str, value: str) -> list[str]:
    out = [ln for ln in fm if not ln.startswith(key + ":")]
    out.append(f"{key}: {value}")
    return out


def as_list(value: str | None) -> list[str]:
    if not value:
        return []
    v = value.strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1]
    return [x.strip().strip("'\"") for x in v.split(",") if x.strip()]


def hooks_shape_ok(hooks: object) -> bool:
    """hooks.json must be {"hooks": {event: [{"hooks": [{"command": str}]}]}}; anything else is
    reported here instead of crashing the substitution below."""
    by_event = hooks.get("hooks") if isinstance(hooks, dict) else None
    if not isinstance(by_event, dict):
        fail("hooks/hooks.json: top level must be an object with a 'hooks' object")
        return False
    ok = True
    for event, entries in by_event.items():
        if not isinstance(entries, list):
            fail(f"hooks/hooks.json: {event} must be a list")
            ok = False
            continue
        for entry in entries:
            cmds = entry.get("hooks") if isinstance(entry, dict) else None
            if not isinstance(cmds, list) or not all(isinstance(h, dict) and isinstance(h.get("command"), str) for h in cmds):
                fail(f"hooks/hooks.json: {event}: every entry needs a 'hooks' list of objects with a string 'command'")
                ok = False
    return ok


def main() -> int:
    out, br, hook_exe = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    claude = out / "claude"
    agents_dir = claude / "agents"
    models = json.loads((br / "agent-models.json").read_text(encoding="utf-8"))["agents"]
    contract = (br / "core" / "subagent-contract.md").read_text(encoding="utf-8").rstrip("\n") + "\n\n"
    # Effort values and the PROACTIVELY sentence are defined once, in the validator's config.
    cfg = json.loads((br / "tools" / "validate.json").read_text(encoding="utf-8"))
    allowed_effort = cfg["allowedEffort"]
    proactive = re.compile(cfg["proactivelyPattern"])

    # --- 1–3: agents -----------------------------------------------------------------------------
    for p in sorted(agents_dir.glob("*.md")):
        name = p.stem
        try:
            fm, body = split(p.read_text(encoding="utf-8"))
        except ValueError as exc:
            fail(f"{name}: {exc}")
            continue
        blocks = block_list_keys(fm)
        for key in blocks:
            fail(f"{name}: block-style list for '{key}' is not supported; use inline [a, b]")
        if blocks:
            continue
        if name not in models:
            fail(f"{name}: no entry in agent-models.json")
            continue
        model, effort = str(models[name]["model"]), str(models[name]["effort"])
        if not re.fullmatch(r"claude-[a-z0-9.-]+", model):
            fail(f"{name}: bad model id {model!r}")
            continue
        if effort not in allowed_effort:
            fail(f"{name}: bad effort {effort!r}")
            continue
        fm = put(fm, "model", model)
        fm = put(fm, "effort", effort)
        fm = put(fm, "omitClaudeMd", "true")
        dis = as_list(get(fm, "disallowedTools"))
        fm = put(fm, "disallowedTools", ", ".join(dis + [t for t in REQUIRED_DISALLOWED if t not in dis]))
        if get(fm, "maxTurns") is None:
            fm = put(fm, "maxTurns", "40")
        if get(fm, "tools") is None:
            fail(f"{name}: agent without an explicit tools: line")
        skills = NIX_AGENT_SKILLS.get(name, [])
        if skills:
            fm = put(fm, "skills", "[" + ", ".join(skills) + "]")
        fm = [proactive.sub("", ln) if ln.startswith("description:") else ln for ln in fm]
        p.write_text(join(fm, "\n" + contract + body.lstrip("\n")), encoding="utf-8")
    for skill_agent in NIX_AGENT_SKILLS:
        if not (agents_dir / f"{skill_agent}.md").is_file():
            fail(f"{skill_agent}: listed in NIX_AGENT_SKILLS but agents/{skill_agent}.md is missing")

    # --- 4: hooks.json ---------------------------------------------------------------------------
    # Parse first, substitute inside the command values only: a raw-text replace would also hit
    # descriptions and break JSON if the path ever needed escaping.
    hooks = json.loads((br / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    hooks_ok = hooks_shape_ok(hooks)
    if hooks_ok:
        for entries in hooks["hooks"].values():
            for entry in entries:
                for h in entry["hooks"]:
                    h["command"] = h["command"].replace("@BR_HOOK@", hook_exe)
        (out / "hooks.json").write_text(json.dumps(hooks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # --- 5: self-checks --------------------------------------------------------------------------
    for p in sorted(agents_dir.glob("*.md")):
        try:
            fm, body = split(p.read_text(encoding="utf-8"))
        except ValueError as exc:
            fail(f"{p.name}: {exc}")
            continue
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
    hits = [str(f.relative_to(out)) for f in out.rglob("*") if f.is_file() and STYLE_MARKER in f.read_text(encoding="utf-8", errors="ignore")]
    if hits != ["claude/output-styles/orchestrator.md"]:
        fail(f"style marker found in {hits}; expected only claude/output-styles/orchestrator.md")

    settings = json.loads((out / "settings.fragment.json").read_text(encoding="utf-8"))
    if not isinstance(settings, dict):
        fail("settings.fragment.json: top level must be an object")
    else:
        if set(settings) != {"env", "outputStyle"}:
            fail(f"settings.fragment.json: keys {sorted(settings)}, expected ['env', 'outputStyle']")
        env = settings.get("env")
        if not isinstance(env, dict) or env.get("CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH") != "1":
            fail("settings.fragment.json: CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH must be \"1\"")
        if settings.get("outputStyle") != "orchestrator":
            fail("settings.fragment.json: outputStyle must be orchestrator")

    for p in sorted((claude / "rules" / "br").glob("*.md")):
        try:
            fm, _ = split(p.read_text(encoding="utf-8"))
        except ValueError:
            fm = []
        if not any(ln.startswith("paths:") for ln in fm):
            fail(f"rules/br/{p.name}: no paths: frontmatter (would load into every session)")

    if hooks_ok:
        raw = (out / "hooks.json").read_text(encoding="utf-8")
        if "@BR_HOOK@" in raw:
            fail("hooks.json: @BR_HOOK@ left")
        for entries in hooks["hooks"].values():
            for entry in entries:
                if not str(entry.get("id", "")).startswith("br:"):
                    fail(f"hooks.json: id {entry.get('id')} does not start with br:")
                for h in entry["hooks"]:
                    parts = h["command"].split()
                    if len(parts) != 2 or parts[0] != hook_exe or not (br / "hooks" / f"{parts[1]}.py").is_file():
                        fail(f"hooks.json: bad command {h['command']!r}")

    for d, want in [("skills/architecture-guide/references/layers", 11), ("skills/security-review/references", 5)]:
        count = len(list((claude / d).glob("*.md")))
        if count != want:
            fail(f"{d}: {count} files, expected {want}")
    if not (claude / "skills/project-docs/templates/example_db.dbml").is_file():
        fail("skills/project-docs/templates/example_db.dbml missing")

    if errors:
        print("br payload self-check failed:", file=sys.stderr)
        for msg in errors:
            print("  - " + msg, file=sys.stderr)
        return 1
    print(f"br payload: {len(list(agents_dir.glob('*.md')))} agents, "
          f"{len(list((claude / 'skills').iterdir()))} skills, "
          f"{len(list((claude / 'commands').glob('*.md')))} commands, "
          f"{len(list((claude / 'rules' / 'br').glob('*.md')))} rules — self-checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
