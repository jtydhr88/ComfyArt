"""#41 guard: every original (upstream 5231d59) Agent feature is kept on main.

Rule (#78): keep all original features, only swap local models for cloud ones.
`custom_workflow` was restored as a cloud feature by #75 and is now required too.
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Extracted from `git show 5231d59:api/mcp_tools/canvas.py` (39 `_tool(` keys).
UPSTREAM_TOOLS = [
    "get_canvas",
    "view_canvas",
    "list_models",
    "brand_kits",
    "generate_image",
    "generate_video",
    "edit_image",
    "animate_image",
    "upscale_image",
    "remove_background",
    "expand_image",
    "split_layers",
    "change_angle",
    "replace_text",
    "edit_region",
    "erase_region",
    "move_object",
    "style_transfer",
    "vectorize_image",
    "upscale_video",
    "remove_video_background",
    "extend_video",
    "generate_music",
    "generate_sound_effect",
    "text_to_speech",
    "edit_elements",
    "create_mockup",
    "place_design",
    "place_html",
    "create_slides",
    "add_text",
    "add_shape",
    "create_frame",
    "update_shapes",
    "delete_shapes",
    "focus",
    "memory",
    "skill",
    "custom_workflow",
]

# Extracted from `git show 5231d59:src/botCommands.ts` (frontend handler keys).
UPSTREAM_FRONTEND_HANDLERS = [
    "animate_image",
    "change_angle",
    "create_mockup",
    "custom_workflow",
    "edit_elements",
    "edit_image",
    "edit_region",
    "erase_region",
    "expand_image",
    "extend_video",
    "generate_image",
    "generate_music",
    "generate_sound_effect",
    "generate_video",
    "list_models",
    "move_object",
    "remove_background",
    "remove_video_background",
    "replace_text",
    "split_layers",
    "style_transfer",
    "text_to_speech",
    "upscale_image",
    "upscale_video",
    "wait_generation",
]

# From `git show 5231d59:bot/guide.py` (host ComfyUI MCP tools, kept as-is).
UPSTREAM_COMFY_MCP_ALLOWED_TOOLS = [
    "server_info", "nodes", "validate_workflow", "search_models",
    "search_templates", "get_template", "list_workflow_slots",
    "list_workflow_notes", "workflow_deps", "node_dependencies",
    "system_stats", "which",
]

PENDING: set = set()  # #75 restored custom_workflow; nothing pending


def _missing(expected, actual):
    return sorted(set(expected) - PENDING - set(actual))


def test_agent_tools_superset_of_upstream():
    assert len(UPSTREAM_TOOLS) == 39
    text = (ROOT / "api/mcp_tools/canvas.py").read_text(encoding="utf-8")
    main = set(re.findall(r'^\s*"([a-z_0-9]+)": _tool\(', text, re.M))
    missing = _missing(UPSTREAM_TOOLS, main)
    assert not missing, f"Agent tools missing vs upstream 5231d59: {missing}"


def test_comfy_mcp_allowed_tools_kept():
    # #754: the list now lives in the vendored kit (bot/agent_host.py); bot/guide.py re-exports it.
    allowed = None
    for node in (n for f in ("bot/agent_host.py", "bot/guide.py")
                 for n in ast.parse((ROOT / f).read_text(encoding="utf-8")).body):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "COMFY_MCP_ALLOWED_TOOLS" for t in node.targets
        ):
            allowed = ast.literal_eval(node.value)
    assert allowed is not None, "COMFY_MCP_ALLOWED_TOOLS not found in bot/agent_host.py or bot/guide.py"
    missing = _missing(UPSTREAM_COMFY_MCP_ALLOWED_TOOLS, allowed)
    assert not missing, f"COMFY_MCP_ALLOWED_TOOLS missing vs upstream: {missing}"


def test_frontend_handlers_kept():
    text = (ROOT / "src/botCommands.ts").read_text(encoding="utf-8")
    main = set(re.findall(r"^  ([a-z_0-9]+): \(", text, re.M))
    # list_models moved to the backend (#95): api/mcp_tools/canvas.py _list_models (paged, 4000-char cap) always
    # answered the MCP tool, so the page handler was unreachable; tests/test_list_models_backend_only.py guards it.
    missing = [h for h in _missing(UPSTREAM_FRONTEND_HANDLERS, main) if h != "list_models"]
    assert not missing, f"src/botCommands.ts handlers missing vs upstream: {missing}"
