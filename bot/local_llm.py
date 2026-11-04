import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Callable, Optional

import aiohttp

from ._cli_common import (
    PROBE_CACHE_S,
    TOOL_RESULT_CAP,
    merge_usage,
)
from . import lms
from . import robustness as _rb
from .guide import AGENT_GUIDE, CORE_MCP_TOOLS, PAID_TOOLS
from .plan_quote import CANCEL_TEXT, QUOTE_TOOL, canon_key
from .providers import (
    AgentProvider,
    BotEvent,
    EmitFn,
    ProviderCaps,
    ProviderStatus,
    TurnHandle,
    TurnRequest,
    TurnResult,
)

_log = logging.getLogger(__name__)
_NET_ERRORS = (aiohttp.ClientError, asyncio.TimeoutError, OSError, RuntimeError, ValueError)

_API_KEY_ENV = "COMFYART_LOCAL_LLM_API_KEY"
_MAX_ITERATIONS = 300  # #391: hard cap only; budget + progress end a run long before
_MAX_WAIT_SLICES = 12
_LLM_TIMEOUT_S = 300
# #234: input is counted in tokens against the model's context window. #493: the window is
# the endpoint's declared one, else the known-model table, else _FALLBACK_CONTEXT_WINDOW.
# 70% of that window is the input budget; the rest is left for the reply and tool calls.
# Past the budget, the latest 6 turns stay verbatim and older turns become one summary
# capped by summary_token_cap(window).
_FALLBACK_CONTEXT_WINDOW = 270_000
# #493: windows of known models, used only when the endpoint's /models does not declare
# one. Matched by lowercase PREFIX of the model id's last path segment (endpoints prefix ids
# with a provider: "deepseek/deepseek-v4.1-flash-1017", "openrouter/deepseek/deepseek-v4-pro");
# first hit wins. Data only: add a row only for a model whose window is verified from its vendor docs.
# Source: https://api-docs.deepseek.com/ and the DeepSeek V4 release notes:
#   deepseek-flash = DeepSeek-V4.1-Flash-1017 (the model behind deepseek-flash; the old name
#   deepseek-v4-flash aliases to it), deepseek-v4-pro; 1M context, max output 384K.
#   "deepseek-v4" covers deepseek-v4-* and deepseek-v4.1-*.
#   deepseek-chat / deepseek-reasoner were retired 2026-07-24 and are deliberately absent.
_KNOWN_MODEL_WINDOWS: tuple[tuple[str, int], ...] = (
    ("deepseek-flash", 1_000_000),
    ("deepseek-v4", 1_000_000),
)


def known_model_window(model: str) -> int:
    """#493: window from the known-model table, 0 if the model is not listed. Only the part
    after the last '/' is matched, so provider prefixes do not hide a known model."""
    mid = (model or "").strip().rsplit("/", 1)[-1].lower()
    if not mid:
        return 0
    for prefix, window in _KNOWN_MODEL_WINDOWS:
        if mid.startswith(prefix):
            return window
    return 0


def resolve_context_window(model: str, declared: int = 0) -> int:
    """#493: one rule for every caller. Endpoint-declared window wins, then the
    known-model table, then _FALLBACK_CONTEXT_WINDOW (270k)."""
    if isinstance(declared, int) and declared > 0:
        return declared
    return known_model_window(model) or _FALLBACK_CONTEXT_WINDOW


# #493 overflow guard: a context-exceeded answer is re-fitted and resent exactly once.
# #493 (product AC): when the error states no window, shrink by half but never below 32k.
OVERFLOW_SHRINK = 0.5
OVERFLOW_FLOOR = 32_000
_OVERFLOW_RE = re.compile(
    r"context[_ ]length[_ ]exceeded|maximum context|context (?:length|window|size)|"
    r"prompt is too long|too many (?:input )?tokens|input (?:is )?too long|exceeds? the (?:model'?s? )?"
    r"(?:context|max)", re.I)
_OVERFLOW_WINDOW_RE = re.compile(
    r"(?:maximum context length|context (?:length|window|size)|max(?:imum)? (?:input|prompt) tokens?|"
    r"limit)\D{0,30}?(\d[\d,_]{2,})", re.I)


def is_context_overflow(exc: BaseException) -> bool:
    """#493: the model refused the request because the prompt is over its window."""
    if not isinstance(exc, LlmHttpError) or exc.status not in (400, 413, 422):
        return False
    return bool(_OVERFLOW_RE.search(exc.body or ""))


def parse_overflow_window(text: str) -> int:
    """#493: the real window stated in a context-exceeded error, 0 if none is given."""
    m = _OVERFLOW_WINDOW_RE.search(text or "")
    if not m:
        return 0
    try:
        return int(re.sub(r"[,_]", "", m.group(1)))
    except ValueError:
        return 0


def summary_token_cap(window: object = None) -> int:
    """#493: the rolling-summary cap, 5% of the model window clamped to [1000, 16000].
    A missing/invalid window uses the 270k fallback (13500)."""
    size = window if isinstance(window, int) and window > 0 else _FALLBACK_CONTEXT_WINDOW
    return max(_SUMMARY_CAP_MIN, min(_SUMMARY_CAP_MAX, round(size * _SUMMARY_CAP_RATIO)))


_INPUT_BUDGET_PERCENT = 70
_VERBATIM_TURNS = 6
_SUMMARY_CAP_RATIO = 0.05   # #493: summary cap = 5% of the window ...
_SUMMARY_CAP_MIN = 1_000    # ... never below 1000 tokens ...
_SUMMARY_CAP_MAX = 16_000   # ... and never above 16000.
_SUMMARY_HEADER = "Earlier conversation summary:"
_REPEAT_STOP = 3
_CACHED_SKILL_STOP = 3  # cumulative cached skill re-reads per turn (A/B/A/B...)
_MAX_STEPS_ENV = "COMFYART_AGENT_MAX_STEPS"
_MAX_STEPS_RANGE = (1, 500)
# #232: an LLM request that timed out, got 429 or a 5xx is retried twice; tool calls (paid) never are.
_LLM_RETRIES = 2
_RETRY_BACKOFF_S = (2.0, 4.0)       # timeout / 5xx: wait before retry 1, 2
_RATE_LIMIT_WAIT_S = (5.0, 10.0)    # 429 without Retry-After: countdown before retry 1, 2
_RATE_LIMIT_WAIT_CAP_S = 60.0
_STEP_LIMIT_TEXT = {
    "zh": "已达到 {n} 步上限，已停止，未继续扣费。",
    "en": "Reached the {n}-step limit and stopped; no further charges.",
}
_LLM_FAIL_TEXT = {
    "timeout": {"zh": "模型响应超时，已重试 {r} 次仍失败，已停止，请稍后再试。",
                "en": "The model timed out; still failing after {r} retries, so the task stopped. "
                      "Please try again later."},
    "429": {"zh": "模型请求过于频繁（HTTP 429），已重试 {r} 次仍失败，已停止，请稍后再试。",
            "en": "Too many requests to the model (HTTP 429); still failing after {r} retries, "
                  "so the task stopped. Please try again later."},
    "5xx": {"zh": "模型服务出错（HTTP {status}），已重试 {r} 次仍失败，已停止，请稍后再试。",
            "en": "The model service failed (HTTP {status}); still failing after {r} retries, "
                  "so the task stopped. Please try again later."},
}
# The paid guard's cancel / refusal texts (api/paid_guard.py) and a declined confirm: the step shows
# 已取消 / Cancelled, never success (#232, regression case 13). Same patterns as src/ui/stepState.ts.
_CANCEL_RE = re.compile(
    r'"cancelled"\s*:\s*true|"status"\s*:\s*"declined"|已取消该生成，未扣费|'
    r"Cancelled this generation; nothing was charged|已取消：未确认费用|Cancelled: cost not confirmed|"
    r"已取消，没有扣费。|Cancelled\. Nothing was charged\.")
# #393: shared over-quote card schema (also imported by src/ui/ChatMessage.tsx). One definition.
OVER_QUOTE = json.loads((Path(__file__).with_name("over_quote.json")).read_text(encoding="utf-8"))


def over_quote_spec(lang: str, price: float) -> dict:
    from .run_budget import ui_credits
    c = OVER_QUOTE["copy"]["zh" if lang == "zh" else "en"]
    credits = ui_credits(price)
    return {"kind": OVER_QUOTE["kind"], "prompt": c["body"].format(credits=credits), "credits": credits,
            "options": [{"id": OVER_QUOTE["decline"], "label": c["decline"]},
                        {"id": OVER_QUOTE["confirm"], "label": c["confirm"]}],
            "min_selections": 1, "max_selections": 1, "allow_other": False}


# #236: image tools covered by the #133 table. Video is outside that table.
_FALLBACK_TOOLS = frozenset({"generate_image", "edit_image", "edit_region"})
_GUARD_RE = re.compile(
    r"未继续扣费|no further charges|不要再提交|do not resubmit|blocked before submitting",
    re.I)
_MODEL_FAIL_RE = re.compile(
    r"wavespeed|generation submit failed|unknown model|task failed|调用失败|生成失败",
    re.I)
_REPEAT_STOP_TEXT = {
    "zh": "任务卡在重复步骤，已停止，未继续扣费。",
    "en": "The task got stuck repeating a step and was stopped; no further "
          "charges.",
}
# Same wording as the chat panel's TOOL_LABELS (src/bot.ts + locales).
_STEP_LABELS: dict[str, tuple[str, str]] = {
    'ToolSearch': ('查找工具', 'Find tools'),
    'tool_search': ('查找工具', 'Find tools'),
    'server_info': ('查看状态', 'Check status'),
    'get_canvas': ('查看画布', 'View canvas'),
    'view_canvas': ('观察画面', 'Look at canvas'),
    'view_video': ('查看视频', 'Watch video'),
    'list_models': ('查看模型', 'View models'),
    'brand_kits': ('查看品牌套件', 'View brand kit'),
    'generate_image': ('生成图像', 'Generate image'),
    'generate_video': ('生成视频', 'Generate video'),
    'edit_video': ('编辑视频', 'Edit video'),
    'edit_image': ('编辑图片', 'Edit image'),
    'animate_image': ('动态图片', 'Animate Image'),
    'upscale_image': ('放大', 'Upscale'),
    'remove_background': ('去背景', 'Remove Background'),
    'expand_image': ('扩图', 'Expand image'),
    'split_layers': ('图层拆分', 'Split Layers'),
    'change_angle': ('多角度', 'Multi-Angle'),
    'replace_text': ('编辑文字', 'Edit Text'),
    'edit_region': ('局部重绘', 'Inpaint'),
    'erase_region': ('橡皮工具', 'Eraser'),
    'move_object': ('移动对象', 'Move Object'),
    'style_transfer': ('风格迁移', 'Style Transfer'),
    'vectorize_image': ('矢量化', 'Vectorize'),
    'extend_video': ('视频延长', 'Extend Video'),
    'upscale_video': ('视频放大', 'Upscale Video'),
    'remove_video_background': ('去背景', 'Remove Background'),
    'generate_music': ('配乐', 'Music'),
    'generate_sound_effect': ('音效', 'Sound effect'),
    'text_to_speech': ('配音', 'Voiceover'),
    'edit_elements': ('编辑元素', 'Edit Elements'),
    'create_mockup': ('样机', 'Mockup'),
    'place_design': ('设计稿', 'Design'),
    'image_to_3d': ('转 3D', 'Image to 3D'),
    'wait_generation': ('等待生成结果', 'Wait for results'),
    'place_html': ('放置网页', 'Place web page'),
    'create_slides': ('制作 PPT', 'Create PPT'),
    'add_text': ('添加文字', 'Add text'),
    'add_shape': ('添加形状', 'Add shape'),
    'create_frame': ('创建画板', 'Create artboard'),
    'update_shapes': ('调整元素', 'Adjust elements'),
    'delete_shapes': ('删除元素', 'Delete elements'),
    'focus': ('定位元素', 'Locate elements'),
    'memory': ('记忆', 'Memory'),
    'skill': ('技能', 'Skill'),
    'custom_workflow': ('自定义工作流', 'Custom workflows'),
    'ask_user': ('向你提问', 'Ask you'),
    'update_plan': ('计划', 'Plan'),
    'quote_plan': ('确认费用', 'Confirm cost'),
}
_CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
_SKILL_HINT_RE = re.compile(
    r"Use the ComfyArt skill [\s\S]*?then follow those instructions\.")


def _reply_lang(user_text: str) -> str:
    """Reply in the user's language (same rule as AGENT_GUIDE)."""
    text = _SKILL_HINT_RE.sub("", user_text or "")
    return "zh" if _CJK_RE.search(text) else "en"


def _call_key(name: str, args: dict) -> str:
    return name + "\x00" + json.dumps(args, sort_keys=True, ensure_ascii=False)


def _skill_read_key(name: str, args: dict) -> str:
    if name != "skill" or str(args.get("action") or "").lower() != "read":
        return ""
    ref = args.get("name") or args.get("id") or ""
    return str(ref).strip().lower()


def _step_label(name: str, args: dict, lang: str) -> str:
    zh = lang == "zh"
    base = re.sub(r"^mcp__\w+__", "", name or "")
    if base == "skill":
        ref = str(args.get("name") or args.get("id") or "").strip()
        if str(args.get("action") or "").lower() == "read" and ref:
            return f"读取技能：{ref}" if zh else f"Read skill: {ref}"
    pair = _STEP_LABELS.get(base)
    if pair:
        return pair[0] if zh else pair[1]
    return "其他步骤" if zh else "Other step"


class LlmHttpError(RuntimeError):
    """A non-2xx answer; keeps the status and Retry-After for the retry policy (#232)."""

    def __init__(self, status: int, text: str, retry_after: Optional[float] = None) -> None:
        super().__init__(f"HTTP {status}: {text[:300]}")
        self.status = status
        self.body = text or ""  # #493: full text, the overflow guard reads the window from it
        self.retry_after = retry_after


def _retry_after(value: Optional[str]) -> Optional[float]:
    try:
        return max(0.0, float(str(value).strip())) if value else None
    except ValueError:
        return None


def _tool_base(name: str) -> str:
    return re.sub(r"^mcp__\w+__", "", name or "")


def _json_obj(text: str) -> Optional[dict]:
    body = text or ""
    for prefix in ("[tool error] ", "[error] "):
        if body.startswith(prefix):
            body = body[len(prefix):]
            break
    try:
        data = json.loads(body)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _payload_failed(data: dict) -> bool:
    """A model run failed. A declined confirm or an explicit same-model refusal is not one."""
    status = str(data.get("status") or "")
    if status in ("declined", "cancelled") or data.get("cancelled") or data.get("same_model_retry") is False:
        return False
    if status in ("failed", "error"):
        return True
    err = data.get("error")
    if not err or status in ("done", "running"):
        return False
    blob = str(err)
    return bool(data.get("model") or data.get("model_choice") or _MODEL_FAIL_RE.search(blob))


def model_call_failed(name: str, args: dict, text: str) -> Optional[str]:
    """The model id that failed, '' when the payload omits it, or None when this is not a model failure.

    '' means the caller should use the id from the call that started the job. A cost-confirm
    decline and a paid-guard refusal are not model failures, so they never switch models.
    """
    base = _tool_base(name)
    if base not in _FALLBACK_TOOLS and base != "wait_generation":
        return None
    if _CANCEL_RE.search(text or "") or _GUARD_RE.search(text or ""):
        return None
    data = _json_obj(text or "")
    if base == "wait_generation":
        if not isinstance(data, dict):
            return None
        bad = [r for r in data.get("results") or []
               if isinstance(r, dict) and r.get("status") == "error" and not r.get("cancelled")]
        if not bad:
            return None
        return str(bad[0].get("model") or "")
    failed = isinstance(data, dict) and _payload_failed(data)
    if not failed and ((text or "").startswith("[tool error]") or (text or "").startswith("[error]")):
        failed = _MODEL_FAIL_RE.search(text or "") is not None
    if not failed:
        return None
    if isinstance(data, dict):
        mc = data.get("model_choice") if isinstance(data.get("model_choice"), dict) else {}
        found = mc.get("model") or data.get("model") or ""
        if found:
            return str(found)
    return str((args or {}).get("model") or (args or {}).get("edit_model") or "")


def _remember_generation(gens: dict, name: str, args: dict, text: str) -> None:
    base = _tool_base(name)
    if base not in _FALLBACK_TOOLS or (text or "").startswith(("[tool error]", "[error]")):
        return
    data = _json_obj(text)
    if not isinstance(data, dict) or data.get("error") or data.get("cancelled"):
        return
    if str(data.get("status") or "") in ("failed", "error", "declined", "cancelled"):
        return
    mc = data.get("model_choice") if isinstance(data.get("model_choice"), dict) else {}
    model = str(mc.get("model") or data.get("model") or "")
    call = {k: v for k, v in (args or {}).items() if k != "fallback_for"}
    for gid in data.get("ids") or []:
        if gid:
            gens[str(gid)] = {"name": base, "args": call, "model": model}


def _cost_block_note(failed: str, target: str, lang: str) -> str:
    zh = f"未改用备用模型 {target}：再提交会超出本轮费用规则，没有用 {failed} 再次提交。"
    en = (f"Did not switch to {target}: another submit would exceed this turn's cost rules, "
          f"so {failed} was not submitted again.")
    return f"{zh} / {en}" if lang == "zh" else f"{en} / {zh}"


def _no_switch_note(failed: str, target: str, lang: str) -> str:
    zh = f"没有同意换模型，所以没有改用 {target}，也没有用 {failed} 再次提交。"
    en = f"The switch was not accepted, so {target} was not used and {failed} was not submitted again."
    return f"{zh} / {en}" if lang == "zh" else f"{en} / {zh}"


def _retry_kind(exc: BaseException) -> str:
    """'timeout' | '429' | '5xx' for a retryable LLM failure, '' otherwise."""
    if isinstance(exc, asyncio.TimeoutError):
        return "timeout"
    if isinstance(exc, LlmHttpError):
        if exc.status == 429:
            return "429"
        if 500 <= exc.status < 600:
            return "5xx"
    return ""


def _done_items(done: list[str], zh: bool) -> str:
    counts: dict[str, int] = {}
    for label in done:
        counts[label] = counts.get(label, 0) + 1
    items = [n + (f" ×{c}" if c > 1 else "") for n, c in counts.items()]
    if zh:
        return "已完成：" + ("、".join(items) if items else "无")
    return "Done so far: " + (", ".join(items) if items else "nothing") + "."


def _with_done(head: str, done: list[str], lang: str) -> str:
    """One line for the red error notice: what happened + the steps already done (no line breaks)."""
    zh = lang == "zh"
    return head + ("" if zh else " ") + _done_items(done, zh)


def _step_limit_summary(done: list[str], limit: int, lang: str = "zh") -> str:
    return _with_done(_STEP_LIMIT_TEXT["zh" if lang == "zh" else "en"].format(n=limit), done, lang)


def _llm_fail_summary(kind: str, exc: BaseException, done: list[str], lang: str = "zh") -> str:
    status = getattr(exc, "status", "")
    head = _LLM_FAIL_TEXT[kind]["zh" if lang == "zh" else "en"].format(r=_LLM_RETRIES, status=status)
    return _with_done(head, done, lang)


def max_steps_from(value: object, default: int = _MAX_ITERATIONS) -> int:
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    lo, hi = _MAX_STEPS_RANGE
    return min(hi, max(lo, n)) if n > 0 else default


def _stop_summary(done: list[str], lang: str = "zh") -> str:
    """One line: shown in the chat panel's error notice (no line breaks)."""
    zh = lang == "zh"
    counts: dict[str, int] = {}
    for label in done:
        counts[label] = counts.get(label, 0) + 1
    items = [n + (f" ×{c}" if c > 1 else "") for n, c in counts.items()]
    if zh:
        return (_REPEAT_STOP_TEXT["zh"] + "已完成："
                + ("、".join(items) if items else "无") + "。")
    return (_REPEAT_STOP_TEXT["en"] + " Done so far: "
            + (", ".join(items) if items else "nothing") + ".")


_THINK_RE = re.compile(r"(?:<think>|^)([\s\S]*?)</think>|<think>([\s\S]*)$")

# #235: built-in agent only. External CLIs keep AGENT_GUIDE unchanged (#238).
_PLAN_QUOTE_RULE = (
    "Multi-step paid task: when the task needs two or more paid generations, "
    "call update_plan, then quote_plan, before any paid tool. quote_plan steps "
    "are {text, tool, model, arguments} for every paid step, using only the "
    "selected model (do not include a fallback model). quote_plan estimates the "
    "total and does not generate or charge. If it asks the user, wait. If they "
    "decline, stop and do not retry. If it says to start, call each paid tool "
    "with the same arguments. A single paid generation does not use quote_plan. "
    "Do not tell the user a per-step or running cost; the confirm card is the "
    "only cost display, and only when the total reaches the threshold."
)
_SYSTEM_PROMPT = AGENT_GUIDE + "\n\n" + _PLAN_QUOTE_RULE
_PLAN_REFUSE = {
    "zh": "[tool error] 这是多步付费任务。请先调用 quote_plan 列出每一个付费步骤，用户确认后再调用付费工具。这次调用没有执行。",
    "en": "[tool error] This is a multi-step paid task. Call quote_plan with every paid step and wait for the user before any paid tool. This call did not run.",
}
_QUOTE_PLAN_TOOL = {
    "type": "function",
    "function": {
        "name": QUOTE_TOOL,
        "description": (
            "Estimate the total of a multi-step paid task and, when it reaches "
            "the user's confirm limit, ask before any paid tool runs. Does not "
            "generate or charge. steps: one object per paid step with text (step "
            "name), tool, model (the selected model only; do not pass a fallback "
            "model), and arguments (the exact arguments you will pass to that "
            "tool). Call it after update_plan and before any paid tool when the "
            "task needs two or more paid generations. A single paid generation "
            "does not use this. If the result says start, call each paid tool "
            "with the same arguments. If the user declines, stop and do not retry."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "tool": {"type": "string"},
                            "model": {"type": "string"},
                            "arguments": {"type": "object"},
                        },
                        "required": ["text", "tool", "arguments"],
                    },
                },
            },
            "required": ["steps"],
        },
    },
}


_WINDOW_FIELDS = (
    "context_window", "context_length", "max_context_length",
    "max_model_len", "max_context_tokens", "n_ctx", "max_input_tokens",
)
# #390-2: LiteLLM puts the window under model_info, OpenRouter also under top_provider.
_WINDOW_NESTED = ("meta", "metadata", "details", "architecture", "model_info", "top_provider")
_DATA_URL_RE = re.compile(r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\r\n]+", re.I)
_REQ_RES = (
    re.compile(r"(?:数量|count|qty)\s*[:：]?\s*\d+\s*(?:张|幅|个|images?|pictures?|shots?)?", re.I),
    re.compile(r"\d+\s*(?:张|幅|个|images?|pictures?|shots?)", re.I),
    re.compile(r"(?:尺寸|大小|size|ratio|分辨率|resolution)\s*[:：]?\s*(?:\d+\s*[:：x×]\s*\d+|[^\s,，。;；]{1,24})", re.I),
    re.compile(r"\d+\s*[:：x×]\s*\d+"),
    re.compile(r"\d+\s*(?:px|像素|秒|seconds?|minutes?)", re.I),
    re.compile(r"(?:风格|style)\s*[:：]?\s*[^\n,，。;；]{1,40}", re.I),
    re.compile(r"[\u4e00-\u9fffA-Za-z0-9]{1,16}风格"),
    re.compile(r"(?:预算|budget|不超过|under|max)\s*[:：]?\s*\$?\d+(?:\.\d+)?", re.I),
    re.compile(r"\$\d+(?:\.\d+)?"),
)
_DECISION_RE = re.compile(
    r"(?:决定|改为|改成|就用|选定|decided|decision|we'll use|we will use|let's use|going with|switch to)"
    r"[^\n。.]{0,80}", re.I)
_FAIL_RE = re.compile(r"(?:失败|出错|报错|failed|failure|error)\s*[:：]?\s*[^\n]{0,120}", re.I)
_SHAPE_TYPE = {
    "generate_image": "image", "edit_image": "image", "upscale_image": "image",
    "remove_background": "image", "expand_image": "image", "animate_image": "image",
    "replace_text": "image", "edit_region": "image", "erase_region": "image",
    "move_object": "image", "style_transfer": "image", "vectorize_image": "image",
    "split_layers": "image", "change_angle": "image", "edit_elements": "image",
    "create_mockup": "image", "generate_video": "video", "edit_video": "video",
    "extend_video": "video", "upscale_video": "video", "remove_video_background": "video",
    "generate_music": "audio", "generate_sound_effect": "audio", "text_to_speech": "audio",
    "image_to_3d": "model3d", "add_text": "text", "add_shape": "shape",
    "create_frame": "frame", "place_html": "html", "create_slides": "slides",
}


def _positive_int(value: object) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, int):
        return value if value > 0 else 0
    if isinstance(value, float):
        return int(value) if value > 0 else 0
    if isinstance(value, str):
        try:
            n = int(value.strip())
        except ValueError:
            return 0
        return n if n > 0 else 0
    return 0


def explicit_context_window(model_info: object) -> int:
    """The context window a model payload actually states, or 0 when it does not."""
    if not isinstance(model_info, dict):
        return 0
    for key in _WINDOW_FIELDS:
        n = _positive_int(model_info.get(key))
        if n:
            return n
    for nest in _WINDOW_NESTED:
        inner = model_info.get(nest)
        if isinstance(inner, dict):
            for key in _WINDOW_FIELDS:
                n = _positive_int(inner.get(key))
                if n:
                    return n
            # #390-2: GGUF-style keys carry the architecture as a prefix
            # ("llama.context_length", "qwen2.context_length").
            for key, value in inner.items():
                if isinstance(key, str) and key.endswith(".context_length"):
                    n = _positive_int(value)
                    if n:
                        return n
    return 0


def context_window_tokens(model_info: object) -> int:
    """#234: tokens in this model's window. Unknown (or a missing payload) is the 270k fallback."""
    found = explicit_context_window(model_info)
    return found if found else _FALLBACK_CONTEXT_WINDOW


def input_token_budget(window: object, max_input: object = 0) -> int:
    """70% of the model window, capped by the endpoint's declared max_input_tokens when it
    states one (#493). A missing/invalid window uses the 270k fallback."""
    size = window if isinstance(window, int) and window > 0 else _FALLBACK_CONTEXT_WINDOW
    budget = size * _INPUT_BUDGET_PERCENT // 100
    cap = _positive_int(max_input)
    return min(budget, cap) if cap else budget


def declared_max_input(model_info: object) -> int:
    """#493: max_input_tokens a /models entry states (top level or nested), 0 when absent."""
    if not isinstance(model_info, dict):
        return 0
    n = _positive_int(model_info.get("max_input_tokens"))
    if n:
        return n
    for nest in _WINDOW_NESTED:
        inner = model_info.get(nest)
        if isinstance(inner, dict):
            n = _positive_int(inner.get("max_input_tokens"))
            if n:
                return n
    return 0


def count_tokens(text: str) -> int:
    """Token count used against the model window. CJK, kana and hangul are 1 token;
    every other character is 1/4 token (rounded up). No network and no tokenizer download."""
    if not text:
        return 0
    cjk = other = 0
    for ch in text:
        o = ord(ch)
        if ((0x3400 <= o <= 0x9FFF) or (0xF900 <= o <= 0xFAFF)
                or (0x3040 <= o <= 0x30FF) or (0xAC00 <= o <= 0xD7AF)
                or (0xFF00 <= o <= 0xFFEF)):
            cjk += 1
        else:
            other += 1
    return cjk + (other + 3) // 4


def truncate_to_tokens(text: str, limit: int) -> str:
    if limit <= 0 or not text:
        return ""
    if count_tokens(text) <= limit:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if count_tokens(text[:mid]) <= limit:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip()


def _content_tokens(content: object) -> int:
    if isinstance(content, str):
        return count_tokens(content)
    if isinstance(content, list):
        return sum(count_tokens(str(part.get("text") or ""))
                   for part in content
                   if isinstance(part, dict) and part.get("type") == "text")
    return count_tokens(str(content or ""))


def _strip_screenshots(text: str) -> str:
    """Raw screenshots never enter the summary (#234)."""
    return _DATA_URL_RE.sub("", text or "")


def _looks_raw(text: str) -> bool:
    s = (text or "").strip()
    return s.startswith("{") or s.startswith("[")


def _plain(text: str) -> str:
    text = _strip_screenshots(text).strip()
    if not text or _looks_raw(text):
        return ""
    return text


def _one_sentence(text: str, limit: int = 120) -> str:
    text = " ".join((text or "").split())
    if not text:
        return ""
    sentence = re.split(r"(?<=[。．.!?！？])\s*", text, maxsplit=1)[0]
    if len(sentence) > limit:
        sentence = sentence[:limit].rstrip()
    return sentence


def _uniq(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _requirements(text: str) -> list[str]:
    found = []
    for pattern in _REQ_RES:
        found.extend(m.group(0).strip() for m in pattern.finditer(text))
    return found


def _decisions(text: str) -> list[str]:
    return [m.group(0).strip() for m in _DECISION_RE.finditer(text)]


def _failures_in_text(text: str) -> list[dict]:
    out = []
    for m in _FAIL_RE.finditer(text):
        reason = _one_sentence(_strip_screenshots(m.group(0)), 160)
        if reason:
            out.append({"attempt": "turn", "reason": reason})
    return out


def _tool_base(name: str) -> str:
    return re.sub(r"^mcp__\w+__", "", name or "")


def _shape_ids(value: object) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, dict) and value.get("id"):
        return [str(value["id"])]
    if isinstance(value, list):
        ids: list[str] = []
        for item in value:
            ids.extend(_shape_ids(item))
        return ids
    return []


def _json_obj(text: str) -> Optional[dict]:
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _failure_reason(text: str, data: Optional[dict]) -> str:
    if isinstance(data, dict):
        for key in ("error", "message", "reason", "note"):
            val = data.get(key)
            if isinstance(val, dict):
                val = val.get("en") or val.get("zh") or ""
            if isinstance(val, str) and val.strip() and not _looks_raw(val):
                return _one_sentence(_strip_screenshots(val), 160)
        if data.get("status") in ("error", "declined", "cancelled"):
            return _one_sentence(str(data.get("status")), 160)
    cleaned = re.sub(r"^\[(?:tool error|error)\]\s*", "", _strip_screenshots(text or "")).strip()
    if not cleaned or _looks_raw(cleaned):
        return "tool failed"
    return _one_sentence(cleaned, 160)


def _shape_line(shape: dict) -> str:
    prompt = _one_sentence(_strip_screenshots(str(shape.get("prompt") or "")), 120)
    return (f"id={shape.get('id')} type={shape.get('type') or ''} "
            f"model={shape.get('model') or ''} prompt={prompt}")


def turn_result_from_blocks(blocks: Optional[list[dict]]) -> Optional[dict]:
    """#234: one record per turn — each placed shape (id, type, model, one-sentence
    prompt) and each failed attempt. Raw tool JSON and screenshots are not kept."""
    pending: list[dict] = []
    shapes: list[dict] = []
    failures: list[dict] = []
    seen: set[str] = set()

    def add_shape(sid: str, kind: str, model: str, prompt: str) -> None:
        sid = str(sid or "").strip()
        if not sid or sid in seen:
            return
        seen.add(sid)
        shapes.append({
            "id": sid,
            "type": kind or "shape",
            "model": model or "",
            "prompt": _one_sentence(_strip_screenshots(prompt), 120),
        })

    def slot_for(job: str) -> Optional[dict]:
        if job:
            for slot in reversed(pending):
                if job in slot["ids"]:
                    return slot
        for slot in reversed(pending):
            if slot["tool"] in _SHAPE_TYPE:
                return slot
        return None

    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        name = _tool_base(str(block.get("name") or ""))
        if kind == "tool_use":
            args = block.get("input") if isinstance(block.get("input"), dict) else {}
            prompt = str(args.get("prompt") or args.get("text") or args.get("to") or "")
            model = str(args.get("model") or args.get("edit_model") or "")
            pending.append({"tool": name, "prompt": prompt, "model": model, "ids": []})
            continue
        if kind != "tool_result":
            continue
        text = str(block.get("text") or "")
        data = _json_obj(text)
        status = str(block.get("status") or "")
        failed = (status in ("error", "cancelled")
                  or text.startswith("[tool error]") or text.startswith("[error]")
                  or (isinstance(data, dict) and (
                      data.get("cancelled") or data.get("status") in ("error", "declined", "cancelled"))))
        if failed:
            failures.append({"attempt": name or "tool", "reason": _failure_reason(text, data)})
            continue
        if not isinstance(data, dict):
            continue
        model = str(data.get("model") or "")
        slot = next((s for s in reversed(pending) if s["tool"] == name), None)
        if slot is not None:
            if model and not slot["model"]:
                slot["model"] = model
            slot["ids"] = [str(i) for i in (data.get("ids") or []) if i]
        if name == "wait_generation":
            for res in data.get("results") or []:
                if not isinstance(res, dict):
                    continue
                if res.get("status") in ("error", "declined", "cancelled") or res.get("error") or res.get("cancelled"):
                    failures.append({
                        "attempt": name,
                        "reason": _failure_reason(str(res.get("error") or res.get("status") or ""), res),
                    })
                    continue
                job = str(res.get("id") or "")
                owner = slot_for(job)
                kind_name = _SHAPE_TYPE.get((owner or {}).get("tool") or "", "shape")
                model_name = (owner or {}).get("model") or ""
                prompt = (owner or {}).get("prompt") or ""
                for sid in _shape_ids(res.get("shapes")):
                    add_shape(sid, kind_name, model_name, prompt)
            continue
        if name in _SHAPE_TYPE:
            owner = slot or {}
            kind_name = "frame" if name == "create_slides" else _SHAPE_TYPE[name]
            model_name = owner.get("model") or model
            prompt = owner.get("prompt") or ""
            if data.get("id"):
                add_shape(str(data["id"]), kind_name, model_name, prompt)
            for sid in _shape_ids(data.get("frames")):
                add_shape(str(sid), "frame", model_name, prompt)
            for sid in _shape_ids(data.get("shapes")):
                add_shape(str(sid), kind_name, model_name, prompt)
    if not shapes and not failures:
        return None
    return {"shapes": shapes, "failures": failures}


def _result_suffix(result: Optional[dict]) -> str:
    if not isinstance(result, dict):
        return ""
    parts = [_shape_line(s) for s in result.get("shapes") or [] if isinstance(s, dict) and s.get("id")]
    for fail in result.get("failures") or []:
        if isinstance(fail, dict) and (fail.get("attempt") or fail.get("reason")):
            parts.append(f"failed {fail.get('attempt') or 'tool'}: {fail.get('reason') or ''}".rstrip())
    if not parts:
        return ""
    return "[turn result] " + "; ".join(parts)


def _group_turns(history: Optional[list[dict]]) -> list[list[dict]]:
    turns: list[list[dict]] = []
    current: list[dict] = []
    for msg in history or []:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue
        text = str(msg.get("text") or "").strip()
        result = msg.get("result") if isinstance(msg.get("result"), dict) else None
        refs = msg.get("refs") if isinstance(msg.get("refs"), list) else None
        if not text and not result and not refs:
            continue
        if role == "user" and current:
            turns.append(current)
            current = []
        current.append({"role": role, "text": text, "result": result, "refs": refs})
    if current:
        turns.append(current)
    return turns


def _ref_lines_for(msg: dict) -> str:
    """#422: ensure previous-turn image refs appear even if text omitted them."""
    refs = msg.get("refs") or []
    if not refs:
        return ""
    text = msg.get("text") or ""
    # blocks_text already embeds Attached-lines; don't duplicate
    if "[Attached " in text or "shape id " in text:
        return ""
    try:
        from ..api.bot_turns import format_ref_lines
    except ImportError:
        from ComfyArt.api.bot_turns import format_ref_lines  # type: ignore
    return "\n".join(format_ref_lines(refs))


def _render_turns(turns: list[list[dict]]) -> list[dict]:
    out: list[dict] = []
    for turn in turns:
        for msg in turn:
            suffix = _result_suffix(msg.get("result")) if msg["role"] == "assistant" else ""
            text = msg["text"]
            refs = _ref_lines_for(msg)
            if refs:
                text = f"{text}\n{refs}" if text else refs
            content = f"{text}\n{suffix}" if text and suffix else (text or suffix)
            if content:
                out.append({"role": msg["role"], "content": content})
    return out


def _summarize_turns(turns: list[list[dict]]) -> str:
    """Goals, requirements, decisions, image refs, shapes and failures. Nothing else."""
    goals: list[str] = []
    reqs: list[str] = []
    decisions: list[str] = []
    shapes: list[dict] = []
    failures: list[dict] = []
    image_refs: list[dict] = []
    seen: set[str] = set()
    seen_refs: set[str] = set()
    for turn in turns:
        for msg in turn:
            result = msg.get("result") if isinstance(msg.get("result"), dict) else {}
            for shape in result.get("shapes") or []:
                if isinstance(shape, dict) and shape.get("id") and str(shape["id"]) not in seen:
                    seen.add(str(shape["id"]))
                    shapes.append(shape)
            for fail in result.get("failures") or []:
                if isinstance(fail, dict):
                    failures.append(fail)
            # #422: keep previous-turn image refs when compressing
            for r in msg.get("refs") or []:
                if not isinstance(r, dict):
                    continue
                key = str(r.get("id") or r.get("src") or "")
                if key and key not in seen_refs:
                    seen_refs.add(key)
                    image_refs.append(r)
            text = _plain(msg.get("text") or "")
            if not text:
                continue
            if msg["role"] == "user":
                goal = _one_sentence(text, 160)
                if goal:
                    goals.append(goal)
                reqs.extend(_requirements(text))
            else:
                failures.extend(_failures_in_text(text))
            decisions.extend(_decisions(text))
    lines = [_SUMMARY_HEADER]
    if goals:
        lines.append("Goals: " + "; ".join(_uniq(goals)))
    if reqs:
        lines.append("Requirements: " + "; ".join(_uniq(reqs)))
    if decisions:
        lines.append("Decisions: " + "; ".join(_uniq(decisions)))
    if image_refs:
        lines.append("Image refs:")
        for r in image_refs:
            kind = r.get("kind") or "image"
            sid = r.get("id") or ""
            src = r.get("src") or ""
            bit = f"- {kind}"
            if sid:
                bit += f" id={sid}"
            if src:
                bit += f" src={src}"
            lines.append(bit)
    # Failures stay ahead of the shape list so the summary_token_cap() limit drops extra
    # shapes before it drops a failed attempt.
    if failures:
        lines.append("Failures:")
        for fail in failures:
            attempt = str(fail.get("attempt") or "tool")
            reason = _one_sentence(_strip_screenshots(str(fail.get("reason") or "")), 160)
            if attempt or reason:
                lines.append(f"- {attempt}: {reason}")
    if shapes:
        lines.append("Shapes:")
        lines.extend("- " + _shape_line(s) for s in shapes)
    if len(lines) == 1:
        lines.append("Earlier turns were compressed.")
    return "\n".join(lines)


def refit_messages(messages: list[dict], window: int, max_input: int = 0) -> list[dict]:
    """#493: drop the oldest non-system messages until the rest fit min(70% of `window`,
    `max_input`) (P1). The last user message and the latest steps are kept; a tool result never
    starts the kept tail."""
    budget = input_token_budget(window, max_input)
    system = [m for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]
    while len(rest) > 1 and _message_tokens(system + rest) > budget:
        rest = rest[1:]
        while len(rest) > 1 and rest[0].get("role") == "tool":
            rest = rest[1:]
    return system + rest


def _message_tokens(messages: list[dict]) -> int:
    return sum(count_tokens(str(m.get("content") or "")) for m in messages)


def _owner_kw(turn) -> dict:
    """#390 ownership keys for stored data (local defaults in the single-user build)."""
    from .run_budget import LOCAL_OWNER_ID, LOCAL_PROJECT_ID, LOCAL_WORKSPACE_ID
    return {"owner_id": str(getattr(turn, "owner_id", "") or LOCAL_OWNER_ID),
            "workspace_id": str(getattr(turn, "workspace_id", "") or LOCAL_WORKSPACE_ID),
            "project_id": str(getattr(turn, "project_id", "") or LOCAL_PROJECT_ID)}


def fit_history(history: Optional[list[dict]], *, context_window: Optional[int] = None,
                reserved_tokens: int = 0, max_input_tokens: int = 0) -> list[dict]:
    """History that fits the input budget. Over the budget, the last 6 turns stay
    verbatim and earlier turns are one summary of at most summary_token_cap(window) tokens."""
    budget = max(0, input_token_budget(context_window, max_input_tokens) - max(0, int(reserved_tokens or 0)))
    turns = _group_turns(history)
    verbatim = _render_turns(turns)
    if _message_tokens(verbatim) <= budget:
        return verbatim
    head, tail = turns[:-_VERBATIM_TURNS], turns[-_VERBATIM_TURNS:]
    tail_msgs = _render_turns(tail)
    room = min(summary_token_cap(context_window), max(0, budget - _message_tokens(tail_msgs)))
    summary = truncate_to_tokens(_summarize_turns(head), room) if head and room else ""
    out: list[dict] = []
    if summary.strip():
        out.append({"role": "system", "content": summary})
    out.extend(tail_msgs)
    return out


def _user_content(text: str, attachments: Optional[list[dict]]):
    images = [
        {"type": "image_url",
         "image_url": {"url": f"data:{a.get('media_type') or 'image/jpeg'}"
                              f";base64,{a['data']}"}}
        for a in attachments or [] if a.get("data")
    ]
    if not images:
        return text
    return [{"type": "text", "text": text}, *images]


KEEP_SCREENSHOTS = 2  # #233: only the latest N tool screenshots go to the LLM each round
_TOOL_IMAGES_PREFIX = "Images returned by "


def _prune_screenshots(messages: list[dict], keep: int = KEEP_SCREENSHOTS) -> list[dict]:
    """Return a copy of `messages` where only the newest `keep` tool-returned images stay; each older
    one becomes a one-line text placeholder. The user's own attachments are never touched, and the
    stored history (`messages` itself) is left as is, so a later round can still prune correctly."""
    seen = 0
    out: list[dict] = [None] * len(messages)  # type: ignore[list-item]
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        c = m.get("content")
        if (m.get("role") != "user" or not isinstance(c, list) or not c
                or not str(c[0].get("text", "")).startswith(_TOOL_IMAGES_PREFIX)):
            out[i] = m
            continue
        parts = []
        for part in reversed(c):
            if part.get("type") == "image_url":
                seen += 1
                if seen > keep:
                    part = {"type": "text", "text": "[older screenshot omitted]"}
            parts.append(part)
        out[i] = {**m, "content": parts[::-1]}
    return out


class _PlanGate:
    """#235: after the user presses 开始, only the quoted calls may run.

    Under the threshold, and when the model never calls quote_plan, each job
    still confirms on its own (#127). Refusing those calls would block a plan
    item the user can still approve one at a time.
    """

    def __init__(self) -> None:
        self.strict = False
        self.keys: set[tuple] = set()

    def allow(self, quote, strict: bool) -> None:
        self.strict = strict
        self.keys = set(quote.keys)

    def blocks(self, name: str, args: dict) -> bool:
        if not self.strict or name not in PAID_TOOLS:
            return False
        return canon_key(name, args) not in self.keys


TEST_TIMEOUT_S = 10.0


async def test_local_llm(*, base_url: str, api_key: str = "", model: str = "",
                         timeout: float = TEST_TIMEOUT_S) -> dict:
    """#321: light probe — reachability, auth, optional model id. No chat completion."""
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return {"ok": False, "code": "no_url"}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{base}/models",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                body = await resp.text()
                if resp.status in (401, 403):
                    return {"ok": False, "code": "auth_failed", "status": resp.status}
                if resp.status >= 400:
                    return {"ok": False, "code": "unreachable", "status": resp.status}
                try:
                    data = json.loads(body) if body else {}
                except ValueError:
                    data = {}
    except asyncio.TimeoutError:
        return {"ok": False, "code": "timeout"}
    except (aiohttp.ClientError, OSError) as e:
        return {"ok": False, "code": "unreachable", "detail": str(e)[:200]}

    rows = data.get("data") if isinstance(data, dict) else None
    models = [
        str(m.get("id") or "")
        for m in (rows or [])
        if isinstance(m, dict) and m.get("id")
    ]
    want = (model or "").strip()
    if want and models and want not in models:
        return {
            "ok": False,
            "code": "model_missing",
            "model": want,
            "models": models[:20],
        }
    return {"ok": True, "code": "ok", "models": models[:20]}


class LocalLlmProvider(AgentProvider):
    id = "local-llm"
    label = "Local LLM"

    def __init__(self, *, base_url: Callable[[], str]) -> None:
        self._base_url_source = base_url
        self._probe_cache: Optional[tuple[float, str, ProviderStatus]] = None

    def capabilities(self) -> ProviderCaps:
        return ProviderCaps(stateful=False, tools="mcp", attachments=True)

    def _base_url(self) -> str:
        return self._base_url_source().strip().rstrip("/")

    def _api_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        key = os.environ.get(_API_KEY_ENV, "")
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    @staticmethod
    def _mcp_headers() -> dict:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    async def _request_json(self, session: aiohttp.ClientSession, method: str,
                            url: str, *, headers: dict,
                            json_body: Optional[dict] = None,
                            timeout: float = 120) -> dict:
        async with session.request(
            method, url, headers=headers, json=json_body,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise LlmHttpError(resp.status, text,
                                   _retry_after(resp.headers.get("Retry-After")))
            return json.loads(text) if text else {}

    async def probe(self) -> ProviderStatus:
        now = time.monotonic()
        base = self._base_url()
        if self._probe_cache and self._probe_cache[1] == base and now - self._probe_cache[0] < PROBE_CACHE_S:
            return self._probe_cache[2]
        if not base:
            status = ProviderStatus(
                available=False,
                detail="no endpoint configured — set the Local LLM endpoint "
                       "URL under Agent Settings",
            )
            self._probe_cache = (now, base, status)
            return status
        try:
            async with aiohttp.ClientSession() as session:
                data = await self._request_json(
                    session, "GET", f"{base}/models",
                    headers=self._api_headers(), timeout=10,
                )
            models = [str(m.get("id") or "") for m in data.get("data") or []]
            models = [m for m in models if m]
            if not models:
                status = ProviderStatus(
                    available=False,
                    detail="the endpoint is up but reports no models — load "
                           "a model first",
                )
            else:
                status = ProviderStatus(
                    available=True, version=models[0], logged_in=True,
                )
        except _NET_ERRORS as e:
            status = ProviderStatus(available=False, detail=str(e))
        self._probe_cache = (now, base, status)
        return status

    async def list_models(self) -> list[str]:
        base = self._base_url()
        if not base:
            return []
        try:
            async with aiohttp.ClientSession() as session:
                data = await self._request_json(
                    session, "GET", f"{base}/models",
                    headers=self._api_headers(), timeout=10,
                )
            models = [str(m.get("id") or "") for m in data.get("data") or []]
            return [m for m in models if m]
        except _NET_ERRORS:
            return []

    async def _mcp_list_tools(self, session: aiohttp.ClientSession,
                              endpoint: str) -> list[dict]:
        data = await self._request_json(
            session, "POST", endpoint, headers=self._mcp_headers(),
            json_body={"jsonrpc": "2.0", "id": "tools", "method": "tools/list",
                       "params": {}}, timeout=30,
        )
        tools = (data.get("result") or {}).get("tools") or []
        return [t for t in tools if t.get("name") in CORE_MCP_TOOLS]

    async def _mcp_call_tool(self, session: aiohttp.ClientSession,
                             endpoint: str, name: str,
                             arguments: dict) -> tuple[str, list[str]]:
        data = await self._request_json(
            session, "POST", endpoint, headers=self._mcp_headers(),
            json_body={"jsonrpc": "2.0", "id": f"call-{name}",
                       "method": "tools/call",
                       "params": {"name": name, "arguments": arguments}},
            timeout=560 if name == "ask_user" else 200,
        )
        result = data.get("result") or {}
        content = result.get("content")
        text = self._extract_text(content)
        images = [f"data:{b.get('mimeType') or 'image/png'};base64,{b['data']}"
                  for b in content or [] if isinstance(b, dict)
                  and b.get("type") == "image" and b.get("data")]
        if result.get("isError"):
            return "[tool error] " + text, []
        return text, images

    @staticmethod
    def _extract_text(content: object) -> str:
        if isinstance(content, str):
            return content
        parts = []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text") or ""))
        return "\n".join(parts)

    @staticmethod
    def _build_tools(tools: list[dict]) -> list[dict]:
        return [{
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": str(tool.get("description") or "").strip(),
                "parameters": tool.get("inputSchema")
                or {"type": "object", "properties": {}},
            },
        } for tool in tools]

    @staticmethod
    def _history_messages(history: Optional[list[dict]], *,
                          context_window: Optional[int] = None,
                          reserved_tokens: int = 0, max_input_tokens: int = 0) -> list[dict]:
        """#234: keep history inside 70% of the model window. Unknown window = 270k fallback."""
        return fit_history(history, context_window=context_window,
                           reserved_tokens=reserved_tokens, max_input_tokens=max_input_tokens)

    async def _context_window(self, session: aiohttp.ClientSession, model: str) -> int:
        """Tokens in `model`'s window, from the endpoint's /models payload. If it does
        not say, the model is missing, or the request fails: #493 known-model table,
        then the 270k fallback. A window learnt from an overflow error (#493) is cached
        here too.

        #390-2: cached per (endpoint, model). The same model id on another endpoint
        (e.g. a local 8k quant vs. a hosted 128k one) is looked up again."""
        cache: dict = getattr(self, "_model_windows", None) or {}
        self._model_windows = cache
        if getattr(self, "_max_inputs", None) is None:
            self._max_inputs: dict = {}
        base = self._base_url()
        if not base:
            return resolve_context_window(model)
        key = (base, model)
        if model and key in cache:
            return cache[key]
        try:
            data = await self._request_json(
                session, "GET", f"{base}/models", headers=self._api_headers(), timeout=10)
        except _NET_ERRORS:
            return resolve_context_window(model)
        if isinstance(data, dict):
            for entry in data.get("data") or []:
                if not isinstance(entry, dict) or not entry.get("id"):
                    continue
                # Every listed id is cached from this one fetch (declared window, else
                # table / fallback), so a model without a window does not refetch.
                cache[(base, str(entry["id"]))] = (explicit_context_window(entry)
                                                   or resolve_context_window(str(entry["id"])))
                max_input = declared_max_input(entry)
                if max_input:
                    self._max_inputs[(base, str(entry["id"]))] = max_input
        # Remember a miss too (as the table / fallback value), so a model that never
        # advertises a window does not refetch /models on every turn. A failed
        # request is not cached.
        if model and key not in cache:
            cache[key] = resolve_context_window(model)
        return cache.get(key) or resolve_context_window(model)

    def _declared_max_input(self, model: str) -> int:
        """#493: max_input_tokens the endpoint's /models declared for `model`, 0 when unknown."""
        return (getattr(self, "_max_inputs", None) or {}).get((self._base_url(), model), 0)

    def _input_budget(self, model: str, window: int) -> int:
        """#493: input budget for this endpoint + model = min(70% of window, declared max_input_tokens)."""
        return input_token_budget(window, self._declared_max_input(model))

    async def _wait_stage_done(self, session: aiohttp.ClientSession,
                               endpoint: str, args: dict, model: str,
                               handle: TurnHandle) -> str:
        args = dict(args)
        args.setdefault("timeout_s", 170)
        unloaded = bool(lms.lms_bin()) and await lms.unload_models()
        try:
            raw = ""
            for _ in range(_MAX_WAIT_SLICES):
                if handle.stop_requested:
                    break
                raw, _images = await self._mcp_call_tool(
                    session, endpoint, "wait_generation", args)
                try:
                    data = json.loads(raw)
                except ValueError:
                    break
                if not isinstance(data, dict) or data.get("status") != "running":
                    break
            return raw
        finally:
            if unloaded:
                await lms.load_model(model)

    def _max_steps(self) -> int:
        """#232: the step limit is configurable (env here; the built-in agent also reads its setting)."""
        return max_steps_from(os.environ.get(_MAX_STEPS_ENV), _MAX_ITERATIONS)

    def _run_policy(self):
        """#391: the single policy entry (system -> workspace -> user -> plan); env here."""
        from .run_budget import resolve_policy
        return resolve_policy()

    def _paid_run_context(self, turn: TurnRequest, *, window: int, lang: str, policy):
        """#400: legacy fixed-step loop still needs a RunContext so paid tools hit the same
        paid_gate as agent-loop (over-quote confirm / unattended skip / pending marker).
        store=None keeps legacy non-resumable (no run_ events); gating does not need the store."""
        import uuid
        from . import agent_loop
        from .run_budget import BudgetLimits, ProgressTracker, RunBudget
        limits = BudgetLimits.from_policy(policy, window=window, tier="single_gen")
        budget = RunBudget(limits, k=policy["projection_window"], soft_fraction=policy["soft_fraction"],
                           clock=self._run_clock)
        tracker = ProgressTracker(policy["stall_steps"], policy["readonly_max"],
                                  policy["tool_fail_max"], policy["repeat_max"])
        ctx = agent_loop.RunContext(
            run_id=f"legacy-{uuid.uuid4().hex[:12]}", store=None,
            lease_owner=turn.lease_owner or f"legacy-{uuid.uuid4().hex[:8]}",
            policy=policy, budget=budget, tracker=tracker,
            mode=turn.run_mode or "interactive",
            goal=turn.goal_text or turn.user_text, lang=lang,
            owner_id=turn.owner_id, workspace_id=turn.workspace_id,
            project_id=turn.project_id or "local", window=window)
        ctx.pricer = self._price_call
        return ctx

    _run_clock = staticmethod(time.monotonic)  # #391 wall-time source (tests swap it)

    def _run_store(self):
        from .run_store import get_run_store
        return get_run_store()

    async def _price_call(self, name: str, args: dict):
        """#391: price of one paid call (the quote it is capped by). None when unknown."""
        model = str(args.get("model") or "")
        if not model:
            return None
        return await self._price_one(model, args)

    async def _llm_request(self, session: aiohttp.ClientSession, url: str,
                           body: dict, emit: EmitFn, handle: TurnHandle) -> dict:
        """POST to the LLM; a timeout, 429 or 5xx is retried _LLM_RETRIES times. Each wait shows as a
        retry row in the chat (429: with a countdown). Tool calls never go through here, so a paid
        run is never repeated."""
        attempt = 0
        while True:
            try:
                return await self._request_json(
                    session, "POST", url, headers=self._api_headers(),
                    json_body=body, timeout=_LLM_TIMEOUT_S)
            except (asyncio.TimeoutError, LlmHttpError) as e:
                kind = _retry_kind(e)
                if not kind or attempt >= _LLM_RETRIES or handle.stop_requested:
                    raise
                if kind == "429":
                    ra = getattr(e, "retry_after", None)
                    wait = min(_RATE_LIMIT_WAIT_CAP_S,
                               ra if ra is not None else _RATE_LIMIT_WAIT_S[attempt])
                else:
                    wait = _RETRY_BACKOFF_S[attempt]
                attempt += 1
                _log.warning("[ComfyArt/local-llm] LLM %s, retry %d/%d in %.1fs",
                             kind, attempt, _LLM_RETRIES, wait)
                await emit(BotEvent(t="retry", name=kind, input={
                    "attempt": attempt, "max": _LLM_RETRIES, "wait_s": round(wait, 1),
                    "until": int((time.time() + wait) * 1000),
                    "http_status": getattr(e, "status", 0)}))
                end = time.monotonic() + wait
                while not handle.stop_requested and time.monotonic() < end:
                    await asyncio.sleep(min(0.25, max(0.0, end - time.monotonic())))
                if handle.stop_requested:
                    raise e

    def remember_window(self, model: str, window: int) -> None:
        """#493: store a window for (current endpoint, model), e.g. one learnt from an overflow."""
        if not model or not isinstance(window, int) or window <= 0:
            return
        cache: dict = getattr(self, "_model_windows", None) or {}
        self._model_windows = cache
        cache[(self._base_url(), model)] = window

    async def _llm_request_fit(self, session: aiohttp.ClientSession, url: str, body: dict,
                               emit: EmitFn, handle: TurnHandle, *, model: str, window: int,
                               refit) -> tuple[dict, int]:
        """#493 overflow guard around _llm_request. On a context-exceeded error: read the real
        window from the error (else max(OVERFLOW_FLOOR, window * OVERFLOW_SHRINK)), cache it for (endpoint, model),
        re-fit the messages with `refit(messages, new_window)` and resend exactly once. A second
        overflow (or any other error) is raised. Returns (data, window used).

        Loop guard / billing: the failed request returned no message, so it reaches neither the
        tool-call repeat detector nor charge_request; the caller sees one response for one step."""
        try:
            return await self._llm_request(session, url, body, emit, handle), window
        except LlmHttpError as e:
            if not is_context_overflow(e) or handle.stop_requested:
                raise
            stated = parse_overflow_window(e.body)
            if not 0 < stated < window and window <= OVERFLOW_FLOOR:
                raise  # #493 P2: no number and already at/below the floor: nothing smaller to try
            new_window = stated if 0 < stated < window else min(
                window - 1, max(OVERFLOW_FLOOR, int(window * OVERFLOW_SHRINK)))  # P2: never >= original
            _log.warning("[ComfyArt/local-llm] context overflow for %s: window %d -> %d, resend once",
                         model, window, new_window)
            self.remember_window(model, new_window)
            # #493 B2: re-fit to min(70% of the new window, declared max_input_tokens).
            fit_window = new_window
            max_input = self._declared_max_input(model)
            if max_input:
                fit_window = min(new_window, max_input * 100 // _INPUT_BUDGET_PERCENT)
            resent = {**body, "messages": refit(list(body.get("messages") or []), fit_window)}
        return await self._llm_request(session, url, resent, emit, handle), new_window

    async def _summarize_llm(self, session, base: str, model: str, previous: str, new_turns: str) -> str:
        """One model call: previous summary + newly pushed-out turns -> updated summary. No retries."""
        data = await self._request_json(
            session, "POST", f"{base}/chat/completions", headers=self._api_headers(),
            json_body={"model": model, "temperature": 0.1, "messages": [
                {"role": "system", "content": _rb.SUMMARY_PROMPT},
                {"role": "user", "content": f"Previous summary:\n{previous or '(none)'}\n\n"
                                            f"Turns that just left the context:\n{new_turns}"}]},
            timeout=_rb.DEFAULTS["summary_timeout_s"])
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        return _THINK_RE.sub("", self._extract_text(msg.get("content") or "")).strip()

    async def _history_with_model_summary(self, session, base: str, model: str, turn, window: int,
                                          *, reserved: int) -> list[dict]:
        """#390-1: the rule fit decides what stays verbatim (last 6 turns at most, 70% of the window);
        the turns it pushed out get a rolling model summary (<= summary_token_cap(window), cut to the room left)."""
        max_input = self._declared_max_input(model)
        msgs = self._history_messages(turn.history, context_window=window, reserved_tokens=reserved,
                                      max_input_tokens=max_input)
        if not msgs or msgs[0].get("role") != "system":
            return msgs  # fits verbatim (or nothing fits): no model call
        turns = _group_turns(turn.history)
        kept = sum(1 for m in msgs[1:] if m.get("role") == "user")
        head = turns[:max(0, len(turns) - kept)]
        if not head:
            return msgs
        head_texts = ["\n".join(f"{m['role']}: {m['content']}" for m in _render_turns([t])) for t in head]
        rule = str(msgs[0]["content"])

        async def llm(previous: str, new_turns: str) -> str:
            return await self._summarize_llm(session, base, model, previous, new_turns)
        text, source, _n = await _rb.model_summary(head_texts, rule, llm, model_id=model,
                                                     timeout_s=_rb.DEFAULTS["summary_timeout_s"],
                                                     **_owner_kw(turn))
        if source == "rule":
            return msgs
        budget = max(0, input_token_budget(window, max_input) - reserved - _message_tokens(msgs[1:]))
        text = truncate_to_tokens(f"{_SUMMARY_HEADER}\n{text}", min(summary_token_cap(window), budget))
        return [{"role": "system", "content": text}, *msgs[1:]] if text else msgs[1:]

    def _threshold(self) -> float:
        from ComfyArt.api.wavespeed import confirm_usd
        return float(confirm_usd())

    async def _price_one(self, model: str, inputs: dict):
        from ComfyArt.api.wavespeed import quote
        price, _source = await quote(model, inputs)
        return price

    async def _models_for(self, feature: str):
        from ComfyArt.api.wavespeed import grouped_models
        grouped = await grouped_models()
        feat = grouped.get(feature) or {}
        rows = []
        for m in feat.get("models") or []:
            price = m.get("price")
            rows.append((str(m.get("id") or ""),
                         float(price) if isinstance(price, (int, float)) and not isinstance(price, bool) else None))
        return rows

    async def _quote_steps(self, steps, lang: str):
        from .plan_quote import build_quote
        return await build_quote(steps, lang, threshold=self._threshold(),
                                 pricer=self._price_one, models_for=self._models_for)

    async def _confirm_plan(self, spec: dict, turn: TurnRequest, handle: TurnHandle, *,
                            run=None, messages: Optional[list] = None) -> str:
        """'start', 'cancel' (the user's Cancel / dismiss) or 'unattended' (no live turn to ask: nothing
        is charged and it is not a user stop). #418: an interactive card waits indefinitely, and the run
        is checkpointed as 'awaiting_confirm' while it does."""
        if handle.stop_requested:
            return "cancel"
        from ComfyArt.api.bot_turns import ACTIVE_TURNS
        from ComfyArt.api.mcp_tools.bot_tools import _await_ask
        state = ACTIVE_TURNS.get(turn.chat_id)
        if state is None:
            return "unattended"
        state.awaiting = "confirm"
        if run is not None:
            try:
                run.checkpoint(messages, status="awaiting_confirm", detail="plan_quote")
            except Exception:
                _log.warning("[ComfyArt/local-llm] awaiting_confirm checkpoint failed", exc_info=True)
        try:
            outcome = await _await_ask(turn.chat_id, state, spec, wait_forever=True)
        except Exception:
            _log.exception("[ComfyArt/local-llm] plan confirm failed")
            return "cancel"
        finally:
            state.awaiting = ""
        selected = outcome.get("selected") or []
        if outcome.get("status") == "answered" and "start" in selected:
            return "start"
        return "cancel"

    def _implicit_step(self, item: dict, lang: str) -> dict:
        args = item["args"]
        return {
            "text": _step_label(item["name"], args, lang),
            "tool": item["name"],
            "model": str(args.get("model") or ""),
            "arguments": args,
        }

    async def _confirm_over_quote(self, turn, handle, lang: str, name: str, price: float, left: float) -> bool:
        """#391: a paid call over the run's remaining quote needs an explicit yes; never auto-continue.
        #393: a dedicated card (not QuestionCard) built from the shared bot/over_quote.json schema; the
        answer is selected [confirm] | [decline]. Anything else (dismiss, timeout, no live turn) declines."""
        if handle is not None and handle.stop_requested:
            return False
        from ComfyArt.api.bot_turns import ACTIVE_TURNS
        from ComfyArt.api.mcp_tools.bot_tools import _await_ask
        state = ACTIVE_TURNS.get(turn.chat_id) if turn is not None else None
        if state is None:
            return False
        try:
            outcome = await _await_ask(turn.chat_id, state, over_quote_spec(lang, price))
        except Exception:
            _log.exception("[ComfyArt/local-llm] over-quote confirm failed")
            return False
        return outcome.get("status") == "answered" and OVER_QUOTE["confirm"] in (outcome.get("selected") or [])

    async def _emit_mcp(self, item: dict, *, session, turn, emit, handle,
                        done: list, lang: str, skill_cache: dict, llm_model: str,
                        run=None) -> list[dict]:
        """Run one real MCP tool and return the chat messages for it. Emits the tool row."""
        name, args, tc_id = item["name"], item["args"], item["id"]
        skill_key, cached = item["skill_key"], item["cached"]
        price = 0.0
        if run is not None and name in PAID_TOOLS:
            from . import agent_loop

            async def ask(n, a, p, left):
                return await self._confirm_over_quote(turn, handle, lang, n, p, left)
            action, text, price = await agent_loop.paid_gate(run, name, args, ask, call_id=tc_id or "")
            if action != "call":
                await emit(BotEvent(t="tool_use", name=name, input=args, id=tc_id))
                await emit(BotEvent(t="tool_result", name=name, text=text or "", id=tc_id,
                                    detail="cancelled" if action == "skip" else ""))
                return [{"role": "tool", "tool_call_id": tc_id or name, "content": text or ""}]
        await emit(BotEvent(t="tool_use", name=name, input=args, id=tc_id))
        tool_failed = False
        images: list[str] = []
        from .agent_loop import lease_heartbeat
        try:
            async with lease_heartbeat(run if (run is not None and not cached) else None):
                if cached:
                    result_text = skill_cache[skill_key]
                elif name == "wait_generation":
                    result_text = await self._wait_stage_done(
                        session, turn.mcp_endpoint, args, llm_model, handle)
                else:
                    result_text, images = await self._mcp_call_tool(
                        session, turn.mcp_endpoint, name, args)
        except _NET_ERRORS as e:
            result_text = f"[error] {type(e).__name__}: {e}"
            tool_failed = True
        if skill_key and not tool_failed:
            skill_cache.setdefault(skill_key, result_text)
        if not cached:
            done.append(_step_label(name, args, lang))
        if len(result_text) > TOOL_RESULT_CAP:
            result_text = (result_text[:TOOL_RESULT_CAP]
                           + f"\n…[truncated {len(result_text) - TOOL_RESULT_CAP} chars]")
        if run is not None and name in PAID_TOOLS:
            from . import agent_loop
            agent_loop.paid_done(run, name, args, result_text, price,
                                 tool_failed or bool(model_call_failed(name, args, result_text)), call_id=tc_id or "")
        # #421: model/payload failures (not only transport) must be is_error so the UI
        # shows a failed step instead of the success/done generation row.
        model_failed = bool(model_call_failed(name, args, result_text))
        await emit(BotEvent(
            t="tool_result", name=name, text=result_text, id=tc_id,
            is_error=tool_failed or model_failed,
            detail="cancelled" if _CANCEL_RE.search(result_text) else ""))
        out = [{"role": "tool", "tool_call_id": tc_id or name, "content": result_text}]
        if images:
            out.append({"role": "user", "content": [
                {"type": "text", "text": f"{_TOOL_IMAGES_PREFIX}{name}:"},
                *({"type": "image_url", "image_url": {"url": u}} for u in images),
            ]})
        return out

    async def _emit_result(self, item: dict, text: str, *, emit, done: list, lang: str,
                           is_error: bool = False, detail: str = "", count_done: bool = True) -> list[dict]:
        name, args, tc_id = item["name"], item["args"], item["id"]
        await emit(BotEvent(t="tool_use", name=name, input=args, id=tc_id))
        if count_done and not item["cached"]:
            done.append(_step_label(name, args, lang))
        await emit(BotEvent(
            t="tool_result", name=name, text=text, id=tc_id, is_error=is_error, detail=detail))
        return [{"role": "tool", "tool_call_id": tc_id or name, "content": text}]

    async def _dispatch_tools(self, tool_calls, *, session, turn, emit, handle,
                              messages, done, lang, skill_cache, loop, gate, usage,
                              llm_model: str) -> Optional[TurnResult]:
        """One assistant message. A multi-step paid batch is priced before any paid tool_use."""
        parsed = []
        tripped = False
        for tool_call in tool_calls:
            if handle.stop_requested:
                return TurnResult(aborted=True, usage=usage)
            fn = tool_call.get("function") or {}
            name = str(fn.get("name") or "")
            tc_id = str(tool_call.get("id") or "")
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except ValueError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            if loop.get("run") is not None:  # #705: empty skill read in a skill run -> the run's skill
                from .agent_loop import autofill_skill_read
                filled = autofill_skill_read(loop["run"], name, args)
                if filled is not args:
                    args = filled
                    fn["arguments"] = json.dumps(args, ensure_ascii=False)
            key = _call_key(name, args)
            loop["repeat"] = loop["repeat"] + 1 if key == loop["last_key"] else 1
            loop["last_key"] = key
            skill_key = _skill_read_key(name, args)
            cached = bool(skill_key) and skill_key in skill_cache
            if cached:
                loop["cache_hits"] += 1
            if loop.get("budget_loop"):
                pass  # #391: the ProgressTracker owns repeat / stall detection
            elif loop["repeat"] >= _REPEAT_STOP or loop["cache_hits"] >= _CACHED_SKILL_STOP:
                _log.warning("[ComfyArt/local-llm] loop guard: %s repeat=%d cached_skill_reads=%d, stopping",
                             name, loop["repeat"], loop["cache_hits"])
                tripped = True
                break
            parsed.append({"name": name, "args": args, "id": tc_id,
                           "skill_key": skill_key, "cached": cached})

        quote_item = next((it for it in parsed if it["name"] == QUOTE_TOOL), None)
        paid = [it for it in parsed if it["name"] in PAID_TOOLS]
        chunks: list[Optional[list]] = [None] * len(parsed)

        ran: list[int] = []

        async def run_mcp(i: int) -> None:
            ran.append(i)
            chunks[i] = await self._emit_mcp(
                parsed[i], session=session, turn=turn, emit=emit, handle=handle,
                done=done, lang=lang, skill_cache=skill_cache, llm_model=llm_model,
                run=loop.get("run"))

        # Checklist (and any other free tool) lands before the confirm card.
        for i, it in enumerate(parsed):
            if it["name"] not in PAID_TOOLS and it["name"] != QUOTE_TOOL:
                await run_mcp(i)

        decision = ""
        quote = None
        quote_error = ""
        # #418: a single paid call is quoted too (build_quote returns None under the confirm line,
        # so cheap calls run as before). Not after a strict 开始: there the gate refuses unquoted calls.
        single = quote_item is None and len(paid) == 1
        if quote_item is not None or len(paid) >= 2 or (single and not gate.strict):
            steps = (quote_item["args"].get("steps") if quote_item is not None
                     else [self._implicit_step(it, lang) for it in paid])
            try:
                quote = await self._quote_steps(steps if isinstance(steps, list) else [], lang)
            except Exception as e:
                _log.exception("[ComfyArt/local-llm] plan quote failed")
                quote_error = f"[error] {type(e).__name__}: {e}"
                decision = "error"
            else:
                if quote is None:
                    decision = "passthrough"
                elif not quote.ask:
                    gate.allow(quote, False)
                    decision = "start"
                else:
                    from .run_budget import Stop, StopReason
                    run = loop.get("run")
                    unattended = run is not None and run.mode == "unattended"
                    # #418 ruling: unattended (routine / headless / no live client) never waits: the
                    # card is not approved -> zero paid calls, turn ends normally as awaiting_confirm:not_approved.
                    choice = "unattended" if unattended else await self._confirm_plan(
                        quote.ask_spec(), turn, handle, run=run, messages=messages)
                    if handle.stop_requested:
                        return TurnResult(aborted=True, usage=usage)
                    if choice == "start":
                        if not single:  # #418: one OK covers this call only; don't arm the plan gate
                            gate.allow(quote, True)
                        decision = "start"
                    else:
                        decision = "cancel"
                        if run is not None:
                            step = run.budget.used.steps
                            # only the user's own Cancel is a user stop
                            run.pending_stop = (Stop(StopReason.USER_STOP, "quote_declined", step=step)
                                                if choice == "cancel" else
                                                Stop(StopReason.AWAITING_CONFIRM, "not_approved", step=step))

        lang_key = "zh" if lang == "zh" else "en"
        for i, it in enumerate(parsed):
            if chunks[i] is not None:
                continue
            name = it["name"]
            if name == QUOTE_TOOL:
                if decision == "error":
                    chunks[i] = await self._emit_result(
                        it, quote_error, emit=emit, done=done, lang=lang, is_error=True)
                elif decision == "cancel":
                    text = quote.cancel_text if quote else CANCEL_TEXT[lang_key]
                    chunks[i] = await self._emit_result(
                        it, text, emit=emit, done=done, lang=lang, detail="cancelled")
                else:
                    text = quote.started_result() if quote else json.dumps({"ok": True, "start": True})
                    chunks[i] = await self._emit_result(it, text, emit=emit, done=done, lang=lang)
                continue
            if name in PAID_TOOLS and decision == "cancel":
                continue  # do not emit a paid row: the user stopped before anything ran
            if name in PAID_TOOLS and handle.stop_requested:
                continue  # #419: stopped before this step was submitted: skip it, no row, no charge, no placeholder
            if name in PAID_TOOLS and gate.blocks(name, it["args"]):
                chunks[i] = await self._emit_result(
                    it, _PLAN_REFUSE[lang_key], emit=emit, done=done, lang=lang, is_error=True)
                continue
            await run_mcp(i)

        for ch in chunks:
            if ch:
                messages.extend(ch)
        for i in ran:  # #236: one fallback per failed model call, after its result is in the transcript
            it, ch = parsed[i], chunks[i]
            run = loop.get("run")
            if run is not None and run.pending_stop is not None:
                break  # #393: a declined quote (or any run stop) ends the run here: no fallback, no new quote
            if handle.stop_requested or not ch or it["cached"] or it["args"].get("fallback_for"):
                continue
            await self._maybe_model_fallback(
                session, turn.mcp_endpoint, handle, emit, lang, messages, done,
                turn.chat_id, it["name"], it["args"], str(ch[0].get("content") or ""),
                loop["gens"], run=run, turn=turn)
        if decision == "cancel":
            text = quote.cancel_text if quote else CANCEL_TEXT[lang_key]
            run = loop.get("run")
            if run is not None and run.pending_stop is not None and run.pending_stop.code == "awaiting_confirm:not_approved":
                from .agent_loop import stop_text
                text = stop_text(run.pending_stop, lang, done)  # not a cancel: nobody was there to confirm
            await emit(BotEvent(t="delta", text=text))
            return TurnResult(usage=usage)
        if tripped:
            return TurnResult(usage=usage, error=_stop_summary(done, lang))
        return None

    async def _speak(self, messages: list[dict], emit: EmitFn, text: str) -> None:
        """Put one line in the reply and in the transcript. It names the model and why nothing else ran."""
        messages.append({"role": "user", "content": text + " Do not submit the failed model again."})
        await emit(BotEvent(t="delta", text=text))

    async def _run_fallback_tool(self, session: aiohttp.ClientSession, endpoint: str,
                                 emit: EmitFn, lang: str, messages: list[dict], done: list[str],
                                 name: str, args: dict) -> str:
        base = _tool_base(name)
        tc_id = f"fb-{base}-{len(messages)}"
        messages.append({"role": "assistant", "content": None, "tool_calls": [{
            "id": tc_id, "type": "function",
            "function": {"name": base, "arguments": json.dumps(args, ensure_ascii=False)},
        }]})
        await emit(BotEvent(t="tool_use", name=base, input=args, id=tc_id))
        images: list[str] = []
        try:
            result_text, images = await self._mcp_call_tool(session, endpoint, base, args)
        except _NET_ERRORS as e:
            result_text = f"[error] {type(e).__name__}: {e}"
        if len(result_text) > TOOL_RESULT_CAP:
            result_text = (result_text[:TOOL_RESULT_CAP]
                           + f"\n…[truncated {len(result_text) - TOOL_RESULT_CAP} chars]")
        detail = "cancelled" if _CANCEL_RE.search(result_text) else ""
        messages.append({"role": "tool", "tool_call_id": tc_id, "content": result_text})
        await emit(BotEvent(t="tool_result", name=base, text=result_text, id=tc_id,
                            is_error=(result_text.startswith(("[tool error]", "[error]"))
                                      or bool(model_call_failed(base, args, result_text))),
                            detail=detail))
        done.append(_step_label(base, args, lang))
        if images:
            messages.append({"role": "user", "content": [
                {"type": "text", "text": f"Images returned by {base}:"},
                *({"type": "image_url", "image_url": {"url": u}} for u in images),
            ]})
        return result_text

    async def _confirm_fallback(self, session: aiohttp.ClientSession, endpoint: str,
                                emit: EmitFn, lang: str, messages: list[dict], done: list[str],
                                failed: str, target: str) -> bool:
        """#236: a paid fallback asks first. Anything other than an explicit yes does not submit."""
        zh = lang == "zh"
        prompt = (f"「{failed}」调用失败。要按对应表改用备用模型「{target}」再试一次吗？"
                  f"仍会走现有费用确认，不会用同一模型再提交。" if zh else
                  f"{failed} failed. Switch to the fallback model {target} from the table and try once? "
                  f"The usual cost check still applies, and the same model will not be submitted again.")
        args = {"prompt": prompt, "options": [
            {"id": "yes", "label": "换备用模型" if zh else "Use the fallback"},
            {"id": "no", "label": "不换" if zh else "Don't switch"},
        ], "min_selections": 1, "max_selections": 1, "allow_other": False}
        text = await self._run_fallback_tool(
            session, endpoint, emit, lang, messages, done, "ask_user", args)
        data = _json_obj(text) or {}
        return data.get("status") == "answered" and "yes" in (data.get("selected") or [])

    async def _maybe_model_fallback(self, session: aiohttp.ClientSession, endpoint: str,
                                    handle: TurnHandle, emit: EmitFn, lang: str,
                                    messages: list[dict], done: list[str], chat_id: str,
                                    name: str, args: dict, result_text: str,
                                    gens: dict, run=None, turn=None) -> None:
        """#236: on a model failure, switch once to the #133 backup. Never the same paid model.
        #393: a paid fallback goes through the same paid_gate as any paid call (never around it). The
        post-step `break` on pending_stop is what stops the fallback loop after 先到这里 / Esc."""
        if handle.stop_requested or not endpoint or (args or {}).get("fallback_for"):
            return
        _remember_generation(gens, name, args, result_text)
        signal = model_call_failed(name, args, result_text)
        if signal is None:
            return
        base = _tool_base(name)
        if base == "wait_generation":
            data = _json_obj(result_text) or {}
            bad = [r for r in data.get("results") or []
                   if isinstance(r, dict) and r.get("status") == "error" and not r.get("cancelled")]
            if not bad:
                return
            info = gens.get(str(bad[0].get("id") or ""))
            if not info or not info.get("name"):
                return
            tool, call_args = info["name"], dict(info["args"])
            failed = signal or str(info.get("model") or "")
        else:
            tool = base
            call_args = {k: v for k, v in args.items() if k != "fallback_for"}
            failed = signal or str(args.get("model") or args.get("edit_model") or "")
        if not failed:
            from ..api.mcp_tools.canvas import _auto_choice
            picked = _auto_choice(tool, call_args)
            failed = str(picked["model"]) if picked else ""
        if not failed or not tool:
            return
        from ..api.mcp_tools.canvas import _fallback_choice
        choice = _fallback_choice(tool, call_args, failed)
        if not choice or choice["model"] == failed:
            _log.warning("[ComfyArt/local-llm] no distinct #133 fallback for %s; not submitting it again", failed)
            return
        target = str(choice["model"])
        from ..api.paid_guard import fallback_allowed
        if not fallback_allowed(chat_id, tool, call_args):
            _log.warning("[ComfyArt/local-llm] fallback to %s blocked by the cost rules", target)
            await self._speak(messages, emit, _cost_block_note(failed, target, lang))
            return
        if tool in PAID_TOOLS:
            agreed = await self._confirm_fallback(
                session, endpoint, emit, lang, messages, done, failed, target)
            if handle.stop_requested or not agreed:
                if not handle.stop_requested:
                    await self._speak(messages, emit, _no_switch_note(failed, target, lang))
                return
        fb_args = {**call_args, "fallback_for": failed}
        price = 0.0
        gated = run is not None and tool in PAID_TOOLS
        cid = f"fb-{failed}-{len(messages)}"
        if gated:
            from . import agent_loop

            async def ask(n, a, p, left):
                return await self._confirm_over_quote(turn, handle, lang, n, p, left)
            action, _txt, price = await agent_loop.paid_gate(run, tool, fb_args, ask,
                                                             call_id=cid)
            if action != "call":
                return  # declined / stopping / pending: the fallback does not run and spends nothing
        text = await self._run_fallback_tool(
            session, endpoint, emit, lang, messages, done, tool, fb_args)
        if gated:
            agent_loop.paid_done(run, tool, fb_args, text, price, bool(model_call_failed(tool, fb_args, text)),
                                 call_id=cid)
        _remember_generation(gens, tool, fb_args, text)

    async def send(self, turn: TurnRequest, emit: EmitFn,
                   handle: TurnHandle) -> TurnResult:
        base = self._base_url()
        if not base:
            return TurnResult(
                error="no Local LLM endpoint configured — set the endpoint "
                      "URL under Agent Settings")
        try:
            async with aiohttp.ClientSession() as session:
                handle.process = session
                model = turn.model
                if not model:
                    models = await self.list_models()
                    model = models[0] if models else ""
                if not model:
                    return TurnResult(
                        error="no model available on the Local LLM endpoint")

                tools = self._build_tools(
                    await self._mcp_list_tools(session, turn.mcp_endpoint)) if turn.mcp_endpoint else []
                if tools:  # #235 synthetic tool: not an MCP tool, so external agents never see it
                    tools = [*tools, _QUOTE_PLAN_TOOL]
                system = _SYSTEM_PROMPT if tools else ""
                user_msg = _user_content(turn.user_text, turn.attachments)
                window = await self._context_window(session, model)
                history_msgs = await self._history_with_model_summary(
                    session, base, model, turn, window,
                    reserved=_content_tokens(system) + _content_tokens(user_msg))
                messages: list[dict] = [
                    *([{"role": "system", "content": system}] if system else []),
                    *history_msgs,
                    {"role": "user", "content": user_msg},
                ]

                usage: Optional[dict] = None
                done: list[str] = []
                lang = (turn.lang if turn.lang in ("zh", "en")
                        else _reply_lang(turn.user_text))
                policy = self._run_policy()
                if policy.enabled:  # #391 budget loop; flag agent.budget_loop off = legacy loop below
                    from . import agent_loop
                    return await agent_loop.run(
                        self, session=session, turn=turn, emit=emit, handle=handle, base=base,
                        model=model, tools=tools, messages=messages, window=window, lang=lang,
                        policy=policy, store=self._run_store(), clock=self._run_clock)
                # #400: legacy path is still reachable (settings agent-budget-loop / env
                # COMFYART_AGENT_BUDGET_LOOP=0). Attach a RunContext so paid tools and paid
                # fallbacks hit the same paid_gate as agent-loop (decline / unattended = 0 charge).
                skill_cache: dict[str, str] = {}
                gens: dict[str, dict] = {}
                run_ctx = self._paid_run_context(turn, window=window, lang=lang, policy=policy)
                loop = {"repeat": 0, "last_key": "", "cache_hits": 0, "gens": gens, "run": run_ctx}
                gate = _PlanGate()
                limit = self._max_steps()
                for _ in range(limit):
                    if handle.stop_requested:
                        return TurnResult(aborted=True, usage=usage)
                    try:
                        data, fitted = await self._llm_request_fit(
                            session, f"{base}/chat/completions", {
                                "model": model,
                                "messages": _prune_screenshots(messages),
                                **({"tools": tools, "tool_choice": "auto"} if tools else {}),
                                "temperature": 0.2,
                            }, emit, handle, model=model, window=window,
                            refit=lambda m, w: refit_messages(m, w, self._declared_max_input(model)))
                        if fitted != window:  # #493: later steps of this turn use the real window
                            window = fitted
                            messages[:] = refit_messages(messages, window, self._declared_max_input(model))
                    except (asyncio.TimeoutError, LlmHttpError) as e:
                        if handle.stop_requested:
                            return TurnResult(aborted=True, usage=usage)
                        kind = _retry_kind(e)
                        if not kind:
                            raise
                        return TurnResult(usage=usage,
                                          error=_llm_fail_summary(kind, e, done, lang))
                    usage = merge_usage(usage, data.get("usage"))
                    message = (data.get("choices") or [{}])[0].get("message") or {}
                    content = self._extract_text(message.get("content") or "")
                    thought = _THINK_RE.search(content)
                    reasoning = str(message.get("reasoning_content") or message.get("reasoning") or "") or (thought.group(1) or thought.group(2) or "" if thought else "")
                    content = _THINK_RE.sub("", content).strip()
                    tool_calls = message.get("tool_calls") or []

                    if reasoning.strip():
                        await emit(BotEvent(t="thinking", text=reasoning.strip()))
                    if content:
                        await emit(BotEvent(t="delta", text=content))
                    if not tool_calls:
                        return TurnResult(usage=usage)

                    messages.append({
                        "role": "assistant",
                        "content": content or None,
                        "tool_calls": tool_calls,
                    })
                    stopped = await self._dispatch_tools(
                        tool_calls, session=session, turn=turn, emit=emit, handle=handle,
                        messages=messages, done=done, lang=lang, skill_cache=skill_cache,
                        loop=loop, gate=gate, usage=usage, llm_model=model)
                    if stopped is not None:
                        return stopped
                    # #400: paid_gate decline / unattended skip sets pending_stop; do not keep looping
                    if run_ctx.pending_stop is not None:
                        from .run_budget import StopReason
                        stop = run_ctx.pending_stop
                        if stop.reason == StopReason.USER_STOP:
                            return TurnResult(aborted=True, usage=usage)
                        if stop.reason == StopReason.AWAITING_CONFIRM:
                            return TurnResult(usage=usage)  # #418: not approved ends normally
                        from .agent_loop import stop_text
                        return TurnResult(usage=usage, error=stop_text(stop, lang, done))
                return TurnResult(error=_step_limit_summary(done, limit, lang),
                                  usage=usage)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if handle.stop_requested:
                return TurnResult(aborted=True)
            _log.exception("[ComfyArt/local-llm] turn failed")
            return TurnResult(error=str(e) or type(e).__name__)
        finally:
            handle.process = None

    async def stop(self, handle: TurnHandle) -> None:
        handle.stop_requested = True
        session = handle.process
        if isinstance(session, aiohttp.ClientSession):
            await session.close()
