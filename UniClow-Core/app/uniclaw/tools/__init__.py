"""Built-in tool package for Uniclaw.

Tools are exposed through `RunContext[SkillDeps]` and share a common result
format. This package includes:

- base result and metadata models
- tool catalog and profile helpers
- approval and truncation utilities
- runtime, filesystem, web, memory, session, and UI tools
"""

from app.uniclaw.tools.base import ToolResult, ToolMetadata
from app.uniclaw.tools.catalog import ToolCatalog, ToolProfile
from app.uniclaw.tools.approval import ApprovalManager, ApprovalPolicy, ApprovalRequest
from app.uniclaw.tools.truncation import TruncationConfig, truncate_output, truncate_image_payload

__all__ = [
    "ToolResult",
    "ToolMetadata",
    "ToolCatalog",
    "ToolProfile",
    "ApprovalManager",
    "ApprovalPolicy",
    "ApprovalRequest",
    "TruncationConfig",
    "truncate_output",
    "truncate_image_payload",
]
