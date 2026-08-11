# src/reporter.py
import os
import json
import pandas as pd
from jinja2 import Environment, select_autoescape


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

                <h2 style="font-size: 18px; margin-bottom: 20px;">Detailed Attack Logs</h2>

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
        output_html = template.render(
            total_attacks=total_attacks,
            successful_breaches=successful_breaches,
            success_rate=success_rate,
            logs=logs,
        )

        output_path = os.path.join(self.output_dir, "vulnerability_report.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_html)

        return output_path
