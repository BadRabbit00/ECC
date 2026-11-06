---
description: Run only the tests affected by the current changes (or since a given ref) and show the numbers. Usage /test-affected [base-ref]
argument-hint: "[base ref, default develop]"
---

# /test-affected

1. Base ref = `$ARGUMENTS` or `develop` (fall back to `main` if `develop` does not exist). Say which one you used.
2. Dispatch `test-runner`, mode `affected`, with that base.
3. Show its result in Russian, briefly: the commands with passed / failed / skipped, then failures with their class (regression, flaky, env) and the first assertion line. No interpretation beyond what the runner reported.
4. If something is red, offer the next step (send it to `build-fixer` for a broken build, or describe the regression for a task); do nothing without «да».
