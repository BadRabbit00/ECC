"""Tests for measure_tokens.py. Run from badrabbit/tools: python3 -m unittest test_measure_tokens"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import measure_tokens as mt

W = (1.25, 0.1, 5.0)


def usage(inp, cw=0, cr=0, out=0):
    return {"input_tokens": inp, "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr, "output_tokens": out}


def assistant(msg_id, u, content=None, **extra):
    return {"type": "assistant", "message": {"id": msg_id, "role": "assistant", "content": content or [], "usage": u}, **extra}


def user(text, **extra):
    return {"type": "user", "message": {"role": "user", "content": text}, **extra}


def task_call(agent, prompt):
    return {"type": "tool_use", "name": "Task", "id": "tu1", "input": {"subagent_type": agent, "prompt": prompt, "description": "d"}}


def write(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


class MeasureTokens(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_dedup_streamed_lines_by_message_id(self):
        u = usage(10, 1000, 0, 50)
        write(self.tmp / "s.jsonl", [user("hi"), assistant("m1", u), assistant("m1", u), assistant("m2", usage(5, 0, 1000, 20))])
        runs = mt.collect([str(self.tmp)])
        self.assertEqual(len(runs), 1)
        m = runs[0].metrics(W)
        self.assertEqual(m["requests"], 2)
        self.assertEqual(m["start"], 1010)
        self.assertEqual(m["peak"], 1010)
        self.assertEqual(m["output"], 70)

    def test_subagent_file_gets_type_from_parent_prompt(self):
        brief = "Task: T1 — order statuses\nGoal: failing tests"
        write(self.tmp / "abc.jsonl", [user("go"), assistant("m1", usage(3, 500), [task_call("test-writer", brief)])])
        write(self.tmp / "abc" / "subagents" / "agent-1.jsonl", [user(brief), assistant("s1", usage(2, 4000, 0, 10))])
        stats = mt.by_type(mt.collect([str(self.tmp)]), W)
        self.assertIn("test-writer", stats)
        self.assertEqual(stats["test-writer"]["start_median"], 4002)
        self.assertEqual(list(stats)[0], "main")

    def test_inline_sidechain_split_from_main(self):
        brief = "review T2"
        write(self.tmp / "s.jsonl", [
            user("start"), assistant("m1", usage(1, 100), [task_call("code-reviewer", brief)]),
            user(brief, isSidechain=True, agentId="x"), assistant("s1", usage(1, 3000), isSidechain=True, agentId="x"),
        ])
        stats = mt.by_type(mt.collect([str(self.tmp)]), W)
        self.assertEqual(stats["main"]["start_median"], 101)
        self.assertEqual(stats["code-reviewer"]["start_median"], 3001)

    def test_declared_agent_type_wins(self):
        write(self.tmp / "agent-9.jsonl", [user("x", agentType="db-reviewer"), assistant("s", usage(1, 10))])
        self.assertEqual(mt.collect([str(self.tmp)])[0].agent_type, "db-reviewer")

    def test_unknown_when_parent_missing_and_bad_lines_skipped(self):
        p = self.tmp / "agent-2.jsonl"
        write(p, [user("orphan"), assistant("s", usage(1, 1))])
        with p.open("a") as fh:
            fh.write("not json\n")
        self.assertEqual(mt.collect([str(p)])[0].agent_type, "unknown")

    def test_compare_with_pairs(self):
        a, b = self.tmp / "a", self.tmp / "b"
        write(a / "s.jsonl", [user("x"), assistant("m", usage(0, 40000), [task_call("tdd-guide", "brief")])])
        write(a / "s" / "subagents" / "agent-1.jsonl", [user("brief"), assistant("q", usage(0, 20000))])
        write(b / "s.jsonl", [user("x"), assistant("m", usage(0, 20000), [task_call("test-writer", "brief")])])
        write(b / "s" / "subagents" / "agent-1.jsonl", [user("brief"), assistant("q", usage(0, 5000))])
        pairs = self.tmp / "pairs.json"
        pairs.write_text(json.dumps({"tdd-guide": "test-writer"}))
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = mt.main(["compare", "--a", str(a), "--b", str(b), "--pairs", str(pairs)])
        out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("| main | 40,000 | 20,000 | -50% |", out)
        self.assertIn("tdd-guide → test-writer | 20,000 | 5,000 | -75% |", out)

    def test_report_json_and_weights(self):
        write(self.tmp / "s.jsonl", [user("x"), assistant("m", usage(100, 1000, 2000, 10))])
        buf = io.StringIO()
        with redirect_stdout(buf):
            mt.main(["--weights", "2,0.1,5", "report", str(self.tmp), "--json"])
        data = json.loads(buf.getvalue())
        self.assertEqual(data["agents"]["main"]["weighted"], 100 + 2000 + 200 + 50)


if __name__ == "__main__":
    unittest.main()
