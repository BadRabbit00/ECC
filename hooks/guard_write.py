#!/usr/bin/env python3
"""PreToolUse · Edit|Write|MultiEdit|NotebookEdit — test boundary, task write sets, orchestrator scope."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brhooks import write_checks  # noqa: E402
from brhooks.common import deny, read_event, run_guarded  # noqa: E402


def main() -> None:
    reason = write_checks.check_write(read_event())
    if reason:
        deny(reason)


if __name__ == "__main__":
    run_guarded(main)
