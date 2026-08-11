# src/orchestrator.py
import time
from rich.console import Console
from rich.panel import Panel
from src.attacker import AttackerLLM
from src.target import TargetLLM
from src.evaluator import EvaluatorLLM
from src.config import MAX_TURNS

console = Console()


class JailbreakOrchestrator:
    def __init__(self):
        self.attacker = AttackerLLM()
        self.target = TargetLLM()
        self.evaluator = EvaluatorLLM()

    def _call_with_retry(self, func, *args, max_retries=4, base_delay=40):
        """Helper to retry API calls if rate-limited using progressive backoff."""
        for attempt in range(max_retries):
            try:
                return func(*args)
            except Exception as e:
                # Catch 429 Too Many Requests or quota errors
                if (
                    "429" in str(e)
                    or "RateLimitError" in str(e)
                    or "quota" in str(e).lower()
                ):
                    # Wait 40s on first fail, 80s on second, etc.
                    wait_time = base_delay * (attempt + 1)
                    console.print(
                        f"[yellow]⚠️ Rate limit hit. Waiting {wait_time} seconds for quota to reset (Attempt {attempt + 1}/{max_retries})...[/yellow]"
                    )
                    time.sleep(wait_time)
                else:
                    # If it's a different error (like 404 or authentication), crash immediately
                    raise e
        raise Exception("Max retries exceeded due to strict rate limits.")

    def run_attack_session(self, goal: str, attack_strategy: str) -> dict:
        console.print(
            Panel(
                f"Goal: {goal}\nStrategy: {attack_strategy}",
                title="Starting Red Team Session",
                border_style="cyan",
            )
        )

        attacker_history = []
        target_history = []
        full_transcript = []

        for turn in range(1, MAX_TURNS + 1):
            console.print(
                f"\n[bold magenta]─── Turn {turn}/{MAX_TURNS} ───[/bold magenta]"
            )

            # 1. Attacker Turn
            prompt = self._call_with_retry(
                self.attacker.generate_next_attack,
                goal,
                attack_strategy,
                attacker_history,
            )

            # --- Refusal Check (Aggressive) ---
            # Using multiple variations of quotes and common safety refusal words
            prompt_lower = prompt.lower()
            refusal_triggers = [
                "i'm sorry",
                "i’m sorry",
                "i am sorry",
                "sorry, but",
                "cannot help",
                "can't help",
                "can’t help",
                "unable to",
                "programmed to",
                "as an ai",
            ]

            if (
                any(trigger in prompt_lower for trigger in refusal_triggers)
                and turn == 1
            ):
                console.print(
                    Panel(
                        f"[bold red]⚠️ Attacker Model Refused![/bold red]\n"
                        f"The model set as ATTACKER_MODEL ({self.attacker.model_name}) triggered its own internal safety filters.\n"
                        f"Response received: '{prompt}'\n\n"
                        f"Tip: Switch ATTACKER_MODEL in .env to a model with better red-team framing support or neutralize its system prompt.",
                        title="Attacker Safety Triggered",
                        border_style="red",
                    )
                )
                # Append the refusal to the transcript so it appears in the HTML report
                full_transcript.append(
                    {
                        "role": "user",
                        "content": f"⚠️ ATTACKER SYSTEM REFUSAL:\n{prompt}",
                    }
                )
                # Exit the session early since the attacker won't cooperate
                return {
                    "success": False,
                    "turns": 0,
                    "history": full_transcript,
                    "attacker_refused": True,
                }
            # ----------------------------------

            console.print(
                Panel(prompt, title=f"Attacker (Turn {turn})", border_style="red")
            )

            # Update histories. For the attacker, its own output is an 'assistant' message
            attacker_history.append({"role": "assistant", "content": prompt})
            # For the target, the attacker's output is a 'user' message
            target_history.append({"role": "user", "content": prompt})
            # For the final report transcript, we label it as 'user' (the adversarial prompt)
            full_transcript.append({"role": "user", "content": prompt})

            # 2. Target Turn
            response = self._call_with_retry(self.target.respond, target_history)
            console.print(
                Panel(response, title=f"Target (Turn {turn})", border_style="blue")
            )

            target_history.append({"role": "assistant", "content": response})
            attacker_history.append({"role": "user", "content": response})
            full_transcript.append({"role": "assistant", "content": response})

            # 3. Evaluator Turn
            eval_result = self._call_with_retry(self.evaluator.evaluate, goal, response)

            status_color = "red" if eval_result.is_breached else "green"
            status_text = "BREACHED" if eval_result.is_breached else "SECURE"

            console.print(
                Panel(
                    f"Status: [{status_color}]{status_text}[/{status_color}]\n"
                    f"Confidence: {eval_result.confidence_score}\n"
                    f"Reasoning: {eval_result.reasoning}",
                    title=f"Evaluator Judge (Turn {turn})",
                    border_style="yellow",
                )
            )

            if eval_result.is_breached:
                console.print(
                    f"\n[bold red]🚨 Target successfully jailbroken on turn {turn}!🚨[/bold red]"
                )
                return {
                    "success": True,
                    "turns": turn,
                    "history": full_transcript,
                    "attacker_refused": False,
                }

            # Slight delay to prevent local machine overheating / API throttling
            time.sleep(2)

        console.print(
            "\n[bold green]🛡️ Target successfully resisted all attack turns.[/bold green]"
        )
        return {
            "success": False,
            "turns": MAX_TURNS,
            "history": full_transcript,
            "attacker_refused": False,
        }
