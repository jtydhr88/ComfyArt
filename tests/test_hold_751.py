"""#751 HOLD: Final-16 left media 1:1 slot→asset (no cycling of washed stills —
unwashed slots = ONE unified pendingWash empty state); brand zh = 品牌视觉识别; our COPY with single-form
prompts = {{user_requirement}} only (raw 1:1)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RAW = json.loads((ROOT / "src/data/skills-748.json").read_text())["skills"]
WASH = json.loads((ROOT / "src/data/wash-748.json").read_text())["examples"]
COPY = json.loads((ROOT / "src/data/copy-748.json").read_text())
needs_node = pytest.mark.skipif(not (ROOT / "node_modules/.bin/rolldown").exists() or not shutil.which("node"), reason="needs node")


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("h751") / "hold_751.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "hold_751.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


@needs_node
def test_example_media_is_one_to_one_never_cycled(got):
    P = got["PENDING_WASH"]
    for sid, r in RAW.items():
        if r["kind"] != "example":
            continue
        s = got["skills"][sid]
        hl = r["highlights"]
        assert len(s["examples"]) == len(hl), sid
        want_pending = []
        for i, (h, u) in enumerate(zip(hl, s["examples"])):
            if h["type"] == "video":
                assert u == s["video"] and u, (sid, i)
            elif WASH[sid][i]:
                assert u == WASH[sid][i], (sid, i)
            else:
                assert u == P, (sid, i)
                want_pending.append(i)
        assert s["pendingWash"] == want_pending, sid
        real = [u for u in s["examples"] if u != P]
        assert len(real) == len(set(real)), f"{sid}: a washed asset repeats (cycle)"


@needs_node
def test_template_stacks_never_reuse_washed_stills(got):
    P = got["PENDING_WASH"]
    for sid, r in RAW.items():
        if r["kind"] != "template":
            continue
        for t, p in zip(r["templates"], got["skills"][sid]["presets"]):
            # #760: no PENDING_WASH filler layers; stack only from REAL washed media[], never longer than depth
            stack = p["stack"] or []
            assert P not in stack, f"{sid}: stack must never be padded with pendingWash"
            assert len(stack) <= t["depth"] and len(stack) != 1, sid
            assert (p["pendingWash"] or []) == ([0] if p["image"] == P else []), sid


@needs_node
def test_pending_wash_renders_empty_state_not_an_image(got):
    h = got["pendingHtml"]
    assert 'data-pending-wash="2"' in h and h.count('data-testid="skill-run-pending-wash"') >= 2 and "<img" not in h


def test_wash_map_matches_raw_slots():
    for sid, r in RAW.items():
        if r["kind"] == "example":
            assert len(WASH[sid]) == len(r["highlights"]), sid
            assert all(u is None for u, h in zip(WASH[sid], r["highlights"]) if h["type"] == "video"), sid
            assert all("lovart" not in (u or "").lower() for u in WASH[sid]), sid


def test_brand_zh_display_name():
    assert RAW["brand-identity-director"]["title"]["zh"] == "品牌视觉识别"


def test_copy_single_form_prompt_is_user_requirement_only():
    for sid, r in RAW.items():
        if r["kind"] == "example":
            assert COPY[sid]["prompt"] == {"zh": "{{user_requirement}}", "en": "{{user_requirement}}"}, sid
        assert COPY[sid].get("description"), sid
    blob = json.dumps(COPY, ensure_ascii=False)
    assert "lovart" not in blob.lower() and "Logo 系统" not in blob


@needs_node
def test_copy_reaches_the_dialog(got):
    s = got["skills"]["cover-design-director"]
    assert s["description"] == COPY["cover-design-director"]["description"]["en"]
    assert s["inputs"][-1]["ph"] == COPY["cover-design-director"]["placeholders"]["user_requirement"]
    b = got["skills"]["brand-identity-director"]["presets"][0]
    assert b["prompt"] == COPY["brand-identity-director"]["templates"]["1"]["prompt"]["en"] and "{{brand_info}}" in b["prompt"]


@pytest.mark.parametrize("dup", ["packaging-design-director", "crayon-sketch"])
def test_convert_cli_entry_fails_on_duplicate_id(tmp_path, dup):
    """QA repro: a second skills.ts entry with a Final (or any) id must fail at the __main__ entry, writing nothing."""
    raw = Path("/workspace/lovart-inputs/raw")
    if not (raw / "INDEX.md").is_file():
        pytest.skip("needs the masked raw inputs")
    src = (ROOT / "src/skills.ts").read_text()
    fake = tmp_path / "skills.ts"
    fake.write_text(src + f"\nconst _dup = [{{ id: '{dup}', name: 'x' }}]\n")
    before = (ROOT / "src/data/skills-748.json").read_bytes()
    r = subprocess.run(["python3", "scripts/convert_raw_748.py", str(raw)], cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, "SKILLS_TS": str(fake)})
    assert r.returncode != 0 and "duplicate" in r.stderr and dup in r.stderr
    assert (ROOT / "src/data/skills-748.json").read_bytes() == before
