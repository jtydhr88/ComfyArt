import contextvars

BOT_CHAT_ID: contextvars.ContextVar[str] = contextvars.ContextVar("comfyart_bot_chat", default="")
PROJECT: contextvars.ContextVar[str] = contextvars.ContextVar("comfyart_project", default="")
# #730: paid-guard bucket (real bot_chat, or __noturn__:<session/ip> when the call has no turn)
GUARD_CHAT_ID: contextvars.ContextVar[str] = contextvars.ContextVar("comfyart_guard_chat", default="")
MCP_EXTERNAL: contextvars.ContextVar[bool] = contextvars.ContextVar("comfyart_mcp_external", default=False)
