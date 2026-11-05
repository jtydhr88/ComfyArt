"""#687-3 opt-in e2e: push a small real mp4 through the motion dialog's REAL upload path (uploadSkillImage →
ComfyUI POST /api/upload/image) against a live ComfyUI behind the app. No generation, no paid API.
Run: QA687_REAL_URL=http://127.0.0.1:8188/comfyart/ (this repo symlinked into a real ComfyUI custom_nodes, same origin as prod). Skipped otherwise."""
from __future__ import annotations

import hashlib
import os
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.async_api")
URL = os.environ.get("QA687_REAL_URL")
SHOTS = os.environ.get("QA687_SHOTS")
pytestmark = pytest.mark.skipif(not URL, reason="needs QA687_REAL_URL (app in front of a real ComfyUI)")


async def test_motion_reference_video_real_upload_687(tmp_path):
    mp4 = tmp_path / "qa687_ref.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=10", "-t", "1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)], check=True)
    data = mp4.read_bytes()
    assert 1000 < len(data) < 20000
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await (await browser.new_context(viewport={"width": 1440, "height": 900})).new_page()
        await pg.add_init_script("localStorage.setItem('comfyart.lang','en');localStorage.setItem('comfyart.theme','light')")
        posts: list[tuple[str, int]] = []
        pg.on("response", lambda r: posts.append((r.url, r.status)) if "/upload/image" in r.url else None)
        await pg.goto(URL)
        await pg.get_by_test_id("rail-skills").click()
        card = pg.locator('[data-testid="skills-wall"] [data-testid="skills-wall-card"][data-skill="motion-poster-generator"]')
        await card.scroll_into_view_if_needed()
        await card.hover()
        await card.get_by_test_id("skills-card-try").click()
        dlg = pg.locator('[data-testid="skill-run-dialog"][data-skill="motion-poster-generator"]')
        await dlg.wait_for(timeout=10000)
        box = dlg.locator('[data-testid="skill-run-field"][data-key="refVideo"]')
        await box.locator("input[type=file]").set_input_files(str(mp4))
        video = box.locator("video")
        try:
            await video.wait_for(timeout=15000)
        except Exception:
            print("DEBUG", posts, await box.inner_html())
            raise
        src = await video.get_attribute("src")
        assert await dlg.get_by_test_id("skill-run-upload-error").count() == 0
        ok = await video.evaluate("v => new Promise(r => { if (v.readyState >= 1) return r(v.videoWidth); v.onloadedmetadata = () => r(v.videoWidth); v.onerror = () => r(-1) })")
        if SHOTS:
            await pg.wait_for_timeout(1200)  # let the dialog open animation settle
            await pg.screenshot(path=str(Path(SHOTS) / "skill-fields-motion-real-mp4-upload-en-light.png"))
        await browser.close()
    assert posts and all(s == 200 for _, s in posts), posts
    assert ok == 160, ok  # the browser decodes the uploaded mp4 served back by ComfyUI /view
    full = urllib.request.urlopen(urllib.parse.urljoin(URL, src)).read()
    assert hashlib.sha256(full).hexdigest() == hashlib.sha256(data).hexdigest()  # byte-identical round trip
    print("UPLOAD", posts, src, len(full))
