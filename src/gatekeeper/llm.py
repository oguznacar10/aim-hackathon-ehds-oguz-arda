"""Minimal JSON chat client for OpenAI, Anthropic and OpenRouter. Only request text is ever sent."""
import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.request

DEFAULT_MODELS = {"openai": "gpt-4o-mini", "anthropic": "claude-3-5-haiku-latest",
                  "openrouter": "openai/gpt-4o"}
KEY_ENV = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "openrouter": "OPENROUTER_API_KEY",
           "typesafe": "TYPESAFE_API_KEY"}
# <KEY_ENV>_SECRET names a Google Secret Manager resource (projects/<id>/secrets/<name>);
# the key is fetched inside this process with Application Default Credentials and never printed.
KEY_SECRET_ENV = {p: env + "_SECRET" for p, env in KEY_ENV.items()}
_keys = {}
OPENAI_STYLE_URLS = {"openai": "https://api.openai.com/v1/chat/completions",
                     "openrouter": "https://openrouter.ai/api/v1/chat/completions"}


RETRY_CODES = {429, 500, 502, 503, 504}
RETRIES = 3
BACKOFF_S = 1.0
JSON_ONLY = "Answer with one JSON object only, no prose, no code fences."


class LLMUnavailable(RuntimeError):
    pass


def available_providers():
    """Chat providers with a key; typesafe is a decision-model backend, not a chat provider."""
    return [p for p in KEY_ENV if p != "typesafe"
            and (os.environ.get(KEY_ENV[p]) or os.environ.get(KEY_SECRET_ENV[p]))]


def key_for(provider):
    return _key(provider)


def _key(provider):
    if provider not in _keys:
        _keys[provider] = (os.environ.get(KEY_ENV[provider])
                           or _from_secret_manager(os.environ.get(KEY_SECRET_ENV[provider])))
    return _keys[provider]


def _from_secret_manager(resource):
    if not resource:
        return None
    token = subprocess.run(["gcloud", "auth", "application-default", "print-access-token"],
                           capture_output=True, text=True, check=True).stdout.strip()
    project = resource.split("/")[1]
    req = urllib.request.Request(
        f"https://secretmanager.googleapis.com/v1/{resource}/versions/latest:access",
        headers={"Authorization": f"Bearer {token}", "x-goog-user-project": project})
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.load(resp)["payload"]["data"]
    return base64.b64decode(payload).decode().strip()


def chat_json(prompt, provider, model=None, temperature=0.0, timeout=45):
    key = _key(provider)
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
    data = _send(req, timeout)
    text = (data["choices"][0]["message"]["content"] if provider in OPENAI_STYLE_URLS
            else data["content"][0]["text"])
    return json.loads(_strip_fences(text))


def _send(req, timeout, retries=RETRIES):
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_CODES or attempt == retries:
                raise
            time.sleep(BACKOFF_S * 2 ** attempt)


def _strip_fences(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return text
