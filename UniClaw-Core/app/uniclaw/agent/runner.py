"""Streaming agent runner built on top of `PydanticAI.iter()`.

The runner adds checkpoint-style controls around agent execution:
- abort-signal checks
- timeout and context checks
- tool-call safety limits
- steering message injection from the session queue

Supported hooks:
`before_agent_start`, `llm_input`, `llm_output`, `before_tool_call`,
`after_tool_call`, and `agent_end`
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager, nullcontext
from typing import AsyncIterator, Optional, Any, TYPE_CHECKING

from app.uniclaw.core.deps import SkillDeps
from app.uniclaw.agent.stream import StreamEvent
from app.uniclaw.agent.compaction import CompactionPipeline, CompactionConfig
from app.uniclaw.agent.prompt_builder import PromptBuilder, PromptBuilderConfig

if TYPE_CHECKING:
    from app.uniclaw.session.manager import SessionManager
    from app.uniclaw.session.queue import SessionQueue
    from app.uniclaw.hooks.system import HookSystem


class AgentRunner:
    """Execute a streaming PydanticAI agent with runtime safeguards."""
    
    def __init__(
        self,
        agent: Any,  # pydantic_ai.Agent
        session_manager: "SessionManager",
        prompt_builder: Optional[PromptBuilder] = None,
        compaction: Optional[CompactionPipeline] = None,
        hook_system: Optional["HookSystem"] = None,
        session_queue: Optional["SessionQueue"] = None,
    ):
        """Initialize the agent runner.

        Args:
            agent: PydanticAI agent instance.
            session_manager: Session manager used for transcript persistence.
            prompt_builder: Runtime system prompt builder.
            compaction: Optional compaction pipeline.
            hook_system: Optional hook dispatcher.
            session_queue: Optional queue used for steering message injection.
        """
        self.agent = agent
        self.sessions = session_manager
        self.prompt_builder = prompt_builder or PromptBuilder(PromptBuilderConfig())
        self.compaction = compaction or CompactionPipeline(CompactionConfig())
        self.hooks = hook_system
        self.queue = session_queue
    
    async def run(
        self,
        session_key: str,
        user_message: str,
        deps: SkillDeps,
        *,
        max_tool_calls: int = 50,
        timeout_seconds: int = 600,
    ) -> AsyncIterator[StreamEvent]:
        """Execute one agent turn as a stream of runtime events."""
        start_time = time.monotonic()
        tool_calls_count = 0
        compaction_applied = False
        persist_override_messages: Optional[list[dict]] = None
        persist_override_base_len: int = 0

        try:
            yield StreamEvent.lifecycle_start()

            # --:session + build prompt --
            session = await self.sessions.get_or_create(session_key)
            transcript = await self.sessions.load_transcript(session_key)
            message_history = self._build_message_history(transcript)

            system_prompt = self._build_system_prompt(session=session, deps=deps)
            if self.hooks:
                prompt_ctx = await self.hooks.trigger(
                    "before_prompt_build",
                    {
                        "session_key": session_key,
                        "user_message": user_message,
                        "system_prompt": system_prompt,
                    },
                )
                system_prompt = prompt_ctx.get("system_prompt", system_prompt)

            # at iter,.
            if message_history and self.compaction.should_compact(message_history, session):
                if self.hooks:
                    await self.hooks.trigger(
                        "before_compaction",
                        {
                            "session_key": session_key,
                            "message_count": len(message_history),
                        },
                    )
                yield StreamEvent.compaction_start()
                compressed_history = await self.compaction.compact(message_history, session)
                message_history = self._normalize_messages(compressed_history)
                await self.sessions.mark_compacted(session_key)
                compaction_applied = True
                yield StreamEvent.compaction_end()
                if self.hooks:
                    await self.hooks.trigger(
                        "after_compaction",
                        {
                            "session_key": session_key,
                            "message_count": len(message_history),
                        },
                    )

            # -- hook:before_agent_start --
            if self.hooks:
                start_ctx = await self.hooks.trigger(
                    "before_agent_start",
                    {
                        "session_key": session_key,
                        "user_message": user_message,
                    },
                )
                user_message = start_ctx.get("user_message", user_message)

                # llm_input at leastat start trigger
                await self.hooks.trigger(
                    "llm_input",
                    {
                        "session_key": session_key,
                        "user_message": user_message,
                        "system_prompt": system_prompt,
                        "message_history": message_history,
                    },
                )

            # -- inject user_message to deps, for Skills --
            deps.user_message = user_message

            # ========================================
            # :PydanticAI iter()
            # ========================================
            try:
                async with self._run_iter_with_optional_override(
                    user_message=user_message,
                    deps=deps,
                    message_history=message_history,
                    system_prompt=system_prompt,
                ) as agent_run:

                    async for node in agent_run:
                        # -- checkpoint 1:abort_signal --
                        if deps.is_aborted():
                            yield StreamEvent.lifecycle_aborted()
                            break

                        # -- checkpoint 2:--
                        if time.monotonic() - start_time > timeout_seconds:
                            yield StreamEvent.error_event("timeout")
                            break

                        # -- checkpoint 3:context -> trigger --
                        current_messages = self._normalize_messages(agent_run.all_messages())
                        if self.compaction.should_compact(current_messages, session):
                            if self.hooks:
                                await self.hooks.trigger(
                                    "before_compaction",
                                    {
                                        "session_key": session_key,
                                        "message_count": len(current_messages),
                                    },
                                )
                            yield StreamEvent.compaction_start()
                            compressed = await self.compaction.compact(current_messages, session)
                            persist_override_messages = self._normalize_messages(compressed)
                            persist_override_base_len = len(current_messages)
                            await self.sessions.mark_compacted(session_key)
                            compaction_applied = True
                            yield StreamEvent.compaction_end()
                            if self.hooks:
                                await self.hooks.trigger(
                                    "after_compaction",
                                    {
                                        "session_key": session_key,
                                        "message_count": len(persist_override_messages),
                                    },
                                )

                        # -- hook:llm_input() --
                        if self.hooks and self._is_model_request_node(node):
                            await self.hooks.trigger(
                                "llm_input",
                                {
                                    "session_key": session_key,
                                    "user_message": user_message,
                                    "system_prompt": system_prompt,
                                    "message_history": current_messages,
                                },
                            )

                        # Emit model output chunks as assistant deltas.
                        if hasattr(node, "content") and node.content:
                            content = str(node.content)
                            if self.hooks:
                                await self.hooks.trigger(
                                    "llm_output",
                                    {
                                        "session_key": session_key,
                                        "content": content,
                                    },
                                )
                            yield StreamEvent.assistant_delta(content)

                        # Surface tool activity in the event stream.
                        if hasattr(node, "tool_name"):
                            tool_calls_count += 1
                            tool_name = str(node.tool_name)

                            # Abort before starting another tool when requested.
                            if deps.is_aborted():
                                yield StreamEvent.lifecycle_aborted()
                                break

                            # Enforce the tool-call safety cap.
                            if tool_calls_count > max_tool_calls:
                                yield StreamEvent.error_event("max_tool_calls_exceeded")
                                break

                            # -- hook:before_tool_call --
                            if self.hooks:
                                await self.hooks.trigger("before_tool_call", {"tool": tool_name})

                            yield StreamEvent.tool_start(tool_name)
                            # PydanticAI executes the tool internally.
                            yield StreamEvent.tool_end(tool_name)

                            # -- hook:after_tool_call --
                            if self.hooks:
                                await self.hooks.trigger("after_tool_call", {"tool": tool_name})

                            # Inject queued steering messages after each tool call.
                            if self.queue:
                                steer_messages = self.queue.get_steer_messages(session_key)
                                if steer_messages:
                                    combined = "\n".join(steer_messages)
                                    yield StreamEvent.assistant_delta(f"\n[用户补充]: {combined}\n")

                    # Persist the final normalized transcript.
                    final_messages = self._normalize_messages(agent_run.all_messages())
                    if persist_override_messages is not None:
                        if len(final_messages) > persist_override_base_len > 0:
                            # Preserve override messages and append new run output.
                            final_messages = persist_override_messages + final_messages[persist_override_base_len:]
                        else:
                            final_messages = persist_override_messages
                    await self.sessions.persist_transcript(session_key, final_messages)

            except Exception as e:
                # Surface agent runtime errors as stream events.
                yield StreamEvent.error_event(f"agent_error: {str(e)}")

            # -- hook:agent_end --
            if self.hooks:
                await self.hooks.trigger(
                    "agent_end",
                    {
                        "session_key": session_key,
                        "tool_calls_count": tool_calls_count,
                        "compaction_applied": compaction_applied,
                    },
                )

            yield StreamEvent.lifecycle_end()

        except Exception as e:
            yield StreamEvent.error_event(str(e))

    @asynccontextmanager
    async def _run_iter_with_optional_override(
        self,
        *,
        user_message: str,
        deps: SkillDeps,
        message_history: list[dict],
        system_prompt: str,
    ):
        """Run `agent.iter()` with optional system-prompt overrides."""
        override_factory = getattr(self.agent, "override", None)
        if callable(override_factory) and system_prompt:
            try:
                override_cm = override_factory(system_prompt=system_prompt)
            except TypeError:
                override_cm = nullcontext()
        else:
            override_cm = nullcontext()

        if hasattr(override_cm, "__aenter__"):
            async with override_cm:
                async with self.agent.iter(
                    user_message,
                    deps=deps,
                    message_history=message_history,
                ) as agent_run:
                    yield agent_run
            return

        with override_cm:
            async with self.agent.iter(
                user_message,
                deps=deps,
                message_history=message_history,
            ) as agent_run:
                yield agent_run

    def _build_system_prompt(self, session: Any, deps: SkillDeps) -> str:
        """Build the runtime system prompt for the current session."""
        skills = self._collect_skills_snapshot(deps)
        tools = self._collect_tools_snapshot()
        md_skills = self._collect_md_skills_snapshot(deps)
        return self.prompt_builder.build(
            session=session, skills=skills, tools=tools, md_skills=md_skills,
            user_info=deps.user_info,
        )

    def _collect_skills_snapshot(self, deps: SkillDeps) -> list[dict]:
        """Read a structured skills snapshot from `deps.extra` if present."""
        extra = deps.extra if isinstance(deps.extra, dict) else {}
        for key in ("skills_snapshot", "skills"):
            value = extra.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []

    def _collect_md_skills_snapshot(self, deps: SkillDeps) -> list[dict]:
        """Read a Markdown-skill snapshot from `deps.extra` if present."""
        extra = deps.extra if isinstance(deps.extra, dict) else {}
        for key in ("md_skills_snapshot", "md_skills"):
            value = extra.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []

    def _collect_tools_snapshot(self) -> list[dict]:
        """Collect tool name and description pairs for prompt building."""
        raw_tools = getattr(self.agent, "tools", None)
        if not raw_tools:
            return []

        tools: list[dict] = []
        for tool in raw_tools:
            if isinstance(tool, dict):
                name = tool.get("name")
                description = tool.get("description", "")
            else:
                name = getattr(tool, "name", None) or getattr(tool, "__name__", None)
                description = getattr(tool, "description", "") or getattr(tool, "__doc__", "") or ""
            if name:
                tools.append({"name": str(name), "description": str(description).strip()})
        return tools

    def _normalize_messages(self, messages: list[Any]) -> list[dict]:
        """Normalize agent messages into session-manager dictionaries."""
        normalized: list[dict] = []
        for msg in messages or []:
            if isinstance(msg, dict):
                item = dict(msg)
                item.setdefault("role", "assistant")
                item.setdefault("content", "")
                normalized.append(item)
                continue

            role = getattr(msg, "role", "assistant")
            content = getattr(msg, "content", "")
            item = {
                "role": str(role),
                "content": content if isinstance(content, str) else str(content),
            }
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                item["tool_calls"] = tool_calls
            normalized.append(item)
        return normalized

    def _is_model_request_node(self, node: Any) -> bool:
        """Return whether a node represents a model request boundary."""
        node_type = type(node).__name__.lower()
        return "modelrequest" in node_type or node_type.endswith("requestnode")
    
    def _build_message_history(self, transcript: list) -> list[dict]:
        """Convert transcript entries into PydanticAI-compatible messages."""
        messages = []
        for entry in transcript:
            msg = {
                "role": entry.role,
                "content": entry.content,
            }
            if entry.tool_calls:
                msg["tool_calls"] = entry.tool_calls
            messages.append(msg)
        return messages
    
    async def run_single(
        self,
        user_message: str,
        deps: SkillDeps,
        *,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Run a single non-streaming agent call."""
        # Simplified helper that bypasses the streaming session pipeline.
        try:
            result = await self.agent.run(
                user_message,
                deps=deps,
            )
            return result.data if hasattr(result, "data") else str(result)
        except Exception as e:
            return f"[错误: {str(e)}]"


class MockAgentRunner:
    """Testing stub that returns predefined responses and tool calls."""
    
    def __init__(
        self,
        responses: Optional[list[str]] = None,
        tool_calls: Optional[list[dict]] = None,
    ):
        """Initialize the mock runner with scripted outputs."""
        self.responses = responses or ["这是一个 Mock 响应。"]
        self.tool_calls = tool_calls or []
        self._response_index = 0
        self._tool_index = 0
    
    async def run(
        self,
        session_key: str,
        user_message: str,
        deps: SkillDeps,
        **kwargs,
    ) -> AsyncIterator[StreamEvent]:
        """Yield a deterministic mock event stream."""
        yield StreamEvent.lifecycle_start()
        
        # Replay scripted tool calls first.
        for tc in self.tool_calls:
            tool_name = tc.get("name", "mock_tool")
            yield StreamEvent.tool_start(tool_name)
            await asyncio.sleep(0.1)  # 
            yield StreamEvent.tool_end(tool_name, tc.get("result", ""))
        
        # return
        response = self.responses[self._response_index % len(self.responses)]
        self._response_index += 1
        
        # return
        chunk_size = 50
        for i in range(0, len(response), chunk_size):
            chunk = response[i:i + chunk_size]
            yield StreamEvent.assistant_delta(chunk)
            await asyncio.sleep(0.05)  # streaming
        
        yield StreamEvent.lifecycle_end()
