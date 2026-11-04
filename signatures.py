import dspy
from typing import Literal

CATEGORIES = Literal[
    "question game-state",
    "assert game-state",
    "acknowledge",
    "probe intention",
    "propose intention or action",
    "interact with resource",
    "act on game-state",
    "argue",
    "out-of-gameplay",
]

TurnCategory = CATEGORIES


class TurnClassifier(dspy.Signature):
    """Given the context for a Dungeons & Dragons game turn and the game turn itself, classify the turn."""

    context: str = dspy.InputField(desc="The three previous game turns which describe a player's action or their dialogue.")
    question: str = dspy.InputField(desc="The current turn taken by a player, which can include a description of an action or a piece of dialogue.")
    response: CATEGORIES = dspy.OutputField()
class PlayerInstruction(dspy.Signature):
    """Generate an instruction for a D&D player agent from a turn category."""

    category: TurnCategory = dspy.InputField()
    player_instruction: str = dspy.OutputField(desc="Instruction on how to behave within a D&D game.")


class ChatbotSignature(dspy.Signature):
    """Respond as a D&D player character using the supplied scenario and behaviour instructions."""

    instruct_prompt: str = dspy.InputField()
    scenario_context: str = dspy.InputField()
    user_input: str = dspy.InputField()
    response: str = dspy.OutputField()


class Assess(dspy.Signature):
    """Assess the quality of a prompt along a specified dimension."""

    assessed_text: list[str] = dspy.InputField()
    assessment_question: str = dspy.InputField()
    assessment_answer: bool = dspy.OutputField()
