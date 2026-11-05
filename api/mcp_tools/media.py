import asyncio

from .._common import view_path
from ...bot.media_sheet import contact_sheet, jpeg, video_frames

MAX_FRAMES = 16
SHEET_PX = 1536


async def _view_video(args: dict) -> dict:
    path = view_path(str(args.get("url") or ""))
    count = max(2, min(int(args.get("frames") or 8), MAX_FRAMES))
    start = float(args.get("start") or 0)
    end = float(args["end"]) if args.get("end") is not None else None
    frames, duration = await asyncio.to_thread(video_frames, path, count, start, end)
    sheet = await asyncio.to_thread(lambda: jpeg(contact_sheet(frames, SHEET_PX), SHEET_PX))
    return {"duration_s": round(duration, 2), "frames_at_s": [round(at, 2) for at, _ in frames],
            "_images": [{"data": sheet["data"], "mime": sheet["media_type"]}]}


TOOLS: dict[str, dict] = {
    "view_video": {
        "description": (
            "Look inside a video: returns one image with frames evenly spaced between start and end "
            "seconds (whole video by default), each labelled with its time, plus the duration. url is "
            "the video URL from get_canvas or an attached video. frames 2-16 (default 8); narrow "
            "start/end to study one moment closely."),
        "inputSchema": {"type": "object", "properties": {
            "url": {"type": "string"}, "frames": {"type": "integer"},
            "start": {"type": "number"}, "end": {"type": "number"}},
            "required": ["url"], "additionalProperties": False},
        "handler": _view_video,
    },
}
