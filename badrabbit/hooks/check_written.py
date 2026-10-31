#!/usr/bin/env python3
"""PostToolUse · Edit|Write|MultiEdit — fix encoding, catch secrets, lint compose/Dockerfile."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brhooks import post_checks  # noqa: E402
from brhooks.common import post_block, post_context, read_event, run_guarded  # noqa: E402


def main() -> None:
    result = post_checks.run(read_event())
    if not result:
        return
    kind, message = result
    (post_block if kind == "block" else post_context)(message)


if __name__ == "__main__":
    run_guarded(main)
