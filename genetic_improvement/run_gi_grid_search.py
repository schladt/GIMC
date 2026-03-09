#!/usr/bin/env python3
"""Run GI grid search with CSV logging and resume support."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

CSV_HEADER = [
    "search_id",
    "run_index",
    "total_runs",
    "start_time",
    "end_time",
    "duration_seconds",
    "exit_code",
    "num_variants",
    "population_size",
    "mutation_rate",
    "generations",
    "checkpoint_prefix",
]


@dataclass(frozen=True)
class GridRun:
    run_index: int
    num_variants: int
    population_size: int
    mutation_rate: str
    generations: int
    search_id: str

    @property
    def checkpoint_prefix(self) -> str:
        mutation_tag = self.mutation_rate.replace(".", "p")
        return (
            f"grid_{self.search_id}_r{self.run_index}_nv{self.num_variants}_"
            f"n{self.population_size}_mr{mutation_tag}"
        )

    @property
    def combo_key(self) -> tuple[int, int, str, int]:
        return (self.num_variants, self.population_size, self.mutation_rate, self.generations)


@dataclass(frozen=True)
class LogSummary:
    path: Path
    search_id: str
    completed_keys: frozenset[tuple[int, int, str, int]]
    completed_count: int
    expected_total: int
    generations: int | None

    @property
    def incomplete(self) -> bool:
        return self.completed_count < self.expected_total


def parse_int_list(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def parse_float_str_list(value: str) -> list[str]:
    return [normalize_float_string(item.strip()) for item in value.split(",") if item.strip()]


def normalize_float_string(value: str | float) -> str:
    return format(float(value), ".12g")


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_log_dir = script_dir / "grid_search_logs"
    default_gi_loop = script_dir / "gi_loop.py"

    parser = argparse.ArgumentParser(description="Run GI grid search and log progress to CSV.")
    parser.add_argument(
        "--num-variants-values",
        default="4,8,16",
        help="Comma-separated --num-variants values (default: 4,8,16).",
    )
    parser.add_argument(
        "--population-size-values",
        default="8,16,32",
        help="Comma-separated population size values (default: 8,16,32).",
    )
    parser.add_argument(
        "--mutation-rate-values",
        default="0.001,0.005,0.01",
        help="Comma-separated mutation rate values (default: 0.001,0.005,0.01).",
    )
    parser.add_argument(
        "--generations",
        type=int,
        default=5,
        help="Number of generations to pass through to gi_loop.py (default: 5).",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=default_log_dir,
        help=f"Directory for grid-search CSV logs (default: {default_log_dir}).",
    )
    parser.add_argument(
        "--gi-loop-path",
        type=Path,
        default=default_gi_loop,
        help=f"Path to gi_loop.py (default: {default_gi_loop}).",
    )
    parser.add_argument(
        "--resume-search-id",
        default=None,
        help="Resume a specific search_id from an existing CSV file.",
    )
    parser.add_argument(
        "--auto-resume-latest",
        action="store_true",
        help="Automatically resume the most recent incomplete CSV search if available.",
    )
    return parser.parse_args()


def build_grid_runs(
    search_id: str,
    num_variants_values: list[int],
    population_size_values: list[int],
    mutation_rate_values: list[str],
    generations: int,
) -> list[GridRun]:
    runs: list[GridRun] = []
    run_index = 0
    for num_variants in num_variants_values:
        for population_size in population_size_values:
            for mutation_rate in mutation_rate_values:
                run_index += 1
                runs.append(
                    GridRun(
                        run_index=run_index,
                        num_variants=num_variants,
                        population_size=population_size,
                        mutation_rate=mutation_rate,
                        generations=generations,
                        search_id=search_id,
                    )
                )
    return runs


def parse_csv_row_combo(row: dict[str, str]) -> tuple[int, int, str, int] | None:
    try:
        return (
            int(row["num_variants"]),
            int(row["population_size"]),
            normalize_float_string(row["mutation_rate"]),
            int(row["generations"]),
        )
    except (KeyError, ValueError, TypeError):
        return None


def read_log_summary(path: Path) -> LogSummary | None:
    try:
        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return None

            rows = list(reader)
            if not rows:
                return None
    except OSError:
        return None

    search_id = rows[0].get("search_id", "").strip()
    if not search_id:
        return None

    completed_keys: set[tuple[int, int, str, int]] = set()
    totals: list[int] = []
    generations_seen: set[int] = set()

    for row in rows:
        combo = parse_csv_row_combo(row)
        if combo is not None:
            completed_keys.add(combo)
            generations_seen.add(combo[3])
        try:
            totals.append(int(row["total_runs"]))
        except (KeyError, ValueError, TypeError):
            continue

    expected_total = max(totals) if totals else len(completed_keys)
    generations = next(iter(generations_seen)) if len(generations_seen) == 1 else None

    return LogSummary(
        path=path,
        search_id=search_id,
        completed_keys=frozenset(completed_keys),
        completed_count=len(completed_keys),
        expected_total=expected_total,
        generations=generations,
    )


def find_log_summaries(log_dir: Path) -> list[LogSummary]:
    if not log_dir.exists():
        return []

    summaries: list[LogSummary] = []
    for csv_path in sorted(log_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True):
        summary = read_log_summary(csv_path)
        if summary is not None:
            summaries.append(summary)
    return summaries


def choose_resume_summary(
    args: argparse.Namespace,
    summaries: Iterable[LogSummary],
) -> LogSummary | None:
    summaries = list(summaries)
    if not summaries:
        return None

    by_search_id = {summary.search_id: summary for summary in summaries}
    if args.resume_search_id:
        selected = by_search_id.get(args.resume_search_id)
        if selected is None:
            raise ValueError(
                f"--resume-search-id '{args.resume_search_id}' not found in {args.log_dir}"
            )
        return selected

    incomplete = [summary for summary in summaries if summary.incomplete]
    if not incomplete:
        return None

    latest = incomplete[0]
    if args.auto_resume_latest:
        print(
            f"Auto-resuming latest incomplete search: {latest.search_id} "
            f"({latest.completed_count}/{latest.expected_total} complete)"
        )
        return latest

    if not sys.stdin.isatty():
        print(
            "Found incomplete grid search CSV(s), but stdin is non-interactive. "
            "Starting a new search. Use --auto-resume-latest or --resume-search-id to resume."
        )
        return None

    print("Found incomplete grid search CSV(s):")
    for summary in incomplete:
        marker = " (latest)" if summary is latest else ""
        print(
            f"  - search_id={summary.search_id}: {summary.completed_count}/{summary.expected_total} "
            f"complete, file={summary.path.name}{marker}"
        )

    response = input(
        f"Resume latest incomplete search_id '{latest.search_id}'? [Y/n]: "
    ).strip().lower()
    if response in ("", "y", "yes"):
        return latest

    print("Starting a new search.")
    return None


def ensure_csv_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)


def append_log_row(path: Path, row: list[str | int]) -> None:
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)


def run_one_grid_point(gi_loop_path: Path, run: GridRun) -> int:
    cmd = [
        sys.executable,
        str(gi_loop_path),
        "-N",
        str(run.population_size),
        "-G",
        str(run.generations),
        "--mutation-rate",
        run.mutation_rate,
        "--num-variants",
        str(run.num_variants),
        "--checkpoint-prefix",
        run.checkpoint_prefix,
    ]
    return subprocess.run(cmd, check=False).returncode


def main() -> int:
    args = parse_args()
    num_variants_values = parse_int_list(args.num_variants_values)
    population_size_values = parse_int_list(args.population_size_values)
    mutation_rate_values = parse_float_str_list(args.mutation_rate_values)

    if not num_variants_values:
        raise ValueError("--num-variants-values cannot be empty")
    if not population_size_values:
        raise ValueError("--population-size-values cannot be empty")
    if not mutation_rate_values:
        raise ValueError("--mutation-rate-values cannot be empty")
    if args.generations <= 0:
        raise ValueError("--generations must be > 0")
    if not args.gi_loop_path.exists():
        raise FileNotFoundError(f"gi_loop path not found: {args.gi_loop_path}")

    total_runs = (
        len(num_variants_values) * len(population_size_values) * len(mutation_rate_values)
    )

    summaries = find_log_summaries(args.log_dir)
    resume_summary = choose_resume_summary(args, summaries)

    if resume_summary is not None:
        if resume_summary.expected_total != total_runs:
            raise ValueError(
                "Resume grid size mismatch. "
                f"CSV expects total_runs={resume_summary.expected_total} but current grid has {total_runs}. "
                "Use matching grid values or start a new search."
            )
        if (
            resume_summary.generations is not None
            and resume_summary.generations != args.generations
        ):
            raise ValueError(
                "Resume generations mismatch. "
                f"CSV uses generations={resume_summary.generations} but --generations={args.generations}."
            )
        search_id = resume_summary.search_id
        log_file = resume_summary.path
    else:
        search_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = args.log_dir / f"gi_grid_search_{search_id}.csv"
        ensure_csv_header(log_file)

    all_runs = build_grid_runs(
        search_id=search_id,
        num_variants_values=num_variants_values,
        population_size_values=population_size_values,
        mutation_rate_values=mutation_rate_values,
        generations=args.generations,
    )

    if resume_summary is not None:
        pending_runs = [run for run in all_runs if run.combo_key not in resume_summary.completed_keys]
    else:
        pending_runs = all_runs

    print(f"Starting GI grid search {search_id}")
    print(f"Log file: {log_file}")
    print(f"Total runs: {total_runs}")
    print(f"Pending runs: {len(pending_runs)}")

    if not pending_runs:
        print("No pending runs. Grid search is already complete.")
        return 0

    for run in pending_runs:
        print(
            f"[{run.run_index}/{total_runs}] "
            f"num_variants={run.num_variants} "
            f"population_size={run.population_size} "
            f"mutation_rate={run.mutation_rate} "
            f"checkpoint_prefix={run.checkpoint_prefix}"
        )
        start_epoch = int(time.time())
        start_iso = datetime.now().astimezone().isoformat(timespec="seconds")

        exit_code = run_one_grid_point(args.gi_loop_path, run)

        end_epoch = int(time.time())
        end_iso = datetime.now().astimezone().isoformat(timespec="seconds")
        duration_seconds = end_epoch - start_epoch

        append_log_row(
            log_file,
            [
                search_id,
                run.run_index,
                total_runs,
                start_iso,
                end_iso,
                duration_seconds,
                exit_code,
                run.num_variants,
                run.population_size,
                run.mutation_rate,
                run.generations,
                run.checkpoint_prefix,
            ],
        )

    print(f"Grid search complete. Results logged to: {log_file}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2)
