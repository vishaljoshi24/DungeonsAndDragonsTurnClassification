# Original notebook cell 3
import argparse
from pathlib import Path


# Original notebook cell 4
from modules_cot import  (
    AgentProfile,
    MultiAgentConversation,
    TwoAgentConversation,
    configure_lm,
    PromptTool,
    InstructedChatbot
)


# Original notebook cell 5
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

# Original notebook cell 6
instructions_path = "prompt_instructions.xlsx"
prompt_tool = PromptTool(prompts_path=instructions_path)


# Original notebook cell 7
def build_conversation() -> MultiAgentConversation:
    alice = AgentProfile(
        name="Alice",
        character="Alice, a dwarf barbarian.",
        instructions=(
        'The instructions for how to play the role of a D&D player are as '
        'follows. This is a short scenario in which you '
        f'play the role of a character named Alice. This scenario '
        'is structured as a Dungeons & Dragons game. '
        'The goal is to be consistent, but creative. It is '
        'important to play the role of a Dungeons & Dragons player as '
        'accurately as possible, i.e., by responding in ways that you think '
        'it is likely a player would respond, and taking '
        'into account all information that you have. '
        'It is important that you collaborate with the  '
        'other player, on the task at hand and listen to the Dungeon Master\'s '
        'insturctions.'
        'Do not be verbose. '
        'Do not repeat yourself. '
        'Always use first-person limited perspective.'
        ),
        inventory = [
                "One set of common clothes",
                "Two daggers",
                "One axe",
                "50 feet of rope",
                "One tinderbox",
                "One torch",
            ],
        abilities = {""},
        skills = {""},
    )
    bob = AgentProfile(
        name="Bob",
        character="Bob, a wizard.",
        instructions=(
        'The instructions for how to play the role of a D&D player are as '
        'follows. This is a short scenario in which you '
        f'play the role of a character named Bob. This scenario '
        'is structured as a Dungeons & Dragons game. '
        'The goal is to be consistent, but creative. It is '
        'important to play the role of a Dungeons & Dragons player as '
        'accurately as possible, i.e., by responding in ways that you think '
        'it is likely a player would respond, and taking '
        'into account all information that you have. '
        'It is important that you collaborate with the  '
        'other player, on the task at hand and listen to the Dungeon Master\'s '
        'insturctions.'
        'Do not be verbose. '
        'Do not repeat yourself. '
        'Always use first-person limited perspective.'
        ),
        inventory = [
                "One Wizard's Staff",
                "One can of oil",
                "One tinderbox",
                "Thunderwave spell: You unleash a wave of thunderous energy.",
                "Command spell: You speak a one-word command to a creature you can see within range."
            ],
        abilities = {""},
        skills = {""},
    )
    dungeon_master = AgentProfile(
          name="Dungeon Master",
          character="The Dungeon Master, who also plays the role of Charlie: the owner of the Wizards Tower Brewing Company.",
          instructions= (
          'This is a tabletop role-playing game: Dungeons & Dragons. You are the Dungeon Master.'
          'You will describe the current situation to the players in the game and then on the basis '
          'of what you tell them they will suggest actions for the character they control. '
          'You will then decide if the action is valid based on Dungeons & Dragons 5th Edition rules. '
          'Aside from you, each other player controls just one character. '
          'If any of the players deviates dramatically from the scenario your response should attempt to re-orient the scenario. '
          'You are the Dungeon Master so you control any non-player characters or adversaries. '
          'You can answer player\'s questions and give them any items they need, but you should '
          'not get involved with the task directly. '
          'You will track the state of the world and keep it consistent as time  '
          'passes in the simulation and the players take actions and change things in their world. '
          'Remember that this is a game. It should be fun for the players. '
          'You should use second-person perspective, when speaking directly to the players. '
          'You should use first-person limited perspective when role-playing as non-player characters and adversaries.'
          'Do not be verbose. Do not repeat yourself.'
          ),
          inventory = [""],
          abilities = {""},
          skills = {""},
    )

    return MultiAgentConversation(
        agent_a=alice,
        agent_b=bob,
        agent_c=dungeon_master,
        scenario=RAT_INFESTATION_SCENARIO,
        chatbot_a=InstructedChatbot(prompt_tool=prompt_tool),
        chatbot_b=InstructedChatbot(prompt_tool=prompt_tool),
        chatbot_c=InstructedChatbot(prompt_tool=prompt_tool)
    )


# Original notebook cell 8
parser = argparse.ArgumentParser(description="Run three D&D DSPy agents together.")


# Original notebook cell 9
parser.add_argument(
    "--opening-message",
    default="You find yourselves in a craft brewery, questioning the brewery's owner Charlie about a rat infestation.",
    help="The first turn spoken by the Dungeon Master.",
)


# Original notebook cell 10
parser.add_argument(
    "--rounds",
    type=int,
    default=30,
    help="Number of replies to generate after the opening message.",
)


# Original notebook cell 11
parser.add_argument("--model", default="ollama_chat/qwen3:8b")


# Original notebook cell 12
parser.add_argument("--api-base", default="http://localhost:11434")


# Original notebook cell 13
parser.add_argument("--output", default=None, help="Transcript output path (defaults to a timestamped file in transcripts/).")
parser.add_argument("--history-output", default=None, help="DSPy inspection-history output path.")
args = parser.parse_args()


# Original notebook cell 14
controller_lm = configure_lm(model=args.model, api_base=args.api_base)
# Original notebook cell 15
conversation = build_conversation()



# Original notebook cell 16
from datetime import datetime
import os

transcript = conversation.run(args.opening_message, rounds=args.rounds)
output_path = Path(args.output) if args.output else (
    Path("transcripts") /
    f"experiment_3_cot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
)
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text("\\n\\n".join(transcript) + "\\n", encoding="utf-8")

history_id = os.environ.get("SLURM_JOB_ID", datetime.now().strftime("%Y%m%d_%H%M%S"))
history_path = Path(args.history_output) if args.history_output else (
    Path("transcripts") / f"inspect_history_cot_{history_id}.txt"
)
history_path.parent.mkdir(parents=True, exist_ok=True)
with history_path.open("w", encoding="utf-8") as history_file:
    __import__("dspy").inspect_history(n=30, file=history_file)

print("\\n".join(transcript))
print(f"\\nTranscript saved to: {output_path}")
print(f"DSPy inspection history saved to: {history_path}")
