import os

from gatekeeper import llm

# Tests never call an LLM, even when a key is set in the shell (module fixtures run before autouse ones).
for env in llm.KEY_ENV.values():
    os.environ.pop(env, None)
