from pydantic import BaseModel


class QueueJoinResponse(BaseModel):
    queue_position: int
    total: int
    message: str


class QueueLeaveResponse(BaseModel):
    message: str