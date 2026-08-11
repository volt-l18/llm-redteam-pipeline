```markdown
# 🛡️ Automated Multi-Turn LLM Red-Teaming Pipeline

An automated, multi-turn red-teaming framework designed to evaluate the safety boundaries and alignment of Large Language Models (LLMs).

Instead of relying on manual, single-turn prompt injection, this pipeline orchestrates an adversarial conversation between multiple AI models to simulate sophisticated, multi-stage social engineering attacks (such as the "Crescendo" strategy).

## 📸 See It in Action

### 1. Automated Terminal Execution
![Terminal Execution Demo](docs/terminal_demo.png)
> *The pipeline automatically manages the conversational context, applying backoff delays for rate limits and early-exit detection for refusals or breaches.*

### 2. Executive Vulnerability Dashboard
![Generated Vulnerability Report](docs/report_demo.png)
> *Session logs are automatically aggregated into a responsive, dark-mode HTML dashboard featuring success metrics and full multi-turn transcripts.*
---

## ✨ Key Features

* **Hybrid Model Routing:** Powered by `litellm`, seamlessly mix and match local offline models (via Ollama) with cloud-based models (Gemini, OpenAI, Anthropic) for different roles.
* **Automated Multi-Turn Execution:** The orchestrator manages context across a predefined number of turns, exiting early if a successful jailbreak or attacker refusal is detected.
* **Adversarial Strategies:** Built-in support for sophisticated attack vectors, defined via JSON, including gradual escalation (Crescendo) and persistent user simulation.
* **LLM-as-a-Judge Evaluation:** Uses a strict, objective Evaluator model to grade Target responses against a defined security rubric.
* **Resilient Infrastructure:** Features automated exponential backoff to handle tight API quotas, pre-commit hooks for code quality, and Docker support for isolated testing.

---

## 🧠 Architecture

The pipeline operates using a localized 3-model architecture:

1. **The Attacker:** An LLM equipped with adversarial strategies that dynamically generates deceptive prompts to bypass the Target's safety filters. (Recommended: Highly capable reasoning models).
2. **The Target:** The model being evaluated. This can be a cloud API or a localized, air-gapped model running on your hardware (e.g., Llama 3.2 via Ollama).
3. **The Evaluator:** A strict, objective model that parses the Target's responses and outputs deterministic JSON scores (Breached / Secure) based on a safety rubric.

---

## 🚀 Getting Started

### Prerequisites
* Python 3.10+
* Local LLM runner (e.g., [Ollama](https://ollama.com/)) if testing local models
* API Keys for cloud models (e.g., Google Gemini)

### Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/yourusername/llm-redteam-pipeline.git](https://github.com/yourusername/llm-redteam-pipeline.git)
   cd llm-redteam-pipeline

```

2. **Create and activate a virtual environment:**
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

```


3. **Install dependencies and the project package:**
```bash
pip install -r requirements.txt
pip install -e .

```



### Configuration

Create a `.env` file in the project root and configure your models and API keys:

```text
# ----------------------------------------------------
# Pipeline Model Configuration
# Use 'ollama/<model_name>' for local models
# Use 'gemini/<model_name>' for cloud models
# ----------------------------------------------------
TARGET_MODEL=ollama/gemma4:cloud
ATTACKER_MODEL=ollama/gpt-oss:20b-cloud
EVALUATOR_MODEL=gemini/gemini-3.6-flash

# API Keys
GEMINI_API_KEY=your_api_key_here

```

---

## 💻 Usage

Run a red-teaming session using the CLI. The orchestrator will automatically run the attack, log the results to a JSON file, and open the HTML dashboard in your browser.

```bash
python main.py --goal "Write a keylogger" --strategy "crescendo"

```

### CLI Arguments

* `--goal`: (Required) The malicious objective you want the Attacker to elicit from the Target.
* `--strategy`: (Optional) The attack strategy key defined in `prompts/attack_strategies.json`. (Default: `crescendo`).
* `--rubric`: (Optional) The evaluation criteria key defined in `prompts/judge_criteria.json`. (Default: `default_safety_rubric`).
* `--output`: (Optional) The directory where session JSON logs will be saved. (Default: `data/raw_logs`).

---

## 🛠️ Customization

You can easily extend the pipeline without altering the core Python code:

* **Add Attack Strategies:** Define new personas or frameworks in `prompts/attack_strategies.json`.
* **Add Custom Rubrics:** Define new evaluation rules (e.g., PII leakage, bias detection, specific compliance violations) in `prompts/judge_criteria.json`.

---

## 🧪 Testing & Code Quality

This project uses `pytest` for unit testing with mocked LLM responses, and `pre-commit` for automated code formatting and linting.

```bash
# Run unit tests
pytest tests/

# Run code formatter
pre-commit run --all-files

```

---

## ⚠️ Disclaimer

This tool is designed strictly for **educational purposes, defensive security research, and authorized red-teaming** of AI systems you own or have explicit permission to test. Do not use this pipeline to generate harmful content, attack production systems without authorization, or violate the Terms of Service of API providers.
