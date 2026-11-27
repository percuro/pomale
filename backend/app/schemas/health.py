from typing import Literal

from pydantic import BaseModel, Field


class HealthRead(BaseModel):
    status: Literal["ok"]
    version: str = Field(description="The pomale version, e.g. 1.0.0")
