from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import types
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO.parent) not in sys.path:
    sys.path.insert(0, str(_REPO.parent))

BASE = Path(tempfile.mkdtemp(prefix="comfyart-tests-"))
SENT: list[tuple[str, dict]] = []


def _make_module(name: str, **attrs) -> types.ModuleType:
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


def _install_stubs() -> None:
    state = {"base": BASE}

    def _annotated_filepath(name: str) -> str:
        kind = "input"
        for t in ("input", "output", "temp"):
            if name.endswith(f" [{t}]"):
                name, kind = name[: -len(t) - 3], t
        return str(state["base"] / kind / name)

    def _save_image_path(prefix: str, root: str):
        subfolder, _, name = prefix.rpartition("/")
        folder = os.path.join(root, subfolder)
        os.makedirs(folder, exist_ok=True)
        return folder, name, 1, subfolder, prefix

    def user_dir() -> str:
        return str(state["base"] / "user")

    _make_module(
        "folder_paths",
        STATE=state,
        SYSTEM_USER_PREFIX="__",
        get_user_directory=user_dir,
        get_system_user_directory=lambda name="system": os.path.join(user_dir(), f"__{name}"),
        get_public_user_directory=lambda user: None if user.startswith("__") else os.path.join(user_dir(), user),
        get_input_directory=lambda: str(state["base"] / "input"),
        get_output_directory=lambda: str(state["base"] / "output"),
        get_temp_directory=lambda: str(state["base"] / "temp"),
        get_annotated_filepath=_annotated_filepath,
        get_save_image_path=_save_image_path,
        get_directory_by_type=lambda t: str(state["base"] / t) if t in ("input", "output", "temp") else None,
        get_filename_list=lambda kind: [],
        get_full_path_or_raise=lambda kind, name: name,
    )
    comfy = _make_module("comfy")
    comfy.ops = _make_module("comfy.ops", manual_cast=object)
    comfy.sd = _make_module("comfy.sd", load_diffusion_model=lambda *a, **k: None)
    comfy.utils = _make_module("comfy.utils", ProgressBar=lambda total: types.SimpleNamespace(update=lambda n: None))
    comfy.model_management = _make_module("comfy.model_management", throw_exception_if_processing_interrupted=lambda: None)
    comfy.cli_args = _make_module("comfy.cli_args", args=types.SimpleNamespace(tls_keyfile=None, tls_certfile=None))

    from aiohttp import web

    class _UserManager:
        users = {"default", "alice"}

        def get_request_user_id(self, request):
            user = request.headers.get("comfy-user", "default")
            if user not in self.users:
                raise KeyError("Unknown user: " + user)
            return user

        def get_request_user_filepath(self, request, file, create_dir=True):
            root = os.path.join(user_dir(), self.get_request_user_id(request))
            path = os.path.abspath(os.path.join(root, file))
            return path if os.path.commonpath((root, path)) == root else None

    class _Queue:
        def get_tasks_remaining(self):
            return 0

    class _PromptServer:
        instance = None

    ps = _PromptServer()
    ps.routes = web.RouteTableDef()
    ps.address = "127.0.0.1"
    ps.port = 8188
    ps.user_manager = _UserManager()
    ps.prompt_queue = _Queue()
    ps.sockets = {}
    ps.send_sync = lambda event, data, sid=None: SENT.append((event, {**data, "_sid": sid} if sid else data))
    _PromptServer.instance = ps
    _make_module("server", PromptServer=_PromptServer)


_install_stubs()

from ComfyArt import api
from ComfyArt.api import chat_store
from ComfyArt.bot import bot_asks
from ComfyArt.api.bot_turns import ACTIVE_TURNS, QUEUED
from ComfyArt.api.settings import SETTINGS_SPEC
from ComfyArt.bot import register_provider
from ComfyArt.bot.providers import AgentProvider, ProviderCaps, ProviderStatus, TurnResult


@pytest.fixture(autouse=True)
def fresh_user_dir(tmp_path):
    import folder_paths
    folder_paths.STATE["base"] = tmp_path
    SENT.clear()
    from server import PromptServer
    PromptServer.instance.sockets.clear()
    yield tmp_path


def write_settings(**values) -> None:
    from ComfyArt.api import settings
    current = settings.all_settings()
    current.update(values)
    settings.write_json(settings.app_path("settings.json"), current)


class FakeProvider(AgentProvider):
    id = "fake-test"
    label = "Fake"

    def __init__(self):
        self.script = []
        self.result = TurnResult(resume_token="tok-1")
        self.gate = None
        self.stopped = False
        self.last_turn = None

    async def probe(self):
        return ProviderStatus(available=True, version="0.0", logged_in=True)

    def capabilities(self):
        return ProviderCaps(stateful=True, tools="mcp")

    async def send(self, turn, emit, handle):
        self.last_turn = turn
        for ev in self.script:
            await emit(ev)
        if self.gate is not None:
            await self.gate.wait()
        if handle.stop_requested:
            return TurnResult(resume_token="tok-abort", aborted=True)
        return self.result

    async def stop(self, handle):
        self.stopped = True
        handle.stop_requested = True
        if self.gate is not None:
            self.gate.set()


class FakeStatelessProvider(FakeProvider):
    id = "fake-stateless"

    def capabilities(self):
        return ProviderCaps(stateful=False, tools="mcp")


@pytest.fixture()
def fake_provider(monkeypatch):
    provider = FakeProvider()
    register_provider(provider)
    monkeypatch.setitem(SETTINGS_SPEC, "bot-model-fake-test", "")
    return provider


@pytest.fixture()
def fake_stateless():
    provider = FakeStatelessProvider()
    register_provider(provider)
    return provider


@pytest.fixture()
async def bot_client():
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer

    import server
    write_settings(**{"enable-mcp": True, "enable-bot": True})
    ACTIVE_TURNS.clear()
    QUEUED.clear()
    bot_asks.PENDING.clear()
    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    client = TestClient(TestServer(app))
    await client.start_server()
    yield client
    ACTIVE_TURNS.clear()
    QUEUED.clear()
    bot_asks.PENDING.clear()
    await client.close()


async def wait_bot_done(client, chat_id, timeout=5.0):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        data = await (await client.get(f"/comfyart/bot/chats/{chat_id}")).json()
        msgs = data["messages"]
        if msgs and all(m["status"] != "streaming" for m in msgs):
            return data
        await asyncio.sleep(0.02)
    raise AssertionError("turn did not finish")
