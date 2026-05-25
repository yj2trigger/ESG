from datetime import datetime
from pydantic import BaseModel


class QueueJoinResponse(BaseModel):
    queue_position: int
    total: int
    message: str


class QueueLeaveResponse(BaseModel):
    message: str


class QueueStatusResponse(BaseModel):
    in_queue: bool
    queue_position: int | None = None
    total: int | None = None
    is_notified: bool = False
    accept_until: datetime | None = None