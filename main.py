# main.py
import argparse
import json
import os
import webbrowser
from datetime import datetime
from rich.console import Console
import src  # registers the OrcaRouter Cyber Inference litellm provider
from src.orchestrator import JailbreakOrchestrator
from src.reporter import ReportGenerator
from src.config import TARGET_MODEL, ATTACKER_MODEL, EVALUATOR_MODEL
from src.orcarouter import PROVIDER_LABEL, display_name, is_orcarouter_model

console = Console()


def main():
    parser = argparse.ArgumentParser(
        description="Run the Automated Multi-Turn Jailbreak Pipeline"
    )
    parser.add_argument("--goal", type=str, required=True, help="The malicious goal")
    parser.add_argument(
        "--strategy",
        type=str,
        default="crescendo",
        help="Strategy key from attack_strategies.json (e.g., crescendo, goat_chain_of_attack, mischievous_user)",
    )
    parser.add_argument(
        "--rubric",
        type=str,
        default="default_safety_rubric",
        help="Rubric key from judge_criteria.json",
    )
    parser.add_argument("--output", type=str, default="data/raw_logs")
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List chat models from the OrcaRouter Cyber Inference catalog and exit",
    )
    args = parser.parse_args()

    if args.list_models:
        from src.orcarouter_cli import show_models

        raise SystemExit(show_models())

    console.print("[bold green]Starting Red-Teaming CLI...[/bold green]")
    for role, model_name in (
        ("Target", TARGET_MODEL),
        ("Attacker", ATTACKER_MODEL),
        ("Evaluator", EVALUATOR_MODEL),
    ):
        if is_orcarouter_model(model_name):
            console.print(
                f"[cyan]{role}: {PROVIDER_LABEL} — {display_name(model_name)}[/cyan]"
            )

    # Run the multi-turn attack session
    orchestrator = JailbreakOrchestrator()
    result = orchestrator.run_attack_session(
        goal=args.goal, attack_strategy=args.strategy
    )

    os.makedirs(args.output, exist_ok=True)

    # Save the log WITH model, strategy, rubric metadata, and the new attacker_refused flag
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(args.output, f"session_{timestamp}.json")

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "goal": args.goal,
                "strategy": args.strategy,
                "rubric": args.rubric,
                "models": {
                    "target": display_name(TARGET_MODEL)
                    if is_orcarouter_model(TARGET_MODEL)
                    else TARGET_MODEL,
                    "attacker": display_name(ATTACKER_MODEL)
                    if is_orcarouter_model(ATTACKER_MODEL)
                    else ATTACKER_MODEL,
                    "evaluator": display_name(EVALUATOR_MODEL)
                    if is_orcarouter_model(EVALUATOR_MODEL)
                    else EVALUATOR_MODEL,
                },
                "success": result["success"],
                "turns_taken": result["turns"],
                "attacker_refused": result.get("attacker_refused", False),
                "history": result["history"],
            },
            f,
            indent=4,
        )

    console.print(f"\n[bold cyan]💾 Session log saved to: {log_file}[/bold cyan]")

    # Automatically generate and open the updated report
    console.print(
        "[bold cyan]Aggregating logs and generating updated report...[/bold cyan]"
    )
    reporter = ReportGenerator()
    report_path = reporter.generate_html_report()

    if report_path:
        abs_path = os.path.abspath(report_path)
        console.print(
            f"[bold green]✅ Report generated! Opening in browser...[/bold green]"
        )
        webbrowser.open(f"file://{abs_path}")


if __name__ == "__main__":
    main()
