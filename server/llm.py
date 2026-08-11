"""Foundation Model client for the AI assistant — LIVE mode.

Routes through AI Gateway when AI_GATEWAY_URL is set (so Gateway usage counters
and inference tables register); otherwise falls back to the standard serving
path. Used by the /api/assistant route.
"""
from openai import OpenAI

from .config import (
    AI_GATEWAY_URL,
    LLM_ENDPOINT,
    get_oauth_token,
    get_workspace_host,
)


def get_llm_client() -> OpenAI:
    token = get_oauth_token()
    if AI_GATEWAY_URL:
        base_url = AI_GATEWAY_URL.rstrip("/")
    else:
        # Legacy fallback — still records in system.serving.endpoint_usage.
        base_url = f"{get_workspace_host()}/serving-endpoints"
    return OpenAI(api_key=token, base_url=base_url)


def chat_completion(messages: list[dict], model: str | None = None,
                    max_tokens: int = 1024, temperature: float = 0.3) -> str:
    client = get_llm_client()
    resp = client.chat.completions.create(
        model=model or LLM_ENDPOINT,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return resp.choices[0].message.content or ""
