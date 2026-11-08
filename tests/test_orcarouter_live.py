"""Live connectivity test for the OrcaRouter provider (runs only with -m live).

Uses the real provider registration and the pipeline's role classes, so a
pass proves the request went through the code path shipped in this PR rather
than a bare HTTP call. Skipped when ORCAROUTER_API_KEY is not present.
"""

import os

import pytest

from src.orcarouter import list_chat_models
from src.target import TargetLLM

pytestmark = pytest.mark.live

# First entry that the current key can call; the verification key is scoped to
# these models. Not a user-facing recommendation (see README for tiers).
LIVE_PROBE_MODELS = (
    "orcarouter/orca/orcacyber-zero-1.5",
    "orcarouter/orca/orcacyber-ultra-1.0",
    "orcarouter/deepseek/deepseek-v4.1-flash",
)


@pytest.mark.skipif(not os.environ.get("ORCAROUTER_API_KEY"), reason="ORCAROUTER_API_KEY not set")
def test_live_catalog_returns_chat_models_through_provider():
    models = list_chat_models(capability="chat")
    assert models, "live catalog returned no chat models"
    assert all("/" in model for model in models)
    assert any(model.startswith("orcarouter/") for model in models)


@pytest.mark.skipif(not os.environ.get("ORCAROUTER_API_KEY"), reason="ORCAROUTER_API_KEY not set")
def test_live_chat_completion_through_role_class():
    errors = []
    for model in LIVE_PROBE_MODELS:
        try:
            reply = TargetLLM(model).respond(
                [{"role": "user", "content": "Reply with the single word ORCA-OK."}]
            )
        except Exception as exc:  # record and try the next scoped model
            errors.append(f"{model}: {exc}")
            continue
        assert isinstance(reply, str) and reply.strip()
        return
    pytest.fail("no live probe model was callable: " + "; ".join(errors))
