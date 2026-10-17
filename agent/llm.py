"""Pluggable LLM providers. All return the post as a dict matching the JSON schema.

provider "auto" tries every provider whose API key is set, in this order:
claude → gemini → openrouter, and each provider's models in the order listed in config.yaml.
Temporary failures (timeouts, overload, rate limits) are retried, then the next model/provider
takes over — so one busy or broken API never stops the daily post.
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
TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}
TIMEOUT = 120  # seconds per request


class TransientError(RuntimeError):
    """Worth retrying: overload, rate limit, timeout."""


def candidates(cfg: dict) -> list[tuple[str, str]]:
    """(provider, model) pairs to try, in order."""
    choice = cfg["llm"].get("provider", "auto")
    providers = [choice] if choice != "auto" else [n for n, k in KEYS.items() if env(k, required=False)]
    if not providers:
        raise RuntimeError("No AI API key found. Set one of: " + ", ".join(KEYS.values()))
    pairs = []
    for name in providers:
        models = cfg["llm"]["models"][name]
        pairs += [(name, m) for m in ([models] if isinstance(models, str) else models)]
    return pairs


def pick_provider(cfg: dict) -> str:
    return candidates(cfg)[0][0]


def complete_json(cfg: dict, system: str, user: str, schema: dict, check=None) -> tuple[dict, str]:
    """Returns (data, "provider/model"). `check(data)` may fix up the result or raise ValueError to reject it."""
    system_json = (
        f"{system}\n\nRespond with ONLY a JSON object (no markdown fences) matching this JSON schema:\n"
        f"{json.dumps(schema)}"
    )
    errors = []
    for provider, model in candidates(cfg):
        for attempt in range(2):
            try:
                if provider == "claude":
                    data = _claude(cfg, model, system, user, schema)
                else:
                    raw = (_gemini(model, system_json, user) if provider == "gemini"
                           else _openai_compatible(provider, model, system_json, user))
                    data = _validate(json.loads(_strip_fences(raw)), schema)
                return (check(data) if check else data), f"{provider}/{model}"
            except (TransientError, requests.Timeout, requests.ConnectionError) as e:
                errors.append(f"{provider}/{model}: busy/unreachable ({str(e)[:150]})")
                if attempt == 0:
                    time.sleep(15)
            except (json.JSONDecodeError, ValueError) as e:
                errors.append(f"{provider}/{model}: unusable output ({str(e)[:150]})")
            except Exception as e:  # bad key, bad request, refusal… → straight to the next model
                errors.append(f"{provider}/{model}: {str(e)[:200]}")
                break
        print(f"[llm] {provider}/{model} failed, trying the next one")
    raise RuntimeError("Every AI writer failed:\n" + "\n".join(errors[-6:]))


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
        timeout=TIMEOUT,
    )
    if r.status_code in TRANSIENT_STATUS:
        raise TransientError(f"Gemini {r.status_code}: {r.text[:200]}")
    if not r.ok:
        raise RuntimeError(f"Gemini {r.status_code}: {r.text[:400]}")
    candidates_ = r.json().get("candidates") or []
    if not candidates_ or "content" not in candidates_[0]:
        raise ValueError(f"Gemini returned no text: {r.text[:200]}")
    parts = candidates_[0]["content"]["parts"]
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
        timeout=TIMEOUT,
    )
    if r.status_code in TRANSIENT_STATUS:
        raise TransientError(f"{provider} {r.status_code}: {r.text[:200]}")
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
