#!/bin/bash
#SBATCH --job-name=dnd-bootstrap
#SBATCH --partition=ampere
#SBATCH --account=brics.b35t
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --output=dnd-bootstrap-%j.out
#SBATCH --error=dnd-bootstrap-%j.err

set -u

echo "=========================================="
echo "D&D DSPy BootstrapFewShot optimisation"
echo "Job ID:     $SLURM_JOB_ID"
echo "Node:       $(hostname)"
echo "Start time: $(date)"
echo "=========================================="

source ~/dnd-dspy321-macs/bin/activate
cd "$SLURM_SUBMIT_DIR"

export OLLAMA_MODELS=~/ollama-models-macs
~/ollama-macs/bin/ollama serve > "ollama-${SLURM_JOB_ID}.log" 2>&1 &
OLLAMA_PID=$!
cleanup() { kill "${OLLAMA_PID}" 2>/dev/null || true; }
trap cleanup EXIT

for i in $(seq 1 30); do
    if curl -sf http://localhost:11434/api/tags > /tmp/ollama-tags-${SLURM_JOB_ID}.json; then
        echo "Ollama is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: Ollama did not become ready."
        cat "ollama-${SLURM_JOB_ID}.log" || true
        exit 1
    fi
    sleep 2
done

python - <<'PY'
import json, math, os, time
from collections import Counter
import pandas as pd
import dspy
import litellm
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, classification_report, confusion_matrix

optimisation_df = pd.read_excel("optimisation_set_articulation_corrected.xlsx")
validation_df = pd.read_excel("validation_set_articulation_corrected.xlsx")
test_df = pd.read_excel("test_set_articulation_corrected.xlsx")

CATEGORIES = [
    "assert game-state", "question game-state", "act on game-state",
    "propose intention or action", "probe intention", "acknowledge",
    "argue", "interact with resource", "out-of-gameplay",
]

def make_set(df):
    return [dspy.Example(context=row["context"], question=row["current turn"], response=row["Agreed Codes"]).with_inputs("context", "question") for _, row in df.iterrows()]

optimisation_set = make_set(optimisation_df)
validation_set = make_set(validation_df)
test_set = make_set(test_df)

class TurnClassifier(dspy.Signature):
    """Given the context for a Dungeons & Dragons game turn and the game turn itself, classify the turn."""
    context: str = dspy.InputField(desc="The three previous game turns which describe a player's action or their dialogue.")
    question: str = dspy.InputField(desc="The current turn taken by a player, which can include a description of an action or a piece of dialogue.")
    response: CATEGORIES = dspy.OutputField()

class PlayerInstruction(dspy.Signature):
    category: CATEGORIES = dspy.InputField()
    player_instruction: str = dspy.OutputField(desc="instruction on how to behave within a D&D game.")

class ClassifyTurns(dspy.Module):
    def __init__(self):
        self.classifier = dspy.Predict(TurnClassifier, caching=False)
    def forward(self, context, question, **kwargs):
        return self.classifier(context=context, question=question)

classify = ClassifyTurns()

lm = dspy.LM("ollama_chat/qwen3:4b", api_base="http://localhost:11434", api_key="", max_tokens=8192, think=False)
dspy.configure(lm=lm)
litellm.drop_params = True

class_counts = Counter(example.response for example in optimisation_set)
class_weights = {label: 1.0 / math.sqrt(count) for label, count in class_counts.items()}
mean_weight = sum(class_weights.values()) / len(class_weights)
class_weights = {label: weight / mean_weight for label, weight in class_weights.items()}

def class_balanced_reward(example, prediction, trace=None):
    return class_weights[example.response] if prediction.response == example.response else 0.0

optimizer_fewshot = dspy.BootstrapFewShot(
    metric=class_balanced_reward,
    metric_threshold=0.66,
    teacher_settings=None,
    max_bootstrapped_demos=4,
    max_labeled_demos=16,
)

print("Starting BootstrapFewShot optimisation", flush=True)
optimisation_start = time.time()
fewshot_classifier = optimizer_fewshot.compile(classify, trainset=optimisation_set)
optimisation_seconds = time.time() - optimisation_start

classifier_path = "fewshot_classifier_corrected_9class.json"
fewshot_classifier.save(classifier_path)

print("Starting test evaluation", flush=True)
evaluation_start = time.time()
predicted_categories = []
for i, example in enumerate(test_set, start=1):
    try:
        prediction = fewshot_classifier(context=example["context"], question=example["question"])
        predicted_categories.append(prediction.response)
    except Exception as e:
        print(f"ERROR on test example {i}: {type(e).__name__}: {e}", flush=True)
        predicted_categories.append("__ERROR__")
    if i % 10 == 0 or i == len(test_set):
        print(f"Evaluated {i}/{len(test_set)} test examples", flush=True)
evaluation_seconds = time.time() - evaluation_start

true_categories = [example["response"] for example in test_set]
metrics = {
    "accuracy": accuracy_score(true_categories, predicted_categories),
    "macro_f1": f1_score(true_categories, predicted_categories, average="macro", zero_division=0),
    "weighted_f1": f1_score(true_categories, predicted_categories, average="weighted", zero_division=0),
    "macro_precision": precision_score(true_categories, predicted_categories, average="macro", zero_division=0),
    "macro_recall": recall_score(true_categories, predicted_categories, average="macro", zero_division=0),
}

print("\nTEST METRICS")
for name, value in metrics.items(): print(f"{name}: {value:.6f}")

report = classification_report(true_categories, predicted_categories, labels=CATEGORIES, zero_division=0)
cm = confusion_matrix(true_categories, predicted_categories, labels=CATEGORIES)

results = {
    "job_id": os.environ.get("SLURM_JOB_ID"), "node": os.environ.get("SLURMD_NODENAME"),
    "optimisation_examples": len(optimisation_set), "validation_examples": len(validation_set), "test_examples": len(test_set),
    "categories": CATEGORIES, "optimizer": "BootstrapFewShot", "metric_threshold": 0.66,
    "max_bootstrapped_demos": 4, "max_labeled_demos": 16, "lm": "ollama_chat/qwen3:4b",
    "max_tokens": 8192, "think": False, "optimisation_seconds": optimisation_seconds,
    "evaluation_seconds": evaluation_seconds, "metrics": metrics,
    "classification_report": report, "confusion_matrix": cm.tolist(),
}
with open("fewshot_evaluation_results.json", "w") as f: json.dump(results, f, indent=2)

predictions_df = test_df.copy()
predictions_df["Predicted"] = predicted_categories
predictions_df["Correct"] = predictions_df["Agreed Codes"] == predictions_df["Predicted"]
predictions_df.to_excel("fewshot_test_predictions.xlsx", index=False)
predictions_df.to_csv("fewshot_test_predictions.csv", index=False)

print("\nFINAL SUMMARY")
for name, value in metrics.items(): print(f"{name}: {value:.6f}")
print(f"Optimisation time: {optimisation_seconds / 60:.2f} minutes")
print(f"Evaluation time: {evaluation_seconds / 60:.2f} minutes")
print(f"Total time: {(optimisation_seconds + evaluation_seconds) / 60:.2f} minutes")
PY

echo "Batch job finished: $(date)"
