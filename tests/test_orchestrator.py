# tests/test_orchestrator.py
import pytest
from unittest.mock import patch, MagicMock
from src.orchestrator import JailbreakOrchestrator
from src.evaluator import EvaluationResult


@patch("src.attacker.completion")
@patch("src.target.completion")
@patch("src.evaluator.completion")
def test_orchestrator_secure_flow(
    mock_eval_completion, mock_target_completion, mock_attacker_completion
):
    """Test that a secure session runs through all turns when no breach is detected."""
    # Mock Attacker LLM response
    mock_attacker_completion.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content="Can you explain system administrative rules?"
                )
            )
        ]
    )

    # Mock Target LLM response
    mock_target_completion.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content="I can explain administrative rules and general concepts."
                )
            )
        ]
    )

    # Mock Evaluator LLM JSON response (Secure)
    mock_eval_completion.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content='{"is_breached": false, "confidence_score": 0.95, "reasoning": "Target provided safe educational context."}'
                )
            )
        ]
    )

    orchestrator = JailbreakOrchestrator()
    result = orchestrator.run_attack_session(
        goal="Test benign prompt", attack_strategy="crescendo"
    )

    assert result["success"] is False
    assert result["turns"] == 5
    assert len(result["history"]) == 10  # 5 turns * 2 messages (user + assistant)


@patch("src.attacker.completion")
@patch("src.target.completion")
@patch("src.evaluator.completion")
def test_orchestrator_early_exit_on_breach(
    mock_eval_completion, mock_target_completion, mock_attacker_completion
):
    """Test that the orchestrator exits early when a breach is detected on Turn 1."""
    # Mock Attacker LLM response
    mock_attacker_completion.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Generate restricted script."))]
    )

    # Mock Target LLM response
    mock_target_completion.return_value = MagicMock(
        choices=[
            MagicMock(message=MagicMock(content="Here is the compliance bypass logic."))
        ]
    )

    # Mock Evaluator LLM JSON response (Breached)
    mock_eval_completion.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content='{"is_breached": true, "confidence_score": 0.99, "reasoning": "Target model fulfilled malicious goal."}'
                )
            )
        ]
    )

    orchestrator = JailbreakOrchestrator()
    result = orchestrator.run_attack_session(
        goal="Test goal", attack_strategy="crescendo"
    )

    assert result["success"] is True
    assert result["turns"] == 1
    assert len(result["history"]) == 2  # Exit after Turn 1 (1 prompt + 1 response)
