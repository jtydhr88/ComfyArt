"""#687 — hard-coded Lovart dialog field spec (source: docs/qa/687-audit/README.md @6fdfd01c + gold dialog_fields.txt).
Shared by the unit test (tests/test_skill_fields_687.py) and the e2e (tests/test_e2e_skill_fields_687.py).
Row = (key, type, required, accept, maxLength, zh label, en label, en placeholder)."""
# #748 FINAL: spec = the converted reference structure (src/data/skills-748.json, raw/INDEX.md Final table).
# The measured inputs (skill-inputs-748.json) are VOID and deleted. Template cards: default form = first template's
# questions; example cards: the shared user_image + user_requirement; HOLD cards: empty form.
import json as _json
from pathlib import Path as _Path
_R = _json.loads((_Path(__file__).resolve().parents[1] / "src/data/skills-748.json").read_text())["skills"]
# #751 HOLD: our filled copy (docs/design/748/COPY-REWRITE.md → src/data/copy-748.json) supplies placeholders
_C = _json.loads((_Path(__file__).resolve().parents[1] / "src/data/copy-748.json").read_text())
def _ours_ph(sid):
    c = _C.get(sid, {})
    return (c.get("templates", {}).get("1", {}) or c).get("placeholders", {}) if c.get("templates") else c.get("placeholders", {})
def _raw_row(q, sid=None):
    ph = _ours_ph(sid).get(q["key"]) if sid else None
    ph = ph or ({"en": f"Enter {q['label']['en'].lower()}"} if q["type"] == "text" else None)  # generic fallback
    t = "image" if q["type"] == "image" else ("textarea" if (q.get("maxLength") or 0) > 200 else "text")
    return (q["key"], t, bool(q["required"]), "image" if q["type"] == "image" else None, q.get("maxLength"),
            q["label"]["zh"], q["label"]["en"], ph["en"] if ph else None)
RAW_748 = _R
def _inputs(v):
    return v["templates"][0]["inputs"] if v["kind"] == "template" else v.get("inputs", [])
SPEC = {sid: [_raw_row(q, sid) for q in _inputs(v)] for sid, v in _R.items()}
CHANGED = list(SPEC)
OURS_PH = _ours_ph
REF12 = [k for k, v in _R.items() if v["kind"] == "example" and not v.get("hold")]  # example cards with the shared form
MOTION_TITLE = {"zh": _R["motion-poster-generator"]["title"]["zh"], "en": _R["motion-poster-generator"]["title"]["en"]}  # #748 raw title 动态海报
MOTION_DESC_EN = "Adapt a reference video with your content while preserving its shot structure and pacing"
MOTION_FEATURED_REMOVED = "580/featured-v1/motion/03.webp"

# #687 decision (技术经理): NO old→new key mapping. Old drafts / handoff links using these pre-#687 keys
# must not throw and must open the dialog with empty fields.
OLD_KEYS_687 = {
    "brand-identity-director": {"brandInfo": "Old brand", "brandAssets": "/view?f=old.png"},  # #748: `visual` is a live key again
    "packaging-design-director": {"packInfo": "Old pack"},
    "character-sheet-design": {"characterRef": "/view?f=old.png", "characterInfo": "Old char"},
    "logo-material-explorer": {"logoImage": "/view?f=old.png", "materialNotes": "old"},
    "meta-ads-creative-director": {"campaignBrief": "Old brief", "adAssets": "/view?f=old.png"},
    "marketing-campaign-generator": {"campaignGoal": "Old goal", "campaignAssets": "/view?f=old.png"},
    "web-product-visual-design": {"webBrief": "Old web", "webRefs": "/view?f=old.png"},
    "mobile-app-visual-design": {"appBrief": "Old app", "uiRefs": "/view?f=old.png"},
    "rednote-cover-maker": {"productRef": "/view?f=old.png", "personRef": "/view?f=old.png"},
    "motion-poster-generator": {"stillArt": "/view?f=old.png", "motionNotes": "Old motion"},
}
