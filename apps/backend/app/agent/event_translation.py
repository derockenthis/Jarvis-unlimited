import json
import re

from app.schemas import ChatEvent, ChatEventPayload

CHANNEL_MARKER_PATTERN = re.compile(r"<\|?/?channel\|?>\s*thought\s*", re.IGNORECASE)


def clean_assistant_text(text: str) -> str:
    """Remove provider channel markers that should not render as final answer text."""

    return CHANNEL_MARKER_PATTERN.sub("", text)


def translate_event(event: object) -> list[ChatEvent]:
    """Translate a single ADK event into zero or more UI chat events."""

    events: list[ChatEvent] = []

    for call in event.get_function_calls():
        args_detail = ""
        if call.args:
            try:
                args_detail = json.dumps(call.args, default=str)
            except (TypeError, ValueError):
                args_detail = str(call.args)
        events.append(
            ChatEvent(
                type="tool_call",
                content=f"Calling {call.name}",
                payload=ChatEventPayload(
                    tool_name=call.name, status="running", detail=args_detail or None
                ),
            )
        )

    for response in event.get_function_responses():
        status = "success"
        detail = None
        result = response.response
        if isinstance(result, dict):
            status = str(result.get("status", "error" if result.get("isError") else "success"))
            detail = result.get("error") or result.get("diff")
            if detail is None and isinstance(result.get("content"), list):
                text_parts = [
                    item.get("text", "")
                    for item in result["content"]
                    if isinstance(item, dict) and item.get("type") == "text"
                ]
                detail = "\n".join(part for part in text_parts if part) or None
            if detail is None and "data" in result:
                try:
                    detail = json.dumps(result["data"], default=str)[:2000]
                except (TypeError, ValueError):
                    detail = str(result["data"])[:2000]
        events.append(
            ChatEvent(
                type="tool_result",
                content=f"{response.name} finished",
                payload=ChatEventPayload(tool_name=response.name, status=status, detail=detail),
            )
        )

    content = getattr(event, "content", None)
    if content is not None and content.parts:
        for part in content.parts:
            text = getattr(part, "text", None)
            if not text:
                continue
            if getattr(part, "thought", False):
                events.append(ChatEvent(type="thought", content=text))
            else:
                cleaned_text = clean_assistant_text(text)
                if cleaned_text:
                    events.append(ChatEvent(type="assistant_message", content=cleaned_text))

    return events