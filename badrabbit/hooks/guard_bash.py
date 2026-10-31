#!/usr/bin/env python3
"""PreToolUse · Bash — host installs, git rules, destructive commands, secrets, test files via shell."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brhooks import bash_checks  # noqa: E402
from brhooks.common import deny, read_event, run_guarded  # noqa: E402


def main() -> None:
    reason = bash_checks.run(read_event())
    if reason:
        deny(reason)


if __name__ == "__main__":
    run_guarded(main)
