#!/usr/bin/env python3
"""Offline kie.ai asset wash for issue #643 only.

Script-only batch tool. It sends each Lovart skill image (cover, examples,
or featured) through kie.ai image-to-image, saves the new bytes under
``--out``, and writes ``manifest.out.json`` so a later commit can pin them.
Nothing in ``src/``, ``api/``, ComfyUI, or WaveSpeed imports this file.
It is not a product feature and it is not a second generation channel.

Usage
-----
Source the key, then run the washer. ``--dry-run`` never reads the key and
never calls the network::

    source /home/box/secrets/comfyart-test.env
    python3 scripts/kie_wash_phase3.py \\
      --manifest docs/design/643/wash-manifest.json \\
      --out docs/design/643/wash \\
      [--dry-run] [--limit N] [--model NAME]

Env
---
``KIE_API_KEY``
    Bearer token for api.kie.ai. Required on a live run. Read from the
    environment only (the ``source`` line above). Never printed, never
    written into ``manifest.out.json``, and never sent to any host other
    than the kie API and the kie file-upload host.
``KIE_WASH_MODEL``
    Optional model when ``--model`` is omitted.
``KIE_WASH_POLL_TIMEOUT``
    Seconds to poll one task before failing it. Default 600.

Models
------
``gpt-image-2-5-flare-image-to-image``
    Default.
``gpt-image-2-5-sunburst-image-to-image``
    Allowed override via ``--model`` or ``KIE_WASH_MODEL``.

Live calls are ``POST /api/v1/jobs/createTask`` then ``GET
/api/v1/jobs/recordInfo`` until ``state`` is ``success`` or ``fail``.
The body is ``model`` plus ``input.prompt``, ``input.input_urls``,
``input.aspect_ratio`` (default ``auto``), and ``input.resolution``
(default ``2K``). HTTP 200 is not success: the JSON ``code`` field must
be 200. ``resultJson.resultUrls[0]`` is downloaded and saved. A local
``source_path`` is uploaded with the kie file-stream API first; that
temporary URL is not recorded.

Out layout
----------
::

    --out/<skill_id>/cover/cover.png|webp
    --out/<skill_id>/examples/NN.png|webp
    --out/<skill_id>/featured/NN.png|webp
    <parent of --out>/manifest.out.json

``NN`` is the zero-padded ``index``. Paths inside the manifest are
relative to ``--out``. Each row has ``skill_id``, ``slot``, ``index``,
``path``, ``sha256`` (saved bytes), ``model``, ``task_id``, and
``source``. ``source`` is ``sha256:`` plus the hex digest of a
``source_url``, or the basename of a ``source_path``. Lovart CDN URLs
are never printed and never written. Re-runs upsert rows in the existing
manifest and spend credits again for every selected entry.

Input shape: ``docs/design/643/wash-manifest.example.json``.
Example of the file a live run writes:
``docs/design/643/manifest.out.example.json``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import NoReturn

API_BASE = "https://api.kie.ai"
UPLOAD_BASE = "https://kieai.redpandaai.co"
CREATE_PATH = "/api/v1/jobs/createTask"
RECORD_PATH = "/api/v1/jobs/recordInfo"
UPLOAD_PATH = "/api/file-stream-upload"

DEFAULT_MODEL = "gpt-image-2-5-flare-image-to-image"
ALLOWED_MODELS = (
    DEFAULT_MODEL,
    "gpt-image-2-5-sunburst-image-to-image",
)
DEFAULT_PROMPT = (
    "Recreate this as original artwork. No brand marks, watermarks, or competitor logos."
)
SLOTS = ("cover", "examples", "featured")
SKILL_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ASPECT = re.compile(r"^(?:auto|\d{1,2}:\d{1,2})$")
RESOLUTIONS = ("1K", "2K", "4K")
LOVART_URL = re.compile(r"https?://[^\s\"'<>]*lovart[^\s\"'<>]*", re.IGNORECASE)
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
AUTH_HOSTS = frozenset({"api.kie.ai", "kieai.redpandaai.co"})
MAX_IMAGE_BYTES = 30 * 1024 * 1024
POLL_STATES = frozenset({"waiting", "queuing", "generating"})

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class KieError(RuntimeError):
    """kie.ai returned a failure, or a result could not be saved."""


def redact(text: str, key: str = "") -> str:
    """Drop the API key, bearer tokens, and any URL from text we print or save."""
    out = str(text)
    if key:
        out = out.replace(key, "[redacted]")
    out = re.sub(r"Bearer\s+\S+", "Bearer [redacted]", out, flags=re.IGNORECASE)
    out = LOVART_URL.sub("[url-redacted]", out)
    out = URL_RE.sub("[url-redacted]", out)
    return out


def lovart_url(value: str) -> bool:
    return bool(LOVART_URL.search(value or ""))


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_label(source_url: str | None, source_path: str | None) -> str:
    """Output source field: hash of the URL, or the path basename. Never a URL."""
    if source_url:
        return "sha256:" + sha256_hex(source_url.encode("utf-8"))
    name = Path(source_path or "").name
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise ValueError("source_path basename is empty")
    return name


def sniff_image(data: bytes) -> str:
    if data.startswith(PNG_MAGIC):
        return "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    return ""


def normalize_image(data: bytes) -> tuple[bytes, str]:
    """Return bytes to commit and the file extension. JPEG becomes PNG when Pillow is installed."""
    kind = sniff_image(data)
    if kind == "png":
        return data, ".png"
    if kind == "webp":
        return data, ".webp"
    if kind == "jpeg":
        try:
            from PIL import Image
        except ImportError as exc:
            raise KieError("result is jpeg; install Pillow to transcode it to png") from exc
        import io

        buf = io.BytesIO()
        Image.open(io.BytesIO(data)).save(buf, format="PNG")
        png = buf.getvalue()
        if not png.startswith(PNG_MAGIC):
            raise KieError("jpeg transcode did not produce a png")
        return png, ".png"
    raise KieError("result is not a png, webp, or jpeg")


def output_name(slot: str, index: int, ext: str) -> str:
    if slot == "cover":
        return f"cover{ext}"
    return f"{index:02d}{ext}"


def manifest_path_for(out_dir: Path) -> Path:
    """``manifest.out.json`` sits next to the ``--out`` directory, not inside it."""
    return out_dir.parent / "manifest.out.json"


def _host(url: str) -> str:
    return (urllib.parse.urlparse(url).hostname or "").lower()


class _NoLovartRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if lovart_url(newurl):
            raise KieError("refusing redirect to a Lovart URL")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _multipart(fields: dict[str, str], filename: str, content: bytes, mime: str) -> tuple[bytes, str]:
    boundary = "----kieWash" + uuid.uuid4().hex
    while boundary.encode("ascii") in content:
        boundary = "----kieWash" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        )
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename) or "image.png"
    chunks.append(
        (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"file\"; filename=\"{safe}\"\r\n"
            f"Content-Type: {mime}\r\n\r\n"
        ).encode()
        + content
        + b"\r\n"
    )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


class KieClient:
    """Minimal kie.ai jobs client. The key stays on the Authorization header."""

    def __init__(self, key: str, *, transport=None, download=None, sleep=time.sleep,
                 clock=time.monotonic, poll_timeout: float = 600.0):
        if not key or not key.strip():
            raise KieError("KIE_API_KEY is empty")
        self.key = key.strip()
        self.sleep = sleep
        self.clock = clock
        self.poll_timeout = poll_timeout
        self._opener = urllib.request.build_opener(_NoLovartRedirect)
        self._transport = transport or self._urllib_json
        self._download = download or self._urllib_download

    def _redact(self, text: str) -> str:
        return redact(text, self.key)

    def _urllib_json(self, method: str, url: str, *, json_body=None, raw=None, content_type=None) -> dict:
        if _host(url) not in AUTH_HOSTS:
            raise KieError("refusing to send the API key to an unexpected host")
        payload = raw
        headers = {"Authorization": f"Bearer {self.key}", "Accept": "application/json"}
        if json_body is not None:
            payload = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif content_type:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(url, data=payload, method=method, headers=headers)
        try:
            with self._opener.open(req, timeout=120) as res:
                text = res.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", "replace")
        except urllib.error.URLError as exc:
            raise KieError(self._redact(f"network error: {exc.reason}")) from exc
        try:
            parsed = json.loads(text) if text else {}
        except json.JSONDecodeError as exc:
            raise KieError(self._redact("response was not JSON")) from exc
        if not isinstance(parsed, dict):
            raise KieError("response was not a JSON object")
        return parsed

    def _urllib_download(self, url: str) -> bytes:
        if urllib.parse.urlparse(url).scheme != "https" or lovart_url(url):
            raise KieError("refusing to download result")
        # No Authorization header: result hosts are not the kie API.
        req = urllib.request.Request(url, method="GET")
        try:
            with self._opener.open(req, timeout=120) as res:
                data = res.read(MAX_IMAGE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            raise KieError(self._redact(f"download failed HTTP {exc.code}")) from exc
        except urllib.error.URLError as exc:
            raise KieError(self._redact(f"download failed: {exc.reason}")) from exc
        if len(data) > MAX_IMAGE_BYTES:
            raise KieError("result image exceeds the size cap")
        if not data:
            raise KieError("result image is empty")
        return data

    def _check(self, payload: dict, what: str) -> dict:
        code = payload.get("code")
        if code != 200 and str(code) != "200":
            raise KieError(self._redact(f"{what} code={code} msg={payload.get('msg')}"))
        if payload.get("success") is False:
            raise KieError(self._redact(f"{what} code={code} msg={payload.get('msg')}"))
        return payload

    def upload_file(self, path: Path) -> str:
        content = path.read_bytes()
        if not content or len(content) > MAX_IMAGE_BYTES:
            raise KieError("source_path is empty or larger than the upload cap")
        if sniff_image(content) not in {"png", "webp", "jpeg"}:
            raise KieError("source_path is not a png, webp, or jpeg")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if mime not in {"image/png", "image/webp", "image/jpeg"}:
            mime = {"png": "image/png", "webp": "image/webp", "jpeg": "image/jpeg"}[sniff_image(content)]
        filename = sha256_hex(content)[:16] + (path.suffix.lower() if path.suffix else ".png")
        raw, content_type = _multipart(
            {"uploadPath": "643/wash", "fileName": filename}, filename, content, mime
        )
        payload = self._check(
            self._transport(
                "POST", UPLOAD_BASE + UPLOAD_PATH, raw=raw, content_type=content_type
            ),
            "upload",
        )
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        url = data.get("downloadUrl")
        if not isinstance(url, str) or urllib.parse.urlparse(url).scheme != "https" or lovart_url(url):
            raise KieError("upload response had no usable download URL")
        return url

    def create_task(self, body: dict) -> str:
        payload = self._check(
            self._transport("POST", API_BASE + CREATE_PATH, json_body=body),
            "createTask",
        )
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        task_id = data.get("taskId")
        if not isinstance(task_id, str) or not task_id.strip():
            raise KieError("createTask returned no taskId")
        return task_id.strip()

    def poll(self, task_id: str) -> list[str]:
        deadline = self.clock() + self.poll_timeout
        delay = 2.0
        query = urllib.parse.urlencode({"taskId": task_id})
        url = f"{API_BASE}{RECORD_PATH}?{query}"
        while True:
            payload = self._check(self._transport("GET", url), "recordInfo")
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            state = data.get("state")
            if isinstance(state, str):
                state = state.lower()
            if state == "success":
                return result_urls(data)
            if state == "fail":
                raise KieError(self._redact(
                    f"task failed code={data.get('failCode')} msg={data.get('failMsg')}"
                ))
            if state not in POLL_STATES and state not in {None, ""}:
                raise KieError(self._redact(f"unexpected task state={state}"))
            if self.clock() >= deadline:
                raise KieError(self._redact(f"task timed out state={state}"))
            self.sleep(delay)
            delay = min(delay * 1.5, 15.0)


def result_urls(data: dict) -> list[str]:
    raw = data.get("resultJson")
    obj = None
    if isinstance(raw, str) and raw.strip():
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise KieError("resultJson was not JSON") from exc
    elif isinstance(raw, dict):
        obj = raw
    elif isinstance(data.get("response"), dict):
        obj = data["response"]
    if not isinstance(obj, dict):
        raise KieError("success response has no resultJson")
    urls = obj.get("resultUrls")
    if not isinstance(urls, list) or not urls:
        raise KieError("resultJson.resultUrls is empty")
    cleaned = []
    for url in urls:
        if not isinstance(url, str) or urllib.parse.urlparse(url).scheme != "https":
            raise KieError("result URL is not https")
        if lovart_url(url):
            raise KieError("refusing a Lovart result URL")
        cleaned.append(url)
    return cleaned


def build_create_body(model: str, prompt: str, input_url: str, aspect_ratio: str, resolution: str) -> dict:
    return {
        "model": model,
        "input": {
            "prompt": prompt,
            "input_urls": [input_url],
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
        },
    }


def _bad(index: int, message: str) -> NoReturn:
    raise ValueError(f"manifest entry {index}: {message}")


def _optional_str(entry: dict, key: str, index: int) -> str | None:
    if key not in entry or entry[key] is None:
        return None
    value = entry[key]
    if not isinstance(value, str):
        _bad(index, f"{key} must be a string")
    value = value.strip()
    return value or None


def parse_entry(entry: dict, index: int) -> dict:
    if not isinstance(entry, dict):
        _bad(index, "must be an object")
    skill_id = entry.get("skill_id")
    if not isinstance(skill_id, str) or not SKILL_ID.fullmatch(skill_id) or len(skill_id) > 64:
        _bad(index, "skill_id must be a lowercase slug")
    slot = entry.get("slot")
    if slot not in SLOTS:
        _bad(index, "slot must be cover, examples, or featured")
    if "index" in entry and entry["index"] is not None:
        number = entry["index"]
        if isinstance(number, bool) or not isinstance(number, int) or not 0 <= number <= 99:
            _bad(index, "index must be an integer from 0 to 99")
    elif slot == "cover":
        number = 0
    else:
        _bad(index, "index is required for examples and featured")
    source_url = _optional_str(entry, "source_url", index)
    source_path = _optional_str(entry, "source_path", index)
    if bool(source_url) == bool(source_path):
        _bad(index, "set exactly one of source_url or source_path")
    if source_url:
        parts = urllib.parse.urlparse(source_url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            _bad(index, "source_url must be an http(s) URL")
        if any(ch in source_url for ch in "\r\n\t "):
            _bad(index, "source_url contains whitespace")
    else:
        path = Path(source_path)
        if not path.is_file():
            _bad(index, "source_path is not an existing file")
        source_path = str(path)
    prompt = _optional_str(entry, "prompt", index) or DEFAULT_PROMPT
    if len(prompt) > 20000:
        _bad(index, "prompt is longer than 20000 characters")
    if lovart_url(prompt):
        _bad(index, "prompt contains a URL")
    aspect_ratio = _optional_str(entry, "aspect_ratio", index) or "auto"
    if not ASPECT.fullmatch(aspect_ratio):
        _bad(index, "aspect_ratio is not auto or W:H")
    resolution = _optional_str(entry, "resolution", index) or "2K"
    if resolution not in RESOLUTIONS:
        _bad(index, "resolution must be 1K, 2K, or 4K")
    return {
        "skill_id": skill_id,
        "slot": slot,
        "index": number,
        "source_url": source_url,
        "source_path": source_path,
        "prompt": prompt,
        "prompt_kind": "default" if prompt == DEFAULT_PROMPT else "custom",
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "source": source_label(source_url, source_path),
    }


def load_manifest(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read manifest: {exc.strerror or exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"manifest is not JSON: {exc.msg}") from exc
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("assets")
        if not isinstance(items, list):
            raise ValueError("manifest object needs an assets array")
    else:
        raise ValueError("manifest must be an object or an array")
    if not items:
        raise ValueError("manifest has no assets")
    parsed = [parse_entry(item, i) for i, item in enumerate(items, start=1)]
    seen: set[tuple] = set()
    covers: set[str] = set()
    for item in parsed:
        key = (item["skill_id"], item["slot"], item["index"])
        if key in seen:
            raise ValueError(f"duplicate asset {item['skill_id']} {item['slot']} {item['index']}")
        seen.add(key)
        if item["slot"] == "cover":
            if item["skill_id"] in covers:
                raise ValueError(f"duplicate cover for {item['skill_id']}")
            covers.add(item["skill_id"])
    return parsed


def resolve_model(cli_model: str, env: dict | None = None) -> str:
    env = os.environ if env is None else env
    model = (cli_model or env.get("KIE_WASH_MODEL") or DEFAULT_MODEL).strip()
    if model not in ALLOWED_MODELS:
        allowed = ", ".join(ALLOWED_MODELS)
        raise ValueError(f"model must be one of: {allowed}")
    return model


def plan_lines(entries: list[dict], model: str) -> list[str]:
    lines = [
        f"dry-run model={model} planned={len(entries)}",
        "endpoint POST /api/v1/jobs/createTask",
        "endpoint GET /api/v1/jobs/recordInfo",
    ]
    for item in entries:
        lines.append(
            "plan skill={skill_id} slot={slot} index={index} source={source} "
            "aspect_ratio={aspect_ratio} resolution={resolution} prompt={prompt_kind}".format(**item)
        )
    return lines


def _row_key(row: dict) -> tuple:
    return (row["skill_id"], row["slot"], row["index"])


def load_existing_manifest(path: Path) -> dict:
    if not path.is_file():
        return {"issue": 643, "tool": "scripts/kie_wash_phase3.py", "model": "", "assets": [], "errors": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"existing manifest.out.json cannot be read: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("assets"), list):
        raise ValueError("existing manifest.out.json needs an assets array")
    data.setdefault("errors", [])
    if not isinstance(data["errors"], list):
        raise ValueError("existing manifest.out.json errors must be an array")
    return data


def render_manifest(model: str, assets: list[dict], errors: list[dict], key: str) -> str:
    def sort_key(row: dict) -> tuple:
        return (row.get("skill_id", ""), row.get("slot", ""), row.get("index", 0))

    doc = {
        "issue": 643,
        "tool": "scripts/kie_wash_phase3.py",
        "model": model,
        "assets": sorted(assets, key=sort_key),
        "errors": sorted(errors, key=sort_key),
    }
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if URL_RE.search(text) or LOVART_URL.search(text):
        raise KieError("refusing to write manifest.out.json because it contains a URL")
    if key and key in text:
        raise KieError("refusing to write manifest.out.json because it contains the API key")
    return text


def merge_results(existing: dict, assets: list[dict], errors: list[dict]) -> tuple[list[dict], list[dict]]:
    kept = {_row_key(row): row for row in existing.get("assets", []) if isinstance(row, dict)}
    problems = {_row_key(row): row for row in existing.get("errors", []) if isinstance(row, dict)}
    for row in assets:
        key = _row_key(row)
        kept[key] = row
        problems.pop(key, None)
    for row in errors:
        problems[_row_key(row)] = row
    return list(kept.values()), list(problems.values())


def wash(entries: list[dict], out_dir: Path, model: str, client: KieClient) -> tuple[list[dict], list[dict]]:
    assets: list[dict] = []
    errors: list[dict] = []
    for item in entries:
        label = f"skill={item['skill_id']} slot={item['slot']} index={item['index']}"
        try:
            if item["source_path"]:
                input_url = client.upload_file(Path(item["source_path"]))
            else:
                input_url = item["source_url"]
            body = build_create_body(
                model, item["prompt"], input_url, item["aspect_ratio"], item["resolution"]
            )
            task_id = client.create_task(body)
            urls = client.poll(task_id)
            blob = client._download(urls[0])
            saved, ext = normalize_image(blob)
            rel = f"{item['skill_id']}/{item['slot']}/{output_name(item['slot'], item['index'], ext)}"
            dest = out_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            partial = dest.with_suffix(dest.suffix + ".part")
            partial.write_bytes(saved)
            partial.replace(dest)
            assets.append({
                "skill_id": item["skill_id"],
                "slot": item["slot"],
                "index": item["index"],
                "path": rel,
                "sha256": sha256_hex(saved),
                "model": model,
                "task_id": task_id,
                "source": item["source"],
            })
            extra = f" results={len(urls)} saved=1" if len(urls) > 1 else ""
            print(redact(
                f"ok {label} path={rel} sha256={sha256_hex(saved)} task_id={task_id}{extra}",
                client.key,
            ), flush=True)
        except (KieError, OSError) as exc:
            message = client._redact(str(exc))
            errors.append({
                "skill_id": item["skill_id"],
                "slot": item["slot"],
                "index": item["index"],
                "error": message,
            })
            print(f"FAIL {label} {message}", file=sys.stderr, flush=True)
    return assets, errors


def _poll_timeout(env: dict) -> float:
    raw = (env.get("KIE_WASH_POLL_TIMEOUT") or "").strip()
    if not raw:
        return 600.0
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError("KIE_WASH_POLL_TIMEOUT must be a number of seconds") from exc
    if value <= 0:
        raise ValueError("KIE_WASH_POLL_TIMEOUT must be greater than 0")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scripts/kie_wash_phase3.py",
        description="Offline kie.ai copyright wash for skill assets (#643 only).",
    )
    parser.add_argument("--manifest", required=True, help="input JSON (object with assets, or an array)")
    parser.add_argument("--out", required=True, help="directory for washed cover/examples/featured files")
    parser.add_argument("--dry-run", action="store_true", help="validate and print the plan; do not call kie.ai")
    parser.add_argument("--limit", type=_positive_int, default=None, help="wash only the first N assets")
    parser.add_argument("--model", default="", help="image-to-image model (else KIE_WASH_MODEL, else flare)")
    args = parser.parse_args(argv)
    key = os.environ.get("KIE_API_KEY", "")
    try:
        entries = load_manifest(Path(args.manifest))
        model = resolve_model(args.model)
        selected = entries if args.limit is None else entries[: args.limit]
        if args.dry_run:
            for line in plan_lines(selected, model):
                print(redact(line, key), flush=True)
            return 0
        if not key.strip():
            print(
                "KIE_API_KEY is not set. Source /home/box/secrets/comfyart-test.env and retry.",
                file=sys.stderr,
            )
            return 2
        out_dir = Path(args.out)
        client = KieClient(key, poll_timeout=_poll_timeout(os.environ))
        new_assets, new_errors = wash(selected, out_dir, model, client)
        dest = manifest_path_for(out_dir)
        existing = load_existing_manifest(dest)
        assets, errors = merge_results(existing, new_assets, new_errors)
        text = render_manifest(model, assets, errors, key.strip())
        dest.parent.mkdir(parents=True, exist_ok=True)
        partial = dest.with_suffix(".json.part")
        partial.write_text(text, encoding="utf-8")
        partial.replace(dest)
        print(f"wrote {len(new_assets)} assets, {len(new_errors)} errors -> {dest.name}", flush=True)
        return 1 if new_errors else 0
    except ValueError as exc:
        print(redact(str(exc), key), file=sys.stderr)
        return 2
    except KieError as exc:
        print(redact(str(exc), key), file=sys.stderr)
        return 1


def _positive_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("limit must be an integer") from exc
    if value < 1:
        raise argparse.ArgumentTypeError("limit must be >= 1")
    return value


if __name__ == "__main__":
    sys.exit(main())
