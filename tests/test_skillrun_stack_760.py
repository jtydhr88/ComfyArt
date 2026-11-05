"""#760 — generic SkillRun stack: all media[], aspect-aware rest, focus by count, contain-only covers."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "src/styles/home.css").read_text()
DLG = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
RAW = (ROOT / "src/skillRaw748.ts").read_text()
WASH = (ROOT / "src/data/wash-748.json").read_text()


def test_400ms_expand_collapse_kept():
    assert "--ca-skillrun-stack-dur: 400ms" in CSS
    assert "--ca-skillrun-stack-ease: cubic-bezier(.25, .1, .25, 1)" in CSS
    assert "var(--ca-skillrun-stack-dur)" in CSS


def test_card_well_stays_160_120():
    assert "aspect-ratio: 160 / 120" in CSS and "width: 258px" not in CSS


def test_dialog_scales_1112_to_1200_modal_200ms():
    """@1280 → 1112×820 / cards 344×288 (well 344×258); @1920 → 1200×820 / 388×321."""
    assert "1112px" in CSS and "1200px" in CSS
    assert "(100vw - 1280px) * 88 / 640" in CSS
    assert "ca-skillrun-in 200ms" in CSS
    assert "ca-skillrun-backdrop-in 200ms" in CSS
    assert "ca-skillrun-in 250ms" not in CSS
    # card geometry: right 360 + aspect 160/120 → well 344×258 @1280 / 388×291 @1920
    assert "flex: 0 0 360px" in CSS
    assert "aspect-ratio: 160 / 120" in CSS


def test_rest_aspect_aware_and_focus_by_count():
    seg = CSS.split("#760 — generic SkillRun stack")[1].split("「选择」")[0]
    assert "inset: var(--ca-skillrun-stack-inset)" in seg and "--ca-skillrun-stack-inset: 8px" in seg
    # landscape rest path (~78% AABB)
    assert "height: 76.03%" in seg and "translateY(15.75%) scale(.757178)" in seg
    # portrait rest path
    assert 'data-orient="portrait"' in seg and "55.335%" in seg and "scale(.8057)" in seg
    assert "nth-child(1) { --r: 5deg; }" in seg and "nth-child(2) { --r: -5deg; }" in seg and "nth-child(3) { --r: 10deg; }" in seg
    # indices ≥3 opacity 0
    assert "nth-child(n+4) { opacity: 0; }" in seg
    # no sticky [data-on] expand
    assert "[data-on] .ca-skillrun__stack" not in seg
    assert ":hover .ca-skillrun__stack" in seg
    # 2×2 focus
    assert 'data-n="4"' in seg and "49.085%" in seg and "48.76%" in seg
    # landscape rest contain; portrait rest cover (height-fill 181.5×242)
    assert "object-fit: contain" in seg
    assert "object-fit: cover" in seg


def test_cover_contain_never_cover():
    """Single-tile cover (motion 首尾帧 etc.): contain letterbox only."""
    assert "/* #760 — contain ONLY (never cover)" in CSS
    # absolute centered auto box — height fills for portrait (~145×258 @1280)
    assert "max-width: 100%; max-height: 100%; width: auto; height: auto;" in CSS
    bare = re.findall(r"\.ca-skillrun__presetimg\s+img\b", CSS)
    assert not bare, bare


def test_render_all_media_no_slice_no_pad():
    assert "stack.slice(0, 3)" not in DLG
    assert "stack.map(" in DLG
    assert 'data-n={stack.length >= 4 ? 4 : stack.length}' in DLG
    assert "while (stack.length < target)" not in RAW
    assert "slice(0, target)" not in RAW
    assert "No pad" in RAW or "no pad-with-last" in RAW
    assert "t.media.length > 1 && real.length > 0" in RAW


def test_stack_never_padded_with_pending():
    assert "j === 0 ? image : PENDING_WASH" not in RAW
    assert "stack.length > 1" in DLG
    seg = DLG[DLG.index('data-testid="skill-run-stack"'):][:500]
    assert "PendingWash" not in seg and "pending-wash" not in seg


def test_wash_raw_not_thumb():
    """media URLs = raw originals with real w/h, not @thumb."""
    assert "02-first-to-last-frame-animation.webp" in WASH
    assert "02-first-to-last-frame-animation@thumb.webp" not in WASH
    # packaging stack raw
    assert "packaging__gold.webp" in WASH
    assert "packaging__gold@thumb.webp" not in WASH


def test_skills_category_chip_200ms_not_select_pill():
    """Category chips For you / E-commerce / … = 200ms; card 「选择」/zoom stay 100ms."""
    chip = CSS.split(".ca-skills__chip {", 1)[1].split("}", 1)[0]
    assert "200ms" in chip
    assert "--ca-skillrun-hover-dur: 100ms" in CSS
    assert "--ca-skillrun-hover-dur: 200ms" not in CSS
    assert CSS.count(".ca-skillrun__zoom, .ca-skillrun__pick {") >= 2
    override = CSS.rsplit(".ca-skillrun__zoom, .ca-skillrun__pick {", 1)[1].split("}", 1)[0]
    assert "var(--ca-skillrun-hover-dur)" in override


def test_rest_pile_transform_origin_center():
    seg = CSS.split("#760 — generic SkillRun stack")[1].split("「选择」")[0]
    assert "transform-origin: center center" in seg
    assert "scale(.757178)" in seg

def test_single_portrait_cover_no_stack():
    """主款/Master Packaging: media.length=1 → no stack; ratio 0.75 → 181.5×242 centered frame."""
    assert "Math.abs(r0 - 0.75)" in RAW
    assert "mediaOrient" in RAW
    assert "mediaOrient" in (ROOT / "src/skills.ts").read_text()
    assert 'data-orient={p.stackOrient ?? p.mediaOrient' in DLG
    assert 'presetimg[data-orient="portrait"] > img' in CSS
    assert "0.55335" in CSS and "0.22332" in CSS
    # stack still requires media.length > 1
    assert "t.media.length > 1 && real.length > 0" in RAW
    # #760 r7: Master wash is single-frame 3:4 (no stacked-sheet bitmap); portrait uses contain
    skills = (ROOT / "src/skills.ts").read_text()
    assert "packaging/master.webp" in skills
    assert (ROOT / "public/skills/packaging/master.webp").is_file()
    # portrait single block uses contain (not cover) so 3:4 media is letterboxed-safe
    seg = CSS.split('presetimg[data-orient="portrait"] > img')[1].split("preset-video")[0]
    assert "object-fit: contain" in seg
