---
description: Fix a failing nix eval/build/activation with the nix-build-resolver agent — hash mismatches, missing inputs, sandbox failures, infinite recursion, conflicting options, lockfile builders. Minimal diff, no refactoring.
argument-hint: "[failing command or error text]"
---

# /nix-fix

Invoke **nix-build-resolver** with `$ARGUMENTS` (the failing command, or the last error block). It reproduces with `--show-trace`/`-L`, reads `nix log`, applies one fix at a time and re-runs until green, throttled `--max-jobs 4 --cores 4`.

If it reports that the fix needs a design change, go to `/nix-plan` instead of forcing it. Report error → cause → fix → verification.
