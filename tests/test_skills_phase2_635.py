"""#635 Phase2-S2: deepen social Fashion UGC (instructions/presets/inputs); PRODUCT-LOCK-PHASE2 §A.
$0 static reads; no network. No fashion-ugc id. Dialog→Agent path still wired."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
DLG = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
HANDOFF = (ROOT / "src/home/handoff.ts").read_text()


def _entries() -> dict[str, str]:
    a = SKILLS_TS.index("export const BUILTIN_SKILLS")
    block = SKILLS_TS[a:next(i for i in (SKILLS_TS.find("\n])\n", a), SKILLS_TS.find("\n]\n", a)) if i >= 0)]
    parts = re.split(r"\n  \{ id: '", block)[1:]
    return {p.split("'", 1)[0]: p for p in parts}


def _instructions(entry: str) -> str:
    m = re.search(r"instructions: ((?:'([^']*)')|(?:`([^`]*)`))", entry)
    assert m, entry[:80]
    return m.group(2) if m.group(2) is not None else m.group(3)


def test_no_fashion_ugc_id_and_social_present():
    ids = list(_entries())
    assert "rednote-cover-maker" in ids
    assert "fashion-ugc" not in ids
    assert "fashion_ugc" not in ids
    assert "#635" in SKILLS_TS and "Fashion UGC" in SKILLS_TS


def test_social_fashion_ugc_presets_at_least_two():
    e = _entries()["rednote-cover-maker"]
    presets = re.findall(r"\bP\('([^']+)',\s*'([^']*)',\s*'([^']*)'", e)
    assert len(presets) >= 2, presets
    ids = {p[0] for p in presets}
    ens = {p[2] for p in presets}
    # feed 1:1 + story 9:16 intent via ids or English titles
    blob = " ".join(ids | ens).lower()
    assert ("feed" in blob or "1:1" in blob or "1x1" in blob), blob
    assert ("story" in blob or "9:16" in blob or "9x16" in blob), blob
    assert any("ugc" in x.lower() or "fashion" in x.lower() for x in ids | ens), (ids, ens)
    body = e.split("presets:", 1)[1].split("inputs:", 1)[0]
    assert len(re.findall(r"Style: ", body)) >= 2
    assert "candid" in body.lower() or "off-duty" in body.lower() or "never staged" in body.lower()


def test_social_instructions_candid_and_rednote_coexist():
    instr = _instructions(_entries()["rednote-cover-maker"])
    low = instr.lower()
    assert "you are a production" in low
    assert ("candid" in low) or ("off-duty" in low) or ("off duty" in low)
    assert ("rednote" in low) or ("lifestyle cover" in low)
    assert ("never" in low and "studio" in low) or ("staged" in low)
    assert r"\n1)" in instr and r"\n5)" in instr
    assert "lovart" not in low


def test_social_inputs_product_person_and_examples_kept():
    e = _entries()["rednote-cover-maker"]
    # #687-1: social dialog = reference-card Upload Files + Additional Details (product/person refs go via the upload)
    assert "inputs: REF_CARD_INPUTS_687 }" in e and "productRef" not in e
    assert "examples: ex541(" in e  # RedNote carousel kept
    assert "cover: cover('rednote-cover-maker')" in e


def test_dialog_to_agent_path_still_wired():
    # SkillRunDialog CTA → skillRunParams(..., mode agent) — same path brand/social share
    assert 'data-testid="skill-run-go"' in DLG
    assert "skillRunParams" in DLG and "onStart" in DLG
    assert "mode: 'agent'" in (ROOT / "src/skills.ts").read_text()
    assert "skill-run-dialog" in DLG or "ca-skillrun" in DLG
    assert "inputs:" in _entries()["rednote-cover-maker"]


def test_no_lovart_string_under_src_skills():
    assert "Lovart" not in SKILLS_TS and "lovart" not in SKILLS_TS
