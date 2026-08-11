from setuptools import setup, find_packages

setup(
    name="llm-redteam-pipeline",
    version="1.0.0",
    description="Automated Multi-Turn LLM Jailbreak and Evaluation Pipeline",
    author="Red Team Engineering",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "litellm",
        "pydantic",
        "jinja2",
        "pandas",
        "python-dotenv",
        "rich",
        "google-generativeai",
    ],
)
