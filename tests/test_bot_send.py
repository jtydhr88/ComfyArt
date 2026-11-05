from __future__ import annotations

import zipfile

import av
import pytest
from PIL import Image

from ComfyArt.api import bot_send
from ComfyArt.api.bot_media import video_frames, view_path


def _image(base, name="a.png"):
    folder = base / "output" / "comfyart"
    folder.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (2048, 1024), (200, 10, 10)).save(folder / name)
    return f"/api/view?filename={name}&subfolder=comfyart&type=output"


def test_parse_refs_and_kits_validate_shapes():
    assert bot_send.parse_refs([{"src": "/v", "id": "shape:a"}])[0]["kind"] == "image"
    with pytest.raises(ValueError):
        bot_send.parse_refs([{"id": "shape:a"}])
    with pytest.raises(ValueError):
        bot_send.parse_kits([{"name": "k", "images": [1]}])


def test_view_path_stays_inside_the_folder(fresh_user_dir):
    _image(fresh_user_dir)
    with pytest.raises(ValueError):
        view_path("/api/view?filename=../../secret.txt&type=output")
    with pytest.raises(ValueError):
        view_path("/api/view?filename=a.png&type=models")


async def test_attachments_are_downscaled_and_bad_kit_images_skipped(fresh_user_dir):
    src = _image(fresh_user_dir)
    refs = bot_send.parse_refs([{"src": src, "id": "shape:a", "name": "poster-differentiated-compiler"}])
    kits = bot_send.parse_kits([{"name": "Brand", "description": "Brand kit", "images": [src, "/api/view?filename=missing.png&type=output"]}])
    attachments, lines = await bot_send.prepare_attachments(refs, kits)
    assert len(attachments) == 2 and attachments[0]["media_type"] == "image/jpeg"
    assert "shape id shape:a" in lines[0]
    assert "could not be attached" in lines[-1]


async def test_a_missing_canvas_ref_is_an_error(fresh_user_dir):
    with pytest.raises(ValueError):
        await bot_send.prepare_attachments(bot_send.parse_refs([{"src": "/api/view?filename=nope.png&type=output"}]), [])


def _video(base, name="clip.mp4", seconds=2, fps=10):
    folder = base / "output" / "comfyart"
    folder.mkdir(parents=True, exist_ok=True)
    with av.open(str(folder / name), "w") as out:
        stream = out.add_stream("mpeg4", rate=fps)
        stream.width, stream.height, stream.pix_fmt = 64, 48, "yuv420p"
        for i in range(seconds * fps):
            frame = av.VideoFrame.from_image(Image.new("RGB", (64, 48), (i * 10 % 255, 0, 0)))
            for packet in stream.encode(frame):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    return f"/api/view?filename={name}&subfolder=comfyart&type=output"


def _docx(base, name="brief.docx"):
    folder = base / "input"
    folder.mkdir(parents=True, exist_ok=True)
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = (f'<w:document xmlns:w="{w}"><w:body>'
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Spring launch</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Use warm </w:t></w:r><w:r><w:t>colors.</w:t></w:r></w:p></w:body></w:document>')
    with zipfile.ZipFile(folder / name, "w") as z:
        z.writestr("word/document.xml", body)
    return f"/api/view?filename={name}&type=input"


async def test_audio_refs_send_their_transcript_and_no_picture(fresh_user_dir):
    refs = bot_send.parse_refs([{"src": "/api/view?filename=v.mp3&type=input", "id": "shape:s", "kind": "audio", "transcript": "hello there"}])
    attachments, lines = await bot_send.prepare_attachments(refs, [])
    assert attachments == []
    assert 'Transcript: "hello there"' in lines[0] and "reference_audios" in lines[0]


async def test_video_refs_attach_a_frame_sheet(fresh_user_dir):
    src = _video(fresh_user_dir)
    attachments, lines = await bot_send.prepare_attachments(bot_send.parse_refs([{"src": src, "kind": "video"}]), [])
    assert len(attachments) == 1 and "view_video" in lines[0]
    frames, duration = video_frames(view_path(src), 4)
    assert len(frames) == 4 and 1.5 < duration <= 2.1
    assert [round(at, 2) for at, _ in frames] == [round(duration * (i + 0.5) / 4, 2) for i in range(4)]


async def test_documents_send_their_text(fresh_user_dir):
    src = _docx(fresh_user_dir)
    docs = bot_send.parse_docs([{"src": src, "name": "brief.docx"}])
    attachments, lines = await bot_send.prepare_attachments([], [], docs)
    assert attachments == []
    assert "# Spring launch\nUse warm colors." in lines[0] and 'Attached document "brief.docx"' in lines[0]
    with pytest.raises(ValueError):
        bot_send.parse_docs([{"name": "x"}])


def test_compose_puts_memory_first_and_skill_instruction_before_the_text():
    text = bot_send.compose_provider_text("make it", skill_name="Poster", memory="MEM", lines=["[ref]"])
    assert text.startswith("MEM\n\nUse the ComfyArt skill 'Poster'")
    assert text.endswith("make it\n\n[ref]")
