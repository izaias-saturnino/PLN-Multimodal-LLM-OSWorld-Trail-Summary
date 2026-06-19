#!/usr/bin/env python3

"""
03_complexity_screening.py

Parallel LLM-based complexity screening for OSWorld trajectory
summarization examples.

Each model must:
1. Explain what happened in the trajectory.
2. Explain whether summarizing it is complex.
3. Return exactly one final label:
   COMPLEX, UNCERTAIN, or SIMPLE.

Selection rule:
    accepted if at least N valid model votes are COMPLEX or UNCERTAIN.

Early stopping rule:
    If two valid votes are SIMPLE, reject.
    If two valid votes are COMPLEX/UNCERTAIN, accept.

This means the script does not call missing models for trajectories
that already have a conclusive decision.

Dependencies:
    pip install litellm tqdm pyyaml
"""

from __future__ import annotations

import argparse
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import yaml
from litellm import completion
from tqdm import tqdm


VALID_LABELS = {"COMPLEX", "UNCERTAIN", "SIMPLE"}
NON_SIMPLE_LABELS = {"COMPLEX", "UNCERTAIN"}

FINAL_LABEL_RE = re.compile(
    r"FINAL_LABEL\s*:\s*(COMPLEX|UNCERTAIN|SIMPLE)",
    re.IGNORECASE,
)

STEP_RE = re.compile(
    r"^={10,}\nSTEP\s+(\d+)\n={10,}$",
    re.MULTILINE,
)


def load_jsonl(path: Path):
    if not path.exists():
        return

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                yield json.loads(line)


def write_jsonl(path: Path, records: list[dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def append_jsonl_threadsafe(
    path: Path,
    record: dict[str, Any],
    lock: threading.Lock,
):
    path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(record, ensure_ascii=False) + "\n"

    with lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def trajectory_text_path(
    trajectory_texts_dir: Path,
    record: dict[str, Any],
) -> Path:
    filename = (
        f"{record['source_model']}__"
        f"{record['trajectory_id']}.txt"
    )

    return trajectory_texts_dir / filename


def split_header_and_steps(text: str):
    matches = list(STEP_RE.finditer(text))

    if not matches:
        return text.strip(), []

    header = text[: matches[0].start()].strip()
    steps = []

    for idx, match in enumerate(matches):
        start = match.start()

        if idx + 1 < len(matches):
            end = matches[idx + 1].start()
        else:
            end = len(text)

        steps.append(text[start:end].strip())

    return header, steps


def build_screening_context(
    text: str,
    max_steps_before_truncation: int,
    head_steps: int,
    tail_steps: int,
) -> dict[str, Any]:
    header, steps = split_header_and_steps(text)
    total_steps = len(steps)

    if total_steps == 0:
        return {
            "context": (
                "TRUNCATION_STATUS: UNKNOWN_NO_STEP_MARKERS_FOUND\n\n"
                + text
            ),
            "was_truncated": False,
            "shown_steps": "UNKNOWN",
            "total_steps": None,
        }

    if total_steps <= max_steps_before_truncation:
        context = (
            f"{header}\n\n"
            "TRUNCATION_STATUS: NOT_TRUNCATED\n"
            f"TOTAL_STEPS: {total_steps}\n"
            "SHOWN_STEPS: ALL_STEPS\n"
            "IMPORTANT: The full trajectory is visible below.\n\n"
            + "\n\n".join(steps)
        )

        return {
            "context": context,
            "was_truncated": False,
            "shown_steps": "ALL_STEPS",
            "total_steps": total_steps,
        }

    first_steps = steps[:head_steps]
    last_steps = steps[-tail_steps:]
    omitted_count = total_steps - head_steps - tail_steps

    context = (
        f"{header}\n\n"
        "TRUNCATION_STATUS: TRUNCATED\n"
        f"TOTAL_STEPS: {total_steps}\n"
        f"SHOWN_STEPS: FIRST_{head_steps}_AND_LAST_{tail_steps}\n"
        f"OMITTED_MIDDLE_STEPS: {omitted_count}\n"
        "IMPORTANT: This is not the full trajectory. The middle "
        "steps were omitted for screening efficiency. You must judge "
        "complexity based on the visible beginning and ending while "
        "explicitly acknowledging that the intermediate behavior is "
        "not visible.\n\n"
        + "\n\n".join(first_steps)
        + "\n\n"
        + "=" * 60
        + "\nMIDDLE STEPS OMITTED\n"
        + "=" * 60
        + "\n\n"
        + "\n\n".join(last_steps)
    )

    return {
        "context": context,
        "was_truncated": True,
        "shown_steps": f"FIRST_{head_steps}_AND_LAST_{tail_steps}",
        "total_steps": total_steps,
    }


def build_prompt(context: str) -> str:
    return f"""
You are evaluating whether a computer-use agent trajectory should be included in a benchmark for trajectory summarization.

The trajectory may be written partly or entirely in Chinese. You should understand it directly.

A trajectory is COMPLEX if writing a high-quality procedural summary requires understanding multiple decisions, state transitions, application switching, recovery attempts, partial failures, subtle task requirements, or non-trivial reasoning.

A trajectory is SIMPLE if it can be summarized correctly with little effort and minimal understanding of the execution process.

A trajectory is UNCERTAIN if it is not clearly simple but also not clearly complex.

Important criteria:
- Do not classify a trajectory as SIMPLE merely because it failed.
- Failed trajectories can be COMPLEX if they involve meaningful multi-step behavior, partial progress, recovery attempts, or subtle mistakes.
- A short trajectory can be COMPLEX if it involves subtle task requirements or cross-application behavior.
- A long trajectory can be SIMPLE if it is mostly repetitive or mechanically obvious.
- Pay close attention to whether TRUNCATION_STATUS is TRUNCATED or NOT_TRUNCATED.
- If the trajectory is truncated, explicitly mention that the middle steps are not visible.

You must reason in this order:
1. First explain what the agent did.
2. Then explain whether summarizing the trajectory requires non-trivial understanding.
3. Only then provide the final label.

Use exactly this format:

TRAJECTORY_EXPLANATION:
<brief explanation of what the agent did>

COMPLEXITY_RATIONALE:
<brief explanation of why this trajectory is complex, uncertain, or simple for summarization>

FINAL_LABEL:
<COMPLEX or UNCERTAIN or SIMPLE>

The FINAL_LABEL must be exactly one of:
COMPLEX
UNCERTAIN
SIMPLE

Trajectory:

{context}
""".strip()


def extract_label(response_text: str) -> str | None:
    match = FINAL_LABEL_RE.search(response_text)

    if not match:
        return None

    label = match.group(1).upper()

    if label not in VALID_LABELS:
        return None

    return label


def extract_section(response_text: str, section_name: str) -> str:
    pattern = re.compile(
        rf"{section_name}\s*:\s*(.*?)(?=\n[A-Z_]+\s*:|\Z)",
        re.DOTALL | re.IGNORECASE,
    )

    match = pattern.search(response_text)

    if not match:
        return ""

    return match.group(1).strip()


def build_litellm_kwargs(
    litellm_model: str,
    prompt: str,
    generation_config: dict[str, Any],
) -> dict[str, Any]:
    kwargs = {
        "model": litellm_model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "max_tokens": generation_config.get("max_tokens", 1200),
    }

    temperature = generation_config.get("temperature", None)
    top_p = generation_config.get("top_p", None)

    if temperature is not None:
        kwargs["temperature"] = temperature

    # Anthropic rejects temperature and top_p together for some models.
    # Keep temperature and omit top_p for all Anthropic models.
    if not litellm_model.startswith("anthropic/"):
        if top_p is not None:
            kwargs["top_p"] = top_p

    return kwargs


def call_model(
    litellm_model: str,
    prompt: str,
    generation_config: dict[str, Any],
    retries: int,
    sleep_seconds: float,
) -> str:
    last_error = None

    for attempt in range(retries + 1):
        try:
            kwargs = build_litellm_kwargs(
                litellm_model=litellm_model,
                prompt=prompt,
                generation_config=generation_config,
            )

            response = completion(**kwargs)
            content = response["choices"][0]["message"]["content"]

            if not isinstance(content, str) or not content.strip():
                raise RuntimeError("Empty model response.")

            return content

        except Exception as e:
            last_error = e

            if attempt < retries:
                time.sleep(sleep_seconds)

    raise RuntimeError(
        f"LiteLLM call failed after {retries + 1} attempts: {last_error}"
    )


def make_cache_key(
    trajectory_id: str,
    source_model: str,
    screening_model_name: str,
) -> tuple[str, str, str]:
    return (
        trajectory_id,
        source_model,
        screening_model_name,
    )


def load_cache_records(cache_path: Path) -> list[dict[str, Any]]:
    if not cache_path.exists():
        return []

    return list(load_jsonl(cache_path))


def latest_records_by_key(
    cache_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    latest = {}

    for record in cache_records:
        key = make_cache_key(
            record["trajectory_id"],
            record["source_model"],
            record["screening_model_name"],
        )

        latest[key] = record

    return list(latest.values())


def cache_index(
    cache_records: list[dict[str, Any]],
    retry_errors: bool,
) -> dict[tuple[str, str, str], dict[str, Any]]:
    index = {}

    for record in cache_records:
        key = make_cache_key(
            record["trajectory_id"],
            record["source_model"],
            record["screening_model_name"],
        )

        has_valid_label = record.get("label") in VALID_LABELS
        has_error = "error" in record

        if retry_errors and (has_error or not has_valid_label):
            continue

        index[key] = record

    return index


def build_cache_record_success(
    manifest_record: dict[str, Any],
    model_cfg: dict[str, Any],
    raw_response: str,
    context_info: dict[str, Any],
) -> dict[str, Any]:
    label = extract_label(raw_response)

    if label is None:
        raise RuntimeError(
            "Could not extract a valid FINAL_LABEL from model response."
        )

    return {
        "trajectory_id": manifest_record["trajectory_id"],
        "source_model": manifest_record["source_model"],
        "screening_model_name": model_cfg["name"],
        "litellm_model": model_cfg["litellm_model"],
        "label": label,
        "trajectory_explanation": extract_section(
            raw_response,
            "TRAJECTORY_EXPLANATION",
        ),
        "complexity_rationale": extract_section(
            raw_response,
            "COMPLEXITY_RATIONALE",
        ),
        "raw_response": raw_response,
        "was_truncated_for_screening": context_info["was_truncated"],
        "shown_steps_for_screening": context_info["shown_steps"],
        "total_steps_in_text": context_info["total_steps"],
    }


def build_cache_record_error(
    manifest_record: dict[str, Any],
    model_cfg: dict[str, Any],
    error: Exception,
    context_info: dict[str, Any],
) -> dict[str, Any]:
    return {
        "trajectory_id": manifest_record["trajectory_id"],
        "source_model": manifest_record["source_model"],
        "screening_model_name": model_cfg["name"],
        "litellm_model": model_cfg["litellm_model"],
        "label": None,
        "error": str(error),
        "was_truncated_for_screening": context_info["was_truncated"],
        "shown_steps_for_screening": context_info["shown_steps"],
        "total_steps_in_text": context_info["total_steps"],
    }


def build_screening_task(
    record: dict[str, Any],
    model_cfg: dict[str, Any],
    trajectory_texts_dir: Path,
    max_steps_before_truncation: int,
    head_steps: int,
    tail_steps: int,
) -> dict[str, Any] | None:
    text_path = trajectory_text_path(
        trajectory_texts_dir,
        record,
    )

    if not text_path.exists():
        print(f"[WARNING] Missing trajectory text: {text_path}")
        return None

    full_text = text_path.read_text(
        encoding="utf-8",
    )

    context_info = build_screening_context(
        full_text,
        max_steps_before_truncation=max_steps_before_truncation,
        head_steps=head_steps,
        tail_steps=tail_steps,
    )

    prompt = build_prompt(
        context_info["context"]
    )

    return {
        "manifest_record": record,
        "model_cfg": model_cfg,
        "prompt": prompt,
        "context_info": context_info,
    }


def run_screening_task(
    task: dict[str, Any],
    generation_config: dict[str, Any],
    retries: int,
    sleep_seconds: float,
) -> dict[str, Any]:
    manifest_record = task["manifest_record"]
    model_cfg = task["model_cfg"]
    prompt = task["prompt"]
    context_info = task["context_info"]

    try:
        raw_response = call_model(
            litellm_model=model_cfg["litellm_model"],
            prompt=prompt,
            generation_config=generation_config,
            retries=retries,
            sleep_seconds=sleep_seconds,
        )

        return build_cache_record_success(
            manifest_record=manifest_record,
            model_cfg=model_cfg,
            raw_response=raw_response,
            context_info=context_info,
        )

    except Exception as e:
        return build_cache_record_error(
            manifest_record=manifest_record,
            model_cfg=model_cfg,
            error=e,
            context_info=context_info,
        )


def group_cache_by_trajectory(
    cache_records: list[dict[str, Any]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped = {}

    for record in cache_records:
        key = (
            record["trajectory_id"],
            record["source_model"],
        )

        grouped.setdefault(key, []).append(record)

    return grouped


def vote_counts(
    model_results: list[dict[str, Any]],
) -> dict[str, int]:
    valid_labels = [
        result.get("label")
        for result in model_results
        if result.get("label") in VALID_LABELS
    ]

    simple_votes = sum(
        1
        for label in valid_labels
        if label == "SIMPLE"
    )

    non_simple_votes = sum(
        1
        for label in valid_labels
        if label in NON_SIMPLE_LABELS
    )

    return {
        "num_valid_votes": len(valid_labels),
        "simple_votes": simple_votes,
        "non_simple_votes": non_simple_votes,
    }


def has_conclusive_decision(
    model_results: list[dict[str, Any]],
    minimum_non_simple_votes: int,
) -> bool:
    counts = vote_counts(model_results)

    if counts["simple_votes"] >= 2:
        return True

    if counts["non_simple_votes"] >= minimum_non_simple_votes:
        return True

    return False


def build_final_record(
    manifest_record: dict[str, Any],
    model_results: list[dict[str, Any]],
    minimum_non_simple_votes: int,
    required_valid_votes: int,
) -> dict[str, Any]:
    votes = {}

    for result in model_results:
        model_name = result["screening_model_name"]
        label = result.get("label")
        votes[model_name] = label

    counts = vote_counts(model_results)

    num_valid_votes = counts["num_valid_votes"]
    simple_votes = counts["simple_votes"]
    non_simple_votes = counts["non_simple_votes"]

    if simple_votes >= 2:
        screening_status = "COMPLETE_EARLY"
        selected = False
        decision_reason = "two_valid_simple_votes"

    elif non_simple_votes >= minimum_non_simple_votes:
        screening_status = "COMPLETE_EARLY"
        selected = True
        decision_reason = (
            f"at_least_{minimum_non_simple_votes}"
            "_valid_non_simple_votes"
        )

    elif num_valid_votes < required_valid_votes:
        screening_status = "INCOMPLETE"
        selected = None
        decision_reason = "insufficient_valid_votes"

    else:
        screening_status = "COMPLETE"
        selected = (
            non_simple_votes >= minimum_non_simple_votes
        )
        decision_reason = "full_vote_rule_applied"

    return {
        **manifest_record,
        "complexity_votes": votes,
        "num_valid_complexity_votes": num_valid_votes,
        "simple_votes": simple_votes,
        "non_simple_votes": non_simple_votes,
        "screening_status": screening_status,
        "selected_for_gold_generation": selected,
        "decision_reason": decision_reason,
        "selection_rule": (
            f"accept_if_at_least_{minimum_non_simple_votes}"
            "_valid_votes_are_complex_or_uncertain;"
            "reject_if_at_least_2_valid_votes_are_simple;"
            "allow_early_decision_with_2_conclusive_votes"
        ),
        "screening_results": model_results,
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--manifest",
        required=True,
    )

    parser.add_argument(
        "--trajectory-texts-dir",
        required=True,
    )

    parser.add_argument(
        "--config",
        required=True,
    )

    parser.add_argument(
        "--cache",
        default="outputs/complexity_screening_cache.jsonl",
    )

    parser.add_argument(
        "--output",
        default="outputs/screened_manifest.jsonl",
    )

    parser.add_argument(
        "--retries",
        type=int,
        default=2,
    )

    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=5.0,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit for testing.",
    )

    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help=(
            "Ignore cached error/null-label records and retry them, "
            "but only for trajectories that still do not have a "
            "conclusive decision."
        ),
    )

    parser.add_argument(
        "--overwrite-cache",
        action="store_true",
        help=(
            "Ignore existing cache and start a new cache file."
        ),
    )

    parser.add_argument(
        "--max-workers",
        type=int,
        default=3,
        help=(
            "Maximum number of concurrent API calls. "
            "Start low, e.g. 3, then increase if rate limits allow."
        ),
    )

    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    trajectory_texts_dir = Path(args.trajectory_texts_dir)
    config_path = Path(args.config)
    cache_path = Path(args.cache)
    output_path = Path(args.output)

    config = load_yaml(config_path)

    models = config["models"]
    generation_config = config.get("generation", {})

    selection_config = config.get("selection", {})
    minimum_non_simple_votes = selection_config.get(
        "minimum_non_simple_votes",
        2,
    )
    required_valid_votes = selection_config.get(
        "required_valid_votes",
        len(models),
    )

    context_config = config.get("trajectory_context", {})
    max_steps_before_truncation = context_config.get(
        "max_steps_before_truncation",
        20,
    )
    head_steps = context_config.get("head_steps", 10)
    tail_steps = context_config.get("tail_steps", 10)

    manifest_records = list(load_jsonl(manifest_path))

    if args.limit is not None:
        manifest_records = manifest_records[: args.limit]

    if args.overwrite_cache and cache_path.exists():
        cache_path.unlink()

    existing_cache_records = latest_records_by_key(
        load_cache_records(cache_path)
    )

    existing_index = cache_index(
        existing_cache_records,
        retry_errors=args.retry_errors,
    )

    existing_grouped_cache = group_cache_by_trajectory(
        existing_cache_records
    )

    tasks = []

    skipped_conclusive = 0
    skipped_cached_calls = 0

    for record in manifest_records:
        trajectory_key = (
            record["trajectory_id"],
            record["source_model"],
        )

        existing_results_for_trajectory = existing_grouped_cache.get(
            trajectory_key,
            [],
        )

        if has_conclusive_decision(
            existing_results_for_trajectory,
            minimum_non_simple_votes=minimum_non_simple_votes,
        ):
            skipped_conclusive += 1
            continue

        for model_cfg in models:
            key = make_cache_key(
                trajectory_id=record["trajectory_id"],
                source_model=record["source_model"],
                screening_model_name=model_cfg["name"],
            )

            if key in existing_index:
                skipped_cached_calls += 1
                continue

            task = build_screening_task(
                record=record,
                model_cfg=model_cfg,
                trajectory_texts_dir=trajectory_texts_dir,
                max_steps_before_truncation=max_steps_before_truncation,
                head_steps=head_steps,
                tail_steps=tail_steps,
            )

            if task is not None:
                tasks.append(task)

    print()
    print("=" * 60)
    print("Complexity screening")
    print("=" * 60)
    print(f"Manifest records: {len(manifest_records)}")
    print(f"Models: {len(models)}")
    print(f"Pending API calls: {len(tasks)}")
    print(f"Skipped conclusive trajectories: {skipped_conclusive}")
    print(f"Skipped cached model calls: {skipped_cached_calls}")
    print(f"Max workers: {args.max_workers}")
    print(f"Cache file: {cache_path}")
    print("=" * 60)

    cache_lock = threading.Lock()

    if tasks:
        with ThreadPoolExecutor(
            max_workers=args.max_workers
        ) as executor:
            futures = [
                executor.submit(
                    run_screening_task,
                    task,
                    generation_config,
                    args.retries,
                    args.sleep_seconds,
                )
                for task in tasks
            ]

            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="API calls",
            ):
                cache_record = future.result()

                append_jsonl_threadsafe(
                    cache_path,
                    cache_record,
                    cache_lock,
                )

    final_cache_records = latest_records_by_key(
        load_cache_records(cache_path)
    )

    grouped_cache = group_cache_by_trajectory(
        final_cache_records
    )

    final_records = []

    for record in manifest_records:
        key = (
            record["trajectory_id"],
            record["source_model"],
        )

        model_results = grouped_cache.get(key, [])

        final_record = build_final_record(
            manifest_record=record,
            model_results=model_results,
            minimum_non_simple_votes=minimum_non_simple_votes,
            required_valid_votes=required_valid_votes,
        )

        final_records.append(final_record)

    write_jsonl(
        output_path,
        final_records,
    )

    complete = sum(
        1
        for r in final_records
        if r["screening_status"] == "COMPLETE"
    )

    complete_early = sum(
        1
        for r in final_records
        if r["screening_status"] == "COMPLETE_EARLY"
    )

    incomplete = sum(
        1
        for r in final_records
        if r["screening_status"] == "INCOMPLETE"
    )

    selected = sum(
        1
        for r in final_records
        if r["selected_for_gold_generation"] is True
    )

    rejected = sum(
        1
        for r in final_records
        if r["selected_for_gold_generation"] is False
    )

    print()
    print("=" * 60)
    print("Complexity screening completed")
    print("=" * 60)
    print(f"Cache file: {cache_path}")
    print(f"Output file: {output_path}")
    print(f"Records written: {len(final_records)}")
    print(f"Complete: {complete}")
    print(f"Complete early: {complete_early}")
    print(f"Incomplete: {incomplete}")
    print(f"Selected: {selected}")
    print(f"Rejected: {rejected}")
    print("=" * 60)


if __name__ == "__main__":
    main()