"""#391: budget + progress driven agent loop primitives.

Everything here is pure (no I/O) so the loop, the API, the UI payloads and the tests share one
definition: the StopReason enum, the layered RunPolicy, RunBudget (tokens incl. reasoning and
image tokens, paid credits, wall time, hard step cap), the shared ConfirmPolicy (#388) and the
ProgressTracker.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Optional

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stop reasons: one fixed enum for UI, logs and tests.
# ---------------------------------------------------------------------------


def ui_credits(usd: float) -> int:
    """#393 product rule: the UI only ever shows credits. 1 credit = $0.01, integer, rounded UP; any
    nonzero spend under 1 credit shows 1, zero shows 0. Dollars stay in backend usage logs only."""
    # #393 product ruling: round USD to the nearest micro-dollar (integer), then ceil to credits with
    # integer math only (1 credit = 10_000 micro-dollars). $0.30000001 -> 30, $0.300001 -> 31.
    micro = int(round(max(0.0, float(usd or 0)) * 1_000_000))
    return -(-micro // 10_000)


class StopReason(str, Enum):
    DONE = "done"
    BUDGET = "budget"
    STUCK = "stuck"
    HARD_CAP = "hard_cap"
    USER_STOP = "user_stop"
    AWAITING_CONFIRM = "awaiting_confirm"  # #418: a confirm card nobody approved (unattended)
    ERROR = "error"


SUB_REASONS: dict[StopReason, frozenset[str]] = {
    StopReason.DONE: frozenset({""}),
    StopReason.BUDGET: frozenset({"paused", "exhausted", "unattended_skipped"}),
    StopReason.STUCK: frozenset({"no_progress", "repeat", "tool_error", "readonly_limit", "self_check_failed", "same_tool", "non_retryable", "budget", "timeout"}),
    StopReason.HARD_CAP: frozenset({""}),
    StopReason.USER_STOP: frozenset({"", "quote_declined"}),
    StopReason.AWAITING_CONFIRM: frozenset({"not_approved"}),
    StopReason.ERROR: frozenset({"llm_retry_exhausted", "tool", "network"}),
}
BUDGET_DIMENSIONS = ("tokens", "credits", "time")


@dataclass(frozen=True)
class Stop:
    reason: StopReason
    sub: str = ""
    dimension: str = ""   # tokens | credits | time, only for budget
    step: int = 0
    detail: str = ""

    def __post_init__(self) -> None:
        if self.sub not in SUB_REASONS[self.reason]:
            raise ValueError(f"invalid sub-reason {self.reason.value}:{self.sub}")
        if self.dimension and self.dimension not in BUDGET_DIMENSIONS:
            raise ValueError(f"invalid budget dimension {self.dimension}")

    @property
    def code(self) -> str:
        return f"{self.reason.value}:{self.sub}" if self.sub else self.reason.value

    def to_dict(self) -> dict:
        return {"reason": self.reason.value, "sub": self.sub, "code": self.code,
                "dimension": self.dimension, "step": self.step, "detail": self.detail}


# ---------------------------------------------------------------------------
# Policy: single entry, layered system -> workspace -> user -> plan (reserved, empty today).
# ---------------------------------------------------------------------------

LOCAL_OWNER_ID = "local"
LOCAL_WORKSPACE_ID = "local"
LOCAL_PROJECT_ID = "local"
FEATURE_FLAG = "agent.budget_loop"
LEGACY_MAX_STEPS_ENV = "COMFYART_AGENT_MAX_STEPS"

SYSTEM_DEFAULTS: dict[str, Any] = {
    FEATURE_FLAG: True,
    "hard_cap_steps": 300,
    "max_tool_calls": 30,           # #705: paid/external tool calls per run (generate_image: planned images + 2)
    "max_all_tool_calls": 300,      # #705: backstop, tool calls of any kind per run
    "token_window_multiple": 40,    # per-run token cap = 40 x model window; every request's re-sent input counts
    "wall_time_s": 15 * 60,
    "credits_usd": 5.0,             # paid ceiling per run; every paid call is also capped by its quote
    "soft_fraction": 0.8,           # UI hint level; pausing is projection driven
    "projection_window": 5,         # k: sliding mean over the last k steps
    "stall_steps": 4,               # N consecutive unchanged fingerprints
    "readonly_max": 8,              # M consecutive read-only steps
    "tool_fail_max": 3,
    "repeat_max": 3,
    "compress_percent": 70,
    "verbatim_steps": 6,
    "keep_screenshots": 2,
    "image_tokens": 1_500,          # conservative per image when the provider rule is unknown
    "lease_s": 60,
    "lease_heartbeat_s": 0,         # 0 = lease_s / 3; renews the lease while a long tool call runs
}
# Valid ranges for user/workspace overrides; out of range values are clamped.
POLICY_RANGES: dict[str, tuple[float, float]] = {
    "hard_cap_steps": (1, 1000),
    "token_window_multiple": (1, 200),
    "wall_time_s": (30, 6 * 3600),
    "credits_usd": (0, 1000),
    "soft_fraction": (0.1, 1.0),
    "projection_window": (1, 50),
    "stall_steps": (2, 50),
    "readonly_max": (2, 100),
    "tool_fail_max": (1, 20),
    "repeat_max": (2, 20),
    "compress_percent": (30, 95),
    "verbatim_steps": (1, 50),
    "keep_screenshots": (0, 10),
    "image_tokens": (85, 20_000),
    "lease_s": (5, 3600),
    "lease_heartbeat_s": (0, 3600),
}
# Task tiers (from the first plan): the multiplier scales tokens / time for longer work.
TIER_MULTIPLIER = {"chat": 1.0, "single_gen": 1.0, "batch_or_long": 2.0}


@dataclass(frozen=True)
class RunPolicy:
    values: dict

    def __getitem__(self, key: str) -> Any:
        return self.values[key]

    @property
    def enabled(self) -> bool:
        return bool(self.values.get(FEATURE_FLAG, True))


def _clamp(key: str, value: Any, default: Any) -> Any:
    if key == FEATURE_FLAG:
        if isinstance(value, str):
            return value.strip().lower() not in ("0", "false", "off", "no")
        return bool(value)
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    lo, hi = POLICY_RANGES.get(key, (float("-inf"), float("inf")))
    n = min(hi, max(lo, n))
    return int(n) if isinstance(default, int) and not isinstance(default, bool) else n


def resolve_policy(*, workspace: Optional[dict] = None, user: Optional[dict] = None,
                   plan: Optional[dict] = None, env: Optional[dict] = None) -> RunPolicy:
    """The single entry for budgets/config. Layers: system defaults -> workspace -> user -> plan
    (reserved for a tier override, empty locally). Legacy COMFYART_AGENT_MAX_STEPS maps to
    hard_cap_steps with a deprecation log."""
    out = dict(SYSTEM_DEFAULTS)
    for layer in (workspace, user, plan):
        for k, v in (layer or {}).items():
            if k in out and v is not None and v != "":
                out[k] = _clamp(k, v, SYSTEM_DEFAULTS[k])
    env = os.environ if env is None else env
    legacy = env.get(LEGACY_MAX_STEPS_ENV)
    if legacy:
        _log.warning("[ComfyArt/agent] %s is deprecated; mapped to hard_cap_steps=%s "
                     "(set the agent hard cap in settings instead)", LEGACY_MAX_STEPS_ENV, legacy)
        out["hard_cap_steps"] = _clamp("hard_cap_steps", legacy, SYSTEM_DEFAULTS["hard_cap_steps"])
    flag = env.get("COMFYART_AGENT_BUDGET_LOOP")
    if flag is not None and flag != "":
        out[FEATURE_FLAG] = _clamp(FEATURE_FLAG, flag, True)
    return RunPolicy(out)


# ---------------------------------------------------------------------------
# Shared confirm policy (#388 uses the same function for schedules / patrols).
# ---------------------------------------------------------------------------


class RunMode(str, Enum):
    INTERACTIVE = "interactive"
    UNATTENDED = "unattended"


def confirm_policy(mode: str, kind: str) -> str:
    """What to do when a run needs a human: 'ask' (interactive) or 'skip' (unattended: save the
    checkpoint, notify, stop, charge nothing; never wait). kind: soft_limit | paid_confirm."""
    if kind not in ("soft_limit", "paid_confirm", "exhausted"):
        raise ValueError(kind)
    return "skip" if mode == RunMode.UNATTENDED.value else "ask"


# ---------------------------------------------------------------------------
# Token estimation: text + reasoning + images (provider rule or a conservative constant).
# ---------------------------------------------------------------------------

_DATA_URL_RE = re.compile(r"data:[^;\s]+;base64,[A-Za-z0-9+/=]+")


def text_tokens(text: str) -> int:
    from .local_llm import count_tokens
    return count_tokens(_DATA_URL_RE.sub("[img]", text or ""))


def content_tokens(content: Any, image_tokens: int = SYSTEM_DEFAULTS["image_tokens"]) -> int:
    if content is None:
        return 0
    if isinstance(content, str):
        return text_tokens(content) + image_tokens * len(_DATA_URL_RE.findall(content))
    if isinstance(content, list):
        total = 0
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "image_url":
                total += image_tokens
            else:  # a text part can embed data-URL images too (#393 tester): same rule as a plain string
                total += content_tokens(str(part.get("text") or ""), image_tokens)
        return total
    return text_tokens(str(content))


def message_tokens(m: dict, image_tokens: int = SYSTEM_DEFAULTS["image_tokens"]) -> int:
    n = 4 + content_tokens(m.get("content"), image_tokens)
    for tc in m.get("tool_calls") or []:
        fn = (tc or {}).get("function") or {}
        n += text_tokens(str(fn.get("name") or "")) + text_tokens(str(fn.get("arguments") or ""))
    return n


def messages_tokens(messages: Iterable[dict], image_tokens: int = SYSTEM_DEFAULTS["image_tokens"]) -> int:
    return sum(message_tokens(m, image_tokens) for m in messages)


# ---------------------------------------------------------------------------
# RunBudget
# ---------------------------------------------------------------------------


@dataclass
class BudgetLimits:
    tokens: int
    credits: float
    wall_s: float
    hard_steps: int

    @classmethod
    def from_policy(cls, policy: RunPolicy, *, window: int, tier: str = "single_gen") -> "BudgetLimits":
        mult = TIER_MULTIPLIER.get(tier, 1.0)
        return cls(tokens=int(window * policy["token_window_multiple"] * mult),
                   credits=float(policy["credits_usd"]),
                   wall_s=float(policy["wall_time_s"]) * mult,
                   hard_steps=int(policy["hard_cap_steps"]))


@dataclass
class BudgetUsed:
    tokens: int = 0
    credits: float = 0.0
    wall_s: float = 0.0
    steps: int = 0


class RunBudget:
    """Three lines (tokens, credits, wall time) plus the hard step cap.

    Tokens count what each step adds to the run: model output + reasoning + new tool results,
    with images at `image_tokens` each. The re-sent prefix is bounded separately by rolling
    compression against the real window, so the cap measures work, not context size.
    Soft pause: only when spent + projected remaining > limit on some line, at most once per run.
    """

    def __init__(self, limits: BudgetLimits, *, k: int = 5, soft_fraction: float = 0.8,
                 used: Optional[BudgetUsed] = None, history: Optional[list] = None,
                 soft_used: bool = False, clock: Callable[[], float] = time.monotonic) -> None:
        self.limits = limits
        self.used = used or BudgetUsed()
        self.k = k
        self.soft_fraction = soft_fraction
        self.history: list[list[float]] = list(history or [])  # per step [tokens, credits, wall]
        self.soft_used = soft_used
        self._clock = clock
        self._t0 = clock()
        self._wall0 = self.used.wall_s
        self._step_start = (self.used.tokens, self.used.credits, self.used.wall_s)

    # -- charging ------------------------------------------------------------------
    def tick(self) -> None:
        self.used.wall_s = self._wall0 + (self._clock() - self._t0)

    def charge_request(self, *, usage: Optional[dict], request_tokens: int, output_tokens: int) -> int:
        """#391: one model request costs its INPUT (the whole re-sent context) + output + reasoning
        (+ images, already inside request_tokens). Prefer the provider's usage.prompt_tokens."""
        pt = (usage or {}).get("prompt_tokens") if isinstance(usage, dict) else None
        inp = pt if isinstance(pt, int) and pt > 0 else int(request_tokens)
        n = max(0, inp) + max(0, int(output_tokens))
        self.charge_tokens(n)
        return n

    def charge_tokens(self, n: int) -> None:
        self.used.tokens += max(0, int(n))

    def charge_credits(self, usd: float) -> None:
        self.used.credits = round(self.used.credits + max(0.0, float(usd)), 6)

    def credits_left(self) -> float:
        return max(0.0, self.limits.credits - self.used.credits)

    def can_afford(self, quote_usd: float) -> bool:
        return self.used.credits + max(0.0, quote_usd) <= self.limits.credits + 1e-9

    def end_step(self) -> None:
        self.tick()
        self.used.steps += 1
        t0, c0, w0 = self._step_start
        self.history.append([self.used.tokens - t0, self.used.credits - c0, self.used.wall_s - w0])
        self.history = self.history[-50:]
        self._step_start = (self.used.tokens, self.used.credits, self.used.wall_s)

    # -- decisions -----------------------------------------------------------------
    def exhausted(self) -> Optional[str]:
        self.tick()
        if self.used.tokens >= self.limits.tokens:
            return "tokens"
        if self.limits.credits > 0 and self.used.credits >= self.limits.credits:
            return "credits"
        if self.used.wall_s >= self.limits.wall_s:
            return "time"
        return None

    def projection(self, remaining_steps: int) -> dict:
        recent = self.history[-self.k:]
        if not recent:
            return {"tokens": 0, "credits": 0.0, "time": 0.0}
        n = len(recent)
        mean = [sum(r[i] for r in recent) / n for i in range(3)]
        rs = max(0, remaining_steps)
        return {"tokens": int(mean[0] * rs), "credits": round(mean[1] * rs, 4), "time": round(mean[2] * rs, 1)}

    def over_projection(self, remaining_steps: int) -> Optional[str]:
        """The first line where spent + projected remaining exceeds the limit, else None."""
        p = self.projection(remaining_steps)
        self.tick()
        if self.used.tokens + p["tokens"] > self.limits.tokens:
            return "tokens"
        if p["credits"] > 0 and self.used.credits + p["credits"] > self.limits.credits:
            return "credits"
        if self.used.wall_s + p["time"] > self.limits.wall_s:
            return "time"
        return None

    def should_soft_pause(self, remaining_steps: int) -> Optional[str]:
        """Product rule: only MONEY interrupts the user. The soft pause fires only when spent +
        projected credits exceed the credit budget (once per run); tokens / time run on to their
        hard limit without asking."""
        if self.soft_used or remaining_steps <= 0:
            return None
        self.tick()
        return "credits" if self._credits_over(remaining_steps) else None

    def _credits_over(self, remaining_steps: int) -> bool:
        p = self.projection(remaining_steps)
        return p["credits"] > 0 and self.used.credits + p["credits"] > self.limits.credits

    def extend(self, factor: float = 1.0) -> None:
        """'Continue' after a soft pause / exhaustion: add another budget of the same size."""
        self.limits = BudgetLimits(
            tokens=int(self.limits.tokens + max(self.limits.tokens * factor, self.used.tokens - self.limits.tokens + 1)),
            credits=self.limits.credits * (1 + factor),
            wall_s=max(self.limits.wall_s, self.used.wall_s) + self.limits.wall_s * factor,
            hard_steps=self.limits.hard_steps)

    def snapshot(self) -> dict:
        self.tick()
        return {"limits": asdict(self.limits), "used": asdict(self.used),
                "history": self.history, "soft_used": self.soft_used}

    @classmethod
    def restore(cls, data: dict, **kw) -> "RunBudget":
        return cls(BudgetLimits(**data["limits"]), used=BudgetUsed(**data["used"]),
                   history=data.get("history") or [], soft_used=bool(data.get("soft_used")), **kw)

    def ui(self) -> dict:
        self.tick()
        L, U = self.limits, self.used

        def pct(a, b):
            return round(min(1.0, a / b), 3) if b else 0.0
        return {"step": U.steps, "hard_cap": L.hard_steps,
                "tokens": {"used": U.tokens, "limit": L.tokens, "pct": pct(U.tokens, L.tokens)},
                "credits": {"used": round(U.credits, 4), "limit": L.credits, "pct": pct(U.credits, L.credits)},
                "time": {"used": round(U.wall_s, 1), "limit": L.wall_s, "pct": pct(U.wall_s, L.wall_s)},
                "soft": max(pct(U.tokens, L.tokens), pct(U.credits, L.credits), pct(U.wall_s, L.wall_s)) >= self.soft_fraction}


# ---------------------------------------------------------------------------
# ProgressTracker
# ---------------------------------------------------------------------------

READ_ONLY_TOOLS = frozenset({
    "get_canvas", "view_canvas", "view_video", "list_models", "brand_kits", "server_info",
    "ToolSearch", "tool_search", "read_skill", "list_skills", "memory_read", "read_memory",
    "web_search", "web_fetch", "search", "get_shape", "list_shapes", "wait_generation",
})


def _capped_readonly(tool: str) -> bool:
    base = re.sub(r"^mcp__\w+__", "", tool or "")
    return base == "skill" or (base in READ_ONLY_TOOLS and base != "wait_generation")


_VOLATILE_RE = re.compile(
    r'"(?:elapsed[_a-z]*|duration[_a-z]*|time|timestamp|ts|until|updated_at|created_at|now|request_id)"\s*:\s*[^,}\]]+')
_NUM_TS_RE = re.compile(r"\b1[6-9]\d{8,11}\b")


def normalize_result(text: str) -> str:
    """Drop timestamps / durations / data URLs so the same outcome has the same fingerprint."""
    t = _DATA_URL_RE.sub("[img]", text or "")
    t = _VOLATILE_RE.sub('"_":0', t)
    t = _NUM_TS_RE.sub("0", t)
    return " ".join(t.split())[:4000]


_ID_RE = re.compile(r'"(?:id|ids|shape_id|shapes|artifact_id|job_id)"\s*:\s*(\[[^\]]*\]|"[^"]+")')


def artifact_ids(text: str) -> set[str]:
    out: set[str] = set()
    for m in _ID_RE.finditer(text or ""):
        raw = m.group(1)
        try:
            v = json.loads(raw)
        except ValueError:
            continue
        for item in (v if isinstance(v, list) else [v]):
            if isinstance(item, str) and item:
                out.add(item)
            elif isinstance(item, dict) and item.get("id"):
                out.add(str(item["id"]))
    return out


def _h(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:16]


@dataclass
class StepObservation:
    tool: str
    args_key: str
    result: str
    failed: bool = False


DEFAULT_PLANNED_IMAGES = 4  # generate_image page clamp (plan_quote.units_of)


@dataclass
class ProgressTracker:
    stall_steps: int = 4
    readonly_max: int = 8
    tool_fail_max: int = 3
    repeat_max: int = 3
    last_fp: str = ""
    unchanged: int = 0
    readonly_run: int = 0
    fail_run: int = 0
    last_call: str = ""
    repeat_run: int = 0
    same_tool_max: int = 3   # #705 P1: >3 consecutive steps calling only the same tool = hard stop
    # #705 budget caps (tech lead): <= 30 PAID/external calls (guide.PAID_TOOLS: WaveSpeed generate/edit/video/...;
    # local tools like add_text do not count), <= 300 calls of any tool (backstop), generate_image <= planned + 2.
    # No per-run plan count exists yet and skills declare none, so planned falls back to the page's max batch (4).
    tool_calls_max: int = 30
    all_calls_max: int = 300
    paid_calls: int = 0
    planned_images: int = 0
    total_calls: int = 0
    gen_calls: int = 0
    # #705: wait_generation is outside the 30 cap but each task gets max 10 min OR 120 polls -> stuck:timeout
    wait_max_s: float = 600.0
    wait_max_polls: int = 120
    wait_first: dict = field(default_factory=dict)   # task id -> run-clock time of first poll
    wait_waited_s: float = 0.0                       # #709: longest wait so far (run clock), for the card copy
    wait_polls: dict = field(default_factory=dict)   # task id -> polls so far
    last_tool: str = ""
    same_tool_run: int = 0
    nudged: bool = False
    seen_artifacts: list = field(default_factory=list)
    stuck_at: int = 0

    def observe(self, step: int, obs: list[StepObservation], canvas_fp: str = "") -> Optional[str]:
        """Feed one loop step (one assistant message worth of tool calls). Returns a stuck
        sub-reason (no_progress|repeat|tool_error|readonly_limit) or None."""
        if not obs:
            return None
        seen = set(self.seen_artifacts)
        new_ids: set[str] = set()
        all_ro = True
        for o in obs:
            if o.tool not in READ_ONLY_TOOLS:
                # Polling (wait_generation / get_canvas ...) is not "repeat"; read-only steps are
                # bounded only by readonly_max.
                call = _h(o.tool, o.args_key)
                self.repeat_run = self.repeat_run + 1 if call == self.last_call else 1
                self.last_call = call
            self.fail_run = self.fail_run + 1 if o.failed else 0
            if not o.failed:
                new_ids |= artifact_ids(o.result) - seen
            if o.tool not in READ_ONLY_TOOLS:
                all_ro = False
        self.seen_artifacts = sorted(seen | new_ids)[-2000:]
        if self.fail_run >= self.tool_fail_max:
            return self._stall(step, "tool_error")
        if self.repeat_run >= self.repeat_max:
            return self._stall(step, "repeat")
        # Fingerprint = canvas state + normalized tool results + new artifact ids.
        fp = _h(canvas_fp, *(normalize_result(o.result) for o in obs), *sorted(new_ids))
        if all_ro:
            self.readonly_run += 1
            # Read-only steps never count as "no progress"; they have their own cap.
            if self.readonly_run > self.readonly_max:
                return self._stall(step, "readonly_limit")
        else:
            self.readonly_run = 0
            self.unchanged = self.unchanged + 1 if fp == self.last_fp else 1
            if self.unchanged >= self.stall_steps:
                return self._stall(step, "no_progress")
        self.last_fp = fp
        # #705 P1: one step = one assistant message, so a parallel batch (4x generate_image) counts once;
        # a step that lands a new artifact (shape / job id) is progress and resets the run.
        tools = {o.tool for o in obs if o.tool not in READ_ONLY_TOOLS}
        step_tool = next(iter(tools)) if len(tools) == 1 else ""
        if new_ids or not step_tool:
            self.same_tool_run = 0
        else:
            self.same_tool_run = self.same_tool_run + 1 if step_tool == self.last_tool else 1
        self.last_tool = step_tool
        if self.same_tool_run > self.same_tool_max:
            return self._stall(step, "same_tool")
        return None

    def _stall(self, step: int, sub: str) -> str:
        self.stuck_at = step
        return sub

    def gen_cap(self) -> int:
        return (self.planned_images or DEFAULT_PLANNED_IMAGES) + 2

    def over_budget(self, obs: list[StepObservation]) -> bool:
        """#705: count this step's calls; True once the run exceeds the tool-call or generate_image cap (never reset)."""
        from .guide import PAID_TOOLS
        self.total_calls += len(obs)
        # #705: paid/external calls AND read-only calls (skill reads, views; not wait_generation polls) share the
        # 30 cap, so a read-only loop (stuck:repeat style) cannot run past it either.
        self.paid_calls += sum(1 for o in obs if o.tool in PAID_TOOLS or _capped_readonly(o.tool))
        self.gen_calls += sum(1 for o in obs if o.tool == "generate_image")
        return (self.paid_calls > self.tool_calls_max or self.total_calls > self.all_calls_max
                or self.gen_calls > self.gen_cap())

    def wait_timeout(self, obs: list[StepObservation], now: Optional[float] = None) -> bool:
        """#705: True once any task polled by wait_generation passes wait_max_s since its first poll or wait_max_polls."""
        # #709: callers pass the run's clock (time.monotonic-based, same as the other loop caps)
        now = time.monotonic() if now is None else now
        hit = False
        for o in obs:
            if re.sub(r"^mcp__\w+__", "", o.tool or "") != "wait_generation":
                continue
            try:
                args = json.loads(o.args_key.split("\x00", 1)[1])
            except (IndexError, ValueError):
                args = {}
            ids = args.get("ids") if isinstance(args, dict) else None
            ids = [str(i) for i in ids] if isinstance(ids, list) and ids else ["*"]
            for i in ids:
                self.wait_first.setdefault(i, now)
                self.wait_polls[i] = self.wait_polls.get(i, 0) + 1
                self.wait_waited_s = max(self.wait_waited_s, now - self.wait_first[i])
                if self.wait_polls[i] > self.wait_max_polls or now - self.wait_first[i] > self.wait_max_s:
                    hit = True
        return hit

    def reset_after_nudge(self) -> None:
        self.nudged = True
        self.unchanged = self.readonly_run = self.fail_run = self.repeat_run = self.same_tool_run = 0
        self.last_call = ""

    def snapshot(self) -> dict:
        return asdict(self)

    @classmethod
    def restore(cls, data: dict) -> "ProgressTracker":
        return cls(**{k: v for k, v in (data or {}).items() if k in cls.__dataclass_fields__})


TRY_ANOTHER_APPROACH = {
    "zh": "系统提示：最近几步没有新进展（{why}）。请换一个思路：换工具、换参数或换步骤顺序，不要重复刚才的调用。",
    "en": "System note: the last steps made no progress ({why}). Try a different approach: another "
          "tool, other parameters or another order. Do not repeat the previous calls.",
}
