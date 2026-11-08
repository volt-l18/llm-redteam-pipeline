"""CLI helpers for the OrcaRouter Cyber Inference provider.

* ``show_models``  — interactive model selector built from the live
  ``GET https://api.orcarouter.ai/v1/models`` catalog (chat-capable models only).
* ``show_status``  — key presence, masked, never printed in full.
* ``explain_error``— turn provider exceptions into actionable guidance.
"""

from __future__ import annotations

import sys

import litellm
from rich.console import Console
from rich.table import Table

from src.orcarouter import (
    CYBER_CATALOG_URL,
    CYBER_PAGE_URL,
    KEY_DASHBOARD_URL,
    PROVIDER_LABEL,
    RECOMMENDED_MODELS,
    VERIFIED_SEED_MODELS,
    OrcaRouterAuthError,
    list_chat_models,
    resolve_api_key,
)

console = Console(width=160)


def mask_key(key: str) -> str:
    """Show only enough of the key to recognise it."""
    if not key:
        return "(not set)"
    if len(key) <= 11:
        return "sk-orca-***"
    return "sk-orca-...****"


def render_recommendations() -> None:
    table = Table(title=f"{PROVIDER_LABEL} — recommended models", show_lines=False)
    table.add_column("Role", style="cyan")
    table.add_column("Model id", style="bold")
    for entry in RECOMMENDED_MODELS:
        table.add_row(entry["role"], entry["label"])
    console.print(table)
    console.print(f"Cyber models: {CYBER_CATALOG_URL}")
    console.print(f"Provider page: {CYBER_PAGE_URL}")


_CAPABILITY_CHOICES = ("chat", "text", "image")


def _capability_name(capability: str) -> str:
    return "chat (text)" if capability == "text" else capability


def show_models(search: str = "", api_base: str | None = None, capability: str = "chat") -> int:
    """List selectable models from the real OrcaRouter catalog for one entry point.

    ``chat`` is the text chat/agent entry point, ``image`` is multimodal
    understanding (chat models that explicitly declare image input). Live
    discovery is authoritative. On failure the verified seed (only for text)
    is shown and clearly marked as degraded.
    """
    if capability == "text":
        capability = "chat"
    render_recommendations()
    if not resolve_api_key():
        console.print(
            f"[bold red]ORCAROUTER_API_KEY is not set.[/bold red] Add an sk-orca-... key "
            f"to .env (create one at {KEY_DASHBOARD_URL})."
        )
        return 2
    console.print(f"\nFetching live catalog from OrcaRouter (provider: {PROVIDER_LABEL})...")
    degraded = False
    try:
        models = list_chat_models(api_base=api_base, capability=capability)
        if not models:
            raise ValueError("catalog returned no chat models for this key")
        source = "live"
    except OrcaRouterAuthError as exc:
        console.print(f"[bold red]{exc}[/bold red]")
        return 2
    except Exception as exc:  # network / 5xx / malformed payload
        models = [m for m in VERIFIED_SEED_MODELS] if capability == "chat" else []
        source = "verified-seed"
        degraded = True
        console.print(f"[yellow]Catalog unavailable ({type(exc).__name__}); using verified seed.[/yellow]")
    if search:
        needle = search.lower()
        models = [m for m in models if needle in m.lower()]
    if not models:
        console.print(f"[yellow]No {_capability_name(capability)} models available.[/yellow]")
        return 0
    if degraded:
        table = Table(title="Verified seed (degraded: live catalog unavailable)")
    else:
        table = Table(title=f"Live OrcaRouter catalog ({len(models)} {_capability_name(capability)} models)")
    table.add_column("#", justify="right", no_wrap=True)
    table.add_column("Model id", no_wrap=True)
    table.add_column("Select with", no_wrap=True)
    for index, model_id in enumerate(models, start=1):
        table.add_row(str(index), model_id, f"orcarouter/{model_id}")
    console.print(table)
    console.print("Set e.g. ATTACKER_MODEL=orcarouter/orca/orcacyber-ultra-1.0 in .env")
    return 0


def show_status() -> int:
    key = resolve_api_key()
    console.print(f"[bold]{PROVIDER_LABEL}[/bold] status")
    console.print(f"  API base: https://api.orcarouter.ai/v1")
    console.print(f"  Key:      {mask_key(key or '')} ({'ORCAROUTER_API_KEY' if key else 'missing'})")
    if key:
        console.print("  Key format: looks like an OrcaRouter key" if key.startswith("sk-orca-") else "  Key format: unexpected (expected sk-orca-...)")
    return 0 if key else 2


def explain_error(exc: Exception) -> str:
    if isinstance(exc, OrcaRouterAuthError):
        return f"re-auth required: {exc}"
    if isinstance(exc, litellm.exceptions.AuthenticationError):
        return f"re-auth required (create a new key at {KEY_DASHBOARD_URL}): {exc}"
    if getattr(exc, "permission_denied", False):
        return f"OrcaRouter denied this model for the current key; see {CYBER_CATALOG_URL}: {exc}"
    if isinstance(exc, litellm.exceptions.RateLimitError) and "OrcaRouter" in str(exc):
        return f"OrcaRouter rate limited the request: {exc}"
    return str(exc)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="OrcaRouter Cyber Inference CLI")
    parser.add_argument("action", choices=["models", "status"])
    parser.add_argument(
        "--capability",
        choices=_CAPABILITY_CHOICES,
        default="chat",
        help="entry-point capability filter: chat (text), image (multimodal understanding)",
    )
    parser.add_argument("--search", default="", help="filter model ids by substring")
    args = parser.parse_args(argv)
    if args.action == "models":
        return show_models(search=args.search, capability=args.capability)
    return show_status()


if __name__ == "__main__":
    sys.exit(main())
