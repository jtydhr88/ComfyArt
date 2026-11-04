"""#643 offline kie.ai wash script. No network. Not a product/runtime test."""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_IN = ROOT / "docs/design/643/wash-manifest.example.json"
EXAMPLE_OUT = ROOT / "docs/design/643/manifest.out.example.json"
SCRIPT = ROOT / "scripts/kie_wash_phase3.py"

spec = importlib.util.spec_from_file_location("kie_wash_phase3", SCRIPT)
kie = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(kie)

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)
ASSET_KEYS = {"skill_id", "slot", "index", "path", "sha256", "model", "task_id", "source"}


def _cdn(path: str) -> str:
    # Assembled so this file does not contain a CDN URL literal.
    return "https://cdn." + "lovart" + ".ai/" + path


def _entry(**overrides) -> dict:
    item = {
        "skill_id": "example-skill",
        "slot": "cover",
        "index": 0,
        "source_url": "https://example.com/643-placeholder-cover.png",
    }
    item.update(overrides)
    return item


def _client(transport, download=None, key="super-secret-key", **kwargs):
    return kie.KieClient(
        key,
        transport=transport,
        download=download or (lambda url: PNG),
        sleep=lambda _seconds: None,
        **kwargs,
    )


def test_example_files_match_the_script_contract():
    incoming = json.loads(EXAMPLE_IN.read_text(encoding="utf-8"))
    outgoing = json.loads(EXAMPLE_OUT.read_text(encoding="utf-8"))
    parsed = kie.load_manifest(EXAMPLE_IN)
    assert [item["slot"] for item in parsed] == ["cover", "examples"]
    assert parsed[0]["prompt_kind"] == "custom"
    assert parsed[1]["prompt_kind"] == "default"
    assert parsed[1]["prompt"] == kie.DEFAULT_PROMPT
    assert parsed[1]["aspect_ratio"] == "16:9"
    assert parsed[1]["resolution"] == "2K"
    by_slot = {row["slot"]: row for row in outgoing["assets"]}
    labels = {
        "643-example-cover": "cover",
        "643-example-example": "examples",
    }
    for label, slot in labels.items():
        row = by_slot[slot]
        assert set(row) == ASSET_KEYS
        assert row["sha256"] == hashlib.sha256(label.encode("ascii")).hexdigest()
        assert row["model"] == kie.DEFAULT_MODEL
        assert row["source"] == parsed[{"cover": 0, "examples": 1}[slot]]["source"]
        assert "://" not in row["source"]
    text = EXAMPLE_OUT.read_text(encoding="utf-8")
    assert "https://" not in text
    assert "http://" not in text
    assert "lovart" not in text.lower()


def test_dry_run_prints_plan_without_urls_or_key(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("KIE_API_KEY", "super-secret-key")

    def boom(*_args, **_kwargs):
        raise AssertionError("dry-run contacted the network")

    monkeypatch.setattr(kie.urllib.request, "urlopen", boom)
    out = tmp_path / "wash"
    rc = kie.main([
        "--dry-run",
        "--manifest", str(EXAMPLE_IN),
        "--out", str(out),
    ])
    captured = capsys.readouterr()
    assert rc == 0
    assert "super-secret-key" not in captured.out
    assert "super-secret-key" not in captured.err
    assert "https://" not in captured.out
    assert "example.com" not in captured.out
    assert "planned=2" in captured.out
    assert "prompt=custom" in captured.out
    assert "prompt=default" in captured.out
    assert "POST /api/v1/jobs/createTask" in captured.out
    assert "GET /api/v1/jobs/recordInfo" in captured.out
    assert not out.exists()
    assert not kie.manifest_path_for(out).exists()


def test_dry_run_hides_cdn_source_urls(tmp_path, capsys):
    manifest = tmp_path / "wash-manifest.json"
    manifest.write_text(json.dumps({"assets": [_entry(source_url=_cdn("a.png"))]}), encoding="utf-8")
    rc = kie.main(["--dry-run", "--manifest", str(manifest), "--out", str(tmp_path / "wash")])
    captured = capsys.readouterr()
    assert rc == 0
    assert "lovart" not in captured.out.lower()
    assert "https://" not in captured.out
    assert "sha256:" in captured.out


def test_dry_run_limit_and_sunburst_model(tmp_path, capsys, monkeypatch):
    rc = kie.main([
        "--dry-run",
        "--manifest", str(EXAMPLE_IN),
        "--out", str(tmp_path / "wash"),
        "--limit", "1",
        "--model", "gpt-image-2-5-sunburst-image-to-image",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "planned=1" in out
    assert "model=gpt-image-2-5-sunburst-image-to-image" in out
    assert "slot=examples" not in out
    monkeypatch.setenv("KIE_WASH_MODEL", "gpt-image-2-5-sunburst-image-to-image")
    assert kie.resolve_model("") == "gpt-image-2-5-sunburst-image-to-image"
    assert kie.resolve_model("gpt-image-2-5-flare-image-to-image") == kie.DEFAULT_MODEL


def test_cli_rejects_bad_model_and_missing_key(tmp_path, monkeypatch, capsys):
    rc = kie.main([
        "--dry-run", "--manifest", str(EXAMPLE_IN), "--out", str(tmp_path / "wash"),
        "--model", "not-a-wash-model",
    ])
    assert rc == 2
    assert "model must be one of" in capsys.readouterr().err
    monkeypatch.delenv("KIE_API_KEY", raising=False)
    rc = kie.main(["--manifest", str(EXAMPLE_IN), "--out", str(tmp_path / "wash")])
    assert rc == 2
    assert "KIE_API_KEY" in capsys.readouterr().err
    assert not (tmp_path / "wash").exists()


@pytest.mark.parametrize("item, message, drop_index", [
    ({"slot": "poster"}, "slot", False),
    ({"source_url": None, "source_path": None}, "exactly one", False),
    ({"source_path": "also.png"}, "exactly one", False),
    ({"skill_id": "../escape"}, "skill_id", False),
    ({"slot": "examples"}, "index", True),
    ({"resolution": "8K"}, "resolution", False),
])
def test_manifest_validation(item, message, drop_index):
    payload = _entry(**item)
    if drop_index:
        payload.pop("index", None)
    with pytest.raises(ValueError, match=message):
        kie.parse_entry(payload, 1)


def test_duplicate_cover_and_missing_file(tmp_path):
    first = _entry()
    second = _entry(index=1)
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"assets": [first, second]}), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate cover"):
        kie.load_manifest(path)
    missing = _entry(source_url=None, source_path=str(tmp_path / "missing.png"))
    with pytest.raises(ValueError, match="existing file"):
        kie.parse_entry(missing, 1)


def test_create_body_shape_and_non_200_code():
    body = kie.build_create_body(
        kie.DEFAULT_MODEL, kie.DEFAULT_PROMPT, "https://example.com/in.png", "auto", "2K"
    )
    assert body == {
        "model": kie.DEFAULT_MODEL,
        "input": {
            "prompt": kie.DEFAULT_PROMPT,
            "input_urls": ["https://example.com/in.png"],
            "aspect_ratio": "auto",
            "resolution": "2K",
        },
    }

    def transport(method, url, json_body=None, raw=None, content_type=None):
        assert method == "POST"
        return {"code": 401, "msg": "bad key super-secret-key", "data": None}

    client = _client(transport)
    with pytest.raises(kie.KieError) as caught:
        client.create_task(body)
    assert "super-secret-key" not in str(caught.value)
    assert "[redacted]" in str(caught.value)
    assert "code=401" in str(caught.value)


def test_live_wash_writes_bytes_manifest_and_no_urls(tmp_path):
    calls = {"poll": 0, "download": 0}

    def transport(method, url, json_body=None, raw=None, content_type=None):
        if url.endswith(kie.CREATE_PATH):
            assert json_body["model"] == kie.DEFAULT_MODEL
            assert json_body["input"]["input_urls"] == ["https://example.com/643-placeholder-cover.png"]
            return {"code": 200, "msg": "success", "data": {"taskId": "task_test_1"}}
        if kie.RECORD_PATH in url:
            calls["poll"] += 1
            assert "taskId=task_test_1" in url
            if calls["poll"] == 1:
                return {"code": 200, "data": {"state": "generating", "model": kie.DEFAULT_MODEL}}
            return {
                "code": 200,
                "data": {
                    "state": "SUCCESS",
                    "resultJson": json.dumps({
                        "resultUrls": [
                            "https://tempfile.example/out.png",
                            "https://tempfile.example/extra.png",
                        ]
                    }),
                },
            }
        raise AssertionError(url)

    def download(url):
        calls["download"] += 1
        assert url.endswith("/out.png")
        return PNG

    out = tmp_path / "wash"
    client = _client(transport, download)
    assets, errors = kie.wash(kie.load_manifest(EXAMPLE_IN)[:1], out, kie.DEFAULT_MODEL, client)
    assert errors == []
    assert calls["download"] == 1
    assert calls["poll"] == 2
    saved = out / "example-skill/cover/cover.png"
    assert saved.read_bytes() == PNG
    assert assets[0]["sha256"] == hashlib.sha256(PNG).hexdigest()
    assert assets[0]["task_id"] == "task_test_1"
    assert set(assets[0]) == ASSET_KEYS

    existing = {
        "issue": 643,
        "tool": "scripts/kie_wash_phase3.py",
        "model": "old",
        "assets": [{
            "skill_id": "other-skill",
            "slot": "featured",
            "index": 0,
            "path": "other-skill/featured/00.png",
            "sha256": "ab",
            "model": "old-model",
            "task_id": "task_old",
            "source": "prior.png",
        }],
        "errors": [{
            "skill_id": "example-skill",
            "slot": "cover",
            "index": 0,
            "error": "previous failure",
        }],
    }
    merged_assets, merged_errors = kie.merge_results(existing, assets, [])
    text = kie.render_manifest(kie.DEFAULT_MODEL, merged_assets, merged_errors, "super-secret-key")
    assert "https://" not in text
    assert "super-secret-key" not in text
    doc = json.loads(text)
    assert [row["skill_id"] for row in doc["assets"]] == ["example-skill", "other-skill"]
    assert doc["errors"] == []
    assert kie.manifest_path_for(out) == tmp_path / "manifest.out.json"


def test_failure_redacts_key_and_cdn_and_keeps_going(tmp_path):
    leak = "see " + _cdn("x.png") + " super-secret-key"

    def transport(method, url, json_body=None, raw=None, content_type=None):
        if url.endswith(kie.CREATE_PATH):
            return {"code": 200, "data": {"taskId": "task_fail_1"}}
        return {"code": 200, "data": {"state": "fail", "failCode": "500", "failMsg": leak}}

    assets, errors = kie.wash(
        [kie.parse_entry(_entry(), 1)], tmp_path / "wash", kie.DEFAULT_MODEL, _client(transport)
    )
    assert assets == []
    assert len(errors) == 1
    assert "super-secret-key" not in errors[0]["error"]
    assert "lovart" not in errors[0]["error"].lower()
    assert "[url-redacted]" in errors[0]["error"]
    assert "[redacted]" in errors[0]["error"]
    text = kie.render_manifest(kie.DEFAULT_MODEL, assets, errors, "super-secret-key")
    assert "lovart" not in text.lower()
    assert "https://" not in text


def test_refuses_lovart_result_and_unexpected_auth_host():
    with pytest.raises(kie.KieError, match="Lovart"):
        kie.result_urls({"resultJson": json.dumps({"resultUrls": [_cdn("out.png")]})})
    client = kie.KieClient("super-secret-key")
    with pytest.raises(kie.KieError, match="unexpected host"):
        client._urllib_json("GET", "https://example.com/nope")


def test_source_path_uploads_then_washes_without_recording_upload_url(tmp_path):
    src = tmp_path / "gold-cover.png"
    src.write_bytes(PNG)
    upload_url = "https://tempfile.example/uploaded.png"

    def transport(method, url, json_body=None, raw=None, content_type=None):
        if url.endswith(kie.UPLOAD_PATH):
            assert method == "POST"
            assert raw is not None and PNG in raw
            assert b"super-secret-key" not in raw
            assert "multipart/form-data" in (content_type or "")
            return {"success": True, "code": 200, "msg": "ok", "data": {"downloadUrl": upload_url}}
        if url.endswith(kie.CREATE_PATH):
            assert json_body["input"]["input_urls"] == [upload_url]
            assert json_body["input"]["resolution"] == "2K"
            return {"code": "200", "data": {"taskId": "task_local_1"}}
        if kie.RECORD_PATH in url:
            return {"code": 200, "data": {"state": "success", "resultJson": json.dumps(
                {"resultUrls": ["https://tempfile.example/out.png"]}
            )}}
        raise AssertionError(url)

    entry = kie.parse_entry({
        "skill_id": "example-skill",
        "slot": "featured",
        "index": 2,
        "source_path": str(src),
    }, 1)
    assert entry["source"] == "gold-cover.png"
    assets, errors = kie.wash([entry], tmp_path / "wash", kie.DEFAULT_MODEL, _client(transport))
    assert errors == []
    assert assets[0]["path"] == "example-skill/featured/02.png"
    assert assets[0]["source"] == "gold-cover.png"
    text = kie.render_manifest(kie.DEFAULT_MODEL, assets, [], "super-secret-key")
    assert "tempfile" not in text
    assert "gold-cover.png" in text
    assert str(src.parent) not in text


def test_code_200_with_api_failure_does_not_save(tmp_path):
    def transport(method, url, json_body=None, raw=None, content_type=None):
        return {"code": 422, "msg": "recordInfo is null", "data": None}

    assets, errors = kie.wash(
        [kie.parse_entry(_entry(slot="examples", index=3), 1)],
        tmp_path / "wash",
        kie.DEFAULT_MODEL,
        _client(transport),
    )
    assert assets == []
    assert "code=422" in errors[0]["error"]
    assert not (tmp_path / "wash").exists()


def test_jpeg_without_pillow_is_an_error(monkeypatch):
    real_import = __import__

    def blocked(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "PIL" or name.startswith("PIL."):
            raise ImportError("no PIL")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", blocked)
    with pytest.raises(kie.KieError, match="Pillow"):
        kie.normalize_image(b"\xff\xd8\xff" + b"\x00" * 16)


def test_script_is_not_wired_into_the_app():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "import api" not in text
    assert "from src" not in text
    assert "api/wavespeed.py" not in text
    assert "KIE_API_KEY" in text
    assert "gpt-image-2-5-sunburst-image-to-image" in text


def test_712_lost_poll_resumes_with_saved_task_id(tmp_path):
    calls = {"create": 0, "poll": 0}

    def transport(method, url, json_body=None, raw=None, content_type=None):
        if url.endswith(kie.CREATE_PATH):
            calls["create"] += 1
            return {"code": 200, "data": {"taskId": "task_712"}}
        assert "taskId=task_712" in url
        calls["poll"] += 1
        if calls["poll"] == 1:
            raise kie.KieError("network error: reset")
        return {"code": 200, "data": {"state": "success", "resultJson": json.dumps(
            {"resultUrls": ["https://tempfile.example/out.png"]})}}

    assets, errors = kie.wash([kie.parse_entry(_entry(), 1)], tmp_path / "w", kie.DEFAULT_MODEL, _client(transport))
    assert errors == [] and assets[0]["task_id"] == "task_712" and calls == {"create": 1, "poll": 2}


def test_712_failed_task_row_keeps_task_id_and_marks_not_succeeded(tmp_path):
    def transport(method, url, json_body=None, raw=None, content_type=None):
        if url.endswith(kie.CREATE_PATH):
            return {"code": 200, "data": {"taskId": "task_712b"}}
        return {"code": 200, "data": {"state": "fail", "failCode": "500", "failMsg": "boom"}}

    _, errors = kie.wash([kie.parse_entry(_entry(), 1)], tmp_path / "w", kie.DEFAULT_MODEL, _client(transport))
    assert errors[0]["task_id"] == "task_712b" and errors[0]["generation_succeeded"] is False


def test_712_no_task_id_row_has_none(tmp_path):
    def transport(method, url, json_body=None, raw=None, content_type=None):
        return {"code": 200, "data": {}}

    _, errors = kie.wash([kie.parse_entry(_entry(), 1)], tmp_path / "w", kie.DEFAULT_MODEL, _client(transport))
    assert errors[0]["task_id"] is None and "no taskId" in errors[0]["error"]
