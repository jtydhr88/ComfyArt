"""#592 Phase1-S2: upgrade-9 production instructions / presets / inputs (no empty shells).
$0 static reads; no network."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_TS = (ROOT / "src/skills.ts").read_text()

UPGRADE = ["brand", "packaging", "poster", "product", "character", "social", "motion", "banner", "thumbnail"]
EFFECT = {"poster", "banner", "thumbnail"}  # #641: thumbnail dialog parity → EFFECT_INPUTS
TEMPLATE_COUNTS = {"product": 6, "brand": 6, "packaging": 5, "character": 8, "motion": 0}


def _entries() -> dict[str, str]:
    a = SKILLS_TS.index("export const BUILTIN_SKILLS")
    block = SKILLS_TS[a:next(i for i in (SKILLS_TS.find("\n])\n", a), SKILLS_TS.find("\n]\n", a)) if i >= 0)]
    parts = re.split(r"\n  \{ id: '", block)[1:]
    return {p.split("'", 1)[0]: p for p in parts}


def _instructions(entry: str) -> str:
    m = re.search(r"instructions: ((?:'([^']*)')|(?:`([^`]*)`))", entry)
    assert m, entry[:80]
    return m.group(2) if m.group(2) is not None else m.group(3)


def test_upgrade9_instructions_are_multistep_production():
    entries = _entries()
    for sid in UPGRADE:
        instr = _instructions(entries[sid])
        assert "You are a production" in instr, sid
        # Quoted TS string stores steps as backslash-n escapes.
        assert r"\n1)" in instr and r"\n2)" in instr and r"\n5)" in instr, sid
        assert "demo" not in instr.lower()
        assert len(instr) >= 400, (sid, len(instr))


def test_upgrade9_presets_examples_inputs_complete():
    entries = _entries()
    for sid in UPGRADE:
        e = entries[sid]
        assert "inputs:" in e, sid
        if sid in EFFECT:
            assert ("inputs: REF_CARD_INPUTS_687 }" if sid in ("poster", "banner", "interior") else "inputs: EFFECT_INPUTS }") in e, sid  # #687
            assert len(re.findall(r"\bP\('", e)) == 0, sid
            if sid == "thumbnail":
                assert "titleCopy" not in e, sid
                assert "cover: cover643('thumbnail')" in e and "ex643(" in e and "feat643('thumbnail'" in e, sid
                assert "video: video('thumbnail')" in e, sid
                assert ("examples: [video(" in e and "ex643(" in e), sid
            else:
                assert ("examples: ex541(" in e) or ("examples: [video(" in e and "ex541(" in e), sid  # #575 video lead ok
        elif sid == "social":
            # #635 Phase2-S2: Fashion UGC presets coexist with RedNote examples; custom inputs
            assert "examples: ex541(" in e, sid
            assert "inputs: EFFECT_INPUTS" not in e, sid
            assert len(re.findall(r"\bP\('", e)) >= 2, sid
            body = e.split("presets:", 1)[1].split("inputs:", 1)[0]
            assert len(re.findall(r"Style: |Focus on |Template: ", body)) >= 2, sid
        else:
            n = TEMPLATE_COUNTS[sid]
            if not n:  # #687: motion off-topic templates removed
                assert "presets:" not in e and len(re.findall(r"\bP\('", e)) == 0, sid
                continue
            assert len(re.findall(r"\bP\('", e)) == n, sid
            # Count only preset prompt prefixes, not instruction prose
            body = e.split("presets:", 1)[1].split("inputs:", 1)[0]
            assert len(re.findall(r"Style: |Focus on |Template: ", body)) == n, sid


def test_upgrade9_keeps_existing_media_pins():
    entries = _entries()
    for sid in UPGRADE:
        e = entries[sid]
        if sid == "thumbnail":
            # #643 true-wash cover/featured/examples + Phase1 video hover + quickStart
            assert "cover: cover643('thumbnail')" in e, sid
            assert "video: video('thumbnail')" in e, sid
            assert "feat643('thumbnail'" in e, sid
            assert "quickStartCover: quickStartCover('thumbnail')" in e, sid
        else:
            assert f"cover: cover('{sid}')" in e, sid
            assert f"video: video('{sid}')" in e, sid
            assert f"featured: feedCovers('{sid}')" in e, sid


def test_no_competitor_brand_in_src_skills():
    assert "Lovart" not in SKILLS_TS and "lovart" not in SKILLS_TS
