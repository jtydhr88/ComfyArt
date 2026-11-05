"""#422: multi-turn context carries previous-turn image refs (shape id), not thinking."""
from __future__ import annotations

import json

from ComfyArt.api.bot_turns import (
    blocks_text,
    format_ref_lines,
    refs_from_blocks,
    _replay_history,
)
from ComfyArt.bot.local_llm import fit_history, _summarize_turns, _group_turns


def test_refs_from_blocks_skips_thinking_and_tools():
    blocks = [
        {"type": "thinking", "text": "do not leak"},
        {"type": "text", "text": "edit the poster"},
        {"type": "image", "shape": "shape:abc", "url": "/api/view?f=a.png", "name": "poster-differentiated-compiler"},
        {"type": "tool_use", "name": "generate_image", "input": {}},
        {"type": "video", "shape": "shape:vid", "url": "/api/view?f=v.mp4"},
        {"type": "audio", "shape": "shape:aud", "url": "/api/view?f=a.mp3",
         "transcript": "hello"},
    ]
    refs = refs_from_blocks(blocks)
    assert [r["kind"] for r in refs] == ["image", "video", "audio"]
    assert refs[0]["id"] == "shape:abc" and refs[0]["name"] == "poster-differentiated-compiler"
    assert refs[2]["transcript"] == "hello"
    assert all("do not leak" not in json.dumps(r) for r in refs)


def test_blocks_text_emits_shape_id_not_bare_url():
    blocks = [
        {"type": "thinking", "text": "secret"},
        {"type": "text", "text": "make it warmer"},
        {"type": "image", "shape": "shape:p1", "url": "/api/view?f=p.png", "name": "poster-differentiated-compiler"},
    ]
    text = blocks_text(blocks)
    assert "secret" not in text
    assert "make it warmer" in text
    assert "shape id shape:p1" in text
    assert "[Attached image 1" in text
    assert "[attached image:" not in text  # old bare form gone


def test_format_ref_lines_matches_send_path():
    refs = [{"id": "shape:a", "src": "/v", "name": "x", "kind": "image", "transcript": ""}]
    lines = format_ref_lines(refs)
    assert len(lines) == 1
    assert "shape id shape:a" in lines[0]
    assert "generation ref" in lines[0]


def test_replay_history_carries_refs(fresh_user_dir):
    from ComfyArt.api import chat_store

    chat = chat_store.create_chat(user="default", project="p422", provider="local-llm")
    first = chat_store.create_message(
        chat_id=chat["id"], role="user",
        blocks=[
            {"type": "thinking", "text": "ignore me"},  # should never appear
            {"type": "text", "text": "edit this"},
            {"type": "image", "shape": "shape:poster", "url": "/api/view?f=p.png",
             "name": "poster-differentiated-compiler"},
        ])
    chat_store.create_message(
        chat_id=chat["id"], role="assistant", parent_id=first["id"],
        blocks=[{"type": "text", "text": "done"}])
    nxt = chat_store.create_message(
        chat_id=chat["id"], role="user",
        blocks=[{"type": "text", "text": "brighter"}])
    current = chat_store.create_message(
        chat_id=chat["id"], role="assistant", blocks=[], status="streaming",
        parent_id=nxt["id"])
    history = _replay_history(chat["id"], current["id"])
    assert history[0]["role"] == "user"
    assert "shape id shape:poster" in history[0]["text"]
    assert history[0]["refs"][0]["id"] == "shape:poster"
    assert "ignore me" not in history[0]["text"]
    assert history[1]["role"] == "assistant" and history[1]["text"] == "done"


def test_fit_history_keeps_shape_id_in_verbatim():
    history = [
        {"role": "user",
         "text": 'edit\n[Attached image 1 "poster-differentiated-compiler": shape id shape:p1 — /api/view?f=p.png. '
                 "Use the shape id with edit tools or as a generation ref.]",
         "refs": [{"id": "shape:p1", "src": "/api/view?f=p.png", "name": "poster-differentiated-compiler",
                   "kind": "image", "transcript": ""}]},
        {"role": "assistant", "text": "updated"},
        {"role": "user", "text": "brighter"},
    ]
    msgs = fit_history(history, context_window=32_000)
    user0 = next(m for m in msgs if m["role"] == "user" and "edit" in m["content"])
    assert "shape id shape:p1" in user0["content"]
    assert "generation ref" in user0["content"]


def test_fit_history_summary_lists_image_refs():
    """When earlier turns compress, image refs survive in the summary."""
    long = "please refine the color grade and keep the composition " * 40
    history = []
    for i in range(10):
        history.append({
            "role": "user",
            "text": f"{long} turn{i}",
            "refs": [{"id": f"shape:img{i}", "src": f"/api/view?f={i}.png",
                      "name": "", "kind": "image", "transcript": ""}],
        })
        history.append({"role": "assistant", "text": f"ok{i}"})
    # Tight window forces summary of the head
    msgs = fit_history(history, context_window=4_000)
    summary = next((m["content"] for m in msgs if m["role"] == "system"), "")
    assert "Image refs:" in summary or any(
        "shape id" in m.get("content", "") for m in msgs if m["role"] == "user")
    # At least one earlier shape id must survive (summary or verbatim tail)
    blob = "\n".join(m["content"] for m in msgs)
    assert "shape:img" in blob


def test_summarize_turns_includes_refs_not_thinking():
    turns = _group_turns([
        {"role": "user", "text": "use this",
         "refs": [{"id": "shape:x", "src": "/v", "kind": "image", "name": "",
                   "transcript": ""}]},
        {"role": "assistant", "text": "ok"},
    ])
    s = _summarize_turns(turns)
    assert "Image refs:" in s
    assert "id=shape:x" in s
