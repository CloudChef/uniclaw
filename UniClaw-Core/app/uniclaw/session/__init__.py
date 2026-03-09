"""

Session management module

Includes:
- context:Session context definitions(SessionKey, SessionScope, SessionMetadata etc.)
- manager:Session manager(CRUD, storage,)
- queue:Session serialization queue(SessionQueue)
- storage:storage adapter
"""

from app.uniclaw.session.context import (
    SessionScope,
    ChatType,
    SessionKey,
    SessionKeyFactory,
    IdentityLinks,
    SessionOrigin,
    SessionMetadata,
    TranscriptEntry,
)
from app.uniclaw.session.queue import SessionQueue, QueueMode

__all__ = [
    "SessionScope",
    "ChatType", 
    "SessionKey",
    "SessionKeyFactory",
    "IdentityLinks",
    "SessionOrigin",
    "SessionMetadata",
    "TranscriptEntry",
    "SessionQueue",
    "QueueMode",
]
