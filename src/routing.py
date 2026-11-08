"""Per-model routing kwargs for litellm completion calls."""

from src.config import ORCAROUTER_API_BASE
from src.orcarouter import is_orcarouter_model


def model_kwargs(model_name: str | None) -> dict:
    """Extra kwargs for a litellm call with ``model_name``.

    OrcaRouter calls use ``ORCAROUTER_API_BASE_URL`` when set (self-hosted or
    staging gateway); otherwise the provider's default inference endpoint is
    used. Non-OrcaRouter models get no extra kwargs, so existing providers keep
    their current behaviour.
    """
    if ORCAROUTER_API_BASE and is_orcarouter_model(model_name):
        return {"api_base": ORCAROUTER_API_BASE}
    return {}
