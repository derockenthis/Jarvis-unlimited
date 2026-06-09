from fastapi import APIRouter, Depends

from app.dependencies import get_mcp_service
from app.schemas import McpActionRequest, McpActionResponse
from app.services.mcp_service import McpService

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


@router.get("/tools")
def mcp_tools(service: McpService = Depends(get_mcp_service)) -> dict[str, object]:
    return {"tools": [tool.model_dump() for tool in service.list_tools()]}


@router.post("/tools/{tool_id}/start", response_model=McpActionResponse)
def start_mcp_tool(
    tool_id: str,
    request: McpActionRequest,
    service: McpService = Depends(get_mcp_service),
) -> McpActionResponse:
    return service.start_tool(tool_id, request)


@router.post("/tools/{tool_id}/stop", response_model=McpActionResponse)
def stop_mcp_tool(
    tool_id: str,
    request: McpActionRequest,
    service: McpService = Depends(get_mcp_service),
) -> McpActionResponse:
    return service.stop_tool(tool_id, request)
