"""#494-2: each skill's own input dialog + presets, through the real src/skills.ts (tests/js/skill_dialog_494.ts),
plus wiring greps for the Skills page / dialog / handoff. Harness needs node + npm install; $0, no network."""
from __future__ import annotations

import json
from tests.lovart_fields_687 import RAW_748
from tests.skill_ids_748 import FINAL_IDS, asset_dir
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "src/home/Skills.tsx").read_text()
DLG = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
EDIT = (ROOT / "src/ui/SkillsDialog.tsx").read_text()
HANDOFF = (ROOT / "src/home/handoff.ts").read_text()
CSS = (ROOT / "src/styles/home.css").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
needs_node = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("m4942") / "skill_dialog_494.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "skill_dialog_494.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


EFFECT = ("poster-differentiated-compiler", "banner-design-director", "interior-architectural-visualization", "cover-design-director")
# #636 C5 + #664 NEW19 share NEARMISS_INPUTS (Upload + Additional, none required)
NEARMISS = ("naive-illustration", "logo-abstract", "photo-split-poster", "ppt-visual", "promo-ecommerce",
            "taobao-product", "before-after", "anim-2d", "creator-identity", "product-website", "studio-model",
            "youtube-channel-banner", "ai-model", "product-to-packaging", "game-art", "portrait-studio", "premium-website",
            "animated-poster", "pose-fission", "live-promo-decor", "linkedin-banner", "logo-animation", "restaurant-website", "clothing-swap")  # #641 thumbnail dialog parity → EFFECT_INPUTS
COUNTS = {
          "flash-cut-video": 3, "style-transfer": 3, "person-swap": 3, "commerce-strategist": 3, "lifestyle-scene": 3,
          "naive-illustration": 2, "logo-abstract": 2, "photo-split-poster": 2, "ppt-visual": 3, "promo-ecommerce": 2,
          "yingzao": 2, "crt-interface": 3, "crayon-sketch": 2, "fabric-collage": 2,  # #634 Phase2-S1
          # #640 Phase3-S1 NEW19
          "taobao-product": 3, "before-after": 3, "anim-2d": 2, "creator-identity": 3, "product-website": 2,
          "studio-model": 3, "youtube-channel-banner": 2, "ai-model": 3, "product-to-packaging": 3,
          "game-art": 3, "portrait-studio": 2, "premium-website": 2, "animated-poster": 2, "pose-fission": 3,
          "live-promo-decor": 3, "linkedin-banner": 2, "logo-animation": 2, "restaurant-website": 2, "clothing-swap": 3}
COUNTS.update({sid: len(RAW_748[sid].get("templates", [])) for sid in FINAL_IDS})  # #748 Final: template cards = raw template count; example cards = 0



@needs_node
def test_every_field_is_bilingual_data(got):
    assert len(got["fields"]) == 49  # custom-workflow removed; #591 + #634 + #640 Phase3-S1
    for sid, fields in got["fields"].items():
        assert fields, sid
        # #569: effect skills (upload + note) and character carry no required field, like the reference.
        if sid in FINAL_IDS:  # #748 Final: required flags come from the raw
            assert any(req for _, _, req, *_ in fields) == any(q["required"] for q in (RAW_748[sid]["templates"][0]["inputs"] if RAW_748[sid]["kind"] == "template" else RAW_748[sid]["inputs"])), sid
            continue
        assert any(req for _, _, req, *_ in fields) == (sid not in EFFECT and sid not in NEARMISS and sid not in {"character-sheet-design", "rednote-cover-maker", "universal-multi-angle-grid", "meta-ads-creative-director", "marketing-campaign-generator", "web-product-visual-design", "mobile-app-visual-design"}), sid  # #687-1 reference-card fields optional  # #635 social optional refs; #691 multi-angle upload optional
        for key, typ, req, zh, en, ph in fields:
            assert typ in {"text", "textarea", "select", "image"} and zh and en, (sid, key)
            if req and typ in {"text", "textarea"}:
                assert ph, (sid, key)
    keys = {sid: [f[0] for f in fs] for sid, fs in got["fields"].items()}
    assert keys["poster-differentiated-compiler"] != keys["product-tvc-advertisement-generator"] and keys["brand-identity-director"] != keys["motion-poster-generator"]  # each skill its own dialog (#687: brand now = reference-card Upload + Additional, like poster)


@needs_node
def test_presets_have_prompts(got):
    for sid, ps in got["presets"].items():
        assert len(ps) == COUNTS.get(sid, 0), sid  # #541 AC rev 2 → #569
        assert len({i for i, _, _ in ps}) == len(ps), sid  # unique ids
        assert all(en and prompt for _, en, prompt in ps), sid


@needs_node
def test_builtin_preset_images_unique(got):
    # #569 template washes stay unique; #594 new-6 have no preset.image — presetImage falls back to covers-v4.
    imgs = [u for u in got["builtinPresetImgs"] if u]
    washed = [u for u in imgs if "569/wash/" in u or "541/wash/" in u]
    covers = [u for u in imgs if "494/covers-v4/" in u]
    assert len(washed) == 25  # #748 Final: product 6 washed (+1 SaaS placeholder) / brand 6 / packaging 5 + character 8 (raw 7 + ext)
    assert all("raw.githubusercontent.com/ganjmeng/ComfyArt/" in u for u in washed)
    assert sum("569/wash/character/templates/" in u for u in washed) == 8 and sum("569/wash/motion/templates/" in u for u in washed) == 0
    assert sum("541/wash/product/" in u for u in washed) == 6
    assert sum("541/wash/brand/" in u for u in washed) == 6 and sum("541/wash/packaging/" in u for u in washed) == 5
    assert len(set(washed)) == 25  # no shared cover fallback across washed presets
    assert covers == []  # #748 Final: the new-6 are example cards now (no presets → no cover fallback)


@needs_node
def test_defaults_and_required(got):
    assert got["posterDefaults"] == {"user_image": "", "user_requirement": ""}  # #748 Final example card: shared form
    assert got["brandDefaults"] == {"brand_info": "", "subject_image": "", "visual_direction": ""}  # #748 Final: template 1 questions
    assert got["brandMissing"] == ["brand_info"] and got["brandFilled"] == []
    assert got["posterPresets"] == 0
    assert got["cwDefaults"] == {"brief": ""}
    assert got["posterMissing"] == ["user_image", "user_requirement"] and got["posterFilled"] == ["user_image"]  # #748: both required
    assert got["cwMissing"] == ["brief"]  # whitespace is empty
    assert got["dialog"] == [True, True, False, True]  # old personal skill: no dialog, main's direct start


@needs_node
def test_preset_prompt_appended_after_instructions(got):
    assert got["withPreset"] == got["brandInstr"].rstrip() + "\n\n" + got["secondPrompt"]
    assert got["withUnknown"] and got["withNull"]
    assert got["presetDefault"] != got["presetPick"]
    assert got["presetImg"] and got["presetImg"] != "/comfyart/skills/brand/cover.webp"
    assert "541/wash/brand/brand__handmade.webp" in got["presetImg"]
    assert len(set(got["brandPresetImgs"])) == 6  # brand six thumbs distinct
    assert all(u and "541/wash/brand/" in u for u in got["brandPresetImgs"])


@needs_node
def test_run_params(got):
    p = got["brandRun"]
    assert p["skill"] == "brand-identity-director" and p["mode"] == "agent" and p["ref"] == ["/view?f=a.png"]
    assert p["preset"] and p["preset"] != got["presetDefault"]
    assert p["ask"].splitlines()[0].endswith(": Autumn launch")
    q = got["posterNoPreset"]
    assert q["skill"] == "poster-differentiated-compiler" and q["ref"] == ["/view?f=a.png"] and "preset" not in q and q["ask"].endswith(": Autumn launch")
    assert got["cwRun"] == {"skill": "brief-only", "mode": "agent", "ask": got["cwRun"]["ask"]}
    assert got["cwRun"]["ask"].endswith(": Upscale my photo")
    assert got["emptyRun"]["ask"] == "Old" and "preset" not in got["emptyRun"]


def test_handoff_applies_preset():
    assert "'preset'" in HANDOFF and "withPreset(found, presetId)" in HANDOFF


def test_dialog_is_data_driven():
    assert "skill.inputs" in DLG and "skill.presets" in DLG
    assert "ca-skillrun__left" in DLG and "ca-skillrun__right" in DLG and "ca-skillrun__grid" in DLG
    assert "ca-skillrun__field" in DLG  # right form: one column wrapper per input
    assert 'className="ca-skillform"' in DLG and 'data-testid="skill-run-form"' in DLG
    assert "skillRun.start" in DLG and "skillRun.currentTemplate" in DLG
    # #494-2 对照结构: left column title / author / description above the template grid
    assert 'data-testid="skill-run-head"' in DLG and 'data-testid="skill-run-title"' in DLG
    assert 'data-testid="skill-run-author"' in DLG and 'data-testid="skill-run-desc"' in DLG
    assert "ca-skillrun__head" in DLG and "ca-skillrun__title" in DLG and "ca-skillrun__desc" in DLG
    for bad in ("'poster-differentiated-compiler'", "'product-tvc-advertisement-generator'", "topic", "headline"):
        assert bad not in DLG, bad
    # #687 — Start stays clickable; onStart gates on missing inputs and only then reveals errors (tried).
    assert "if (missing.length) { setTried(true)" in DLG and "skillRunParams(skill, values, preset)" in DLG
    # 「详情」 keeps main's #484 edit page — no new detail route.
    assert "openSkillEditor(skill.id)" in DLG
    # #687 P0: builtins never reach the editor — 「详情」 gated on skill.custom.
    assert "{skill.custom === true && <button" in DLG and 'data-testid="skill-run-detail"' in DLG


def test_page_wiring():
    # #494-3: tryCard owns the dialog-vs-direct rule (was inlined at the call site)
    assert "const tryCard = (s: Skill) => (hasSkillDialog(s) ? setRunning({ id: s.id, preset: null }) : startDirect(s))" in PAGE
    assert "openSkillEditor(landing.id)" in PAGE and "openSkillDetail" not in PAGE
    assert 'data-testid="skills-card-try"' in PAGE and "home.skillsTryThis" in PAGE
    assert "onClick={row ? undefined : onTry}" in PAGE  # cover + title open the same dialog
    # Explore still has author; Personal row layout has none.
    assert 'data-testid="skills-card-author"' in PAGE
    assert PAGE.count('layout="row"') >= 2 and "skills-group-yours" in PAGE and "skills-group-loomi" in PAGE
    assert "ca-swall__card--row" in PAGE and "ca-swall--rows" in PAGE
    assert "home.skillsCreatedByYou" in PAGE and "home.skillsCreatedByLoomi" in PAGE
    assert "home.skillsEmptyLoomi" in PAGE
    assert "!s.learned" in PAGE and "!!s.learned" in PAGE  # same learned[] store #465 uses
    for bad in ("views", "likes", "Icons.heart", "skill-guide", "skillDetail", "SkillDetail", "guideNext"):
        assert bad not in PAGE, bad
    # one file card, reused by the #484 edit form (not a second SKILL.md box on a detail page)
    assert EDIT.count('className="ca-skillform__box"') == 1 and "export function SkillFileBox" in EDIT
    assert "skillDetailAtom" not in SKILLS_TS and "skillGuideAtom" not in SKILLS_TS


def test_copy_and_dialog_style():
    assert ZH["home.skillsTryThis"] == "试用此技能" and EN["home.skillsTryThis"] == "Try this skill"
    assert ZH["skillRun.start"] == "开始制作" and EN["skillRun.start"] == "Start making"  # #593 dual-column CTA gold
    assert ZH["skillRun.header"] == "开始创作" and EN["skillRun.header"] == "Start Creating"  # #601 header ≠ CTA
    assert ZH["skillRun.select"] == "选择" and EN["skillRun.select"] == "Select"
    assert (ZH["home.skillsCreatedByYou"], ZH["home.skillsCreatedByLoomi"]) == ("你创建的", "Loomi 创建的")
    assert (EN["home.skillsCreatedByYou"], EN["home.skillsCreatedByLoomi"]) == ("Created by you", "Created by Loomi")
    assert "暂无自动总结的技能" in ZH["home.skillsEmptyLoomi"] and "No auto-summarized skills yet" in EN["home.skillsEmptyLoomi"]
    assert "Loomi" in ZH["home.skillsEmptyLoomi"] and "Loomi" in EN["home.skillsEmptyLoomi"]
    for k in ("home.skillsTryThis", "home.skillsCreatedByYou", "home.skillsCreatedByLoomi", "home.skillsEmptyLoomi",
              "skillRun.header", "skillRun.start", "skillRun.templates", "skillRun.currentTemplate", "skillRun.pickLeft", "skillRun.detail",
              "skillRun.select"):
        assert k in ZH and k in EN, k
    assert "skillDetail." not in " ".join(k for k in ZH if k.startswith("skillDetail"))
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in CSS
    assert "aspect-ratio: 160 / 120" in CSS  # template cells ~160×120, not 1:1
    assert "inset 0 0 0 1px var(--ca-text)" in CSS  # selected ring 1px
    assert ".ca-skillrun__left" in CSS and ".ca-skillrun__right" in CSS
    assert ".ca-skillrun__head" in CSS and ".ca-skillrun__author" in CSS
    # right form: ca-skillform + field column; every control width 100% (Loomic .field pattern)
    assert ".ca-skillrun__body > .ca-skillform" in CSS
    assert ".ca-skillrun__field" in CSS and "width: 100%" in CSS
    assert ".ca-skillrun .ca-skillform .ca-skillrun__field > .ca-panel__input" in CSS
    assert ".ca-skillrun__field > .ca-skillform__label" in CSS and "display: block" in CSS
    assert "ca-skillrun__templates { flex: 1 1 auto; min-height: 0; overflow: auto; }" in CSS
    assert ".ca-swall__card--row" in CSS and "width: 72px; height: 72px" in CSS
    assert ".ca-swall__try" in CSS
    # #494 anim locks (design beziers): hover 150ms .4,0,.2,1; modal 250ms .2,0,0,1; select none; go color 150ms ease no scale
    assert "150ms" in CSS and "ca-skillrun__pick" in CSS and "ca-skillrun__zoom" in CSS
    assert "ca-skillrun-in" in CSS and "250ms" in CSS and "scale(0.96)" in CSS
    assert "cubic-bezier(.4, 0, .2, 1)" in CSS  # hover chip/pill
    assert "cubic-bezier(.2, 0, 0, 1)" in CSS  # modal open/close
    assert "transition: none" in CSS  # selected ring / ✓
    assert "background-color 150ms ease" in CSS  # 开始制作 color only
    assert "width: 16px; height: 16px" in CSS and "ca-skillrun__check" in CSS
    assert "skillRun.select" in DLG and "Icons.expand" in DLG
