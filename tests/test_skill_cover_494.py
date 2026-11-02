"""#494-1: cover fallback (cover → own images[0] → grey + icon) and data-driven chips through the real src/skills.ts.
Harness: tests/js/skill_cover_494.ts (stubs from tests/js/rolldown.config.mjs, no network, $0)."""
from __future__ import annotations

import json
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
    assert got["custom"] == {"src": got["builtinCovers"]["custom-workflow"], "own": "bundled"}  # #581 real cover


def test_own_image_used(got):
    assert got["ownImage"] == {"src": "input/r.png", "own": "userdata"}


def test_builtin_covers(got):
    """#581 washed covers stay pinned; #594 Phase1 new 6 covers-v4 @ WASH_594."""
    covers = got["builtinCovers"]
    washed = ["poster", "social", "brand", "packaging", "thumbnail", "banner", "character", "product", "motion", "interior", "custom-workflow"]
    phase1_new = ["multi-angle", "logo-material", "meta-ads", "mobile-ui", "web-product", "marketing-campaign"]
    v3, pin = "3c9b87e7eae72164efdd1fe30e00f576144475f4", {
        "banner": ("494/covers-v3.1", "9b23a3e8e3ca2f6b64dc16c0cf36fbf9c41fcaf4"),
        "character": ("494/covers-v3.2", "dc335056e81e0350e2f98487fb680e22ffb14bb9"),
    }
    v4 = "cc76d743d416c3d9a9a6852d811a7a80caf40319"
    assert len(covers) == 17 and "custom-workflow" in covers
    assert {k: covers[k] for k in washed} == {
        k: "https://raw.githubusercontent.com/ganjmeng/ComfyArt/{1}/{0}/{2}.webp".format(*pin.get(k, ("494/covers-v3", v3)), k)
        for k in washed
    }
    assert {k: covers[k] for k in phase1_new} == {
        k: f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{v4}/494/covers-v4/{k}.webp"
        for k in phase1_new
    }


def test_chips_from_data(got):
    assert got["chips"] == ["forYou", "ecommerce", "branding", "social", "website", "ads"]  # #591 website lit
    by = got["byChip"]
    assert len(by["forYou"]) == 17
    # #595: within-chip order follows PHASE1 hot mount (orderBuiltins)
    assert by == {"forYou": by["forYou"],
                  "ecommerce": ["product", "multi-angle", "packaging"],
                  "branding": ["brand", "logo-material"],
                  "social": ["thumbnail", "social"],
                  "website": ["mobile-ui", "web-product"],
                  "ads": ["motion", "meta-ads", "poster", "marketing-campaign", "banner"]}
    assert by["forYou"][:15] == [
        "product", "multi-angle", "brand", "character", "logo-material", "packaging",
        "motion", "meta-ads", "poster", "thumbnail", "mobile-ui", "social",
        "marketing-campaign", "web-product", "banner",
    ]
    for sid in ("character", "interior", "custom-workflow"):
        assert all(sid not in v for k, v in by.items() if k != "forYou")


def test_builtin_videos_unique(got):
    """#529/#623 — 10 upgrade9 @ WASH_VIDEO + 6 new6 @ WASH_623; custom-workflow stays null."""
    vids = got["builtinVideos"]
    assert vids.pop("custom-workflow") is None
    tip = "1bbb3f208f18b26ef95c8d9f16efeea111c43ac7"
    pin623 = "d03ea7938877d084c201a94ef51f943dd0e061b9"
    new6 = ("multi-angle", "logo-material", "meta-ads", "mobile-ui", "web-product", "marketing-campaign")
    for sid in new6:
        assert vids.pop(sid) == f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{pin623}/594/wash/videos/{sid}.mp4"
    assert len(vids) == 10
    assert vids == {
        k: f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{tip}/494/wash/videos/{k}.mp4"
        for k in vids
    }
    assert len(set(vids.values())) == 10


def test_video_field_data_driven(got):
    """#529 mutation: drop/omit video → skillVideo null (badge must not invent video)."""
    assert got["noVideo"] is None and got["customVideo"] is None
    assert got["videoMutated"] is None


def test_575_video_contract(got):
    """#575/#623 — detector, hover play/pause+seek0, new6 pending empty (wired), thumbnail/banner lead mp4, motion preset.video unset."""
    assert got["isVideo"] == {"mp4": True, "webm": True, "mov": True, "webp": False, "empty": False, "undef": False}
    assert got["pendingNew6"] == []  # #623 wired → empty pending
    tip = "1bbb3f208f18b26ef95c8d9f16efeea111c43ac7"
    assert got["thumbEx"][0] == f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{tip}/494/wash/videos/thumbnail.mp4"
    assert got["bannerEx"][0] == f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{tip}/494/wash/videos/banner.mp4"
    assert len(got["thumbEx"]) == 7 and len(got["bannerEx"]) == 2
    assert got["motionPresetVideos"] == [None, None]  # design motion-01/02 mp4 TODO (#622)
    assert got["hoverCalls"] == ["play", "pause"] and got["hoverSeek"] == 0
