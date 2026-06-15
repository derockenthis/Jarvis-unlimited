from functools import lru_cache

from app.agent.runner import AgentStreamRunner
from app.config import Settings, get_settings
from app.security.path_policy import PathPolicy
from app.services.chat_service import ChatService
from app.services.desktop_vision_service import DesktopVisionService
from app.services.conversation_context_service import ConversationContextService
from app.services.memory_service import MemoryService
from app.services.mcp_service import McpService
from app.services.session_terminal_service import SessionTerminalService
from app.services.settings_service import SettingsService
from app.services.transcription_service import SpeechToTextService


@lru_cache(maxsize=1)
def get_path_policy() -> PathPolicy:
    settings = get_settings()
    return PathPolicy(settings.allowed_root_paths, full_access=settings.full_filesystem_access)


@lru_cache(maxsize=1)
def get_chat_runtime() -> AgentStreamRunner:
    return AgentStreamRunner(
        get_settings(),
        get_path_policy(),
        get_mcp_service(),
        get_session_terminal_service(),
        get_desktop_vision_service(),
        get_memory_service(),
        get_conversation_context_service(),
    )


@lru_cache(maxsize=1)
def get_chat_service() -> ChatService:
    return ChatService(get_chat_runtime(), get_settings())


@lru_cache(maxsize=1)
def get_mcp_service() -> McpService:
    return McpService()


@lru_cache(maxsize=1)
def get_session_terminal_service() -> SessionTerminalService:
    return SessionTerminalService()


@lru_cache(maxsize=1)
def get_desktop_vision_service() -> DesktopVisionService:
    return DesktopVisionService(get_settings())


@lru_cache(maxsize=1)
def get_memory_service() -> MemoryService:
    return MemoryService(get_settings())


@lru_cache(maxsize=1)
def get_conversation_context_service() -> ConversationContextService:
    return ConversationContextService(get_settings().sqlite_path)


@lru_cache(maxsize=1)
def get_speech_to_text_service() -> SpeechToTextService:
    return SpeechToTextService(get_settings())


@lru_cache(maxsize=1)
def get_settings_service() -> SettingsService:
    return SettingsService(get_settings())


def settings_dependency() -> Settings:
    return get_settings()
