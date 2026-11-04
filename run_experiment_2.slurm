#!/bin/bash
#SBATCH --job-name=dnd-experiment-2
#SBATCH --array=1-5%2
#SBATCH --partition=ampere
#SBATCH --account=brics.b35t
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --output=experiment-2-%A_%a.out
#SBATCH --error=experiment-2-%A_%a.err

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
        for _ in {1..5}; do
            kill -0 "$OLLAMA_PID" 2>/dev/null || break
            sleep 1
        done
        if kill -0 "$OLLAMA_PID" 2>/dev/null; then
            kill -KILL "$OLLAMA_PID" 2>/dev/null || true
        fi
        wait "$OLLAMA_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

"$HOME/ollama-macs/bin/ollama" serve > "ollama-${SLURM_JOB_ID}.log" 2>&1 &
OLLAMA_PID=$!

OLLAMA_READY=0
for _ in {1..30}; do
    if curl -fsS "http://127.0.0.1:${OLLAMA_PORT}/api/tags" >/dev/null; then
        OLLAMA_READY=1
        break
    fi
    sleep 2
done

if [[ "$OLLAMA_READY" -ne 1 ]]; then
    echo "Ollama did not become ready on port ${OLLAMA_PORT}." >&2
    exit 1
fi

ROUNDS="${ROUNDS:-60}"
OUTPUT="transcripts/experiment_2_${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}.txt"
HISTORY_OUTPUT="transcripts/experiment_2_${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}_history.txt"

python run_experiment_2.py \
    --model "ollama_chat/qwen3:4b" \
    --api-base "http://127.0.0.1:${OLLAMA_PORT}" \
    --rounds "$ROUNDS" \
    --output "$OUTPUT" \
    --history-output "$HISTORY_OUTPUT"
