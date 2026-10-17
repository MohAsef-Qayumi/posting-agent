"""Pluggable LLM providers. All return the post as a dict matching the JSON schema.

provider "auto" picks the first one whose API key is set, in this order:
claude → gemini → openrouter. Add ANTHROPIC_API_KEY later and Claude takes over automatically.
"""
import json
import time

import requests

from .config import env

KEYS = {
    "claude": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}
OPENAI_COMPATIBLE = {
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
}


def pick_provider(cfg: dict) -> str:
    choice = cfg["llm"].get("provider", "auto")
    if choice != "auto":
        return choice
    for name, key in KEYS.items():
        if env(key, required=False):
            return name
    raise RuntimeError("No AI API key found. Set one of: " + ", ".join(KEYS.values()))


def complete_json(cfg: dict, system: str, user: str, schema: dict, check=None) -> tuple[dict, str]:
    """`check(data)` may fix up the result or raise ValueError to trigger a retry (free providers only)."""
    provider = pick_provider(cfg)
    model = cfg["llm"]["models"][provider]
    if provider == "claude":
        return _claude(cfg, model, system, user, schema), f"{provider}/{model}"

    # Free providers: ask for JSON matching the schema, validate, retry once on bad output.
    system_json = (
        f"{system}\n\nRespond with ONLY a JSON object (no markdown fences) matching this JSON schema:\n"
        f"{json.dumps(schema)}"
    )
    last_error = None
    for _ in range(2):
        try:
            raw = _gemini(model, system_json, user) if provider == "gemini" else _openai_compatible(provider, model, system_json, user)
            data = _validate(json.loads(_strip_fences(raw)), schema)
            return (check(data) if check else data), f"{provider}/{model}"
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            time.sleep(3)
    raise RuntimeError(f"{provider} returned invalid JSON twice: {last_error}")


def _claude(cfg: dict, model: str, system: str, user: str, schema: dict) -> dict:
    import anthropic

    response = anthropic.Anthropic().beta.messages.create(
        model=model,
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": cfg["llm"].get("claude_effort", "medium"), "format": {"type": "json_schema", "schema": schema}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude declined to write this post: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Claude's response was cut off (max_tokens)")
    return json.loads(next(b.text for b in response.content if b.type == "text"))


def _gemini(model: str, system: str, user: str) -> str:
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": env("GEMINI_API_KEY"), "Content-Type": "application/json"},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.9},
        },
        timeout=180,
    )
    if not r.ok:
        raise RuntimeError(f"Gemini {r.status_code}: {r.text[:400]}")
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


def _openai_compatible(provider: str, model: str, system: str, user: str) -> str:
    r = requests.post(
        OPENAI_COMPATIBLE[provider],
        headers={"Authorization": f"Bearer {env(KEYS[provider])}"},
        json={
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
            "temperature": 0.9,
        },
        timeout=180,
    )
    if not r.ok:
        raise RuntimeError(f"{provider} {r.status_code}: {r.text[:400]}")
    return r.json()["choices"][0]["message"]["content"]


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return text


def _validate(data: dict, schema: dict) -> dict:
    """Light validation for providers without guaranteed schemas: fill missing strings, reject missing lists."""
    if not isinstance(data, dict):
        raise ValueError("not a JSON object")
    for key, spec in schema["properties"].items():
        if key not in data:
            if spec["type"] == "string":
                data[key] = ""
            else:
                raise ValueError(f"missing '{key}'")
    return data
