import av
from PIL import Image

from ..bot.media_sheet import contact_sheet, jpeg, video_frames
from ._common import view_path

ATTACH_MAX_PX = 1024
ATTACH_MAX_COUNT = 12
SHEET_FRAMES = 4
VIDEO_EXT = (".mp4", ".webm", ".mov", ".mkv")
MEDIA_ERRORS = (ValueError, OSError, av.FFmpegError)


def render_attachment(url: str) -> dict:
    path = view_path(url)
    if path.lower().endswith(VIDEO_EXT):
        return jpeg(contact_sheet(video_frames(path, SHEET_FRAMES)[0], ATTACH_MAX_PX), ATTACH_MAX_PX)
    with Image.open(path) as im:
        return jpeg(im, ATTACH_MAX_PX)
