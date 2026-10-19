"""Display incomplete talk without ever interpreting it as an intent."""

import json


def string_at(text: str, start: int) -> tuple[str, int, bool]:
    """Decode a JSON string prefix. Hold back unfinished escapes and surrogate pairs."""
    end = start + 1
    while end < len(text):
        if text[end] == '"':
            return json.loads(text[start:end + 1]), end + 1, True
        if text[end] == "\\":
            size = 6 if text[end:end + 2] == "\\u" else 2
            if end + size > len(text):
                break
            end += size
        else:
            end += 1
    value = json.loads(text[start:end] + '"')
    # A high surrogate may be waiting for its low half in the next chunk.
    if value and 0xD800 <= ord(value[-1]) <= 0xDBFF:
        value = value[:-1]
    return value, end, False


def partial_message(text: str) -> str | None:
    """Read only top-level fields, in any order. Never match keys inside a message."""
    decoder = json.JSONDecoder()
    fields = {}
    pos = 0
    try:
        pos = len(text) - len(text.lstrip())
        if text[pos:pos + 1] != "{":
            return None
        pos += 1
        while pos < len(text):
            while pos < len(text) and text[pos].isspace():
                pos += 1
            if text[pos:pos + 1] != '"':
                break
            key, pos = decoder.raw_decode(text, pos)
            while pos < len(text) and text[pos].isspace():
                pos += 1
            if text[pos:pos + 1] != ":":
                break
            pos += 1
            while pos < len(text) and text[pos].isspace():
                pos += 1
            if text[pos:pos + 1] == '"':
                value, pos, complete = string_at(text, pos)
                if complete or key == "message":
                    fields[key] = value
                if not complete:
                    break
            else:
                value, pos = decoder.raw_decode(text, pos)
                fields[key] = value
            while pos < len(text) and text[pos].isspace():
                pos += 1
            if text[pos:pos + 1] != ",":
                break
            pos += 1
    except (ValueError, IndexError):
        pass  # A prefix is allowed to stop anywhere, including inside an escape.
    message = fields.get("message")
    return message if fields.get("action") == "talk" and isinstance(message, str) else None


def act_chat(client, world, npc_id, messages, schema, **kwargs):
    """Streaming is opt-in on a web client's act calls. Thoughts still use chat()."""
    live = getattr(client, "live_talk", None)
    if live is None:
        return client.chat(messages, schema, **kwargs)
    try:
        return client.chat(messages, schema, on_text=lambda text: live(
            world, npc_id, partial_message(text)), **kwargs)
    finally:
        # Also clear after a broken connection, malformed JSON, recall or a retry.
        live(world, npc_id, None)
