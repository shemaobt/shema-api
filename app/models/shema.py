from typing import Literal

from pydantic import BaseModel

ShemaModuleStatus = Literal["ok", "degraded"]
ShemaDatabaseStatus = Literal["ok", "unavailable"]


class ShemaHealthResponse(BaseModel):
    module: str
    status: ShemaModuleStatus
    version: str
    database: ShemaDatabaseStatus
