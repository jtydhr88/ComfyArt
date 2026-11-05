"""#328/#330 Question-card protocol: validate_spec / validate_answer."""
from __future__ import annotations

import pytest

from ComfyArt.api import bot_asks


OPTS = [
    {"id": "a", "label": "A"},
    {"id": "b", "label": "B"},
    {"id": "c", "label": "C"},
]


def test_validate_spec_defaults_kind_question_and_allow_skip():
    spec = bot_asks.validate_spec({"prompt": "ratio?", "options": OPTS})
    assert spec["kind"] == bot_asks.QUESTION_KIND
    assert spec["allow_skip"] is True
    assert spec["min_selections"] == 1
    assert spec["max_selections"] == 1
    assert "defaults" not in spec


def test_validate_spec_recommended_and_defaults_and_page():
    opts = [
        {"id": "a", "label": "A", "recommended": True},
        {"id": "b", "label": "B"},
        {"id": "c", "label": "C", "description": "wide"},
    ]
    spec = bot_asks.validate_spec({
        "prompt": "style?",
        "options": opts,
        "max_selections": 2,
        "page": 1,
        "page_count": 2,
    })
    assert spec["defaults"] == ["a"]
    assert spec["options"][0]["recommended"] is True
    assert spec["options"][2]["description"] == "wide"
    assert spec["page"] == 1 and spec["page_count"] == 2

    spec2 = bot_asks.validate_spec({
        "prompt": "style?",
        "options": opts,
        "defaults": ["b", "c"],
        "max_selections": 2,
    })
    assert spec2["defaults"] == ["b", "c"]


def test_validate_spec_rejects_bad_defaults_and_page():
    with pytest.raises(ValueError, match="unknown default"):
        bot_asks.validate_spec({
            "prompt": "q", "options": OPTS, "defaults": ["z"],
        })
    with pytest.raises(ValueError, match="defaults exceed"):
        bot_asks.validate_spec({
            "prompt": "q", "options": OPTS, "defaults": ["a", "b"],
            "max_selections": 1,
        })
    with pytest.raises(ValueError, match="page cannot exceed"):
        bot_asks.validate_spec({
            "prompt": "q", "options": OPTS, "page": 3, "page_count": 2,
        })


def test_validate_answer_skip_empty_selected():
    spec = bot_asks.validate_spec({"prompt": "q", "options": OPTS})
    bot_asks.validate_answer(spec, [], "")  # allow_skip default
    with pytest.raises(ValueError, match="at least"):
        bot_asks.validate_answer({**spec, "allow_skip": False}, [], "")


def test_validate_answer_multi_and_other():
    spec = bot_asks.validate_spec({
        "prompt": "q",
        "options": OPTS,
        "min_selections": 1,
        "max_selections": 2,
        "allow_other": True,
        "allow_skip": False,
    })
    bot_asks.validate_answer(spec, ["a", "b"], "")
    bot_asks.validate_answer(spec, [], "free text")
    with pytest.raises(ValueError, match="at most"):
        bot_asks.validate_answer(spec, ["a", "b", "c"], "")
    with pytest.raises(ValueError, match="unknown"):
        bot_asks.validate_answer(spec, ["z"], "")
    with pytest.raises(ValueError, match="free-text"):
        bot_asks.validate_answer({**spec, "allow_other": False}, [], "nope")


def test_skip_note_text():
    note = bot_asks.skip_note()
    assert "skipped" in note
    assert "acknowledge the skip" in note
    assert "continue the user's original task" in note
    assert "Only if their own instructions asked you to wait" in note
    assert "do not re-ask" in note
    assert "sensible defaults" not in note
    # Wait/no-generate is conditional — not a global forbid on every skip.
    assert "do NOT generate images or call generation tools this turn" not in note


def test_answer_note_text():
    note = bot_asks.answer_note()
    assert "answered" in note
    assert "restate the selected preference" in note
    assert "continue the user's original task" in note
    assert "Only if their own instructions asked you to wait" in note
    assert "sensible defaults" not in note
    assert "do NOT generate images or call generation tools this turn" not in note


def test_allow_skip_false_explicit():
    spec = bot_asks.validate_spec({
        "prompt": "q", "options": OPTS, "allow_skip": False,
    })
    assert spec["allow_skip"] is False


def test_validate_spec_questions_multi_and_paging():
    spec = bot_asks.validate_spec({
        "questions": [
            {
                "id": "brand",
                "prompt": "Brand name?",
                "allow_other": True,
                "options": [],
                "page": 1,
            },
            {
                "id": "style",
                "prompt": "Style?",
                "options": OPTS,
                "page": 1,
            },
            {
                "id": "pack",
                "prompt": "Packaging?",
                "options": [
                    {"id": "bag", "label": "Bag"},
                    {"id": "box", "label": "Box"},
                    {"id": "can", "label": "Can"},
                ],
                "max_selections": 2,
                "page": 2,
            },
        ],
        "page_count": 2,
        "allow_skip": True,
    })
    assert spec["kind"] == bot_asks.QUESTION_KIND
    assert spec["page_count"] == 2
    assert len(spec["questions"]) == 3
    assert spec["prompt"] == "Brand name?"
    assert spec["questions"][0]["options"] == []
    assert spec["questions"][0]["allow_other"] is True


def test_validate_spec_questions_rejects_bad():
    with pytest.raises(ValueError, match="duplicate question"):
        bot_asks.validate_spec({
            "questions": [
                {"id": "a", "prompt": "A?", "options": OPTS},
                {"id": "a", "prompt": "B?", "options": OPTS},
            ],
        })
    with pytest.raises(ValueError, match="allow_other"):
        bot_asks.validate_spec({
            "questions": [
                {"id": "a", "prompt": "A?", "options": []},
            ],
        })
    with pytest.raises(ValueError, match="exceed page_count"):
        bot_asks.validate_spec({
            "questions": [
                {"id": "a", "prompt": "A?", "options": OPTS, "page": 3},
            ],
            "page_count": 2,
        })


def test_validate_answer_answers_map():
    spec = bot_asks.validate_spec({
        "questions": [
            {"id": "brand", "prompt": "Brand?", "allow_other": True, "options": [], "page": 1},
            {"id": "style", "prompt": "Style?", "options": OPTS, "page": 1},
        ],
        "page_count": 1,
        "allow_skip": False,
    })
    bot_asks.validate_answer(spec, [], "", {
        "brand": {"selected": [], "other_text": "Acme"},
        "style": {"selected": ["a"]},
    })
    with pytest.raises(ValueError, match="missing answers"):
        bot_asks.validate_answer(spec, [], "", {"brand": {"selected": [], "other_text": "Acme"}})
    with pytest.raises(ValueError, match="at least"):
        bot_asks.validate_answer(spec, [], "", {
            "brand": {"selected": [], "other_text": "Acme"},
            "style": {"selected": []},
        })


def test_validate_answer_answers_skip():
    spec = bot_asks.validate_spec({
        "questions": [
            {"id": "a", "prompt": "A?", "options": OPTS},
            {"id": "b", "prompt": "B?", "options": OPTS},
        ],
    })
    bot_asks.validate_answer(spec, [], "", {})
    bot_asks.validate_answer(spec, [], "", {
        "a": {"selected": []},
        "b": {"selected": []},
    })


def test_ask_user_confirm_then_continue_guide_and_tool_desc():
    """#766: after ask_user, always confirm; wait/no-generate only if user asked to wait."""
    from ComfyArt.bot.guide import AGENT_GUIDE
    from ComfyArt.api.mcp_tools.bot_tools import TOOLS
    assert "After ask_user returns" in AGENT_GUIDE
    assert "always reply first" in AGENT_GUIDE
    assert "continue the original task" in AGENT_GUIDE
    assert "generation tools are OK" in AGENT_GUIDE
    assert "Only when the user's own instructions" in AGENT_GUIDE
    assert "explicitly asked you to wait or not generate yet" in AGENT_GUIDE
    # Wait templates are examples for the explicit-wait branch, not the default path.
    assert "Got it — your preferred logo style is minimal" in AGENT_GUIDE
    assert "I'll skip the logo style question" in AGENT_GUIDE
    assert "知道了 — 你希望的 logo 风格是极简" in AGENT_GUIDE
    assert "这个问题我先跳过" in AGENT_GUIDE
    # Must NOT globally forbid same-turn generation after every ask_user.
    assert "do NOT call generate_image / generate_video / wait_generation" not in AGENT_GUIDE
    # Do not force ask_user on a plain design prompt.
    assert "Design a logo" not in AGENT_GUIDE or "must ask" not in AGENT_GUIDE.lower()
    desc = TOOLS["ask_user"]["description"]
    assert "acknowledge in chat" in desc
    assert "continue the original task" in desc
    assert "generation OK" in desc
    assert "Only if their own instructions" in desc
    assert "sensible defaults" not in desc


@pytest.mark.asyncio
async def test_ask_user_attaches_answer_or_skip_note(monkeypatch):
    """#766: answered → answer_note; skip → skip_note (confirm then continue; not defaults)."""
    from ComfyArt.api.mcp_tools import bot_tools
    from ComfyArt.api import bot_asks as asks

    async def fake_answered(chat_id, state, spec):
        return {"status": "answered", "selected": ["minimal"], "other_text": ""}

    async def fake_skipped(chat_id, state, spec):
        return {"status": "answered", "selected": [], "other_text": ""}

    monkeypatch.setattr(bot_tools, "bot_turn_state", lambda: ("c1", object()))
    monkeypatch.setattr(bot_tools, "_await_ask", fake_answered)
    opts = [
        {"id": "minimal", "label": "Minimal"},
        {"id": "playful", "label": "Playful"},
    ]
    out = await bot_tools.ask_user({
        "prompt": "logo style?",
        "options": opts,
        "allow_skip": True,
    })
    assert out["status"] == "answered"
    assert out.get("skipped") is not True
    assert out["note"] == asks.answer_note()
    assert "continue the user's original task" in out["note"]
    assert "Only if their own instructions asked you to wait" in out["note"]

    monkeypatch.setattr(bot_tools, "_await_ask", fake_skipped)
    out2 = await bot_tools.ask_user({
        "prompt": "logo style?",
        "options": opts,
        "allow_skip": True,
    })
    assert out2.get("skipped") is True
    assert out2["note"] == asks.skip_note()
    assert "continue the user's original task" in out2["note"]
    assert "sensible defaults" not in out2["note"]
