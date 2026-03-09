"""
Per-request dependency container for tools and skills.

`SkillDeps` is the typed payload passed through `RunContext[SkillDeps]`.
It gives tools and skills access to request-scoped metadata such as the
authenticated user identity, peer identity, session key, and optional
extra context.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from app.uniclaw.auth.models import UserInfo, ANONYMOUS_USER

if TYPE_CHECKING:
    from app.uniclaw.session.manager import SessionManager


@dataclass
class SkillDeps:
    """
    Request-scoped dependencies for ``RunContext[SkillDeps]``.

    Attributes:
        user_info: Authenticated user identity (always present; defaults to
            anonymous when no auth is configured).
        smartcmp_client: Optional SmartCMP HTTP client.
        peer_id: Peer identifier, such as a user or group ID.
        session_key: Stable session key for the current conversation.
        channel: Source channel name for the current request.
        abort_signal: Abort signal shared across the current run.
        session_manager: Optional session manager injected by the caller.
        extra: Additional request-scoped context values.

    Backward compatibility:
        ``deps.user_token`` returns ``deps.user_info.raw_token`` so that
        existing Skills that access the old ``user_token`` attribute continue
        to work without modification.

    Example usage::

        from pydantic_ai import Agent, RunContext
        from app.uniclaw.core.deps import SkillDeps

        agent = Agent("openai:doubao-pro-32k", deps_type=SkillDeps)

        @agent.tool
        async def query_cloud_entries(ctx: RunContext[SkillDeps], cloud_type: str = None):
            deps = ctx.deps
            headers = {"CloudChef-Authenticate": deps.user_token}
            async with httpx.AsyncClient() as client:
                resp = await client.get("/v1/cloudEntries", headers=headers)
                return resp.json()

        result = await agent.run(
            user_message,
            deps=SkillDeps(
                user_info=UserInfo(user_id="u-abc", raw_token=token),
                peer_id=uid,
                session_key=session_key,
                channel="api",
                abort_signal=asyncio.Event(),
            ),
        )
    """

    user_info: UserInfo = field(default_factory=lambda: ANONYMOUS_USER)
    smartcmp_client: Optional[Any] = None   # httpx.AsyncClient
    peer_id: str = ""
    session_key: str = ""
    channel: str = ""
    abort_signal: asyncio.Event = field(default_factory=asyncio.Event)
    session_manager: Optional[Any] = None   # SessionManager injected by caller (per-user scoped)
    memory_manager: Optional[Any] = None    # MemoryManager injected by caller (per-user scoped)
    extra: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Backward-compatibility shim
    # ------------------------------------------------------------------

    @property
    def user_token(self) -> str:
        """Alias for ``user_info.raw_token``. Kept for backward compatibility."""
        return self.user_info.raw_token

    # ------------------------------------------------------------------
    # Abort helpers
    # ------------------------------------------------------------------

    def is_aborted(self) -> bool:
        """Return whether the current run has been aborted."""
        return self.abort_signal.is_set()

    def abort(self) -> None:
        """Signal that the current run should stop."""
        self.abort_signal.set()

    def reset_abort(self) -> None:
        """Clear the abort signal."""
        self.abort_signal.clear()
