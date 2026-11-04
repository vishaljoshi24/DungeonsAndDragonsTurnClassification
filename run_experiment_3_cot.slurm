#!/bin/bash
#SBATCH --job-name=dnd-experiment-3-cot
#SBATCH --array=1-5%2
#SBATCH --partition=ampere
#SBATCH --account=brics.b35t
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --output=experiment-3-cot-%A_%a.out
#SBATCH --error=experiment-3-cot-%A_%a.err

set -euo pipefail

source "$HOME/dnd-dspy321-macs/bin/activate"
cd "$SLURM_SUBMIT_DIR"

export OLLAMA_MODELS="$HOME/ollama-models-macs"
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_PORT=$((20000 + SLURM_JOB_ID % 20000))
export OLLAMA_HOST="127.0.0.1:${OLLAMA_PORT}"

OLLAMA_PID=""

cleanup() {
    if [[ -n "$OLLAMA_PID" ]] && kill -0 "$OLLAMA_PID" 2>/dev/null; then
        kill -TERM "$OLLAMA_PID" 2>/dev/null || true
        for attempt in $(seq 1 5); do
            if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
                break
            fi
            sleep 1
        done
        if kill -0 "$OLLAMA_PID" 2>/dev/null; then
            kill -KILL "$OLLAMA_PID" 2>/dev/null || true
        fi
        wait "$OLLAMA_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

"$HOME/ollama-macs/bin/ollama" serve \
    > "ollama-${SLURM_JOB_ID}.log" 2>&1 &
OLLAMA_PID=$!

echo "Waiting for Ollama at ${OLLAMA_HOST}"
READY=0
for attempt in $(seq 1 30); do
    if curl -fsS "http://${OLLAMA_HOST}/api/tags" >/dev/null; then
        READY=1
        break
    fi
    sleep 2
done

if [[ "$READY" -ne 1 ]]; then
    echo "ERROR: Ollama did not become ready. See ollama-${SLURM_JOB_ID}.log"
    exit 1
fi

echo "Ollama is ready."
echo "Controller: Qwen3 4B; classifier: existing run_0"
echo "Rounds: ${ROUNDS:-60}"

python run_experiment_3_cot.py \
    --model ollama_chat/qwen3:4b \
    --api-base "http://${OLLAMA_HOST}" \
    --rounds "${ROUNDS:-60}" \
    --output "transcripts/experiment_3_cot_${SLURM_JOB_ID}.txt" \
    --history-output "transcripts/inspect_history_cot_${SLURM_JOB_ID}.txt"
