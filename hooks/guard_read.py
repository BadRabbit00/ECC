#!/usr/bin/env python3
"""PreToolUse · Read|Grep — secret files never enter the context."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brhooks import write_checks  # noqa: E402
from brhooks.common import deny, read_event, run_guarded  # noqa: E402


def main() -> None:
    reason = write_checks.check_read(read_event())
    if reason:
        deny(reason)


if __name__ == "__main__":
    run_guarded(main)
