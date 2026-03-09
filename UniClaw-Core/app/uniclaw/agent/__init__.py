"""Agent execution layer for Uniclaw.

The `agent` package groups together the components responsible for prompt
construction, iterative agent execution, response compaction, and stream
chunking.
"""

from app.uniclaw.agent.stream import StreamEvent, BlockChunker
from app.uniclaw.agent.compaction import CompactionPipeline, CompactionConfig

__all__ = [
    "StreamEvent",
    "BlockChunker",
    "CompactionPipeline",
    "CompactionConfig",
]
