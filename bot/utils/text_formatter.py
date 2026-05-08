from datetime import datetime
from typing import Any

_MAX_CHUNK = 4096


def format_messages_for_prompt(messages: list[dict[str, Any]]) -> str:
    lines = []
    for m in messages:
        ts = m.get("timestamp", "")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts).strftime("%H:%M")
            except ValueError:
                ts = ts[:5]
        name = m.get("username") or m.get("first_name") or "unknown"
        text = m.get("text") or ("[медиа]" if m.get("has_media") else "")
        if text:
            lines.append(f"[{ts}] {name}: {text}")
    return "\n".join(lines)


def split_long_message(text: str, limit: int = _MAX_CHUNK) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks
