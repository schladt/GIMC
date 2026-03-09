#!/usr/bin/env bash

set -u -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
GI_LOOP="${PROJECT_ROOT}/genetic_improvement/gi_loop.py"

NUM_VARIANTS_VALUES=(4 8 16)
POPULATION_SIZE_VALUES=(8 16 32)
MUTATION_RATE_VALUES=(0.001 0.005 0.01)

# Keep gi_loop default behavior unless you explicitly change this.
GENERATIONS=5

SEARCH_ID="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="${PROJECT_ROOT}/genetic_improvement/grid_search_logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/gi_grid_search_${SEARCH_ID}.csv"

total_runs=$(( ${#NUM_VARIANTS_VALUES[@]} * ${#POPULATION_SIZE_VALUES[@]} * ${#MUTATION_RATE_VALUES[@]} ))
run_index=0

echo "search_id,run_index,total_runs,start_time,end_time,duration_seconds,exit_code,num_variants,population_size,mutation_rate,generations,checkpoint_prefix" > "${LOG_FILE}"

echo "Starting GI grid search ${SEARCH_ID}"
echo "Log file: ${LOG_FILE}"
echo "Total runs: ${total_runs}"

for num_variants in "${NUM_VARIANTS_VALUES[@]}"; do
  for population_size in "${POPULATION_SIZE_VALUES[@]}"; do
    for mutation_rate in "${MUTATION_RATE_VALUES[@]}"; do
      run_index=$((run_index + 1))

      mutation_tag="${mutation_rate//./p}"
      checkpoint_prefix="grid_${SEARCH_ID}_r${run_index}_nv${num_variants}_n${population_size}_mr${mutation_tag}"

      start_epoch="$(date +%s)"
      start_iso="$(date -Iseconds)"

      echo "[${run_index}/${total_runs}] num_variants=${num_variants} population_size=${population_size} mutation_rate=${mutation_rate} checkpoint_prefix=${checkpoint_prefix}"

      python3 "${GI_LOOP}" \
        -N "${population_size}" \
        -G "${GENERATIONS}" \
        --mutation-rate "${mutation_rate}" \
        --num-variants "${num_variants}" \
        --checkpoint-prefix "${checkpoint_prefix}"

      exit_code=$?
      end_epoch="$(date +%s)"
      end_iso="$(date -Iseconds)"
      duration_seconds=$((end_epoch - start_epoch))

      echo "${SEARCH_ID},${run_index},${total_runs},${start_iso},${end_iso},${duration_seconds},${exit_code},${num_variants},${population_size},${mutation_rate},${GENERATIONS},${checkpoint_prefix}" >> "${LOG_FILE}"
    done
  done
done

echo "Grid search complete. Results logged to: ${LOG_FILE}"
