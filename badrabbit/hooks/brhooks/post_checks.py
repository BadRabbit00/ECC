"""PostToolUse checks after Edit / Write / MultiEdit.

fix_encoding  — silent repair (BOM, mixed line endings); blocks only on bytes that are not UTF-8.
check_secrets — secrets in the newly written text → block (the model must remove them now).
check_compose — compose / Dockerfile lint → additional context (advice, never a block).
"""
from __future__ import annotations

import re
from pathlib import Path

from .common import Event, is_test_path, rel

TEXT_EXT_CRLF_OK = {".bat", ".cmd", ".ps1", ".psm1", ".sln", ".vcxproj"}
BOM = b"\xef\xbb\xbf"


def written_text(ev: Event) -> str:
    ti = ev.tool_input
    if "content" in ti:
        return ti.get("content") or ""
    if "new_string" in ti:
        return ti.get("new_string") or ""
    if "edits" in ti:
        return "\n".join(e.get("new_string", "") for e in ti.get("edits") or [])
    return ""


# ---------------------------------------------------------------- encoding

def fix_encoding(path: Path) -> str | None:
    """Returns a block reason, or None. Repairs in place when it can."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:8192]:
        return None                               # binary file: not ours to judge
    fixed = data[len(BOM):] if data.startswith(BOM) else data
    if path.suffix.lower() not in TEXT_EXT_CRLF_OK and b"\r\n" in fixed:
        lone_lf = fixed.count(b"\n") - fixed.count(b"\r\n")
        if lone_lf > 0:                           # mixed endings: normalise to LF
            fixed = fixed.replace(b"\r\n", b"\n")
    try:
        fixed.decode("utf-8")
    except UnicodeDecodeError as exc:
        return (f"`{path.name}` is not valid UTF-8 (byte {exc.start}). Rewrite it as UTF-8; text files in this "
                "setup are UTF-8 with LF line endings.")
    if fixed != data:
        path.write_bytes(fixed)
    return None


# ---------------------------------------------------------------- secrets

SECRET_PATTERNS = [
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key"),
    (re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"), "private key"),
    (re.compile(r"\b(?:ghp|gho|ghs|ghu|ghr)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{50,}"), "GitHub token"),
    (re.compile(r"\bsk-(?:ant-|proj-|live_)?[A-Za-z0-9_-]{24,}"), "API secret key (sk-…)"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "Slack token"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "JWT"),
    (re.compile(r"\b(?:AIza[0-9A-Za-z_-]{35})\b"), "Google API key"),
    (re.compile(r"\b(?:sk|rk)_live_[0-9A-Za-z]{20,}"), "Stripe live key"),
]
GENERIC_ASSIGN = re.compile(
    r"(?i)\b[\w.-]*(password|passwd|secret|token|api[_-]?key|private[_-]?key|access[_-]?key)[\w.-]*\b"
    r"\s*[:=]\s*[\"']([^\"'\s]{8,})[\"']")
URL_PASSWORD = re.compile(r"\b[a-z][a-z0-9+.-]*://[^:/\s@]+:([^@\s/]{6,})@")
PLACEHOLDER = re.compile(r"(?i)change[-_]?me|example|placeholder|dummy|fake|sample|xxx|\*\*\*|<[^>]*>|\$\{|\{\{|"
                         r"^test|^dev[-_]|^local[-_]|your[-_]|redacted|os\.environ|getenv|settings\.|env\(")


def _skip_secret_scan(r: str) -> bool:
    name = Path(r).name
    # .env is where secrets belong (gitignored); sops files are encrypted
    return (name == ".env" or (name.startswith(".env.") and not name.endswith((".example", ".sample", ".template")))
            or name.endswith((".sops.yaml", ".sops.yml", ".enc.yaml", ".enc.json")))


def find_secrets(text: str, r: str) -> list[str]:
    if _skip_secret_scan(r) or "ENC[AES256_GCM" in text:
        return []
    docs = r.endswith((".md", ".mdx", ".rst", ".html"))
    found = [what for rx, what in SECRET_PATTERNS if rx.search(text) and not (docs and what == "JWT")]
    if is_test_path(r) or docs:
        return found                              # tests/docs hold fake values; only real-format keys count
    for m in GENERIC_ASSIGN.finditer(text):
        if not PLACEHOLDER.search(m.group(2)):
            found.append(f"hard-coded {m.group(1).lower()}")
            break
    for m in URL_PASSWORD.finditer(text):
        if not PLACEHOLDER.search(m.group(1)):
            found.append("password inside a connection URL")
            break
    return found


# ---------------------------------------------------------------- compose / Dockerfile

COMPOSE_NAME = re.compile(r"^(docker-)?compose(\.[\w-]+)?\.ya?ml$")
IMAGE_LINE = re.compile(r"^\s*image:\s*[\"']?([^\s\"'#]+)", re.M)
DEPENDS_LIST = re.compile(r"^(\s*)depends_on:\s*(\[|\n\1\s+-\s)", re.M)
FROM_LINE = re.compile(r"^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)", re.M | re.I)


def _unpinned(image: str) -> bool:
    if "@sha256:" in image or image.startswith("${"):
        return False
    tail = image.rsplit("/", 1)[-1]
    return ":" not in tail or tail.endswith(":latest")


def lint_compose(text: str) -> list[str]:
    notes = []
    bad = [i for i in IMAGE_LINE.findall(text) if _unpinned(i)]
    if bad:
        notes.append(f"R-COMPOSE-PINNED: pin an exact tag for {', '.join(sorted(set(bad))[:4])}.")
    in_ports = False
    exposed = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("ports:"):
            in_ports = True
            continue
        if in_ports:
            if s.startswith("-"):
                item = s[1:].strip().strip("\"'")
                if not item.startswith(("127.0.0.1:", "${", "[::1]:")) and item.count(":") >= 1:
                    exposed.append(item)
            elif s and not s.startswith("#"):
                in_ports = False
    if exposed:
        notes.append(f"R-COMPOSE-PORTS: bind published ports to 127.0.0.1 with an overridable host port "
                     f"(`\"127.0.0.1:${{API_HOST_PORT:-18000}}:8000\"`): {', '.join(exposed[:4])}.")
    if DEPENDS_LIST.search(text):
        notes.append("R-COMPOSE-HEALTH: use the map form of depends_on with `condition: service_healthy` "
                     "(or `service_completed_successfully` for one-shot jobs).")
    return notes


def lint_dockerfile(text: str) -> list[str]:
    notes = []
    stages = FROM_LINE.findall(text)
    names = set(re.findall(r"(?im)^\s*FROM\s+\S+\s+AS\s+(\S+)", text))
    bad = [f for f in stages if f.lower() not in {n.lower() for n in names} and f != "scratch" and _unpinned(f)]
    if bad:
        notes.append(f"R-COMPOSE-PINNED: pin base images ({', '.join(bad[:3])}).")
    if not re.search(r"(?im)^\s*USER\s+(?!root\b|0\b)\S+", text):
        notes.append("R-COMPOSE-NONROOT: the final stage has no non-root USER.")
    if re.search(r"(?im)^\s*(CMD|ENTRYPOINT)\s+[^\[\s]", text):
        notes.append("R-COMPOSE-NONROOT: use exec form `CMD [\"/app/bin/api\"]` so SIGTERM reaches the process.")
    if re.search(r"(?im)^\s*(ARG|ENV)\s+\w*(SECRET|TOKEN|PASSWORD|API_KEY)\w*\s*=?\s*\S", text) or \
       re.search(r"(?im)^\s*COPY\s+.*\.env(\s|$)", text):
        notes.append("R-SECRET-NOT-IN-ARTIFACTS: no secrets in ARG/ENV or a copied .env; pass them at runtime.")
    return notes


def lint_file(path: Path, r: str) -> list[str]:
    name = path.name
    if not (COMPOSE_NAME.match(name) or name == "Dockerfile" or name.endswith(".Dockerfile")):
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return lint_compose(text) if COMPOSE_NAME.match(name) else lint_dockerfile(text)


def run(ev: Event) -> tuple[str, str] | None:
    """('block'|'context', message) or None."""
    path_s = ev.tool_input.get("file_path")
    if not path_s:
        return None
    path = Path(path_s)
    if not path.is_absolute():
        path = ev.project_root / path
    r = rel(path, ev.project_root)
    reason = fix_encoding(path)
    if reason:
        return "block", reason
    secrets = find_secrets(written_text(ev), r)
    if secrets:
        return "block", (f"`{r}` now contains what looks like a secret ({', '.join(secrets)}). Remove it now: read it "
                         "from the environment/settings and add the variable to `.env.example` with a `change-me-…` "
                         "value. If it is a real credential, say so in the report: it must be rotated.")
    notes = lint_file(path, r)
    if notes:
        return "context", f"`{r}`: " + " ".join(notes)
    return None
