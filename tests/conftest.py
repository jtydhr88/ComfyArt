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


os.environ.setdefault("COMFYART_SKIP_KEY_CHECK", "1")
_install_stubs()

# Bind `ComfyArt` to THIS checkout even when it lives in a worktree dir with another name
# (otherwise a sibling ../ComfyArt with a stale dist/ gets imported and served).
if "ComfyArt" not in sys.modules or Path(getattr(sys.modules["ComfyArt"], "__file__", "") or "").resolve().parent != _REPO:
    import importlib.util as _ilu
    for _k in [k for k in sys.modules if k == "ComfyArt" or k.startswith("ComfyArt.")]:
        del sys.modules[_k]
    _spec = _ilu.spec_from_file_location("ComfyArt", _REPO / "__init__.py", submodule_search_locations=[str(_REPO)])
    _mod = _ilu.module_from_spec(_spec)
    sys.modules["ComfyArt"] = _mod
    _spec.loader.exec_module(_mod)
from ComfyArt import api
from ComfyArt.api import bot_asks, chat_store
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
    bot_asks.ANSWERED_RUN_APPROVALS.clear()
    from ComfyArt.api.ask_store import set_store
    set_store(None)  # fresh JsonAskStore under tmp user dir
    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    client = TestClient(TestServer(app))
    await client.start_server()
    yield client
    ACTIVE_TURNS.clear()
    QUEUED.clear()
    bot_asks.PENDING.clear()
    bot_asks.ANSWERED_RUN_APPROVALS.clear()
    from ComfyArt.api.ask_store import set_store
    set_store(None)
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


# #131: the frontend tests bundle src/ with rolldown and run it in node. Without `npm ci` they used to skip quietly
# (~9 tests), so a green run proved nothing about the frontend. Fail the session up front instead; set
# COMFYART_SKIP_NODE_TESTS=1 to knowingly run the Python-only subset (the node tests then skip, as before).
NODE_HINT = ("frontend tests need node + node_modules: run `npm ci` in the repo root (or scripts/test.sh, which does it), "
             "or set COMFYART_SKIP_NODE_TESTS=1 to skip them on purpose")


def node_ready() -> bool:
    import shutil
    return (_REPO / "node_modules" / ".bin" / "rolldown").exists() and shutil.which("node") is not None


def pytest_sessionstart(session):
    if not node_ready() and os.environ.get("COMFYART_SKIP_NODE_TESTS") != "1":
        raise pytest.UsageError(NODE_HINT)


# --- #712 no-spend: under scripts/gate.sh (GATE=1) paid keys are unset and outbound network is blocked ---
GATE_PAID_KEYS = ("WAVESPEED_API_KEY", "KIE_API_KEY")
_LOCAL = ("127.0.0.1", "::1", "localhost", "0.0.0.0")


class GateNetworkBlocked(OSError):
    pass


def _gate_guard() -> None:
    import socket

    for k in GATE_PAID_KEYS:
        os.environ.pop(k, None)
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def _check(sock, addr):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            host = addr[0] if isinstance(addr, tuple) else addr
            if host not in _LOCAL:
                raise GateNetworkBlocked(f"gate: outbound network blocked ({host}); use a localhost mock (#712)")

    def connect(self, addr):
        _check(self, addr)
        return real_connect(self, addr)

    def connect_ex(self, addr):
        _check(self, addr)
        return real_connect_ex(self, addr)

    socket.socket.connect, socket.socket.connect_ex = connect, connect_ex
    real_gai = socket.getaddrinfo

    def getaddrinfo(host, *a, **kw):
        if host not in _LOCAL and host is not None:
            raise GateNetworkBlocked(f"gate: DNS lookup blocked ({host}) (#712)")
        return real_gai(host, *a, **kw)

    socket.getaddrinfo = getaddrinfo


if os.environ.get("GATE") == "1":
    _gate_guard()
