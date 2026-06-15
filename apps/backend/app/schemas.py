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
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None


class ChatEvent(BaseModel):
    type: str
    content: str
    payload: ChatEventPayload = Field(default_factory=ChatEventPayload)


class Conversation(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str


class ConversationMessage(BaseModel):
    id: int
    conversation_id: str
    role: str
    content: str
    created_at: str


class ProviderModelSettings(BaseModel):
    provider: str
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    speech_model: str = ""


class ModelSettingsResponse(BaseModel):
    current_provider: str = "openrouter"
    providers: list[ProviderModelSettings] = Field(default_factory=list)


class UpsertModelSettingsRequest(BaseModel):
    provider: str = Field(min_length=1)
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    speech_model: str = ""


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
