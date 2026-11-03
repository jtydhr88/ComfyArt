"""#533 / #494-3: home 「用 Skill 快速开始」+「精选」open the same SkillRunDialog as Skills;
+ → 技能 still only adds a chip (#491). Data-driven featured cases from presets[]."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = (ROOT / "src/home/Home.tsx").read_text()
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
PAGE = (ROOT / "src/home/Skills.tsx").read_text()
CSS = (ROOT / "src/styles/home.css").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())


def _home_skill_card_click() -> str:
    m = re.search(
        r'data-testid="home-skill-card"[\s\S]*?onClick=\{\(\) => (.*?)\}',
        HOME,
    )
    assert m, "home-skill-card missing"
    return m.group(1)


def _home_skill_card_click_prop() -> str:
    m = re.search(r'data-testid="home-skill-card"[\s\S]*?onClick=\{(\w+)\}', HOME)
    assert m, "home-skill-card missing"
    return m.group(1)


def _featured_card_click() -> str:
    m = re.search(
        r'data-testid="home-featured-card"[\s\S]*?onClick=\{\(\) => (.*?)\}',
        HOME,
    )
    assert m, "home-featured-card missing"
    return m.group(1)


def _plus_skill_row_click() -> str:
    m = re.search(r'data-testid="home-skill-row" onClick=\{\(\) => \{(.*?)\}\}>', HOME, re.S)
    assert m, "home-skill-row missing"
    return m.group(1)


def test_home_imports_same_dialog_as_skills() -> None:
    assert "import { SkillRunDialog } from '../ui/SkillRunDialog'" in HOME
    assert "import { SkillRunDialog } from '../ui/SkillRunDialog'" in PAGE
    assert "hasSkillDialog" in HOME and "skillFeaturedCases" in HOME and "skillQuickStartCover" in HOME


def test_quick_start_opens_dialog_not_direct_project() -> None:
    # skills-cut1: HomeSkillCard is a component; it forwards onTry and the row passes trySkill(s)
    assert _home_skill_card_click_prop() == "onTry"
    assert "<HomeSkillCard key={s.id} skill={s} onTry={() => trySkill(s)} />" in HOME
    body = HOME.split("const trySkill = (s: Skill", 1)[1].split("\n  }\n", 1)[0]
    assert "if (hasSkillDialog(s)) { setRunning({ id: s.id, preset }); return }" in body
    assert body.index("hasSkillDialog(s)") < body.index("newProject({ skill: s.id })")  # direct start only without dialog
    assert 'data-testid="home-start-skill"' in HOME
    assert 'data-testid="home-skill-grid"' in HOME
    assert "startFromSkill" in HOME and "ca-skillgrid" in HOME  # keep #460 entry surface


def test_featured_opens_dialog_with_preset() -> None:
    click = _featured_card_click()
    assert "trySkill(s, p?.id ?? null)" in click
    assert 'data-testid="home-featured"' in HOME
    assert 'data-testid="home-featured-card"' in HOME
    assert "data-preset={p?.id}" in HOME
    assert "home.skillCase" in HOME and "skillRun.start" in HOME
    assert "skillFeaturedCases(shown)" in HOME


def test_plus_skills_still_chip_only() -> None:
    click = _plus_skill_row_click()
    assert "setPicked(s)" in click
    for bad in ("trySkill", "setRunning", "SkillRunDialog", "newProject", "startProject", "openView"):
        assert bad not in click, bad


def test_featured_helper_is_data_driven() -> None:
    assert "export function skillFeaturedCases" in SKILLS_TS
    assert "preset.image" in SKILLS_TS  # #580: template-type tiles use the preset's own image
    helper = SKILLS_TS.split("export function skillFeaturedCases", 1)[1].split("\nexport ", 1)[0]
    low = helper.lower()
    for bad in ("'poster'", '"poster"', "'product'", "'demo'", '"demo"'):
        assert bad not in helper, bad
    assert "lovart" not in low


def test_copy_and_style() -> None:
    assert ZH["home.startFromSkill"] == "用 Skill 快速开始"
    assert EN["home.startFromSkill"] == "Start with a Skill"
    assert ZH["home.featured"] == "精选" and EN["home.featured"] == "Featured"
    assert ZH["home.skillCase"] == "Skill 案例" and EN["home.skillCase"] == "Skill case"
    assert ".ca-featured" in CSS and ".ca-featured__go" in CSS
    # #537: waterfall columns (Loomic pack); aspect via inline style, not fixed 231/173 grid
    assert "ca-featured--waterfall" in CSS or "ca-featured--waterfall" in HOME
    assert ".ca-featured__col" in CSS
    assert "scale(0.85)" in CSS  # hover 「开始制作」 pill


def test_mutation_direct_newproject_on_home_cards_fails() -> None:
    """If someone rewires home skill cards back to newProject({skill}), this assertion fails."""
    body = HOME.split('data-testid="home-start-skill"', 1)[1].split('data-testid="home-featured"', 1)[0]
    assert "newProject({ skill: s.id })" not in body
    feat = HOME.split('data-testid="home-featured"', 1)[1].split("{runSkill &&", 1)[0]
    assert "newProject(" not in feat
