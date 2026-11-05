#!/usr/bin/env python3
"""#748 — reference raw → OUR structure-only skill data (src/data/skills-748.json).

Source of truth: <raw>/INDEX.md 「Final skill table」 (16 rows: old id | new id | raw file | card type | zh | en).
Reads ONLY those raw files (never HAR, never _har_quarantine).
  template card (collection_card): left = collectionMembers[] (name = member i18n title), stack depth = len(media[]),
      media type = video iff url ends .mp4, ratio = coverWidth/coverHeight; right = that member's template.questions[]
  example card (skill_plaza_card): left = content.highlights[] (explicit mediaType), coverMode single|carousel;
      right = content.template.questions[] (no template → form HOLD, empty)
Never emitted: URLs, stats (tryCount…), long copy (descriptions / placeholders / inputTemplate → COPY-REWRITE.md),
reference ids. Checks: id kebab-case; own skill ids must not collide with a reference skillKey."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QTYPES = {"TEXT": "text", "IMAGE_UPLOAD": "image"}
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
COPY: list = []
WASH: list = []


def _ratio(w, h):
    return round(w / h, 4) if w and h else None


def _kind(url: str) -> str:
    return "video" if (url or "").split("?")[0].lower().endswith(".mp4") else "image"


def _copy(sid, slot, zh, en):
    if zh or en:
        clean = lambda s: (s or "").replace("|", "/").replace("\n", " ")
        COPY.append((sid, slot, clean(zh), clean(en)))


def _title(node: dict) -> dict:
    i = (node.get("content") or {}).get("i18n") or {}
    zh = (i.get("zh") or {}).get("title") or node.get("title")
    en = (i.get("en") or {}).get("title") or ((node.get("extra") or {}).get("i18n_title") or {}).get("en") or zh
    return {"zh": zh, "en": en}


def _questions(sid, slot, tpl: dict) -> list:
    out = []
    for q in (tpl or {}).get("questions") or []:
        i = q.get("i18n") or {}
        zh = (i.get("zh") or {}).get("title") or q["key"]
        r = {"key": q["key"], "type": QTYPES[q["type"]], "required": bool(q.get("required")),
             "label": {"zh": zh, "en": (i.get("en") or {}).get("title") or zh}}
        for k in ("maxLength", "maxCount", "maxSizeMb"):
            if k in (q.get("limits") or {}):
                r[k] = q["limits"][k]
        _copy(sid, f"{slot} {q['key']} placeholder", (i.get("zh") or {}).get("placeholder"), (i.get("en") or {}).get("placeholder"))
        out.append(r)
    it = (tpl or {}).get("inputTemplate") or {}
    _copy(sid, f"{slot} prompt (inputTemplate)", it.get("zh"), it.get("en"))
    return out


def final_table(index: str) -> list[dict]:
    sec = index.split("## Final skill table", 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in sec.splitlines():
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) < 6 or c[0] in ("old id", "") or set(c[0]) <= {"-"}:
            continue
        rows.append({"assetDir": c[0], "id": c[1], "file": re.search(r"`([^`]+)`", c[2]).group(1), "card": c[3], "zh": c[4], "en": c[5]})
    return rows


EXT_REQUIRED = {"character-sheet-design": 1}  # sid -> own templates that MUST be merged (c67ac2aa layout: raw/../own/)


def load_ext(raw: Path, sid: str) -> list:
    """own/<skillKey>.ext.json (sibling of raw/, i.e. /workspace/lovart-inputs/own/): our extra templates after the reference ones.
    A required ext that is missing (wrong dir, file absent) is a HARD FAIL — never silently emit fewer templates."""
    own = raw.parent / "own"
    f = own / f"{sid}.ext.json"
    if not f.exists():
        if sid in EXT_REQUIRED:
            raise ConvertError(f"required ext missing: {f} (own dir {'exists' if own.is_dir() else 'MISSING'})")
        return []
    e = json.loads(f.read_text())
    if e.get("skillKey") != sid or e.get("source") != "comfyart":
        raise ConvertError(f"bad ext file {f.name}: skillKey/source")
    return e.get("collectionMembers") or []


class ConvertError(Exception):
    """Hard failure: never written to src/data."""


UGC_SUFFIX = re.compile(r"-\d{10,}-[0-9a-z]{4,}$")  # publisher `-timestamp-hash`


def app_id(skill_key: str) -> str:
    """#748: app id = English prefix of a UGC skillKey (publisher `-timestamp-hash` stripped); official keys stay full."""
    sid = UGC_SUFFIX.sub("", skill_key)
    if not KEBAB.match(sid):
        raise ConvertError(f"bad id format: {skill_key!r} -> {sid!r}")
    return sid


def check_app_ids(keys: list[str], official: set[str]) -> dict:
    """Fail hard on (1) bad format, (2) a stripped UGC id colliding with an official skillKey, (3) two cards collapsing to one id."""
    out: dict = {}
    for k in keys:
        sid = app_id(k)
        if sid != k and sid in official:
            raise ConvertError(f"UGC id {sid!r} (from {k!r}) collides with official skillKey")
        if sid in out:
            raise ConvertError(f"duplicate app id {sid!r}: {out[sid]!r} and {k!r}")
        out[sid] = k
    return out


def convert(raw: Path) -> dict:
    rows = final_table((raw / "INDEX.md").read_text())
    assert len(rows) == 16, len(rows)
    keys = [r["id"] for r in rows]
    check_app_ids(keys, {k for k in keys if not UGC_SUFFIX.search(k)})
    skills = {}
    for r in rows:
        sid = app_id(r["id"])
        d = json.loads((raw / r["file"]).read_text())
        c = d.get("content") or {}
        ci = c.get("i18n") or {}
        _copy(sid, "skill description", (ci.get("zh") or {}).get("description") or d.get("description"), (ci.get("en") or {}).get("description"))
        s = {"source": "reference", "kind": r["card"], "title": {"zh": r["zh"], "en": r["en"]}, "assetDir": r["assetDir"]}
        if r["card"] == "template":
            tpls = []
            members = [(m, False) for m in d.get("collectionMembers") or []] + [(m, True) for m in load_ext(raw, sid)]  # INDEX rule: raw + own ext
            for ti, (m, own) in enumerate(members):
                mc = m.get("content") or {}
                media = [{"type": _kind(x.get("url")), "ratio": _ratio(x.get("coverWidth"), x.get("coverHeight"))} for x in mc.get("media") or []]
                for j, x in enumerate(media if not own else []):  # ext media are already our washed assets
                    WASH.append((sid, f"template {ti + 1} media {j + 1}", x["type"], x["ratio"]))
                mi = mc.get("i18n") or {}
                _copy(sid, f"template {ti + 1} description", (mi.get("zh") or {}).get("description"), (mi.get("en") or {}).get("description"))
                tpls.append({"name": _title(m), "depth": len(media), "media": media,
                             "inputs": _questions(sid, f"template {ti + 1}", mc.get("template")),
                             **({"source": "comfyart"} if own else {})})
            s["templates"] = tpls
        else:
            hl = sorted(c.get("highlights") or [], key=lambda h: h.get("order", 0))
            s["coverMode"] = c.get("coverMode") or "single"
            s["highlights"] = [{"type": "video" if h.get("mediaType") == "video" else "image", "ratio": _ratio(h.get("width"), h.get("height"))} for h in hl]
            for j, h in enumerate(s["highlights"]):
                WASH.append((sid, f"highlight {j + 1}", h["type"], h["ratio"]))
            qs = _questions(sid, "form", c.get("template"))
            s["inputs"] = qs
            if not c.get("template"):
                s["hold"] = "no content.template in raw yet — form empty until product fetches it"
        cov = c.get("cover")
        if cov:
            k = cov.get("mediaType") if isinstance(cov, dict) else _kind(cov)
            WASH.append((sid, "cover", k, None))
        skills[sid] = s
    return skills


def check_own(skills: dict, own_ids: list[str], feed_ids: frozenset = frozenset()) -> None:
    for oid in own_ids:
        if not KEBAB.match(oid):
            raise ConvertError(f"bad id format: {oid!r}")
        if oid in skills:
            raise ConvertError(f"own id collides with a Final skill id: {oid!r}")
        if oid in feed_ids:
            raise ConvertError(f"own id collides with a reference feed skillKey: {oid!r}")


if __name__ == "__main__":
    raw = Path(sys.argv[1] if len(sys.argv) > 1 else "/workspace/lovart-inputs/raw")
    assert "quarantine" not in str(raw)
    skills = convert(raw)
    src = (ROOT / "src/skills.ts").read_text()
    own = sorted(set(re.findall(r"\{ id: '([^']+)'", src)) - set(skills))
    feed = frozenset(re.sub(r"-<masked>-<masked>$", "", x["skillKey"]) for x in json.loads((raw / "feed-list.json").read_text())["cards"] if x.get("skillKey"))
    check_own(skills, own, feed)
    for sid, n in EXT_REQUIRED.items():
        got = sum(1 for t in skills[sid]["templates"] if t.get("source") == "comfyart")
        if got != n:
            raise ConvertError(f"{sid}: {got} ext templates merged, want {n}")
    if len(skills["character-sheet-design"]["templates"]) != 8:
        raise ConvertError("character-sheet-design must have 8 templates (raw 7 + ext 1)")
    (ROOT / "src/data/skills-748.json").write_text(json.dumps({"source": "scripts/convert_raw_748.py (structure only)", "skills": skills}, ensure_ascii=False, indent=2) + "\n")
    d = ROOT / "docs/design/748"
    d.mkdir(parents=True, exist_ok=True)
    (d / "COPY-REWRITE.md").write_text("\n".join(["# #748 COPY-REWRITE checklist (keys only)", "",
        "Reference copy is NOT in this repo (originals: review-assets `lovart-raw/2026-11-05/COPY-REWRITE-originals.md`).",
        "Product writes our own zh/en per row; until then the app uses our generic copy.", "",
        "| skill | slot | zh (ours) | en (ours) |", "|---|---|---|---|"] +
        [f"| {a} | {b} | TODO | TODO |" for a, b, c, e in COPY]) + "\n")
    orig = os.environ.get("COPY_ORIGINALS_OUT")  # never inside the repo
    if orig:
        assert not Path(orig).resolve().is_relative_to(ROOT.resolve())
        Path(orig).write_text("\n".join(["# #748 reference copy originals (review-assets only, never main)", "", "| skill | slot | zh | en |", "|---|---|---|---|"] +
            [f"| {a} | {b} | {c} | {e} |" for a, b, c, e in COPY]) + "\n")
    (d / "WASH-TODO.md").write_text("\n".join(["# #748 wash TODO (slots on temporary placeholders)", "", "| skill | slot | type | ratio |", "|---|---|---|---|"] +
        [f"| {a} | {b} | {c} | {e} |" for a, b, c, e in WASH]) + "\n")
    print(f"{len(skills)} skills, {sum(len(s.get('templates', [])) for s in skills.values())} templates, {len(WASH)} wash slots, {len(COPY)} copy rows, own ids checked: {len(own)}")
