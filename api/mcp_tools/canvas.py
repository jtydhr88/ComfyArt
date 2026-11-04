import logging

from ..auto_models import UnregisteredModel, choose, load_table, note, registered, skill_pin, tool_feature
from ..mcp_commands import submit_command
from ..wavespeed import compact_models, grouped_models, load_config, model_details
from ._context import BOT_CHAT_ID, PROJECT
from .bot_tools import maybe_ask_run_approval

log = logging.getLogger("comfyart")
WAIT_MAX_S = 170
SLOW_S = 90.0

_ID = {"type": "string", "description": "shape id exactly as get_canvas returns it, e.g. shape:abc"}
_IDS = {"type": "array", "items": {"type": "string"}}
_POINT = {"type": "number"}
_REGION = {"x": _POINT, "y": _POINT, "width": _POINT, "height": _POINT}
_PLACE = {
    "frame": {"type": "string", "description": "frame id to place the result inside"},
    "near": {"type": "string", "description": "shape id to place the result next to"},
}


_MODEL_AUTO = {"type": "string", "description": "Only when the user named a model; otherwise omit it and Auto picks "
               "by task type (the result's model_choice says which and why)."}


def _schema(properties: dict, required: list[str] = ()) -> dict:
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


def _relay(action: str, *, timeout: float = 20.0, approval: str = ""):
    async def handler(args: dict) -> dict:
        args = dict(args)
        fallback_for = str(args.pop("fallback_for", "") or "")
        if approval:
            label = str(args.get("prompt") or args.get("to") or "")[:80]
            blocked = await maybe_ask_run_approval(f"{approval}{'：' + label if label else ''}")
            if blocked is not None:
                return blocked
        try:
            return await _relay_run(action, args, fallback_for, timeout)
        except UnregisteredModel as e:
            # #712: an unregistered table model is an explicit error, never a silent swap to another model
            log.error("%s", e)
            return {"status": "failed", "generation_succeeded": False, "error": str(e), "kind": "unregisteredModel",
                    "user_message": _unregistered_copy()}
    return handler


def _unregistered_copy() -> str:
    """#712: the same zh/en copy as src/locales wsErr.unregisteredModel (the UI shows it for kind=unregisteredModel)."""
    import json as _json
    from pathlib import Path as _P
    loc = _P(__file__).resolve().parents[2] / "src" / "locales"
    return " / ".join(_json.loads((loc / f"{l}.json").read_text(encoding="utf-8"))["wsErr.unregisteredModel"] for l in ("zh", "en"))


async def _relay_run(action: str, args: dict, fallback_for: str, timeout: float) -> dict:
    if fallback_for:
        # #236: switch once, to a different model from the #133 table. Never submit the failed model again.
        choice = _fallback_choice(action, args, fallback_for)
        if not choice or choice["model"] == fallback_for:
            return _same_model_block(fallback_for)
        if "edit_model" in choice:
            args.pop("model", None)
            args.pop("auto_model", None)
            args["edit_model"] = choice["edit_model"]
        else:
            args.pop("edit_model", None)
            args["model"] = choice["model"]
            args["auto_model"] = True
        if (args.get("edit_model") or args.get("model")) == fallback_for:
            return _same_model_block(fallback_for)
    else:
        requested = unregistered_model(action, args)
        if requested:
            # #734: a model id the catalog does not register never errors out or asks the user: drop it and let
            # Auto pick, recording the original value and why on the result (model_choice).
            log.warning("model %r for %s is not registered; falling back to Auto", requested, action)
            args = {k: v for k, v in args.items() if k not in ("model", "auto_model")}
        choice = _auto_choice(action, args)
        if choice and choice.get("category") == "skill_unregistered":
            return _unregistered_block(choice)
        if requested:
            choice = {**(choice or {"model": "", "auto": True, "category": "auto",
                                    "reason": {"zh": "自动选择", "en": "Auto picked it"}}),
                      "requested_model": requested, "fallback_reason": _unregistered_reason(requested)}
        if choice and choice["auto"] and choice["category"] != "references" and "model" not in args and choice["model"] != load_config()["features"][tool_feature(action)]["default"]:
            args = {**args, "model": choice["model"], "auto_model": True} if "edit_model" not in choice else {**args, "edit_model": choice["edit_model"]}
    if choice and choice.get("category") in ("skill", "skill_fallback"):
        args = _pin_args(args, choice)
    args.pop("skill", None)
    result = await submit_command(action, args, PROJECT.get(), timeout, chat=BOT_CHAT_ID.get())
    if choice and isinstance(result, dict) and not result.get("cancelled"):
        ran = result.get("model")
        if choice["auto"] and "edit_model" not in choice and choice["category"] != "references" and ran and ran != choice["model"]:
            log.warning("auto model %s is disabled on the page; %s ran instead", choice["model"], ran)
            if choice.get("category") == "fallback":
                asked, failed = choice["model"], choice.get("fallback") or choice["model"]
                choice = {**choice, "model": ran, "fallback": failed,
                          "reason": {"zh": f"{failed} 调用失败，备用模型 {asked} 已在模型设置里关闭，实际改用 {ran}",
                                     "en": f"{failed} failed, and the fallback {asked} is turned off in model settings, so {ran} ran"}}
            else:
                choice = {**choice, "model": ran, "fallback": choice["model"],
                          "reason": {"zh": f"{choice['reason']['zh']}，但 {choice['model']} 已在模型设置里关闭，改用默认模型",
                                     "en": f"{choice['reason']['en']}, but {choice['model']} is turned off in model settings, so the default model was used"}}
        result["model_choice"] = {**choice, "note": note(choice) if choice.get("model") else choice["fallback_reason"]["en"]}
        if choice.get("requested_model"):
            result["requested_model"] = choice["requested_model"]
            result["model_fallback_reason"] = choice["fallback_reason"]
    image = result.pop("png", None)
    if image:
        result["_images"] = [{"data": image, "mime": "image/png"}]
    return result


async def _wait_generation(args: dict) -> dict:
    timeout = max(1, min(int(args.get("timeout_s") or WAIT_MAX_S), WAIT_MAX_S))
    return await submit_command("wait_generation", {**args, "timeout_s": timeout}, PROJECT.get(), timeout + 15)


def _running_feature(action: str, args: dict) -> str | None:
    """Feature whose model actually runs. Refs and a base image run on image_edit (#133)."""
    if action == "generate_image" and (args.get("refs") or args.get("base")):
        return "image_edit"
    return tool_feature(action)


def _fallback_choice(action: str, args: dict, failed: str) -> dict | None:
    """#236: one backup from the #133 table, never the model that just failed.

    The table's model for this task is the backup when it is a different model.
    When that model is the one that failed, the backup is the feature default
    (the table's 通用 row, and the same stand-in #133 uses when a table model
    cannot run). None when both are the model that failed: do not submit it again.
    """
    failed = str(failed or "")
    feature = _running_feature(action, args)
    if not feature or not failed:
        return None
    clean = {k: v for k, v in args.items() if k not in ("model", "edit_model", "auto_model", "fallback_for")}
    pin = _skill_row(action, clean)
    if pin:
        return _skill_fallback(clean, pin, failed)
    primary = _auto_choice(action, clean)
    if not primary:
        return None
    cfg = load_config()["features"][feature]
    ids = {m["id"] for m in cfg["models"]}
    default = cfg["default"]
    table_model = primary["model"]
    if table_model in ids and table_model != failed:
        target = table_model
        why = {"zh": f"{failed} 调用失败，按对应表改用备用模型：{primary['reason']['zh']}",
               "en": f"{failed} failed, so the table's fallback was used: {primary['reason']['en']}"}
    elif default in ids and default != failed:
        target = default
        why = {"zh": f"{failed} 调用失败，按对应表改用默认备用模型",
               "en": f"{failed} failed, so the table's default fallback model was used"}
    else:
        return None
    choice = {"model": target, "auto": True, "category": "fallback", "fallback": failed, "reason": why}
    if action == "generate_image" and (clean.get("refs") or clean.get("base")):
        choice["edit_model"] = target
    return choice


def _same_model_block(model: str) -> dict:
    """#236: a paid submit is never repeated on the model that just failed."""
    log.warning("refusing to submit %s again after it failed", model)
    return {"status": "failed", "model": model, "same_model_retry": False,
            "error": f"the same model was not submitted again: {model}",
            "note": f"没有用 {model} 再次提交。/ Did not submit {model} again."}



def _skill_row(action: str, args: dict) -> dict | None:
    """#708: the skill's pinned row when this call runs on that row's feature and names no model."""
    pin = skill_pin(args.get("skill"))
    if not pin or args.get("model") or _running_feature(action, args) != pin.get("feature"):
        return None
    return pin


def _edit_ids() -> set:
    return {m["id"] for m in load_config()["features"]["image_edit"]["models"]}


def _skill_choice(args: dict, pin: dict) -> dict:
    skill = str(args.get("skill"))
    if pin["model"] not in _edit_ids():
        # #712: never a silent switch to the feature default
        log.error("skill %s pins %s, which is not in the catalog; not submitting", skill, pin["model"])
        return {"model": pin["model"], "auto": True, "category": "skill_unregistered", "skill": skill,
                "reason": {"zh": f"{skill} 固定的模型 {pin['model']} 不在模型列表里", "en": f"{pin['model']} pinned by {skill} is not in the model catalog"}}
    return {"model": pin["model"], "auto": True, "category": "skill", "skill": skill, "edit_model": pin["model"],
            "resolution": pin.get("resolution"), "ratio": pin.get("ratio"), "reason": {"zh": pin["zh"], "en": pin["en"]}}


def _skill_fallback(args: dict, pin: dict, failed: str) -> dict | None:
    """#708: the pinned fallback runs only after the pinned model failed; anything else is not switched."""
    skill = str(args.get("skill"))
    fb = pin.get("fallback")
    if failed != pin["model"] or not fb or fb == failed:
        return None
    if fb not in _edit_ids():
        log.error("skill %s fallback %s is not in the catalog; not submitting", skill, fb)
        return None
    log.warning("skill %s: %s failed; falling back to %s", skill, failed, fb)
    return {"model": fb, "auto": True, "category": "skill_fallback", "skill": skill, "fallback": failed, "edit_model": fb,
            "resolution": pin.get("resolution"), "ratio": pin.get("ratio"),
            "reason": {"zh": f"{failed} 调用失败，按 {skill} 的登记改用备用模型 {fb}",
                       "en": f"{failed} failed, so {skill}'s registered fallback {fb} was used"}}


def _pin_args(args: dict, choice: dict) -> dict:
    args = {k: v for k, v in args.items() if k not in ("model", "auto_model")}
    args["edit_model"] = choice["edit_model"]
    if choice.get("resolution"):
        args["edit_resolution"] = choice["resolution"]
    if choice.get("ratio") and not args.get("ratio"):
        args["ratio"] = choice["ratio"]
    return args


def _unregistered_block(choice: dict) -> dict:
    return {"status": "failed", "model": choice["model"], "error": choice["reason"]["en"],
            "note": f"没有提交：{choice['reason']['zh']}。/ Not submitted: {choice['reason']['en']}."}


def registered_ids(action: str) -> set[str]:
    """#734: model ids the catalog registers for this tool's feature (empty when the tool has no model feature)."""
    feature = tool_feature(action)
    if not feature:
        return set()
    feats = load_config()["features"]
    return {m["id"] for m in (feats.get(feature) or {}).get("models") or []}


def unregistered_model(action: str, args: dict) -> str:
    """#734: the agent-passed model when the catalog does not register it for this tool, else ''."""
    model = str(args.get("model") or "")
    if not model or not tool_feature(action):
        return ""
    return "" if model in registered_ids(action) else model


def _unregistered_reason(model: str) -> dict:
    return {"zh": f"{model} 不是已注册的模型，已改用自动选择",
            "en": f"{model} is not a registered model, so Auto picked the model instead"}


def _auto_choice(action: str, args: dict) -> dict | None:
    """#133: which model runs and why (user-named wins, else the Auto table). #708: a skill pin wins over Auto."""
    feature = tool_feature(action)
    if not feature:
        return None
    pin = _skill_row(action, args)
    if pin:
        return _skill_choice(args, pin)
    cfg = load_config()
    if action == "generate_image" and (args.get("refs") or args.get("base")):
        # refs/base run on image_edit (src/generate.ts). Auto (#133 ruling): 2+ refs -> the multi-reference row,
        # else the edit default. A user-named (text-to-image) model keeps the page's edit default as before.
        refs = len(args.get("refs") or [])
        if not args.get("model") and refs >= 2:
            multi = load_table()["image_edit"]["multi_reference"]
            ids = {m["id"] for m in cfg["features"]["image_edit"]["models"]}
            model, failed = registered(multi, ids, "image_edit/multi_reference")  # #712: no silent fallback
            out = {"model": model, "auto": True, "category": "multi_reference", "edit_model": model,
                   "reason": {"zh": multi["zh"].format(n=refs), "en": multi["en"].format(n=refs)}}
            return {**out, "fallback": failed} if failed else out
        if args.get("model"):
            reason = {"zh": f"你指定了 {args['model']}，但带参考图时走图片编辑，用的是它的默认模型",
                      "en": f"you named {args['model']}, but references run on image editing, which uses its default model"}
        else:
            reason = {"zh": "只有 1 张参考图（或底图），用图片编辑的默认模型就够了",
                      "en": "there is one reference (or base) image, which the image-edit default model handles"}
        return {"model": cfg["features"]["image_edit"]["default"], "auto": not args.get("model"), "category": "references", "reason": reason}
    masked = action in (load_table()[feature].get("masked") or {}).get("tools", [])
    return choose(feature, str(args.get("prompt") or ""), str(args.get("model") or "") or None, cfg, masked=masked)


def _tool(description: str, properties: dict, required: list[str] = (), **relay) -> dict:
    return {"description": description, "inputSchema": _schema(properties, required), "relay": relay}


SPECS: dict[str, dict] = {
    "get_canvas": _tool(
        "List the open project: pages, the current page's frames and shapes (id, type, name or text, "
        "x/y/width/height, parent, image or video URL and its pixel size, generation prompt, the text of "
        "imported PDF pages), the selection, the linked "
        "brand kit and running generations. page selects another page by id or name.",
        {"page": {"type": "string"}}),
    "view_canvas": _tool(
        "Render real pixels of the current page (default), of some shapes or frames (ids), so you can "
        "see layout and results. max_px caps the long side (default 1024).",
        {"ids": _IDS, "max_px": {"type": "integer"}}, timeout=SLOW_S),
    "list_models": _tool(
        "WaveSpeed cloud models grouped by feature (text_to_image, image_edit, upscale_image, ...): id, "
        "starting price in USD per run and a one-line description. Pass an id as model to the matching tool, "
        "or omit model to use the default. type: image, image_tools, video, video_tools, audio, 3d, a "
        "feature name or a tool name (e.g. animate_image) for that group's recommended models (without type only an index). all=true with "
        "page (1..pages) lists every model. model_id: one model's params (accepted ratios, durations, "
        "resolutions, max reference images) and quality tiers; call it before using a non-default model so "
        "its params are valid. Extra reference images beyond its max are dropped, not charged.",
        {"type": {"type": "string"}, "all": {"type": "boolean"}, "page": {"type": "integer"},
         "model_id": {"type": "string"}}),
    "brand_kits": _tool(
        "The user's brand kits and saved assets (characters, products): names, descriptions, colors "
        "with roles, fonts, logo and reference image URLs, and which kit this project is linked to.", {}),
    "generate_image": _tool(
        "Start generating images on the canvas. Returns ids at once; call wait_generation with them. "
        "prompt: detailed English description (put exact text to render in quotes). ratio like 1:1, "
        "3:4, 16:9. count 1-4. refs: image shape ids or image URLs the result must follow (subject, "
        "product, style); naming a reference in the prompt does not send it, only refs do. ref_modes: one mode per ref, same order, saying how to use it: content, style, "
        "composition, or a structure guide canny, lineart, depth, normal, pose, mlsd, scribble, softedge, seg, "
        "tile (structure guides also work on models with control instead of refs, e.g. Qwen Image 2512). "
        "base: an image shape id to transform (image-to-image) with base_strength 0-100 (higher changes more). "
        "skill: the id of the skill you are running (e.g. pose-fission); a skill with a registered model runs on it.",
        {"prompt": {"type": "string"}, "model": _MODEL_AUTO, "ratio": {"type": "string"},
         "count": {"type": "integer"}, "refs": _IDS, "ref_modes": {"type": "array", "items": {"type": "string"}}, "base": {"type": "string"},
         "base_strength": {"type": "integer"}, "skill": {"type": "string"}, **_PLACE},
        ["prompt"], approval="生成图像"),
    "generate_video": _tool(
        "Start generating a video. Returns ids at once; call wait_generation with them. first_frame / "
        "last_frame are image shape ids. References make a video that follows characters, products, scenes, "
        "motion or sound instead of starting from a frame: reference_images (up to 9 image shape ids, "
        "<Picture 1>…), reference_videos (up to 3 video shape ids, <Video 1>…), reference_audios (up to 3 "
        "audio shape ids, <Audio 1>…). With references, first say what each one is and what it does "
        "(\"Use <Picture 1> as the product, <Video 1> for the camera move, <Audio 1> as the voice\"), then "
        "describe the shot; a tag only mentioned in passing is ignored. motion_video (a video shape id) "
        "makes the person in first_frame copy that video's body motion. speech_audio (an audio shape id) "
        "makes the person in first_frame say that audio with matching lip movement; the video lasts as long "
        "as the audio. duration in seconds (5, 10 or 15); pass what the user asked for: it is rounded up to the "
        "model's next allowed length (capped at its longest) and a duration_note in the result must be told "
        "to the user.",
        {"prompt": {"type": "string"}, "model": {"type": "string"}, "ratio": {"type": "string"},
         "duration": {"type": "integer"}, "first_frame": {"type": "string"}, "last_frame": {"type": "string"},
         "reference_images": _IDS, "reference_videos": _IDS, "reference_audios": _IDS,
         "motion_video": {"type": "string"}, "speech_audio": {"type": "string"}, **_PLACE},
        ["prompt"], approval="生成视频"),
    "edit_image": _tool(
        "Edit an image shape with an instruction (change, add or remove things, restyle). The result is "
        "placed next to it. Returns ids for wait_generation.",
        {"id": _ID, "prompt": {"type": "string"}}, ["id", "prompt"], approval="编辑图片"),
    "animate_image": _tool(
        "Turn an image shape into an animated image (a looping WebP of a few seconds, motion described by "
        "prompt), placed as an image. loop makes the last frame match the first. For a real video use "
        "generate_video with first_frame. Returns ids for wait_generation.",
        {"id": _ID, "prompt": {"type": "string"}, "loop": {"type": "boolean"}}, ["id", "prompt"],
        approval="动态图片"),
    "upscale_image": _tool(
        "Upscale an image shape by factor 2 or 4. creative=true re-renders details (style optional).",
        {"id": _ID, "factor": {"type": "integer", "enum": [2, 4]}, "creative": {"type": "boolean"},
         "style": {"type": "string"}}, ["id"], approval="放大"),
    "remove_background": _tool(
        "Cut the main subject out of an image shape onto a transparent background.",
        {"id": _ID}, ["id"], approval="去背景"),
    "expand_image": _tool(
        "Outpaint an image shape: extend it by left/top/right/bottom pixels, filling the new area "
        "(prompt optional).",
        {"id": _ID, "left": _POINT, "top": _POINT, "right": _POINT, "bottom": _POINT, "prompt": {"type": "string"}},
        ["id"], approval="扩图"),
    "split_layers": _tool(
        "Split an image shape into separate transparent layers (layers: how many, default 4).",
        {"id": _ID, "layers": {"type": "integer"}, "prompt": {"type": "string"}}, ["id"], approval="图层拆分"),
    "change_angle": _tool(
        "Re-render an image shape from another camera angle. horizontal is sent as 0..359 "
        "(0 front, 90 right, 270 left, 180 back). Negative degrees wrap into that range, so -90 is sent as 270. "
        "vertical -30..60 (clamped), zoom 0..10 (7 or more is close-up, 3 up to 7 is medium, below 3 is wide).",
        {"id": _ID, "horizontal": _POINT, "vertical": _POINT, "zoom": _POINT}, ["id"], approval="多角度"),
    "replace_text": _tool(
        "Replace text rendered inside an image shape: from is the current text, to the new text.",
        {"id": _ID, "from": {"type": "string"}, "to": {"type": "string"}}, ["id", "from", "to"],
        approval="编辑文字"),
    "edit_region": _tool(
        "Repaint only a region of an image shape following prompt; the rest stays untouched. x/y/width/"
        "height are in the image's own pixels (get_canvas pixels gives its size; comments sent by the "
        "user carry a ready region).",
        {"id": _ID, **_REGION, "prompt": {"type": "string"}, "model": _MODEL_AUTO}, ["id", "x", "y", "width", "height", "prompt"],
        approval="局部重绘"),
    "erase_region": _tool(
        "Remove whatever is inside a region of an image shape and fill it with the surrounding "
        "background. Region in the image's own pixels.",
        {"id": _ID, **_REGION}, ["id", "x", "y", "width", "height"], approval="擦除"),
    "move_object": _tool(
        "Move one object inside an image shape by dx/dy image pixels; the old spot is filled with "
        "background. Pick the object by object (a short English name like 'apple') or by x/y (a point "
        "on it, in the image's own pixels).",
        {"id": _ID, "object": {"type": "string"}, "x": _POINT, "y": _POINT, "dx": _POINT, "dy": _POINT},
        ["id", "dx", "dy"],
        approval="移动对象"),
    "style_transfer": _tool(
        "Redraw an image shape in another style: style describes it in words, ref is an optional image "
        "shape id or URL whose style to copy.",
        {"id": _ID, "style": {"type": "string"}, "ref": {"type": "string"}}, ["id"], approval="风格迁移"),
    "vectorize_image": _tool(
        "Trace an image shape into an SVG vector image placed next to it (best for logos, icons, flat "
        "art). Returns the new shape id at once.",
        {"id": _ID}, ["id"], timeout=SLOW_S),
    "upscale_video": _tool(
        "Upscale a video shape to target 1080p, 2K or 4K (long side).",
        {"id": _ID, "target": {"type": "string", "enum": ["1080p", "2K", "4K"]}}, ["id"], approval="视频放大"),
    "remove_video_background": _tool(
        "Cut the main subject out of a video shape onto a black background.",
        {"id": _ID}, ["id"], approval="视频去背景"),
    "extend_video": _tool(
        "Continue a video shape by duration seconds following prompt.",
        {"id": _ID, "prompt": {"type": "string"}, "duration": {"type": "integer"}}, ["id", "prompt"],
        approval="视频延长"),
    "edit_video": _tool(
        "Cut several video shapes into one new video, like a video editor: clips play in order, each "
        "{id, start, end} in seconds of its own source video (speed and volume optional). transitions[i] "
        "is the cut between clip i and i+1: {type: none|fade|black|white, duration}; default a hard cut. "
        "music: {id of an audio element, start (seconds into the song), volume} plays from the first frame "
        "under the clips. captions: [{text, start, end}] in seconds of the result. The output keeps the first "
        "clip's size, 24 fps. Returns ids for wait_generation.",
        {"clips": {"type": "array", "items": {"type": "object"}}, "transitions": {"type": "array", "items": {"type": "object"}},
         "music": {"type": "object"}, "captions": {"type": "array", "items": {"type": "object"}}},
        ["clips"], approval="剪辑视频"),
    "generate_music": _tool(
        "Generate a piece of music as an audio element on the canvas. model: a music model id from list_models "
        "(default the first). prompt: English description of genre, mood, instruments, tempo and vocal type. "
        "lyrics optional (use [intro]/[verse]/[chorus]/[outro] lines; omit for an instrumental). duration in "
        "seconds (default 30), clamped to the model's duration range; YuE2 and MiniMax Music 3 have no duration and ignore it (length follows the lyrics). bpm, language (e.g. en, ko, zh, ja) and key (e.g. F minor) are used by ACE-Step; "
        "MiniMax Music 3 and YuE2 read them from the prompt. Returns ids for wait_generation.",
        {"prompt": {"type": "string"}, "lyrics": {"type": "string"}, "duration": {"type": "integer"}, "model": {"type": "string"},
         "bpm": {"type": "integer"}, "language": {"type": "string"}, "key": {"type": "string"}, "seed": {"type": "integer"}},
        ["prompt"], approval="生成配乐"),
    "generate_sound_effect": _tool(
        "Generate a short sound effect (an audio element) from an English description. duration in "
        "seconds (default 8; Stable Audio is trained on clips up to 47 s). Returns ids for wait_generation.",
        {"prompt": {"type": "string"}, "duration": {"type": "integer"}}, ["prompt"], approval="生成音效"),
    "text_to_speech": _tool(
        "Read text aloud as an audio element. voice is a built-in voice id (zf_/zm_ Chinese female/male, "
        "af_/am_ American, bf_/bm_ British, jf_/jm_ Japanese; default zf_xiaoxiao; or the Qwen3-TTS speakers "
        "Serena, Vivian, Uncle_fu, Dylan, Eric, Ryan, Aiden, Ono_anna, Sohee; default Serena), or pass reference "
        "(an audio shape id) to clone that recording's voice. Returns ids for wait_generation.",
        {"text": {"type": "string"}, "voice": {"type": "string"}, "reference": _ID}, ["text"], approval="生成配音"),
    "edit_elements": _tool(
        "Turn the text inside an image shape into editable text: OCR finds each line, the text is erased "
        "from the picture, and a new artboard holds the clean background plus one editable text shape "
        "per line (same position, size, color). Then change the texts with update_shapes. Returns ids "
        "for wait_generation; the returned shape is the background image inside the new artboard.",
        {"id": _ID}, ["id"], approval="编辑元素"),
    "create_mockup": _tool(
        "Turn a product photo (image shape) into a mockup: its surface (depth, outline, shading) is "
        "analysed so a design can be printed onto it. Returns ids for wait_generation; the placed shape "
        "is the mockup. Then call place_design.",
        {"id": _ID}, ["id"], approval="制作样机"),
    "place_design": _tool(
        "Print a design onto a mockup shape. design: an image shape id or URL. x/y: design center as "
        "0-1 of the mockup width/height; scale: design width as a fraction of the mockup width; "
        "rotation in degrees; warp 0-1 (how much the design follows the surface). bake=true also "
        "places the result as a normal image and returns its id.",
        {"id": _ID, "design": {"type": "string"}, "x": _POINT, "y": _POINT, "scale": _POINT,
         "rotation": _POINT, "warp": _POINT, "bake": {"type": "boolean"}},
        ["id"], timeout=SLOW_S),
    "image_to_3d": _tool(
        "Turn an image shape (best: one object on a plain background) into a textured 3D model placed next "
        "to it. Takes a few minutes. Returns ids for wait_generation. Runs on WaveSpeed "
        "(default: first image_to_3d id from list_models). model: trellis2 (default), pixal3d, custom "
        "(the user's assigned model3d workflow), or a WaveSpeed image_to_3d id. views: 1-4 image shape ids of the same object as front, "
        "left, back and right, in that order; when given, tripo3d/h3.1/multiview-to-3d builds one model from "
        "all of them and id is ignored.",
        {"id": _ID, "model": {"type": "string", "description": "trellis2, pixal3d, custom (assigned model3d workflow), or a WaveSpeed image_to_3d id from list_models; omit for the default. Multiple views use tripo3d/h3.1/multiview-to-3d"}, "views": _IDS}, approval="转 3D"),
    "place_html": _tool(
        "Place a web page on the canvas: html is one complete self-contained HTML document you wrote "
        "(inline CSS/JS, images by absolute URL). width/height in canvas units.",
        {"html": {"type": "string"}, "name": {"type": "string"}, "x": _POINT, "y": _POINT,
         "width": _POINT, "height": _POINT},
        ["html"]),
    "create_slides": _tool(
        "Build a slide deck as 1280x720 frames with editable title and bullet text; slides with image "
        "get a generated picture (image is an English image prompt). Returns frame ids and generation ids.",
        {"title": {"type": "string"},
         "slides": {"type": "array", "items": _schema({"title": {"type": "string"},
                                                       "bullets": {"type": "array", "items": {"type": "string"}},
                                                       "image": {"type": "string"}}, ["title"])}},
        ["slides"], approval="制作 PPT"),
    "add_text": _tool(
        "Add an editable text shape. font_size in px, color as hex, font family name (brand fonts work), "
        "width wraps the text. x/y are page coordinates, or relative to frame when frame is given.",
        {"text": {"type": "string"}, "x": _POINT, "y": _POINT, "width": _POINT, "font_size": _POINT,
         "color": {"type": "string"}, "font": {"type": "string"},
         "align": {"type": "string", "enum": ["left", "center", "right"]}, "frame": _PLACE["frame"]},
        ["text"]),
    "add_shape": _tool(
        "Add a vector shape: kind rect, ellipse, polygon (sides) or star (sides = points). fill and "
        "stroke as hex. x/y are page coordinates, or relative to frame when frame is given.",
        {"kind": {"type": "string", "enum": ["rect", "ellipse", "polygon", "star"]}, "x": _POINT, "y": _POINT,
         "width": _POINT, "height": _POINT, "sides": {"type": "integer"}, "fill": {"type": "string"},
         "stroke": {"type": "string"}, "frame": _PLACE["frame"]},
        ["kind"]),
    "create_frame": _tool(
        "Create an artboard frame (name, width, height). children: shape ids to move inside it.",
        {"name": {"type": "string"}, "width": _POINT, "height": _POINT, "x": _POINT, "y": _POINT,
         "children": _IDS},
        ["width", "height"]),
    "update_shapes": _tool(
        "Change shapes: each update has id plus any of x, y (page coordinates), width, height, rotation "
        "(degrees), name (frames), text (text shapes), color (hex; text color or shape fill), opacity "
        "(0-1), frame (move into a frame id, or '' for the page).",
        {"updates": {"type": "array", "items": _schema({
            "id": _ID, "x": _POINT, "y": _POINT, "width": _POINT, "height": _POINT, "rotation": _POINT,
            "name": {"type": "string"}, "text": {"type": "string"}, "color": {"type": "string"},
            "opacity": _POINT, "frame": {"type": "string"}}, ["id"])}},
        ["updates"]),
    "delete_shapes": _tool("Delete shapes by id.", {"ids": _IDS}, ["ids"]),
    "focus": _tool(
        "Show shapes to the user: switch page if needed, select them and zoom to them.",
        {"ids": _IDS}, ["ids"]),
    "memory": _tool(
        "The user's long-term memory across projects. action list; add with text and category (about, "
        "taste, work, assets); correct with old (copied exactly) and new; forget with text (copied "
        "exactly). When the user states a preference, brand, requirement, or makes a choice, call add FIRST, then reply "
        "(think again after add, then answer). Do not rely on a later fallback to save it. Save only what the user told us: preferences, brands, requirements and facts they stated, and conclusions the user confirmed or chose in this turn (e.g. picked palette 2, always 16:9). Never save your own guesses, plans the user has not confirmed, generated content itself, or one-off task details. Every memory must trace back to one user sentence or choice.",
        {"action": {"type": "string", "enum": ["list", "add", "correct", "forget"]},
         "text": {"type": "string"}, "category": {"type": "string"},
         "old": {"type": "string"}, "new": {"type": "string"}},
        ["action"]),
    "skill": _tool(
        "Installed skills (instruction packs). action list (returns id, name and description); read with id or name "
        "(and optional path for a bundled file); save with name and instructions to store a reusable workflow the "
        "user wants to keep, plus an optional one-line description. To edit an existing skill, save with its id "
        "(several skills can share a name); instructions and description you leave out are kept. "
        "When a task matches a skill, read it first and follow it.",
        {"action": {"type": "string", "enum": ["list", "read", "save"]}, "id": {"type": "string"}, "name": {"type": "string"},
         "path": {"type": "string"}, "instructions": {"type": "string"}, "description": {"type": "string"}},
        ["action"]),
    "custom_workflow": _tool(
        "Connect the user's own WaveSpeed model to a ComfyArt feature (image generation, edit, inpaint, "
        "upscale, video, music...). action rules: how to describe the model, read it first. list: each feature's "
        "markers, its saved files and the one in use. check: validate workflow ({model, fields, params} "
        "object) or file for a feature and report what to fix. install: save workflow as name for "
        "feature and use it (refused while check has errors). assign: give feature one of its files, or "
        "file \"\" to switch back to built in. There is no delete; the user removes files on disk.",
        {"action": {"type": "string", "enum": ["rules", "list", "check", "install", "assign"]},
         "feature": {"type": "string"}, "workflow": {"type": "object"}, "file": {"type": "string"},
         "name": {"type": "string"}},
        ["action"]),
}

_MODEL = {"type": "string", "description": "WaveSpeed model id from list_models for this tool's feature; only when the user named a model, "
          "otherwise omit it (Auto). "
          "Before using a non-default model, call list_models(model_id=...) for its accepted params"}
for _name in load_config()["tool_features"]:
    if _name in SPECS:
        SPECS[_name]["inputSchema"]["properties"].setdefault("model", _MODEL)


async def _list_models(args: dict) -> dict:
    grouped = await grouped_models()
    if args.get("model_id"):
        return {"model": model_details(grouped, str(args["model_id"]).strip())}
    kind = str(args.get("type") or "").strip().lower() or None
    tool_features = load_config()["tool_features"]
    try:
        page = int(args.get("page") or 1)
    except (TypeError, ValueError):
        page = 1
    res = compact_models(grouped, kind, tool_features, bool(args.get("all")) and bool(kind), page)
    # kind results already carry features + footer (paged ones also page/pages); no-kind stays wrapped
    out = res if "features" in res else {"features": res}
    if not kind:
        out["tool_features"] = tool_features
    return out


TOOLS: dict[str, dict] = {
    name: {"description": spec["description"], "inputSchema": spec["inputSchema"],
           "handler": _relay(name, **spec["relay"])}
    for name, spec in SPECS.items()
}
TOOLS["list_models"]["handler"] = _list_models
TOOLS["wait_generation"] = {
    "description": (
        "Wait for generations started by generate_image, generate_video and the edit tools. ids are the "
        "ids those tools returned. Returns status done with the placed shape ids and URLs of each "
        "result (or its error), or status running when timeout_s (max 170) passed first — then call "
        "it again."),
    "inputSchema": _schema({"ids": _IDS, "timeout_s": {"type": "integer"}}, ["ids"]),
    "handler": _wait_generation,
}
