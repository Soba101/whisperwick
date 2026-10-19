"""OpenAI SSE framing. The full content still goes through the ordinary JSON parser."""

import json


def read_stream(response, on_text):
    text = ""
    metadata = {}
    data = []
    done = False

    def event():
        nonlocal text, done
        payload = "\n".join(data)
        data.clear()
        if payload == "[DONE]":
            done = True
            return
        reply = json.loads(payload)
        if "error" in reply:
            raise ValueError(str(reply["error"]))
        # Usage-only chunks have no choices. Keep timings from the last chunk that has them.
        for key in ("usage", "timings"):
            if reply.get(key):
                metadata[key] = reply[key]
        choices = reply.get("choices", [])
        if choices:
            content = choices[0].get("delta", {}).get("content")
            if content:
                text += content
                on_text(text)

    for raw in response:
        line = raw.decode("utf-8").rstrip("\r\n")
        if not line:
            if data:
                event()
            if done:
                break
        elif line.startswith("data:"):
            data.append(line[5:].removeprefix(" "))
    if data:
        event()
    if not done:
        raise ValueError("stream ended before [DONE]")
    return {**metadata, "choices": [{"message": {"content": text}}]}
