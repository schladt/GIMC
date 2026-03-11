#!/usr/bin/env python3
"""Analyze GI grid-search checkpoints using notebook-style Genome fitness logic."""

from __future__ import annotations

import argparse
import csv
import math
import pickle
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

# Ensure project root is importable for Genome unpickling.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Imported for pickle compatibility and notebook-parity lookup logic.
from genetic_improvement.genome import Genome  # noqa: F401

PHASE_DEFS: list[tuple[str, str, str]] = [
    ("Repair Operation", "population", "repaired_population"),
    ("Mutation Operation", "repaired_population", "mutated_population"),
    ("Repair Mutants Operation", "mutated_population", "repaired_mutants"),
    ("Selection Operation", "repaired_mutants", "selected_population"),
]
STAGE_ORDER = [
    "population",
    "repaired_population",
    "mutated_population",
    "repaired_mutants",
    "selected_population",
]
PARAM_FACTORS = ["num_variants", "population_size", "mutation_rate"]
PRIMARY_METRIC = "final_selected_max"


@dataclass
class LookupStats:
    ok: int = 0
    missing: int = 0
    errors: int = 0


FITNESS_CACHE: dict[str, float] = {}
LOOKUP_STATUS: dict[str, str] = {}
LOOKUP_ERROR_MSG: dict[str, str] = {}


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description=(
            "Analyze GI grid-search checkpoints using the same Genome->Candidate "
            "fitness access pattern as results-visualization.ipynb."
        )
    )
    parser.add_argument(
        "--log-csv",
        type=Path,
        default=script_dir / "grid_search_logs" / "gi_grid_search_20260309_015032.csv",
        help="Path to GI grid-search CSV log.",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("/mnt/data/gimc/GI"),
        help="Directory containing GI checkpoint pickle files.",
    )
    parser.add_argument(
        "--classification",
        default="com",
        help="Expected classification suffix in checkpoint filenames.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to genetic_improvement/grid_search_analysis/<log-stem>/",
    )
    return parser.parse_args()


def cohen_d(group1: np.ndarray, group2: np.ndarray) -> float:
    """Calculate Cohen's d effect size with safe fallbacks."""
    n1 = int(group1.size)
    n2 = int(group2.size)
    if n1 < 2 or n2 < 2:
        return 0.0

    var1 = float(np.var(group1, ddof=1))
    var2 = float(np.var(group2, ddof=1))
    pooled_denom = (n1 + n2 - 2)
    if pooled_denom <= 0:
        return 0.0
    pooled_std = math.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / pooled_denom)
    if pooled_std <= 0:
        return 0.0
    return float((np.mean(group1) - np.mean(group2)) / pooled_std)


def effect_interp(effect_size: float) -> str:
    abs_d = abs(effect_size)
    if abs_d < 0.2:
        return "negligible"
    if abs_d < 0.5:
        return "small"
    if abs_d < 0.8:
        return "medium"
    return "large"


def normality_pvalue(scores: np.ndarray) -> float:
    """Notebook-style normality gate with guardrails for degenerate data."""
    n = int(scores.size)
    if n > 5000:
        return 0.05
    if n < 3:
        return 0.0
    if float(np.std(scores)) == 0.0:
        return 0.0
    try:
        _, p = stats.shapiro(scores)
        return float(p)
    except Exception:
        return 0.0


def resolve_checkpoint_file(
    checkpoint_prefix: str,
    results_dir: Path,
    classification: str,
) -> Path:
    exact = results_dir / f"{checkpoint_prefix}_{classification}_checkpoint.pkl"
    if exact.exists():
        return exact

    candidates = sorted(results_dir.glob(f"{checkpoint_prefix}_*_checkpoint.pkl"))
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise FileNotFoundError(
            f"No checkpoint found for prefix '{checkpoint_prefix}' in {results_dir}"
        )
    raise FileNotFoundError(
        f"Ambiguous checkpoint prefix '{checkpoint_prefix}'. Matches: "
        + ", ".join(path.name for path in candidates)
    )


def fitness_of(genome: Any) -> float:
    """Get candidate fitness through Genome.get_candidate() (notebook-compatible)."""
    candidate_hash = getattr(genome, "candidate_hash", None)
    if candidate_hash in FITNESS_CACHE:
        return FITNESS_CACHE[candidate_hash]  # type: ignore[index]

    if not isinstance(candidate_hash, str) or not candidate_hash:
        return 0.0

    try:
        candidate = genome.get_candidate()
    except Exception as exc:
        LOOKUP_STATUS[candidate_hash] = "error"
        LOOKUP_ERROR_MSG[candidate_hash] = f"{type(exc).__name__}: {exc}"
        FITNESS_CACHE[candidate_hash] = 0.0
        return 0.0

    if candidate is None:
        LOOKUP_STATUS[candidate_hash] = "missing"
        FITNESS_CACHE[candidate_hash] = 0.0
        return 0.0

    try:
        score = candidate.get_fitness()
        fit_val = float(score if score is not None else 0.0)
    except Exception as exc:
        LOOKUP_STATUS[candidate_hash] = "error"
        LOOKUP_ERROR_MSG[candidate_hash] = f"{type(exc).__name__}: {exc}"
        FITNESS_CACHE[candidate_hash] = 0.0
        return 0.0

    LOOKUP_STATUS[candidate_hash] = "ok"
    FITNESS_CACHE[candidate_hash] = fit_val
    return fit_val


def reconstruct_selected_population(checkpoint: list[dict[str, list[Any]]]) -> None:
    """
    Recreate selected_population exactly as in results-visualization.ipynb:
    top-N (N = initial population size) across all four non-selected stages.
    """
    if not checkpoint:
        return

    initial_n = len(checkpoint[0].get("population", []))
    for generation in checkpoint:
        all_individuals: list[Any] = []
        all_individuals.extend(generation.get("population", []))
        all_individuals.extend(generation.get("repaired_population", []))
        all_individuals.extend(generation.get("mutated_population", []))
        all_individuals.extend(generation.get("repaired_mutants", []))

        sorted_individuals = sorted(all_individuals, key=fitness_of, reverse=True)
        generation["selected_population"] = sorted_individuals[:initial_n]


def stage_scores(stage_genomes: list[Any]) -> np.ndarray:
    return np.array([fitness_of(genome) for genome in stage_genomes], dtype=float)


def analyze_phase_transition(
    before: list[Any],
    after: list[Any],
    phase_name: str,
    generation_index: int,
) -> dict[str, Any]:
    """Notebook-style phase transition statistics."""
    before_scores = stage_scores(before)
    after_scores = stage_scores(after)

    before_mean = float(np.mean(before_scores)) if before_scores.size else 0.0
    before_std = float(np.std(before_scores)) if before_scores.size else 0.0
    after_mean = float(np.mean(after_scores)) if after_scores.size else 0.0
    after_std = float(np.std(after_scores)) if after_scores.size else 0.0
    mean_diff = after_mean - before_mean
    pct_change = (mean_diff / before_mean * 100.0) if before_mean != 0 else 0.0

    before_p_norm = normality_pvalue(before_scores)
    after_p_norm = normality_pvalue(after_scores)

    if before_p_norm > 0.05 and after_p_norm > 0.05:
        _, p_value = stats.ttest_ind(after_scores, before_scores)
        test_used = "Independent t-test"
    else:
        _, p_value = stats.mannwhitneyu(after_scores, before_scores, alternative="two-sided")
        test_used = "Mann-Whitney U"

    effect_size = cohen_d(after_scores, before_scores)
    interp = effect_interp(effect_size)

    return {
        "generation": generation_index + 1,
        "phase": phase_name,
        "before_mean": before_mean,
        "before_std": before_std,
        "after_mean": after_mean,
        "after_std": after_std,
        "mean_diff": mean_diff,
        "pct_change": pct_change,
        "p_value": float(p_value),
        "significant": bool(p_value < 0.05),
        "effect_size": effect_size,
        "effect_interp": interp,
        "test_used": test_used,
        "n_before": int(before_scores.size),
        "n_after": int(after_scores.size),
        "before_p_norm": before_p_norm,
        "after_p_norm": after_p_norm,
    }


def summarize_stage(
    run_meta: dict[str, Any],
    generation_idx: int,
    stage_name: str,
    genomes: list[Any],
) -> dict[str, Any]:
    scores = stage_scores(genomes)
    return {
        **run_meta,
        "generation": generation_idx + 1,
        "stage": stage_name,
        "n": int(scores.size),
        "mean_fitness": float(np.mean(scores)) if scores.size else 0.0,
        "std_fitness": float(np.std(scores)) if scores.size else 0.0,
        "min_fitness": float(np.min(scores)) if scores.size else 0.0,
        "max_fitness": float(np.max(scores)) if scores.size else 0.0,
    }


def lookup_stats_for_hashes(hashes: set[str]) -> LookupStats:
    stats_out = LookupStats()
    for candidate_hash in hashes:
        status = LOOKUP_STATUS.get(candidate_hash)
        if status == "ok":
            stats_out.ok += 1
        elif status == "missing":
            stats_out.missing += 1
        elif status == "error":
            stats_out.errors += 1
    return stats_out


def run_two_sample_inference(group_a: np.ndarray, group_b: np.ndarray) -> dict[str, Any]:
    p_norm_a = normality_pvalue(group_a)
    p_norm_b = normality_pvalue(group_b)
    if p_norm_a > 0.05 and p_norm_b > 0.05:
        stat, p_val = stats.ttest_ind(group_a, group_b)
        test_used = "Independent t-test"
    else:
        stat, p_val = stats.mannwhitneyu(group_a, group_b, alternative="two-sided")
        test_used = "Mann-Whitney U"

    d_val = cohen_d(group_a, group_b)
    return {
        "test_used": test_used,
        "statistic": float(stat),
        "p_value": float(p_val),
        "effect_size": float(d_val),
        "effect_interp": effect_interp(float(d_val)),
        "group_a_p_norm": p_norm_a,
        "group_b_p_norm": p_norm_b,
    }


def pairwise_factor_tests(
    run_summary_df: pd.DataFrame,
    factor: str,
    metric: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    levels = sorted(run_summary_df[factor].unique())
    for idx, lvl_a in enumerate(levels):
        for lvl_b in levels[idx + 1 :]:
            group_a = run_summary_df.loc[run_summary_df[factor] == lvl_a, metric].to_numpy(dtype=float)
            group_b = run_summary_df.loc[run_summary_df[factor] == lvl_b, metric].to_numpy(dtype=float)
            res = run_two_sample_inference(group_a, group_b)
            rows.append(
                {
                    "factor": factor,
                    "metric": metric,
                    "level_a": lvl_a,
                    "level_b": lvl_b,
                    "n_a": int(group_a.size),
                    "n_b": int(group_b.size),
                    "mean_a": float(np.mean(group_a)),
                    "mean_b": float(np.mean(group_b)),
                    "mean_diff_a_minus_b": float(np.mean(group_a) - np.mean(group_b)),
                    **res,
                }
            )
    return pd.DataFrame(rows)


def omnibus_factor_test(
    run_summary_df: pd.DataFrame,
    factor: str,
    metric: str,
) -> dict[str, Any]:
    groups = []
    labels = []
    for level, group in run_summary_df.groupby(factor):
        groups.append(group[metric].to_numpy(dtype=float))
        labels.append(level)

    normals = [normality_pvalue(arr) > 0.05 for arr in groups]
    if all(normals):
        stat, p_val = stats.f_oneway(*groups)
        test_used = "One-way ANOVA"
    else:
        stat, p_val = stats.kruskal(*groups)
        test_used = "Kruskal-Wallis"

    return {
        "factor": factor,
        "metric": metric,
        "test_used": test_used,
        "p_value": float(p_val),
        "statistic": float(stat),
        "levels": ", ".join(str(label) for label in labels),
    }


def factor_level_summary(run_summary_df: pd.DataFrame, factor: str) -> pd.DataFrame:
    grouped = run_summary_df.groupby(factor).agg(
        n_runs=("run_index", "count"),
        final_selected_max_mean=("final_selected_max", "mean"),
        final_selected_max_std=("final_selected_max", "std"),
        final_selected_mean_mean=("final_selected_mean", "mean"),
        final_selected_mean_std=("final_selected_mean", "std"),
        selected_gain_mean=("selected_mean_gain_abs", "mean"),
        duration_mean_sec=("duration_seconds", "mean"),
        duration_std_sec=("duration_seconds", "std"),
        quality_per_hour_mean=("quality_per_hour", "mean"),
        quality_per_hour_std=("quality_per_hour", "std"),
    )
    out = grouped.reset_index()
    out.insert(0, "factor", factor)
    return out


def choose_recommendations(run_summary_df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    quality_ranked = run_summary_df.sort_values(
        by=["final_selected_max", "final_selected_mean", "selected_mean_gain_abs"],
        ascending=False,
    )
    best_quality = quality_ranked.iloc[0]

    # Balanced choice: within 95% of best final max, pick highest quality/hour.
    quality_threshold = 0.95 * float(best_quality["final_selected_max"])
    near_best = run_summary_df.loc[run_summary_df["final_selected_max"] >= quality_threshold].copy()
    if near_best.empty:
        near_best = run_summary_df.copy()
    best_balanced = near_best.sort_values(
        by=["quality_per_hour", "final_selected_mean", "final_selected_max"],
        ascending=False,
    ).iloc[0]
    return best_quality, best_balanced


def fmt(v: Any, digits: int = 4) -> str:
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        return f"{float(v):.{digits}f}"
    return str(v)


def build_markdown_report(
    log_csv_path: Path,
    output_dir: Path,
    run_summary_df: pd.DataFrame,
    phase_df: pd.DataFrame,
    level_df: pd.DataFrame,
    omnibus_df: pd.DataFrame,
    pairwise_df: pd.DataFrame,
    best_quality: pd.Series,
    best_balanced: pd.Series,
) -> str:
    phase_overall = (
        phase_df.groupby("phase")
        .agg(
            avg_mean_diff=("mean_diff", "mean"),
            avg_effect_size=("effect_size", "mean"),
            effect_size_std=("effect_size", "std"),
            significant_rate=("significant", "mean"),
            n=("phase", "count"),
        )
        .reset_index()
    )

    top5 = run_summary_df.sort_values(
        by=["final_selected_max", "final_selected_mean"], ascending=False
    ).head(5)

    lines: list[str] = []
    lines.append(f"# GI Grid Search Recommendation ({log_csv_path.stem})")
    lines.append("")
    lines.append("## Data & Method")
    lines.append(f"- Log CSV: `{log_csv_path}`")
    lines.append(f"- Runs analyzed: **{len(run_summary_df)}**")
    lines.append(f"- Generations per run (median): **{int(run_summary_df['generations_observed'].median())}**")
    lines.append(
        "- Fitness extraction uses `Genome.get_candidate().get_fitness()` and "
        "reconstructs `selected_population` with the same top-N logic as "
        "`results-visualization.ipynb`."
    )
    lines.append(
        "- Inferential tests mirror notebook style: Shapiro normality check, "
        "then Independent t-test or Mann-Whitney U, with Cohen's d."
    )
    lines.append("")
    lines.append("## Primary Recommendation")
    lines.append(
        "- **Use this parameter set for max quality**: "
        f"`num_variants={int(best_quality['num_variants'])}`, "
        f"`population_size={int(best_quality['population_size'])}`, "
        f"`mutation_rate={best_quality['mutation_rate']}`"
    )
    lines.append(
        f"- Evidence: final selected max fitness={fmt(best_quality['final_selected_max'])}, "
        f"final selected mean={fmt(best_quality['final_selected_mean'])}, "
        f"duration={fmt(best_quality['duration_seconds'] / 3600.0)}h."
    )
    if int(best_balanced["run_index"]) != int(best_quality["run_index"]):
        lines.append("")
        lines.append("## Balanced Alternative")
        lines.append(
            "- **Use this if runtime efficiency matters**: "
            f"`num_variants={int(best_balanced['num_variants'])}`, "
            f"`population_size={int(best_balanced['population_size'])}`, "
            f"`mutation_rate={best_balanced['mutation_rate']}`"
        )
        lines.append(
            f"- Evidence: quality/hour={fmt(best_balanced['quality_per_hour'])}, "
            f"final selected max={fmt(best_balanced['final_selected_max'])}, "
            f"duration={fmt(best_balanced['duration_seconds'] / 3600.0)}h."
        )

    lines.append("")
    lines.append("## Top 5 Runs (Quality)")
    lines.append("| run_index | num_variants | population_size | mutation_rate | final_selected_max | final_selected_mean | duration_h |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for _, row in top5.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    fmt(row["run_index"], 0),
                    fmt(row["num_variants"], 0),
                    fmt(row["population_size"], 0),
                    str(row["mutation_rate"]),
                    fmt(row["final_selected_max"]),
                    fmt(row["final_selected_mean"]),
                    fmt(row["duration_seconds"] / 3600.0),
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("## Phase Impact Summary")
    lines.append("| phase | avg_mean_diff | avg_effect_size | effect_size_std | significant_rate | n |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for _, row in phase_overall.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["phase"]),
                    fmt(row["avg_mean_diff"]),
                    fmt(row["avg_effect_size"]),
                    fmt(row["effect_size_std"]),
                    fmt(100.0 * row["significant_rate"], 1) + "%",
                    fmt(row["n"], 0),
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("## Factor-Level Means")
    lines.append("| factor | level | n_runs | final_selected_max_mean | final_selected_mean_mean | duration_mean_h | quality_per_hour_mean |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for _, row in level_df.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["factor"]),
                    str(row[PARAM_FACTORS[0]])
                    if row["factor"] == PARAM_FACTORS[0]
                    else str(row[PARAM_FACTORS[1]])
                    if row["factor"] == PARAM_FACTORS[1]
                    else str(row[PARAM_FACTORS[2]]),
                    fmt(row["n_runs"], 0),
                    fmt(row["final_selected_max_mean"]),
                    fmt(row["final_selected_mean_mean"]),
                    fmt(row["duration_mean_sec"] / 3600.0),
                    fmt(row["quality_per_hour_mean"]),
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("## Omnibus Tests")
    lines.append("| factor | metric | test_used | statistic | p_value |")
    lines.append("| --- | --- | --- | --- | --- |")
    for _, row in omnibus_df.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["factor"]),
                    str(row["metric"]),
                    str(row["test_used"]),
                    fmt(row["statistic"]),
                    fmt(row["p_value"]),
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("## Pairwise Tests (Primary Metric)")
    primary_pairs = pairwise_df[pairwise_df["metric"] == PRIMARY_METRIC].copy()
    primary_pairs = primary_pairs.sort_values(by=["factor", "p_value"])
    lines.append("| factor | level_a | level_b | test_used | p_value | effect_size | effect_interp | mean_diff_a_minus_b |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for _, row in primary_pairs.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["factor"]),
                    str(row["level_a"]),
                    str(row["level_b"]),
                    str(row["test_used"]),
                    fmt(row["p_value"]),
                    fmt(row["effect_size"]),
                    str(row["effect_interp"]),
                    fmt(row["mean_diff_a_minus_b"]),
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("## Artifacts")
    lines.append(f"- `phase_transition_results.csv`")
    lines.append(f"- `stage_metrics_by_generation.csv`")
    lines.append(f"- `run_summary.csv`")
    lines.append(f"- `factor_level_summary.csv`")
    lines.append(f"- `factor_omnibus_tests.csv`")
    lines.append(f"- `factor_pairwise_tests.csv`")
    lines.append(f"- `recommendation.md`")
    lines.append("")
    lines.append(f"_Generated in `{output_dir}`_")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()

    if not args.log_csv.exists():
        raise FileNotFoundError(f"Log CSV not found: {args.log_csv}")
    if not args.results_dir.exists():
        raise FileNotFoundError(f"Results directory not found: {args.results_dir}")

    output_dir = args.output_dir
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent / "grid_search_analysis" / args.log_csv.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    with args.log_csv.open("r", newline="", encoding="utf-8") as f:
        log_rows = list(csv.DictReader(f))
    if not log_rows:
        raise ValueError(f"No rows in log CSV: {args.log_csv}")

    phase_rows: list[dict[str, Any]] = []
    stage_rows: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []

    for idx, row in enumerate(log_rows, start=1):
        checkpoint_prefix = row["checkpoint_prefix"].strip()
        checkpoint_path = resolve_checkpoint_file(
            checkpoint_prefix=checkpoint_prefix,
            results_dir=args.results_dir,
            classification=args.classification,
        )
        with checkpoint_path.open("rb") as f:
            checkpoint = pickle.load(f)

        reconstruct_selected_population(checkpoint)

        run_meta: dict[str, Any] = {
            "search_id": row.get("search_id", ""),
            "run_index": int(row["run_index"]),
            "num_variants": int(row["num_variants"]),
            "population_size": int(row["population_size"]),
            "mutation_rate": row["mutation_rate"],
            "generations": int(row["generations"]),
            "duration_seconds": float(row.get("duration_seconds", 0) or 0),
            "checkpoint_prefix": checkpoint_prefix,
            "checkpoint_file": checkpoint_path.name,
            "exit_code": int(row.get("exit_code", 0) or 0),
        }

        run_hashes: set[str] = set()

        for gen_idx, generation in enumerate(checkpoint):
            for stage_name in STAGE_ORDER:
                genomes = generation.get(stage_name, [])
                for genome in genomes:
                    candidate_hash = getattr(genome, "candidate_hash", None)
                    if isinstance(candidate_hash, str) and candidate_hash:
                        run_hashes.add(candidate_hash)
                stage_rows.append(summarize_stage(run_meta, gen_idx, stage_name, genomes))

            for phase_name, before_key, after_key in PHASE_DEFS:
                phase_row = analyze_phase_transition(
                    before=generation.get(before_key, []),
                    after=generation.get(after_key, []),
                    phase_name=phase_name,
                    generation_index=gen_idx,
                )
                phase_rows.append({**run_meta, **phase_row})

        stage_df_run = pd.DataFrame([r for r in stage_rows if r["run_index"] == run_meta["run_index"]])
        phase_df_run = pd.DataFrame([r for r in phase_rows if r["run_index"] == run_meta["run_index"]])

        first_pop_mean = float(
            stage_df_run.loc[
                (stage_df_run["generation"] == 1) & (stage_df_run["stage"] == "population"),
                "mean_fitness",
            ].iloc[0]
        )
        last_gen = int(stage_df_run["generation"].max())
        final_selected = stage_df_run.loc[
            (stage_df_run["generation"] == last_gen) & (stage_df_run["stage"] == "selected_population")
        ].iloc[0]
        selected_overall_mean = float(
            stage_df_run.loc[stage_df_run["stage"] == "selected_population", "mean_fitness"].mean()
        )
        selection_phase = phase_df_run.loc[phase_df_run["phase"] == "Selection Operation"]
        mutation_phase = phase_df_run.loc[phase_df_run["phase"] == "Mutation Operation"]

        lookup = lookup_stats_for_hashes(run_hashes)
        duration_hours = run_meta["duration_seconds"] / 3600.0 if run_meta["duration_seconds"] > 0 else np.nan
        quality_per_hour = (
            float(final_selected["max_fitness"]) / duration_hours
            if duration_hours and not np.isnan(duration_hours)
            else np.nan
        )

        run_rows.append(
            {
                **run_meta,
                "generations_observed": last_gen,
                "unique_candidates_seen": len(run_hashes),
                "candidate_lookup_ok": lookup.ok,
                "candidate_lookup_missing": lookup.missing,
                "candidate_lookup_errors": lookup.errors,
                "initial_population_mean": first_pop_mean,
                "final_selected_mean": float(final_selected["mean_fitness"]),
                "final_selected_max": float(final_selected["max_fitness"]),
                "final_selected_min": float(final_selected["min_fitness"]),
                "selected_mean_across_generations": selected_overall_mean,
                "selected_mean_gain_abs": float(final_selected["mean_fitness"]) - first_pop_mean,
                "selected_mean_gain_pct": (
                    ((float(final_selected["mean_fitness"]) - first_pop_mean) / first_pop_mean * 100.0)
                    if first_pop_mean != 0
                    else 0.0
                ),
                "selection_effect_size_mean": float(selection_phase["effect_size"].mean()),
                "selection_significant_rate": float(selection_phase["significant"].mean()),
                "mutation_effect_size_mean": float(mutation_phase["effect_size"].mean()),
                "quality_per_hour": quality_per_hour,
            }
        )

        print(
            f"[{idx}/{len(log_rows)}] run_index={run_meta['run_index']} "
            f"params=(nv={run_meta['num_variants']}, n={run_meta['population_size']}, "
            f"mr={run_meta['mutation_rate']}) complete"
        )

    phase_df = pd.DataFrame(phase_rows)
    stage_df = pd.DataFrame(stage_rows)
    run_summary_df = pd.DataFrame(run_rows).sort_values("run_index").reset_index(drop=True)

    factor_level_frames = [factor_level_summary(run_summary_df, factor) for factor in PARAM_FACTORS]
    level_df = pd.concat(factor_level_frames, ignore_index=True)

    omnibus_rows: list[dict[str, Any]] = []
    pairwise_frames: list[pd.DataFrame] = []
    metrics_for_factor_tests = ["final_selected_max", "final_selected_mean", "quality_per_hour"]
    for factor in PARAM_FACTORS:
        for metric in metrics_for_factor_tests:
            omnibus_rows.append(omnibus_factor_test(run_summary_df, factor, metric))
            pairwise_frames.append(pairwise_factor_tests(run_summary_df, factor, metric))
    omnibus_df = pd.DataFrame(omnibus_rows)
    pairwise_df = pd.concat(pairwise_frames, ignore_index=True)

    best_quality, best_balanced = choose_recommendations(run_summary_df)

    # Persist artifacts.
    phase_df.to_csv(output_dir / "phase_transition_results.csv", index=False)
    stage_df.to_csv(output_dir / "stage_metrics_by_generation.csv", index=False)
    run_summary_df.to_csv(output_dir / "run_summary.csv", index=False)
    level_df.to_csv(output_dir / "factor_level_summary.csv", index=False)
    omnibus_df.to_csv(output_dir / "factor_omnibus_tests.csv", index=False)
    pairwise_df.to_csv(output_dir / "factor_pairwise_tests.csv", index=False)

    recommendation_md = build_markdown_report(
        log_csv_path=args.log_csv,
        output_dir=output_dir,
        run_summary_df=run_summary_df,
        phase_df=phase_df,
        level_df=level_df,
        omnibus_df=omnibus_df,
        pairwise_df=pairwise_df,
        best_quality=best_quality,
        best_balanced=best_balanced,
    )
    (output_dir / "recommendation.md").write_text(recommendation_md, encoding="utf-8")

    overall_lookup = LookupStats(
        ok=sum(1 for status in LOOKUP_STATUS.values() if status == "ok"),
        missing=sum(1 for status in LOOKUP_STATUS.values() if status == "missing"),
        errors=sum(1 for status in LOOKUP_STATUS.values() if status == "error"),
    )
    print("")
    print("Analysis complete.")
    print(f"Output directory: {output_dir}")
    print(
        "Lookup summary: "
        f"ok={overall_lookup.ok}, missing={overall_lookup.missing}, errors={overall_lookup.errors}"
    )
    print(
        "Recommended (quality): "
        f"nv={int(best_quality['num_variants'])}, "
        f"n={int(best_quality['population_size'])}, "
        f"mr={best_quality['mutation_rate']}"
    )
    print(
        "Recommended (balanced): "
        f"nv={int(best_balanced['num_variants'])}, "
        f"n={int(best_balanced['population_size'])}, "
        f"mr={best_balanced['mutation_rate']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
