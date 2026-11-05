import asyncio
from typing import Optional

from . import chat_store
from .bot_docs import DOC_ERRORS, document_line, read_document
from .bot_media import ATTACH_MAX_COUNT, MEDIA_ERRORS, SHEET_FRAMES, render_attachment
from .bot_turns import ACTIVE_TURNS, QUEUED, begin_turn, broadcast


def _strings(raw, name: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        raise ValueError(f"{name} must be an array of strings")
    return raw


def parse_refs(raw) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("refs must be an array")
    refs = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or not isinstance(item.get("src"), str):
            raise ValueError(f"refs[{i}] needs src")
        refs.append({"id": str(item.get("id") or ""), "src": item["src"], "name": str(item.get("name") or ""),
                     "kind": item.get("kind") if item.get("kind") in ("video", "audio") else "image",
                     "transcript": str(item.get("transcript") or "")})
    return refs


def parse_docs(raw) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("docs must be an array")
    docs = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or not isinstance(item.get("src"), str):
            raise ValueError(f"docs[{i}] needs src")
        docs.append({"src": item["src"], "name": str(item.get("name") or "document")})
    return docs


def parse_kits(raw) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("kits must be an array")
    kits = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError(f"kits[{i}] needs name")
        kits.append({"name": item["name"], "description": str(item.get("description") or ""),
                     "images": _strings(item.get("images"), f"kits[{i}].images")})
    return kits


def visual_refs(refs: list[dict]) -> list[dict]:
    return [r for r in refs if r["kind"] != "audio"]


async def prepare_attachments(refs: list[dict], kits: list[dict], docs: list[dict] = (),
                              page_images: bool = True) -> tuple[list[dict], list[str]]:
    attachments = []
    for r in visual_refs(refs)[:ATTACH_MAX_COUNT]:
        try:
            attachments.append(await asyncio.to_thread(render_attachment, r["src"]))
        except MEDIA_ERRORS as e:
            raise ValueError(f"could not read {r['src']} ({e})") from e
    doc_lines = []
    for d in docs:
        try:
            text, pages, images = await asyncio.to_thread(read_document, d["src"])
        except DOC_ERRORS as e:
            doc_lines.append(f"[Attached document {d['name']}: {d['src']} — could not read its text ({e})]")
            continue
        images = images[:max(0, ATTACH_MAX_COUNT - len(attachments))] if page_images else []
        attachments += images
        doc_lines.append(document_line(d["name"], d["src"], text, pages, len(images)))
    skipped = []
    for src in [src for k in kits for src in k["images"]][:max(0, ATTACH_MAX_COUNT - len(attachments))]:
        try:
            attachments.append(await asyncio.to_thread(render_attachment, src))
        except MEDIA_ERRORS:
            skipped.append(src)
    lines = []
    for i, r in enumerate(refs):
        label = f' "{r["name"]}"' if r["name"] else ""
        target = f"shape id {r['id']}" if r["id"] else "not on the canvas"
        if r["kind"] == "audio":
            heard = f' Transcript: "{r["transcript"]}"' if r["transcript"] else " No speech was recognised in it."
            lines.append(f"[Attached audio {i + 1}{label}: {target} — {r['src']}. Use the shape id as reference_audios, speech_audio or a voice reference.{heard}]")
            continue
        frames = f" Its picture shows {SHEET_FRAMES} frames across the video; call view_video for more." if r["kind"] == "video" else ""
        lines.append(f"[Attached {r['kind']} {i + 1}{label}: {target} — {r['src']}. Use the shape id with edit tools or as a generation ref.{frames}]")
    lines += doc_lines
    for k in kits:
        lines.append(f"[Referenced asset: {k['description'] or k['name']}. Its {len(k['images'])} image(s) are attached after the canvas images; pass their URLs as refs to follow them.]"
                     + "".join(f"\n  - {src}" for src in k["images"]))
    if len(visual_refs(refs)) + sum(len(k["images"]) for k in kits) > ATTACH_MAX_COUNT:
        lines.append(f"[Only the first {ATTACH_MAX_COUNT} images are attached; look at the rest with view_canvas.]")
    if skipped:
        lines.append(f"[These asset images could not be attached: {', '.join(skipped)}]")
    return attachments, lines


def compose_provider_text(text: str, *, skill_name: str = "", memory: str = "",
                          lines: list[str] = ()) -> str:
    provider_text = text or "Look at the attached images and tell me what you see."
    if skill_name:
        provider_text = (
            f"Use the ComfyArt skill {skill_name!r} for this task: first call "
            f"the comfyart MCP tool skill with action='read' and "
            f"name={skill_name!r}, then follow those instructions.\n\n"
            + provider_text)
    if lines:
        provider_text += "\n\n" + "\n".join(lines)
    if memory:
        provider_text = memory + "\n\n" + provider_text
    return provider_text


def queue_or_begin(chat: dict, *, text: str, provider_text: str,
                   attachments: list[dict], display_blocks: list[dict]) -> tuple[dict, Optional[dict]]:
    if chat["id"] in ACTIVE_TURNS:
        user_msg = chat_store.create_message(chat_id=chat["id"], role="user", blocks=display_blocks, status="queued")
        QUEUED.setdefault(chat["id"], []).append({
            "user_msg": user_msg,
            "text": text,
            "provider_text": provider_text,
            "attachments": attachments,
        })
        broadcast("message_queued", {"chat_id": chat["id"], "user_message": user_msg})
        return user_msg, None
    user_msg = chat_store.create_message(chat_id=chat["id"], role="user", blocks=display_blocks)
    assistant_msg = begin_turn(chat, text=text, provider_text=provider_text,
                               attachments=attachments, user_msg=user_msg)
    return user_msg, assistant_msg
