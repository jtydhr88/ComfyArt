"""#133 Auto model choice: when the user names no model, pick one by task type from api/auto_models.json
(product table v1). Deterministic: same prompt -> same category -> same model. User-named models win.

#237: a row matches when any keyword hits, or every term of an ``also`` group hits. English keywords
are whole words ('icon' not in 'iconic'); Chinese keywords are substrings. A hit is ignored when a
negation sits just before it ('no headline', '不要任何文字'). ``exclude`` phrases are blanked first
('portrait orientation', 'job title', 'context menu'). Categories are still first-match, so one
task keeps one model.
"""
import json
import logging
import re
from pathlib import Path

log = logging.getLogger("comfyart")
TABLE = Path(__file__).with_name("auto_models.json")

# Filler between a negation and the keyword: "no headline", "don't add a title", "不要太小的文字".
_NEG_EN = re.compile(r"(?:\bno|without|never|not|don'?t|do not)\b(?:\s+\w+){0,4}\s*$")
# 无 / 别 are single characters and also start unrelated words (无限), so they only count
# immediately before the keyword. The longer negations may take a few characters of filler.
_NEG_ZH = re.compile(r"(?:(?:不要|没有|别加|不加|勿)(?:[\u4e00-\u9fff]{0,4})|(?:无|别)(?:任何)?)$")


def load_table() -> dict:
    with open(TABLE, encoding="utf-8") as f:
        return json.load(f)["features"]


def skill_pin(skill: str | None) -> dict | None:
    """#708: a skill's explicitly registered model row (model, resolution, ratio, fallback), or None."""
    if not skill:
        return None
    with open(TABLE, encoding="utf-8") as f:
        row = (json.load(f).get("skills") or {}).get(str(skill))
    return dict(row) if isinstance(row, dict) else None


def tool_feature(tool: str) -> str | None:
    return next((f for f, spec in load_table().items() if spec["tool"] == tool or tool in (spec.get("masked") or {}).get("tools", [])), None)


def _norm(text: str) -> str:
    text = (text or "").lower().replace("–", "-").replace("—", "-").replace("−", "-")
    text = re.sub(r"(?<=[a-z0-9])[-_/](?=[a-z0-9])", " ", text)
    return re.sub(r"\s+", " ", text)


def _spans(keyword: str, text: str):
    k = _norm(keyword)
    if not k:
        return
    if k.isascii():
        for m in re.finditer(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", text):
            yield m.start(), m.end()
        return
    start = 0
    while True:
        i = text.find(k, start)
        if i < 0:
            return
        yield i, i + len(k)
        start = i + len(k)


def hit(keyword: str, text: str) -> bool:
    """English keywords match whole words ('icon' not in 'iconic'); Chinese ones match as substrings."""
    return next(_spans(keyword, _norm(text)), None) is not None


def _negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 18):start]
    return _NEG_EN.search(prefix) is not None or _NEG_ZH.search(prefix) is not None


def _positive(keyword: str, text: str) -> bool:
    return any(not _negated(text, start) for start, _end in _spans(keyword, text))


def _scrub(text: str, phrases: list[str]) -> str:
    chars = list(text)
    for phrase in sorted(phrases or [], key=len, reverse=True):
        for start, end in _spans(phrase, text):
            for i in range(start, end):
                chars[i] = " "
    return "".join(chars)


def _matches(cat: dict, text: str) -> bool:
    text = _scrub(text, cat.get("exclude") or [])
    if any(_positive(k, text) for k in cat.get("keywords") or []):
        return True
    return any(group and all(_positive(k, text) for k in group) for group in cat.get("also") or [])


def choose(feature: str, prompt: str, named: str | None, catalog: dict, masked: bool = False) -> dict:
    """catalog: load_config() result. Returns {model, auto, category, reason: {zh, en}}.
    masked (#45): the edit has a selection or brushed mask -> the table's 'masked' row (user-named still wins)."""
    cfg = catalog["features"][feature]
    if named:
        return {"model": named, "auto": False, "category": "user",
                "reason": {"zh": "你指定了这个模型", "en": "you named this model"}}
    spec = load_table()[feature]
    row = spec.get("masked") if masked else None
    if row and row["model"] in {m["id"] for m in cfg["models"]}:
        return {"model": row["model"], "auto": True, "category": "masked", "reason": {"zh": row["zh"], "en": row["en"]}}
    text = _norm(prompt or "")
    cat = next((c for c in spec["categories"] if _matches(c, text)), None)
    ids = {m["id"] for m in cfg["models"]}
    if cat and cat["model"] not in ids:
        log.warning("auto model %s for %s/%s not in catalog; falling back to %s", cat["model"], feature, cat["id"], cfg["default"])
        return {"model": cfg["default"], "auto": True, "category": cat["id"], "fallback": cat["model"],
                "reason": {"zh": f"{cat['zh']}，但 {cat['model']} 当前不可用，改用默认模型",
                           "en": f"{cat['en']}, but {cat['model']} is unavailable, so the default model was used"}}
    if cat:
        return {"model": cat["model"], "auto": True, "category": cat["id"], "reason": {"zh": cat["zh"], "en": cat["en"]}}
    return {"model": cfg["default"], "auto": True, "category": "default", "reason": dict(spec["default"]), "plain": True}


def note(choice: dict) -> str:
    """One line the agent repeats in its reply: 用了 X，因为 Y / used X because Y."""
    m, r = choice["model"], choice["reason"]
    if choice.get("plain"):
        return f"用了 {m}，{r['zh']}。/ Used {m}, {r['en']}."
    return f"用了 {m}，因为{r['zh']}。/ Used {m} because {r['en']}."
