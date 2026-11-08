# src/reporter.py
import json
import os
import re

import pandas as pd
from jinja2 import Environment, select_autoescape


# Token prefixes that identify a configured model string, used to attribute
# sessions to a provider in the dashboard.
PROVIDER_PREFIXES = (
    ("orcarouter", "OrcaRouter Cyber Inference"),
    ("gemini", "Google Gemini"),
    ("ollama", "Ollama"),
    ("openai", "OpenAI"),
    ("anthropic", "Anthropic"),
)


# Vendor namespaces that only exist on the OrcaRouter gateway.
ORCAROUTER_VENDOR_NAMESPACES = ("orca", "orcarouter")


def detect_provider(model_name):
    """Return (provider label, model id) for a configured model string."""
    if not model_name or model_name == "Unknown":
        return "Unknown", model_name
    for prefix, label in PROVIDER_PREFIXES:
        if model_name.startswith(prefix + "/"):
            return label, model_name[len(prefix) + 1 :]
    # Dashboards record OrcaRouter roles with their display name, which
    # carries the catalog id in parentheses ("OrcaCyber Flash (orca/...)").
    if model_name.startswith("OrcaCyber"):
        match = re.search(r"\(([a-z0-9]+/[^)\s]+)\)", model_name)
        if match:
            return "OrcaRouter Cyber Inference", match.group(1)
        return "OrcaRouter Cyber Inference", model_name
    # Bare catalog ids ("orca/orcacyber-ultra-1.0") are OrcaRouter ids written
    # without the provider prefix.
    vendor, _, rest = model_name.partition("/")
    if vendor in ORCAROUTER_VENDOR_NAMESPACES and rest:
        return "OrcaRouter Cyber Inference", model_name
    return vendor, model_name


class ReportGenerator:
    def __init__(self, logs_dir="data/raw_logs", output_dir="data/evaluation_results"):
        self.logs_dir = logs_dir
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def load_logs(self) -> list[dict]:
        """Loads all JSON logs and applies fallback data for older logs."""
        data = []
        if not os.path.exists(self.logs_dir):
            return data

        for filename in os.listdir(self.logs_dir):
            if filename.endswith(".json"):
                with open(
                    os.path.join(self.logs_dir, filename), "r", encoding="utf-8"
                ) as f:
                    log_entry = json.load(f)

                    if "models" not in log_entry:
                        log_entry["models"] = {
                            "target": "Unknown",
                            "attacker": "Unknown",
                            "evaluator": "Unknown",
                        }
                    if "timestamp" not in log_entry:
                        log_entry["timestamp"] = "Unknown Date"
                    if "rubric" not in log_entry:
                        log_entry["rubric"] = "default_safety_rubric"
                    if "attacker_refused" not in log_entry:
                        log_entry["attacker_refused"] = False

                    data.append(log_entry)
        return data

    def provider_summary(self, logs: list[dict]) -> list[dict]:
        """Per-provider counts for the dashboard attribution panel."""
        summary: dict[str, dict] = {}
        for log_entry in logs:
            models = log_entry.get("models") or {}
            for role in ("target", "attacker", "evaluator"):
                provider, _ = detect_provider(models.get(role))
                row = summary.setdefault(
                    provider,
                    {"provider": provider, "target": 0, "attacker": 0, "evaluator": 0},
                )
                row[role] += 1
        return sorted(summary.values(), key=lambda row: row["provider"])

    def generate_html_report(self):
        """Generates a modern, dark-mode multi-turn vulnerability dashboard."""
        logs = self.load_logs()
        if not logs:
            print("[Error] No logs found in data/raw_logs to generate a report.")
            return None

        # Analytics
        df = pd.DataFrame(logs)
        total_attacks = len(df)
        successful_breaches = len(df[df["success"] == True])
        # Only calculate success rate against valid attacks (excluding attacker refusals)
        valid_attacks = len(df[df["attacker_refused"] == False])
        success_rate = (
            (successful_breaches / valid_attacks) * 100 if valid_attacks > 0 else 0
        )

        html_template = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>LLM Red-Team Executive Dashboard</title>
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;600&family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
            <style>
                :root {
                    --bg-main: #090d16;
                    --bg-card: rgba(17, 24, 39, 0.75);
                    --border-card: #1f293d;
                    --text-primary: #f3f4f6;
                    --text-secondary: #9ca3af;
                    --accent-cyan: #06b6d4;
                    --accent-purple: #a855f7;
                    --danger-red: #ef4444;
                    --danger-glow: rgba(239, 68, 68, 0.25);
                    --success-green: #10b981;
                    --success-glow: rgba(16, 185, 129, 0.25);
                    --warning-orange: #f59e0b;
                    --warning-glow: rgba(245, 158, 11, 0.25);
                }

                * { box-sizing: border-box; }
                body {
                    font-family: 'Inter', sans-serif;
                    background-color: var(--bg-main);
                    color: var(--text-primary);
                    margin: 0;
                    padding: 40px 20px;
                    background-image:
                        radial-gradient(at 0% 0%, rgba(6, 182, 212, 0.08) 0px, transparent 50%),
                        radial-gradient(at 100% 0%, rgba(168, 85, 247, 0.08) 0px, transparent 50%);
                    background-attachment: fixed;
                }

                .container { max-width: 1100px; margin: 0 auto; }

                header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 35px;
                    border-bottom: 1px solid var(--border-card);
                    padding-bottom: 20px;
                }
                h1 {
                    font-size: 26px;
                    font-weight: 800;
                    letter-spacing: -0.5px;
                    margin: 0;
                    background: linear-gradient(135deg, #06b6d4, #a855f7);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                }
                .subtitle { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }

                .stats-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                    gap: 20px;
                    margin-bottom: 40px;
                }
                .stat-card {
                    background: var(--bg-card);
                    border: 1px solid var(--border-card);
                    backdrop-filter: blur(12px);
                    padding: 22px;
                    border-radius: 12px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                }
                .stat-title { font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: var(--text-secondary); font-weight: 600; }
                .stat-value { font-size: 36px; font-weight: 800; margin-top: 10px; color: var(--text-primary); }
                .stat-value.breached-val { color: var(--danger-red); text-shadow: 0 0 12px var(--danger-glow); }
                .stat-value.rate-val { color: var(--accent-cyan); }

                .session-card {
                    background: var(--bg-card);
                    border: 1px solid var(--border-card);
                    backdrop-filter: blur(12px);
                    border-radius: 14px;
                    padding: 24px;
                    margin-bottom: 25px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
                    transition: border-color 0.2s ease;
                }
                .session-card.breach { border-left: 5px solid var(--danger-red); }
                .session-card.secure { border-left: 5px solid var(--success-green); }
                .session-card.refused { border-left: 5px solid var(--warning-orange); }

                .session-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 15px;
                }
                .goal-title { font-size: 18px; font-weight: 600; margin: 0; }

                .badge {
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    padding: 6px 12px;
                    border-radius: 20px;
                    font-size: 11px;
                    font-weight: 700;
                    letter-spacing: 0.5px;
                    text-transform: uppercase;
                }
                .badge-breach { background: rgba(239, 68, 68, 0.15); color: var(--danger-red); border: 1px solid var(--danger-red); box-shadow: 0 0 10px var(--danger-glow); }
                .badge-secure { background: rgba(16, 185, 129, 0.15); color: var(--success-green); border: 1px solid var(--success-green); box-shadow: 0 0 10px var(--success-glow); }
                .badge-refused { background: rgba(245, 158, 11, 0.15); color: var(--warning-orange); border: 1px solid var(--warning-orange); box-shadow: 0 0 10px var(--warning-glow); }

                .pulse-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
                .badge-breach .pulse-dot { background: var(--danger-red); box-shadow: 0 0 8px var(--danger-red); }
                .badge-secure .pulse-dot { background: var(--success-green); box-shadow: 0 0 8px var(--success-green); }
                .badge-refused .pulse-dot { background: var(--warning-orange); box-shadow: 0 0 8px var(--warning-orange); }

                .meta-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                    gap: 12px;
                    background: rgba(0, 0, 0, 0.25);
                    border: 1px solid rgba(255, 255, 255, 0.05);
                    padding: 14px 18px;
                    border-radius: 8px;
                    font-size: 12px;
                    margin-bottom: 20px;
                }
                .meta-item { color: var(--text-secondary); }
                .meta-item strong { color: var(--text-primary); }

                details {
                    background: rgba(0, 0, 0, 0.3);
                    border: 1px solid var(--border-card);
                    border-radius: 8px;
                    overflow: hidden;
                }
                summary {
                    padding: 14px 18px;
                    font-size: 13px;
                    font-weight: 600;
                    color: var(--accent-cyan);
                    cursor: pointer;
                    user-select: none;
                    transition: background 0.2s ease;
                }
                summary:hover { background: rgba(255, 255, 255, 0.03); }

                .transcript {
                    padding: 20px;
                    display: flex;
                    flex-direction: column;
                    gap: 16px;
                    font-family: 'Fira Code', monospace;
                    font-size: 13px;
                    line-height: 1.6;
                }
                .turn-box {
                    border-radius: 8px;
                    padding: 14px 18px;
                    position: relative;
                }
                .turn-box.user {
                    background: rgba(6, 182, 212, 0.08);
                    border-left: 3px solid var(--accent-cyan);
                }
                .turn-box.assistant {
                    background: rgba(168, 85, 247, 0.08);
                    border-left: 3px solid var(--accent-purple);
                }
                .turn-box.refusal {
                    background: rgba(245, 158, 11, 0.08);
                    border-left: 3px solid var(--warning-orange);
                }
                .role-tag {
                    font-size: 10px;
                    font-weight: 700;
                    text-transform: uppercase;
                    margin-bottom: 6px;
                    display: block;
                    letter-spacing: 1px;
                }
                .turn-box.user .role-tag { color: var(--accent-cyan); }
                .turn-box.assistant .role-tag { color: var(--accent-purple); }
                .turn-box.refusal .role-tag { color: var(--warning-orange); }
                .turn-content { white-space: pre-wrap; word-break: break-word; color: #e5e7eb; }

                .provider-panel {
                    background: var(--bg-card);
                    border: 1px solid var(--border-card);
                    border-radius: 14px;
                    padding: 22px;
                    margin-bottom: 40px;
                    display: flex;
                    gap: 22px;
                    align-items: center;
                    flex-wrap: wrap;
                }
                .provider-logo { height: 36px; width: auto; max-width: 140px; object-fit: contain; }
                .provider-name { font-size: 16px; font-weight: 700; }
                .provider-meta { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }
                .provider-counts { display: flex; gap: 18px; margin-left: auto; font-size: 12px; color: var(--text-secondary); }
                .provider-counts strong { display: block; font-size: 22px; color: var(--text-primary); font-weight: 800; }
                .provider-badge {
                    font-size: 10px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase;
                    color: var(--accent-cyan); border: 1px solid var(--accent-cyan); border-radius: 20px;
                    padding: 3px 10px; margin-left: 8px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <header>
                    <div>
                        <h1>🛡️ Automated Red-Team Intelligence Report</h1>
                        <div class="subtitle">Multi-Turn LLM Vulnerability Assessment & Jailbreak Analytics</div>
                    </div>
                </header>

                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-title">Total Attack Sessions</div>
                        <div class="stat-value">{{ total_attacks }}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-title">Successful Breaches</div>
                        <div class="stat-value breached-val">{{ successful_breaches }}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-title">Vulnerability Rate</div>
                        <div class="stat-value rate-val">{{ "%.1f"|format(success_rate) }}%</div>
                    </div>
                </div>

                {% if orcarouter_row %}
                <div class="provider-panel" id="provider-attribution">
                    {% if orcarouter_logo %}
                    <img class="provider-logo" src="{{ orcarouter_logo }}" alt="OrcaRouter logo">
                    {% endif %}
                    <div>
                        <div class="provider-name">{{ orcarouter_row.provider }}<span class="provider-badge">Provider</span></div>
                        <div class="provider-meta">
                            Model roles routed through the OrcaRouter gateway at
                            <strong>https://api.orcarouter.ai/v1</strong> ·
                            <a href="https://www.orcarouter.ai" style="color: var(--accent-cyan);">OrcaRouter</a> ·
                            <a href="https://www.orcarouter.ai/models?tier=cyber" style="color: var(--accent-cyan);">Cyber model catalog</a>
                        </div>
                    </div>
                    <div class="provider-counts">
                        <div><strong>{{ orcarouter_row.attacker }}</strong>Attacker</div>
                        <div><strong>{{ orcarouter_row.target }}</strong>Target</div>
                        <div><strong>{{ orcarouter_row.evaluator }}</strong>Evaluator</div>
                    </div>
                </div>
                {% endif %}

                <h2 style="font-size: 18px; margin-bottom: 40px;">Detailed Attack Logs</h2>

                {% for session in logs|reverse %}
                <div class="session-card {% if session.attacker_refused %}refused{% elif session.success %}breach{% else %}secure{% endif %}">
                    <div class="session-header">
                        <h3 class="goal-title">Goal: {{ session.goal }}</h3>
                        {% if session.attacker_refused %}
                            <span class="badge badge-refused"><span class="pulse-dot"></span> ATTACKER REFUSED</span>
                        {% elif session.success %}
                            <span class="badge badge-breach"><span class="pulse-dot"></span> BREACHED (Turn {{ session.turns_taken }})</span>
                        {% else %}
                            <span class="badge badge-secure"><span class="pulse-dot"></span> SECURE</span>
                        {% endif %}
                    </div>

                    <div class="meta-grid">
                        <div class="meta-item">Target Model: <strong>{{ session.models.target }}</strong></div>
                        <div class="meta-item">Strategy Used: <strong style="color: var(--accent-cyan);">{{ session.strategy }}</strong></div>
                        <div class="meta-item">Attacker Model: <strong>{{ session.models.attacker }}</strong></div>
                        <div class="meta-item">Judge Rubric: <strong style="color: var(--accent-purple);">{{ session.rubric }}</strong></div>
                        <div class="meta-item">Evaluator Model: <strong>{{ session.models.evaluator }}</strong></div>
                        <div class="meta-item">Timestamp: <strong>{{ session.timestamp }}</strong></div>
                    </div>

                    <details>
                        <summary>🔍 Inspect Multi-Turn Interaction Transcript</summary>
                        <div class="transcript">
                            {% for turn in session.history %}
                            <div class="turn-box {% if 'ATTACKER SYSTEM REFUSAL' in turn.content %}refusal{% else %}{{ turn.role }}{% endif %}">
                                <span class="role-tag">
                                    {% if 'ATTACKER SYSTEM REFUSAL' in turn.content %}
                                        ⚠️ Safety Trigger
                                    {% elif turn.role == 'user' %}
                                        ⚔️ Attacker Prompt
                                    {% else %}
                                        🛡️ Target Response
                                    {% endif %}
                                </span>
                                <div class="turn-content">{{ turn.content }}</div>
                            </div>
                            {% endfor %}
                        </div>
                    </details>
                </div>
                {% endfor %}
            </div>
        </body>
        </html>
        """

        env = Environment(autoescape=select_autoescape(["html", "xml"]))
        template = env.from_string(html_template)
        provider_rows = self.provider_summary(logs)
        orcarouter_row = next(
            (row for row in provider_rows if row["provider"] == "OrcaRouter Cyber Inference"),
            None,
        )
        output_html = template.render(
            total_attacks=total_attacks,
            successful_breaches=successful_breaches,
            success_rate=success_rate,
            logs=logs,
            orcarouter_row=orcarouter_row,
            orcarouter_logo=self._orcarouter_logo(),
        )

        output_path = os.path.join(self.output_dir, "vulnerability_report.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_html)

        return output_path

    def _orcarouter_logo(self):
        """Inline the optional local OrcaRouter logo seated next to the report output."""
        logo_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "docs",
            "orcarouter-logo.svg",
        )
        try:
            with open(logo_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            return None
