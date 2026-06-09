from typing import Any

from pydantic import BaseModel


class ToolResult(BaseModel):
    status: str
    data: Any = None
    error: str | None = None
    diff: str | None = None
