#!/usr/bin/env python3
"""Token usage per agent from Claude Code session transcripts (JSONL). Stdlib only.

Transcripts live in ~/.claude/projects/<project-dir>/<session-id>.jsonl. Subagent runs are either
separate files (<session-id>/subagents/agent-<id>.jsonl) or lines with "isSidechain": true inside
the main file. Both layouts are read.

Usage:
  measure_tokens.py report PATH... [--json]
  measure_tokens.py compare --a PATH... --b PATH... [--label-a legacy] [--label-b br] [--pairs pairs.json]

PATH is a .jsonl file or a directory (searched recursively).

Per run:
  start  = prompt size of the first API request (input + cache write + cache read): what the agent
           pays before doing anything — system prompt, tools, CLAUDE.md, rules, the brief.
  peak   = the largest prompt of the run.
  input / cache_write / cache_read / output = sums over the run's requests.
  weighted = input + cache_write * W + cache_read * R + output * O, in "input-token units"
             (defaults W=1.25, R=0.1, O=5; change with --weights). A comparison number, not a price.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

AGENT_TOOLS = {"Task", "Agent"}
PROMPT_KEY_LEN = 400


@dataclass
class Run:
    source: str
    kind: str  # "main" | "subagent"
    agent_type: str = "unknown"
    first_prompt: str = ""
    requests: list[dict] = field(default_factory=list)
    _seen: set = field(default_factory=set)

    def add(self, msg_id: str | None, usage: dict) -> None:
        if msg_id and msg_id in self._seen:
            return
        if msg_id:
            self._seen.add(msg_id)
        self.requests.append(usage)

    @staticmethod
    def prompt_size(u: dict) -> int:
        return int(u.get("input_tokens", 0)) + int(u.get("cache_creation_input_tokens", 0)) + int(
            u.get("cache_read_input_tokens", 0))

    def metrics(self, w: tuple[float, float, float]) -> dict:
        def total(key: str) -> int:
            return sum(int(u.get(key, 0)) for u in self.requests)
        sizes = [self.prompt_size(u) for u in self.requests]
        m = {
            "requests": len(self.requests),
            "start": sizes[0] if sizes else 0,
            "peak": max(sizes) if sizes else 0,
            "input": total("input_tokens"),
            "cache_write": total("cache_creation_input_tokens"),
            "cache_read": total("cache_read_input_tokens"),
            "output": total("output_tokens"),
        }
        m["weighted"] = round(m["input"] + m["cache_write"] * w[0] + m["cache_read"] * w[1] + m["output"] * w[2])
        return m


def iter_files(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            out.extend(sorted(p.rglob("*.jsonl")))
        elif p.suffix == ".jsonl" and p.exists():
            out.append(p)
        else:
            print(f"warning: skipped {p}", file=sys.stderr)
    return out


def read_lines(path: Path):
    with path.open(encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                print(f"warning: {path}:{n} is not JSON", file=sys.stderr)


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(parts)
    return ""


def prompt_key(text: str) -> str:
    return " ".join(text.split())[:PROMPT_KEY_LEN]


def collect(paths: list[str]) -> list[Run]:
    runs: list[Run] = []
    prompt_to_type: dict[str, str] = {}
    for path in iter_files(paths):
        is_agent_file = path.name.startswith("agent-") or "subagents" in path.parts
        main = Run(source=str(path), kind="subagent" if is_agent_file else "main",
                   agent_type="unknown" if is_agent_file else "main")
        side: dict[str, Run] = {}
        for rec in read_lines(path):
            if not isinstance(rec, dict):
                continue
            msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
            target = main
            if rec.get("isSidechain") and not is_agent_file:
                key = str(rec.get("agentId") or rec.get("sessionId") or "sidechain")
                target = side.setdefault(key, Run(source=f"{path}#{key}", kind="subagent"))
            declared = rec.get("agentType") or rec.get("subagent_type")
            if declared and target.kind == "subagent":
                target.agent_type = str(declared)
            if rec.get("type") == "user" and not target.first_prompt:
                target.first_prompt = text_of(msg.get("content"))
            if rec.get("type") == "assistant":
                for block in msg.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") in AGENT_TOOLS:
                        inp = block.get("input") or {}
                        if inp.get("subagent_type") and inp.get("prompt"):
                            prompt_to_type[prompt_key(str(inp["prompt"]))] = str(inp["subagent_type"])
                usage = msg.get("usage")
                if isinstance(usage, dict):
                    target.add(msg.get("id") or rec.get("requestId"), usage)
        for run in [main, *side.values()]:
            if run.requests:
                runs.append(run)
    for run in runs:
        if run.kind == "subagent" and run.agent_type == "unknown":
            run.agent_type = prompt_to_type.get(prompt_key(run.first_prompt), "unknown")
    return runs


def by_type(runs: list[Run], w) -> dict[str, dict]:
    groups: dict[str, list[dict]] = {}
    for r in runs:
        groups.setdefault(r.agent_type, []).append(r.metrics(w))
    out = {}
    for name, ms in sorted(groups.items(), key=lambda kv: (kv[0] != "main", kv[0])):
        out[name] = {
            "runs": len(ms),
            "start_median": round(statistics.median(m["start"] for m in ms)),
            "start_max": max(m["start"] for m in ms),
            "peak_max": max(m["peak"] for m in ms),
            "requests": sum(m["requests"] for m in ms),
            "input": sum(m["input"] for m in ms),
            "cache_write": sum(m["cache_write"] for m in ms),
            "cache_read": sum(m["cache_read"] for m in ms),
            "output": sum(m["output"] for m in ms),
            "weighted": sum(m["weighted"] for m in ms),
        }
    return out


COLS = ["runs", "start_median", "start_max", "peak_max", "requests", "input", "cache_write", "cache_read", "output", "weighted"]


def table(stats: dict[str, dict]) -> str:
    lines = ["| agent | " + " | ".join(COLS) + " |", "|---" * (len(COLS) + 1) + "|"]
    for name, s in stats.items():
        lines.append(f"| {name} | " + " | ".join(f"{s[c]:,}" for c in COLS) + " |")
    total = {c: sum(s[c] for s in stats.values()) for c in COLS if c not in ("start_median", "start_max", "peak_max")}
    lines.append("| **total** | " + " | ".join(f"{total[c]:,}" if c in total else "—" for c in COLS) + " |")
    return "\n".join(lines)


def pct(a: int, b: int) -> str:
    if a == 0:
        return "—"
    return f"{(b - a) / a * 100:+.0f}%"


def compare(a: dict, b: dict, label_a: str, label_b: str, pairs: dict[str, str]) -> str:
    rows = []
    mapped_b = set()
    for name_a, sa in a.items():
        name_b = pairs.get(name_a, name_a)
        sb = b.get(name_b)
        if sb:
            mapped_b.add(name_b)
        rows.append((f"{name_a} → {name_b}" if name_b != name_a else name_a, sa, sb))
    for name_b, sb in b.items():
        if name_b not in mapped_b and name_b not in a:
            rows.append((f"— → {name_b}", None, sb))
    head = (f"| role | start {label_a} | start {label_b} | Δ start | weighted/run {label_a} | "
            f"weighted/run {label_b} | Δ weighted/run |")
    lines = [head, "|---|---|---|---|---|---|---|"]
    for name, sa, sb in rows:
        s_a = sa["start_median"] if sa else 0
        s_b = sb["start_median"] if sb else 0
        w_a = round(sa["weighted"] / sa["runs"]) if sa else 0
        w_b = round(sb["weighted"] / sb["runs"]) if sb else 0
        lines.append(f"| {name} | {s_a:,} | {s_b:,} | {pct(s_a, s_b) if sa and sb else '—'} | "
                     f"{w_a:,} | {w_b:,} | {pct(w_a, w_b) if sa and sb else '—'} |")
    return "\n".join(lines)


def parse_weights(s: str) -> tuple[float, float, float]:
    parts = [float(x) for x in s.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("--weights needs three numbers: cache_write,cache_read,output")
    return parts[0], parts[1], parts[2]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weights", type=parse_weights, default=(1.25, 0.1, 5.0),
                    help="multipliers cache_write,cache_read,output (default 1.25,0.1,5)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("report")
    rp.add_argument("paths", nargs="+")
    rp.add_argument("--json", action="store_true")
    cp = sub.add_parser("compare")
    cp.add_argument("--a", nargs="+", required=True)
    cp.add_argument("--b", nargs="+", required=True)
    cp.add_argument("--label-a", default="legacy")
    cp.add_argument("--label-b", default="br")
    cp.add_argument("--pairs", help="JSON object mapping agent types of A to B, e.g. {\"tdd-guide\": \"test-writer\"}")
    args = ap.parse_args(argv)

    if args.cmd == "report":
        runs = collect(args.paths)
        if not runs:
            print("no usage records found", file=sys.stderr)
            return 1
        stats = by_type(runs, args.weights)
        if args.json:
            print(json.dumps({"agents": stats, "runs": [
                {"source": r.source, "agent": r.agent_type, **r.metrics(args.weights)} for r in runs]}, indent=2))
        else:
            print(table(stats))
            unknown = sum(1 for r in runs if r.agent_type == "unknown")
            if unknown:
                print(f"\n{unknown} subagent run(s) without a known agent type (the parent transcript was not given).")
        return 0

    a_runs, b_runs = collect(args.a), collect(args.b)
    if not a_runs or not b_runs:
        print("no usage records found on one side", file=sys.stderr)
        return 1
    pairs = json.loads(Path(args.pairs).read_text(encoding="utf-8")) if args.pairs else {}
    print(compare(by_type(a_runs, args.weights), by_type(b_runs, args.weights), args.label_a, args.label_b, pairs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
