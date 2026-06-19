#!/usr/bin/env python3

"""
05_generate_gold_drafts.py

Generates draft gold procedural summaries for selected OSWorld
trajectory summarization examples.

Input:
    outputs/selected_paired_balanced_manifest.jsonl
    outputs/trajectory_texts/

Output:
    outputs/gold_draft_cache.jsonl
    outputs/gold_drafts.jsonl
    outputs/gold_drafts_review/*.md

Design:
    - Uses one strong model to generate draft summaries.
    - These drafts are not final gold labels.
    - The human author must review and revise them.
    - The model used here should not be treated as a normal evaluated
      model unless this is explicitly disclosed and separated.
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
            f.write(
                json.dumps(record, ensure_ascii=False)
                + "\n"
            )


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


def make_example_id(record: dict[str, Any]) -> str:
    return (
        f"{record['source_model']}__"
        f"{record['trajectory_id']}"
    )


def safe_filename(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
    text = text.strip("_")

    return text[:180]


def build_prompt(
    record: dict[str, Any],
    trajectory_text: str,
) -> str:
    instruction = record.get("instruction", "")
    source_model = record.get("source_model", "")
    domain = record.get("domain", "")
    success_binary = record.get("success_binary", None)
    success_raw = record.get("success_raw", None)
    num_steps = record.get("num_steps", None)

    return f"""
You are creating a draft reference summary for a benchmark of computer-use agent trajectory summarization.

The input is an execution trajectory from an agent attempting an OSWorld task.

The trajectory may contain Chinese thoughts and Python automation code. Understand the trajectory directly.

Your job is to write a procedural summary of what the agent actually did.

Important rules:
- Summarize the observed behavior, not the ideal solution.
- Do not invent actions that are not supported by the trajectory.
- Include major actions, application switches, decisions, repeated attempts, corrections, mistakes, and the final outcome when visible.
- If the agent failed, summarize the failed behavior accurately rather than rewriting it as a successful solution.
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

Metadata:
Trajectory ID: {record.get("trajectory_id")}
Source model: {source_model}
Domain: {domain}
Task instruction: {instruction}
Success binary: {success_binary}
Success raw: {success_raw}
Number of steps: {num_steps}

Trajectory:
{trajectory_text}
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

    if temperature is not None:
        kwargs["temperature"] = temperature

    # Anthropic may reject temperature and top_p together for some models.
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
    record: dict[str, Any],
) -> tuple[str, str]:
    return (
        record["trajectory_id"],
        record["source_model"],
    )


def load_cache_records(cache_path: Path) -> list[dict[str, Any]]:
    if not cache_path.exists():
        return []

    return list(load_jsonl(cache_path))


def latest_cache_index(
    cache_records: list[dict[str, Any]],
    retry_errors: bool,
) -> dict[tuple[str, str], dict[str, Any]]:
    index = {}

    for record in cache_records:
        key = (
            record["trajectory_id"],
            record["source_model"],
        )

        has_summary = bool(record.get("draft_summary"))
        has_error = "error" in record

        if retry_errors and (has_error or not has_summary):
            continue

        index[key] = record

    return index


def build_task(
    record: dict[str, Any],
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

    prompt = build_prompt(
        record=record,
        trajectory_text=trajectory_text,
    )

    return {
        "record": record,
        "trajectory_text_path": str(text_path),
        "prompt": prompt,
    }


def run_task(
    task: dict[str, Any],
    model_name: str,
    litellm_model: str,
    generation_config: dict[str, Any],
    retries: int,
    sleep_seconds: float,
) -> dict[str, Any]:
    record = task["record"]

    try:
        raw_response = call_model(
            litellm_model=litellm_model,
            prompt=task["prompt"],
            generation_config=generation_config,
            retries=retries,
            sleep_seconds=sleep_seconds,
        )

        draft_summary = extract_summary(
            raw_response
        )

        if not draft_summary:
            raise RuntimeError(
                "Could not extract non-empty draft summary."
            )

        return {
            "trajectory_id": record["trajectory_id"],
            "source_model": record["source_model"],
            "example_id": make_example_id(record),
            "gold_draft_model_name": model_name,
            "gold_draft_litellm_model": litellm_model,
            "draft_summary": draft_summary,
            "raw_response": raw_response,
            "trajectory_text_path": task["trajectory_text_path"],
            "status": "OK",
        }

    except Exception as e:
        return {
            "trajectory_id": record["trajectory_id"],
            "source_model": record["source_model"],
            "example_id": make_example_id(record),
            "gold_draft_model_name": model_name,
            "gold_draft_litellm_model": litellm_model,
            "draft_summary": None,
            "trajectory_text_path": task["trajectory_text_path"],
            "status": "ERROR",
            "error": str(e),
        }


def merge_manifest_and_drafts(
    manifest_records: list[dict[str, Any]],
    draft_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    draft_index = {}

    for draft in draft_records:
        key = (
            draft["trajectory_id"],
            draft["source_model"],
        )

        draft_index[key] = draft

    merged = []

    for record in manifest_records:
        key = (
            record["trajectory_id"],
            record["source_model"],
        )

        draft = draft_index.get(key)

        if draft is None:
            merged.append(
                {
                    **record,
                    "gold_draft_status": "MISSING",
                    "draft_summary": None,
                }
            )

        else:
            merged.append(
                {
                    **record,
                    "gold_draft_status": draft.get("status"),
                    "gold_draft_model_name": draft.get(
                        "gold_draft_model_name"
                    ),
                    "gold_draft_litellm_model": draft.get(
                        "gold_draft_litellm_model"
                    ),
                    "draft_summary": draft.get("draft_summary"),
                    "gold_draft_error": draft.get("error"),
                    "trajectory_text_path": draft.get(
                        "trajectory_text_path"
                    ),
                }
            )

    return merged


def write_review_markdown_files(
    records: list[dict[str, Any]],
    review_dir: Path,
):
    review_dir.mkdir(parents=True, exist_ok=True)

    for record in records:
        example_id = make_example_id(record)

        filename = safe_filename(example_id) + ".md"
        path = review_dir / filename

        draft_summary = record.get("draft_summary") or ""

        content = f"""# Gold Draft Review

## Metadata

- trajectory_id: `{record.get("trajectory_id")}`
- source_model: `{record.get("source_model")}`
- domain: `{record.get("domain")}`
- success_binary: `{record.get("success_binary")}`
- success_raw: `{record.get("success_raw")}`
- num_steps: `{record.get("num_steps")}`
- gold_draft_status: `{record.get("gold_draft_status")}`

## Task Instruction

{record.get("instruction", "")}

## Draft Summary

{draft_summary}

## Human-Revised Gold Summary

<!-- Replace this section with your final human-revised gold summary. -->

{draft_summary}
"""

        path.write_text(
            content,
            encoding="utf-8",
        )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
        help="Path to selected_paired_balanced_manifest.jsonl",
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
        default="outputs/gold_draft_cache.jsonl",
    )

    parser.add_argument(
        "--output",
        default="outputs/gold_drafts.jsonl",
    )

    parser.add_argument(
        "--review-dir",
        default="outputs/gold_drafts_review",
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
    review_dir = Path(args.review_dir)

    config = load_yaml(config_path)

    model_cfg = config["model"]
    model_name = model_cfg["name"]
    litellm_model = model_cfg["litellm_model"]
    generation_config = config.get("generation", {})

    manifest_records = list(load_jsonl(input_path))

    if args.limit is not None:
        manifest_records = manifest_records[: args.limit]

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

    for record in manifest_records:
        key = make_cache_key(record)

        if key in existing_index:
            continue

        task = build_task(
            record=record,
            trajectory_texts_dir=trajectory_texts_dir,
        )

        if task is not None:
            tasks.append(task)

    print()
    print("=" * 60)
    print("Gold draft generation")
    print("=" * 60)
    print(f"Input records: {len(manifest_records)}")
    print(f"Pending API calls: {len(tasks)}")
    print(f"Model name: {model_name}")
    print(f"LiteLLM model: {litellm_model}")
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
                    model_name,
                    litellm_model,
                    generation_config,
                    args.retries,
                    args.sleep_seconds,
                )
                for task in tasks
            ]

            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="Draft generation",
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

    merged_records = merge_manifest_and_drafts(
        manifest_records=manifest_records,
        draft_records=final_cache_records,
    )

    write_jsonl(
        output_path,
        merged_records,
    )

    write_review_markdown_files(
        records=merged_records,
        review_dir=review_dir,
    )

    ok = sum(
        1
        for record in merged_records
        if record.get("gold_draft_status") == "OK"
    )

    error = sum(
        1
        for record in merged_records
        if record.get("gold_draft_status") == "ERROR"
    )

    missing = sum(
        1
        for record in merged_records
        if record.get("gold_draft_status") == "MISSING"
    )

    print()
    print("=" * 60)
    print("Gold draft generation completed")
    print("=" * 60)
    print(f"Output file: {output_path}")
    print(f"Review directory: {review_dir}")
    print(f"Records written: {len(merged_records)}")
    print(f"OK: {ok}")
    print(f"ERROR: {error}")
    print(f"MISSING: {missing}")
    print("=" * 60)


if __name__ == "__main__":
    main()