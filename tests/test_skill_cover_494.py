"""#494-1: cover fallback (cover → own images[0] → grey + icon) and data-driven chips through the real src/skills.ts.
Harness: tests/js/skill_cover_494.ts (stubs from tests/js/rolldown.config.mjs, no network, $0)."""
from __future__ import annotations

import json
from tests.skill_ids_748 import asset_dir
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("m494") / "skill_cover_494.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "skill_cover_494.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


def test_no_image_falls_back_to_icon(got):
    assert got["noImage"] is None and got["customNoCover"] is None  # null → grey background + Lucide icon
    assert got["custom"] == {"src": got["builtinCovers"]["interior-architectural-visualization"], "own": "bundled"}  # #581 real cover


def test_own_image_used(got):
    assert got["ownImage"] == {"src": "input/r.png", "own": "userdata"}


def test_builtin_covers(got):
    """#581 washed covers stay pinned; #594 Phase1 new 6 covers-v4 @ WASH_594."""
    covers = got["builtinCovers"]
    washed = ["poster-differentiated-compiler", "rednote-cover-maker", "brand-identity-director", "packaging-design-director", "banner-design-director", "character-sheet-design", "product-tvc-advertisement-generator", "motion-poster-generator", "interior-architectural-visualization"]
    phase1_new = ["universal-multi-angle-grid", "logo-material-explorer", "meta-ads-creative-director", "mobile-app-visual-design", "web-product-visual-design", "marketing-campaign-generator"]
    v3, pin = "3c9b87e7eae72164efdd1fe30e00f576144475f4", {
        "banner-design-director": ("494/covers-v3.1", "9b23a3e8e3ca2f6b64dc16c0cf36fbf9c41fcaf4"),
        "character-sheet-design": ("494/covers-v3.2", "dc335056e81e0350e2f98487fb680e22ffb14bb9"),
    }
    v4 = "cc76d743d416c3d9a9a6852d811a7a80caf40319"
    assert len(covers) == 49 and "custom-workflow" not in covers  # #640 Phase3-S1 +19 NEW (null covers)
    assert {k: covers[k] for k in washed} == {
        k: "https://raw.githubusercontent.com/ganjmeng/ComfyArt/{1}/{0}/{2}.webp".format(*pin.get(k, ("494/covers-v3", v3)), asset_dir(k))
        for k in washed
    }
    # #643 (#659) thumbnail true wash re-pinned cover to WASH_643
    assert covers["cover-design-director"] == "https://raw.githubusercontent.com/ganjmeng/ComfyArt/0be4350be224066cccf5e2929bfcb02e0bf8f7a9/643/wash/thumbnail/cover.webp"
    assert {k: covers[k] for k in phase1_new} == {
        k: f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{v4}/494/covers-v4/{k}.webp"
        for k in phase1_new
    }


def test_chips_from_data(got):
    assert got["chips"] == ["forYou", "ecommerce", "branding", "social", "website", "ads"]  # #591 website lit
    by = got["byChip"]
    assert len(by["forYou"]) == 49  # #640 Phase3-S1
    # #595: within-chip order follows PHASE1 hot mount (orderBuiltins)
    assert by == {"forYou": by["forYou"],
                  "ecommerce": ["product-tvc-advertisement-generator", "universal-multi-angle-grid", "packaging-design-director", "person-swap", "commerce-strategist", "lifestyle-scene", "promo-ecommerce", "taobao-product", "studio-model", "ai-model", "product-to-packaging", "pose-fission", "live-promo-decor", "clothing-swap"],
                  "branding": ["brand-identity-director", "logo-material-explorer", "style-transfer", "logo-abstract", "creator-identity", "logo-animation"],
                  "social": ["cover-design-director", "rednote-cover-maker", "naive-illustration", "yingzao", "crt-interface", "crayon-sketch", "fabric-collage", "youtube-channel-banner", "portrait-studio", "linkedin-banner"],
                  "website": ["mobile-app-visual-design", "web-product-visual-design", "ppt-visual", "product-website", "premium-website", "restaurant-website"],
                  "ads": ["motion-poster-generator", "meta-ads-creative-director", "poster-differentiated-compiler", "marketing-campaign-generator", "banner-design-director", "flash-cut-video", "photo-split-poster", "before-after", "anim-2d", "game-art", "animated-poster"]}
    assert by["forYou"][:15] == [
        "product-tvc-advertisement-generator", "universal-multi-angle-grid", "brand-identity-director", "character-sheet-design", "logo-material-explorer", "packaging-design-director",
        "motion-poster-generator", "meta-ads-creative-director", "poster-differentiated-compiler", "cover-design-director", "mobile-app-visual-design", "rednote-cover-maker",
        "marketing-campaign-generator", "web-product-visual-design", "banner-design-director",
    ]
    for sid in ("character-sheet-design", "interior-architectural-visualization"):
        assert all(sid not in v for k, v in by.items() if k != "forYou")


def test_builtin_videos_unique(got):
    """#529/#623 — 10 upgrade9 @ WASH_VIDEO + 6 new6 @ WASH_623; custom-workflow card removed."""
    vids = got["builtinVideos"]
    assert "custom-workflow" not in vids
    tip = "1bbb3f208f18b26ef95c8d9f16efeea111c43ac7"
    pin623 = "d03ea7938877d084c201a94ef51f943dd0e061b9"
    new6 = ("universal-multi-angle-grid", "logo-material-explorer", "meta-ads-creative-director", "mobile-app-visual-design", "web-product-visual-design", "marketing-campaign-generator")
    for sid in new6:
        assert vids.pop(sid) == f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{pin623}/594/wash/videos/{asset_dir(sid)}.mp4"
    pin637 = "2109c085aa74c617cd34517f99626f357062c81c"
    # #637: flash-cut + commerce get single-video example.mp4 as skill.video; other phase2 still null
    for sid in ("flash-cut-video", "commerce-strategist"):
        assert vids.pop(sid) == f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{pin637}/637/wash/{sid}/example.mp4"
    phase2_null = ("style-transfer", "person-swap", "lifestyle-scene",
              "naive-illustration", "logo-abstract", "photo-split-poster", "ppt-visual", "promo-ecommerce",
              "yingzao", "crt-interface", "crayon-sketch", "fabric-collage")
    for sid in phase2_null:
        assert vids.pop(sid) is None  # C/D + still-only B remain null
    phase3_null = (
        "taobao-product", "before-after", "anim-2d", "creator-identity", "product-website",
        "studio-model", "youtube-channel-banner", "ai-model", "product-to-packaging",
        "game-art", "portrait-studio", "premium-website", "animated-poster", "pose-fission",
        "live-promo-decor", "linkedin-banner", "logo-animation", "restaurant-website", "clothing-swap",
    )
    for sid in phase3_null:
        assert vids.pop(sid) is None  # #640 Phase3-S1 empty video until S4
    assert len(vids) == 10
    assert vids == {
        k: f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{tip}/494/wash/videos/{asset_dir(k)}.mp4"
        for k in vids
    }
    assert len(set(vids.values())) == 10


def test_video_field_data_driven(got):
    """#529 mutation: drop/omit video → skillVideo null (badge must not invent video)."""
    assert got["noVideo"] is None and got["customVideo"] is None
    assert got["videoMutated"] is None


def test_575_video_contract(got):
    """#575/#623/#622 — detector, hover play/pause+seek0, new6 pending empty (wired), thumbnail/banner lead mp4, motion preset.video wash-v1."""
    assert got["isVideo"] == {"mp4": True, "webm": True, "mov": True, "webp": False, "empty": False, "undef": False}
    assert got["pendingNew6"] == []  # #623 wired → empty pending
    tip = "1bbb3f208f18b26ef95c8d9f16efeea111c43ac7"
    assert got["thumbEx"][0] == f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{tip}/494/wash/videos/thumbnail.mp4"
    assert got["bannerEx"][0] == f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{tip}/494/wash/videos/banner.mp4"
    assert len(got["thumbEx"]) == 1 and len(got["bannerEx"]) == 1  # #748 raw highlights: 1 video each (convert)
    motion_tip = "5a8d22ed88f732d38f8709a2c0740f074a400a89"
    assert got["motionPresetVideos"] == [None, None]  # #751 HOLD: skill-level video no longer shared onto template cards (each card keeps its OWN cover)  # #748 raw: 2 templates; our wash video is the placeholder (WASH-TODO)
    # mutation: drop preset.video → null (red if wired URLs vanish)
    assert all(v and v.endswith(".mp4") for v in got["motionPresetVideos"])
    assert got["hoverCalls"] == ["play", "pause"] and got["hoverSeek"] == 0
