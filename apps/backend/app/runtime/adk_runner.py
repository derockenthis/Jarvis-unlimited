from app.agent.runner import AgentStreamRunner


class ChatRuntime(AgentStreamRunner):
    """FastAPI-facing adapter kept for backwards compatibility with existing services/tests."""
