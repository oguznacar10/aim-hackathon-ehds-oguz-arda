"""Minimal JSON chat client for OpenAI, Anthropic and OpenRouter. Only request text is ever sent."""
import json
import os
import urllib.request

DEFAULT_MODELS = {"openai": "gpt-4o-mini", "anthropic": "claude-3-5-haiku-latest",
                  "openrouter": "openai/gpt-4o"}
KEY_ENV = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
OPENAI_STYLE_URLS = {"openai": "https://api.openai.com/v1/chat/completions",
                     "openrouter": "https://openrouter.ai/api/v1/chat/completions"}


JSON_ONLY = "Answer with one JSON object only, no prose, no code fences."


class LLMUnavailable(RuntimeError):
    pass


def available_providers():
    return [p for p, env in KEY_ENV.items() if os.environ.get(env)]


def chat_json(prompt, provider, model=None, temperature=0.0, timeout=45):
    key = os.environ.get(KEY_ENV[provider])
    if not key:
        raise LLMUnavailable(f"{KEY_ENV[provider]} is not set")
    model = model or DEFAULT_MODELS[provider]
    if provider in OPENAI_STYLE_URLS:
        url = OPENAI_STYLE_URLS[provider]
        headers = {"Authorization": f"Bearer {key}"}
        body = {"model": model, "temperature": temperature,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": JSON_ONLY},
                             {"role": "user", "content": prompt}]}
    else:
        url = "https://api.anthropic.com/v1/messages"
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        body = {"model": model, "temperature": temperature, "max_tokens": 4096,
                "system": JSON_ONLY,
                "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={**headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    text = (data["choices"][0]["message"]["content"] if provider in OPENAI_STYLE_URLS
            else data["content"][0]["text"])
    return json.loads(_strip_fences(text))


def _strip_fences(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return text
