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

    def __init__(self, model="claude-sonnet-4-5", api_key=None, max_tokens=1024):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.max_tokens = max_tokens

    def complete(self, system, user, schema):
        import anthropic  # lazy: optional runtime dep

        client = anthropic.Anthropic(api_key=self.api_key)
        instruction = (user + "\n\nReturn ONLY a single JSON object matching "
                       "this schema, with no prose:\n"
                       + json.dumps(schema))
        resp = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": instruction}],
        )
        text = "".join(block.text for block in resp.content
                       if getattr(block, "type", None) == "text")
        return json.loads(text)


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
