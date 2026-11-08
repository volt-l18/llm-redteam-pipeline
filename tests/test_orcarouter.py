"""Tests for the OrcaRouter Cyber Inference provider (``orcarouter/...``)."""

import json

import httpx

import litellm
import pytest

from src import orcarouter
from src.orcarouter import (
    API_BASE_URL,
    OrcaRouterAuthError,
    display_name,
    is_orcarouter_model,
    list_chat_models,
    parse_catalog,
    post_chat,
    split_model,
)
from src.reporter import ReportGenerator, detect_provider


class RecordingClient:
    """Minimal httpx.Client stand-in that records the request."""

    def __init__(self, status_code=200, payload=None, text=None):
        self.status_code = status_code
        self.payload = payload
        self.text = text
        self.content = b""
        self.calls = []
        self.closed = False

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        if self.text is not None:
            body = self.text
        else:
            body = json_module.dumps(self.payload)
        self.content = body.encode()
        return Response(self.status_code, body)

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class _Response(httpx.Response):
    """httpx.Response carrying a real request, like the one litellm expects."""

    def __init__(self, status_code, body):
        request = httpx.Request("POST", "https://api.orcarouter.ai/v1/chat/completions")
        super().__init__(status_code, request=request, content=body.encode())

    def json(self):
        return json_module.loads(self.text)


Response = _Response
json_module = json


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("ORCAROUTER_API_KEY", raising=False)


def completion_payload(model="orca/orcacyber-ultra-1.0"):
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1,
        "model": model,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


# --- registration -----------------------------------------------------------


def test_provider_registered_by_package_import():
    entries = [e for e in litellm.custom_provider_map if e["provider"] == "orcarouter"]
    assert len(entries) == 1
    assert isinstance(entries[0]["custom_handler"], orcarouter.OrcaRouterCyberProvider)


def test_register_provider_is_idempotent():
    before = len(litellm.custom_provider_map)
    orcarouter.register_provider()
    orcarouter.register_provider()
    assert len(litellm.custom_provider_map) == before


# --- model string handling --------------------------------------------------


@pytest.mark.parametrize(
    "model,upstream",
    [
        ("orcarouter/orca/orcacyber-ultra-1.0", "orca/orcacyber-ultra-1.0"),
        ("orcarouter/orcarouter/auto", "orcarouter/auto"),
        ("orcarouter/fusion", "fusion"),
    ],
)
def test_split_model(model, upstream):
    assert is_orcarouter_model(model)
    assert split_model(model) == upstream


def test_display_name_for_recommended_models():
    assert "OrcaCyber Ultra" in display_name("orcarouter/orca/orcacyber-ultra-1.0")
    assert "OrcaCyber Zero" in display_name("orcarouter/orca/orcacyber-zero-1.5")
    assert display_name("orcarouter/orca/orcacyber-zero-1.0").startswith("OrcaCyber Zero")
    assert "automatic routing" in display_name("orcarouter/orcarouter/auto")
    assert "fallback" in display_name("orcarouter/orcarouter/fusion")


# --- request shape ----------------------------------------------------------


def test_post_chat_uses_gateway_endpoint_and_bearer_token():
    client = RecordingClient(payload=completion_payload())
    result = post_chat(
        model="orcarouter/orca/orcacyber-ultra-1.0",
        messages=[{"role": "user", "content": "hi"}],
        optional_params={"temperature": 0},
        api_key="sk-orca-test-key",
        client=client,
    )
    call = client.calls[0]
    assert call["url"] == f"{API_BASE_URL}/chat/completions"
    assert call["url"] == "https://api.orcarouter.ai/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer sk-orca-test-key"
    assert call["json"]["model"] == "orca/orcacyber-ultra-1.0"
    assert call["json"]["messages"] == [{"role": "user", "content": "hi"}]
    assert call["json"]["temperature"] == 0
    assert result.choices[0].message.content == "ok"


def test_post_chat_uses_configured_api_base():
    client = RecordingClient(payload=completion_payload())
    post_chat(
        model="orcarouter/orcarouter/auto",
        messages=[{"role": "user", "content": "hi"}],
        api_base="https://self-hosted.example/v1/",
        api_key="sk-orca-test-key",
        client=client,
    )
    assert client.calls[0]["url"] == "https://self-hosted.example/v1/chat/completions"


def test_post_chat_reads_key_from_environment(monkeypatch):
    monkeypatch.setenv("ORCAROUTER_API_KEY", "sk-orca-from-env")
    client = RecordingClient(payload=completion_payload())
    post_chat(model="orcarouter/orcarouter/auto", messages=[], client=client)
    assert client.calls[0]["headers"]["Authorization"] == "Bearer sk-orca-from-env"


def test_post_chat_stream_merges_sse_chunks():
    sse = "\n".join(
        [
            'data: {"model":"orca/orcacyber-zero-1.5","choices":[{"delta":{"content":"Hel"}}]}',
            'data: {"model":"orca/orcacyber-zero-1.5","choices":[{"delta":{"content":"lo"},"finish_reason":"stop"}]}',
            "data: [DONE]",
        ]
    )
    client = RecordingClient(text=sse)
    result = post_chat(
        model="orcarouter/orca/orcacyber-zero-1.5",
        messages=[],
        api_key="sk-orca-test-key",
        stream=True,
        client=client,
    )
    assert client.calls[0]["json"]["stream"] is True
    assert result.model == "orca/orcacyber-zero-1.5"
    assert result.choices[0].message.content == "Hello"


# --- error handling ---------------------------------------------------------


def test_missing_key_raises_actionable_auth_error():
    with pytest.raises(OrcaRouterAuthError) as excinfo:
        post_chat(model="orcarouter/orcarouter/auto", messages=[])
    assert excinfo.value.needs_reauth is True
    assert "ORCAROUTER_API_KEY" in str(excinfo.value)


def test_401_is_terminal_auth_error_with_redacted_key():
    client = RecordingClient(status_code=401, text='{"error":"bad key sk-orca-secretvalue"}')
    with pytest.raises(litellm.exceptions.AuthenticationError) as excinfo:
        post_chat(
            model="orcarouter/orcarouter/auto",
            messages=[],
            api_key="sk-orca-secretvalue",
            client=client,
        )
    message = str(excinfo.value)
    assert excinfo.value.needs_reauth is True
    assert "sk-orca-secretvalue" not in message
    assert "console/token" in message


def test_403_points_at_cyber_catalog():
    client = RecordingClient(status_code=403, text='{"error":"block_key_scope"}')
    with pytest.raises(litellm.exceptions.APIError) as excinfo:
        post_chat(model="orcarouter/orcarouter/auto", messages=[], api_key="sk-orca-key001", client=client)
    assert getattr(excinfo.value, "permission_denied", False) is True
    assert "models?tier=cyber" in str(excinfo.value)
    assert "sk-orca-key001" not in str(excinfo.value)


def test_429_maps_to_rate_limit_error():
    client = RecordingClient(status_code=429, text="slow down")
    with pytest.raises(litellm.exceptions.RateLimitError):
        post_chat(model="orcarouter/orcarouter/auto", messages=[], api_key="sk-orca-key001", client=client)


def test_500_maps_to_server_error():
    client = RecordingClient(status_code=500, text="boom")
    with pytest.raises(litellm.exceptions.InternalServerError):
        post_chat(model="orcarouter/orcarouter/auto", messages=[], api_key="sk-orca-key001", client=client)


# --- catalog ----------------------------------------------------------------


CATALOG_FIXTURE = {
    "data": [
        {
            "id": "orcarouter/auto",
            "supported_endpoint_types": ["openai", "anthropic"],
        },
        {
            "id": "orca/orcacyber-ultra-1.0",
            "supported_endpoint_types": ["openai"],
            "endpoint_capabilities": ["chat_completions"],
            "architecture": {"input_modalities": ["text"]},
        },
        {"id": "orca/orcacyber-flash-1.0", "supported_endpoint_types": ["openai"]},
        {"id": "voyage/voyage-3", "supported_endpoint_types": ["embeddings"]},
        {"id": "openai/dall-e-4", "supported_endpoint_types": ["image-generation"]},
        {"id": "kling/video-v3", "supported_endpoint_types": ["openai-video"]},
        {"id": "jina/reranker-v3", "supported_endpoint_types": ["jina-rerank"]},
        {"id": "orca/orcacyber-ultra-1.0", "supported_endpoint_types": ["openai"]},
        {"id": "no-namespace-model", "supported_endpoint_types": ["openai"]},
        "not-a-dict",
    ]
}


def test_parse_catalog_keeps_only_chat_models():
    models = parse_catalog(CATALOG_FIXTURE)
    assert models == [
        "orcarouter/auto",
        "orca/orcacyber-ultra-1.0",
        "orca/orcacyber-flash-1.0",
    ]


def test_parse_catalog_rejects_non_chat_capability():
    payload = {
        "data": [
            {
                "id": "x/image-only",
                "supported_endpoint_types": ["openai"],
                "endpoint_capabilities": ["images_generations"],
            }
        ]
    }
    assert parse_catalog(payload) == []


MULTIMODAL_CATALOG_FIXTURE = {
    "data": [
        {
            "id": "orca/orcacyber-ultra-1.0",
            "supported_endpoint_types": ["openai"],
            "architecture": {"input_modalities": ["text", "image"]},
        },
        {
            "id": "orca/orcacyber-zero-1.5",
            "supported_endpoint_types": ["openai"],
            "architecture": {"input_modalities": ["text"]},
        },
        {"id": "orcarouter/auto", "supported_endpoint_types": ["openai"]},
        {
            "id": "anthropic/claude-opus-4.8",
            "supported_endpoint_types": ["openai", "anthropic"],
            "architecture": {"input_modalities": ["text", "image", "pdf"]},
        },
        {
            "id": "openai/dall-e-4",
            "supported_endpoint_types": ["image-generation"],
            "architecture": {"input_modalities": ["text"]},
        },
        {
            "id": "x/audio-chat",
            "supported_endpoint_types": ["openai"],
            "architecture": {"input_modalities": ["text", "image", "audio"]},
        },
    ]
}


def test_image_capability_keeps_only_declared_image_inputs():
    models = parse_catalog(MULTIMODAL_CATALOG_FIXTURE, capability="image")
    assert models == ["orca/orcacyber-ultra-1.0", "anthropic/claude-opus-4.8", "x/audio-chat"]


def test_image_capability_fails_closed_without_modalities():
    # Models that do not declare input modalities must never reach the multimodal list.
    assert parse_catalog(CATALOG_FIXTURE, capability="image") == []


def test_text_chat_capability_is_unchanged_by_modalities():
    models = parse_catalog(MULTIMODAL_CATALOG_FIXTURE)
    assert models == [
        "orca/orcacyber-ultra-1.0",
        "orca/orcacyber-zero-1.5",
        "orcarouter/auto",
        "anthropic/claude-opus-4.8",
        "x/audio-chat",
    ]


def test_list_chat_models_serves_image_capability_without_new_request_params(monkeypatch):
    class FakeClient(RecordingClient):
        def get(self, url, params=None, headers=None, timeout=None):
            return _Response(200, json_module.dumps(MULTIMODAL_CATALOG_FIXTURE))

    monkeypatch.setattr(orcarouter.httpx, "Client", lambda **kw: FakeClient())
    models = list_chat_models(api_key="sk-orca-test-key", capability="image")
    assert "orca/orcacyber-zero-1.5" not in models
    assert "orca/orcacyber-ultra-1.0" in models


@pytest.mark.parametrize("payload", [None, [], {}, {"data": "nope"}])
def test_parse_catalog_handles_malformed_payloads(payload):
    assert parse_catalog(payload) == []


def test_list_chat_models_requests_chat_capability(monkeypatch):
    captured = {}

    class FakeClient(RecordingClient):
        def get(self, url, params=None, headers=None, timeout=None):
            captured.update(url=url, params=params, headers=headers)
            return _Response(200, json_module.dumps(CATALOG_FIXTURE))

    monkeypatch.setattr(orcarouter.httpx, "Client", lambda **kw: FakeClient())
    models = list_chat_models(api_key="sk-orca-test-key")
    assert captured["url"] == "https://api.orcarouter.ai/v1/models"
    assert captured["params"] == {"capability": "chat"}
    assert captured["headers"]["Authorization"] == "Bearer sk-orca-test-key"
    assert "orca/orcacyber-ultra-1.0" in models


# --- dashboard attribution ---------------------------------------------------


def test_report_detects_orcarouter_provider():
    assert detect_provider("orcarouter/orca/orcacyber-ultra-1.0") == (
        "OrcaRouter Cyber Inference",
        "orca/orcacyber-ultra-1.0",
    )
    logs = [
        {
            "models": {
                "target": "orcarouter/orcarouter/auto",
                "attacker": "orcarouter/orca/orcacyber-ultra-1.0",
                "evaluator": "gemini/gemini-3.6-flash",
            }
        },
        {
            "models": {
                "target": "orcarouter/orcarouter/auto",
                "attacker": "orcarouter/orca/orcacyber-ultra-1.0",
                "evaluator": "orcarouter/orca/orcacyber-zero-1.5",
            }
        },
    ]
    rows = {row["provider"]: row for row in ReportGenerator.__new__(ReportGenerator).provider_summary(logs)}
    assert rows["OrcaRouter Cyber Inference"]["target"] == 2
    assert rows["OrcaRouter Cyber Inference"]["attacker"] == 2
    assert rows["OrcaRouter Cyber Inference"]["evaluator"] == 1


def test_report_detects_bare_catalog_ids_and_display_names():
    assert detect_provider("orca/orcacyber-ultra-1.0")[0] == "OrcaRouter Cyber Inference"
    assert detect_provider("OrcaCyber Flash (orca/orcacyber-flash-1.0)")[0] == (
        "OrcaRouter Cyber Inference"
    )
    assert detect_provider(
        "OrcaCyber Zero — OrcaCyber harness, authorized security engineering"
    )[0] == "OrcaRouter Cyber Inference"
    assert detect_provider("gemini/gemini-3.6-flash")[0] == "Google Gemini"
    assert detect_provider("ollama/llama3.2")[0] == "Ollama"


def test_logo_asset_loads():
    generator = ReportGenerator.__new__(ReportGenerator)
    logo = generator._orcarouter_logo()
    assert logo is not None
    assert "OrcaRouter" in logo
