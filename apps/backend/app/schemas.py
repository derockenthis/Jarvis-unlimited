from pydantic import BaseModel, Field


class ChatEventPayload(BaseModel):
    tool_name: str | None = None
    status: str | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    app: str
    openrouter_configured: bool
    ripgrep_available: bool


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str = "default"
    user_id: str = "local-user"
    screen_share_enabled: bool = False
    skills_root: str | None = None


class ChatEvent(BaseModel):
    type: str
    content: str
    payload: ChatEventPayload = Field(default_factory=ChatEventPayload)


class SpeechTranscriptionResponse(BaseModel):
    text: str
    model: str


class McpToolConfig(BaseModel):
    id: str
    name: str
    command: str
    args: list[str]
    enabled: bool = True
    auto_start: bool = False
    status: str = "stopped"
    description: str = ""


class McpActionRequest(BaseModel):
    user_id: str = "local-user"


class McpActionResponse(BaseModel):
    tool_id: str
    status: str
    message: str


class WorkspaceRoot(BaseModel):
    path: str
    access: str = "granted"
