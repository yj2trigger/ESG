from pydantic import BaseModel


class QueueJoinResponse(BaseModel):
    queue_position: int
    message: str


class QueueLeaveResponse(BaseModel):
    message: str