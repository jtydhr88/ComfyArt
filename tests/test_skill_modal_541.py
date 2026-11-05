"""#541: skill modal to Lovart's measurements (no media wall). Real-data meta line via src/skills.ts + wiring greps."""
from __future__ import annotations

import json
from tests.skill_ids_748 import asset_dir
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DLG = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
CSS = (ROOT / "src/styles/home.css").read_text()
BASE = (ROOT / "src/styles/base.css").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())
needs_node = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("m541") / "skill_modal_541.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "skill_modal_541.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


@needs_node
def test_meta_is_template_count_only(got):
    # #581: skillMeta also carries usage (0 when store empty). No presets + no usage → null.
    for sid, n in got["presets"].items():
        # #644 design: the count is the dialog's real thumbnails (examples + preset tiles with media), not presets[]
        assert (got["meta"][sid] is None) == (n == 0 or got["thumbs"][sid] == 0), sid  # 0 thumbnails → no label
        if got["meta"][sid]:
            assert got["meta"][sid]["templates"] == got["thumbs"][sid] and got["meta"][sid]["usage"] == 0, sid
    assert "custom-workflow" not in got["meta"] and got["old"] is None


def test_meta_copy_has_no_fake_usage():
    assert ZH["skillRun.templateCount"] == "{0} 个模板" and EN["skillRun.templateCount"] == "{0} templates"
    # #581: real usage copy is allowed via skillMetaLabel; still no hardcoded fake number in the dialog source.
    assert "skillRun.used" not in DLG
    assert "skillMetaLabel(meta)" in DLG and "skill-run-meta" in DLG
    assert "Math.random" not in DLG


def test_lovart_sizes_and_theme_vars():
    assert "width: min(1112px, calc(100vw - 32px))" in CSS and "height: min(820px" in CSS
    assert "flex: 1 1 752px" in CSS and "flex: 0 0 360px" in CSS
    css_rules = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)  # hex may appear in history comments (#632)
    assert "background: var(--ca-skillrun-side)" in CSS and "#f5f5f5" not in css_rules
    assert BASE.count("--ca-skillrun-side:") == 2 and BASE.count("--ca-skillrun-tile:") == 2  # light + dark
    assert "object-fit: contain" in CSS and "aspect-ratio: 160 / 120" in CSS  # 344×258 well
    assert "width: 22px; height: 22px" in CSS  # zoom
    assert "height: 86px" in CSS and "width: 36px; height: 36px" in CSS  # current card + thumb
    assert "1px dashed" in CSS and "height: 140px; box-sizing: border-box" in CSS  # upload (#636 4289c673 gold: 108 → 140)
    assert "margin-top: auto" in CSS  # pinned submit
    # #576: ring on image only (title outside frame)
    assert ".ca-skillrun__preset[data-on] .ca-skillrun__presetimg::after" in CSS
    assert ".ca-skillrun__preset[data-on]::after" not in CSS


def test_tiles_from_presets_and_zoom_is_sibling_button():
    assert "skill.presets" in DLG and not re.search(r"\.slice\(0,\s*6\)", DLG)
    assert 'data-testid="skill-run-zoom"' in DLG and 'data-testid="skill-run-zoomview"' in DLG
    tile = DLG[DLG.index('className="ca-skillrun__tile"'):DLG.index('data-testid="skill-run-zoom"')]
    assert tile.count("</button>") == 1  # zoom is not nested inside the radio button
    for k in ("skillRun.zoom", "skillRun.uploadHint", "skillRun.templateCount"):
        assert k in ZH and k in EN


@needs_node
def test_product_has_six_presets(got):
    assert got["presets"]["product-tvc-advertisement-generator"] == 7 and got["meta"]["product-tvc-advertisement-generator"] == {"templates": 7, "usage": 0}  # #748 raw: 7 (+SaaS)
    assert got["productIds"] == ["white", "lifestyle", "detail", "electronics", "food", "beauty", "t7"]
    assert all("/688a702a1f322082cde4e5ed46200c3593db9c43/541/wash/product/product__" in u for u in got["productNew"][:3])  # t7 (SaaS) = placeholder, WASH-TODO


R541 = "https://raw.githubusercontent.com/ganjmeng/ComfyArt/{}/541/wash/{}/{}__{}.webp"


@needs_node
def test_rev2_cells_pinned(got):
    """AC rev 2 (6546010130): product 6 (detail @2422dc5), brand 6 @f204502, packaging 5 @c26cfad (no mockup)."""
    p, b, k = got["imgs"]["product-tvc-advertisement-generator"], got["imgs"]["brand-identity-director"], got["imgs"]["packaging-design-director"]
    for pid in ("white", "lifestyle", "electronics", "food", "beauty"):
        assert p[pid] == R541.format("688a702a1f322082cde4e5ed46200c3593db9c43", asset_dir("product-tvc-advertisement-generator"), asset_dir("product-tvc-advertisement-generator"), pid)
    assert p["detail"] == R541.format("2422dc53d37b8f4437a7f9f7986440d2ea79bbf1", asset_dir("product-tvc-advertisement-generator"), asset_dir("product-tvc-advertisement-generator"), "detail")
    assert list(b) == ["geometric", "handmade", "tech", "beauty", "foodbev", "pet"]
    assert all(u == R541.format("f2045022727c73e24bd6d5ebcb3815bedb7b8797", asset_dir("brand-identity-director"), asset_dir("brand-identity-director"), i) for i, u in b.items())
    assert list(k) == ["eco", "gold", "playful", "panels", "shelf"] and "mockup" not in k
    # packaging re-pinned to manifest c26cfad (mockup dropped; same 5 image blobs as 1014ef2)
    assert all(u == R541.format("c26cfaddc5e12c8652b151ef09ad12c47b2062a0", asset_dir("packaging-design-director"), asset_dir("packaging-design-director"), i) for i, u in k.items() if i != "shelf")
    assert k["shelf"] == R541.format("35c819e64b38cc7d64dcd814ae8b86133976fc8a", asset_dir("packaging-design-director"), asset_dir("packaging-design-director"), "shelf")  # retail-shelf re-wash
    assert got["presets"]["motion-poster-generator"] == 2 and got["presets"]["poster-differentiated-compiler"] == 0  # #748 raw: 2 motion templates (overrides #687 removal); poster effect-only


@needs_node
def test_examples_carousel_is_data_driven(got):
    want = {"poster-differentiated-compiler": 5, "cover-design-director": 7, "rednote-cover-maker": 10, "banner-design-director": 2, "interior-architectural-visualization": 4,  # #575: thumbnail/banner lead with wash mp4
            "universal-multi-angle-grid": 4, "logo-material-explorer": 3, "meta-ads-creative-director": 4, "mobile-app-visual-design": 4, "web-product-visual-design": 4, "marketing-campaign-generator": 4,  # #593 new-6
            "flash-cut-video": 1, "style-transfer": 4, "person-swap": 1, "commerce-strategist": 1, "lifestyle-scene": 2,  # #637 B5 hardMax
            "logo-abstract": 4, "photo-split-poster": 1, "ppt-visual": 1, "promo-ecommerce": 1, "naive-illustration": 4,  # #673 C re-wash (promo ex01 pulled; logo 4)
            "taobao-product": 8, "before-after": 8, "product-website": 3, "linkedin-banner": 1, "clothing-swap": 2,  # #643 batch1 (#667)
            "anim-2d": 3, "creator-identity": 1, "portrait-studio": 6,
            "youtube-channel-banner": 9,  # #678
            "animated-poster": 2,  # #643 per-slot PR
            "premium-website": 7,  # #643 per-slot PR
            "studio-model": 2,  # #643 per-slot PR
            "restaurant-website": 7,  # #643 per-slot PR
            "product-to-packaging": 14,  # #643 per-slot PR
            "game-art": 20,  # #643 per-slot PR
            "logo-animation": 4,  # #643 per-slot PR
            "live-promo-decor": 12,  # #643 per-slot PR
            "ai-model": 6,  # #643 per-slot PR
            "pose-fission": 4}  # #643 per-slot PR
    assert {k: v for k, v in got["examples"].items() if v} == want
    for sid in ("product-tvc-advertisement-generator", "brand-identity-director", "packaging-design-director", "motion-poster-generator", "character-sheet-design"):
        assert got["examples"][sid] == 0, sid
    # Unset examples stay omitted. An explicit empty list is the #641 「暂无示例」 state.
    assert got["exNone"][0] == ""
    assert 'data-testid="skill-run-examples-empty"' in got["exNone"][1]
    assert "No examples yet" in got["exNone"][1]
    html = got["exMock"]
    assert 'data-testid="skill-run-examples"' in html and 'data-count="5"' in html
    assert html.count('data-testid="skill-run-example-thumb"') == 5 and html.count('aria-selected="true"') == 1
    assert 'data-testid="skill-run-example-stage"' in html and 'data-media="image"' in html
    assert 'src="https://x.test/e1.webp"' in html
    assert "skill-run-example-thumb" not in got["exOne"] and "skill-run-example-stage" in got["exOne"]
    assert ZH["skillRun.examples"] == "效果示例" and EN["skillRun.examples"] == "Examples"
    assert ".ca-skillrun__stage" in CSS and "aspect-ratio: 704 / 506" in CSS and "object-fit: contain" in CSS
    assert ".ca-skillrun__stage img, .ca-skillrun__stage video" in CSS
    assert ".ca-skillrun__thumb img, .ca-skillrun__thumb video" in CSS
    assert "<SkillExamples examples={skill.media?.length ? examples : skill.examples} />" in DLG and "from './SkillExamples'" in DLG


EX541 = {"interior-architectural-visualization": ("535d9568d1b8ca25e300fa32db1eca887889ba88", [1, 2, 3, 4]), "poster-differentiated-compiler": ("6d864bd2dd53b9f5b487829f2834d94be013b0a5", [1, 2, 3, 4, 5]),
         "rednote-cover-maker": ("cb41cb8a450139cd903e777c8f84024019d517cd", list(range(1, 11))),
         "banner-design-director": ("8cc3fb305f7ce29ebbab63525680e3436e964dbb", [1])}  # 1 × ~2:1 composite


TIP_VIDEO = "1bbb3f208f18b26ef95c8d9f16efeea111c43ac7"
VIDEO_LEAD = {"cover-design-director", "banner-design-director"}  # #575 lead example is upgrade9 wash mp4


@needs_node
def test_examples_pinned_to_image_commits(got):
    for sid, (sha, ids) in EX541.items():
        stills = [f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{sha}/541/wash/{asset_dir(sid)}/examples/{n}.webp" for n in ids]
        want = ([f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{TIP_VIDEO}/494/wash/videos/{asset_dir(sid)}.mp4"] + stills) if sid in VIDEO_LEAD else stills
        assert got["exUrls"][sid] == want, sid
    # #643 (#659) thumbnail true wash: lead mp4 + 6 stills re-pinned to WASH_643
    w643 = "https://raw.githubusercontent.com/ganjmeng/ComfyArt/0be4350be224066cccf5e2929bfcb02e0bf8f7a9/643/wash/thumbnail/examples"
    assert got["exUrls"]["cover-design-director"] == [f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{TIP_VIDEO}/494/wash/videos/thumbnail.mp4"] + [f"{w643}/{n:02d}.webp" for n in range(1, 7)]
    assert not any("/541/wash/examples/" in u for us in got["exUrls"].values() for u in us)  # old void path


@needs_node
def test_examples_video_stage_markup(got):
    """#575 — SkillExamples renders muted looping <video> for mp4 examples; stills stay <img>."""
    html = got["exVideoMock"]
    assert 'data-media="video"' in html and 'data-testid="skill-run-example-stage-video"' in html
    assert 'src="https://x.test/clip.mp4"' in html and "muted" in html and "loop" in html
    assert got["isVideoMp4"] is True and got["isVideoWebp"] is False
    assert 'data-testid="skill-run-example-thumb-video"' in html


def test_brand_logo_system_prompts():
    src = (ROOT / "src/skills.ts").read_text()
    for pid in ("beauty", "foodbev", "pet"):
        line = src[src.index(f"P('{pid}', ", src.index("id: 'brand-identity-director'")):]
        line = line[:line.index("wash541(")]
        assert "logo system presentation board" in line and "no product mockups" in line, pid
        assert "applied" not in line and "stacked mockups" not in line, pid
