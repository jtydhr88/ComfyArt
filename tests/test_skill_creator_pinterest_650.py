"""#650 follow-up: Pinterest must not leak into the Skill Creator surface, and the
creation-complete state (Skill ready → Skill Created + card) must stay wired."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOC = ROOT / "src" / "locales"
EXPECTED_PINTEREST_KEYS = {
    "home.tab.pinterest",
    "home.tabPanel.pinterest.title",
    "home.tabPanel.pinterest.text",
    "home.tabPanel.pinterest.action",
}


def _flat(d, p=""):
    for k, v in d.items():
        if isinstance(v, dict):
            yield from _flat(v, f"{p}{k}.")
        else:
            yield f"{p}{k}", v


def _locale(lang):
    return dict(_flat(json.loads((LOC / f"{lang}.json").read_text(encoding="utf-8"))))


def test_en_agent_panel_has_no_pinterest():
    en = _locale("en")
    panel = {k: v for k, v in en.items() if k.startswith("agentPanel.")}
    assert panel, "agentPanel.* keys missing"
    bad = {k: v for k, v in panel.items() if "pinterest" in f"{k} {v}".lower()}
    assert bad == {}


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_pinterest_keys_only_the_four_home_keys(lang):
    loc = _locale(lang)
    keys = {k for k in loc if "pinterest" in k.lower()}
    assert keys == EXPECTED_PINTEREST_KEYS
    assert len(keys) == 4
    assert all(k.startswith("home.") for k in keys)
    # no non-home string mentions Pinterest either
    leaked = {k for k, v in loc.items() if not k.startswith("home.") and "pinterest" in str(v).lower()}
    assert leaked == set()


def test_composer_source_and_strings_have_no_pinterest():
    src = (ROOT / "src" / "ui" / "Composer.tsx").read_text(encoding="utf-8")
    assert "pinterest" not in src.lower()
    used = set(re.findall(r"""\bt\(\s*['"]([\w.\-]+)['"]""", src))
    assert used, "Composer uses no t() keys?"
    for lang in ("en", "zh"):
        loc = _locale(lang)
        for k in used | {k for k in loc if k.startswith("composer.")}:
            assert "pinterest" not in f"{k} {loc.get(k, '')}".lower(), (lang, k)


@pytest.mark.parametrize("lang,ready,created,preview,tryit", [
    ("en", "Skill ready", "Skill Created", "Preview", "Try this skill"),
    ("zh", "技能加载完成", "技能已创建", "预览", "试用此技能"),
])
def test_skill_created_locale_strings(lang, ready, created, preview, tryit):
    loc = _locale(lang)
    assert loc["chatMessage.skillReady"] == ready
    assert loc["chatMessage.skillCreated"] == created
    assert loc["chatMessage.skillPreview"] == preview
    assert loc["chatMessage.tryThisSkill"] == tryit


def test_skill_created_wiring_in_chat_message():
    src = (ROOT / "src" / "ui" / "ChatMessage.tsx").read_text(encoding="utf-8")
    assert "'skill_created'" in src
    assert "export function skillCreatedOf" in src
    assert "export function SkillCreatedCard" in src
    for tid in ("skill-created-card", "skill-created-name", "skill-created-desc",
                "skill-created-preview", "skill-created-try"):
        assert f'data-testid="{tid}"' in src, tid
    assert "t('chatMessage.skillCreated')" in src
