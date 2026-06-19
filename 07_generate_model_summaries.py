#!/usr/bin/env python3

"""
07_generate_model_summaries.py

Generates candidate summaries from evaluation models.

Input:
    outputs/gold_final_paired_clean.jsonl
    outputs/trajectory_texts/

Output:
    outputs/model_summary_cache.jsonl
    outputs/model_summaries.jsonl

Important:
    - The evaluated models do NOT receive the gold summary.
    - The evaluated models do NOT receive success_binary/success_raw.
    - The evaluated models do NOT receive the trajectory source model name.
    - All models receive the same sanitized trajectory text and prompt.
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


SUMMARY_RE = re.compile(
    r"PROCEDURAL_SUMMARY\s*:\s*(.*)",
    re.DOTALL | re.IGNORECASE,
)


REMOVE_HEADER_LINE_PATTERNS = [
    re.compile(r"^Source Model\s*:.*$", re.IGNORECASE),
    re.compile(r"^Success Binary\s*:.*$", re.IGNORECASE),
    re.compile(r"^Success Raw\s*:.*$", re.IGNORECASE),
]


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


def make_example_id(record: dict[str, Any]) -> str:
    return (
        f"{record['source_model']}__"
        f"{record['trajectory_id']}"
    )


def trajectory_text_path(
    trajectory_texts_dir: Path,
    record: dict[str, Any],
) -> Path:
    filename = (
        f"{record['source_model']}__"
        f"{record['trajectory_id']}.txt"
    )

    return trajectory_texts_dir / filename


def sanitize_trajectory_text(text: str) -> str:
    """
    Removes metadata that should not be shown to evaluated models.

    The model should infer the behavior from the trajectory, not from
    success labels or source-agent identity.
    """
    sanitized_lines = []

    for line in text.splitlines():
        should_remove = False

        for pattern in REMOVE_HEADER_LINE_PATTERNS:
            if pattern.match(line.strip()):
                should_remove = True
                break

        if not should_remove:
            sanitized_lines.append(line)

    return "\n".join(sanitized_lines).strip()


def build_prompt(
    record: dict[str, Any],
    sanitized_trajectory_text: str,
) -> str:
    instruction = record.get("instruction", "")

    return f"""
You are summarizing a computer-use agent trajectory.

The trajectory may contain Chinese thoughts and Python automation code. Understand the trajectory directly.

Your task is to write a procedural summary of what the agent actually did.

Important rules:
- Summarize the observed behavior, not the ideal solution.
- Do not invent actions that are not supported by the trajectory.
- Include major actions, application switches, decisions, repeated attempts, corrections, mistakes, and the final outcome when visible.
- If the agent failed or made a mistake, describe the observed failed behavior accurately rather than rewriting it as a successful solution.
- If the agent issued DONE, mention that it terminated.
- Do not include low-level pixel coordinates unless they are necessary to understand the behavior.
- Do not include irrelevant implementation details such as every import statement.
- Preserve task-relevant file names, applications, URLs, spreadsheet cells, document edits, and user-visible content.
- The summary should be concise but complete enough that a human can reconstruct the procedure.

Output language:
- Write the summary in English.

Output format:
Use exactly this format:

PROCEDURAL_SUMMARY:
<one coherent procedural summary>

Task instruction:
{instruction}

Trajectory:
{sanitized_trajectory_text}
""".strip()


def extract_summary(response_text: str) -> str:
    match = SUMMARY_RE.search(response_text)

    if not match:
        return response_text.strip()

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
        "max_tokens": generation_config.get("max_tokens", 2000),
    }

    temperature = generation_config.get("temperature", None)
    top_p = generation_config.get("top_p", None)

    openai_default_sampling_only_models = (
        litellm_model.startswith("openai/gpt-5")
        or litellm_model.startswith("openai/o")
    )

    if not openai_default_sampling_only_models:
        if temperature is not None:
            kwargs["temperature"] = temperature

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
    eval_model_name: str,
) -> tuple[str, str, str]:
    return (
        trajectory_id,
        source_model,
        eval_model_name,
    )


def load_cache_records(cache_path: Path) -> list[dict[str, Any]]:
    if not cache_path.exists():
        return []

    return list(load_jsonl(cache_path))


def latest_cache_index(
    cache_records: list[dict[str, Any]],
    retry_errors: bool,
) -> dict[tuple[str, str, str], dict[str, Any]]:
    index = {}

    for record in cache_records:
        key = make_cache_key(
            trajectory_id=record["trajectory_id"],
            source_model=record["source_model"],
            eval_model_name=record["eval_model_name"],
        )

        has_summary = bool(record.get("model_summary"))
        has_error = "error" in record

        if retry_errors and (has_error or not has_summary):
            continue

        index[key] = record

    return index


def build_task(
    record: dict[str, Any],
    model_cfg: dict[str, Any],
    trajectory_texts_dir: Path,
) -> dict[str, Any] | None:
    text_path = trajectory_text_path(
        trajectory_texts_dir,
        record,
    )

    if not text_path.exists():
        print(f"[WARNING] Missing trajectory text: {text_path}")
        return None

    trajectory_text = text_path.read_text(
        encoding="utf-8",
    )

    sanitized_text = sanitize_trajectory_text(
        trajectory_text
    )

    prompt = build_prompt(
        record=record,
        sanitized_trajectory_text=sanitized_text,
    )

    return {
        "record": record,
        "model_cfg": model_cfg,
        "trajectory_text_path": str(text_path),
        "prompt": prompt,
    }


def run_task(
    task: dict[str, Any],
    generation_config: dict[str, Any],
    retries: int,
    sleep_seconds: float,
) -> dict[str, Any]:
    record = task["record"]
    model_cfg = task["model_cfg"]

    eval_model_name = model_cfg["name"]
    litellm_model = model_cfg["litellm_model"]

    try:
        raw_response = call_model(
            litellm_model=litellm_model,
            prompt=task["prompt"],
            generation_config=generation_config,
            retries=retries,
            sleep_seconds=sleep_seconds,
        )

        model_summary = extract_summary(
            raw_response
        )

        if not model_summary:
            raise RuntimeError(
                "Could not extract non-empty model summary."
            )

        return {
            "trajectory_id": record["trajectory_id"],
            "source_model": record["source_model"],
            "example_id": make_example_id(record),
            "eval_model_name": eval_model_name,
            "eval_litellm_model": litellm_model,
            "model_summary": model_summary,
            "raw_response": raw_response,
            "trajectory_text_path": task["trajectory_text_path"],
            "status": "OK",
        }

    except Exception as e:
        return {
            "trajectory_id": record["trajectory_id"],
            "source_model": record["source_model"],
            "example_id": make_example_id(record),
            "eval_model_name": eval_model_name,
            "eval_litellm_model": litellm_model,
            "model_summary": None,
            "trajectory_text_path": task["trajectory_text_path"],
            "status": "ERROR",
            "error": str(e),
        }


def merge_gold_and_model_summaries(
    gold_records: list[dict[str, Any]],
    summary_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    summary_index = {}

    for summary in summary_records:
        key = (
            summary["trajectory_id"],
            summary["source_model"],
            summary["eval_model_name"],
        )

        summary_index[key] = summary

    eval_model_names = sorted(
        {
            summary["eval_model_name"]
            for summary in summary_records
        }
    )

    merged = []

    for gold_record in gold_records:
        for eval_model_name in eval_model_names:
            key = (
                gold_record["trajectory_id"],
                gold_record["source_model"],
                eval_model_name,
            )

            summary = summary_index.get(key)

            if summary is None:
                merged.append(
                    {
                        **gold_record,
                        "eval_model_name": eval_model_name,
                        "eval_litellm_model": None,
                        "model_summary": None,
                        "model_summary_status": "MISSING",
                        "model_summary_error": None,
                    }
                )

            else:
                merged.append(
                    {
                        **gold_record,
                        "eval_model_name": summary.get("eval_model_name"),
                        "eval_litellm_model": summary.get("eval_litellm_model"),
                        "model_summary": summary.get("model_summary"),
                        "model_summary_status": summary.get("status"),
                        "model_summary_error": summary.get("error"),
                        "model_raw_response": summary.get("raw_response"),
                    }
                )

    return merged


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
        help="Path to gold_final_paired_clean.jsonl",
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
        default="outputs/model_summary_cache.jsonl",
    )

    parser.add_argument(
        "--output",
        default="outputs/model_summaries.jsonl",
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
        "--max-workers",
        type=int,
        default=3,
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
        help="Retry cached error/null-summary records.",
    )

    parser.add_argument(
        "--overwrite-cache",
        action="store_true",
        help="Delete existing cache before running.",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    trajectory_texts_dir = Path(args.trajectory_texts_dir)
    config_path = Path(args.config)
    cache_path = Path(args.cache)
    output_path = Path(args.output)

    config = load_yaml(config_path)

    models = config["models"]
    generation_config = config.get("generation", {})

    gold_records = list(load_jsonl(input_path))

    if args.limit is not None:
        gold_records = gold_records[: args.limit]

    if args.overwrite_cache and cache_path.exists():
        cache_path.unlink()

    existing_cache_records = load_cache_records(
        cache_path
    )

    existing_index = latest_cache_index(
        existing_cache_records,
        retry_errors=args.retry_errors,
    )

    tasks = []

    for record in gold_records:
        for model_cfg in models:
            key = make_cache_key(
                trajectory_id=record["trajectory_id"],
                source_model=record["source_model"],
                eval_model_name=model_cfg["name"],
            )

            if key in existing_index:
                continue

            task = build_task(
                record=record,
                model_cfg=model_cfg,
                trajectory_texts_dir=trajectory_texts_dir,
            )

            if task is not None:
                tasks.append(task)

    print()
    print("=" * 60)
    print("Model summary generation")
    print("=" * 60)
    print(f"Gold records: {len(gold_records)}")
    print(f"Models: {len(models)}")
    print(f"Pending API calls: {len(tasks)}")
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
                    run_task,
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
                desc="Model summaries",
            ):
                cache_record = future.result()

                append_jsonl_threadsafe(
                    cache_path,
                    cache_record,
                    cache_lock,
                )

    final_cache_records = list(
        latest_cache_index(
            load_cache_records(cache_path),
            retry_errors=False,
        ).values()
    )

    merged_records = merge_gold_and_model_summaries(
        gold_records=gold_records,
        summary_records=final_cache_records,
    )

    write_jsonl(
        output_path,
        merged_records,
    )

    ok = sum(
        1
        for record in merged_records
        if record.get("model_summary_status") == "OK"
    )

    error = sum(
        1
        for record in merged_records
        if record.get("model_summary_status") == "ERROR"
    )

    missing = sum(
        1
        for record in merged_records
        if record.get("model_summary_status") == "MISSING"
    )

    by_model = {}

    for model_cfg in models:
        model_name = model_cfg["name"]

        model_records = [
            record
            for record in merged_records
            if record.get("eval_model_name") == model_name
        ]

        by_model[model_name] = {
            "OK": sum(
                1
                for record in model_records
                if record.get("model_summary_status") == "OK"
            ),
            "ERROR": sum(
                1
                for record in model_records
                if record.get("model_summary_status") == "ERROR"
            ),
            "MISSING": sum(
                1
                for record in model_records
                if record.get("model_summary_status") == "MISSING"
            ),
        }

    print()
    print("=" * 60)
    print("Model summary generation completed")
    print("=" * 60)
    print(f"Output file: {output_path}")
    print(f"Records written: {len(merged_records)}")
    print(f"OK: {ok}")
    print(f"ERROR: {error}")
    print(f"MISSING: {missing}")

    print()
    print("By model")
    print("--------")

    for model_name, counts in by_model.items():
        print(
            f"{model_name}: "
            f"OK={counts['OK']} "
            f"ERROR={counts['ERROR']} "
            f"MISSING={counts['MISSING']}"
        )

    print("=" * 60)


if __name__ == "__main__":
    main()