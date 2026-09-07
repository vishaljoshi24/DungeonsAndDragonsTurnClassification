from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import dspy
import pandas as pd

from signatures import Assess, ChatbotSignature, TurnClassifier


DEFAULT_MODEL = "ollama_chat/qwen3:8b"
DEFAULT_API_BASE = "http://localhost:11434"
DEFAULT_CLASSIFIER_PATH = Path(__file__).with_name("optimized_classifier.json")
DEFAULT_INSTRUCTIONS_PATH = Path(__file__).with_name("instructions.xlsx")


def configure_lm(
    model: str = DEFAULT_MODEL,
    api_base: str = DEFAULT_API_BASE,
    api_key: str = "",
    max_tokens: int = 4096,
) -> dspy.LM:
    """Configure DSPy for the local Ollama-backed model used in the notebooks."""

    lm = dspy.LM(model, api_base=api_base, api_key=api_key, max_tokens=max_tokens)
    dspy.configure(lm=lm)
    return lm


def _as_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value)


def _prediction_label(prediction: Any) -> str:
    if isinstance(prediction, str):
        return prediction
    if hasattr(prediction, "response"):
        return str(prediction.response)
    if isinstance(prediction, dict) and "response" in prediction:
        return str(prediction["response"])
    return str(prediction)


class ClassifyTurns(dspy.Module):
    def __init__(self, optimized_path: str | Path | None = DEFAULT_CLASSIFIER_PATH):
        super().__init__()
        self.classifier = dspy.ChainOfThought(TurnClassifier, caching=False)
        if optimized_path and Path(optimized_path).exists():
            self.load(str(optimized_path))

    def forward(self, context: str, question: str, **kwargs: Any):
        return self.classifier(context=context, question=question)


class PromptTool:
    """Retrieve behaviour instructions using the optimized turn classifier."""

    def __init__(
        self,
        prompts_path: str | Path = DEFAULT_INSTRUCTIONS_PATH,
        classifier: ClassifyTurns | None = None,
    ):
        self.prompts = self._load_prompts(prompts_path)
        self.classify = ClassifyTurns()

    @staticmethod
    def _load_prompts(prompts_path: str | Path) -> dict[str, str]:
        df = pd.read_excel(prompts_path)
        df = df.drop(columns=[column for column in df.columns if str(column).startswith("Unnamed")])
        df = df.drop_duplicates(subset=[df.columns[0]], inplace=False)

        prompts: list[str] = []
        for classes, instructions in df.values:
            examples = dspy.Example(classes=classes, instructions=instructions).with_inputs("classes", "instructions")
            prompts.append(examples)
        return prompts

    def classify_input(
        self,
        context: str,
        query: str,
        user_id: str = "default_user",
    ) -> str:
        """Classify a player's input into a D&D behaviour category."""

        prompt_class = self.classify(context=context, question=query)
        return prompt_class

    def search_prompts(
        self,
        prompt_class: str,
        context: str,
        query: str,
        user_id: str = "default_user",
        limit: int = 4,
    ) -> str:
        """Find the instruction text for a classified player behaviour."""
        prompt_text = "Update instructions with the following prompt:\n"
        for i in range(len(self.prompts)):
            if prompt_class == self.prompts[i]['classes']:
                prompt_text += self.prompts[i]['instructions']
                return prompt_text
            if not prompt_class:
                return "No relevant prompt found."

    def update_prompt(
        self,
        context: str,
        query: str,
        instruct_prompt: str,
        prompt_text: str,
        new_prompt: str = "",
    ) -> str:
        """Append retrieved instructions to the current agent prompt."""

        updated_prompt = instruct_prompt + new_prompt
        return f"Updated prompt with new instructions: {updated_prompt}"

class BaselineChatbot(dspy.Module):
    """A CoT D&D player agent with basline behaviour instructions."""

    def __init__(self):
        super().__init__()
        self.baseline_agent = dspy.ChainOfThought(signature=ChatbotSignature)

    def forward(self, instruct_prompt: str, scenario_context: str, user_input: str):
        """Process another agent's input with prompt aware reasoning"""
        return self.baseline_agent(
            instruct_prompt=_as_text(instruct_prompt),
            scenario_context=_as_text(scenario_context),
            user_input=user_input,
        )

class InstructedChatbot(dspy.Module):
    """A ReAct D&D player agent which uses tools to update its prompt instructions."""

    def __init__(self, prompt_tool: PromptTool | None = None, max_iters: int = 6):
        super().__init__()
        self.prompt_tools = PromptTool()
        self.react = dspy.ReAct(
            signature=ChatbotSignature,
            tools=[self.prompt_tools.classify_input,
                  self.prompt_tools.search_prompts,
                  self.prompt_tools.update_prompt],
            max_iters=max_iters,
        )

    def forward(self, instruct_prompt: str, scenario_context: str, user_input: str):
        """Process another agent's input with prompt aware reasoning"""
        return self.react(
            instruct_prompt=_as_text(instruct_prompt),
            scenario_context=_as_text(scenario_context),
            user_input=user_input,
        )


@dataclass
class AgentProfile:
    name: str
    character: str
    instructions: str
    inventory: list[str]
    abilities: dict[str|str]
    skills: dict[str|str]


@dataclass
class TwoAgentConversation:
    """Run two Instructed agents against each other."""

    agent_a: AgentProfile
    agent_b: AgentProfile
    scenario: str
    chatbot_a: InstructedChatbot = field(default_factory=InstructedChatbot)
    chatbot_b: InstructedChatbot = field(default_factory=InstructedChatbot)
    history: list[str] = field(default_factory=list)

    def run(self, opening_message: str, rounds: int = 4) -> list[str]:
        self.history.append(f"{self.agent_a.name}: {opening_message}")
        next_message = opening_message

        for turn_index in range(rounds):
            speaker, chatbot = (
                (self.agent_b, self.chatbot_b)
                if turn_index % 2 == 0
                else (self.agent_a, self.chatbot_a)
            )

            prediction = chatbot(
                instruct_prompt=self._agent_prompt(speaker),
                scenario_context=self._context(),
                user_input=next_message,
            )
            next_message = _prediction_label(prediction)
            self.history.append(f"{speaker.name}: {next_message}")

        return self.history

    def _context(self) -> str:
        recent_history = "\n".join(self.history[-3:])
        return f"{self.scenario}\n\nRecent turns:\n{recent_history}"

    def _agent_prompt(self, profile: AgentProfile) -> str:
        return (
            "You are playing a Dungeons & Dragons scene.\n"
            f"Character: {profile.character}\n"
            f"{profile.instructions}\n"
            "Stay in character and reply with only the next spoken turn."
        )

@dataclass
class BaselineConversation:
    """Run two Instructed agents against each other."""

    agent_a: AgentProfile
    agent_b: AgentProfile
    agent_c: AgentProfile
    scenario: str
    chatbot_a: BaselineChatbot = field(default_factory=BaselineChatbot)
    chatbot_b: BaselineChatbot = field(default_factory=BaselineChatbot)
    chatbot_c: BaselineChatbot = field(default_factory=BaselineChatbot)
    history: list[str] = field(default_factory=list)

    def run(self, opening_message: str, rounds: int = 4) -> list[str]:
        self.history.append(f"{self.agent_c.name}: {opening_message}")
        next_message = opening_message

        for turn_index in range(rounds):
            if turn_index % 3 == 0:
                speaker, chatbot = (self.agent_a, self.chatbot_a)
            elif turn_index % 3 == 1: 
                speaker, chatbot = (self.agent_b, self.chatbot_b)
            else:     
                speaker, chatbot = (self.agent_c, self.chatbot_c)

            prediction = chatbot(
                instruct_prompt=self._agent_prompt(speaker),
                scenario_context=self._context(),
                user_input=next_message,
            )
            next_message = _prediction_label(prediction)
            self.history.append(f"{speaker.name}: {next_message}")

        return self.history

    def _context(self) -> str:
        recent_history = "\n".join(self.history[-3:])
        return f"{self.scenario}\n\nRecent turns:\n{recent_history}"

    def _agent_prompt(self, profile: AgentProfile) -> str:
        return (
            "You are playing a Dungeons & Dragons scene.\n"
            f"Character: {profile.character}\n"
            f"Instructions: {profile.instructions}\n"
            f"Inventory: {profile.inventory}\n"
            "Stay in character and reply with only the next spoken turn."
        )


@dataclass
class MultiAgentConversation:
    """Run two Instructed agents against each other."""

    agent_a: AgentProfile
    agent_b: AgentProfile
    agent_c: AgentProfile
    scenario: str
    chatbot_a: InstructedChatbot = field(default_factory=InstructedChatbot)
    chatbot_b: InstructedChatbot = field(default_factory=InstructedChatbot)
    chatbot_c: InstructedChatbot = field(default_factory=InstructedChatbot)
    history: list[str] = field(default_factory=list)

    def run(self, opening_message: str, rounds: int = 4) -> list[str]:
        self.history.append(f"{self.agent_c.name}: {opening_message}")
        next_message = opening_message

        for turn_index in range(rounds):
            if turn_index % 3 == 0:
                speaker, chatbot = (self.agent_a, self.chatbot_a)
            elif turn_index % 3 == 1: 
                speaker, chatbot = (self.agent_b, self.chatbot_b)
            else:     
                speaker, chatbot = (self.agent_c, self.chatbot_c)

            prediction = chatbot(
                instruct_prompt=self._agent_prompt(speaker),
                scenario_context=self._context(),
                user_input=next_message,
            )
            next_message = _prediction_label(prediction)
            self.history.append(f"{speaker.name}: {next_message}")

        return self.history

    def _context(self) -> str:
        recent_history = "\n".join(self.history[-3:])
        return f"{self.scenario}\n\nRecent turns:\n{recent_history}"

    def _agent_prompt(self, profile: AgentProfile) -> str:
        return (
            "You are playing a Dungeons & Dragons scene.\n"
            f"Character: {profile.character}\n"
            f"Instructions: {profile.instructions}\n"
            f"Inventory: {profile.inventory}\n"
            "Stay in character and reply with only the next spoken turn."
        )


