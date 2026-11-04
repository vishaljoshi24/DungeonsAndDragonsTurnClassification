from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import dspy
import pandas as pd

from signatures import Assess, CATEGORIES, ChatbotSignature, TurnClassifier


DEFAULT_MODEL = "ollama_chat/qwen3:8b"
DEFAULT_API_BASE = "http://localhost:11434"
DEFAULT_CLASSIFIER_PATH = Path(__file__).parent / "optimized_classifiers" / "bfs_qwen3_4b_default_run_0.json"
DEFAULT_INSTRUCTIONS_PATH = Path(__file__).with_name("prompt_instructions.xlsx")


def configure_lm(
    model: str = DEFAULT_MODEL,
    api_base: str = DEFAULT_API_BASE,
    api_key: str = "",
    max_tokens: int = 8192,
    cache: bool = False,
) -> dspy.LM:
    """Configure DSPy for the local Ollama-backed model used in the notebooks."""

    lm = dspy.LM(model, api_base=api_base, api_key=api_key, max_tokens=max_tokens, cache=cache)
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
        self.classifier = dspy.Predict(TurnClassifier, caching=False)
        if optimized_path and Path(optimized_path).exists():
            self.load(str(optimized_path))

    def forward(self, context: str, question: str, **kwargs: Any):
        return self.classifier(context=context, question=question)


class PromptTool:
    """Classify turns and retrieve matching behaviour instructions."""

    def __init__(self, prompts_path=DEFAULT_INSTRUCTIONS_PATH, classifier=None):
        self.prompts = self._load_prompts(prompts_path)
        self.classify = classifier if classifier is not None else ClassifyTurns()

    @staticmethod
    def _load_prompts(prompts_path) -> dict[str, str]:
        df = pd.read_excel(prompts_path)
        df = df.drop(columns=[
            column for column in df.columns
            if str(column).startswith("Unnamed")
        ])
        if not {"classes", "instructions"}.issubset(df.columns):
            raise ValueError(
                f"Expected 'classes' and 'instructions' columns; found {list(df.columns)}"
            )

        prompts = {}
        for _, row in df.iterrows():
            label, instructions = row["classes"], row["instructions"]
            if pd.isna(label) or pd.isna(instructions):
                continue
            label = str(label).strip()
            instructions = str(instructions).strip()
            if label:
                prompts.setdefault(label, instructions)
        return prompts

    def classify_input(self, context, query, user_id="default_user") -> str:
        prediction = self.classify(context=context, question=query)
        label = str(getattr(prediction, "response", "")).strip()
        if label not in CATEGORIES.__args__:
            raise ValueError(
                f"Invalid classifier category {label!r}; expected one of "
                f"{CATEGORIES.__args__}"
            )
        return label

    def search_prompts(
        self, prompt_class, context, query, user_id="default_user", limit=4
    ) -> str:
        label = str(prompt_class).strip()
        if label not in CATEGORIES.__args__:
            raise ValueError(f"Invalid category for prompt lookup: {label!r}")
        if label not in self.prompts:
            raise KeyError(f"No spreadsheet instructions for category {label!r}")
        return self.prompts[label]

    def update_prompt(
        self, context, query, instruct_prompt, prompt_text, new_prompt=""
    ) -> str:
        additions = [
            value.strip() for value in (prompt_text, new_prompt)
            if value and value.strip()
        ]
        if not additions:
            raise ValueError("No behaviour instructions supplied.")
        return (
            f"{instruct_prompt.rstrip()}\n\n"
            "Behaviour instructions for this turn:\n"
            + "\n\n".join(additions)
        )

class BaselineChatbot(dspy.Module):
    """A D&D player agent with behaviour instructions."""

    def __init__(self):
        super().__init__()
        self.baseline_agent = dspy.Predict(signature=ChatbotSignature)

    def forward(self, instruct_prompt: str, scenario_context: str, user_input: str):
        """Process another agent's input with prompt aware reasoning"""
        return self.baseline_agent(
            instruct_prompt=_as_text(instruct_prompt),
            scenario_context=_as_text(scenario_context),
            user_input=user_input,
        )

class InstructedChatbot(dspy.Module):
    """D&D player agent with deterministic tool orchestration."""

    def __init__(self, prompt_tool=None, max_iters=6):
        super().__init__()
        # Keep max_iters for compatibility with existing call sites.
        self.prompt_tools = prompt_tool if prompt_tool is not None else PromptTool()
        self.response_generator = dspy.Predict(signature=ChatbotSignature)

    def forward(self, instruct_prompt, scenario_context, user_input):
        context = _as_text(scenario_context)
        query = _as_text(user_input)

        # These steps always run in this order; ReAct cannot skip them.
        category = self.prompt_tools.classify_input(context=context, query=query)
        category = str(category).strip()
        allowed_categories = CATEGORIES.__args__
        if category not in allowed_categories:
            raise ValueError(
                f"Invalid classifier category {category!r}; expected one of "
                f"{allowed_categories}"
            )

        instructions = self.prompt_tools.search_prompts(
            prompt_class=category, context=context, query=query
        )
        updated_prompt = self.prompt_tools.update_prompt(
            context=context,
            query=query,
            instruct_prompt=_as_text(instruct_prompt),
            prompt_text=instructions,
        )
        return self.response_generator(
            instruct_prompt=updated_prompt,
            scenario_context=context,
            user_input=query,
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


