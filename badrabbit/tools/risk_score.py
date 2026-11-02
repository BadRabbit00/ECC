#!/usr/bin/env python3
"""Risk map calculator for docs/RISK.toml (skill `risk-model`). Stdlib only, Python 3.11+.

The model only fills scores and reasons in RISK.toml. Every number derived from them is computed
here, so the same input always gives the same map.

Usage:
  risk_score.py docs/RISK.toml                 # validate, compute, write docs/RISK.md and docs/RISK.json
  risk_score.py docs/RISK.toml --check         # validate only; exit 1 on any problem
  risk_score.py docs/RISK.toml --out X.md --json X.json

Model (defaults; override in the [model] table of RISK.toml):
  axes        C (confidentiality), I (integrity), A (availability), R (compliance), integers 0–10
  inheritance down (process -> data): A to every used data asset, I only where the process writes
              (access w or rw); a use may set need = { I = n, A = n } instead, when the process depends
              on that data less than its own score.
              up (data -> process): a process gets at least the C and R of the data it uses,
              except secrets (kind = "secret"): keys are scored on their own asset.
  base        max(C, I, A, R)
  bonus       bonus_weight × (sum of the other three axes)        default 0.1
  magnitude   min(10, (base + bonus) × scope)                      scope: one 1.0 · several 1.1 · all 1.2
  risk        magnitude × exposure / 10                            exposure: integer 0–10
  level       first threshold the risk reaches: critical 8 · high 6 · medium 4 · low 2 · info 0
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

AXES = ("C", "I", "A", "R")
UP = ("C", "R")     # data -> process (not from secrets)
DEFAULT_MODEL = {
    "bonus_weight": 0.1,
    "scope": {"one": 1.0, "several": 1.1, "all": 1.2},
    "levels": [[8, "critical"], [6, "high"], [4, "medium"], [2, "low"], [0, "info"]],
}
ID_RE = {"process": re.compile(r"^P-\d{2,3}$"), "data": re.compile(r"^D-\d{2,3}$")}
LEVEL_RU = {"critical": "критический", "high": "высокий", "medium": "средний", "low": "низкий", "info": "информационный"}
AXIS_RU = {"C": "конфиденциальность", "I": "целостность", "A": "доступность", "R": "соответствие требованиям"}


class InputError(Exception):
    pass


@dataclass
class Asset:
    kind: str                      # "process" | "data"
    id: str
    name: str
    scope: str
    exposure: int
    given: dict[str, int]
    why: dict[str, str]
    exposure_why: str
    raw: dict
    final: dict[str, int] = field(default_factory=dict)
    raised: list[str] = field(default_factory=list)
    uses: list[str] = field(default_factory=list)
    links: list[dict] = field(default_factory=list)   # process only: {data, access, need}
    magnitude: float = 0.0
    risk: float = 0.0
    level: str = ""


def load(path: Path) -> tuple[dict, dict, list[Asset]]:
    try:
        doc = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise InputError(f"{path}: not valid TOML: {e}") from e
    model = {**DEFAULT_MODEL, **doc.get("model", {})}
    errors: list[str] = []
    assets: list[Asset] = []
    seen: set[str] = set()
    for kind in ("process", "data"):
        for i, a in enumerate(doc.get(kind, []), 1):
            where = f"[[{kind}]] #{i}"
            aid = str(a.get("id", ""))
            where = f"{where} ({aid or 'no id'})"
            if not ID_RE[kind].match(aid):
                errors.append(f"{where}: id must look like {'P-01' if kind == 'process' else 'D-01'}")
            if aid in seen:
                errors.append(f"{where}: duplicate id")
            seen.add(aid)
            if not str(a.get("name", "")).strip():
                errors.append(f"{where}: name is empty")
            scope = a.get("scope")
            if scope not in model["scope"]:
                errors.append(f"{where}: scope must be one of {sorted(model['scope'])}, got {scope!r}")
            given: dict[str, int] = {}
            why = a.get("why", {}) if isinstance(a.get("why"), dict) else {}
            for ax in AXES:
                v = a.get(ax)
                if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 10:
                    errors.append(f"{where}: {ax} must be an integer 0–10, got {v!r}")
                    v = 0
                given[ax] = v
                if not str(why.get(ax, "")).strip():
                    errors.append(f"{where}: why.{ax} is empty (every score needs a reason)")
            exp = a.get("exposure")
            if not isinstance(exp, int) or isinstance(exp, bool) or not 0 <= exp <= 10:
                errors.append(f"{where}: exposure must be an integer 0–10, got {exp!r}")
                exp = 0
            if not str(a.get("exposure_why", "")).strip():
                errors.append(f"{where}: exposure_why is empty")
            asset = Asset(kind, aid, str(a.get("name", "")), str(scope), exp, given,
                          {k: str(v) for k, v in why.items()}, str(a.get("exposure_why", "")), a)
            if kind == "process":
                for u in a.get("uses", []):
                    if not isinstance(u, dict):
                        errors.append(f"{where}: uses entries must be {{ data = \"D-01\", access = \"rw\" }}")
                        continue
                    did, acc, need = str(u.get("data", "")), u.get("access"), u.get("need", {})
                    if acc not in ("r", "w", "rw"):
                        errors.append(f"{where}: access for {did} must be r, w or rw, got {acc!r}")
                    if not isinstance(need, dict) or any(
                            k not in ("I", "A") or not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 10
                            for k, v in need.items()):
                        errors.append(f"{where}: need for {did} must be {{ I = 0–10, A = 0–10 }}")
                        need = {}
                    asset.uses.append(did)
                    asset.links.append({"data": did, "access": acc, "need": need})
            elif a.get("kind", "data") not in ("data", "file", "secret", "log"):
                errors.append(f"{where}: kind must be data, file, secret or log")
            assets.append(asset)
    by_id = {a.id: a for a in assets}
    used: set[str] = set()
    for p in (a for a in assets if a.kind == "process"):
        if not p.uses:
            errors.append(f"[[process]] {p.id}: uses is empty — a process with no data is not on the map")
        for did in p.uses:
            if did not in by_id or by_id[did].kind != "data":
                errors.append(f"[[process]] {p.id}: uses unknown data asset {did!r}")
            used.add(did)
    for d in (a for a in assets if a.kind == "data"):
        if d.id not in used:
            errors.append(f"[[data]] {d.id}: no process uses it — link it or remove it")
    if not assets:
        errors.append("no [[process]] or [[data]] assets")
    levels = model["levels"]
    if not isinstance(levels, list) or not all(isinstance(x, list) and len(x) == 2 for x in levels):
        errors.append("[model] levels must be a list of [threshold, name] pairs")
    if errors:
        raise InputError("\n".join(errors))
    return doc, model, assets


def compute(model: dict, assets: list[Asset]) -> None:
    by_id = {a.id: a for a in assets}
    for a in assets:
        a.final = dict(a.given)
    # Fixed point: inheritance can chain (a process raises data, data raises another process).
    for _ in range(len(assets) + 1):
        changed = False
        for p in (a for a in assets if a.kind == "process"):
            for link in p.links:
                d = by_id[link["data"]]
                need = dict(link["need"])
                need.setdefault("A", p.final["A"])
                need.setdefault("I", p.final["I"] if "w" in (link["access"] or "") else 0)
                for ax in ("I", "A"):
                    if d.final[ax] < need[ax]:
                        d.raised.append(f"{ax} {d.final[ax]} → {need[ax]} from {p.id} ({p.name})")
                        d.final[ax] = need[ax]
                        changed = True
                if d.raw.get("kind", "data") == "secret":
                    continue
                for ax in UP:
                    if p.final[ax] < d.final[ax]:
                        p.raised.append(f"{ax} {p.final[ax]} → {d.final[ax]} from {d.id} ({d.name})")
                        p.final[ax] = d.final[ax]
                        changed = True
        if not changed:
            break
    levels = sorted(model["levels"], key=lambda x: -x[0])
    for a in assets:
        vals = sorted((a.final[ax] for ax in AXES), reverse=True)
        base, rest = vals[0], sum(vals[1:])
        raw = (base + model["bonus_weight"] * rest) * model["scope"][a.scope]
        a.magnitude = round(min(10.0, raw), 1)
        a.risk = round(a.magnitude * a.exposure / 10, 1)
        a.level = next(name for thr, name in levels if a.risk >= thr)


def heat_bucket(v: float) -> int:
    return min(4, int(v // 2))   # 0–1.9 → 0 … 8–10 → 4


def render_md(doc: dict, model: dict, assets: list[Asset], src: str) -> str:
    title = doc.get("project", {}).get("name", "Project")
    order = sorted(assets, key=lambda a: (-a.risk, -a.magnitude, a.id))
    out = [f"# RISK — {title}", "",
           f"<!-- Generated by risk_score.py from {src}. Do not edit by hand: change {src} and re-run. -->", "",
           "Scale 0–10 for every axis. Magnitude = min(10, (max + "
           f"{model['bonus_weight']} × sum of the other three) × scope). Risk = magnitude × exposure / 10.", ""]
    counts = {name: sum(1 for a in assets if a.level == name) for _, name in model["levels"]}
    out += ["## Summary", "", "| Level | Assets |", "|---|---|"]
    out += [f"| {n} | {c} |" for n, c in counts.items()]
    out += ["", "## Asset map", "", "```mermaid", "flowchart LR"]
    for a in assets:
        label = f"{a.id} {a.name}<br/>M {a.magnitude} · R {a.risk}".replace('"', "'")
        shape = ('(["', '"])') if a.kind == "process" else ('[("', '")]')
        out.append(f'  {a.id.replace("-", "")}{shape[0]}{label}{shape[1]}:::{a.level}')
    for p in (a for a in assets if a.kind == "process"):
        for link in p.links:
            out.append(f"  {p.id.replace('-', '')} -- {link['access']} --> {link['data'].replace('-', '')}")
    out += ["  classDef critical fill:#b42318,color:#fff", "  classDef high fill:#e8772e,color:#111",
            "  classDef medium fill:#f2c94c,color:#111", "  classDef low fill:#9fc5a8,color:#111",
            "  classDef info fill:#d9dee5,color:#111", "```", ""]
    out += ["## Register", "", "| Asset | Type | C | I | A | R | Scope | Magnitude | Exposure | Risk | Level |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for a in order:
        cells = [f"{a.final[ax]}{'↑' if a.final[ax] != a.given[ax] else ''}" for ax in AXES]
        out.append(f"| {a.id} {a.name} | {a.kind} | " + " | ".join(cells) +
                   f" | {a.scope} | {a.magnitude} | {a.exposure} | **{a.risk}** | {a.level} |")
    out += ["", "↑ = raised by inheritance (see below).", "", "## Heat map (magnitude × exposure)", "",
            "| Magnitude \\ Exposure | 0–1 | 2–3 | 4–5 | 6–7 | 8–10 |", "|---|---|---|---|---|---|"]
    names = ["8–10", "6–7", "4–5", "2–3", "0–1"]
    for mb, label in zip(range(4, -1, -1), names):
        row = []
        for eb in range(5):
            ids = [a.id for a in assets if heat_bucket(a.magnitude) == mb and heat_bucket(a.exposure) == eb]
            row.append(", ".join(ids) or "·")
        out.append(f"| **{label}** | " + " | ".join(row) + " |")
    out += ["", "## Reasons", ""]
    for a in order:
        out.append(f"### {a.id} — {a.name}")
        out.append("")
        for ax in AXES:
            out.append(f"- **{ax} {a.given[ax]}** — {a.why.get(ax, '')}")
        out.append(f"- **Exposure {a.exposure}** — {a.exposure_why}")
        if a.raw.get("sources"):
            out.append("- Sources: " + ", ".join(f"`{s}`" for s in a.raw["sources"]))
        out.append("")
    raised = [(a, r) for a in assets for r in a.raised]
    out += ["## Inheritance", ""]
    out += [f"- {a.id}: {r}" for a, r in raised] or ["- none"]
    controls = doc.get("controls", {})
    if controls:
        out += ["", "## Minimum controls by level", ""]
        for _, name in model["levels"]:
            items = controls.get(name, [])
            if items:
                ids = ", ".join(a.id for a in order if a.level == name) or "—"
                out += [f"### {name} ({ids})", ""] + [f"- {c}" for c in items] + [""]
    return "\n".join(out).rstrip() + "\n"


def to_json(doc: dict, model: dict, assets: list[Asset]) -> dict:
    return {
        "project": doc.get("project", {}).get("name", ""),
        "model": model,
        "levels_ru": LEVEL_RU,
        "axes_ru": AXIS_RU,
        "assets": [{
            "id": a.id, "kind": a.kind, "name": a.name, "scope": a.scope,
            "given": a.given, "final": a.final, "raised": a.raised, "uses": a.uses,
            "magnitude": a.magnitude, "exposure": a.exposure, "risk": a.risk, "level": a.level,
        } for a in sorted(assets, key=lambda a: (-a.risk, a.id))],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compute the risk map from docs/RISK.toml.")
    ap.add_argument("toml", type=Path)
    ap.add_argument("--out", type=Path, help="markdown output (default: RISK.md next to the toml)")
    ap.add_argument("--json", type=Path, help="json output for slides (default: RISK.json next to the toml)")
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    args = ap.parse_args(argv)
    try:
        doc, model, assets = load(args.toml)
    except (InputError, OSError) as e:
        print(f"risk_score: input problems:\n{e}", file=sys.stderr)
        return 1
    compute(model, assets)
    if args.check:
        print(f"risk_score: {len(assets)} assets ok")
        return 0
    out = args.out or args.toml.with_name("RISK.md")
    js = args.json or args.toml.with_name("RISK.json")
    out.write_text(render_md(doc, model, assets, args.toml.name), encoding="utf-8")
    js.write_text(json.dumps(to_json(doc, model, assets), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    top = sorted(assets, key=lambda a: -a.risk)[:5]
    print(f"risk_score: {len(assets)} assets → {out} and {js}")
    for a in top:
        print(f"  {a.id} {a.name}: M {a.magnitude} × E {a.exposure} → risk {a.risk} ({a.level})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
