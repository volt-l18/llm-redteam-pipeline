"""OrcaRouter Cyber Inference provider for litellm.

This module registers a first-class, named provider with litellm so the
pipeline can select OrcaRouter the same way it selects any other provider:

    TARGET_MODEL=orcarouter/orcarouter/auto
    ATTACKER_MODEL=orcarouter/orca/orcacyber-ultra-1.0
    EVALUATOR_MODEL=orcarouter/orca/orcacyber-zero-1.5

The prefix ``orcarouter/`` is the provider; everything after it is the vendor
model id exactly as OrcaRouter's catalog returns it (namespace preserved).
Requests go to ``https://api.orcarouter.ai/v1/chat/completions`` with the
user's own ``sk-orca-...`` key from ``ORCAROUTER_API_KEY`` (``.env`` is loaded
by ``src.config`` before the provider is used).

OrcaRouter Cyber Inference is aimed at security teams doing authorized work:
red teams can run OrcaCyber models (Ultra / Zero) for scoped security
reasoning, and blue teams keep gateway-level controls on the same endpoint.
Provider page: https://www.orcarouter.ai/cyber
Cyber model catalog: https://www.orcarouter.ai/models?tier=cyber
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
import litellm
import openai
from litellm.llms.openai.chat.gpt_transformation import OpenAIGPTConfig

try:  # litellm >= 1.9x ships the base class for user-defined providers
    from litellm.llms.custom_llm import CustomLLM
except ImportError:  # pragma: no cover - older litellm releases
    from litellm.llms.base import CustomLLM  # type: ignore[attr-defined]

PROVIDER_NAME = "orcarouter"
PROVIDER_LABEL = "OrcaRouter Cyber Inference"
API_BASE_URL = "https://api.orcarouter.ai/v1"
API_KEY_ENV = "ORCAROUTER_API_KEY"
KEY_DASHBOARD_URL = "https://www.orcarouter.ai/console/token"
CYBER_PAGE_URL = "https://www.orcarouter.ai/cyber"
CYBER_CATALOG_URL = "https://www.orcarouter.ai/models?tier=cyber"

# Endpoint types in OrcaRouter's catalog that speak a chat wire format.
_TEXT_ENDPOINT_TYPES = {"openai", "openai-response", "anthropic", "gemini"}
# Catalog endpoint types that are never plain text chat.
_NON_CHAT_ENDPOINT_TYPES = {
    "image-generation",
    "openai-video",
    "jina-rerank",
    "embeddings",
    "embedding",
}

# Verified cold-start seed (checked against GET /v1/models on 2026-11-08).
# Every id here appears in the OrcaRouter catalog with a chat endpoint type.
VERIFIED_SEED_MODELS = (
    "orcarouter/auto",
    "orca/orcacyber-ultra-1.0",
    "orca/orcacyber-zero-1.5",
    "orcarouter/fusion",
    "openai/gpt-5.5",
    "anthropic/claude-opus-4.8",
    "google/gemini-3.5-flash",
    "deepseek/deepseek-v4-pro",
)

# How the provider presents its models to users (docs, README, CLI hints).
RECOMMENDED_MODELS = (
    {
        "id": "orcarouter/auto",
        "role": "default",
        "label": "orcarouter/auto — automatic routing, works with any key",
    },
    {
        "id": "orca/orcacyber-ultra-1.0",
        "role": "recommended-cyber",
        "label": "OrcaCyber Ultra — security code review and long multi-step audits",
    },
    {
        "id": "orca/orcacyber-zero-1.5",
        "role": "recommended-cyber",
        "label": "OrcaCyber Zero — OrcaCyber harness, authorized security engineering",
    },
    {
        "id": "orcarouter/fusion",
        "role": "fallback",
        "label": "orcarouter/fusion — general-purpose fallback",
    },
)

CATALOG_TIMEOUT_SECONDS = 20.0
CATALOG_MAX_BYTES = 4 * 1024 * 1024
CATALOG_MAX_ITEMS = 2000


class OrcaRouterAuthError(litellm.AuthenticationError):
    """Terminal authentication failure: the stored key must be replaced.

    A rejected ``sk-orca-`` key is ``needsReauth``: there is no refresh grant,
    so callers should stop and ask for a new key rather than retry.
    """

    def __init__(self, message: str, model: str = "orcarouter/*"):
        super().__init__(message=message, llm_provider=PROVIDER_NAME, model=model)
        self.needs_reauth = True


def resolve_api_base(api_base: str | None = None) -> str:
    """Inference base URL; an explicit argument wins over the default origin."""
    return (api_base or API_BASE_URL).rstrip("/")


def resolve_api_key(api_key: str | None = None) -> str | None:
    """Key from the argument, litellm params, or the project's env/.env file."""
    if api_key:
        return api_key
    secret = litellm.get_secret(API_KEY_ENV) if hasattr(litellm, "get_secret") else None
    return secret or os.environ.get(API_KEY_ENV) or None


def is_orcarouter_model(model: str | None) -> bool:
    return bool(model) and model.startswith(PROVIDER_NAME + "/")


def split_model(model: str) -> str:
    """``orcarouter/vendor/model`` -> ``vendor/model`` (the id sent upstream)."""
    if is_orcarouter_model(model):
        return model[len(PROVIDER_NAME) + 1 :]
    return model


# Versioned aliases: OrcaCyber Zero ships as 1.5 and 1.0 on the same model slot.
_CYBER_FAMILY_LABELS = (
    ("orca/orcacyber-ultra", "OrcaCyber Ultra"),
    ("orca/orcacyber-zero", "OrcaCyber Zero"),
    ("orca/orcacyber-flash", "OrcaCyber Flash"),
)


def display_name(model: str) -> str:
    upstream = split_model(model)
    for entry in RECOMMENDED_MODELS:
        if entry["id"] == upstream:
            return entry["label"]
    for prefix, family in _CYBER_FAMILY_LABELS:
        if upstream.startswith(prefix):
            return f"{family} ({upstream})"
    return upstream


def _redact(text: str, api_key: str | None) -> str:
    if api_key:
        text = text.replace(api_key, "sk-orca-***")
    return text


def _status_error(status_code: int, message: str, httpx_response: httpx.Response, body: str):
    """Build the openai status exception litellm's mapper keys on for ``status_code``."""
    specific = {
        401: openai.AuthenticationError,
        403: openai.PermissionDeniedError,
        429: openai.RateLimitError,
    }.get(status_code)
    if specific is None:
        return openai.APIStatusError(message=message, response=httpx_response, body=body)
    return specific(message=message, response=httpx_response, body=body)


def _litellm_exception(
    httpx_response: httpx.Response, api_key: str | None, model: str
) -> litellm.exceptions.APIError:
    """Translate an OpenAI-compatible error response into a litellm exception.

    Goes through litellm's own OpenAI-compatible mapping so 401/403/429/5xx
    surface as the same exception types (and retryability) every other
    provider gets. Messages are redacted and extended with OrcaRouter guidance.
    """
    status_code = httpx_response.status_code
    body = _redact(httpx_response.text[:500], api_key)
    if status_code == 401:
        hint = (
            f"OrcaRouter rejected the API key (HTTP 401). Create an sk-orca-... key at "
            f"{KEY_DASHBOARD_URL} and set {API_KEY_ENV}."
        )
    elif status_code == 403:
        hint = (
            "OrcaRouter denied this model for the current key (HTTP 403). Dedicated "
            f"cyber models may need business verification; see {CYBER_CATALOG_URL}."
        )
    elif status_code == 429:
        hint = "OrcaRouter rate limit (HTTP 429)."
    else:
        hint = f"OrcaRouter request failed (HTTP {status_code})."
    original = _status_error(status_code, f"{hint} Details: {body}", httpx_response, body)
    try:
        mapped = litellm.exception_type(
            model=model,
            original_exception=original,
            custom_llm_provider="openai",
        )
    except openai.OpenAIError as exc:  # litellm raises the mapped type, not returns it
        mapped = exc
    except Exception:  # pragma: no cover - mapping must never mask the real error
        mapped = None
    if isinstance(mapped, Exception):
        if status_code == 401:
            mapped.needs_reauth = True
        # 403 has no dedicated litellm type: keep an APIError but mark it as a
        # permission failure so callers can tell it apart from a transient error.
        if status_code == 403:
            mapped = litellm.exceptions.APIError(
                status_code=403,
                message=str(mapped),
                llm_provider=PROVIDER_NAME,
                model=model,
            )
            mapped.permission_denied = True
        return mapped
    return litellm.exceptions.APIError(
        status_code=status_code,
        message=f"{hint} Details: {body}",
        llm_provider=PROVIDER_NAME,
        model=model,
    )


def build_request(model: str, messages: list, optional_params: dict | None, api_base: str | None = None) -> tuple:
    """Build (url, body, headers, upstream_model, key) for a chat request."""
    key = resolve_api_key()
    upstream_model = split_model(model)
    optional = dict(optional_params or {})
    optional.pop("stream", None)
    url = f"{resolve_api_base(api_base)}/chat/completions"
    body = {"model": upstream_model, "messages": messages, **optional}
    headers = {"Authorization": f"Bearer {key or ''}", "Content-Type": "application/json"}
    return url, body, headers, upstream_model, key


def parse_chat_completion(payload: dict) -> dict:
    """Keep the OpenAI response shape, remember the upstream model id."""
    choices = []
    for choice in payload.get("choices") or []:
        message = dict(choice.get("message") or {})
        choices.append(
            {
                "index": choice.get("index", 0),
                "message": message,
                "finish_reason": choice.get("finish_reason", "stop"),
            }
        )
    return {
        "id": payload.get("id", "orcarouter-completion"),
        "object": "chat.completion",
        "created": payload.get("created", 0),
        "model": payload.get("model", ""),
        "choices": choices,
        "usage": payload.get("usage"),
    }


def _merge_sse(raw_text: str) -> dict:
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    finish_reason = None
    usage = None
    model_id = ""
    for line in raw_text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[len("data:") :].strip()
        if not data or data == "[DONE]":
            continue
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        model_id = chunk.get("model") or model_id
        usage = chunk.get("usage") or usage
        for choice in chunk.get("choices") or []:
            delta = choice.get("delta") or {}
            content_parts.append(delta.get("content") or "")
            reasoning_parts.append(delta.get("reasoning_content") or "")
            finish_reason = choice.get("finish_reason") or finish_reason
    message: dict[str, Any] = {"role": "assistant", "content": "".join(content_parts)}
    if any(reasoning_parts):
        message["reasoning_content"] = "".join(reasoning_parts)
    return {
        "id": "orcarouter-stream",
        "object": "chat.completion",
        "created": 0,
        "model": model_id,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": usage,
    }


def post_chat(
    model: str,
    messages: list,
    optional_params: dict | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
    headers: dict | None = None,
    timeout: float | None = None,
    client: httpx.Client | None = None,
    stream: bool = False,
) -> litellm.ModelResponse:
    """POST /chat/completions and return a litellm ``ModelResponse``.

    Every error path carries a message that already had the key redacted, and a
    ``401`` becomes a terminal ``OrcaRouterAuthError`` (``needs_reauth``).
    """
    key = resolve_api_key(api_key)
    upstream_model = split_model(model)
    if not key:
        raise OrcaRouterAuthError(
            f"{API_KEY_ENV} is not set. Add your sk-orca-... key to .env "
            f"(create one at {KEY_DASHBOARD_URL}).",
            model=upstream_model,
        )
    optional = dict(optional_params or {})
    stream_requested = stream or bool(optional.pop("stream", False))
    url = f"{resolve_api_base(api_base)}/chat/completions"
    body = {"model": upstream_model, "messages": messages, **optional}
    if stream_requested:
        body["stream"] = True
    request_headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    request_headers.update(headers or {})

    owns_client = client is None
    http = client or httpx.Client()
    try:
        response = http.post(url, json=body, headers=request_headers, timeout=timeout or 120.0)
    except httpx.HTTPError as exc:
        raise litellm.exceptions.APIConnectionError(
            message=f"OrcaRouter network error: {type(exc).__name__}",
            llm_provider=PROVIDER_NAME,
            model=upstream_model,
        ) from exc
    finally:
        if owns_client:
            http.close()

    if response.status_code != 200:
        raise _litellm_exception(response, key, upstream_model)

    if stream_requested:
        payload = _merge_sse(response.text)
    else:
        payload = response.json()
    completion = parse_chat_completion(payload)
    completion["_orca_upstream_model"] = upstream_model
    return litellm.ModelResponse(**{k: v for k, v in completion.items() if not k.startswith("_")})


class OrcaRouterCyberProvider(CustomLLM):
    """litellm custom provider backed by the OrcaRouter Cyber Inference endpoint."""

    def __init__(self, client_factory: Any = httpx.Client):
        super().__init__()
        self._client_factory = client_factory

    def completion(
        self,
        model: str,
        messages: list,
        api_base: str = None,
        custom_prompt_dict: dict = None,
        model_response: Any = None,
        print_verbose: Any = None,
        encoding: Any = None,
        api_key: str = None,
        logging_obj: Any = None,
        optional_params: dict = None,
        acompletion: Any = None,
        litellm_params: dict = None,
        logger_fn: Any = None,
        headers: dict = None,
        timeout: Any = None,
        client: Any = None,
    ):
        with self._client_factory() as http:
            return post_chat(
                model=model,
                messages=messages,
                optional_params=optional_params,
                api_base=api_base,
                api_key=api_key,
                headers=headers,
                timeout=timeout,
                client=http,
                stream=bool((litellm_params or {}).get("stream")),
            )


def register_provider(handler: OrcaRouterCyberProvider | None = None) -> OrcaRouterCyberProvider:
    """Register (idempotently) the provider with litellm and return the handler."""
    existing = [
        item for item in (litellm.custom_provider_map or []) if item.get("provider") == PROVIDER_NAME
    ]
    if existing:
        return existing[0]["custom_handler"]
    handler = handler or OrcaRouterCyberProvider()
    litellm.custom_provider_map = list(litellm.custom_provider_map or []) + [
        {"provider": PROVIDER_NAME, "custom_handler": handler}
    ]
    return handler


def require_api_key() -> str:
    """Fail fast with an actionable message when no key is configured."""
    key = resolve_api_key()
    if not key:
        raise OrcaRouterAuthError(
            f"{API_KEY_ENV} is not set. Add your sk-orca-... key to .env "
            f"(create one at {KEY_DASHBOARD_URL}).",
            model="orcarouter/*",
        )
    return key


def _catalog_url(api_base: str | None = None) -> str:
    return f"{resolve_api_base(api_base)}/models"


def _looks_like_chat_model(entry: dict) -> bool:
    endpoint_types = set(entry.get("supported_endpoint_types") or [])
    if endpoint_types and not (endpoint_types & _TEXT_ENDPOINT_TYPES):
        return False
    capabilities = entry.get("endpoint_capabilities")
    if capabilities is not None and "chat_completions" not in capabilities:
        return False
    modalities = (entry.get("architecture") or {}).get("output_modalities")
    if modalities and "text" not in modalities:
        return False
    return bool(endpoint_types) or bool(capabilities)


def _input_modalities(entry: dict) -> set[str]:
    modalities = (entry.get("architecture") or {}).get("input_modalities")
    if not isinstance(modalities, list):
        return set()
    return {item for item in modalities if isinstance(item, str)}


def _matches_capability(entry: dict, capability: str) -> bool:
    """Capability match against catalog metadata only; never guess from names.

    ``chat`` accepts text-capable chat models. A modality name (``image``,
    ``audio``, ``video``) means "chat that explicitly declares that input
    modality"; models without a declared list fail closed.
    """
    if not _looks_like_chat_model(entry):
        return False
    if capability == "chat":
        return True
    return capability in _input_modalities(entry)


def parse_catalog(payload: Any, capability: str = "chat") -> list[str]:
    """Return model ids compatible with ``capability`` from a ``GET /v1/models`` payload."""
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    ids: list[str] = []
    seen: set[str] = set()
    for entry in data[:CATALOG_MAX_ITEMS]:
        if not isinstance(entry, dict):
            continue
        model_id = entry.get("id")
        if not isinstance(model_id, str) or "/" not in model_id or model_id in seen:
            continue
        if not _matches_capability(entry, capability):
            continue
        seen.add(model_id)
        ids.append(model_id)
    return ids


def list_chat_models(
    api_key: str | None = None, api_base: str | None = None, capability: str = "chat"
) -> list[str]:
    """Fetch the live chat catalog for the configured key.

    Raises ``httpx.HTTPError``/``ValueError`` on failure so callers can choose
    between the verified seed and the last-known-good catalog. Never returns an
    empty success: an empty catalog is treated as a failure by the CLI.
    """
    key = resolve_api_key(api_key)
    if not key:
        raise OrcaRouterAuthError(
            f"{API_KEY_ENV} is not set; cannot list OrcaRouter models.", model="catalog"
        )
    with httpx.Client(follow_redirects=False) as http:
        response = http.get(
            _catalog_url(api_base),
            params={"capability": "chat"},
            headers={"Authorization": f"Bearer {key}"},
            timeout=CATALOG_TIMEOUT_SECONDS,
        )
    if response.status_code in (401, 403):
        raise _litellm_exception(response, key, "catalog")
    if response.status_code != 200:
        raise litellm.exceptions.APIError(
            status_code=response.status_code,
            message=f"OrcaRouter model catalog failed (HTTP {response.status_code}).",
            llm_provider=PROVIDER_NAME,
            model="catalog",
        )
    if len(response.content) > CATALOG_MAX_BYTES:
        raise ValueError("OrcaRouter model catalog response exceeded the size limit")
    return parse_catalog(response.json(), capability=capability)
