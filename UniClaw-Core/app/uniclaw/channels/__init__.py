"""Channel adapter interfaces and built-in adapter exports."""

from app.uniclaw.channels.base import (
    ChannelAdapter,
    ChannelMessage,
    ChannelConfig,
    MessageChunk,
    TypingIndicator,
)
from app.uniclaw.channels.registry import (
    ChannelAdapterRegistry,
    create_adapter,
)
from app.uniclaw.channels.websocket_adapter import WebSocketAdapter
from app.uniclaw.channels.sse_adapter import SSEAdapter
from app.uniclaw.channels.rest_adapter import RESTCallbackAdapter

__all__ = [
    "ChannelAdapter",
    "ChannelMessage",
    "ChannelConfig",
    "MessageChunk",
    "TypingIndicator",
    "ChannelAdapterRegistry",
    "create_adapter",
    "WebSocketAdapter",
    "SSEAdapter",
    "RESTCallbackAdapter",
]
