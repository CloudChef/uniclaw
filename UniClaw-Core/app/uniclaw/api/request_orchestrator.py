"""Request orchestration pipeline for gateway-driven agent execution.

The orchestrator coordinates the main runtime path:
Gateway/API -> Workflow Engine -> Agent Router -> Skill Registry -> Agent Runner

High-level flow:
1. Receive the request from the gateway or API layer
2. Run intent recognition when workflow routing is enabled
3. Select the target agent from routing rules or intent results
4. Filter skills based on the selected agent configuration
5. Execute the run through `AgentRunner`
6. Return a streaming or aggregated response
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Callable, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

from app.uniclaw.agent.routing import (
    AgentConfig,
    AgentRouter,
    BindingRule,
    RoutingContext,
)
from app.uniclaw.agent.runner import AgentRunner
from app.uniclaw.agent.stream import StreamEvent
from app.uniclaw.core.deps import SkillDeps
from app.uniclaw.auth.models import UserInfo, ANONYMOUS_USER
from app.uniclaw.skills.registry import SkillMetadata, SkillRegistry
from app.uniclaw.session.manager import SessionManager
from app.uniclaw.workflow.engine import WorkflowEngine

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from app.uniclaw.core.provider_registry import ServiceProviderRegistry


class IntentType(str, Enum):
    """High-level request intent categories."""

    RESOURCE_QUERY = "resource_query"  # Look up resources or knowledge.
    TICKET_SUBMIT = "ticket_submit"    # Create or update ticket-like items.
    GENERAL_CHAT = "general_chat"      # Regular conversational requests.
    UNKNOWN = "unknown"                # Intent could not be classified.


@dataclass
class IntentResult:
    """Structured result returned by intent recognition.

    Attributes:
        intent: Classified intent type.
        confidence: Confidence score in the range `[0, 1]`.
        agent_id: Suggested agent identifier.
        extracted_entities: Structured entities extracted from the request.
        raw_response: Raw recognizer output for debugging.
    """
    intent: IntentType
    confidence: float = 0.0
    agent_id: str = ""
    extracted_entities: dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""


class AgentInstance:
    """Runtime wrapper around a configured PydanticAI agent."""
    
    def __init__(
        self,
        config: AgentConfig,
        pydantic_agent: "Agent",
        skills: list[SkillMetadata],
    ):
        """Initialize a runtime agent instance."""
        self.config = config
        self.agent = pydantic_agent
        self.skills = skills
        self.created_at = time.time()
    
    @property
    def id(self) -> str:
        return self.config.id
    
    @property
    def model(self) -> str:
        return self.config.model


class AgentFactory:
    """Build and cache runtime agents from agent configuration."""
    
    def __init__(
        self,
        skill_registry: SkillRegistry,
        default_model: str = "gpt-4o",
    ):
        """Initialize the factory with a skill registry and default model."""
        self.skill_registry = skill_registry
        self.default_model = default_model
        self._agent_cache: dict[str, AgentInstance] = {}
    
    def create(self, config: AgentConfig) -> AgentInstance:
        """Create or reuse an agent instance for the given configuration."""
        # Reuse cached instances when possible.
        if config.id in self._agent_cache:
            return self._agent_cache[config.id]

        # Filter the skill registry through the agent's tool policy.
        allowed_skills = self._filter_skills(config)

        # Create the underlying PydanticAI agent.
        from pydantic_ai import Agent
        
        model = config.model or self.default_model
        agent = Agent(
            model,
            deps_type=SkillDeps,
            system_prompt=self._build_system_prompt(config),
        )
        
        # Register the allowed skills as agent tools.
        for meta, handler in allowed_skills:
            agent.tool(handler, name=meta.name)
        
        instance = AgentInstance(
            config=config,
            pydantic_agent=agent,
            skills=[meta for meta, _ in allowed_skills],
        )
        
        self._agent_cache[config.id] = instance
        return instance
    
    def _filter_skills(
        self,
        config: AgentConfig,
    ) -> list[tuple[SkillMetadata, Any]]:
        """Filter the skill registry through the agent tool policy."""
        allowed = []
        for name in self.skill_registry.list_skills():
            skill = self.skill_registry.get(name)
            if skill and config.tools.is_allowed(name):
                allowed.append(skill)
        return allowed
    
    def _build_system_prompt(self, config: AgentConfig) -> str:
        """Build a minimal system prompt from agent metadata."""
        parts = [f"你是 {config.id} 智能助手。"]
        
        if config.metadata.get("role"):
            parts.append(f"角色：{config.metadata['role']}")
        if config.metadata.get("goal"):
            parts.append(f"目标：{config.metadata['goal']}")
        
        return "\n".join(parts)
    
    def invalidate(self, agent_id: str) -> bool:
        """Invalidate one cached agent instance."""
        if agent_id in self._agent_cache:
            del self._agent_cache[agent_id]
            return True
        return False
    
    def invalidate_all(self) -> int:
        """Invalidate all cached agent instances and return the count."""
        count = len(self._agent_cache)
        self._agent_cache.clear()
        return count


class IntentRecognizer:
    """Recognize a high-level request intent from user input."""
    
    INTENT_PROMPT = """分析用户输入，识别意图类型。

可选意图：
- resource_query: 查询云资源（虚拟机、存储、网络等）
- ticket_submit: 提交工单或服务请求
- general_chat: 一般对话或问答

用户输入：{user_input}

返回 JSON 格式：
{{"intent": "意图类型", "confidence": 0.0-1.0, "entities": {{}}}}
"""
    
    def __init__(
        self,
        llm_caller: Optional[Callable[[str], str]] = None,
    ):
        """Initialize the recognizer with an optional LLM callback."""
        self._llm_caller = llm_caller
    
    async def recognize(self, user_input: str) -> IntentResult:
        """Recognize the intent for a user request.

        The recognizer tries a fast keyword-based classifier first and falls
        back to the optional LLM callback when needed.
        """
        # Run the fast-path matcher first.
        fast_result = self._fast_match(user_input)
        if fast_result.confidence > 0.8:
            return fast_result
        
        # Fall back to the LLM recognizer when available.
        if self._llm_caller:
            try:
                prompt = self.INTENT_PROMPT.format(user_input=user_input)
                response = self._llm_caller(prompt)
                return self._parse_response(response)
            except Exception:
                pass
        
        return IntentResult(intent=IntentType.GENERAL_CHAT, confidence=0.5)
    
    def _fast_match(self, user_input: str) -> IntentResult:
        """Run lightweight keyword matching for common request types."""
        text = user_input.lower()
        
        # Resource lookup style requests.
        resource_keywords = ["查询", "查看", "虚拟机", "vm", "资源", "列表", "状态"]
        if any(kw in text for kw in resource_keywords):
            return IntentResult(
                intent=IntentType.RESOURCE_QUERY,
                confidence=0.85,
                agent_id="resource_agent",
            )
        
        # Ticket or service request style prompts.
        ticket_keywords = ["申请", "工单", "提交", "创建", "扩容", "新建"]
        if any(kw in text for kw in ticket_keywords):
            return IntentResult(
                intent=IntentType.TICKET_SUBMIT,
                confidence=0.85,
                agent_id="ticket_agent",
            )
        
        return IntentResult(intent=IntentType.UNKNOWN, confidence=0.3)
    
    def _parse_response(self, response: str) -> IntentResult:
        """Parse the JSON response returned by the LLM recognizer."""
        import json
        
        try:
            data = json.loads(response)
            intent_str = data.get("intent", "general_chat")
            
            intent_map = {
                "resource_query": IntentType.RESOURCE_QUERY,
                "ticket_submit": IntentType.TICKET_SUBMIT,
                "general_chat": IntentType.GENERAL_CHAT,
            }
            
            return IntentResult(
                intent=intent_map.get(intent_str, IntentType.GENERAL_CHAT),
                confidence=data.get("confidence", 0.7),
                extracted_entities=data.get("entities", {}),
                raw_response=response,
            )
        except Exception:
            return IntentResult(
                intent=IntentType.GENERAL_CHAT,
                confidence=0.5,
                raw_response=response,
            )


class RequestOrchestrator:
    """Coordinate intent recognition, routing, and agent execution.

    Example:
        ```python
        orchestrator = RequestOrchestrator(
            skill_registry=registry,
            session_manager=session_manager,
            agent_router=router,
        )

        async for event in orchestrator.process(
            user_input="hello",
            peer_id="user123",
            channel="telegram",
        ):
            if event.type == "assistant":
                print(event.content)
        ```
    """
    
    def __init__(
        self,
        skill_registry: SkillRegistry,
        session_manager: SessionManager,
        agent_router: Optional[AgentRouter] = None,
        intent_recognizer: Optional[IntentRecognizer] = None,
        agent_factory: Optional[AgentFactory] = None,
        service_provider_registry: Optional["ServiceProviderRegistry"] = None,
    ):
        """Initialize the request orchestrator."""
        self.skill_registry = skill_registry
        self.session_manager = session_manager
        self.agent_router = agent_router or AgentRouter()
        self.intent_recognizer = intent_recognizer or IntentRecognizer()
        self.agent_factory = agent_factory or AgentFactory(skill_registry)
        self.service_provider_registry = service_provider_registry
        
        # Default mapping from recognized intent to agent ID.
        self._intent_agent_map: dict[IntentType, str] = {
            IntentType.RESOURCE_QUERY: "resource_agent",
            IntentType.TICKET_SUBMIT: "ticket_agent",
            IntentType.GENERAL_CHAT: "main",
        }
    
    def register_intent_agent(self, intent: IntentType, agent_id: str) -> None:
        """Register the default agent used for a recognized intent."""
        self._intent_agent_map[intent] = agent_id
    
    async def process(
        self,
        user_input: str,
        peer_id: str,
        channel: str,
        *,
        user_token: str = "",
        user_info: Optional[UserInfo] = None,
        account_id: str = "",
        guild_id: str = "",
        chat_type: str = "dm",
        extra: Optional[dict] = None,
        max_tool_calls: int = 50,
        timeout_seconds: int = 600,
    ) -> AsyncIterator[StreamEvent]:
        """Process one user request and yield streaming events.

        Flow:
        intent recognition -> agent selection -> skill loading -> execution
        """
        # Resolve UserInfo: explicit user_info takes priority over legacy user_token
        resolved_user_info: UserInfo = (
            user_info
            if user_info is not None
            else (
                UserInfo(user_id="anonymous", raw_token=user_token)
                if user_token
                else ANONYMOUS_USER
            )
        )
        yield StreamEvent.lifecycle_start()
        
        try:
            # 1. Recognize the request intent.
            intent_result = await self.intent_recognizer.recognize(user_input)
            
            yield StreamEvent(
                type="intent",
                phase="recognized",
                metadata={
                    "intent": intent_result.intent.value,
                    "confidence": intent_result.confidence,
                },
            )
            
            # 2. Select the target agent.
            agent_config = await self._select_agent(
                intent_result=intent_result,
                peer_id=peer_id,
                channel=channel,
                account_id=account_id,
                guild_id=guild_id,
                chat_type=chat_type,
            )
            
            yield StreamEvent(
                type="agent",
                phase="selected",
                metadata={
                    "agent_id": agent_config.id,
                    "model": agent_config.model,
                },
            )
            
            # 3. Create the runtime agent instance and load its skills.
            agent_instance = self.agent_factory.create(agent_config)
            
            yield StreamEvent(
                type="skills",
                phase="loaded",
                metadata={
                    "count": len(agent_instance.skills),
                    "names": [s.name for s in agent_instance.skills],
                },
            )
            
            # 4. Build the session key for this request.
            session_scope = self.agent_router.get_session_scope(agent_config, RoutingContext(
                peer_id=peer_id,
                channel=channel,
                account_id=account_id,
                guild_id=guild_id,
                chat_type=chat_type,
            ))
            session_key = f"agent:{agent_config.id}:{channel}:{session_scope}:{peer_id}"
            
            # 5. Build request-scoped dependencies.
            deps_extra = extra or {}
            # Inject service-provider context when available.
            if self.service_provider_registry is not None:
                deps_extra["available_providers"] = (
                    self.service_provider_registry.get_available_providers_summary()
                )
                deps_extra["_service_provider_registry"] = self.service_provider_registry

            # Inject the Markdown skill snapshot for prompt construction.
            if hasattr(self, "skill_registry"):
                deps_extra["md_skills_snapshot"] = self.skill_registry.md_snapshot()

            deps = SkillDeps(
                user_info=resolved_user_info,
                peer_id=peer_id,
                session_key=session_key,
                channel=channel,
                extra=deps_extra,
            )
            
            # 6. Execute the request through the agent runner.
            runner = AgentRunner(
                agent=agent_instance.agent,
                session_manager=self.session_manager,
            )
            
            async for event in runner.run(
                session_key=session_key,
                user_message=user_input,
                deps=deps,
                max_tool_calls=max_tool_calls,
                timeout_seconds=timeout_seconds,
            ):
                yield event
            
        except Exception as e:
            yield StreamEvent.error_event(str(e))
        
        yield StreamEvent.lifecycle_end()
    
    async def _select_agent(
        self,
        intent_result: IntentResult,
        peer_id: str,
        channel: str,
        account_id: str,
        guild_id: str,
        chat_type: str,
    ) -> AgentConfig:
        """Select the target agent for the current request."""
        # Prefer the agent explicitly suggested by intent recognition.
        if intent_result.confidence > 0.7 and intent_result.agent_id:
            agent = self.agent_router.get_agent(intent_result.agent_id)
            if agent:
                return agent
        
        # Otherwise fall back to the default agent mapped to the intent.
        if intent_result.intent in self._intent_agent_map:
            agent_id = self._intent_agent_map[intent_result.intent]
            agent = self.agent_router.get_agent(agent_id)
            if agent:
                return agent
        
        # Finally fall back to routing rules.
        ctx = RoutingContext(
            peer_id=peer_id,
            channel=channel,
            account_id=account_id,
            guild_id=guild_id,
            chat_type=chat_type,
        )
        return self.agent_router.route(ctx)
    
    def get_stats(self) -> dict:
        """Return lightweight orchestrator statistics."""
        return {
            "registered_skills": len(self.skill_registry.list_skills()),
            "registered_agents": len(self.agent_router.list_agents()),
            "cached_agents": len(self.agent_factory._agent_cache),
            "intent_mappings": {
                k.value: v for k, v in self._intent_agent_map.items()
            },
        }
