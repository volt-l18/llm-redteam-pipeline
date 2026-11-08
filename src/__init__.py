"""Automated LLM Multi-Turn Jailbreak Pipeline Source Package."""

from src.attacker import AttackerLLM
from src.target import TargetLLM
from src.evaluator import EvaluatorLLM
from src.orchestrator import JailbreakOrchestrator
from src.reporter import ReportGenerator
from src.orcarouter import register_provider

__all__ = [
    "AttackerLLM",
    "TargetLLM",
    "EvaluatorLLM",
    "JailbreakOrchestrator",
    "ReportGenerator",
    "register_provider",
]

# Make "orcarouter/..." a first-class litellm provider (OrcaRouter Cyber Inference)
# for every entry point that imports the package (CLI, tests, notebooks).
register_provider()
