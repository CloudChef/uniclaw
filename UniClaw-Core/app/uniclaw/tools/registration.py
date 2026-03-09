"""Register built-in tools into the skill registry."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from app.uniclaw.tools.base import ToolMetadata
from app.uniclaw.tools.catalog import ToolCatalog, ToolProfile, GROUP_TOOLS
from app.uniclaw.skills.registry import SkillRegistry, SkillMetadata

if TYPE_CHECKING:
    pass

# Registry entries map tool names to metadata and import targets.
_TOOL_REGISTRY: dict[str, tuple[ToolMetadata, str, str]] = {
    # name -> (metadata, module_path, function_name)
    "exec": (
        ToolMetadata(name="exec", description="Execute shell command", group="runtime", requires_approval=True),
        "app.uniclaw.tools.runtime.exec_tool",
        "exec_tool",
    ),
    "process": (
        ToolMetadata(name="process", description="Background process management", group="runtime"),
        "app.uniclaw.tools.runtime.process_tool",
        "process_tool",
    ),
    "read": (
        ToolMetadata(name="read", description="Read file content", group="fs"),
        "app.uniclaw.tools.filesystem.read_tool",
        "read_tool",
    ),
    "write": (
        ToolMetadata(name="write", description="Create/overwrite file", group="fs"),
        "app.uniclaw.tools.filesystem.write_tool",
        "write_tool",
    ),
    "edit": (
        ToolMetadata(name="edit", description="Precise string replacement edit", group="fs"),
        "app.uniclaw.tools.filesystem.edit_tool",
        "edit_tool",
    ),
    "delete_file": (
        ToolMetadata(name="delete_file", description="Delete file", group="fs", requires_approval=True),
        "app.uniclaw.tools.filesystem.delete_tool",
        "delete_file_tool",
    ),
    "browser": (
        ToolMetadata(name="browser", description="Browser automation", group="ui"),
        "app.uniclaw.tools.ui.browser_tool",
        "browser_tool",
    ),
    # Session tools
    "sessions_list": (
        ToolMetadata(name="sessions_list", description="List sessions", group="sessions"),
        "app.uniclaw.tools.sessions.list_tool",
        "sessions_list_tool",
    ),
    "sessions_history": (
        ToolMetadata(name="sessions_history", description="Get session conversation history", group="sessions"),
        "app.uniclaw.tools.sessions.history_tool",
        "sessions_history_tool",
    ),
    "sessions_send": (
        ToolMetadata(name="sessions_send", description="Send message to other sessions", group="sessions"),
        "app.uniclaw.tools.sessions.send_tool",
        "sessions_send_tool",
    ),
    "sessions_spawn": (
        ToolMetadata(name="sessions_spawn", description="Spawn isolated sub-agent", group="sessions"),
        "app.uniclaw.tools.sessions.spawn_tool",
        "sessions_spawn_tool",
    ),
    "subagents": (
        ToolMetadata(name="subagents", description="Manage running sub-agents", group="sessions"),
        "app.uniclaw.tools.sessions.subagents_tool",
        "subagents_tool",
    ),
    "session_status": (
        ToolMetadata(name="session_status", description="Current session status", group="sessions"),
        "app.uniclaw.tools.sessions.status_tool",
        "session_status_tool",
    ),
    # Memory tools
    "memory_search": (
        ToolMetadata(name="memory_search", description="Semantic search long-term memory", group="memory"),
        "app.uniclaw.tools.memory.search_tool",
        "memory_search_tool",
    ),
    "memory_get": (
        ToolMetadata(name="memory_get", description="Read memory file by offset", group="memory"),
        "app.uniclaw.tools.memory.get_tool",
        "memory_get_tool",
    ),
    # Web tools
    "web_search": (
        ToolMetadata(name="web_search", description="Web search", group="web"),
        "app.uniclaw.tools.web.search_tool",
        "web_search_tool",
    ),
    "web_fetch": (
        ToolMetadata(name="web_fetch", description="Fetch webpage content", group="web"),
        "app.uniclaw.tools.web.fetch_tool",
        "web_fetch_tool",
    ),
    # Provider tools
    "list_provider_instances": (
        ToolMetadata(name="list_provider_instances", description="List Provider service instances", group="providers"),
        "app.uniclaw.tools.providers.instance_tools",
        "list_provider_instances_tool",
    ),
    "select_provider_instance": (
        ToolMetadata(name="select_provider_instance", description="Select Provider service instance", group="providers"),
        "app.uniclaw.tools.providers.instance_tools",
        "select_provider_instance_tool",
    ),
}


def _import_tool_function(module_path: str, function_name: str):
    """Import and return a tool function by module path and symbol name."""
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, function_name)


def register_builtin_tools(
    registry: SkillRegistry,
    profile: str | ToolProfile = ToolProfile.FULL,
    allow: Optional[list[str]] = None,
    deny: Optional[list[str]] = None,
) -> list[str]:
    """Register built-in tools into the skill registry.

    Args:
        registry: Target skill registry.
        profile: Tool profile used as the base selection.
        allow: Optional allowlist of tools or groups.
        deny: Optional denylist of tools or groups.

    Returns:
        Names of tools that were successfully registered.
    """
    # Resolve the base tool set from the requested profile.
    profile_tools = ToolCatalog.get_tools_by_profile(profile)

    # Apply allow/deny filtering on top of the profile selection.
    filtered_tools = ToolCatalog.filter_tools(profile_tools, allow=allow, deny=deny)

    registered: list[str] = []
    for tool_name in filtered_tools:
        if tool_name not in _TOOL_REGISTRY:
            continue

        tool_meta, module_path, func_name = _TOOL_REGISTRY[tool_name]

        try:
            handler = _import_tool_function(module_path, func_name)
        except (ImportError, AttributeError):
            continue

        skill_meta = SkillMetadata(
            name=tool_name,
            description=tool_meta.description,
            category=f"builtin:{tool_meta.group}",
            location="built-in",
        )
        registry.register(skill_meta, handler)
        registered.append(tool_name)

    return registered
