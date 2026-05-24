from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

MachineMode = Literal["A", "B", "C"]
MachineStatus = Literal["available", "in_use", "soft_reserved", "broken"]


class FloorSummary(BaseModel):
    floor: int
    available_count: int


class MachineDetail(BaseModel):
    id: int
    floor: int
    machine_number: int

    model_config = {"from_attributes": True}


class MachinesResponse(BaseModel):
    mode: MachineMode
    floors: list[FloorSummary]
    assigned_machine: Optional[MachineDetail] = None
    queue_position: Optional[int] = None


class MachineRequestResponse(BaseModel):
    assigned_machine: MachineDetail
    reserved_until: datetime