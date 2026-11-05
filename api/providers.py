import os

from ..bot.providers import ProviderStatus
from ..bot import (
    ClaudeCodeProvider,
    CodexCodeProvider,
    DeepSeekHarnessProvider,
    HermesProvider,
    LocalLlmProvider,
    QwenCodeProvider,
    register_provider,
)
from ..bot.guide import HOST
from ._common import app_path
from .llm_key import is_wavespeed_url, llm_api_key
from .settings import get_setting


# #219: shown to the frontend, which turns it into the "set your WaveSpeed key" notice
NO_KEY_DETAIL = "no-wavespeed-key"


NO_KEY_ERROR = {
    "zh": "还没有设置 WaveSpeed Key，请先在 WaveSpeed Key 设置里填写。",
    "en": "No WaveSpeed key yet: set one in WaveSpeed key settings.",
}


def no_key_error(lang: str) -> str:
    """#227: the no-Key chat error follows the UI language; bilingual only when the language is unknown."""
    if lang in NO_KEY_ERROR:
        return NO_KEY_ERROR[lang]
    return f"{NO_KEY_ERROR['zh']} / {NO_KEY_ERROR['en']}"


class AgentLlmProvider(LocalLlmProvider):
    """The unchanged agent loop (built-in ComfyArt Agent); the key lookup also covers the WaveSpeed LLM
    default (#120). #219: no WaveSpeed key -> a clear status instead of a raw 401, and a saved model name
    keeps the agent usable when the endpoint's /models fails or is empty."""

    id = "local-llm"
    label = "ComfyArt Agent (built-in)"

    @staticmethod
    def _mcp_headers() -> dict:
        # #219: the in-process secret lets the built-in agent use the canvas tools while external MCP is off
        from .mcp import INTERNAL_HEADER, INTERNAL_TOKEN
        return {**LocalLlmProvider._mcp_headers(), INTERNAL_HEADER: INTERNAL_TOKEN}

    @property
    def unloads_lms_during_waits(self) -> bool:
        """#754: a WaveSpeed (hosted) endpoint has no local LM Studio to unload/reload; local URLs keep it."""
        base = self._base_url()
        return not (base and is_wavespeed_url(base))

    async def probe(self) -> ProviderStatus:
        base = self._base_url()
        if base and is_wavespeed_url(base) and not llm_api_key(base):
            return ProviderStatus(available=False, detail=NO_KEY_DETAIL)
        status = await super().probe()
        model = str(get_setting("bot-model-local-llm") or "").strip()
        if not status.available and base and model and status.detail != NO_KEY_DETAIL:
            return ProviderStatus(available=True, version=model, logged_in=True,
                                  detail=f"/models unavailable, using {model}")
        return status

    async def send(self, turn, emit, handle):
        base = self._base_url()
        if base and is_wavespeed_url(base) and not llm_api_key(base):
            from ..bot.providers import TurnResult

            return TurnResult(error=no_key_error(getattr(turn, "lang", "")))
        return await super().send(turn, emit, handle)

    def _max_steps(self) -> int:
        from ..bot.local_llm import _MAX_STEPS_ENV, max_steps_from
        if os.environ.get(_MAX_STEPS_ENV):
            return super()._max_steps()
        return max_steps_from(get_setting("bot-max-steps"))

    def _run_policy(self):
        """#391: user layer from Agent settings over system defaults (workspace / plan layers are
        reserved and empty locally); COMFYART_AGENT_MAX_STEPS still wins (deprecated)."""
        from ..bot.run_budget import resolve_policy
        return resolve_policy(workspace=None, user=user_policy_layer(), plan=None)

    def _run_store(self):
        return ensure_run_store()

    async def list_models(self) -> list[str]:
        models = await super().list_models()
        model = str(get_setting("bot-model-local-llm") or "").strip()
        return models or ([model] if model else [])

    def _api_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        key = llm_api_key(self._base_url())
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers


# #219: the built-in agent is listed first; external CLIs follow
register_provider(AgentLlmProvider(host=HOST, base_url=lambda: str(get_setting("bot-local-llm-url"))))
register_provider(ClaudeCodeProvider(host=HOST, home_dir=app_path("bot-home")))
register_provider(CodexCodeProvider(host=HOST, home_dir=app_path("bot-home-codex")))
register_provider(QwenCodeProvider(host=HOST, home_dir=app_path("bot-home-qwen")))
register_provider(DeepSeekHarnessProvider(host=HOST, home_dir=app_path("bot-home-deepseek-harness")))
register_provider(HermesProvider(host=HOST, home_dir=app_path("bot-home-hermes"),
                                 ssh_host=lambda: str(get_setting("bot-hermes-ssh-host")),
                                 profile=lambda: str(get_setting("bot-hermes-profile"))))


def user_policy_layer() -> dict:
    steps = get_setting("bot-max-steps")
    return {
        # The setting's default is 300 now, so a saved 80 is a real choice and is honored.
        "hard_cap_steps": steps,
        "wall_time_s": int(get_setting("agent-wall-time-min")) * 60,
        "credits_usd": get_setting("agent-credits-usd"),
        "token_window_multiple": get_setting("agent-token-window-multiple"),
        "agent.budget_loop": get_setting("agent-budget-loop"),
    }


def ensure_run_store():
    """#391: one SqliteRunStore per process. Creating it marks runs left 'running' by a previous
    process as paused(interrupted), so they can be continued from their last checkpoint."""
    from ..bot.run_store import get_run_store, set_run_store
    store = get_run_store()
    if store is None:
        from .run_store_sqlite import SqliteRunStore
        store = SqliteRunStore()
        store.mark_interrupted()
        set_run_store(store)
    return store
