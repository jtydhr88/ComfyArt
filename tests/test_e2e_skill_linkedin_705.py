"""#705 e2e — linkedin-banner chain through the real budget agent loop (bot/agent_loop.py) with a scripted LLM and
mocked MCP / WaveSpeed (no paid call). Covers the happy chain and the #705 repro (6 skill loads -> empty id)."""
from __future__ import annotations

import json

import pytest

from ComfyArt.api.bot_send import compose_provider_text
from tests.test_agent_budget_391 import Rig, _known_low_price, calls, card, reply, stop_of, store  # noqa: F401

SKILL = "LinkedIn Banner"
READ = ("skill", {"action": "read", "name": SKILL})
# #705: the REAL tool format: status=success, text "[tool error] ValueError: ..." (not "[error]").
EMPTY_ERR = "[tool error] ValueError: [non-retryable] skill read needs a non-empty id or name (e.g. id=\"linkedin-banner\")"


def _mcp(name, args, i):
    if name == "skill":
        if not (args.get("id") or args.get("name")):
            return EMPTY_ERR
        return json.dumps({"id": "linkedin-banner", "name": SKILL, "instructions": "Ship 1584x396 banners."})
    if name == "generate_image":
        return json.dumps({"id": f"shape:{i}", "job": f"job{i}"})
    return json.dumps({"id": f"shape:{i}"})


def test_prompt_names_the_skill_for_the_read() -> None:
    text = compose_provider_text("Banner for a data engineer", skill_name=SKILL)
    assert "action='read'" in text and f"name={SKILL!r}" in text


async def test_linkedin_banner_chain_happy_path(monkeypatch, store):  # noqa: F811
    script = [calls(READ), calls(("generate_image", {"prompt": "1584x396 LinkedIn banner", "width": 1584, "height": 396})),
              calls(("wait_generation", {"ids": ["job2"]})), reply("Done")]
    r = Rig(monkeypatch, script, store=store, mcp=_mcp)
    res, _ = await r.send(compose_provider_text("Banner for a data engineer", skill_name=SKILL))
    assert stop_of(res)["reason"] == "done", stop_of(res)
    assert [c[0] for c in r.mcp] == ["skill", "generate_image", "wait_generation"]
    assert r.mcp[0][1] == {"action": "read", "name": SKILL}


async def test_linkedin_banner_705_repro_stops_on_empty_id(monkeypatch, store):  # noqa: F811
    """#705: no current skill (plain chat) and the model reads with an empty id. The tool returns the REAL format
    (status success, "[tool error] ValueError: [non-retryable] ...") -> one hard, non-retryable stop."""
    r = Rig(monkeypatch, lambda m, n: calls(("skill", {"action": "read", "id": ""})), store=store, mcp=_mcp)
    res, events = await r.send("Banner")
    s = stop_of(res)
    assert (s["reason"], s["sub"]) == ("stuck", "non_retryable"), s
    empties = [c for c in r.mcp if c[0] == "skill" and not (c[1].get("id") or c[1].get("name"))]
    assert len(empties) == 1                       # never retried
    assert not [c for c in r.mcp if c[0] == "generate_image"]  # nothing paid


async def test_read_without_id_gets_autofilled_then_images_are_produced(monkeypatch, store, caplog):  # noqa: F811
    """#705 root cause: deepseek's first call is skill {"action":"read"} with no id/name. In a run started from a
    skill the server fills the run's skill, logs it once, and the chain goes on to produce the image."""
    script = [calls(("skill", {"action": "read"})),
              calls(("generate_image", {"prompt": "1584x396 LinkedIn banner", "width": 1584, "height": 396})),
              calls(("wait_generation", {"ids": ["job2"]})), reply("Done")]
    r = Rig(monkeypatch, script, store=store, mcp=_mcp)
    with caplog.at_level("INFO"):
        res, _ = await r.send(compose_provider_text("Banner for a data engineer", skill_name=SKILL))
    assert stop_of(res)["reason"] == "done", stop_of(res)
    assert r.mcp[0] == ("skill", {"action": "read", "name": SKILL}) or tuple(r.mcp[0][:2]) == ("skill", {"action": "read", "name": SKILL})
    assert [c[0] for c in r.mcp] == ["skill", "generate_image", "wait_generation"]
    fills = [m for m in caplog.messages if '"skill_autofill"' in m]
    assert len(fills) == 1 and SKILL in fills[0]


async def test_same_tool_guard_stops_varied_generate_without_progress(monkeypatch, store):  # noqa: F811
    """P1: same tool >3 steps in a row with no new artifact -> hard stop (no nudge)."""
    r = Rig(monkeypatch, lambda m, n: calls(("generate_image", {"prompt": f"v{n}"})), store=store,
            mcp=lambda name, a, i: f"queued attempt {i}")
    res, _ = await r.send("Banner")
    s = stop_of(res)
    assert s["sub"] == "same_tool", s
    assert len(r.paid_mcp()) == 4


async def test_budget_cap_every_step_new_image_never_finishes(monkeypatch, store):  # noqa: F811
    """#705 tech lead: each step produces a new image (real progress) but the model never finishes ->
    stopped at planned(4, default)+2 generate_image calls with stuck:budget. Alternating tools dodge same_tool."""
    def script(m, n):
        return calls(("generate_image", {"prompt": f"v{n}"})) if n % 2 == 0 else calls(("get_canvas", {"n": n}))
    r = Rig(monkeypatch, script, store=store, mcp=_mcp)
    res, _ = await r.send(compose_provider_text("Banner", skill_name=SKILL))
    s = stop_of(res)
    assert (s["reason"], s["sub"]) == ("stuck", "budget"), s
    assert len([c for c in r.mcp if c[0] == "generate_image"]) == 7  # 7th call trips the cap of 6
