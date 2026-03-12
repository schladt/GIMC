#!/usr/bin/env python3
"""Run multi-generation GI loop with checkpoint resume support."""

from __future__ import annotations

import argparse
import base64
import math
import os
import pickle
import random
import statistics
import sys
import time
from collections import Counter
from typing import Dict, Iterable, List

# Ensure project root is importable when running this file directly.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from genetic_improvement.config import (  # noqa: E402
    BSI_CLASSIFICATION,
    DATA_PATH,
    MODEL,
    NUM_VARIANTS,
    SYSTEM_PROMPT,
    USER_PROMPT,
    bsi_objectives,
)
from genetic_improvement.genome import Edit, Genome  # noqa: E402
from genetic_improvement.ollamachat import OllamaChat  # noqa: E402

REQUIRED_STAGE_KEYS = (
    "population",
    "repaired_population",
    "mutated_population",
    "repaired_mutants",
)
EDITABLE_TAGS = ["struct", "function", "decl", "condition", "expr", "if_stmt", "call"]

# Multi-metric bottleneck detection thresholds
BOTTLENECK_STD_THRESHOLD = 1e-2           # Fitness std threshold
BOTTLENECK_CV_THRESHOLD = 0.05            # Coefficient of variation threshold (5%)
BOTTLENECK_RANGE_THRESHOLD = 0.01         # Min fitness range threshold
BOTTLENECK_STAGNATION_WINDOW = 3          # Number of generations to check for stagnation
BOTTLENECK_STAGNATION_EPSILON = 1e-3      # Minimum improvement required
BOTTLENECK_SAMPLE_SIZE = 5                # Number of top candidates to sample for bottleneck analysis


def parse_args() -> argparse.Namespace:
    """Parse CLI options for GI loop execution."""
    parser = argparse.ArgumentParser(description="Run full GI loop for N generations.")
    parser.add_argument(
        "-N",
        "--population-size",
        type=int,
        default=20,
        help="Base population size N. Generation 0 starts with N; later generations start with 2N.",
    )
    parser.add_argument(
        "-G",
        "--generations",
        type=int,
        default=5,
        help="Total number of generations to run.",
    )
    parser.add_argument(
        "--mutation-rate",
        type=float,
        default=0.01,
        help="Chromosome mutation probability used during mutation stage.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="Polling interval in seconds while waiting for candidate status completion.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional RNG seed for reproducible mutation selection.",
    )
    parser.add_argument(
        "--checkpoint-prefix",
        type=str,
        default="",
        help="Optional prefix prepended to checkpoint filename.",
    )
    parser.add_argument(
        "--num-variants",
        type=int,
        default=NUM_VARIANTS,
        help=f"LLM variants requested per generation batch (default from config: {NUM_VARIANTS}).",
    )
    return parser.parse_args()


def get_checkpoint_path(checkpoint_prefix: str = "") -> str:
    """Return checkpoint path based on DATA_PATH and BSI classification."""
    filename = f"{checkpoint_prefix}_{BSI_CLASSIFICATION}_checkpoint.pkl"
    return os.path.join(DATA_PATH, "GI", filename)


def ensure_checkpoint_dir(path: str) -> None:
    """Ensure checkpoint directory exists."""
    os.makedirs(os.path.dirname(path), exist_ok=True)


def load_checkpoint(path: str) -> List[Dict[str, List[Genome]]]:
    """Load checkpoint data or return an empty generation list."""
    if not os.path.exists(path):
        return []

    with open(path, "rb") as f:
        data = pickle.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Checkpoint at {path} is not a list.")

    return data


def save_checkpoint(path: str, data: List[Dict[str, List[Genome]]]) -> None:
    """Persist generation records to checkpoint."""
    ensure_checkpoint_dir(path)
    with open(path, "wb") as f:
        pickle.dump(data, f)


def is_complete_generation(generation_record: Dict[str, List[Genome]]) -> bool:
    """Check if all required stage outputs are present."""
    return all(key in generation_record for key in REQUIRED_STAGE_KEYS)


def completed_generation_count(data: List[Dict[str, List[Genome]]]) -> int:
    """Count generations that contain all required stage keys."""
    return sum(1 for generation_record in data if is_complete_generation(generation_record))


def poll_until_complete(stage: str, genomes: List[Genome], poll_interval: float) -> None:
    """Poll candidate statuses until all genomes are complete/error (status >= 3)."""
    if not genomes:
        print(f"[{stage}] No candidates to wait for.")
        return

    print(f"[{stage}] Waiting for {len(genomes)} candidate(s) to reach status >= 3...")
    start = time.time()

    while True:
        statuses = []
        missing = 0

        for genome in genomes:
            candidate = genome.get_candidate()
            if candidate is None:
                missing += 1
                statuses.append(-1)
            else:
                statuses.append(candidate.status)

        status_counts = Counter(statuses)
        all_done = missing == 0 and all(status >= 3 for status in statuses)

        if all_done:
            elapsed = time.time() - start
            print(f"[{stage}] Complete after {elapsed:.1f}s. Status counts: {dict(status_counts)}")
            return

        elapsed = time.time() - start
        print(f"[{stage}] Elapsed {elapsed:.1f}s | Status counts: {dict(status_counts)}")
        time.sleep(poll_interval)


def fitness_of(genome: Genome) -> float:
    """Return candidate fitness score with safe fallback."""
    candidate = genome.get_candidate()
    if candidate is None:
        return 0.0
    fitness = candidate.get_fitness()
    return float(fitness if fitness is not None else 0.0)


def summarize_stage(stage: str, genomes: List[Genome]) -> None:
    """Print concise stats for a stage population."""
    if not genomes:
        print(f"[{stage}] count=0")
        return

    candidates = [genome.get_candidate() for genome in genomes]
    fitness_scores = [fitness_of(genome) for genome in genomes]
    status_counts = Counter(candidate.status if candidate else -1 for candidate in candidates)
    error_count = sum(1 for candidate in candidates if candidate and candidate.error_message)

    mean_fit = statistics.fmean(fitness_scores) if fitness_scores else 0.0
    min_fit = min(fitness_scores) if fitness_scores else 0.0
    max_fit = max(fitness_scores) if fitness_scores else 0.0
    std_fit = statistics.pstdev(fitness_scores) if len(fitness_scores) > 1 else 0.0

    print(
        f"[{stage}] count={len(genomes)} | fitness(mean/min/max/std)="
        f"{mean_fit:.4f}/{min_fit:.4f}/{max_fit:.4f}/{std_fit:.4f} | "
        f"errors={error_count} | statuses={dict(status_counts)}"
    )


def detect_bottleneck(
    genomes: List[Genome], 
    generation: int,
    best_fitness_history: List[float]
) -> bool:
    """Detect if a bottleneck has occurred using multiple metrics (OR configuration).
    
    A bottleneck is detected if ANY of the following conditions are met:
    1. Fitness standard deviation is too low (population convergence)
    2. Coefficient of variation is too low (relative diversity loss)
    3. Fitness range (max-min) is too small (compressed fitness landscape)
    4. Best fitness has stagnated over recent generations (no improvement)
    
    Args:
        genomes: Current population of genomes
        generation: Current generation number
        best_fitness_history: List of best fitness values from all generations
        
    Returns:
        True if bottleneck detected, False otherwise
    """
    if not genomes or len(genomes) < 2:
        return False
    
    fitness_scores = [fitness_of(genome) for genome in genomes]
    
    # Metric 1: Standard deviation
    std_fit = statistics.pstdev(fitness_scores)
    std_bottleneck = std_fit < BOTTLENECK_STD_THRESHOLD
    
    # Metric 2: Coefficient of Variation (relative diversity)
    mean_fit = statistics.fmean(fitness_scores)
    cv_bottleneck = False
    cv = 0.0
    if mean_fit > 0:
        cv = std_fit / mean_fit
        cv_bottleneck = cv < BOTTLENECK_CV_THRESHOLD
    
    # Metric 3: Fitness range compression
    min_fit = min(fitness_scores)
    max_fit = max(fitness_scores)
    fitness_range = max_fit - min_fit
    range_bottleneck = fitness_range < BOTTLENECK_RANGE_THRESHOLD
    
    # Metric 4: Fitness stagnation (no improvement over recent generations)
    stagnation_bottleneck = False
    improvement = 0.0
    if len(best_fitness_history) >= BOTTLENECK_STAGNATION_WINDOW:
        recent_best = max(best_fitness_history[-BOTTLENECK_STAGNATION_WINDOW:])
        older_best = max(best_fitness_history[:-BOTTLENECK_STAGNATION_WINDOW]) if len(best_fitness_history) > BOTTLENECK_STAGNATION_WINDOW else 0.0
        improvement = recent_best - older_best
        stagnation_bottleneck = improvement < BOTTLENECK_STAGNATION_EPSILON
    
    # OR configuration: any metric triggers bottleneck
    is_bottleneck = std_bottleneck or cv_bottleneck or range_bottleneck or stagnation_bottleneck
    
    if is_bottleneck:
        triggered_metrics = []
        if std_bottleneck:
            triggered_metrics.append(f"std={std_fit:.4e}<{BOTTLENECK_STD_THRESHOLD:.4e}")
        if cv_bottleneck:
            triggered_metrics.append(f"CV={cv:.4e}<{BOTTLENECK_CV_THRESHOLD:.4e}")
        if range_bottleneck:
            triggered_metrics.append(f"range={fitness_range:.4e}<{BOTTLENECK_RANGE_THRESHOLD:.4e}")
        if stagnation_bottleneck:
            triggered_metrics.append(f"stagnation: Δbest={improvement:.4e}<{BOTTLENECK_STAGNATION_EPSILON:.4e} over {BOTTLENECK_STAGNATION_WINDOW} gens")
        
        print(
            f"[bottleneck] Generation {generation}: Bottleneck detected\n"
            f"[bottleneck]   Triggered metrics: {' | '.join(triggered_metrics)}\n"
            f"[bottleneck]   Fitness stats: mean={mean_fit:.4f}, std={std_fit:.4e}, "
            f"min={min_fit:.4f}, max={max_fit:.4f}, range={fitness_range:.4e}"
        )
    
    return is_bottleneck


def generate_bottleneck_warning(genomes: List[Genome], generation: int) -> str | None:
    """Generate LLM warning message for detected bottleneck."""
    if not genomes:
        return None
    
    # Get top N candidates sorted by fitness
    top_candidates = sorted(genomes, key=fitness_of, reverse=True)[:BOTTLENECK_SAMPLE_SIZE]
    
    # Decode code samples
    code_samples = []
    for genome in top_candidates:
        candidate = genome.get_candidate()
        if candidate and candidate.code:
            try:
                decoded_code = base64.b64decode(candidate.code).decode('utf-8')
                code_samples.append(decoded_code)
            except Exception as e:
                print(f"[bottleneck] Warning: Failed to decode candidate code: {e}")
                continue
    
    if not code_samples:
        print("[bottleneck] Warning: No code samples available for bottleneck analysis")
        return None
    
    # Generate warning message using LLM
    print(f"[bottleneck] Generating warning message from {len(code_samples)} code sample(s)...")
    bottleneck_system_prompt = (
        "You are a helpful assistant that provides feedback on code snippets "
        "and is an expert in cybersecurity TTPs and malware analysis"
    )
    bottleneck_chat = OllamaChat(model=MODEL, system_prompt=bottleneck_system_prompt, temperature=0.7)
    
    code_str = "\n\n=== code example ===\n\n".join(code_samples)
    message_str = (
        f"The following code samples (separated by === code example ===) appear to take "
        f"the same high level approach as each other in attempting to accomplish the objective of: \n"
        f"{bsi_objectives}\n\n"
        f"Summarize this approach in two lines.\n"
        f"Prepend your message with 'Previously tested solutions take the following approach:'\n"
        f"Append your message with 'Do not generate any more solutions that take the same approach. "
        f"Alternative approaches could include [include a short list of alternative approaches]'\n\n"
        f"=== code example ===\n\n{code_str}"
    )
    
    try:
        response = bottleneck_chat.chat(message_str, stream=False)
        print(f"[bottleneck] Generation {generation} warning generated successfully")
        return response
    except Exception as e:
        print(f"[bottleneck] Error generating warning: {e}")
        return None


def generate_new_variants(
    target_count: int, num_variants: int, bottleneck_warnings: List[str] | None = None
) -> List[Genome]:
    """Generate and submit new variants until target count is reached or attempts are exhausted.
    
    Args:
        target_count: Number of variants to generate
        num_variants: Batch size for LLM generation
        bottleneck_warnings: List of warning messages from bottleneck detection to append to prompt
    """
    if target_count <= 0:
        return []

    batch_size = max(1, num_variants)
    genomes: List[Genome] = []
    attempts = 0
    max_attempts = max(3, math.ceil(target_count / batch_size) * 3)

    print(
        f"[generation] Target new candidates: {target_count} | "
        f"Variants per batch: {batch_size} | "
        f"max generation batches allowed: {max_attempts} (stops early once target is reached)"
    )

    while len(genomes) < target_count and attempts < max_attempts:
        attempts += 1
        remaining = target_count - len(genomes)
        print(
            f"[generation] LLM generation batch {attempts} (up to {max_attempts}); "
            f"remaining candidates needed: {remaining}"
        )

        # Build prompt with bottleneck warnings appended
        prompt = USER_PROMPT
        if bottleneck_warnings:
            warnings_text = "\n\n".join(bottleneck_warnings)
            prompt = f"{USER_PROMPT}\n\n=== IMPORTANT CONSTRAINTS ===\n{warnings_text}"
            print(f"[generation] Using prompt with {len(bottleneck_warnings)} bottleneck warning(s)")
        
        chat = OllamaChat(model=MODEL, system_prompt=SYSTEM_PROMPT, temperature=1.0)
        variants = chat.generate_variants(num_variants=num_variants, initial_prompt=prompt)
        parsed_count = len(variants)
        print(f"[generation] Generation batch {attempts}: parsed {parsed_count} variant(s) from {num_variants} requests.")

        if not variants:
            print("[generation] Warning: parsed 0 variants from this generation batch.")
            continue

        candidate_hashes = OllamaChat.submit_variants(variants, classification=BSI_CLASSIFICATION)
        submitted_count = len(candidate_hashes)
        accepted_count = sum(1 for candidate_hash in candidate_hashes if candidate_hash is not None)
        added_count = 0
        for candidate_hash in candidate_hashes:
            if candidate_hash is None:
                continue
            genomes.append(Genome(candidate_hash=candidate_hash))
            added_count += 1
            if len(genomes) >= target_count:
                break

        failed_submissions = submitted_count - accepted_count
        skipped_due_to_target = max(0, accepted_count - added_count)
        print(
            f"[generation] Generation batch {attempts}: submitted={submitted_count}, "
            f"accepted={accepted_count}, submission_failures={failed_submissions}, "
            f"added={added_count}, skipped_due_to_target={skipped_due_to_target}, "
            f"total_created={len(genomes)}/{target_count}"
        )

    if len(genomes) >= target_count:
        print(
            f"[generation] Target reached after {attempts} generation batch(es); "
            f"{max_attempts - attempts} batch(es) remained unused."
        )

    if len(genomes) < target_count:
        print(
            f"[generation] Warning: requested {target_count} new candidates but only created {len(genomes)}."
        )

    return genomes[:target_count]


def repair_population(population: Iterable[Genome], stage_name: str) -> List[Genome]:
    """Repair candidates with errors and keep originals when repair fails."""
    repaired_population: List[Genome] = []

    for idx, genome in enumerate(population, start=1):
        candidate = genome.get_candidate()
        if candidate and candidate.error_message is not None:
            print(f"[{stage_name}] Repairing candidate {idx} ({genome.candidate_hash[:8]})")
            repaired_hash = genome.repair_code()
            if repaired_hash is not None:
                repaired_population.append(Genome(repaired_hash))
            else:
                repaired_population.append(genome)
        else:
            repaired_population.append(genome)

    return repaired_population


def build_donor_pool(population: Iterable[Genome]) -> List[Dict[str, int | str]]:
    """Build donor metadata from chromosome-level genome representations."""
    donor_pool: List[Dict[str, int | str]] = []

    for genome in population:
        genome.build_genome()
        for chromosome in genome.chromosomes:
            donor_pool.append(
                {
                    "position": chromosome.position,
                    "tag": chromosome.tag,
                    "candidate_hash": genome.candidate_hash,
                    "depth": chromosome.depth,
                }
            )

    return donor_pool


def mutate_population(repaired_population: List[Genome], mutation_rate: float) -> List[Genome]:
    """Apply replace edits to repaired population and submit mutated candidates."""
    donor_pool = build_donor_pool(repaired_population)
    print(f"[mutation] Donor pool size: {len(donor_pool)}")

    for genome in repaired_population:
        for chromosome in genome.chromosomes:
            if chromosome.tag not in EDITABLE_TAGS:
                continue
            if random.random() >= mutation_rate:
                continue

            max_depth = chromosome.depth + 2
            min_depth = chromosome.depth - 2
            sub_pool = [
                donor
                for donor in donor_pool
                if donor["tag"] == chromosome.tag and min_depth <= donor["depth"] <= max_depth
            ]
            if not sub_pool:
                continue

            donor = random.choice(sub_pool)
            chromosome.edits.append(
                Edit(
                    edit_type="replace",
                    candidate_hash=str(donor["candidate_hash"]),
                    candidate_position=int(donor["position"]),
                )
            )

    mutated_population: List[Genome] = []
    for genome in repaired_population:
        mutated_hash = genome.apply_edits()
        if mutated_hash is not None:
            mutated_population.append(Genome(mutated_hash, build_genome=True))

    return mutated_population


def unique_by_hash(genomes: Iterable[Genome]) -> List[Genome]:
    """Deduplicate genomes by candidate hash while preserving first occurrence."""
    deduped: Dict[str, Genome] = {}
    for genome in genomes:
        if genome.candidate_hash not in deduped:
            deduped[genome.candidate_hash] = genome
    return list(deduped.values())


def select_top_n_from_generation(generation_record: Dict[str, List[Genome]], n: int) -> List[Genome]:
    """Select top-N candidates by fitness across all generation stage outputs."""
    pool: List[Genome] = []
    for key in REQUIRED_STAGE_KEYS:
        pool.extend(generation_record.get(key, []))

    deduped_pool = unique_by_hash(pool)
    ranked = sorted(deduped_pool, key=fitness_of, reverse=True)
    selected = ranked[:n]

    print(
        f"[selection] Selected {len(selected)} of {len(deduped_pool)} unique candidates "
        f"from population/repaired/mutated/repaired_mutants."
    )
    summarize_stage("selection", selected)
    return selected


def main() -> None:
    """Run the full GI loop, with resume support, through the requested generation count."""
    args = parse_args()

    if args.population_size <= 0:
        raise ValueError("--population-size must be > 0")
    if args.generations <= 0:
        raise ValueError("--generations must be > 0")
    if not (0.0 <= args.mutation_rate <= 1.0):
        raise ValueError("--mutation-rate must be in [0.0, 1.0]")
    if args.num_variants <= 0:
        raise ValueError("--num-variants must be > 0")

    if args.seed is not None:
        random.seed(args.seed)

    checkpoint_path = get_checkpoint_path(args.checkpoint_prefix)
    ensure_checkpoint_dir(checkpoint_path)

    print(f"Using checkpoint: {checkpoint_path}")
    print(f"Classification: {BSI_CLASSIFICATION}")
    print(
        f"Run config: N={args.population_size}, generations={args.generations}, "
        f"mutation_rate={args.mutation_rate}, poll_interval={args.poll_interval}s, "
        f"num_variants={args.num_variants}"
    )

    generational_data = load_checkpoint(checkpoint_path)
    completed = completed_generation_count(generational_data)

    if len(generational_data) != completed:
        print(
            "Checkpoint contains incomplete generation data; continuing from completed generations only."
        )
        generational_data = generational_data[:completed]
        save_checkpoint(checkpoint_path, generational_data)

    print(f"Completed generations found in checkpoint: {completed}")

    if completed >= args.generations:
        print("Requested generation count already satisfied by checkpoint. Exiting.")
        return

    selected_for_next = (
        select_top_n_from_generation(generational_data[completed - 1], args.population_size)
        if completed > 0
        else []
    )
    
    # Track bottleneck warnings across generations
    bottleneck_warnings: List[str] = []
    
    # Track best fitness history for stagnation detection
    best_fitness_history: List[float] = []

    for gen_idx in range(completed, args.generations):
        gen_num = gen_idx + 1
        print("\n" + "=" * 80)
        print(f"Generation {gen_num}/{args.generations}")
        print("=" * 80)

        # Stage 1: build current population (N on first generation, else carry-over + N fresh).
        if gen_idx == 0:
            print(
                f"[stage: population] Initial generation: creating {args.population_size} "
                "new candidate(s)."
            )
            population = generate_new_variants(
                args.population_size, args.num_variants, bottleneck_warnings
            )
        else:
            print(
                f"[stage: population] Carrying over {len(selected_for_next)} selected candidate(s) "
                f"and creating {args.population_size} fresh candidate(s) "
                f"(target combined population: {len(selected_for_next) + args.population_size})."
            )
            fresh_population = generate_new_variants(
                args.population_size, args.num_variants, bottleneck_warnings
            )
            population = selected_for_next + fresh_population

        generation_record: Dict[str, List[Genome]] = {"population": population}
        if len(generational_data) <= gen_idx:
            generational_data.append(generation_record)
        else:
            generational_data[gen_idx] = generation_record

        poll_until_complete("population", generation_record["population"], args.poll_interval)
        summarize_stage("population", generation_record["population"])
        save_checkpoint(checkpoint_path, generational_data)

        # Stage 2: attempt repair for non-compiling or errored base candidates.
        print("[stage: repair_population] Repairing compile/runtime-failed initial candidates.")
        generation_record["repaired_population"] = repair_population(
            generation_record["population"], stage_name="repair_population"
        )

        poll_until_complete("repaired_population", generation_record["repaired_population"], args.poll_interval)
        summarize_stage("repaired_population", generation_record["repaired_population"])
        save_checkpoint(checkpoint_path, generational_data)

        # Stage 3: mutate repaired population via donor-based edit replacement.
        print("[stage: mutate_population] Building donor pool and applying edits.")
        generation_record["mutated_population"] = mutate_population(
            generation_record["repaired_population"], args.mutation_rate
        )

        poll_until_complete("mutated_population", generation_record["mutated_population"], args.poll_interval)
        summarize_stage("mutated_population", generation_record["mutated_population"])
        save_checkpoint(checkpoint_path, generational_data)

        # Stage 4: repair mutated candidates that still have errors.
        print("[stage: repair_mutants] Repairing mutated candidates with errors.")
        generation_record["repaired_mutants"] = repair_population(
            generation_record["mutated_population"], stage_name="repair_mutants"
        )

        poll_until_complete("repaired_mutants", generation_record["repaired_mutants"], args.poll_interval)
        summarize_stage("repaired_mutants", generation_record["repaired_mutants"])
        save_checkpoint(checkpoint_path, generational_data)

        # Selection: keep top-N from all candidates observed in this generation.
        selected_for_next = select_top_n_from_generation(generation_record, args.population_size)
        
        # Track best fitness for stagnation detection
        if selected_for_next:
            current_best = max(fitness_of(g) for g in selected_for_next)
            best_fitness_history.append(current_best)
        else:
            best_fitness_history.append(0.0)
        
        # Print generation summary for top N selected candidates
        print(f"\n[Generation {gen_num} Summary - Top N Selected]")
        summarize_stage("selected_population", selected_for_next)
        
        # Bottleneck detection: check if population has converged
        if detect_bottleneck(selected_for_next, gen_num, best_fitness_history):
            warning = generate_bottleneck_warning(selected_for_next, gen_num)
            if warning:
                bottleneck_warnings.append(warning)
                print(f"[bottleneck] Total warnings accumulated: {len(bottleneck_warnings)}")
            
            # After bottleneck detection, pass nothing to next generation
            selected_for_next = []
            print(f"[bottleneck] Cleared selection - no candidates passed to next generation")
        
        save_checkpoint(checkpoint_path, generational_data)

    print("\nGI loop complete.")
    print(f"Saved {len(generational_data)} generation record(s) to {checkpoint_path}")


if __name__ == "__main__":
    main()
