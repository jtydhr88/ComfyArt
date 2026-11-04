"""#494-1 skill data schema + Explore cards: real built-ins only, data-driven categories, one cover per skill, no counts."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
SKILLS = (ROOT / "src/home/Skills.tsx").read_text()
NEW19 = (  # #640 Phase3-S1 NEW19 → #664 NEARMISS_INPUTS
    "taobao-product", "before-after", "anim-2d", "creator-identity", "product-website", "studio-model",
    "youtube-channel-banner", "ai-model", "product-to-packaging", "game-art", "portrait-studio", "premium-website",
    "animated-poster", "pose-fission", "live-promo-decor", "linkedin-banner", "logo-animation", "restaurant-website", "clothing-swap",
)
HOME_CSS = (ROOT / "src/styles/home.css").read_text()
ICONS = (ROOT / "src/ui/icons.tsx").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())
COVERS = ROOT / "public/skills"
REAL = ["poster", "social", "brand", "packaging", "thumbnail", "banner", "character", "product", "motion",
        "multi-angle", "logo-material", "meta-ads", "mobile-ui", "web-product", "marketing-campaign",
        "flash-cut-video", "style-transfer", "person-swap", "commerce-strategist", "lifestyle-scene",
        "naive-illustration", "logo-abstract", "photo-split-poster", "ppt-visual", "promo-ecommerce",
        "yingzao", "crt-interface", "crayon-sketch", "fabric-collage",
        # #640 Phase3-S1 — 19 NEW (upgrade thumbnail already above)
        "taobao-product", "before-after", "anim-2d", "creator-identity", "product-website",
        "studio-model", "youtube-channel-banner", "ai-model", "product-to-packaging",
        "game-art", "portrait-studio", "premium-website", "animated-poster", "pose-fission",
        "live-promo-decor", "linkedin-banner", "logo-animation", "restaurant-website", "clothing-swap",
        "interior"]  # custom-workflow removed (no Lovart card)
PHASE1_HOT = ["brand", "packaging", "poster", "product", "character", "social", "motion", "banner", "thumbnail",
              "multi-angle", "logo-material", "meta-ads", "mobile-ui", "web-product", "marketing-campaign"]
COVERED = ["poster", "social", "brand", "packaging", "thumbnail", "banner", "character", "product", "motion", "interior"]  # local public/skills; phase1_new=#594 cover(); phase2_b=#637 cover637(); phase2_c=#636 cover673()
# Product ruling (#494 18:26 + AC comment 23:15): 3 skills have no category and appear only under 为你推荐.
CATEGORY = {"poster": "ads", "social": "social", "brand": "branding", "packaging": "ecommerce", "thumbnail": "social",
            "banner": "ads", "character": None, "product": "ecommerce", "motion": "ads",
            "multi-angle": "ecommerce", "logo-material": "branding", "meta-ads": "ads",
            "mobile-ui": "website", "web-product": "website", "marketing-campaign": "ads",
            "flash-cut-video": "ads", "style-transfer": "branding", "person-swap": "ecommerce",
            "commerce-strategist": "ecommerce", "lifestyle-scene": "ecommerce",
            "naive-illustration": "social", "logo-abstract": "branding", "photo-split-poster": "ads",
            "ppt-visual": "website", "promo-ecommerce": "ecommerce",
            "yingzao": "social", "crt-interface": "social", "crayon-sketch": "social", "fabric-collage": "social",
            # #640 Phase3-S1 NEW19 (+ thumbnail upgrade already mapped)
            "taobao-product": "ecommerce", "before-after": "ads", "anim-2d": "ads", "creator-identity": "branding",
            "product-website": "website", "studio-model": "ecommerce", "youtube-channel-banner": "social",
            "ai-model": "ecommerce", "product-to-packaging": "ecommerce", "game-art": "ads",
            "portrait-studio": "social", "premium-website": "website", "animated-poster": "ads",
            "pose-fission": "ecommerce", "live-promo-decor": "ecommerce", "linkedin-banner": "social",
            "logo-animation": "branding", "restaurant-website": "website", "clothing-swap": "ecommerce",
            "interior": None}


def _builtin_block() -> str:
    a = SKILLS_TS.index("export const BUILTIN_SKILLS")
    return SKILLS_TS[a:next(i for i in (SKILLS_TS.find("\n])\n", a), SKILLS_TS.find("\n]\n", a)) if i >= 0)]


def _entries() -> dict[str, str]:
    block = _builtin_block()
    parts = re.split(r"\n  \{ id: '", block)[1:]
    return {p.split("'", 1)[0]: p for p in parts}


def test_builtins_are_exactly_the_real_skills():
    assert list(_entries()) == REAL
    assert set(PHASE1_HOT) <= set(REAL)
    assert len(PHASE1_HOT) == 15


def test_categories_live_in_data():
    for sid, entry in _entries().items():
        m = re.search(r"category: '(\w+)'", entry)
        assert (m.group(1) if m else None) == CATEGORY[sid], sid
    assert not re.search(r"\bcategory\s*[:=]|\.category\b|'poster'|'product'", SKILLS)  # components never map ids → categories
    assert "skillChips(explore)" in SKILLS and "matchesSkillChip" in SKILLS


def test_empty_categories_hidden():
    assert "SKILL_CATEGORY_ORDER.filter((c) => used.has(c))" in SKILLS_TS
    assert "chips.map" in SKILLS
    assert "category: 'website'" in SKILLS_TS  # #591: mobile-ui / web-product light the 网站 chip
    assert "CHIPS.map" not in SKILLS


def test_fake_wall_meta_gone():
    # Banned tokens are split so this file itself keeps the repo-wide counts at 0 (QA greps added lines).
    for bad in ("WALL" + "_META", "CHIP_BY" + "_SKILL", "skillWall" + "Meta", "skillChip(", "skillsViews", "views:", "likes", "Icons.eye", "Icons.heart", "社" + "区"):
        assert bad not in SKILLS_TS + SKILLS, bad
    assert "home.skillsCommunity" not in ZH and "home.skillsViews" not in ZH


def test_presets_and_inputs_schema():
    for sid, e in _entries().items():
        assert len(re.findall(r"\bP\('", e)) == {"product": 6, "brand": 6, "packaging": 5, "character": 8, "motion": 2, "multi-angle": 0, "logo-material": 4, "meta-ads": 4, "mobile-ui": 4, "web-product": 4, "marketing-campaign": 4, "flash-cut-video": 3, "style-transfer": 3, "person-swap": 3, "commerce-strategist": 3, "lifestyle-scene": 3, "naive-illustration": 2, "logo-abstract": 2, "photo-split-poster": 2, "ppt-visual": 3, "promo-ecommerce": 2, "yingzao": 2, "crt-interface": 3, "crayon-sketch": 2, "fabric-collage": 2, "social": 2, "taobao-product": 3, "before-after": 3, "anim-2d": 2, "creator-identity": 3, "product-website": 2, "studio-model": 3, "youtube-channel-banner": 2, "ai-model": 3, "product-to-packaging": 3, "game-art": 3, "portrait-studio": 2, "premium-website": 2, "animated-poster": 2, "pose-fission": 3, "live-promo-decor": 3, "linkedin-banner": 2, "logo-animation": 2, "restaurant-website": 2, "clothing-swap": 3}.get(sid, 0), sid  # #541/#569 + #593 + #634 + #635 + #640 Phase3
        # #494-2: required inputs now also carry a zh/en placeholder after the flag → ", true" (was ", true)").
        # #569: effect skills share EFFECT_INPUTS (upload + note, none required); character's Lovart fields are optional too.
        if sid in ("poster", "banner", "interior", "thumbnail"):
            assert "inputs: EFFECT_INPUTS }" in e, sid
        elif sid == "social":
            # #635: Fashion UGC inputs (file + product/person refs + note); no required fields
            assert "inputs: [" in e and "productRef" in e and "personRef" in e, sid
            assert "inputs: EFFECT_INPUTS" not in e, sid
        elif sid == "multi-angle":
            # #691: Upload + Additional, upload optional (no required fields)
            assert "inputs: MULTI_ANGLE_INPUTS }" in e and ", true" not in e, sid
        elif sid in ("naive-illustration", "logo-abstract", "photo-split-poster", "ppt-visual", "promo-ecommerce") or sid in NEW19:
            # #636 C nearMiss Examples-only right rail; #664 NEW19 dialog field parity (Upload + Additional)
            assert "inputs: NEARMISS_INPUTS" in e, sid
        else:
            assert "inputs: [" in e and (", true" in e) == (sid != "character"), f"{sid} required input"
    # AC 11 was "preset prompts and input en copy are step 2"; #494-2 lands them: every preset has an en prompt and
    # every input label has zh + en (updated, not removed).
    assert "prompt?: string" in SKILLS_TS
    assert "SkillPreset =>" in SKILLS_TS and "prompt, ...(image ? { image } : {}), ...(video ? { video } : {})" in SKILLS_TS  # #520 wash image + #622 video
    assert "label: { zh, en }," in SKILLS_TS and "label: { zh }," not in SKILLS_TS
    for sid, e in _entries().items():
        assert len(re.findall(r"\bwashPreset\(", e)) == 0, sid  # #569: 494 preset washes retired
        assert len(re.findall(r"\bwash569\(", e)) == {"character": 8, "motion": 2}.get(sid, 0), sid  # #569 manifest washes
        assert len(re.findall(r"\bwashProduct541\(", e)) == (6 if sid == "product" else 0), sid  # #541 product 6
        assert len(re.findall(r"\bP\('[^']*', '[^']*', '[^']*', '(?:Style: |Focus on |Motion: |Template: )", e)) == {"product": 6, "brand": 6, "packaging": 5, "character": 8, "motion": 2, "multi-angle": 0, "logo-material": 4, "meta-ads": 4, "mobile-ui": 4, "web-product": 4, "marketing-campaign": 4, "flash-cut-video": 3, "style-transfer": 3, "person-swap": 3, "commerce-strategist": 3, "lifestyle-scene": 3, "naive-illustration": 2, "logo-abstract": 2, "photo-split-poster": 2, "ppt-visual": 3, "promo-ecommerce": 2, "yingzao": 2, "crt-interface": 3, "crayon-sketch": 2, "fabric-collage": 2, "social": 2, "taobao-product": 3, "before-after": 3, "anim-2d": 2, "creator-identity": 3, "product-website": 2, "studio-model": 3, "youtube-channel-banner": 2, "ai-model": 3, "product-to-packaging": 3, "game-art": 3, "portrait-studio": 2, "premium-website": 2, "animated-poster": 2, "pose-fission": 3, "live-promo-decor": 3, "linkedin-banner": 2, "logo-animation": 2, "restaurant-website": 2, "clothing-swap": 3}.get(sid, 0), sid  # en prompt body, counted per preset (logo-animation instructions also say "Motion: ") (#593 + #634 + #635 + #640)
    # names/descriptions keep coming from locale keys (AC 1)
    for e in _entries().values():
        assert re.match(r"[\w-]+', name: t\('skills\.\w+'\)", e)


def test_covers_ten_webps_with_source_manifest():
    man = json.loads((COVERS / "covers.json").read_text())
    files = sorted(p.relative_to(COVERS).as_posix() for p in COVERS.rglob("*") if p.is_file())
    local_covered = list(COVERED)  # legacy local public/skills; new6 are remote-only
    assert files == sorted(["covers.json"] + [f"{s}/cover.webp" for s in local_covered])
    assert man["encoder"] == "Pillow==13.0.0" and man["size"] == [462, 346]
    assert set(man["covers"]) == set(local_covered)
    for sid, c in man["covers"].items():
        assert hashlib.sha256((COVERS / sid / "cover.webp").read_bytes()).hexdigest() == c["sha256"], sid
        assert re.fullmatch(r"[0-9a-f]{64}", c["source_sha256"]) and c["source"] == f"494/covers/{sid}/1.png"
        assert (COVERS / sid / "cover.webp").read_bytes()[8:12] == b"WEBP"
    assert "PILLOW = \"13.0.0\"" in (ROOT / "scripts/skill_covers_494.py").read_text()
    phase1_new = ["multi-angle", "logo-material", "meta-ads", "mobile-ui", "web-product", "marketing-campaign"]
    # #637 Phase2-S4 B NEW5: remote cover637 wash pins (not local public/skills COVERED)
    phase2_b = ["flash-cut-video", "style-transfer", "person-swap", "commerce-strategist", "lifestyle-scene"]
    phase2_c = ["naive-illustration", "logo-abstract", "photo-split-poster", "ppt-visual", "promo-ecommerce"]
    for sid, e in _entries().items():
        head = e.split("inputs:", 1)[0]
        if sid == "thumbnail":
            assert "cover: cover643('thumbnail')" in head, sid  # #643 true-wash cover
        elif sid in COVERED or sid in phase1_new:
            assert f"cover: cover('{sid}')" in head, sid  # #581 + #594 covers-v4 pins
        elif sid in phase2_b:
            assert f"cover: cover637('{sid}')" in head, sid  # #637 soft wash intentional covers
        elif sid in phase2_c:
            assert f"cover: cover673('{sid}')" in head, sid  # #636 C soft wash intentional covers
        elif sid in {"taobao-product", "before-after", "anim-2d", "creator-identity", "product-website", "studio-model", "youtube-channel-banner", "ai-model", "product-to-packaging", "game-art", "portrait-studio", "premium-website", "animated-poster", "pose-fission", "live-promo-decor", "linkedin-banner", "logo-animation", "restaurant-website", "clothing-swap"}:
            assert f"cover: cover643('{sid}')" in head, sid  # #643 NEW19 true-wash covers
        else:
            assert "cover:" not in head, sid


def test_cover_fallback_single_place():
    body = SKILLS_TS.split("export function skillCover", 1)[1].split("\n}\n", 1)[0]
    assert "skill.cover" in body and "Object.values(skill.images ?? {})[0]" in body  # own image first (AC 5)
    assert "pool" not in SKILLS_TS.lower() and "hash" not in SKILLS_TS.lower()  # 23:20 ruling: no image pool
    swall = HOME_CSS.split(".ca-swall {", 1)[1].split("@media", 1)[0]
    assert "gradient" not in re.sub(r"/\*.*?\*/", "", swall, flags=re.S)  # #575 comment may say 'not gradient'
    assert "data-tone" not in SKILLS
    assert "Icons.workflow" not in SKILLS and "workflow:" in ICONS  # custom-workflow card removed; icon kept for WorkflowsDialog
    assert "alt={skill.name}" in SKILLS


def test_badge_position_and_placeholder_colour():
    # 23:27 ruling: badge bottom-left inside the cover on every card; placeholder icon uses the secondary text var
    css = HOME_CSS
    badge = css[css.index(".ca-swall__badge {"):].split("}", 1)[0]
    assert "position: absolute; left: 8px; bottom: 8px;" in badge and "top:" not in badge
    ph = css[css.index(".ca-swall__placeholder {"):].split("}", 1)[0]
    assert "color: var(--ca-text-2);" in ph and "#" not in ph.split("*/")[-1] and "rgb" not in ph
    assert "background: var(--ca-hover);" in css[css.index(".ca-swall__cover {"):].split("}", 1)[0]
    tsx = (ROOT / "src/home/Skills.tsx").read_text()
    cover = tsx[tsx.index('className="ca-swall__cover"'):tsx.index('className="ca-swall__title"')]
    assert 'data-testid="skills-card-kind"' in cover and "{src" in cover  # badge outside the src ternary → every card
    assert "imageLine: L(Image, 2)," in (ROOT / "src/ui/icons.tsx").read_text()


def test_card_author_badge_bookmark():
    assert 'data-testid="skills-card-author"' in SKILLS and "skillAuthor(skill)" in SKILLS
    assert ZH["home.skillsAuthorPersonal"] == "个人" and EN["home.skillsAuthorPersonal"] == "Personal"
    # d932c50 (#532): kind is dynamic (image | video), not hard-coded
    assert 'data-testid="skills-card-kind" data-kind={kind}' in SKILLS and "videoSrc ? 'video' : 'image'" in SKILLS
    assert "e.stopPropagation(); onFav()" in SKILLS and "Icons.bookmark" in SKILLS
    assert "onTry" in SKILLS and "newProject({ skill: s.id })" in SKILLS  # AC 3: main's click kept (legacy path); #494-2 wires cover/title/try → onTry
    # #494-2: hover 「试用此技能」 lands — same dialog as cover / title click.
    assert 'data-testid="skills-card-try"' in SKILLS and ZH["home.skillsTryThis"] == "试用此技能" and EN["home.skillsTryThis"] == "Try this skill"


def test_tab_labels_zh_488():
    assert (ZH["home.skillsExplore"], ZH["home.skillsFavourites"], ZH["home.skillsPersonal"]) == ("探索", "收藏", "个人")


def test_title_and_create_zh_494():
    # 「+」由图标渲染，文案里不带「+」，避免重复
    assert (ZH["home.skills"], ZH["home.skillsCreate"]) == ("技能", "创建")
    assert (EN["home.skills"], EN["home.skillsCreate"]) == ("Skills", "Create")
    assert "{t('home.skillsCreate')}" in SKILLS and "Icons.plus" not in SKILLS.split("skills-create", 1)[1].split("skills-create-menu", 1)[0]


def test_card_layout_css():
    assert "grid-template-columns: repeat(auto-fill, minmax(min(100%, 296px), 1fr));" in HOME_CSS
    assert "gap: 24px 16px;" in HOME_CSS.split(".ca-swall {", 1)[1].split("}", 1)[0]
    assert "aspect-ratio: 231 / 173" in HOME_CSS and "border-radius: 12px" in HOME_CSS
    assert "inset: -4px -4px -8px -4px; border-radius: 16px" in HOME_CSS
    for cls in (".ca-swall__title", ".ca-swall__desc"):
        rule = HOME_CSS.split(cls + " {", 1)[1].split("}", 1)[0]
        assert "white-space: nowrap" in rule and "text-overflow: ellipsis" in rule


def test_no_banned_strings():
    for f in ("src/skills.ts", "src/home/Skills.tsx", "src/styles/home.css", "public/skills/covers.json"):
        txt = (ROOT / f).read_text().lower()
        # the repo-wide gate is the domain + font; pre-existing prose comments in home.css on main are out of scope
        assert "lov" + "art.ai" not in txt and "gt-" + "standard" not in txt


def test_builtin_author_is_brand_name_494():
    """作者行取 BRAND.name，不得写死品牌字符串。"""
    body = SKILLS_TS.split("export function skillAuthor", 1)[1].split("\n}", 1)[0]
    assert "{ kind: 'builtin', label: BRAND.name }" in body
    assert not re.search(r"label: ['\"]", body.replace("t('home.skillsAuthorPersonal')", ""))
    assert re.search(r"^import \{ BRAND \} from './brand'$", SKILLS_TS, re.M)


def test_broken_cover_falls_back_to_placeholder_494():
    """图片加载失败（onError）与无图走同一个占位；按 src 记录失败，src 变化后重试。"""
    card = SKILLS.split("const cover = skillCover(skill)", 1)[1].split("ca-swall__badge", 1)[0]
    assert "const [failedSrc, setFailedSrc] = useState<string | null>(null)" in card
    assert "const showImg = !!src && failedSrc !== src" in card
    assert "{showImg\n" in card and "onError={() => setFailedSrc(src)}" in card
    assert card.count("ca-swall__placeholder") == 1 and card.count("<img") == 1
