"""#391 + #383: the budget + progress driven agent loop (feature flag agent.budget_loop).

Replaces the fixed step count: a run stops on done (after the #383 goal self-check), budget
(tokens / credits / wall time), stuck (no progress), the hard cap (300 by default, always
announced), user stop or error. Every step is checkpointed server-side through RunStore under a
DB lease, so a restart or a "continue" resumes from the last step without repeating paid calls.
"""
from __future__ import annotations

import asyncio

import aiohttp
import json
import re
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from . import self_check as sc_mod
from .guide import PAID_TOOLS
from .plan_quote import canon_key
from . import reasoning_boost
from .run_budget import ui_credits
from .providers import BotEvent, TurnResult
from .run_budget import (
    BudgetLimits,
    ProgressTracker,
    RunBudget,
    RunPolicy,
    StepObservation,
    Stop,
    StopReason,
    TRY_ANOTHER_APPROACH,
    artifact_ids,
    confirm_policy,
    message_tokens,
    messages_tokens,
    text_tokens,
)
from .run_store import RunStore

_log = logging.getLogger("ComfyArt.agent_run")

_SUMMARY_HEAD = "Earlier steps of this run (compressed):"
_SUMMARY_CAP = 2_000
_BLOCK_TEXT_CAP = 4_000

_STOP_TEXT = {
    "budget:exhausted": {"zh": "{dim}预算已用完，已停止，未继续扣费。可以点「继续」追加预算后从断点接着跑。",
                         "en": "The {dim} budget is used up; stopped with no further charges. Press Continue to "
                               "add budget and resume from this step."},
    "budget:unattended_skipped": {"zh": "无人值守任务预计会超出{dim}预算，已保存断点并停止，未扣费。",
                                  "en": "Unattended run would exceed the {dim} budget; checkpoint saved, stopped, "
                                        "nothing charged."},
    "user_stop:quote_declined": {"zh": "已取消：超出报价的付费调用未确认，未扣费。",
                                 "en": "Cancelled: the paid call over the quote was not confirmed; nothing charged."},
    "awaiting_confirm:not_approved": {"zh": "这次生成需要确认，但没有人确认，未开始，未扣费。",
                                      "en": "This generation needs a confirmation and none came, so it did not start; nothing charged."},
    "stuck": {"zh": "任务卡住了（{sub}），停在第 {step} 步，换思路重试后仍无进展，已停止，未继续扣费。",
                "en": "The task is stuck ({sub}) at step {step}; still no progress after trying another "
                      "approach, so it stopped with no further charges."},
    "hard_cap": {"zh": "先停在这里了，进度已保存，点「继续」接着做。",
                 "en": "Paused here for now; progress is saved. Press Continue to keep going."},
    "error:llm_retry_exhausted": {"zh": "{detail}", "en": "{detail}"},
    "error:tool": {"zh": "工具出错：{detail}", "en": "Tool error: {detail}"},
}
_DIM = {"zh": {"tokens": "token ", "credits": "积分", "time": "时长"},
        "en": {"tokens": "token", "credits": "credit", "time": "time"}}
NON_RETRYABLE_MARK = "[non-retryable]"  # #705: keep in sync with SKILL_NON_RETRYABLE (src/skills.ts)
_STALL_LABEL = {
    "zh": {"no_progress": "连续多步没有新产出", "repeat": "同一调用反复出现", "tool_error": "工具连续失败",
           "readonly_limit": "连续只读步骤过多", "same_tool": "同一工具连续调用超过 3 次", "non_retryable": "工具返回不可重试的错误", "budget": "超过单次运行的付费/工具调用上限", "timeout": "等待生成结果超时（10 分钟或 120 次轮询）", "self_check_failed": "结果未通过自检"},
    "en": {"no_progress": "no new output for several steps", "repeat": "the same call repeated",
           "tool_error": "tool failed repeatedly", "readonly_limit": "too many read-only steps in a row", "same_tool": "the same tool was called more than 3 times in a row", "non_retryable": "a tool returned a non-retryable error", "budget": "the run hit its paid or total tool-call cap", "timeout": "waiting for a generation took over 10 minutes or 120 polls",
           "self_check_failed": "the result failed the self-check"},
}
_SELF_CHECK_NUDGE = {
    "zh": "系统核对：目标要求 {exp} 个{kind}，目前只有 {placed} 个落到画布。请继续把缺的 {miss} 个做完并放到画布上，不要只回复文字。",
    "en": "System check: the goal asks for {exp} {kind}; only {placed} are on the canvas. Generate the "
          "missing {miss} and place them on the canvas; do not reply with text only.",
}
_PAID_DEDUPE_NOTE = {
    "zh": "（断点续跑：该付费调用此前已执行，复用已有结果，未重复扣费）",
    "en": "(resumed run: this paid call already ran; reusing its result, not charged again)",
}
_PAID_PENDING_NOTE = {
    "zh": "该付费调用在中断前已提交，为避免重复扣费不再提交；请用 wait_generation / get_canvas 查看结果。",
    "en": "This paid call was submitted before the interruption; it is not resubmitted to avoid a duplicate "
          "charge. Use wait_generation / get_canvas to see its result.",
}



_SKILL_START_RE = re.compile(r"Use the ComfyArt skill (['\"])(.+?)\1 for this task")


def current_skill_from_messages(messages: list) -> str:
    """#705: the skill a run was started from (api/bot_send.compose_provider_text puts it in the first user turn)."""
    for m in messages or []:
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, list):
            c = " ".join(str(p.get("text") or "") for p in c if isinstance(p, dict))
        hit = _SKILL_START_RE.search(str(c or ""))
        if hit:
            return hit.group(2).strip()
    return ""


def autofill_skill_read(ctx: Optional["RunContext"], name: str, args: dict) -> dict:
    """#705: `skill {"action":"read"}` with no id/name inside a skill run reads the run's skill; logged in the run log."""
    if ctx is None or name != "skill" or str(args.get("action") or "").lower() != "read" or not ctx.current_skill:
        return args
    if str(args.get("id") or "").strip() or str(args.get("name") or "").strip():
        return args
    ctx.skill_autofills += 1
    record = {"event": "skill_autofill", "run_id": ctx.run_id, "filled": {"name": ctx.current_skill},
              "detail": f"skill read had no id/name; filled name={ctx.current_skill!r} from the run's skill"}
    _log.info("[ComfyArt/agent] %s", json.dumps(record, ensure_ascii=False))
    if ctx.store:
        try:
            ctx.store.add_run_log(run_id=ctx.run_id, record=record, owner_id=ctx.owner_id,
                                  workspace_id=ctx.workspace_id, project_id=ctx.project_id)
        except Exception:  # noqa: BLE001 — logging must never break the run
            _log.debug("skill_autofill run log failed", exc_info=True)
    return {**args, "name": ctx.current_skill}


def _result_failed(b: dict) -> bool:
    """#705: a tool result failed if status=error or its text starts with [error] / [tool error]
    (mirror bot/local_llm.py). Real tools return status=success + "[tool error] ValueError: ..."."""
    t = str(b.get("text") or "").lstrip()
    return b.get("status") == "error" or t.startswith("[error]") or t.startswith("[tool error]")

def _key_str(name: str, args: dict) -> str:
    return json.dumps(canon_key(name, args), ensure_ascii=False)


@dataclass
class RunContext:
    run_id: str
    store: Optional[RunStore]
    lease_owner: str
    policy: RunPolicy
    budget: RunBudget
    tracker: ProgressTracker
    mode: str
    goal: str
    lang: str
    owner_id: str
    workspace_id: str
    window: int
    project_id: str = "local"
    paid: dict = field(default_factory=dict)        # canon key -> {"status", "result", "artifacts"}
    artifacts: list = field(default_factory=list)
    blocks: list = field(default_factory=list)      # compact transcript for the self-check
    done: list = field(default_factory=list)
    pending_stop: Optional[Stop] = None
    compressions: int = 0
    paid_calls: int = 0
    paid_sent: set = field(default_factory=set)     # #419: keys whose paid request went out (kept even if it fails)
    selfcheck_nudged: bool = False
    messages: list = field(default_factory=list)  # live transcript (same list the loop appends to)
    pricer: Any = None
    confirmer: Any = None
    current_skill: str = ""                         # #705: skill the run was started from (auto-fills empty reads)
    skill_autofills: int = 0

    # -- persistence -------------------------------------------------------------
    def state(self, messages: Optional[list] = None) -> dict:
        return {"messages_compact": self.messages if messages is None else messages, "artifacts": self.artifacts, "paid": self.paid,
                "blocks": self.blocks[-400:], "done": self.done, "budget": self.budget.snapshot(),
                "tracker": self.tracker.snapshot(), "compressions": self.compressions,
                "selfcheck_nudged": self.selfcheck_nudged, "window": self.window, "lang": self.lang}

    def checkpoint(self, messages: Optional[list] = None, *, status: str = "running", detail: str = "",
                   stop: Optional[Stop] = None) -> None:
        if not self.store:
            return
        ok = self.store.save_checkpoint(self.run_id, self.lease_owner, status=status, status_detail=detail,
                                        step=self.budget.used.steps, state=self.state(messages),
                                        stop=stop.to_dict() if stop else None)
        if not ok:
            raise LeaseLost(self.run_id)
        self.store.renew_lease(self.run_id, self.lease_owner, self.policy["lease_s"])

    def pending_paid(self, key: str, usage: dict) -> Optional[int]:
        """Write the pending checkpoint AND the pending usage event in one transaction."""
        if not self.store:
            return None
        eid = self.store.save_checkpoint_with_usage(
            self.run_id, self.lease_owner, status="running", step=self.budget.used.steps, state=self.state(),
            usage={"owner_id": self.owner_id, "workspace_id": self.workspace_id, "status": "pending",
                   "call_id": key, **usage})
        if eid is None:
            raise LeaseLost(self.run_id)
        self.store.renew_lease(self.run_id, self.lease_owner, self.policy["lease_s"])
        return eid

    def heartbeat_s(self) -> float:
        hb = float(self.policy.get("lease_heartbeat_s") or 0)
        return hb if hb > 0 else max(1.0, float(self.policy["lease_s"]) / 3)

    def usage_event(self, **kw) -> None:
        if self.store:
            self.store.add_usage_event(run_id=self.run_id, owner_id=self.owner_id,
                                       workspace_id=self.workspace_id, **kw)


class LeaseLost(RuntimeError):
    pass


class lease_heartbeat:
    """#391: renew the run lease in the background while one (possibly long, e.g. video) tool call
    runs, so a call longer than lease_s never lets another instance take the run over."""

    def __init__(self, ctx: Optional["RunContext"]) -> None:
        self.ctx = ctx
        self.task: Optional[asyncio.Task] = None
        self.renewals = 0
        self.lost = False

    async def _beat(self) -> None:
        ctx = self.ctx
        while True:
            await asyncio.sleep(ctx.heartbeat_s())
            ok = ctx.store.renew_lease(ctx.run_id, ctx.lease_owner, ctx.policy["lease_s"])
            self.renewals += 1
            if not ok:
                self.lost = True
                _log.warning("[ComfyArt/agent] lease lost for %s during a tool call", ctx.run_id)
                return

    async def __aenter__(self):
        if self.ctx is not None and self.ctx.store is not None:
            self.task = asyncio.create_task(self._beat())
        return self

    async def __aexit__(self, *exc):
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        return False


# ---------------------------------------------------------------------------
# Rolling in-run compression against the real model window.
# ---------------------------------------------------------------------------


def _groups(messages: list[dict]) -> tuple[list[dict], list[list[dict]]]:
    """Head (system + first user goal) and step groups (assistant + its tool/user follow-ups)."""
    head: list[dict] = []
    i = 0
    while i < len(messages) and messages[i].get("role") == "system":
        head.append(messages[i])
        i += 1
    # History turns and the goal: everything up to the first assistant message with tool calls.
    while i < len(messages) and not (messages[i].get("role") == "assistant" and messages[i].get("tool_calls")):
        head.append(messages[i])
        i += 1
    groups: list[list[dict]] = []
    for m in messages[i:]:
        if m.get("role") == "assistant" or not groups:
            groups.append([m])
        else:
            groups[-1].append(m)
    return head, groups


def _summarize(groups: list[list[dict]]) -> str:
    lines = []
    for g in groups:
        for m in g:
            if m.get("role") == "assistant":
                for tc in m.get("tool_calls") or []:
                    fn = tc.get("function") or {}
                    lines.append(f"- {fn.get('name')}({str(fn.get('arguments') or '')[:120]})")
            elif m.get("role") == "tool":
                c = str(m.get("content") or "")
                lines.append("  → " + " ".join(c.split())[:160])
            elif m.get("role") == "user" and isinstance(m.get("content"), str) and m["content"].startswith(_SUMMARY_HEAD):
                lines.append(m["content"][len(_SUMMARY_HEAD):].strip())
    from .local_llm import truncate_to_tokens
    return truncate_to_tokens("\n".join(lines), _SUMMARY_CAP)


def prune_images(messages: list[dict], keep: int) -> list[dict]:
    from .local_llm import _prune_screenshots
    return _prune_screenshots(messages, keep)


def compress(messages: list[dict], *, window: int, policy: RunPolicy) -> tuple[list[dict], bool]:
    """Return (messages, compressed). Keeps system/goal/history head, the plan, and the last
    `verbatim_steps` steps verbatim; older steps fold into one summary. Images beyond the newest
    `keep_screenshots` become placeholders; image tokens are counted with `image_tokens`."""
    img = policy["image_tokens"]
    limit = window * policy["compress_percent"] // 100
    pruned = prune_images(messages, policy["keep_screenshots"])
    if messages_tokens(pruned, img) <= limit:
        return messages, False
    head, groups = _groups(pruned)
    keep = policy["verbatim_steps"]
    while True:
        old, recent = groups[:-keep] if keep else groups, groups[-keep:] if keep else []
        summary = [{"role": "user", "content": f"{_SUMMARY_HEAD}\n{_summarize(old)}"}] if old else []
        out = head + summary + [m for g in recent for m in g]
        if messages_tokens(out, img) <= limit or keep <= 1:
            break
        keep -= 1
    # Still over (huge recent tool results): truncate the largest tool contents.
    from .local_llm import truncate_to_tokens
    guard = 0
    while messages_tokens(out, img) > limit and guard < 50:
        guard += 1
        idx = max((i for i, m in enumerate(out) if m.get("role") in ("tool", "user") and isinstance(m.get("content"), str)
                   and i >= len(head)), key=lambda i: message_tokens(out[i], img), default=None)
        if idx is None:
            break
        c = out[idx]["content"]
        out[idx] = {**out[idx], "content": truncate_to_tokens(c, max(50, text_tokens(c) // 2)) + " …[compressed]"}
    return out, True


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------


def _remaining_steps(ctx: RunContext) -> int:
    """Projected steps left: missing deliverables x observed steps per deliverable (+1 to wrap up)."""
    goal = sc_mod.parse_goal(ctx.goal)
    if not goal:
        return 1
    check = sc_mod.check(ctx.goal, ctx.blocks)
    missing = max(0, goal.count - check.placed)
    if missing == 0:
        return 1
    steps = max(1, ctx.budget.used.steps)
    per = steps / check.placed if check.placed else 3.0
    return int(round(missing * per)) + 1


# #391/#383 stop card copy (locked in #391 comment 6440534008). {n} delivered, {m} expected,
# {x} credits to continue, {step} where it got stuck, {miss} what failed the self-check.
CARD_COPY = {
    "done": {"zh": ("已完成", "生成了 {n} 张，已放到画布上", None, None),
             "en": ("Done", "Made {n}, placed on the canvas", None, None)},
    "budget": {"zh": ("已自动暂停", "{reason}", "继续生成", "先到这里"),
               "en": ("Paused automatically", "{reason}", "Continue generating",
                      "Stop here")},
    "hard_cap": {"zh": ("先停在这里了", "已完成 {n}/{m}，继续大约需要 {x} 积分", "继续生成", "先到这里"),
                 "en": ("Paused here for now", "{n}/{m} done; continuing needs about {x} credits", "Continue generating",
                        "Stop here")},
    "stuck": {"zh": ("已暂停", "{reason}", "继续生成", "先到这里"),
              "en": ("Paused", "{reason}", "Continue generating", "Stop here")},
    "stuck:self_check_failed": {"zh": ("结果未通过自检", "已交付 {n} 张，还差：{miss}", "继续", None),
                                "en": ("Result failed the self-check", "Delivered {n}; still missing: {miss}",
                                       "Continue", None)},
    "user_stop": {"zh": ("已停止", "已保留生成的 {n} 张", "继续", None),
                  "en": ("Stopped", "Kept the {n} already generated", "Continue", None)},
    "user_stop:quote_declined": {"zh": ("已取消", "报价没有确认，不会扣费；已保留之前生成的 {n} 张", "继续", None),
                                 "en": ("Cancelled", "Quote not confirmed, so no charge; kept the {n} images generated earlier",
                                        "Continue", None)},
    "awaiting_confirm:not_approved": {"zh": ("等待确认未通过", "需要确认才能开始，未扣费", "继续", None),
                                      "en": ("Confirmation not approved", "Needs your OK to start; nothing charged", "Continue", None)},
    "error:network": {"zh": ("网络断开了", "已保留生成的 {n} 张", "重试", None),
                      "en": ("Network disconnected", "Kept the {n} already generated", "Retry", None)},
    "error": {"zh": ("出错了", "{reason}", "重试", None),
              "en": ("Something went wrong", "{reason}", "Retry", None)},
}
# #418: label for a card still WAITING on the user (pending, not a stop). Must differ from the
# awaiting_confirm:not_approved stop title so a pending card and an unapproved one never read the same.
PENDING_CONFIRM_LABEL = {"zh": "等待确认", "en": "Awaiting confirmation"}
# primary button action: continue the run from its checkpoint | rephrase (focus the composer) | retry
_PRIMARY_ACTION = {"error": "retry"}  # #709: stuck primary = 继续生成 (continue)
# #709: every paused card names WHY it paused (one plain line) and stuck cards also offer 继续, which resumes
# the same run from its checkpoint (agent_loop resume: fresh progress window for stuck, +1 budget for budget).
# #709 UIUX: the card's reason is a plain sentence (never stuck:* / budget:* codes).
_STUCK_REASON = {
    "zh": {"no_progress": "连续几步都没有新产出，自动暂停", "repeat": "同一个操作反复出现，自动暂停",
           "tool_error": "工具连续出错，自动暂停", "readonly_limit": "连续多步只在查看、没有生成，自动暂停",
           "same_tool": "连续重复同一步，已停下", "non_retryable": "工具返回了无法重试的错误，已暂停",
           "budget": "生成和工具调用次数到了本次上限，自动暂停",
           "timeout": "等待生成结果超过 {N} 分钟"},
    "en": {"no_progress": "No new output for several steps, paused automatically",
           "repeat": "The same action kept repeating, paused automatically",
           "tool_error": "A tool failed several times in a row, paused automatically",
           "readonly_limit": "Several steps only looked and made nothing, paused automatically",
           "same_tool": "Repeated the same step in a row, stopped",
           "non_retryable": "A tool returned an error that can't be retried, paused",
           "budget": "Generation and tool calls reached this run's limit, paused automatically",
           "timeout": "Waited over {N} min for the result"},
}
_CONTINUE_LABEL = {"zh": "继续生成", "en": "Continue generating"}


def _budget_reason(ctx: "RunContext", dim: str, lk: str) -> str:
    """#709 UIUX: one plain sentence with the run's real numbers; never an internal code."""
    u = ctx.budget.used
    if dim == "time":
        mins = max(1, int(round(u.wall_s / 60)))
        return (f"已运行 {mins} 分钟，达到单次时长上限。已生成的图保留在画布上。" if lk == "zh" else
                f"Ran for {mins} min, reaching the per-run time limit. Images already made stay on the canvas.")
    if dim == "credits":
        c = ui_credits(u.credits)
        return (f"已用 {c} 积分，达到单次积分上限。已生成的图保留在画布上。" if lk == "zh" else
                f"Used {c} credits, reaching the per-run credit limit. Images already made stay on the canvas.")
    if dim == "tokens":
        t = _fmt_tokens(u.tokens)
        return (f"模型用量已达 {t}，达到单次上限。已生成的图保留在画布上。" if lk == "zh" else
                f"Model usage reached {t}, the per-run limit. Images already made stay on the canvas.")
    return "已自动暂停" if lk == "zh" else "Paused automatically"


def _stuck_reason(ctx: "RunContext", sub: str, lk: str) -> str:
    t = _STUCK_REASON[lk].get(sub, "已自动暂停" if lk == "zh" else "Paused automatically")
    if "{N}" in t:
        tr = ctx.tracker
        t = t.replace("{N}", str(max(1, int((max(tr.wait_waited_s, 0) or tr.wait_max_s) // 60))))
    return t


# 「详情」 token line label: ONE copy key, design picks the final Chinese word (placeholder 用量).
DETAIL_TOKEN_LABEL = {"zh": "模型用量", "en": "model usage"}
_DETAIL_LABEL = {"zh": ("步数", DETAIL_TOKEN_LABEL["zh"], "积分", "用时"),
                 "en": ("steps", DETAIL_TOKEN_LABEL["en"], "credits", "time")}

# Body fragments used when the locked template would mislead (EL 6441143985): no estimate -> no
# credits clause; no parsable goal -> no "n/m"; non-image or no output -> no "张".
_UNIT = {"zh": {"image": "张", "video": "段视频", "text": "条文案", "": "个结果"},
         "en": {"image": "images", "video": "videos", "text": "texts", "": "results"}}
_FRAG = {
    "zh": {"progress": "已完成 {n}/{m}", "ask": "预算到了，要继续吗？", "est": "，继续大约需要 {x} 积分",
           "done": "已完成", "kept": "已保留生成的 {n} {u}", "kept_none": "进度已保存", "free": "未扣费", "declined": "报价没有确认，不会扣费",
           "self_check": "已交付 {n} {u}，还差：{miss}"},
    "en": {"progress": "{n}/{m} done", "ask": "Budget reached. Continue?", "est": "; continuing needs about {x} credits",
           "done": "Done", "kept": "Kept the {n} {u} already generated", "kept_none": "Progress saved",
           "free": "Nothing charged", "declined": "Quote not confirmed, so no charge", "self_check": "Delivered {n} {u}; still missing: {miss}"},
}


def _card_body(key: str, lk: str, *, n: int, m: Optional[int], x: Optional[int], kind: str, **kw) -> str:
    """Locked copy (#393 product+design): only an image target gets N/M and 「N 张」; the credits sentence
    only when there is a real estimate."""
    f = _FRAG[lk]
    image = kind == "image" and m is not None
    u = _UNIT[lk].get(kind, _UNIT[lk][""])
    sep = "，" if lk == "zh" else "; "
    if key == "budget" and x is not None:   # #709: plain sentence + the real cost to continue
        return kw["reason"] + (f"继续大约需要 {x} 积分。" if lk == "zh" else f" Continuing needs about {x} credits.")
    if key in ("budget", "stuck"):
        return kw["reason"]          # #709: one plain sentence, no separate duplicated reason line
    if key == "hard_cap":
        if not image:
            return f["ask"]
        return f["progress"].format(n=n, m=m) + (f["est"].format(x=x) if x is not None else "")
    if key == "done":
        return CARD_COPY[key][lk][1].format(n=n) if image and n > 0 else f["done"]
    if key == "stuck:self_check_failed":
        return CARD_COPY[key][lk][1].format(n=n, **kw) if kind == "image" else f["self_check"].format(n=n, u=u, **kw)
    if key in ("user_stop", "error:network"):
        if kind == "image" and n > 0:
            return CARD_COPY[key][lk][1].format(n=n)
        return f["kept"].format(n=n, u=u) if n > 0 else f["kept_none"]
    if key == "user_stop:quote_declined":
        if kind == "image":
            return CARD_COPY[key][lk][1].format(n=n) if n > 0 else f["declined"]
        return f["declined"] + (("；" if lk == "zh" else sep) + f["kept"].format(n=n, u=u) if n > 0 else "")
    return CARD_COPY[key][lk][1].format(n=n, m=m, x=x, **kw)


def _fmt_tokens(n: int) -> str:
    return f"{round(n / 1000, 1)}k" if n >= 1000 else str(n)


def _dangling_tool_calls(messages: list) -> Optional[dict]:
    """The assistant tool-call message of a step that crashed before its tool results were recorded."""
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if m.get("role") == "assistant" and m.get("tool_calls"):
            ids = {tc.get("id") for tc in m["tool_calls"]}
            answered = {x.get("tool_call_id") for x in messages[i + 1:] if x.get("role") == "tool"}
            if ids - answered:
                del messages[i:]
                return m
            return None
        if m.get("role") == "user":
            return None
    return None


def card_details(ctx: RunContext) -> dict:
    """「详情」: actual usage only, one plain line each. Never a limit / cap ("/300") and no bars."""
    ctx.budget.tick()
    u = ctx.budget.used
    secs = int(round(u.wall_s))
    vals = (str(u.steps), _fmt_tokens(u.tokens), str(ui_credits(u.credits)), f"{secs // 60}:{secs % 60:02d}")
    return {lk: [f"{lab} {v}" for lab, v in zip(_DETAIL_LABEL[lk], vals)] for lk in ("zh", "en")}


# Cards whose body says what this run kept: the count comes ONLY from the run's paid delivery records.
_KEPT_KEYS = frozenset({"user_stop", "user_stop:quote_declined", "error:network"})


def delivered(ctx: RunContext, kind: str = "") -> int:
    """#393: outputs delivered in THIS run, from its paid-call ledger (ctx.paid, checkpointed with the run):
    every done call counts its delivered ids (a job id or shape ids), at least 1. `kind` filters by output
    kind (image/video/...); empty counts every delivery."""
    from .local_llm import _SHAPE_TYPE, _tool_base
    n = 0
    for rec in (ctx.paid or {}).values():
        if not isinstance(rec, dict) or rec.get("status") != "done":
            continue
        tool = _tool_base(str(rec.get("tool") or ""))
        if kind and _SHAPE_TYPE.get(tool) != kind:
            continue
        n += max(1, len(rec.get("artifacts") or []))
    return n


def submitted_count(ctx: RunContext, before: set) -> int:
    """#419: paid calls this turn whose request was SENT (not only acknowledged): a stop that lands while the
    request is in flight may still be charged, so it counts and the charge note shows (over-warn, never under)."""
    return len({k for k in (ctx.paid_sent or set()) if k not in before})


def card_copy(ctx: RunContext, stop: Stop, check: sc_mod.SelfCheck, remaining: int = 0) -> dict:
    """Both languages, so the card follows a UI language switch. tone: neutral|warn|error|ok."""
    key = stop.code if stop.code in CARD_COPY else stop.reason.value
    goal = check.goal
    n = check.placed if goal else len(ctx.artifacts)
    if key in _KEPT_KEYS:
        n = delivered(ctx, goal.kind if goal else "")   # #393: single source = this run's delivery records
    m = goal.count if goal else None                       # no parsable goal: no "n/m"
    est = ctx.budget.projection(remaining) if remaining else {}
    cr = float(est.get("credits") or 0) if est else 0.0
    x = ui_credits(cr) if cr > 0 else None                 # no estimate: no credits clause
    kind = goal.kind if goal else ""
    out: dict = {"key": key, "action": _PRIMARY_ACTION.get(stop.reason.value, "continue"),
                 "tone": ("ok" if stop.reason == StopReason.DONE else "error" if stop.reason == StopReason.ERROR
                          else "neutral" if stop.reason == StopReason.USER_STOP else "warn")}
    for lk in ("zh", "en"):
        title, body, primary, secondary = CARD_COPY[key][lk]
        last = ctx.done[-1] if ctx.done else ""
        step = last or _STALL_LABEL[lk].get(stop.sub, stop.sub)
        miss = (f"{check.missing} {sc_mod._KIND_LABEL[lk][goal.kind]}" if lk == "en" else
                f"{check.missing} {dict(image='张', video='段', text='条')[goal.kind]}{sc_mod._KIND_LABEL[lk][goal.kind]}") if goal else ""
        reason = (stop.detail or _STALL_LABEL[lk].get(stop.sub, "") or stop.code).strip().splitlines()
        plain = (_budget_reason(ctx, stop.dimension, lk) if key == "budget" else
                 _stuck_reason(ctx, stop.sub, lk) if key == "stuck" else (reason[0] if reason else "")[:160])
        out[lk] = {"title": title,
                   "body": _card_body(key, lk, n=n, m=m, x=x, kind=kind, step=step, miss=miss, reason=plain),
                   "primary": primary, "secondary": secondary}
        if stop.reason in (StopReason.BUDGET, StopReason.STUCK) and key not in ("budget", "stuck"):
            r = (_budget_reason(ctx, stop.dimension, lk) if stop.reason == StopReason.BUDGET
                 else _stuck_reason(ctx, stop.sub, lk))
            if r != out[lk]["body"]:
                out[lk]["reason"] = r
    return out


def _summary_card(ctx: RunContext, stop: Stop, remaining: int = 0,
                  check: Optional[sc_mod.SelfCheck] = None) -> dict:
    goal = sc_mod.parse_goal(ctx.goal)
    check = check or sc_mod.check(ctx.goal, ctx.blocks)
    from .local_llm import _done_items
    zh = ctx.lang == "zh"
    return {
        "run_id": ctx.run_id, "stop": stop.to_dict(), "mode": ctx.mode,
        "done": _done_items(ctx.done, zh),
        "remaining": ({"deliverables": check.missing, "kind": goal.kind, "steps": remaining} if goal
                      else {"deliverables": 0, "kind": "", "steps": remaining}),
        "estimate": ctx.budget.projection(remaining) if remaining else {},
        "details": card_details(ctx),   # no limits / cap numbers on the card
        "self_check": check.to_dict(),
        "can_continue": stop.reason != StopReason.DONE,
        "copy": card_copy(ctx, stop, check, remaining),
    }


def stop_text(stop: Stop, lang: str, done: list[str], hard_cap: int = 0, check: Optional[sc_mod.SelfCheck] = None) -> str:
    from .local_llm import _with_done
    lk = "zh" if lang == "zh" else "en"
    if stop.reason == StopReason.HARD_CAP:
        # Same user copy as budget; the cap number is never shown to users.
        text = _with_done(_STOP_TEXT["hard_cap"][lk], done, lang)
    elif stop.reason == StopReason.STUCK:
        text = _with_done(_STOP_TEXT["stuck"][lk].format(sub=_STALL_LABEL[lk].get(stop.sub, stop.sub),
                                                           step=stop.step), done, lang)
    elif stop.code in _STOP_TEXT:
        tmpl = _STOP_TEXT[stop.code][lk]
        text = tmpl.format(dim=_DIM[lk].get(stop.dimension, ""), detail=stop.detail)
        if stop.reason == StopReason.BUDGET:
            text = _with_done(text, done, lang)
    else:
        text = stop.detail or stop.code
    if check is not None and check.applies and not check.passed:
        if stop.sub == "self_check_failed":
            text = ""
        text = sc_mod.scrub_done_claims((text + " " + sc_mod.missing_note(check, lang)).strip())
    return text


async def run(provider, *, session, turn, emit, handle, base: str, model: str, tools: list,
              messages: list[dict], window: int, lang: str, policy: RunPolicy,
              store: Optional[RunStore], clock=time.monotonic) -> TurnResult:
    from .local_llm import (
        LlmHttpError,
        is_context_overflow,
        _THINK_RE,
        _llm_fail_summary,
        _retry_kind,
        _skill_read_key,
        _step_label,
        _PlanGate,
        _call_key,
    )
    from ._cli_common import merge_usage

    usage: Optional[dict] = None
    lease_owner = turn.lease_owner or f"lease-{uuid.uuid4().hex}"
    resumed = None
    if turn.resume_run_id and store:
        resumed = store.get_run(turn.resume_run_id, owner_id=turn.owner_id)
        if resumed is None:
            return TurnResult(error="run not found")
        if not store.acquire_lease(resumed["id"], lease_owner, policy["lease_s"]):
            return TurnResult(error="this run is already being continued")
    k = policy["projection_window"]
    if resumed:
        st = resumed["state"]
        budget = RunBudget.restore(st["budget"], k=k, soft_fraction=policy["soft_fraction"], clock=clock)
        prev = (resumed.get("stop") or {}).get("reason")
        tracker = ProgressTracker.restore(st.get("tracker") or {})
        if prev == "budget":            # Continue = one more budget of the same size (soft pause stays used)
            budget.extend()
        elif prev == "hard_cap":
            budget.limits.hard_steps += policy["hard_cap_steps"]
        elif prev == "stuck":         # a fresh progress window (and one more nudge) for the user's retry
            tracker = ProgressTracker(policy["stall_steps"], policy["readonly_max"], policy["tool_fail_max"],
                                      policy["repeat_max"], seen_artifacts=tracker.seen_artifacts)
            tracker.tool_calls_max, tracker.all_calls_max = int(policy["max_tool_calls"]), int(policy["max_all_tool_calls"])  # #705
        ctx = RunContext(run_id=resumed["id"], store=store, lease_owner=lease_owner, policy=policy, budget=budget,
                         tracker=tracker, mode=turn.run_mode or resumed["mode"], goal=resumed["goal"], lang=st.get("lang") or lang,
                         owner_id=resumed["owner_id"], workspace_id=resumed["workspace_id"],
                         project_id=resumed.get("project_id") or "local",
                         window=window, paid=st.get("paid") or {}, artifacts=st.get("artifacts") or [],
                         blocks=st.get("blocks") or [], done=st.get("done") or [],
                         compressions=st.get("compressions") or 0, selfcheck_nudged=bool(st.get("selfcheck_nudged")))
        messages = list(st.get("messages_compact") or messages)
        replay = _dangling_tool_calls(messages)
        if turn.user_text.strip():
            messages.append({"role": "user", "content": turn.user_text})
    else:
        replay = None
        from .self_check import parse_goal
        goal = parse_goal(turn.goal_text or turn.user_text)
        tier = "chat" if goal is None else ("batch_or_long" if goal.count > 1 else "single_gen")
        limits = BudgetLimits.from_policy(policy, window=window, tier=tier)
        budget = RunBudget(limits, k=k, soft_fraction=policy["soft_fraction"], clock=clock)
        tracker = ProgressTracker(policy["stall_steps"], policy["readonly_max"], policy["tool_fail_max"],
                                  policy["repeat_max"])
        tracker.tool_calls_max, tracker.all_calls_max = int(policy["max_tool_calls"]), int(policy["max_all_tool_calls"])  # #705
        run_id = f"run-{uuid.uuid4().hex[:16]}"
        ctx = RunContext(run_id=run_id, store=store, lease_owner=lease_owner, policy=policy, budget=budget,
                         tracker=tracker, mode=turn.run_mode or "interactive", goal=turn.user_text, lang=lang,
                         owner_id=turn.owner_id, workspace_id=turn.workspace_id,
                         project_id=turn.project_id or "local", window=window)
        ctx.goal = turn.goal_text  # set by the chat turn (api/bot_turns); empty = no #383 check
        if store:
            store.create_run(run_id=run_id, chat_id=turn.chat_id, message_id="", mode=ctx.mode,
                             goal=ctx.goal, owner_id=turn.owner_id, workspace_id=turn.workspace_id,
                             project_id=ctx.project_id,
                             state=ctx.state(messages))
            store.acquire_lease(run_id, lease_owner, policy["lease_s"])
    ctx.messages = messages
    ctx.current_skill = ctx.current_skill or current_skill_from_messages(messages)
    ctx.pricer = getattr(provider, "_price_call", None)
    ctx.confirmer = getattr(provider, "_confirm_paid_over_quote", None)
    t_start = clock()
    first_step = ctx.budget.used.steps
    paid_before = set(ctx.paid or {})  # #419: paid calls submitted before this turn are not "submitted" by it
    first_tokens = ctx.budget.used.tokens

    async def rec_emit(ev: BotEvent) -> None:
        if ev.t == "tool_use":
            ctx.blocks.append({"type": "tool_use", "name": ev.name, "input": ev.input or {}, "id": ev.id})
        elif ev.t == "tool_result":
            status = "cancelled" if ev.detail == "cancelled" else ("error" if ev.is_error else "success")
            ctx.blocks.append({"type": "tool_result", "name": ev.name, "text": ev.text[:_BLOCK_TEXT_CAP],
                               "status": status, "id": ev.id})
        elif ev.t == "delta":
            ctx.blocks.append({"type": "text", "text": ev.text[:_BLOCK_TEXT_CAP]})
        await emit(ev)

    async def emit_budget() -> None:
        await emit(BotEvent(t="run_budget", input={"run_id": ctx.run_id, **ctx.budget.ui()}))

    async def canvas_ids() -> Optional[set]:
        """#383: read the live canvas (free, read-only, no block) so a shape that was reported
        but is no longer on the canvas does not count. None when the read is unavailable."""
        pre = sc_mod.check(ctx.goal, ctx.blocks)
        if not pre.applies or not pre.placed_ids:
            return None
        try:
            raw, _imgs = await provider._mcp_call_tool(session, turn.mcp_endpoint, "get_canvas", {})
            data = json.loads(raw)
        except Exception:  # noqa: BLE001 - fall back to the tool-reported shapes
            return None
        shapes = data.get("shapes") if isinstance(data, dict) else None
        if not isinstance(shapes, list):
            return None
        return {str(s.get("id")) for s in shapes if isinstance(s, dict) and s.get("id")}

    async def goal_check() -> sc_mod.SelfCheck:
        return sc_mod.check(ctx.goal, ctx.blocks, await canvas_ids())

    async def finish(stop: Stop, *, remaining: int = 0, extra_error: str = "") -> TurnResult:
        check = await goal_check()
        # Every stop except done can be continued / retried from its checkpoint.
        status = "done" if stop.reason == StopReason.DONE else "paused"
        detail = stop.sub or stop.reason.value
        card = _summary_card(ctx, stop, remaining, check)
        if stop.reason == StopReason.USER_STOP and not stop.sub:
            # #419: jobs already submitted to WaveSpeed cannot be cancelled: they finish, fill their
            # placeholders, are charged. The UI shows only the charge note, and only when n > 0 (no stop label).
            card["submitted"] = submitted_count(ctx, paid_before)
        try:
            ctx.checkpoint(messages, status=status, detail=detail, stop=stop)
        except LeaseLost:
            _log.warning("[ComfyArt/agent] lease lost for %s at stop", ctx.run_id)
        record = {
            "event": "agent_run", "run_id": ctx.run_id, "owner_id": ctx.owner_id, "workspace_id": ctx.workspace_id,
            "project_id": ctx.project_id, "mode": ctx.mode, "steps": ctx.budget.used.steps, "steps_this_turn": ctx.budget.used.steps - first_step,
            "tokens": ctx.budget.used.tokens, "credits_usd": round(ctx.budget.used.credits, 4),
            "wall_s": round(ctx.budget.used.wall_s, 2), "turn_s": round(clock() - t_start, 2),
            "stop_reason": stop.reason.value, "stop_sub": stop.sub, "stop_code": stop.code,
            "dimension": stop.dimension, "compressions": ctx.compressions, "paid_calls": ctx.paid_calls,
            "skill_autofills": ctx.skill_autofills, "self_check": check.to_dict(), "status": status,
        }
        _log.info("[ComfyArt/agent] %s", json.dumps(record, ensure_ascii=False))
        if ctx.store:
            ctx.store.add_run_log(run_id=ctx.run_id, record=record, owner_id=ctx.owner_id,
                                  workspace_id=ctx.workspace_id, project_id=ctx.project_id)
            ctx.usage_event(kind="llm_tokens", tokens=ctx.budget.used.tokens - first_tokens,
                            reason=f"turn {stop.code} (tokens of this turn)")
            ctx.store.release_lease(ctx.run_id, ctx.lease_owner)
        await emit(BotEvent(t="run_stop", input=card))
        if ctx.mode == "unattended":  # nobody is watching: every stop reason notifies
            await emit(BotEvent(t="notify", text=stop_text(stop, ctx.lang, ctx.done), input={"run_id": ctx.run_id}))
        run_info = {"run_id": ctx.run_id, "status": status, "stop": stop.to_dict(), "self_check": check.to_dict(),
                    "log": record}
        if stop.reason == StopReason.DONE:
            return TurnResult(usage=usage, run=run_info)
        if stop.reason == StopReason.USER_STOP:
            return TurnResult(usage=usage, aborted=True, run=run_info)
        if stop.reason == StopReason.AWAITING_CONFIRM:  # #418: not approved ends normally, never a user stop
            return TurnResult(usage=usage, run=run_info)
        if stop.code == "budget:paused":
            return TurnResult(usage=usage, run=run_info)
        text = extra_error or stop_text(stop, ctx.lang, ctx.done, ctx.budget.limits.hard_steps, check)
        return TurnResult(usage=usage, error=text, run=run_info)

    skill_cache: dict[str, str] = {}
    gens: dict[str, dict] = {}
    loop = {"repeat": 0, "last_key": "", "cache_hits": 0, "gens": gens, "budget_loop": True, "run": ctx}
    gate = _PlanGate()
    reason_next = False  # #413: set after a step that wrote memory; consumed by the next request
    try:
        while True:
            if handle.stop_requested:
                return await finish(Stop(StopReason.USER_STOP, step=ctx.budget.used.steps))
            if ctx.budget.used.steps >= ctx.budget.limits.hard_steps:
                return await finish(Stop(StopReason.HARD_CAP, step=ctx.budget.used.steps), remaining=_remaining_steps(ctx))
            dim = ctx.budget.exhausted()
            if dim:
                sub = "unattended_skipped" if confirm_policy(ctx.mode, "exhausted") == "skip" else "exhausted"
                return await finish(Stop(StopReason.BUDGET, sub, dimension=dim, step=ctx.budget.used.steps))
            if ctx.budget.used.steps > first_step:
                remaining = _remaining_steps(ctx)
                dim = ctx.budget.should_soft_pause(remaining)
                if dim:
                    ctx.budget.soft_used = True
                    if confirm_policy(ctx.mode, "soft_limit") == "skip":
                        return await finish(Stop(StopReason.BUDGET, "unattended_skipped", dimension=dim,
                                                 step=ctx.budget.used.steps), remaining=remaining)
                    return await finish(Stop(StopReason.BUDGET, "paused", dimension=dim,
                                             step=ctx.budget.used.steps), remaining=remaining)
            new_messages, did = compress(messages, window=window, policy=policy)
            if did:
                ctx.compressions += 1
                messages[:] = new_messages
                await emit(BotEvent(t="run_compress", input={"run_id": ctx.run_id, "count": ctx.compressions}))
            request_messages = prune_images(messages, policy["keep_screenshots"])
            try:
                if replay is not None:
                    # Crash mid-step: re-dispatch the exact same tool calls (same step + tool_call_id), so the
                    # paid gate reuses a done call or refuses a pending one instead of asking the model again.
                    data, replay, request_messages = {"choices": [{"message": replay}]}, None, []
                    fitted = window
                else:
                    body = {
                        "model": model, "messages": request_messages,
                        **({"tools": tools, "tool_choice": "auto"} if tools else {}), "temperature": 0.2,
                    }
                    # #413: only the call right after a successful memory add asks for low reasoning
                    boost = reasoning_boost.reasoning_params(base, model) if reason_next else {}
                    reason_next = False
                    try:
                        data, fitted = await provider._llm_request_fit(
                            session, f"{base}/chat/completions", {**body, **boost}, emit, handle, model=model, window=window,
                            refit=lambda m, w: prune_images(compress(m, window=w, policy=policy)[0],
                                                            policy["keep_screenshots"]))
                    except LlmHttpError as e:
                        if not boost or e.status != 400:
                            raise
                        if is_context_overflow(e):
                            # #493 B1: overflow again after the one resend; never a "no boost" retry.
                            raise
                        # Endpoint/model without that reasoning setting: same request, plain.
                        data, fitted = await provider._llm_request_fit(
                            session, f"{base}/chat/completions", body, emit, handle, model=model, window=window,
                            refit=lambda m, w: prune_images(compress(m, window=w, policy=policy)[0],
                                                            policy["keep_screenshots"]))
            except (asyncio.TimeoutError, LlmHttpError) as e:
                if handle.stop_requested:
                    return await finish(Stop(StopReason.USER_STOP, step=ctx.budget.used.steps))
                kind = _retry_kind(e)
                if not kind:
                    raise
                msg = _llm_fail_summary(kind, e, ctx.done, ctx.lang)
                return await finish(Stop(StopReason.ERROR, "llm_retry_exhausted", step=ctx.budget.used.steps,
                                         detail=msg), extra_error=msg)
            if replay is None and fitted != window:
                # #493: the model stated a smaller window; later steps compress against it. The failed
                # request is not charged and adds no step (only this one response is counted below).
                window = ctx.window = fitted
                messages[:] = compress(messages, window=window, policy=policy)[0]
            usage = merge_usage(usage, data.get("usage"))
            message = (data.get("choices") or [{}])[0].get("message") or {}
            content = provider._extract_text(message.get("content") or "")
            thought = _THINK_RE.search(content)
            reasoning = str(message.get("reasoning_content") or message.get("reasoning") or "") or (
                thought.group(1) or thought.group(2) or "" if thought else "")
            content = _THINK_RE.sub("", content).strip()
            tool_calls = message.get("tool_calls") or []
            # Tokens: output + reasoning (+ provider-reported reasoning tokens when larger).
            out_tokens = text_tokens(content) + text_tokens(reasoning) + sum(
                text_tokens(str((tc.get("function") or {}).get("arguments") or "")) for tc in tool_calls)
            rep = ((data.get("usage") or {}).get("completion_tokens_details") or {}).get("reasoning_tokens")
            if isinstance(rep, int) and rep > text_tokens(reasoning):
                out_tokens += rep - text_tokens(reasoning)
            ctx.budget.charge_request(usage=data.get("usage"), output_tokens=out_tokens,
                                      request_tokens=messages_tokens(request_messages, policy["image_tokens"])
                                      if request_messages else 0)
            if reasoning.strip():
                await emit(BotEvent(t="thinking", text=reasoning.strip()))
            if content:
                await rec_emit(BotEvent(t="delta", text=content))
            if not tool_calls:
                check = await goal_check()
                if check.applies and not check.passed:
                    if not ctx.selfcheck_nudged:
                        ctx.selfcheck_nudged = True
                        lk = "zh" if ctx.lang == "zh" else "en"
                        messages.append({"role": "assistant", "content": content or ""})
                        messages.append({"role": "user", "content": _SELF_CHECK_NUDGE[lk].format(
                            exp=check.goal.count, kind=sc_mod._KIND_LABEL[lk][check.goal.kind],
                            placed=check.placed, miss=check.missing)})
                        ctx.budget.end_step()
                        ctx.checkpoint(messages)
                        await emit_budget()
                        continue
                    return await finish(Stop(StopReason.STUCK, "self_check_failed", step=ctx.budget.used.steps))
                ctx.budget.end_step()
                return await finish(Stop(StopReason.DONE, step=ctx.budget.used.steps))

            messages.append({"role": "assistant", "content": content or None, "tool_calls": tool_calls})
            n_before = len(messages)
            b_before = len(ctx.blocks)
            stopped = await provider._dispatch_tools(
                tool_calls, session=session, turn=turn, emit=rec_emit, handle=handle,
                messages=messages, done=ctx.done, lang=ctx.lang, skill_cache=skill_cache,
                loop=loop, gate=gate, usage=usage, llm_model=model)
            reason_next = reasoning_boost.wrote_memory(ctx.blocks[b_before:])
            # Tool results are charged as input of the next request (they are re-sent with it).
            ctx.budget.end_step()
            if ctx.pending_stop is not None:
                return await finish(ctx.pending_stop)
            if stopped is not None:
                if stopped.aborted or handle.stop_requested:
                    return await finish(Stop(StopReason.USER_STOP, step=ctx.budget.used.steps))
                if stopped.error:
                    return await finish(Stop(StopReason.ERROR, "tool", step=ctx.budget.used.steps,
                                             detail=stopped.error), extra_error=stopped.error)
                return await finish(Stop(StopReason.USER_STOP, step=ctx.budget.used.steps))
            # Progress: one observation per tool result of this step.
            uses = {b.get("id"): b for b in ctx.blocks[b_before:] if b.get("type") == "tool_use"}
            obs = []
            for b in ctx.blocks[b_before:]:
                if b.get("type") != "tool_result":
                    continue
                u = uses.get(b.get("id")) or {}
                obs.append(StepObservation(tool=str(b.get("name") or ""),
                                           args_key=_call_key(str(b.get("name") or ""), u.get("input") or {}),
                                           result=str(b.get("text") or ""),
                                           failed=_result_failed(b)))
            for o in obs:
                if not o.failed:
                    for a in sorted(artifact_ids(o.result)):
                        if a not in ctx.artifacts:
                            ctx.artifacts.append(a)
            fatal = next((o for o in obs if o.failed and NON_RETRYABLE_MARK in o.result), None)
            if fatal is not None:  # #705: never let the model retry a call the tool says cannot succeed
                _log.warning("[ComfyArt/agent] run %s non-retryable %s error, stopping", ctx.run_id, fatal.tool)
                return await finish(Stop(StopReason.STUCK, "non_retryable", step=ctx.budget.used.steps))
            if ctx.tracker.over_budget(obs):  # #705: hard cap, no nudge (e.g. every step a new image, never done)
                _log.warning("[ComfyArt/agent] run %s over budget: %d calls, %d generate_image (cap %d/%d)", ctx.run_id,
                             ctx.tracker.total_calls, ctx.tracker.gen_calls, ctx.tracker.tool_calls_max, ctx.tracker.gen_cap())
                return await finish(Stop(StopReason.STUCK, "budget", step=ctx.budget.used.steps))
            if ctx.tracker.wait_timeout(obs, now=clock()):  # #705: one generation task waited > 10 min or > 120 polls
                _log.warning("[ComfyArt/agent] run %s wait_generation timeout: %s", ctx.run_id, ctx.tracker.wait_polls)
                return await finish(Stop(StopReason.STUCK, "timeout", step=ctx.budget.used.steps))
            stall = ctx.tracker.observe(ctx.budget.used.steps, obs, canvas_fp="|".join(ctx.artifacts[-200:]))
            if stall:
                if not ctx.tracker.nudged and stall != "same_tool":
                    ctx.tracker.reset_after_nudge()
                    lk = "zh" if ctx.lang == "zh" else "en"
                    messages.append({"role": "user", "content": TRY_ANOTHER_APPROACH[lk].format(
                        why=_STALL_LABEL[lk][stall])})
                    _log.info("[ComfyArt/agent] run %s stuck:%s at step %d -> try another approach (once)",
                              ctx.run_id, stall, ctx.budget.used.steps)
                else:
                    return await finish(Stop(StopReason.STUCK, stall, step=ctx.budget.used.steps))
            ctx.checkpoint(messages)
            await emit_budget()
    except LeaseLost:
        return TurnResult(usage=usage, error="this run was taken over by another continue request",
                          run={"run_id": ctx.run_id, "status": "lease_lost"})
    except (aiohttp.ClientError, ConnectionError, OSError) as e:
        if handle.stop_requested:
            # #419: stop() closes the session, so the in-flight call dies with ServerDisconnectedError;
            # that is the user's stop (#391 card + charge note), not a network drop
            return await finish(Stop(StopReason.USER_STOP, step=ctx.budget.used.steps))
        # network drop: keep the run resumable (paused at its last checkpoint) instead of leaving it "running"
        _log.warning("[ComfyArt/agent] network error in %s: %s", ctx.run_id, e)
        msg = ("网络中断，进度已保存，可以重试。" if ctx.lang == "zh" else "Network dropped; progress saved, you can retry.")
        return await finish(Stop(StopReason.ERROR, "network", step=ctx.budget.used.steps, detail=msg), extra_error=msg)


# ---------------------------------------------------------------------------
# Paid call gate (called from LocalLlmProvider._emit_mcp when a run context is present)
# ---------------------------------------------------------------------------


def paid_key(ctx: RunContext, name: str, args: dict, call_id: str = "") -> str:
    """Per-call idempotency id: the step plus the model's tool_call id. Two calls with identical
    params are two calls (4 images = 4 calls); only the SAME call replayed after a checkpoint is
    deduped. Without a call id the params are the fallback."""
    return f"s{ctx.budget.used.steps}:{call_id or _key_str(name, args)}"


async def paid_gate(ctx: RunContext, name: str, args: dict, emit_confirm,
                    call_id: str = "") -> tuple[str, Optional[str], float]:
    """Decide one paid call. Returns (action, text, price): action 'call' (run it, charge `price`),
    'reuse' (idempotent resume: `text` is the stored result), 'skip' (nothing called, `text` explains)."""
    key = paid_key(ctx, name, args, call_id)
    lk = "zh" if ctx.lang == "zh" else "en"
    prev = ctx.paid.get(key)
    if prev and prev.get("status") == "done":
        return "reuse", f"{prev.get('result') or ''}\n{_PAID_DEDUPE_NOTE[lk]}", 0.0
    if prev and prev.get("status") == "pending":
        return "skip", _PAID_PENDING_NOTE[lk], 0.0
    if ctx.pending_stop is not None:
        # #393: the run is already stopping (e.g. a declined quote): later paid calls of the same step are
        # neither asked about nor called. Exactly one quote per decline.
        why = f"{ctx.pending_stop.reason.value}:{ctx.pending_stop.sub}"
        return "skip", (_STOP_TEXT.get(why) or {}).get(lk, ""), 0.0
    price = 0.0
    if ctx.pricer is not None:
        try:
            p = await ctx.pricer(name, args)
            price = float(p) if p is not None else 0.0
        except Exception:
            _log.exception("[ComfyArt/agent] pricing %s failed", name)
    if not ctx.budget.can_afford(price):
        if confirm_policy(ctx.mode, "paid_confirm") == "skip":
            ctx.pending_stop = Stop(StopReason.BUDGET, "unattended_skipped", dimension="credits",
                                    step=ctx.budget.used.steps)
            return "skip", _STOP_TEXT["budget:unattended_skipped"][lk].format(dim=_DIM[lk]["credits"]), 0.0
        agreed = await emit_confirm(name, args, price, ctx.budget.credits_left()) if emit_confirm else False
        if not agreed:
            ctx.pending_stop = Stop(StopReason.USER_STOP, "quote_declined", step=ctx.budget.used.steps)
            return "skip", _STOP_TEXT["user_stop:quote_declined"][lk], 0.0
        # Confirmed: raise the ceiling by exactly this quote, never more (no auto-continue).
        ctx.budget.limits.credits = round(ctx.budget.used.credits + price, 6)
    ctx.paid[key] = {"status": "pending", "price": price}
    ctx.paid_sent.add(key)
    # The pending marker AND its pending usage event are durable (one transaction) before the paid
    # call goes out: a crash never re-calls, and money never moves without a metering row.
    eid = ctx.pending_paid(key, {"kind": "paid_call", "tool": name, "amount_usd": price,
                                 "reason": f"{name} at step {ctx.budget.used.steps + 1} (pending)"})
    if eid is not None:
        ctx.paid[key]["event_id"] = eid
        ctx.checkpoint()
    return "call", None, price


def paid_done(ctx: RunContext, name: str, args: dict, text: str, price: float, failed: bool,
              messages_ref: Optional[list] = None, call_id: str = "") -> None:
    from .run_budget import artifact_ids
    key = paid_key(ctx, name, args, call_id)
    ids = sorted(artifact_ids(text))
    eid = (ctx.paid.get(key) or {}).get("event_id")
    if failed:
        ctx.paid.pop(key, None)
    else:
        ctx.paid[key] = {"status": "done", "price": price, "result": text[:_BLOCK_TEXT_CAP], "artifacts": ids,
                         "tool": name}
        ctx.budget.charge_credits(price)
    ctx.paid_calls += 1
    reason = f"{name} at step {ctx.budget.used.steps + 1}" + (" (failed, not charged)" if failed else "")
    if eid is not None and ctx.store:
        ctx.store.finish_usage_event(eid, status="failed" if failed else "done",
                                     amount_usd=0.0 if failed else price, artifact_ids=ids, reason=reason)
    else:
        ctx.usage_event(kind="paid_call", tool=name, amount_usd=0.0 if failed else price, reason=reason,
                        artifact_ids=ids, status="failed" if failed else "done", call_id=key)
