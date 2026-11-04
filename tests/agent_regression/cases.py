"""#231: the tester's 15 tasks (+ the 80-step limit), each recorded for the zh and the en UI.
Each case is a scripted mock-LLM tool sequence plus what must come out of it."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from harness import Shape, Step

IMG = "shape:img1"


def ids(last: dict) -> dict:
    return {"ids": last.get("ids") or []}


def done(zh: str, en: str) -> Step:
    return Step(reply={"zh": zh, "en": en})


@dataclass
class Case:
    id: str
    title: str
    turns: list[dict]                       # [{"zh": text, "en": text}] one per user turn
    script: list[Step]
    tools: list[str]                        # expected tool-call order (all turns)
    paid: int                               # expected mock WaveSpeed submits
    shapes: dict[str, int]                  # expected shape count by type at the end
    limit: int = 12                         # step limit for this task
    shapes_initial: list[Shape] = field(default_factory=list)
    selection: list[str] = field(default_factory=list)
    brand_kit: Optional[dict] = None
    decline: bool = False
    no_key: bool = False
    status: str = "done"                    # last turn status
    error: Optional[dict] = None            # expected notice text prefix per lang
    reply: Optional[dict] = None            # substring the final reply must contain per lang
    llm_requests: Optional[int] = None
    xfail: str = ""                         # known gap: expected to change (reason)
    baseline_for: str = ""                  # current behaviour recorded; flips in that PR
    note: str = ""                          # free-form note shown in the report
    settings: dict = field(default_factory=dict)  # extra app settings for this case
    extra: Optional[str] = None             # name of an extra check in the test module


def _img(**kw):
    return Shape(id=IMG, type="image", **kw)


BRAND = {"name": "Aurora", "fonts": [{"role": "heading", "family": "Inter"}],
         "colors": [{"role": "primary", "hex": "#FF5A1F"}, {"role": "background", "hex": "#1B1B3A"}]}


def _gen_then_reply(tool, args, zh, en):
    return [Step(calls=[(tool, args)]), Step(calls=[("wait_generation", ids)]), done(zh, en)]


_FAIL = {  # #232: zh UI accepts Chinese only, en UI English only
    "timeout": {"zh": "模型响应超时，已重试 2 次仍失败", "en": "The model timed out; still failing after 2 retries"},
    "429": {"zh": "模型请求过于频繁（HTTP 429），已重试 2 次仍失败", "en": "Too many requests to the model (HTTP 429); still failing after 2 retries"},
    "500": {"zh": "模型服务出错（HTTP 500），已重试 2 次仍失败", "en": "The model service failed (HTTP 500); still failing after 2 retries"},
}


def faults(kind):
    """LLM fault after one paid image that never clears: retried twice (3 LLM attempts), then a bilingual
    error listing the steps already done. The paid tool is not re-run."""
    return Case(
        id=f"15-{kind}", title=f"fault injection: LLM {kind}, retries exhausted",
        turns=[{"zh": "画一只猫", "en": "Draw a cat"}],
        script=[Step(calls=[("generate_image", {"prompt": "a cat"})]), Step(fault=kind), Step(fault=kind),
                Step(fault=kind), done("已完成", "Done")],
        tools=["generate_image"], paid=1, shapes={"image": 1}, status="error",
        error=_FAIL[kind], llm_requests=4, extra="fail_done")


def faults_retry(kind):
    """P1-a: retry the LLM call twice, then carry on; the paid tool is never re-run."""
    return Case(
        id=f"15-{kind}-retry", title=f"fault injection: LLM {kind} retried x2 (P1-a)",
        turns=[{"zh": "画一只猫", "en": "Draw a cat"}],
        script=[Step(calls=[("generate_image", {"prompt": "a cat"})]), Step(fault=kind), Step(fault=kind),
                Step(calls=[("wait_generation", ids)]), done("已完成", "Done")],
        tools=["generate_image", "wait_generation"], paid=1, shapes={"image": 1},
        llm_requests=5, extra="retry_rows")


CASES: list[Case] = [
    Case("01", "t2i 1 image with size + style",
         [{"zh": "画一张水彩风格的猫，3:4 竖版", "en": "Draw a watercolor cat, 3:4 portrait"}],
         _gen_then_reply("generate_image", {"prompt": "a cat, watercolor style", "ratio": "3:4"}, "画好了", "Done"),
         ["generate_image", "wait_generation"], 1, {"image": 1}, extra="ratio"),
    Case("02", "t2i exactly 4 images",
         [{"zh": "画 4 张柯基插画", "en": "Draw 4 corgi illustrations"}],
         _gen_then_reply("generate_image", {"prompt": "corgi illustration", "count": 4}, "4 张画好了", "4 done"),
         ["generate_image", "wait_generation"], 4, {"image": 4}),
    Case("03", "selected image: change background to beach (image edit)",
         [{"zh": "把背景换成海边", "en": "Change the background to a beach"}],
         [Step(calls=[("get_canvas", {})]), *_gen_then_reply(
             "edit_image", lambda last: {"id": last["selection"][0], "prompt": "replace the background with a beach"},
             "背景换好了", "Background changed")],
         ["get_canvas", "edit_image", "wait_generation"], 1, {"image": 2},
         shapes_initial=[_img()], selection=[IMG], extra="edit_target"),
    Case("04", "t2v 5s",
         [{"zh": "生成一段 5 秒的海浪视频", "en": "Make a 5 second video of ocean waves"}],
         _gen_then_reply("generate_video", {"prompt": "ocean waves", "duration": 5}, "视频好了", "Video ready"),
         ["generate_video", "wait_generation"], 1, {"video": 1}, extra="t2v"),
    Case("05", "i2v from the selected image",
         [{"zh": "让选中的图动起来，做成视频", "en": "Turn the selected image into a video"}],
         [Step(calls=[("get_canvas", {})]), *_gen_then_reply(
             "generate_video", lambda last: {"prompt": "gentle camera push-in", "first_frame": last["selection"][0]},
             "视频好了", "Video ready")],
         ["get_canvas", "generate_video", "wait_generation"], 1, {"image": 1, "video": 1},
         shapes_initial=[_img()], selection=[IMG], extra="i2v"),
    Case("06", "15s upbeat music",
         [{"zh": "生成一段 15 秒的轻快音乐", "en": "Make 15 seconds of upbeat music"}],
         _gen_then_reply("generate_music", {"prompt": "upbeat cheerful pop instrumental", "duration": 15},
                         "音乐好了", "Music ready"),
         ["generate_music", "wait_generation"], 1, {"audio": 1}, extra="music"),
    Case("07", "SFX + voiceover as audio cards",
         [{"zh": "做一个开门音效，再配一句「欢迎光临」", "en": "Make a door-opening sound effect and a voiceover saying 'Welcome'"}],
         [Step(calls=[("generate_sound_effect", {"prompt": "door opening", "duration": 3})]),
          Step(calls=[("text_to_speech", {"text": "欢迎光临 / Welcome"})]),
          Step(calls=[("wait_generation", lambda last: {"ids": ["job:1", "job:2"]})]), done("音频好了", "Audio ready")],
         ["generate_sound_effect", "text_to_speech", "wait_generation"], 2, {"audio": 2}),
    Case("08", "edit elements, then title -> SALE",
         [{"zh": "把这张图拆成可编辑元素，标题改成「SALE」", "en": "Split this image into editable elements and change the title to 'SALE'"}],
         [Step(calls=[("edit_elements", {"id": IMG})]), Step(calls=[("wait_generation", ids)]),
          Step(calls=[("update_shapes", lambda last: {"updates": [{"id": last["results"][0]["shapes"][1], "text": "SALE"}]})]),
          done("标题已改成 SALE", "Title changed to SALE")],
         ["edit_elements", "wait_generation", "update_shapes"], 1, {"image": 2, "frame": 1, "text": 2},
         shapes_initial=[_img()], selection=[IMG], extra="sale"),
    Case("09", "single image to 3D",
         [{"zh": "把这张图转成 3D 模型", "en": "Turn this image into a 3D model"}],
         _gen_then_reply("image_to_3d", {"id": IMG}, "3D 模型好了", "3D model ready"),
         ["image_to_3d", "wait_generation"], 1, {"image": 1, "model3d": 1}, shapes_initial=[_img()], selection=[IMG]),
    Case("10", "poster with brand kit font + colors",
         [{"zh": "用品牌套件做一张促销海报", "en": "Make a promo poster with my brand kit"}],
         [Step(calls=[("brand_kits", {})]),
          Step(calls=[("generate_image", lambda last: {"prompt": "promo poster, colors " + ", ".join(c["hex"] for c in last["kits"][0]["colors"]), "ratio": "3:4"})]),
          Step(calls=[("wait_generation", ids)]),
          Step(calls=[("add_text", {"text": "BIG SALE", "font": "Inter", "color": "#FF5A1F", "font_size": 96})]),
          done("海报做好了", "Poster done")],
         ["brand_kits", "generate_image", "wait_generation", "add_text"], 1, {"image": 1, "text": 1},
         brand_kit=BRAND, extra="brand"),
    Case("11", "multi-turn 'brighter': 1 new image edited from the untouched original",
         [{"zh": "画一张咖啡店海报", "en": "Make a coffee shop poster"}, {"zh": "再亮一点", "en": "Make it brighter"}],
         [*_gen_then_reply("generate_image", {"prompt": "coffee shop poster"}, "海报好了", "Poster ready"),
          Step(calls=[("get_canvas", {})]),
          *_gen_then_reply("edit_image", lambda last: {"id": [s["id"] for s in last["shapes"] if s["type"] == "image"][0],
                                                      "prompt": "make it brighter"}, "调亮了", "Brighter now")],
         ["generate_image", "wait_generation", "get_canvas", "edit_image", "wait_generation"], 2, {"image": 2},
         extra="edit_original"),  # product ruling: 1 new edited image beside an untouched original
    Case("12", "PPTX deck, editable mode",
         [{"zh": "做一个 3 页的产品介绍 PPT，文字要可编辑", "en": "Make a 3-slide product deck with editable text"}],
         [Step(calls=[("create_slides", {"title": "Product", "slides": [
             {"title": "Intro", "bullets": ["What it is"]}, {"title": "Features", "bullets": ["Fast", "Simple"], "image": "product photo"},
             {"title": "Pricing", "bullets": ["$9/mo"]}]})]), Step(calls=[("wait_generation", ids)]),
          done("PPT 做好了，导出时选「可编辑文字」", "Deck ready; export with editable text")],
         ["create_slides", "wait_generation"], 1, {"frame": 3, "text": 7, "image": 1}, extra="slides"),
    Case("13", "over threshold -> Cancel: no charge, no retry",
         [{"zh": "画一张猫", "en": "Draw a cat"}],
         [Step(calls=[("generate_image", {"prompt": "a cat"})]),
          Step(calls=[("generate_image", {"prompt": "a cat, retry"})]),  # the model tries again: the guard refuses
          done("已取消该生成，未扣费。要怎么调整？", "Cancelled this generation; nothing was charged. How should I adjust?")],
         ["generate_image", "generate_image"], 0, {}, decline=True,
         reply={"zh": "已取消", "en": "Cancelled"}, extra="cancel"),
    Case("14", "no key: immediate message, no model call",
         [{"zh": "画一张猫", "en": "Draw a cat"}], [], [], 0, {}, no_key=True, status="error",
         error={"zh": "还没有设置 WaveSpeed Key", "en": "No WaveSpeed key yet"}, llm_requests=0),
    faults("timeout"), faults("429"), faults("500"),
    faults_retry("timeout"), faults_retry("429"), faults_retry("500"),
    # #391: the hard-coded 80-step limit is gone. A long, productive task completes; the 300-step hard cap
    # still stops and announces itself (no silent cap). On main both fail at step 80.
    Case("15-steps120", "#391 a 120-step task completes (no 80 cap)",
         [{"zh": "把这 120 条标语逐条加到画布上", "en": "Add these 120 slogans to the canvas one by one"}],
         [*[Step(calls=[("add_text", {"text": f"slogan {i}"})]) for i in range(120)],
          done("120 条标语都加好了", "All 120 slogans added")],
         ["add_text"] * 120, 0, {"text": 120}, limit=300, llm_requests=121, extra="run_done"),
    Case("15-hardcap", "#391 hard cap 300: stops and says so",
         [{"zh": "把这 400 条标语逐条加到画布上", "en": "Add these 400 slogans to the canvas one by one"}],
         [Step(calls=[("add_text", {"text": f"slogan {i}"})]) for i in range(301)],
         ["add_text"] * 300, 0, {"text": 300}, limit=300, status="error",
         error={"zh": "已自动暂停", "en": "Paused automatically"}, llm_requests=300, extra="hard_cap",
         # the token budget must not end a 300-step run first: this case tests the step cap only
         settings={"agent-token-window-multiple": 200}),
    Case("15-readonly", "#391 read-only steps are not 'no progress' up to 8 in a row, then stuck",
         [{"zh": "检查所有页面", "en": "Check every page"}],
         [Step(calls=[("get_canvas", {"page": f"p{i}"})]) for i in range(40)],
         ["get_canvas"] * 18, 0, {}, limit=40, status="error",
         error={"zh": "任务卡住了（连续只读步骤过多）", "en": "The task is stuck (too many read-only steps in a row)"}, extra="stuck"),
    # #383 goal self-check
    Case("16-sc-pass", "#383 4 images generated, 4 on the canvas -> done, self_check pass",
         [{"zh": "画 4 张柯基插画", "en": "Draw 4 corgi illustrations"}],
         _gen_then_reply("generate_image", {"prompt": "corgi illustration", "count": 4}, "4 张画好了", "4 done"),
         ["generate_image", "wait_generation"], 4, {"image": 4}, extra="sc_pass"),
    Case("17-sc-missing", "#383 4 generated but only 2 still on the canvas -> no done claim, missing 2",
         [{"zh": "画 4 张柯基插画", "en": "Draw 4 corgi illustrations"}],
         [Step(calls=[("generate_image", {"prompt": "corgi illustration", "count": 4})]),
          Step(calls=[("wait_generation", ids)]),
          Step(calls=[("delete_shapes", lambda last: {"ids": [last["results"][0]["shapes"][0],
                                                             last["results"][0]["shapes"][1]]})]),
          done("已完成 4 张", "Done: all 4 images"), done("已完成 4 张", "Done: all 4 images")],
         ["generate_image", "wait_generation", "delete_shapes"], 4, {"image": 2}, status="error",
         error={"zh": "目标核对未通过", "en": "Goal check failed"}, llm_requests=5, extra="sc_missing2"),
    Case("18-sc-allfail", "#383 every generation fails -> the reason, never 'done'",
         [{"zh": "画 4 张柯基插画", "en": "Draw 4 corgi illustrations"}],
         [Step(calls=[("generate_image", {"prompt": "FAIL corgi", "count": 4})]),
          Step(calls=[("wait_generation", ids)]),
          done("已完成", "Done"), done("已完成", "Done")],
         ["generate_image", "wait_generation"], 4, {}, status="error",
         error={"zh": "目标核对未通过", "en": "Goal check failed"}, llm_requests=4, extra="sc_allfail"),
    Case("19-sc-claim", "#383 'done, 4 images' with zero tool calls -> rewritten",
         [{"zh": "画 4 张柯基插画", "en": "Draw 4 corgi illustrations"}],
         [done("已完成 4 张", "Done: 4 images"), done("已完成 4 张", "Done: 4 images")],
         [], 0, {}, status="error",
         error={"zh": "目标核对未通过", "en": "Goal check failed"}, llm_requests=2, extra="sc_claim"),
    Case("20-sc-qa", "#383 pure Q&A -> no self-check",
         [{"zh": "水彩和油画有什么区别？", "en": "What is the difference between watercolor and oil painting?"}],
         [done("水彩透明、油画厚重。", "Watercolor is transparent; oil is opaque.")],
         [], 0, {}, llm_requests=1, extra="sc_skip"),
]
