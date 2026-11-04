"""#673/#735 — Phase2 hide list (D-group 4 after #735 unhide of C): not offered for new selection on any pick-list
(home featured / chips / + menu, Skills page, composer /, agent skill list + read) but still resolvable by id so
saved sessions and cards keep opening. Real src/skills.ts through a node harness (tests/js/hide673). $0."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(not (ROOT / "node_modules/.bin/rolldown").exists() or not shutil.which("node"),
                                reason="needs node + npm install")

# #735 — C-group 5 unhidden; D-group 4 remain hidden until Phase4.
HIDDEN = ["yingzao", "crt-interface", "crayon-sketch", "fabric-collage"]
# Listed builtins after #735: Phase1 + Phase2 Soft (B+C) + Phase3 + interior. D stay in BUILTIN but filtered out.
MAIN_ORDER_45 = [
    "product", "multi-angle", "brand", "character", "logo-material", "packaging", "motion", "meta-ads", "poster",
    "thumbnail", "mobile-ui", "social", "marketing-campaign", "web-product", "banner", "flash-cut-video",
    "style-transfer", "person-swap", "commerce-strategist", "lifestyle-scene",
    "naive-illustration", "logo-abstract", "photo-split-poster", "ppt-visual", "promo-ecommerce",
    "taobao-product", "before-after",
    "anim-2d", "creator-identity", "product-website", "studio-model", "youtube-channel-banner", "ai-model",
    "product-to-packaging", "game-art", "portrait-studio", "premium-website", "animated-poster", "pose-fission",
    "live-promo-decor", "linkedin-banner", "logo-animation", "restaurant-website", "clothing-swap", "interior",
]
# Back-compat alias used by e2e imports.
MAIN_ORDER_40 = MAIN_ORDER_45


@lru_cache(maxsize=1)
def report() -> dict:
    out = Path(os.environ.get("TMPDIR", "/tmp")) / f"hide673-{os.getpid()}.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/hide673/rolldown.config.mjs"], cwd=ROOT,
                   check=True, capture_output=True, env={**os.environ, "OUT": str(out)})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True, timeout=60).stdout)


@needs_node
def test_hide_list_is_the_4_d_and_builtins_keep_all_49() -> None:
    r = report()
    assert r["hidden"] == HIDDEN
    assert len(r["builtinAll"]) == 49 and set(HIDDEN) <= set(r["builtinAll"])  # nothing deleted
    assert [i for i in r["builtinAll"] if i not in HIDDEN] == MAIN_ORDER_45


@needs_node
def test_listed_is_the_other_45_in_main_order() -> None:
    assert report()["listed"] == MAIN_ORDER_45


@needs_node
def test_category_chips_never_contain_hidden() -> None:
    r = report()
    for chip, ids in r["byChip"].items():
        assert not set(ids) & set(HIDDEN), (chip, ids)
    assert r["byChip"]["forYou"] == MAIN_ORDER_45
    # every listed skill still lands in some category chip, in order
    for chip, ids in r["byChip"].items():
        assert ids == [i for i in MAIN_ORDER_45 if i in ids], chip


@needs_node
def test_home_featured_never_contains_hidden() -> None:
    f = report()["featured"]
    assert f and not set(f) & set(HIDDEN)


@needs_node
def test_agent_list_excludes_hidden_and_keeps_order() -> None:
    assert report()["agentList"] == MAIN_ORDER_45


@needs_node
@pytest.mark.parametrize("sid", HIDDEN)
def test_agent_read_of_hidden_resolves_by_id_and_by_name_733(sid) -> None:
    """#733: hiding only affects entry points/UI; the agent's read resolves id and display name (either field)."""
    for how in ("byId", "byName", "idInName", "nameInId"):
        res = report()["hiddenReads"][sid][how]
        assert "error" not in res, (how, res)
        assert res["id"] == sid and res["instructions"], (how, res)


@needs_node
def test_agent_read_listed_still_works_and_unknown_lists_only_listed() -> None:
    r = report()
    assert r["listedReadId"] == "poster"
    err = r["unknown"]["error"]
    assert err.startswith("unknown skill") and not any(f"({h})" in err for h in HIDDEN)


@needs_node
@pytest.mark.parametrize("sid", HIDDEN)
def test_saved_session_or_card_still_resolves_hidden_by_id(sid) -> None:
    res = report()["resolved"][sid]
    assert "error" not in res, res
    assert res["found"] is True and res["name"] and res["params"] is True


COPY = {
    "zh": "该技能暂时下线，旧对话仍可查看；如需继续，请换一个技能。",
    "en": "This skill is temporarily unavailable. You can still view this conversation; pick another skill to continue.",
}


@needs_node
@pytest.mark.parametrize("lang", ["zh", "en"])
@pytest.mark.parametrize("sid", ["yingzao", "crt-interface"])
def test_hidden_skill_refused_at_attach_with_plain_copy_and_no_submit(lang, sid) -> None:
    g = report()["guard"][lang][sid]
    # deep link ?skill= / try-it: no chip (the previous chip is cleared too), the copy is shown
    assert g["attached"] is False and g["linkChip"] is None and g["linkNotice"] == COPY[lang]
    # resend of an old session / sendToAgent safety net: blocked before sendMessage, same copy, no submit
    assert g["blocked"] is True and g["resendNotice"] == COPY[lang] and g["submits"] == 0


@needs_node
@pytest.mark.parametrize("lang", ["zh", "en"])
def test_listed_skill_still_attaches_and_clears_notice(lang) -> None:
    g = report()["guard"][lang]
    assert g["notice"] == COPY[lang]
    assert g["listed"] == {"attached": True, "chip": "poster", "notice": None, "blocked": False}


@needs_node
def test_hidden_skill_guard_makes_zero_network_requests() -> None:
    assert report()["guard"]["requests"] == 0


def test_three_attach_paths_use_the_guard_before_any_send() -> None:
    handoff = (ROOT / "src/home/handoff.ts").read_text()
    h = handoff[handoff.index("const found = skillId"):]
    assert "attachSkill(skill)" in h and h.index("attachSkill(skill)") < h.index("sendToAgent(")
    assert h.index("return\n", h.index("attachSkill(skill)")) < h.index("refreshBot()")  # deep link stops before any request
    panel = (ROOT / "src/ui/AgentPanel.tsx").read_text()
    r = panel[panel.index("async function resend"):]
    assert r.index("blockHiddenSkill(skill)) return") < r.index("sendToAgent(")
    chat = (ROOT / "src/ui/ChatMessage.tsx").read_text()
    t = chat[chat.index("const tryIt"):chat.index("return (", chat.index("const tryIt"))]
    assert "attachSkill(s)" in t and "skillAtom.set" not in t
    agent = (ROOT / "src/agent.ts").read_text()
    body = agent[agent.index("export async function sendToAgent"):]
    assert body.index("blockHiddenSkill(skill)) return") < body.index("sendMessage(")
    comp = (ROOT / "src/ui/Composer.tsx").read_text()
    assert 'data-testid="skill-hidden-notice"' in comp and "useValue(skillNoticeAtom)" in comp


@needs_node
@pytest.mark.parametrize("lang", ["zh", "en"])
def test_agent_read_of_hidden_skill_by_id_is_not_an_error_733(lang) -> None:
    # #733: hiding only affects entry points / UI; reading by id resolves
    assert report()["guard"][lang].get("readErr") is None


SRC = ROOT / "src"


@pytest.mark.parametrize("path,n", [("home/Home.tsx", 2), ("home/Skills.tsx", 2), ("ui/Composer.tsx", 1)])
def test_pick_lists_load_listed_skills(path, n) -> None:
    text = (SRC / path).read_text()
    assert text.count("loadListedSkills().then(setSkills)") == n
    assert "loadSkills().then(setSkills)" not in text


def test_lookups_for_saved_work_keep_full_loadSkills() -> None:
    # handoff (saved / shared start by id) and resend must resolve hidden ids
    assert "(await loadSkills()).find((s) => s.id === skillId)" in (SRC / "home/handoff.ts").read_text()
    assert "(await loadSkills()).find((s) => s.name === skillName)" in (SRC / "ui/AgentPanel.tsx").read_text()
    assert "BUILTIN_SKILLS.find((x) => x.id === s.skillId)" in (SRC / "home/Home.tsx").read_text()


def test_relist_instructions_documented() -> None:
    s = (SRC / "skills.ts").read_text()
    m = re.search(r"TO RE-LIST A SKILL:[^\n]*", s)
    assert m and "delete its id from this array" in m.group(0)
