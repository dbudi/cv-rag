"""HTTP client untuk chat completions dan embeddings via LiteLLM proxy.

LiteLLM mengekspos endpoint OpenAI-compatible; model bisa diganti lewat
config (LLM_MODEL / EMBEDDING_MODEL) tanpa ubah kode aplikasi.
"""

import httpx

from app.config import settings

DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


class LLMClientError(Exception):
    pass


def _chat_completions_url() -> str:
    return f"{settings.litellm_base_url.rstrip('/')}/v1/chat/completions"


def _embeddings_url() -> str:
    return f"{settings.litellm_base_url.rstrip('/')}/v1/embeddings"


def _auth_headers() -> dict[str, str]:
    if not settings.litellm_api_key:
        raise LLMClientError("LiteLLM API key is not configured")
    return {
        "Authorization": f"Bearer {settings.litellm_api_key}",
        "content-type": "application/json",
    }


async def _chat_completion(
    client: httpx.AsyncClient,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    response = await client.post(
        _chat_completions_url(),
        headers=_auth_headers(),
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


async def _embedding(client: httpx.AsyncClient, model: str, text: str) -> list[float]:
    response = await client.post(
        _embeddings_url(),
        headers=_auth_headers(),
        json={"model": model, "input": text},
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]


async def generate_completion(
    system_prompt: str,
    user_prompt: str,
    response_language: str,
) -> str:
    language_instruction = (
        f"\n\nRespond in language code: {response_language}. "
        "If the CV content is in a different language, still answer in the "
        "requested response language."
    )
    system = system_prompt + language_instruction

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        return await _chat_completion(client, settings.llm_model, system, user_prompt)


async def generate_embedding(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        return await _embedding(client, settings.embedding_model, text)
