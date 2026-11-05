"""#641 Phase3-S2: upgrade `thumbnail` for YouTube 16:9 CTR covers.
Dialog parity: Upload + Additional only (no presets / no required titleCopy).
PRODUCT-LOCK-PHASE3 thumbnail row. No new skill id. $0 static reads; no network."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
ZH = (ROOT / "src/locales/zh.json").read_text()
EN = (ROOT / "src/locales/en.json").read_text()


def _entries() -> dict[str, str]:
    a = SKILLS_TS.index("export const BUILTIN_SKILLS")
    block = SKILLS_TS[a:next(i for i in (SKILLS_TS.find("\n])\n", a), SKILLS_TS.find("\n]\n", a)) if i >= 0)]
    parts = re.split(r"\n  \{ id: '", block)[1:]
    return {p.split("'", 1)[0]: p for p in parts}


def _instructions(entry: str) -> str:
    m = re.search(r"instructions: ((?:'([^']*)')|(?:`([^`]*)`))", entry)
    assert m, entry[:80]
    return m.group(2) if m.group(2) is not None else m.group(3)


def test_no_youtube_thumbnail_id_and_thumbnail_present():
    ids = list(_entries())
    assert "cover-design-director" in ids
    assert "youtube-thumbnail" not in ids
    assert "youtube_thumbnail" not in ids
    assert "#641" in SKILLS_TS and "Phase3-S2" in SKILLS_TS
    assert "WASH_641" not in SKILLS_TS and "cover641" not in SKILLS_TS and "641/wash" not in SKILLS_TS


def test_thumbnail_dialog_parity_upload_additional():
    e = _entries()["cover-design-director"]
    assert len(re.findall(r"\bP\('", e)) == 0, e
    assert "presets:" not in e
    assert "presetChips" not in e
    assert "titleCopy" not in e
    assert "inputs: EFFECT_INPUTS" in e
    assert "yt-face" not in e and "yt-type" not in e and "yt-contrast" not in e


def test_thumbnail_instructions_yt_ctr_triad():
    instr = _instructions(_entries()["cover-design-director"])
    low = instr.lower()
    assert "you are a production" in low
    assert "youtube" in low and "16:9" in low
    assert ("expressive" in low) or ("face" in low) or ("reaction" in low)
    assert ("three-word" in low) or ("three word" in low) or ("3-word" in low) or ("three punchy" in low)
    assert "contrast" in low
    assert r"\n1)" in instr and r"\n5)" in instr
    assert "lovart" not in low


def test_thumbnail_inputs_media_and_effect_inputs():
    e = _entries()["cover-design-director"]
    assert "titleCopy" not in e
    assert "inputs: EFFECT_INPUTS" in e
    assert "cover: cover643('cover-design-director')" in e
    assert "featured: feat643('cover-design-director'" in e
    assert "ex643('cover-design-director'" in e
    assert "video: video('cover-design-director')" in e
    assert "examples: [video('cover-design-director'), ...ex643(" in e
    assert "quickStartCover: quickStartCover('cover-design-director')" in e
    assert "WASH_643" in SKILLS_TS and "643/wash" in SKILLS_TS


def test_dialog_to_agent_path_still_wired():
    dlg = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
    assert 'data-testid="skill-run-go"' in dlg
    assert "skillRunParams" in dlg and "onStart" in dlg
    assert "mode: 'agent'" in SKILLS_TS
    assert "inputs:" in _entries()["cover-design-director"]


def test_no_lovart_string_under_src_skills():
    assert "Lovart" not in SKILLS_TS and "lovart" not in SKILLS_TS


def test_locales_desc_mentions_youtube():
    assert "YouTube" in ZH or "youtube" in ZH.lower()
    assert "YouTube" in EN
    assert "skills.desc.cover-design-director" in ZH and "skills.desc.cover-design-director" in EN


def test_thumbnail_dialog_states_and_shelf_ratio():
    """Design lock: dialog state hooks + 16:9 shelf cover (chips infra kept for other skills; thumbnail uses EFFECT_INPUTS)."""
    dlg = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
    ex = (ROOT / "src/ui/SkillExamples.tsx").read_text()
    css = (ROOT / "src/styles/home.css").read_text()
    wall = (ROOT / "src/home/Skills.tsx").read_text()
    assert 'data-testid="skill-run-preset-chips"' in dlg
    assert 'data-testid="skill-run-preset-chip"' in dlg
    assert "setPreset(p.id)" in dlg  # chip switch stays in the dialog
    assert 'data-testid="skill-run-field-error"' in dlg
    assert "tried && missing.includes(f.key)" in dlg  # #687: errors only after 开始制作 click
    assert 'disabled={!!uploading}' in dlg and "setTried(true)" in dlg
    close = next(ln for ln in dlg.splitlines() if "skill-run-close" in ln)
    assert "disabled" not in close
    assert 'data-testid="skill-run-run-error"' in dlg
    assert 'data-testid="skill-run-upload-retry"' in dlg
    assert 'data-testid="skill-run-examples-empty"' in ex
    assert "skillRun.noExamples" in ex
    assert 'data-testid="skill-run-example-loading"' in ex
    assert 'data-testid="skill-run-example-retry"' in ex
    assert 'data-count={examples.length}' in ex
    assert '"skillRun.noExamples": "暂无示例"' in ZH
    assert '"skillRun.noExamples": "No examples yet"' in EN
    assert "aspect-ratio: 231 / 173" in css
    assert '.ca-swall__card[data-skill="cover-design-director"] .ca-swall__cover { aspect-ratio: 16 / 9; }' in css
    assert 'data-skill={skill.id}' in wall
    assert "skills-card-author" in wall and "skills-card-usage" in wall and "skills-card-video" in wall
    assert "Lovart" not in dlg and "lovart" not in dlg
    assert "Lovart" not in ex and "lovart" not in ex
