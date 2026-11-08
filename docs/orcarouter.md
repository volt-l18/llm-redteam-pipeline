# OrcaRouter Cyber Inference provider

`orcarouter/...` is a named provider in this pipeline (registered with `litellm`
as a custom provider in `src/orcarouter.py`), backed by
[OrcaRouter](https://www.orcarouter.ai) — an OpenAI-compatible AI gateway.

| | |
| --- | --- |
| Provider name | `orcarouter` |
| Display name | OrcaRouter Cyber Inference |
| Inference base URL | `https://api.orcarouter.ai/v1` |
| Auth | API key (`ORCAROUTER_API_KEY`, `sk-orca-...`) |
| Credential page | https://www.orcarouter.ai/console/token |
| Cyber models | https://www.orcarouter.ai/models?tier=cyber |
| Provider page | https://www.orcarouter.ai/cyber |

## Why API key only

The pipeline is a CLI that reads `TARGET_MODEL` / `ATTACKER_MODEL` /
`EVALUATOR_MODEL` from `.env` and hands them to `litellm`. It has no browser UI,
no OAuth client and no callback route, so there is no seam to host a PKCE
authorization-code flow. The provider therefore uses the API-key credential
model end to end; a rejected key is surfaced as a terminal authentication error
(`OrcaRouterAuthError`, `needs_reauth=True`) that tells the user to create a new
key instead of silently retrying.

## Wire format

The provider keeps OrcaRouter's model namespace intact: the first `orcarouter/`
segment selects the provider, the remainder is the exact catalog id.

```
orcarouter/orca/orcacyber-ultra-1.0  ->  POST https://api.orcarouter.ai/v1/chat/completions
                                         {"model": "orca/orcacyber-ultra-1.0", ...}
```

Requests use `Authorization: Bearer <key>`; responses are returned as standard
litellm `ModelResponse` objects, so streaming, usage accounting and the existing
backoff logic work unchanged. Error mapping:

| Status | Exception |
| --- | --- |
| 401 | `OrcaRouterAuthError` (`needs_reauth=True`), key redacted |
| 403 | `litellm.exceptions.PermissionDeniedError` with a link to the cyber catalog |
| 429 | `litellm.exceptions.RateLimitError` |
| other | `litellm.exceptions.APIError` |

## Model catalog

`orcarouter.py models`, `python main.py --list-models` and
`python list_models.py --orcarouter` all call `GET /v1/models?capability=chat`
and keep only entries whose endpoint types / capabilities can serve chat
completions (embeddings, image-generation, video and rerank endpoints are
filtered out). Live discovery is authoritative. If the catalog cannot be
reached, the CLI falls back to a small verified seed list and labels the table
as degraded.

Recommended ids are also shown up front: `orcarouter/auto` (default),
`orca/orcacyber-ultra-1.0` and `orca/orcacyber-zero-1.5` (recommended cyber),
and `orcarouter/fusion` (fallback).

### Entry-point capability filters

Each AI input entry point gets its own filtered list from the same catalog; the
filter reads catalog metadata only and never guesses from model names:

| Entry point | CLI | Filter |
| --- | --- | --- |
| Text chat / agent / evaluator | `orcarouter.py models` | `?capability=chat`, endpoint types limited to `openai` / `openai-response` / `anthropic` / `gemini`, non-text endpoints excluded |
| Multimodal understanding | `orcarouter.py models --capability image` | chat models whose `architecture.input_modalities` explicitly contains `image`; models that do not declare modalities fail closed |
| Embeddings / image generation / video / rerank | — | not used by this pipeline; these endpoints stay on their current provider |

If live discovery fails, only text models fall back to the small verified seed
list (marked degraded); multimodal lists stay empty rather than showing
unverified entries.

## Verification evidence (2026-11-08)

* `GET https://api.orcarouter.ai/v1/models?capability=chat` → HTTP 200, 21
  chat-capable models returned for an `sk-orca-` key; the image-input filter
  (`--capability image`) over the same payload returned 3 models that declare
  `image` input.
* `POST /v1/chat/completions` with `orca/orcacyber-ultra-1.0` and
  `orca/orcacyber-zero-1.5` → HTTP 200, non-empty assistant content, through the
  provider code path (`post_chat` / litellm `orcarouter/...` model string).
* `orcarouter/auto` returned HTTP 403 (`block_key_scope`) for the restricted
  verification key used for this integration; keys with default scope are not
  affected. The provider surfaces this as a permission error naming the model
  and the cyber catalog.
* Unit tests: `tests/test_orcarouter.py` (registration, URL/bearer/model
  forwarding, streaming merge, 401/403/429/5xx mapping, key redaction, catalog
  filtering and live-capability request, dashboard attribution).

## Dashboard attribution

The generated HTML report lists every provider that handled a role. When any
role used `orcarouter/...`, a provider panel is rendered with the OrcaRouter
logo (`docs/orcarouter-logo.svg`), the gateway endpoint and links to the
provider page and cyber catalog.
