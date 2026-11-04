"""#732 / #734 (smoke run 1 blockers, $0, mocks only).

#732: bot/local_llm.py must not import ``ComfyArt.*`` absolutely (ComfyUI loads the node under its folder name, so
``ComfyArt`` is not importable there), and paid_gate must fail CLOSED when pricing raises.
#734: generate_image with an unregistered model falls back to Auto, records the original value and the reason, never
asks the user, and is still priced (on the model Auto will run) before the call.
"""
import importlib
import importlib.util
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ComfyArt.api.mcp_tools import canvas
from ComfyArt.bot import agent_loop
from ComfyArt.bot.guide import AGENT_GUIDE
from ComfyArt.bot.local_llm import LocalLlmProvider

ROOT = Path(__file__).resolve().parents[1]
PKG_SRC = [p for d in ("api", "bot") for p in (ROOT / d).rglob("*.py")]


def test_package_has_no_absolute_comfyart_imports():
    bad = [f"{p.relative_to(ROOT)}:{i}" for p in PKG_SRC
           for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
           if re.match(r"\s*(from|import)\s+ComfyArt\b", line)]
    assert bad == []


def test_local_llm_imports_under_another_package_name_from_repo_root():
    """The repo root loaded as a package NOT named ComfyArt (like custom_nodes/<folder>): local_llm imports and its
    price helpers resolve api.wavespeed through the package-relative import."""
    name = "comfyart_node_732"
    spec = importlib.util.spec_from_loader(name, loader=None, is_package=True)
    pkg = importlib.util.module_from_spec(spec)
    pkg.__path__ = [str(ROOT)]
    sys.modules[name] = pkg
    try:
        mod = importlib.import_module(f"{name}.bot.local_llm")
        assert float(mod.LocalLlmProvider._threshold(None)) >= 0
        from comfyart_node_732.bot import plan_quote  # noqa: F401  (relative api import inside)
        assert not any(k == "ComfyArt" or k.startswith("ComfyArt.") for k in
                       getattr(mod, "__dict__", {}) if isinstance(k, str) and k.startswith("ComfyArt"))
    finally:
        for k in [k for k in sys.modules if k == name or k.startswith(name + ".")]:
            del sys.modules[k]


def _ctx(pricer):
    return SimpleNamespace(paid={}, lang="en", pending_stop=None, pricer=pricer,
                           budget=SimpleNamespace(used=SimpleNamespace(steps=0),
                                                  can_afford=lambda p: True), mode="interactive")


async def test_paid_gate_fails_closed_when_pricing_raises():
    async def boom(name, args):
        raise ModuleNotFoundError("No module named 'ComfyArt'")
    ctx = _ctx(boom)
    action, text, price = await agent_loop.paid_gate(ctx, "generate_image", {"prompt": "x"}, None, call_id="c1")
    assert action == "skip" and price == 0.0
    assert "ModuleNotFoundError" in text and "not sent" in text
    assert ctx.paid == {}  # no pending marker: nothing went out


REAL_IDS = None


def _unknown():
    return "gpt-image-1.5"


async def test_unknown_model_goes_through_auto_with_original_and_reason(monkeypatch):
    sent = []

    async def submit(action, args, project, timeout, chat=""):
        sent.append(dict(args))
        return {"ids": ["g1"], "model": args.get("model")}

    monkeypatch.setattr(canvas, "submit_command", submit)
    assert canvas.unregistered_model("generate_image", {"model": _unknown()}) == _unknown()
    out = await canvas._relay_run("generate_image", {"prompt": "Naive hand-drawn giant coffee cup", "model": _unknown()},
                                  "", 20.0)
    assert len(sent) == 1 and sent[0].get("model") != _unknown()
    assert "status" not in out or out["status"] != "failed"
    mc = out["model_choice"]
    assert mc["auto"] is True and mc["requested_model"] == _unknown()
    assert out["requested_model"] == _unknown()
    assert _unknown() in out["model_fallback_reason"]["en"] and "Auto" in out["model_fallback_reason"]["en"]
    auto = canvas._auto_choice("generate_image", {"prompt": "Naive hand-drawn giant coffee cup"})
    assert mc["model"] == auto["model"]


async def test_registered_model_is_untouched(monkeypatch):
    sent = []

    async def submit(action, args, project, timeout, chat=""):
        sent.append(dict(args))
        return {"ids": ["g1"], "model": args.get("model")}

    monkeypatch.setattr(canvas, "submit_command", submit)
    real = sorted(canvas.registered_ids("generate_image"))[0]
    out = await canvas._relay_run("generate_image", {"prompt": "x", "model": real}, "", 20.0)
    assert sent[0]["model"] == real and "requested_model" not in out


async def test_unknown_model_is_priced_on_the_auto_model_before_the_call(monkeypatch):
    provider = LocalLlmProvider(base_url=lambda: "http://x/v1")
    priced = []

    async def price_one(model, inputs):
        priced.append((model, dict(inputs)))
        return 0.0378
    monkeypatch.setattr(provider, "_price_one", price_one)
    args = {"prompt": "Naive hand-drawn giant coffee cup", "model": _unknown()}
    assert await provider._price_call("generate_image", args) == 0.0378
    auto = canvas._auto_choice("generate_image", {"prompt": args["prompt"]})
    assert priced == [(auto["model"], {"prompt": args["prompt"]})]


def test_agent_prompt_names_only_registered_model_ids():
    ids = {m for f in __import__("ComfyArt.api.wavespeed", fromlist=["load_config"]).load_config()["features"].values()
           for m in (x["id"] for x in f.get("models") or [])}
    named = set(re.findall(r"\b[a-z0-9-]+/[a-z0-9.\-]+(?:/[a-z0-9.\-]+)?\b", AGENT_GUIDE))
    named = {n for n in named if re.search(r"\d", n)}  # model ids carry versions
    assert {n for n in named if n not in ids} == set()
    assert "registered ids only" in AGENT_GUIDE and "never guess or invent" in AGENT_GUIDE
