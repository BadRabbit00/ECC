"""Checks for Bash tool calls. Each check returns a deny reason or None.

These are heuristics over the command text. They stop the common mistakes, not a determined
adversary; the orchestrator's sha256 check of test files and code review are the backstops.
"""
from __future__ import annotations

import re
import shlex
from pathlib import Path

from .common import NO_TEST_WRITE, PROTECTED_BRANCHES, Event, git_branch, is_test_path

# Split a command line into simple commands on ; && || | & and newlines (good enough for policy checks).
SPLIT = re.compile(r"\s*(?:&&|\|\||;|\||(?<![>&])&(?![>&])|\n)\s*")
WRAPPERS = {"sudo", "doas", "command", "exec", "time", "nohup", "nice", "env"}


def segments(cmd: str) -> list[str]:
    return [s.strip() for s in SPLIT.split(cmd) if s.strip()]


def words(seg: str) -> list[str]:
    try:
        w = shlex.split(seg, comments=True)
    except ValueError:
        w = seg.split()
    # drop leading env assignments and wrappers that do not change meaning
    while w and (re.fullmatch(r"\w+=.*", w[0]) or (w[0] in WRAPPERS and len(w) > 1)):
        w = w[1:]
    # look inside `nix develop -c …` / `nix shell … -c …`
    if len(w) > 2 and w[0] == "nix" and w[1] in {"develop", "shell"}:
        for flag in ("-c", "--command"):
            if flag in w:
                w = w[w.index(flag) + 1:]
                break
    return w


def expand(cmd: str) -> list[str]:
    """Segments, plus the inner script of `bash -c '…'` / `sh -c` (also behind `nix develop -c`)."""
    out = []
    for seg in segments(cmd):
        out.append(seg)
        w = words(seg)
        if len(w) >= 3 and Path(w[0]).name in {"bash", "sh", "zsh"} and w[1] == "-c":
            out.extend(expand(w[2]))
    return out


# ---------------------------------------------------------------- host installs

HOST_INSTALL = [
    (re.compile(r"^(pip3?|python3?(\.\d+)?\s+-m\s+pip|uv\s+pip)\s+install\b"), "pip install"),
    (re.compile(r"^pipx\s+(install|run)\b"), "pipx"),
    (re.compile(r"^uv\s+(sync|venv|add|tool\s+install)\b"), "uv sync/venv/add"),
    (re.compile(r"^(python3?(\.\d+)?\s+-m\s+venv|virtualenv)\b"), "virtualenv"),
    (re.compile(r"^(npm|pnpm)\s+(i|install|add)\b.*\s(-g|--global)\b"), "global npm/pnpm install"),
    (re.compile(r"^yarn\s+global\b"), "yarn global"),
    (re.compile(r"^go\s+install\b"), "go install"),
    (re.compile(r"^cargo\s+install\b"), "cargo install"),
    (re.compile(r"^rustup\s+(toolchain\s+install|component\s+add|target\s+add)\b"), "rustup"),
    (re.compile(r"^nix-env\s+(-i|--install|-iA)\b"), "nix-env -i"),
    (re.compile(r"^nix\s+profile\s+(install|add)\b"), "nix profile install"),
    (re.compile(r"^(apt|apt-get|dnf|yum|zypper|apk)\s+(install|add)\b"), "system package manager"),
    (re.compile(r"^pacman\s+-S"), "pacman"),
    (re.compile(r"^(brew|snap|flatpak|choco|winget)\s+install\b"), "system package manager"),
    (re.compile(r"^python3?(\.\d+)?\s+-c\b"), "inline python (python -c)"),
    (re.compile(r"^node\s+(-e|--eval|-p)\b"), "inline node (node -e)"),
]
CURL_PIPE_SH = re.compile(r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z)?sh\b")


def check_host_install(ev: Event, cmd: str) -> str | None:
    if CURL_PIPE_SH.search(cmd):
        return ("curl | sh installs software on the host. Add the tool to the project devShell "
                "or use `nix shell nixpkgs#<pkg> -c …`.")
    for seg in expand(cmd):
        line = " ".join(words(seg))
        for rx, what in HOST_INSTALL:
            if rx.search(line):
                if what.startswith("inline"):
                    return f"{what} is not allowed: write the script to a file and run it through `nix develop -c`."
                return (f"{what} is not allowed: nothing is installed on the host or into .venv. "
                        "Add the dependency to the project flake/devShell (or pyproject + nixpkgs), "
                        "or run a one-off tool with `nix shell nixpkgs#<pkg> -c <cmd>`.")
    return None


# ---------------------------------------------------------------- git

# Subcommands that change history or the index of the current branch.
GIT_WRITE = {"commit", "rebase", "reset", "cherry-pick", "revert", "am", "pull", "restore", "rm", "mv",
             "add", "merge", "apply", "notes", "replace", "filter-branch", "filter-repo"}
GIT_GLOBAL_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}


def git_call(seg: str, cwd: Path) -> tuple[list[str], Path] | None:
    """(args after global options, effective cwd) or None if the segment is not git."""
    w = words(seg)
    if not w or Path(w[0]).name != "git":
        return None
    i = 1
    while i < len(w) and w[i].startswith("-"):
        if w[i] == "-C" and i + 1 < len(w):
            cwd = Path(w[i + 1]) if Path(w[i + 1]).is_absolute() else cwd / w[i + 1]
        i += 2 if w[i] in GIT_GLOBAL_WITH_ARG else 1
    return (w[i:], cwd) if i < len(w) else None


def _push_reason(rest: list[str], branch: str | None) -> str | None:
    if any(a in {"--all", "--mirror", "--tags"} for a in rest):
        return "`git push --all/--mirror/--tags` touches develop/main and releases. Push your feature branch only."
    targets = [a for a in rest if not a.startswith("-")]
    refspecs = targets[1:]
    if "--delete" in rest or "-d" in rest:
        if any(t.removeprefix("refs/heads/") in PROTECTED_BRANCHES for t in refspecs):
            return "Deleting develop/main on the remote is not allowed."
        return None
    dests = []
    for r in refspecs:
        dst = r.lstrip("+").split(":")[-1].removeprefix("refs/heads/")
        dests.append(branch if dst in {"HEAD", "@", ""} else dst)
    if not refspecs:
        dests = [branch]          # `git push` / `git push origin` pushes the current branch
    if any(d in PROTECTED_BRANCHES for d in dests):
        return ("Pushing develop/main is done by a human. Push your feature branch only "
                "(`git push -u origin feature/<task-id>-<slug>`).")
    return None


def check_git(ev: Event, cmd: str) -> str | None:
    for seg in expand(cmd):
        call = git_call(seg, ev.cwd)
        if not call:
            continue
        args, cwd = call
        sub, rest = args[0], args[1:]
        cache: dict[str, str | None] = {}

        def branch() -> str | None:
            if "b" not in cache:
                cache["b"] = git_branch(cwd)
            return cache["b"]

        if "--no-verify" in rest or (sub == "commit" and "-n" in rest):
            return "--no-verify bypasses the project's git hooks. Fix the failing check instead."
        if sub == "push":
            reason = _push_reason(rest, branch())
            if reason:
                return reason
            continue
        if sub == "clean" and any("x" in a.lstrip("-").lower() for a in rest if a.startswith("-") and not a.startswith("--")):
            return "`git clean -x` deletes ignored files such as .env and local data. Remove specific files instead."
        if sub == "branch" and any(a in {"-D", "-d", "--delete", "-f", "--force", "-m", "-M"} for a in rest) \
                and any(a in PROTECTED_BRANCHES for a in rest):
            return "Deleting, renaming, or force-moving develop/main is not allowed."
        if sub == "update-ref" and any(a.removeprefix("refs/heads/") in PROTECTED_BRANCHES for a in rest):
            return "Moving develop/main refs directly is not allowed."
        if sub not in GIT_WRITE:
            continue
        b = branch()
        if b not in PROTECTED_BRANCHES:
            continue                      # feature branches: free
        if sub == "merge" and b == "develop":
            if "--abort" in rest or "--quit" in rest:
                continue
            sources = [a for a in rest if not a.startswith("-")]
            if sources and all(s.startswith(("feature/", "hotfix/")) for s in sources):
                continue                  # finishing a task: feature → develop is the one allowed write
        if sub == "pull" and "--ff-only" in rest:
            continue                      # updating the local copy without creating commits
        return (f"`git {sub}` on `{b}` is not allowed. Work on `feature/<task-id>-<slug>`. The only write to develop "
                "is `git merge --no-ff feature/…` when the task is done; resolve conflicts by merging develop into "
                "the feature branch first.")
    return None


# ---------------------------------------------------------------- destructive

REBUILDABLE = {"node_modules", "dist", "build", "target", "__pycache__", ".pytest_cache", ".mypy_cache",
               ".ruff_cache", ".next", ".nuxt", "out", "coverage", ".coverage", "htmlcov", ".turbo",
               ".parcel-cache", ".dart_tool", ".gradle", ".svelte-kit"}
RESULT_LINK = re.compile(r"result(-[\w.-]+)?")
TMP_PREFIXES = ("/tmp/", "/var/tmp/")


def _safe_rm_target(t: str) -> bool:
    if t.startswith(TMP_PREFIXES) or "/scratchpad/" in t:
        return ".." not in Path(t).parts
    parts = Path(t.rstrip("/")).parts
    if not parts or ".." in parts or t.startswith(("/", "~", "$")):
        return False
    return any(p in REBUILDABLE for p in parts) or RESULT_LINK.fullmatch(parts[-1]) is not None


SQL_DESTROY = re.compile(r"\b(DROP\s+(TABLE|DATABASE|SCHEMA|COLLECTION|OWNED)|TRUNCATE\b|FLUSHALL|FLUSHDB)|\.drop\(\)|dropDatabase\(\)", re.I)
SQL_CLIENT = re.compile(r"\b(psql|pgcli|mongosh|mongo|mysql|mariadb|sqlite3|clickhouse-client|redis-cli)\b|docker\s+compose\s+exec", re.I)


def check_destructive(ev: Event, cmd: str) -> str | None:
    # whole command: SQL may come through a heredoc on the next lines
    if (SQL_CLIENT.search(cmd) and SQL_DESTROY.search(cmd)) or re.search(r"(^|[\s;&|])dropdb\s", cmd):
        return "DROP/TRUNCATE/FLUSH needs the user's explicit «да» and must never target a shared or production database."
    for seg in expand(cmd):
        w = words(seg)
        if not w:
            continue
        line = " ".join(w)
        if w[0] == "rm":
            flags = [a for a in w[1:] if a.startswith("-")]
            targets = [a for a in w[1:] if not a.startswith("-")]
            if any(Path(a).name == ".git" or (Path(a).name == ".env" or Path(a).name.startswith(".env."))
                   and not re.search(r"\.(example|sample|template)\b", a) for a in targets):
                return "Deleting .env or .git needs the user's explicit «да»."
            if any(re.fullmatch(r"-[a-zA-Z]*[rR][a-zA-Z]*|--recursive", a) for a in flags):
                unsafe = [t for t in targets if not _safe_rm_target(t)]
                if unsafe or not targets:
                    return (f"Recursive delete of {unsafe or 'unknown targets'} needs the user's explicit «да» "
                            "with a named list. Temp dirs and rebuildable caches (node_modules, dist, target, result…) are fine.")
        if w[0] == "find" and ("-delete" in w or ("-exec" in w and "rm" in w)):
            return "Bulk delete with find needs the user's explicit «да» with a named list."
        if re.search(r"docker[\s-]compose\b.*\bdown\b.*(\s-v\b|--volumes)", line) or \
           re.search(r"docker\s+(volume\s+(rm|prune)|system\s+prune\b.*--volumes)", line):
            return "This destroys Docker volumes (databases of this and other projects). Ask the user with a named list first."
        if re.search(r"nix-collect-garbage\s+(-d|--delete-old)|nix\s+profile\s+wipe-history|nix-store\s+--delete", line):
            return "Deleting old generations removes system rollbacks. Only on the user's direct request."
        if re.search(r"^(reboot|poweroff|shutdown|halt)\b|systemctl\s+(reboot|poweroff|restart\s+(docker|display-manager|nix-daemon))", line):
            return "This interrupts the user's session. Prepare the step and let the user run it."
        if re.search(r"^nixos-rebuild\s+(switch|boot|test)\b|^home-manager\s+switch\b|^darwin-rebuild\s+switch\b", line):
            return "Switching the system/home generation is done by the user. Build with `nixos-rebuild build` and report."
        if re.search(r"^(mkfs(\.\w+)?|wipefs)\b|\bdd\b.*\bof=/dev/", line):
            return "Disk-level destructive command."
    return None


# ---------------------------------------------------------------- secrets

SECRET_FILE = re.compile(
    r"(^|[\s/'\"=])\.env(\.(?!example(?=$|[\s'\"]))[\w.-]+)?(?=$|[\s'\"])"   # .env, .env.local; not .env.example
    r"|[\w-]\.(pem|key|p12|pfx)\b"                                       # cert.pem, tls.key
    r"|\bid_(rsa|ed25519|ecdsa)\b(?!\.pub)"                             # ssh private keys
    r"|\bkeys\.txt\b")                                                  # age / sops key file
SECRET_VAR = re.compile(r"\$\{?\w*(SECRET|TOKEN|PASSWORD|PASSWD|API_KEY|PRIVATE|CREDENTIAL|DSN|DATABASE_URL)\w*", re.I)
READERS = {"cat", "less", "more", "head", "tail", "bat", "nl", "xxd", "od", "hexdump", "strings", "base64",
           "jq", "yq", "sed", "awk", "grep", "rg", "cp", "scp", "rsync", "source", ".", "diff", "vim", "nano"}


def check_secrets(ev: Event, cmd: str) -> str | None:
    for seg in expand(cmd):
        w = words(seg)
        if not w:
            continue
        if (w[0] in {"printenv", "env", "set"} and len(w) == 1) or (w[0] == "export" and (len(w) == 1 or "-p" in w)):
            return "Printing the whole environment exposes secrets. Check one variable with `test -n \"$NAME\"`."
        if w[0] == "printenv" and SECRET_VAR.search("$" + " $".join(w[1:])):
            return "Do not print secret values. Check presence with `test -n \"$NAME\"`."
        if Path(w[0]).name in READERS and SECRET_FILE.search(" " + " ".join(w[1:])):
            if w[0] in {"grep", "rg"} and any(a in {"-q", "--quiet", "-c", "--count", "-l"} for a in w):
                continue
            return "Do not read secret files into the output. To check a variable is set: `grep -q '^NAME=.' .env`."
        if w[0] in {"echo", "printf"} and SECRET_VAR.search(seg):
            return "Do not print secret values."
        if w[:3] == ["gh", "secret", "set"] and any(a in {"--body", "-b"} or a.startswith("--body=") for a in w):
            return "Pass the secret through stdin (`gh secret set NAME < file`), not as an argument."
        if w[0] == "sops" and any(a in {"-d", "--decrypt", "decrypt"} for a in w[1:]):
            if "--extract" in seg and re.search(r">\s*/dev/null", seg):
                continue
            return "Do not decrypt sops files to the terminal or a file. Use `sops exec-env` or `--extract … >/dev/null` to check."
        if (w[:3] == ["docker", "compose", "config"] or w[:2] == ["docker-compose", "config"]) \
                and not any(a in {"--quiet", "-q", "--services", "--volumes", "--images"} for a in w):
            return "`docker compose config` prints resolved secrets. Use `docker compose config --quiet`."
    return None


# ---------------------------------------------------------------- tests via bash

REDIRECT = re.compile(r"(?:\d?>{1,2}\|?|&>>?)\s*['\"]?([^\s;&|'\"<>]+)")
# Commands whose path arguments are written to (for cp/ln/install/rsync only the destination).
WRITE_ANY_ARG = {"tee", "rm", "rmdir", "touch", "truncate", "chmod", "chown", "mkdir", "shred", "unlink"}
WRITE_DEST_ONLY = {"cp", "ln", "install", "rsync"}
GIT_WRITE_PATHS = {"checkout", "restore", "rm", "mv", "apply"}


DIFF_TARGET = re.compile(r"^(?:\+\+\+|---) (?:[ab]/)?(\S+)", re.M)


def _diff_targets(diff_file: str | None, cwd: Path) -> list[str]:
    """Files a patch touches; an unreadable patch (stdin/heredoc) is treated as touching tests."""
    if diff_file:
        p = Path(diff_file) if Path(diff_file).is_absolute() else cwd / diff_file
        try:
            return [t for t in DIFF_TARGET.findall(p.read_text(errors="replace")) if t != "/dev/null"]
        except OSError:
            pass
    return ["test/ (patch target unknown)"]


def _test_paths_written(seg: str, cwd: Path) -> list[str]:
    hits = [p for p in REDIRECT.findall(seg) if is_test_path(p.removeprefix("./"))]
    w = words(seg)
    if not w:
        return hits
    name = Path(w[0]).name
    args = [a for a in w[1:] if not a.startswith("-") and not re.fullmatch(r"\d?[<>]{1,2}&?\d?|<<-?\w*", a)]
    redirected_in = re.search(r"<\s*['\"]?([^\s;&|'\"<>]+)", seg)
    cand: list[str] = []
    if name in WRITE_ANY_ARG or name == "mv":         # moving a test away changes it too
        cand = args
    elif name in WRITE_DEST_ONLY and args:
        cand = [args[-1]]
    elif name in {"sed", "perl"} and any(a.startswith("-i") or a == "--in-place" for a in w[1:]):
        cand = args
    elif name == "patch":
        src = next((a[2:] or None for a in w[1:] if a.startswith("-i")), None) or \
            (redirected_in.group(1) if redirected_in else None)
        cand = _diff_targets(src, cwd)
    elif name == "dd":
        cand = [a[3:] for a in w[1:] if a.startswith("of=")]
    elif name == "git" and len(w) > 1 and w[1] == "apply":
        cand = [t for f in (args[1:] or [None]) for t in _diff_targets(f, cwd)]
    elif name == "git" and len(w) > 1 and w[1] in GIT_WRITE_PATHS:
        cand = args[1:]
    return hits + [c for c in cand if is_test_path(c.removeprefix("./"))]


def check_tests_via_bash(ev: Event, cmd: str) -> str | None:
    if ev.agent not in NO_TEST_WRITE:
        return None
    for seg in expand(cmd):
        written = _test_paths_written(seg, ev.cwd)
        if written:
            return (f"`{ev.agent}` may read tests but never change them ({', '.join(written[:3])}). If a test looks "
                    "wrong, stop with STATUS: blocked and explain; the orchestrator returns it to test-writer.")
    return None


CHECKS = [check_host_install, check_git, check_destructive, check_secrets, check_tests_via_bash]


def run(ev: Event) -> str | None:
    cmd = ev.tool_input.get("command", "") or ""
    for check in CHECKS:
        reason = check(ev, cmd)
        if reason:
            return reason
    return None
