"""#133: Auto picks a model by task type from api/auto_models.json (product table v1); user-named wins;
the tool result says which model and why (zh + en). All mocked: no page, no WaveSpeed call."""
import asyncio

import pytest

from ComfyArt.api import auto_models
from ComfyArt.api.mcp_tools import canvas

SENT = []


@pytest.fixture(autouse=True)
def mocked(monkeypatch):
    SENT.clear()

    async def submit(action, args, project, timeout, chat=""):
        SENT.append((action, dict(args)))
        return {"ids": ["shape:g1"]}

    async def no_approval(label):
        return None
    monkeypatch.setattr(canvas, "submit_command", submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", no_approval)


def run(tool, **args):
    return asyncio.run(canvas.TOOLS[tool]["handler"](args))


def default(feature):
    return canvas.load_config()["features"][feature]["default"]


def test_same_prompt_many_turns_same_model():
    picks = {run("generate_image", prompt="a cup of coffee on a table")["model_choice"]["model"] for _ in range(5)}
    assert picks == {default("text_to_image")} == {"openai/gpt-image-2.5-flare/text-to-image"}
    assert all("model" not in a for _, a in SENT)  # default path unchanged: page resolves Auto


@pytest.mark.parametrize("prompt,model", [
    ("Movie poster with the headline \"SUMMER\"", "openai/gpt-image-2.5-flare/text-to-image"),
    ("Photorealistic portrait of an old fisherman", "bytedance/seedream-v5.0-pro"),
    ("Anime girl under cherry blossoms", "midjourney/text-to-image"),
    ("一张写实人像", "bytedance/seedream-v5.0-pro"),
    ("Minimal logo for a tea brand", "recraft-ai/recraft-v3"),
])
def test_task_type_hits_table(prompt, model):
    choice = run("generate_image", prompt=prompt)["model_choice"]
    assert choice["model"] == model and choice["auto"]
    if model != default("text_to_image"):
        assert SENT[-1][1]["model"] == model


def test_user_named_model_wins():
    choice = run("generate_image", prompt="Anime poster", model="alibaba/qwen-image-3.0/text-to-image")["model_choice"]
    assert choice == {**choice, "model": "alibaba/qwen-image-3.0/text-to-image", "auto": False}
    assert SENT[-1][1]["model"] == "alibaba/qwen-image-3.0/text-to-image"


def test_reply_states_model_and_reason_zh_en():
    note = run("generate_image", prompt="Photorealistic portrait")["model_choice"]["note"]
    assert note.startswith("用了 bytedance/seedream-v5.0-pro，因为") and "Used bytedance/seedream-v5.0-pro because" in note
    assert "say in your reply" in __import__("ComfyArt.bot.guide", fromlist=["AGENT_GUIDE"]).AGENT_GUIDE


def test_missing_model_raises_unregistered(monkeypatch, caplog):
    """#712: a table model the catalog does not register is an explicit error, no silent swap to the default."""
    real = auto_models.load_table()
    real["text_to_image"]["categories"][0]["model"] = "nope/not-in-catalog"
    monkeypatch.setattr(auto_models, "load_table", lambda: real)
    n = len(SENT)
    out = run("generate_image", prompt="logo for a cafe")
    assert out["status"] == "failed" and out["kind"] == "unregisteredModel" and out["generation_succeeded"] is False
    assert "所选模型暂不可用" in out["user_message"] and "isn't available right now" in out["user_message"]
    assert "nope/not-in-catalog" in out["error"] and len(SENT) == n  # nothing was sent, nothing charged


def test_missing_model_uses_registered_fallback_and_logs(monkeypatch, caplog):
    real = auto_models.load_table()
    real["text_to_image"]["categories"][0].update(model="nope/not-in-catalog", fallback=["nope/also-missing", default("text_to_image")])
    monkeypatch.setattr(auto_models, "load_table", lambda: real)
    choice = run("generate_image", prompt="logo for a cafe")["model_choice"]
    assert choice["model"] == default("text_to_image") and choice["fallback"] == "nope/not-in-catalog"
    assert "registered fallback" in caplog.text


def test_choose_raises_directly():
    import pytest
    cfg = {"models": [{"id": "a"}], "default": "a"}
    with pytest.raises(auto_models.UnregisteredModel):
        auto_models.registered({"model": "b"}, {"a"}, "x/y")
    assert auto_models.registered({"model": "b", "fallback": "a"}, {"a"}, "x/y") == ("a", "b")


def test_edit_table_and_one_ref():
    assert run("edit_image", id="shape:a", prompt="change the sign text")["model_choice"]["model"] == default("image_edit")
    assert run("edit_image", id="shape:a", prompt="new background, keep the same person")["model_choice"]["model"] == "google/nano-banana-2.1/edit"
    choice = run("generate_image", prompt="poster-differentiated-compiler", refs=["shape:r"])["model_choice"]
    assert choice["model"] == default("image_edit") and choice["category"] == "references"
    assert "model" not in SENT[-1][1] and "edit_model" not in SENT[-1][1]


def test_one_base_image_uses_edit_default():
    choice = run("generate_image", prompt="make it blue", base="shape:b")["model_choice"]
    assert choice["model"] == default("image_edit") and "edit_model" not in SENT[-1][1]


def test_two_refs_auto_uses_nano_banana_and_says_why():
    choice = run("generate_image", prompt="the mug from <Picture 1> on the desk from <Picture 2>", refs=["shape:a", "shape:b"])["model_choice"]
    assert choice["model"] == "google/nano-banana-2.1/edit" and choice["auto"] and choice["category"] == "multi_reference"
    assert SENT[-1][1]["edit_model"] == "google/nano-banana-2.1/edit" and "model" not in SENT[-1][1]
    assert choice["note"].startswith("用了 google/nano-banana-2.1/edit，因为给了 2 张参考图")
    assert "Used google/nano-banana-2.1/edit because 2 reference images were given" in choice["note"]
    # same task, same model, every turn
    assert {run("generate_image", prompt="p", refs=["shape:a", "shape:b", "shape:c"])["model_choice"]["model"] for _ in range(3)} == {"google/nano-banana-2.1/edit"}


def test_two_refs_user_named_model_unchanged():
    choice = run("generate_image", prompt="p", refs=["shape:a", "shape:b"], model="openai/gpt-image-2/text-to-image")["model_choice"]
    assert not choice["auto"] and "edit_model" not in SENT[-1][1] and SENT[-1][1]["model"] == "openai/gpt-image-2/text-to-image"


def test_two_refs_missing_model_raises(monkeypatch):
    real = auto_models.load_table()
    real["image_edit"]["multi_reference"]["model"] = "nope/x"
    monkeypatch.setattr(canvas, "load_table", lambda: real)
    out = run("generate_image", prompt="p", refs=["shape:a", "shape:b"])
    assert out["status"] == "failed" and out["kind"] == "unregisteredModel" and "nope/x" in out["error"]


def test_page_runs_the_auto_edit_pick():
    """Front end: edit_model lands in meta.featureModels.image_edit, which both the real job and the cost estimate use."""
    root = __import__("pathlib").Path(__file__).resolve().parent.parent / "src"
    bot = (root / "botCommands.ts").read_text()
    gen = (root / "generate.ts").read_text()
    assert "featureModels: { image_edit: args.edit_model }" in bot
    assert "feature: 'image_edit', model: modelIn('image_edit', featureModelsOf(shape).image_edit), prompt" in gen
    assert "feature: 'image_edit', model: modelIn('image_edit', featureModelsOf(shape).image_edit), width" in gen


def test_table_models_are_in_catalog():
    cfg = canvas.load_config()["features"]
    for feature, spec in auto_models.load_table().items():
        ids = {m["id"] for m in cfg[feature]["models"]}
        assert all(c["model"] in ids for c in spec["categories"]), feature


def test_disabled_on_page_falls_back_to_default(monkeypatch):
    """Recraft turned off in model prefs: the page runs the default instead of 'unknown model' and the note says so."""
    flare = default("text_to_image")

    async def page(action, args, project, timeout, chat=""):
        SENT.append((action, dict(args)))
        assert args["auto_model"] is True  # tells the page it may fall back
        return {"ids": ["shape:g1"], "model": flare}
    monkeypatch.setattr(canvas, "submit_command", page)
    choice = run("generate_image", prompt="Minimal logo for a tea brand")["model_choice"]
    assert choice["model"] == flare and choice["fallback"] == "recraft-ai/recraft-v3"
    assert f"用了 {flare}" in choice["note"] and "已在模型设置里关闭" in choice["note"] and "turned off in model settings" in choice["note"]
    src = (__import__("pathlib").Path(__file__).resolve().parent.parent / "src" / "botCommands.ts").read_text()
    assert "(args.auto_model ? models[0] : undefined)" in src


@pytest.mark.parametrize("prompt,category", [
    ("an iconic city skyline at dusk", "default"),
    ("a cartoonish dog", "default"),
    ("app icon of a fox", "logo"),
    ("ICON, flat", "logo"),
    ("一个茶饮品牌的图标设计", "logo"),
    ("城市海报", "poster_text"),
])
def test_english_whole_words_chinese_substring(prompt, category):
    assert auto_models.choose("text_to_image", prompt, None, canvas.load_config())["category"] == category


def test_default_reason_wording():
    note = run("generate_image", prompt="a cup of coffee")["model_choice"]["note"]
    flare = default("text_to_image")
    assert note == f"用了 {flare}，这是通用生图的默认模型。/ Used {flare}, the default model for general image generation."


def test_named_model_with_refs_says_why():
    note = run("generate_image", prompt="p", refs=["shape:a", "shape:b"], model="openai/gpt-image-2/text-to-image")["model_choice"]["note"]
    assert "你指定了 openai/gpt-image-2/text-to-image" in note and "you named openai/gpt-image-2/text-to-image" in note
