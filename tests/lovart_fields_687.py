"""#687 — hard-coded Lovart dialog field spec (source: docs/qa/687-audit/README.md @6fdfd01c + gold dialog_fields.txt).
Shared by the unit test (tests/test_skill_fields_687.py) and the e2e (tests/test_e2e_skill_fields_687.py).
Row = (key, type, required, accept, maxLength, zh label, en label, en placeholder)."""
# #748: spec now = product's measured data (src/data/skill-inputs-748.json, #748 comment 6646601205); supersedes the #687 table.
import json as _json
from pathlib import Path as _Path
_M = _json.loads((_Path(__file__).resolve().parents[1] / "src/data/skill-inputs-748.json").read_text())["skills"]
_KEY = {"upload": "file", "notes": "note"}
_EN = {"上传文件": "Upload Files", "补充描述": "Additional Details", "有什么想补充的吗？": "Anything else to add?",
       "商品与包装资料": "Product & packaging info", "商品与包装素材": "Product & packaging assets", "视觉呈现方式": "Visual presentation",
       "静态原稿": "Static artwork", "动态要求": "Motion requirements", "商品图片": "Product images", "商品资料": "Product info",
       "品牌素材（选填）": "Brand assets (optional)", "补充要求": "Additional requirements", "品牌资料": "Brand info", "品牌素材": "Brand assets"}
def _row(f):
    up = f["type"] == "upload"
    ph = f.get("placeholder_zh")
    return (_KEY.get(f["key"], f["key"]), "image" if up else ("textarea" if f["key"] == "notes" else "text"), bool(f.get("required")),
            "image" if up else None, f.get("maxlength"), f["label_zh"], _EN.get(f["label_zh"]), (_EN.get(ph, ph) if ph else None))
SPEC = {sid: [_row(f) for f in v["inputs"]] for sid, v in _M.items()}
CHANGED = list(SPEC)
NOTE_PH_ZH = "有什么想补充的吗？"  # #748 measured zh placeholder on all example-class cards
REF12 = [k for k, v in _M.items() if not v.get("startDisabledWhenEmpty")]
MOTION_TITLE = {"zh": "参考视频重制", "en": "Reference Video Remake"}
MOTION_DESC_EN = "Adapt a reference video with your content while preserving its shot structure and pacing"
MOTION_FEATURED_REMOVED = "580/featured-v1/motion/03.webp"

# #687 decision (技术经理): NO old→new key mapping. Old drafts / handoff links using these pre-#687 keys
# must not throw and must open the dialog with empty fields.
OLD_KEYS_687 = {
    "brand": {"brandInfo": "Old brand", "brandAssets": "/view?f=old.png"},  # #748: `visual` is a live key again
    "packaging": {"packInfo": "Old pack"},
    "character": {"characterRef": "/view?f=old.png", "characterInfo": "Old char"},
    "logo-material": {"logoImage": "/view?f=old.png", "materialNotes": "old"},
    "meta-ads": {"campaignBrief": "Old brief", "adAssets": "/view?f=old.png"},
    "marketing-campaign": {"campaignGoal": "Old goal", "campaignAssets": "/view?f=old.png"},
    "web-product": {"webBrief": "Old web", "webRefs": "/view?f=old.png"},
    "mobile-ui": {"appBrief": "Old app", "uiRefs": "/view?f=old.png"},
    "social": {"productRef": "/view?f=old.png", "personRef": "/view?f=old.png"},
    "motion": {"stillArt": "/view?f=old.png", "motionNotes": "Old motion"},
}
