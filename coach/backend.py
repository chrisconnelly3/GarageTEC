"""Pluggable LLM backends. Only FakeBackend is used by the test suite.

CloudClaude (default) and LocalOllama defer their optional imports/network
calls to .complete(), so importing this module never requires anthropic or a
running Ollama server.
"""
import json
import os


class LLMBackend:
    """Interface: return a dict matching `schema` for the given prompts."""

    name = "base"

    def complete(self, system, user, schema):
        raise NotImplementedError


class FakeBackend(LLMBackend):
    """Returns a canned dict (or raises). Records calls for assertions."""

    name = "fake"

    def __init__(self, canned=None, error=None):
        self.canned = canned
        self.error = error
        self.calls = []

    def complete(self, system, user, schema):
        self.calls.append((system, user, schema))
        if self.error is not None:
            raise self.error
        return self.canned


class CloudClaude(LLMBackend):
    """Anthropic API backend (default). Imports `anthropic` lazily so the module
    imports cleanly without the optional dependency."""

    name = "cloud"

    def __init__(self, model="claude-sonnet-4-5", api_key=None, max_tokens=3000):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.max_tokens = max_tokens

    _TOOL_NAME = "swing_coaching"

    def complete(self, system, user, schema):
        import anthropic  # lazy: optional runtime dep

        client = anthropic.Anthropic(api_key=self.api_key)
        # Force structured output via tool use: the model must call this tool
        # with input matching `schema`, so we get schema-valid JSON back instead
        # of free text we have to fish a JSON object out of.
        tool = {"name": self._TOOL_NAME,
                "description": "Return the structured swing coaching.",
                "input_schema": schema}
        resp = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[tool],
            tool_choice={"type": "tool", "name": self._TOOL_NAME},
        )
        out = None
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" \
                    and getattr(block, "name", None) == self._TOOL_NAME:
                out = block.input
                break
        if out is None:
            # Fallback: parse a JSON object from any text (strip markdown fences).
            text = "".join(getattr(b, "text", "") for b in resp.content
                           if getattr(b, "type", None) == "text").strip()
            if text.startswith("```"):
                text = text.split("```", 2)[1]
                if text.startswith("json"):
                    text = text[4:]
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end != -1:
                text = text[start:end + 1]
            out = json.loads(text)
        # Normalize: the model may omit an array it had nothing to put in. Default
        # the optional arrays to [] so a caveat-free swing doesn't fail validation.
        if isinstance(out, dict):
            for key in ("findings", "drills", "confidence_notes"):
                out.setdefault(key, [])
        return out


class LocalOllama(LLMBackend):
    """Optional local backend (stub). Defers the HTTP call to .complete()."""

    name = "local"

    def __init__(self, model="llama3.1", host=None):
        self.model = model
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    def complete(self, system, user, schema):
        import urllib.request  # lazy; no third-party dep required

        payload = {
            "model": self.model,
            "system": system,
            "prompt": (user + "\n\nReturn ONLY a JSON object matching:\n"
                       + json.dumps(schema)),
            "format": "json",
            "stream": False,
        }
        req = urllib.request.Request(
            self.host.rstrip("/") + "/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as r:
            body = json.loads(r.read().decode("utf-8"))
        return json.loads(body["response"])


def make_backend(name=None, **kwargs):
    """Select a backend by name (default 'cloud'). Extra kwargs go to the ctor."""
    name = (name or os.environ.get("COACH_BACKEND") or "cloud").lower()
    if name == "fake":
        return FakeBackend(canned=kwargs.get("canned"), error=kwargs.get("error"))
    if name in ("cloud", "claude", "anthropic"):
        return CloudClaude(**{k: v for k, v in kwargs.items()
                              if k in ("model", "api_key", "max_tokens")})
    if name in ("local", "ollama"):
        return LocalOllama(**{k: v for k, v in kwargs.items()
                              if k in ("model", "host")})
    raise ValueError(f"unknown backend: {name!r}")
