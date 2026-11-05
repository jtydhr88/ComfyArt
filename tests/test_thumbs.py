from __future__ import annotations

import io

from PIL import Image

from ComfyArt.api import thumbs


def _save(base, name, size):
    path = base / "output" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (200, 80, 40)).save(path)
    return f"/api/view?filename={name}&subfolder=&type=output"


async def test_large_image_gets_a_cached_webp_thumbnail(bot_client, fresh_user_dir):
    url = _save(fresh_user_dir, "big.png", (2000, 1000))
    res = await bot_client.get("/comfyart/thumb", params={"url": url, "max": "256"})
    assert res.status == 200 and res.headers["Content-Type"] == "image/webp"
    im = Image.open(io.BytesIO(await res.read()))
    assert im.format == "WEBP" and max(im.size) == 256
    path = thumbs.thumb_for(url, 256)
    assert path.startswith(str(fresh_user_dir / "user" / "__comfyart" / "thumbs"))
    assert thumbs.thumb_for(url, 200) == path


async def test_small_image_is_served_as_is(bot_client, fresh_user_dir):
    url = _save(fresh_user_dir, "small.png", (300, 200))
    assert thumbs.thumb_for(url, 256) == str(fresh_user_dir / "output" / "small.png")
    assert (await bot_client.get("/comfyart/thumb", params={"url": url})).status == 200


async def test_animated_image_gets_a_still_thumbnail(fresh_user_dir):
    path = fresh_user_dir / "output" / "anim.webp"
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = [Image.new("RGB", (100, 100), c) for c in ((255, 0, 0), (0, 0, 255))]
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=100)
    thumb = thumbs.thumb_for("/api/view?filename=anim.webp&type=output", 256)
    assert thumb != str(path)
    with Image.open(thumb) as im:
        assert not getattr(im, "is_animated", False) and im.getpixel((5, 5))[0] > 200 and im.getpixel((5, 5))[2] < 50


async def test_paths_outside_the_folder_are_not_found(bot_client, fresh_user_dir):
    (fresh_user_dir / "secret.png").write_bytes(b"x")
    res = await bot_client.get("/comfyart/thumb", params={"url": "/api/view?filename=secret.png&subfolder=..&type=output"})
    assert res.status == 404
    res = await bot_client.get("/comfyart/thumb", params={"url": "/api/view?filename=nope.png&type=output"})
    assert res.status == 404


async def test_svg_is_served_sandboxed_and_unreadable_files_are_not_found(bot_client, fresh_user_dir):
    out = fresh_user_dir / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "v.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"/>')
    (out / "bad.png").write_bytes(b"not an image")
    res = await bot_client.get("/comfyart/thumb", params={"url": "/api/view?filename=v.svg&type=output"})
    assert res.status == 200 and res.headers["Content-Type"] == "image/svg+xml"
    assert res.headers["Content-Security-Policy"].startswith("sandbox;") and res.headers["X-Content-Type-Options"] == "nosniff"
    assert (await bot_client.get("/comfyart/thumb", params={"url": "/api/view?filename=bad.png&type=output"})).status == 404
