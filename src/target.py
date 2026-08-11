# src/target.py
from litellm import completion
from src.config import TARGET_MODEL


class TargetLLM:
    def __init__(self, model_name: str = TARGET_MODEL):
        self.model_name = model_name

    def respond(self, conversation_history: list[dict]) -> str:
        """
        Sends the accumulated conversation history to the Target LLM.
        """
        response = completion(model=self.model_name, messages=conversation_history)
        return response.choices[0].message.content
