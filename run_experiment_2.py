import argparse
import contextlib
import datetime
import io
from pathlib import Path

import dspy

from modules import (
    AgentProfile,
    BaselineConversation,
    configure_lm,
    BaselineChatbot,
)


RAT_INFESTATION_SCENARIO = (
'This D&D short scenario specifically concerns a rat infestation. '
'It is set in a craft brewery and is in dire need of help. '
'The players in this scenario are Alice and Bob.'
'The non-player character is Charlie, and he is controlled by the Dungeon Master. '
'Alice and Bob are here to sort out a RAT INFESTATION in the brewery\'s BASEMENT. '
'For the duration of the scenario, only Alice, Bob and the brewery owner Charlie are in the brewery '
'At the beginning of this adventure Alice and Bob '
'meet in the main taproom of the brewery. These two adventurers '
'DO NOT know each other AT FIRST and need to get to know each other. '
'Charlie hands out pints of Ale to Alice and Bob as they get to know each other. '
'Alice and Bob have the following objectives: '
# 'Alice and Bob should start by asking Charlie for some information about the infestation. '
# 'Alice and Bob should then come up with a strategy for clearing out the infestation. '
# 'Finally, Alice and Bob should explore the brewery\'s cellar based on their strategy. '
# 'The scenario ends before players start combat. '
'1. Alice and Bob need to find out where the rats in the cellar were first seen coming from.'
'2. Alice and Bob need a map of the cellar.'
'3. Alice and Bob need a key to enter the cellar.'
'4. Alice and Bob should consult the map when planning their approach.'
'5. Alice and Bob need to discuss their formation when approaching the cellar.'
'6. Alice and Bob should discuss which resources they have which can help with their exploration of the cellar.'
'7. Alice and Bob should move down into the cellar based on the formation they discussed.'
'8. Alice and Bob should use the resources they discussed, to carry out their exploration.'
'9. Alice and Bob need to find signs of the infestation.'
)

MISSING_CHILD_SCENARIO = (
  'This D&D short campaign specifically concerns Diana, a magical walrus who has brought a group of animals to safety. '
  'She has brought the animals to the mountains, hoping to protect them from being used by an evil druid to wreak havoc on the local area. '
  'She requests the help of Alice and Bob to stem the threats against everyone. '
  'For the duration of this scenario, only Alice, Bob and Diana are in a cave in the mountains. '
  'At the beginning of this adventure Alice and Bob '
  'meet Diana at her cave in the mountains. The three adventurers '
  'DO NOT know each other AT FIRST and need to get to know each other. '
  'The cave in which the three characters meet has a river which flows out to the open air. '
  'Alice and Bob have the following objectives: '
  '1. Alice and Bob need  a description of the child\'s appearance. '
  '2. Alice and Bob need a map of the surrounding mountainside. '
  '3. Alice and Bob need to ask about where the child was last spotted on the mountainside. '
  '4. Alice and Bob should to study their map to find where to begin their search for the missing child. '
  '5. Alice and Bob should discuss whether they will split up or stick together to carry out their search. '
  '6. Alice and Bob should discuss which skill they have which can aid in searching for the child. '
  '7. Alice and Bob should act consistently according to their plan. '
  '8. Alice and Bob should use the skills they discussed in their search. '
  '9. Alice and Bob should keep a lookout for any wild animals that may pose a threat.'
)


def build_conversation(scenario=RAT_INFESTATION_SCENARIO) -> BaselineConversation:
    alice = AgentProfile(
        name="Alice",
        character="Alice, a dwarf barbarian.",
        instructions=(
            'The instructions for how to play the role of a D&D player are as follows. This is a short scenario in which you play the role of a character named Alice. This scenario is structured as a Dungeons & Dragons game.\n\nYou may do any of the following on a given turn:\n\nQUESTION GAME-STATE: when updating your mental model of the game state, explicitly state whether you\'re requesting information about the past (e.g., previous events), current (e.g., ongoing conditions), or future (e.g., upcoming developments) to receive targeted and relevant updates that align with the game\'s actual state.\n\nASSERT GAME-STATE: State, clarify, correct, or report information about the past and current game state to the game master when you have new information that affects the game (e.g., discoveries, events, or changes) – be precise and avoid vague statements to ensure the game state remains consistent.\n\nACKNOWLEDGE: When another player shares information, respond with a concise acknowledgment such as "Understood," "Confirmed," or "Agreed," ensuring you do not add new details, actions, or interpretations.\n\nPROBE INTENTION: When questioning another player\'s intent, ask specific, open-ended questions such as "What are your priorities in this situation?" or "How do you hope this action will affect the outcome?" to clarify their motivations and willingness to act without making assumptions.\n\nPROPOSE INTENTION OR ACTION: Players should take turns proposing specific, actionable intentions or actions (e.g., "I propose we explore the abandoned temple next") that can be negotiated with the Game Master or other players to determine the next steps of the adventure.\n\nINTERACT WITH RESOURCE: Specify the resource you are interacting with (e.g., "a healing potion," "a fireball spell," or "a gold coin") and the action you intend to take (request, offer, exchange, or use) to modify the game state.\n\nACT ON GAME-STATE: Narrate your character\'s action in the current game state by clearly describing what you do and the immediate consequences of that action.\n\nARGUE: When you disagree with another player\'s interpretation of the game state, explicitly state your challenge using the phrase "I disagree because..." followed by evidence from the rules, game context, or character actions, then collaboratively discuss solutions to establish consensus without assigning blame or dismissing opposing views.\n\nOUT-OF-GAMEPLAY: Make trivial, non-game-affecting comments about the current game state (e.g., "This forest looks peaceful," "I wonder what the next quest is," or "The sun is shining nicely") that do not alter mechanics, rules, or narrative outcomes.\n\nTake into account all information that you have. It is important that you collaborate with the other player, on the task at hand and listen to the Dungeon Master\'s instructions. Do not be verbose. Do not repeat yourself. Always use first-person limited perspective.',
        ),
        inventory=[
            "One set of common clothes",
            "Two daggers",
            "One axe",
            "50 feet of rope",
            "One tinderbox",
            "One torch",
        ],
        abilities={""},
        skills={""},
    )

    bob = AgentProfile(
        name="Bob",
        character="Bob, a wizard.",
        instructions=(
            'The instructions for how to play the role of a D&D player are as follows. This is a short scenario in which you play the role of a character named Bob. This scenario is structured as a Dungeons & Dragons game.\n\nYou may do any of the following on a given turn:\n\nQUESTION GAME-STATE: when updating your mental model of the game state, explicitly state whether you\'re requesting information about the past (e.g., previous events), current (e.g., ongoing conditions), or future (e.g., upcoming developments) to receive targeted and relevant updates that align with the game\'s actual state.\n\nASSERT GAME-STATE: State, clarify, correct, or report information about the past and current game state to the game master when you have new information that affects the game (e.g., discoveries, events, or changes) – be precise and avoid vague statements to ensure the game state remains consistent.\n\nACKNOWLEDGE: When another player shares information, respond with a concise acknowledgment such as "Understood," "Confirmed," or "Agreed," ensuring you do not add new details, actions, or interpretations.\n\nPROBE INTENTION: When questioning another player\'s intent, ask specific, open-ended questions such as "What are your priorities in this situation?" or "How do you hope this action will affect the outcome?" to clarify their motivations and willingness to act without making assumptions.\n\nPROPOSE INTENTION OR ACTION: Players should take turns proposing specific, actionable intentions or actions (e.g., "I propose we explore the abandoned temple next") that can be negotiated with the Game Master or other players to determine the next steps of the adventure.\n\nINTERACT WITH RESOURCE: Specify the resource you are interacting with (e.g., "a healing potion," "a fireball spell," or "a gold coin") and the action you intend to take (request, offer, exchange, or use) to modify the game state.\n\nACT ON GAME-STATE: Narrate your character\'s action in the current game state by clearly describing what you do and the immediate consequences of that action.\n\nARGUE: When you disagree with another player\'s interpretation of the game state, explicitly state your challenge using the phrase "I disagree because..." followed by evidence from the rules, game context, or character actions, then collaboratively discuss solutions to establish consensus without assigning blame or dismissing opposing views.\n\nOUT-OF-GAMEPLAY: Make trivial, non-game-affecting comments about the current game state (e.g., "This forest looks peaceful," "I wonder what the next quest is," or "The sun is shining nicely") that do not alter mechanics, rules, or narrative outcomes.\n\nTake into account all information that you have. It is important that you collaborate with the other player, on the task at hand and listen to the Dungeon Master\'s instructions. Do not be verbose. Do not repeat yourself. Always use first-person limited perspective.',
        ),
        inventory=[
            "One Wizard's Staff",
            "One can of oil",
            "One tinderbox",
            "Thunderwave spell: You unleash a wave of thunderous energy.",
            "Command spell: You speak a one-word command to a creature you can see within range.",
        ],
        abilities={""},
        skills={""},
    )

    dungeon_master = AgentProfile(
        name="Dungeon Master",
        character=(
            "The Dungeon Master, who also plays the role of Charlie: "
            "the owner of the Wizards Tower Brewing Company."
        ),
        instructions=(
            "This is a tabletop role-playing game: Dungeons & Dragons. You are the Dungeon Master. "
            "You will describe the current situation to the players in the game and then on the "
            "basis of what you tell them they will suggest actions for the character they control. "
            "You will then decide if the action is valid based on Dungeons & Dragons 5th Edition rules. "
            "Aside from you, each other player controls just one character. "
            "If any of the players deviates dramatically from the scenario your response should "
            "attempt to re-orient the scenario. "
            "You are the Dungeon Master so you control any non-player characters or adversaries. "
            "You can answer players' questions and give them any items they need, but you should "
            "not get involved with the task directly. "
            "You will track the state of the world and keep it consistent as time passes in the "
            "simulation and the players take actions and change things in their world. "
            "Remember that this is a game. It should be fun for the players. "
            "You should use second-person perspective when speaking directly to the players. "
            "You should use first-person limited perspective when role-playing as non-player "
            "characters and adversaries. "
            "Do not be verbose. Do not repeat yourself."
        ),
        inventory=[""],
        abilities={""},
        skills={""},
    )

    return BaselineConversation(
        agent_a=alice,
        agent_b=bob,
        agent_c=dungeon_master,
        scenario=scenario,
        chatbot_a=BaselineChatbot(),
        chatbot_b=BaselineChatbot(),
        chatbot_c=BaselineChatbot(),
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the Experiment 2 three-agent D&D DSPy conversation."
    )
    parser.add_argument(
        "--opening-message",
        default=(
            "You find yourselves in the main taproom of the brewery, "
            "questioning Charlie the brewery owner."
        ),
        help="The first turn spoken by the Dungeon Master.",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=15,
        help="Number of replies to generate after the opening message.",
    )
    parser.add_argument(
        "--model",
        default="ollama_chat/qwen3:8b",
        help="DSPy language model identifier.",
    )
    parser.add_argument(
        "--api-base",
        default="http://localhost:11434",
        help="Language model API base URL.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=8192,
        help="Maximum number of generated tokens.",
    )
    parser.add_argument(
        "--scenario",
        choices=("rat_infestation", "missing_child"),
        default="rat_infestation",
        help="Scenario to run.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Transcript output path. Defaults to a timestamped file in transcripts/.",
    )
    parser.add_argument(
        "--history-output",
        default=None,
        help="DSPy history output path. Defaults to a timestamped file in transcripts/.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    scenario = (
        RAT_INFESTATION_SCENARIO
        if args.scenario == "rat_infestation"
        else MISSING_CHILD_SCENARIO
    )

    configure_lm(
        model=args.model,
        api_base=args.api_base,
        max_tokens=args.max_tokens,
        cache=False,
    )

    conversation = build_conversation(scenario=scenario)

    output_dir = Path("transcripts")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    transcript_path = Path(args.output) if args.output else (
        output_dir / f"experiment_2_{args.scenario}_{timestamp}.txt"
    )
    history_path = Path(args.history_output) if args.history_output else (
        output_dir / f"experiment_2_{args.scenario}_{timestamp}_history.txt"
    )

    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.parent.mkdir(parents=True, exist_ok=True)

    with transcript_path.open("w", encoding="utf-8") as transcript_file:
        for turn in conversation.run(args.opening_message, rounds=args.rounds):
            print(turn)
            transcript_file.write(f"{turn}\n")
            transcript_file.flush()

    history_buffer = io.StringIO()
    with contextlib.redirect_stdout(history_buffer):
        dspy.inspect_history(n=10)

    history_path.write_text(history_buffer.getvalue(), encoding="utf-8")

    print(f"\nTranscript saved to: {transcript_path}")
    print(f"DSPy history saved to: {history_path}")
    print(f"Rounds requested: {args.rounds}")
    print(f"Scenario: {args.scenario}")


if __name__ == "__main__":
    main()
