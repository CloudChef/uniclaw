# -*- coding: utf-8 -*-
"""


REST API

implementsession management, Agent run, Skills, etc. REST.
corresponds to tasks.md 7.2.
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Header, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..session.manager import SessionManager
from ..session.context import SessionKey, SessionScope
from ..session.queue import SessionQueue, QueueMode
from ..skills.registry import SkillRegistry
from ..memory.manager import MemoryManager
from ..core.deps import SkillDeps
from ..auth.models import UserInfo, ANONYMOUS_USER
from .sse import SSEManager, SSEEvent, SSEEventType


# ============================================================================
# Pydantic / model
# ============================================================================

class SessionCreateRequest(BaseModel):
    """createsession"""
    agent_id: str = "main"
    channel: str = "api"
    chat_type: str = "dm"
    scope: str = "main"


class SessionResponse(BaseModel):
    """session"""
    session_key: str
    agent_id: str
    channel: str
    user_id: str
    created_at: datetime
    last_activity: datetime
    message_count: int
    total_tokens: int


class SessionResetRequest(BaseModel):
    """Reset a session"""
    archive: bool = True


class AgentRunRequest(BaseModel):
    """Agent run"""
    session_key: str
    message: str
    model: Optional[str] = None
    timeout_seconds: int = 600


class AgentRunResponse(BaseModel):
    """Agent run"""
    run_id: str
    status: str
    session_key: str


class AgentStatusResponse(BaseModel):
    """Agent"""
    run_id: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tokens_used: int = 0
    error: Optional[str] = None


class SkillExecuteRequest(BaseModel):
    """Skill execute"""
    skill_name: str
    args: dict[str, Any] = Field(default_factory=dict)


class SkillExecuteResponse(BaseModel):
    """Skill execute"""
    skill_name: str
    result: Any
    duration_ms: int


class MemorySearchRequest(BaseModel):
    """search"""
    query: str
    top_k: int = 10
    apply_recency: bool = True


class MemorySearchResult(BaseModel):
    """Search results"""
    id: str
    content: str
    score: float
    source: str
    timestamp: datetime
    highlights: list[str]


class MemoryWriteRequest(BaseModel):
    """"""
    content: str
    memory_type: str = "daily"  # daily / long_term
    source: str = ""
    tags: list[str] = Field(default_factory=list)
    section: str = "General"


class QueueModeRequest(BaseModel):
    """Queue mode"""
    mode: str  # collect / steer / followup / steer-backlog / interrupt


class StatusResponse(BaseModel):
    """"""
    session_key: str
    context_tokens: int
    input_tokens: int
    output_tokens: int
    queue_mode: str
    queue_size: int


class CompactRequest(BaseModel):
    """"""
    instruction: Optional[str] = None


# ============================================================================
# API context
# ============================================================================

@dataclass
class APIContext:
    """


API context
 
 contains inject.
 
"""
    session_manager: SessionManager
    session_queue: SessionQueue
    skill_registry: SkillRegistry
    memory_manager: Optional[MemoryManager] = None
    sse_manager: Optional[SSEManager] = None
    agent_runner: Optional[Any] = None  # AgentRunner instance
    
    # run
    active_runs: dict[str, dict[str, Any]] = None
    
    def __post_init__(self):
        if self.active_runs is None:
            self.active_runs = {}
        if self.sse_manager is None:
            self.sse_manager = SSEManager()


# context(apply)
_api_context: Optional[APIContext] = None


def set_api_context(ctx: APIContext) -> None:
    """API context"""
    global _api_context
    _api_context = ctx


def get_api_context() -> APIContext:
    """get API context"""
    if _api_context is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API context not initialized"
        )
    return _api_context


# ============================================================================
# Agent Execution Helper Functions
# ============================================================================

async def _execute_agent_run(
    ctx: APIContext,
    run_id: str,
    session_key: str,
    message: str,
    timeout_seconds: int,
    user_info: Optional[UserInfo] = None,
) -> None:
    """
    Execute Agent run in background and push events via SSE
    
    Args:
        ctx: API context
        run_id: Run ID
        session_key: Session key
        message: User message
        timeout_seconds: Timeout in seconds
        user_info: Authenticated user identity (injected by AuthMiddleware)
    """
    import asyncio
    
    _user_info = user_info or ANONYMOUS_USER
    
    try:
        # Push start event
        ctx.sse_manager.push_lifecycle(run_id, "start")
        
        # Check if AgentRunner is available
        if ctx.agent_runner:
            # Build per-user scoped SessionManager and MemoryManager.
            # Per spec §用户专属实例: each request gets managers scoped to
            # auth_user.user_id, activating per-user path isolation (tasks 9.1/10.1).
            user_id = _user_info.user_id
            scoped_session_mgr = SessionManager(
                agents_dir=str(ctx.session_manager.agents_dir),
                agent_id=ctx.session_manager.agent_id,
                user_id=user_id,
            )
            scoped_memory_mgr: Optional[MemoryManager] = None
            if ctx.memory_manager is not None:
                scoped_memory_mgr = MemoryManager(
                    workspace=str(ctx.memory_manager._workspace),
                    user_id=user_id,
                )

            # Execute with actual AgentRunner
            deps = SkillDeps(
                user_info=_user_info,
                session_key=session_key,
                session_manager=scoped_session_mgr,
                memory_manager=scoped_memory_mgr,
            )
            
            async for event in ctx.agent_runner.run(
                session_key=session_key,
                user_message=message,
                deps=deps,
                timeout_seconds=timeout_seconds
            ):
                # Convert StreamEvent to SSE event
                if event.type == "lifecycle":
                    ctx.sse_manager.push_lifecycle(run_id, event.phase)
                elif event.type == "assistant":
                    ctx.sse_manager.push_assistant(run_id, event.content)
                elif event.type == "tool":
                    ctx.sse_manager.push_tool(
                        run_id, 
                        event.tool, 
                        event.phase,
                        result=event.content if event.content else None
                    )
                elif event.type == "error":
                    ctx.sse_manager.push_error(run_id, event.error)
        else:
            # No AgentRunner available, return mock response
            await asyncio.sleep(0.5)
            ctx.sse_manager.push_assistant(
                run_id,
                f"Received message: {message}\n\nAgentRunner is not configured. Please set agent_runner to enable full functionality."
            )
        
        # Update run status
        if run_id in ctx.active_runs:
            ctx.active_runs[run_id]["status"] = "completed"
            ctx.active_runs[run_id]["completed_at"] = datetime.now(timezone.utc)
        
        # Push end event
        ctx.sse_manager.push_lifecycle(run_id, "end")
        
    except asyncio.TimeoutError:
        ctx.sse_manager.push_error(run_id, "Agent execution timed out")
        ctx.sse_manager.push_lifecycle(run_id, "error")
        if run_id in ctx.active_runs:
            ctx.active_runs[run_id]["status"] = "timeout"
            ctx.active_runs[run_id]["error"] = "Execution timed out"
            
    except Exception as e:
        error_msg = str(e)
        ctx.sse_manager.push_error(run_id, error_msg)
        ctx.sse_manager.push_lifecycle(run_id, "error")
        if run_id in ctx.active_runs:
            ctx.active_runs[run_id]["status"] = "error"
            ctx.active_runs[run_id]["error"] = error_msg
            
    finally:
        # Close SSE stream
        ctx.sse_manager.close_stream(run_id)


# ============================================================================
# create
# ============================================================================

def create_router() -> APIRouter:
    """create API"""
    router = APIRouter(prefix="/api", tags=["Uniclaw API"])
    
    # ----- session management API -----
    
    @router.post("/sessions", response_model=SessionResponse)
    async def create_session(
        request_obj: Request,
        request: SessionCreateRequest,
        ctx: APIContext = Depends(get_api_context)
    ) -> SessionResponse:
        """Create a new session"""
        # Derive user identity from the AuthMiddleware-injected UserInfo
        auth_user: UserInfo = getattr(request_obj.state, "user_info", ANONYMOUS_USER)
        
        key = SessionKey(
            agent_id=request.agent_id,
            channel=request.channel,
            chat_type=request.chat_type,
            user_id=auth_user.user_id,
        )
        session_key_str = key.to_string(scope=SessionScope(request.scope))
        
        session = await ctx.session_manager.get_or_create(session_key_str)
        
        return SessionResponse(
            session_key=session_key_str,
            agent_id=key.agent_id,
            channel=key.channel,
            user_id=key.user_id,
            created_at=session.created_at,
            last_activity=session.updated_at,
            message_count=getattr(session, "message_count", 0),
            total_tokens=session.total_tokens
        )
        
    @router.get("/sessions/{session_key}", response_model=SessionResponse)
    async def get_session(
        session_key: str,
        ctx: APIContext = Depends(get_api_context)
    ) -> SessionResponse:
        """get session"""
        session = await ctx.session_manager.get(session_key)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_key}"
            )
            
        key = SessionKey.from_string(session_key)
        
        return SessionResponse(
            session_key=session_key,
            agent_id=key.agent_id,
            channel=key.channel,
            user_id=key.user_id,
            created_at=session.created_at,
            last_activity=session.last_activity,
            message_count=session.message_count,
            total_tokens=session.total_tokens
        )
        
    @router.post("/sessions/{session_key}/reset")
    async def reset_session(
        session_key: str,
        request: SessionResetRequest,
        ctx: APIContext = Depends(get_api_context)
    ) -> dict[str, Any]:
        """Reset a session"""
        success = await ctx.session_manager.reset(
            session_key, archive=request.archive
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_key}"
            )
            
        return {"status": "reset", "session_key": session_key}
        
    @router.delete("/sessions/{session_key}")
    async def delete_session(
        session_key: str,
        ctx: APIContext = Depends(get_api_context)
    ) -> dict[str, Any]:
        """Delete a session"""
        success = await ctx.session_manager.delete(session_key)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_key}"
            )
            
        return {"status": "deleted", "session_key": session_key}
        
    # ----- Agent run API -----
    
    @router.post("/agent/run", response_model=AgentRunResponse)
    async def start_agent_run(
        request_obj: Request,
        request: AgentRunRequest,
        background_tasks: "BackgroundTasks",
        ctx: APIContext = Depends(get_api_context)
    ) -> AgentRunResponse:
        """Agent run"""
        run_id = str(uuid.uuid4())
        
        # Extract UserInfo injected by AuthMiddleware
        user_info: UserInfo = getattr(request_obj.state, "user_info", ANONYMOUS_USER)
        
        # run
        ctx.active_runs[run_id] = {
            "status": "running",
            "session_key": request.session_key,
            "started_at": datetime.now(timezone.utc),
            "message": request.message,
            "timeout_seconds": request.timeout_seconds
        }
        
        # create SSE stream
        ctx.sse_manager.create_stream(run_id)
        
        # run Agent in background
        background_tasks.add_task(
            _execute_agent_run,
            ctx,
            run_id,
            request.session_key,
            request.message,
            request.timeout_seconds,
            user_info,
        )
        
        return AgentRunResponse(
            run_id=run_id,
            status="running",
            session_key=request.session_key
        )
    
    @router.get("/agent/runs/{run_id}/stream")
    async def stream_agent_run(
        run_id: str,
        last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
        ctx: APIContext = Depends(get_api_context)
    ):
        """
        SSE streaming endpoint
        
        Returns streaming events for Agent run:
        - lifecycle: start/end events
        - assistant: assistant response content
        - tool: tool execution events
        - error: error events
        """
        if run_id not in ctx.active_runs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run not found: {run_id}"
            )
        
        return await ctx.sse_manager.create_response(
            run_id,
            last_event_id=last_event_id
        )
        
    @router.get("/agent/runs/{run_id}", response_model=AgentStatusResponse)
    async def get_agent_status(
        run_id: str,
        ctx: APIContext = Depends(get_api_context)
    ) -> AgentStatusResponse:
        """get Agent run"""
        run_info = ctx.active_runs.get(run_id)
        
        if not run_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run not found: {run_id}"
            )
            
        return AgentStatusResponse(
            run_id=run_id,
            status=run_info.get("status", "unknown"),
            started_at=run_info.get("started_at"),
            completed_at=run_info.get("completed_at"),
            tokens_used=run_info.get("tokens_used", 0),
            error=run_info.get("error")
        )
        
    @router.post("/agent/runs/{run_id}/abort")
    async def abort_agent_run(
        run_id: str,
        ctx: APIContext = Depends(get_api_context)
    ) -> dict[str, Any]:
        """in Agent run"""
        run_info = ctx.active_runs.get(run_id)
        
        if not run_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run not found: {run_id}"
            )
            
        run_info["status"] = "aborted"
        # in through abort_signal implement
        
        return {"status": "aborted", "run_id": run_id}
        
    # ----- Skills API -----
    
    @router.get("/skills")
    async def list_skills(
        ctx: APIContext = Depends(get_api_context)
    ) -> dict[str, Any]:
        """available Skills"""
        snapshot = ctx.skill_registry.snapshot()
        return {
            "skills": [
                {
                    "name": s.name,
                    "description": s.description,
                    "category": s.category,
                    "tags": s.tags
                }
                for s in snapshot
            ]
        }
        
    @router.post("/skills/execute", response_model=SkillExecuteResponse)
    async def execute_skill(
        request: SkillExecuteRequest,
        ctx: APIContext = Depends(get_api_context)
    ) -> SkillExecuteResponse:
        """execute Skill"""
        import time
        start = time.monotonic()
        
        try:
            result = await ctx.skill_registry.execute(
                request.skill_name,
                **request.args
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Skill execution failed: {str(e)}"
            )
            
        duration_ms = int((time.monotonic() - start) * 1000)
        
        return SkillExecuteResponse(
            skill_name=request.skill_name,
            result=result,
            duration_ms=duration_ms
        )
        
    # ----- API -----
    
    @router.post("/memory/search")
    async def search_memory(
        request: MemorySearchRequest,
        ctx: APIContext = Depends(get_api_context)
    ) -> dict[str, Any]:
        """search"""
        if not ctx.memory_manager:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Memory system not configured"
            )
            
        # use Hybrid-Searcher
        # implement:return
        return {"results": [], "query": request.query}
        
    @router.post("/memory/write")
    async def write_memory(
        request: MemoryWriteRequest,
        ctx: APIContext = Depends(get_api_context)
    ) -> dict[str, Any]:
        """"""
        if not ctx.memory_manager:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Memory system not configured"
            )
            
        if request.memory_type == "daily":
            entry = await ctx.memory_manager.write_daily(
                request.content,
                source=request.source,
                tags=request.tags
            )
        else:
            entry = await ctx.memory_manager.write_long_term(
                request.content,
                source=request.source,
                tags=request.tags,
                section=request.section
            )
            
        return {
            "id": entry.id,
            "memory_type": request.memory_type,
            "timestamp": entry.timestamp.isoformat()
        }
        
    # ----- API -----
    
    @router.get("/sessions/{session_key}/status", response_model=StatusResponse)
    async def get_status(
        session_key: str,
        ctx: APIContext = Depends(get_api_context)
    ) -> StatusResponse:
        """get session"""
        session = await ctx.session_manager.get(session_key)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_key}"
            )
            
        queue_info = ctx.session_queue.get_info(session_key)
        
        return StatusResponse(
            session_key=session_key,
            context_tokens=session.context_tokens,
            input_tokens=session.input_tokens,
            output_tokens=session.output_tokens,
            queue_mode=queue_info.get("mode", "collect") if queue_info else "collect",
            queue_size=queue_info.get("size", 0) if queue_info else 0
        )
        
    @router.post("/sessions/{session_key}/queue")
    async def set_queue_mode(
        session_key: str,
        request: QueueModeRequest,
        ctx: APIContext = Depends(get_api_context)
    ) -> dict[str, Any]:
        """Queue mode"""
        try:
            mode = QueueMode(request.mode)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid queue mode: {request.mode}"
            )
            
        ctx.session_queue.set_mode(session_key, mode)
        
        return {"session_key": session_key, "queue_mode": request.mode}
        
    @router.post("/sessions/{session_key}/compact")
    async def trigger_compact(
        session_key: str,
        request: CompactRequest,
        ctx: APIContext = Depends(get_api_context)
    ) -> dict[str, Any]:
        """trigger"""
        session = await ctx.session_manager.get(session_key)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_key}"
            )
            
        # at Compaction-Pipeline in
        # return
        return {
            "session_key": session_key,
            "status": "compaction_triggered",
            "instruction": request.instruction
        }
        
    # ----- check -----
    
    @router.get("/health")
    async def health_check() -> dict[str, Any]:
        """check"""
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    return router
