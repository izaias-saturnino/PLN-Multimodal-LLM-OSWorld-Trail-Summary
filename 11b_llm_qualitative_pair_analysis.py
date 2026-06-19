#!/usr/bin/env python3

"""
11b_llm_qualitative_pair_analysis.py

Uses an LLM to produce structured qualitative analysis of paired OSWorld
trajectory summarization cases.

Input:
    outputs/qualitative_pair_success_failure_cases.jsonl
    or
    outputs/qualitative_pair_cases_for_paper.jsonl

Output:
    outputs/llm_qualitative_pair_analysis_cache.jsonl
    outputs/llm_qualitative_pair_analysis.jsonl
    outputs/llm_qualitative_pair_analysis_summary.json
    outputs/llm_qualitative_pair_analysis_report.md

Purpose:
    This is not a primary metric script. It produces qualitative evidence
    for the paper by analyzing paired task cases.

Recommended use:
    - Run on all mixed success/failure pairs.
    - Optionally run on selected cases_for_paper as well.
"""

from __future__ import annotations

import argparse
import json
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import yaml
from litellm import completion
from tqdm import tqdm


JSON_BLOCK_RE = re.compile(
    r"\{.*\}",
    re.DOTALL,
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


def write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
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


def safe_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value)


def truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return text

    if len(text) <= max_chars:
        return text

    half = max_chars // 2

    return (
        text[:half]
        + "\n\n[... TRUNCATED MIDDLE ...]\n\n"
        + text[-half:]
    )


def make_case_id(pair_record: dict[str, Any]) -> str:
    return pair_record["trajectory_id"]


def load_cache_records(cache_path: Path) -> list[dict[str, Any]]:
    if not cache_path.exists():
        return []

    return list(load_jsonl(cache_path))


def latest_cache_index(
    cache_records: list[dict[str, Any]],
    retry_errors: bool,
) -> dict[str, dict[str, Any]]:
    index = {}

    for record in cache_records:
        key = record["trajectory_id"]

        has_analysis = isinstance(
            record.get("analysis_json"),
            dict,
        )
        has_error = "error" in record

        if retry_errors and (has_error or not has_analysis):
            continue

        index[key] = record

    return index


def extract_json_from_response(response_text: str) -> dict[str, Any]:
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    match = JSON_BLOCK_RE.search(response_text)

    if not match:
        raise RuntimeError("Could not find JSON object in response.")

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Could not parse JSON object from response: {e}"
        )


def validate_analysis_json(data: dict[str, Any]):
    required_fields = [
        "case_type",
        "trajectory_contrast",
        "summary_model_comparison",
        "failure_awareness",
        "main_qualitative_findings",
        "recommended_paper_use",
        "paper_ready_takeaway",
    ]

    for field in required_fields:
        if field not in data:
            raise RuntimeError(
                f"Analysis JSON missing required field: {field}"
            )

    if not isinstance(data["main_qualitative_findings"], list):
        raise RuntimeError(
            "main_qualitative_findings must be a list."
        )


def build_model_summary_block(
    source_entry: dict[str, Any],
) -> str:
    blocks = []

    eval_models = source_entry.get("eval_models", {})

    for model_name, model_entry in sorted(eval_models.items()):
        block = f"""
Evaluated model: {model_name}

Model summary:
{safe_text(model_entry.get("model_summary"))}

Reference metrics:
- ROUGE-L F1: {model_entry.get("rougeL_f1")}
- BERTScore F1: {model_entry.get("bertscore_f1")}

Judge scores:
- Coverage: {model_entry.get("coverage_score")}
- Factuality: {model_entry.get("factuality_score")}
- Temporal order: {model_entry.get("temporal_order_score")}
- Specificity: {model_entry.get("specificity_score")}
- Procedural usefulness: {model_entry.get("procedural_usefulness_score")}
- Omission severity: {model_entry.get("omission_severity")}
- Hallucination severity: {model_entry.get("hallucination_severity")}

Judge main errors:
{json.dumps(model_entry.get("main_errors"), ensure_ascii=False, indent=2)}
""".strip()

        blocks.append(block)

    return "\n\n".join(blocks)


def build_source_block(
    source_model: str,
    source_entry: dict[str, Any],
    max_summary_chars: int,
) -> str:
    gold_summary = truncate_text(
        safe_text(source_entry.get("gold_summary")),
        max_summary_chars,
    )

    model_summary_block = truncate_text(
        build_model_summary_block(source_entry),
        max_summary_chars * 4,
    )

    return f"""
SOURCE TRAJECTORY: {source_model}

Metadata:
- success_binary: {source_entry.get("success_binary")}
- success_raw: {source_entry.get("success_raw")}
- num_steps: {source_entry.get("num_steps")}

Human gold summary:
{gold_summary}

Evaluated model summaries and scores:
{model_summary_block}
""".strip()


def build_prompt(
    pair_record: dict[str, Any],
    max_summary_chars: int,
) -> str:
    source_blocks = []

    for source_model, source_entry in pair_record["sources"].items():
        source_blocks.append(
            build_source_block(
                source_model=source_model,
                source_entry=source_entry,
                max_summary_chars=max_summary_chars,
            )
        )

    return f"""
You are writing a qualitative analysis for a research paper about summarizing computer-use agent trajectories.

You are given a paired OSWorld task case. The task instruction is the same, but there are two trajectories from different source agents.

Your job is to analyze what this paired case shows about trajectory summarization quality.

Focus on:
1. How the two source trajectories differ.
2. Whether the difference is related to success, failure, partial completion, or unknown outcome.
3. Whether evaluated model summaries preserve important differences between the paired trajectories.
4. Whether any evaluated model smooths over failure, omits important procedural details, or abstracts away concrete evidence.
5. Whether the case is useful for the paper and how it should be used.

Use the provided human gold summaries, model summaries, automatic metrics, and judge annotations.
Do not invent details not present in the case data.
Do not overstate conclusions from a single case.
Be objective and concise, but describe substantive mistakes and why they matter.

Return only valid JSON. Do not include markdown or commentary outside JSON.

Use exactly this JSON structure:

{{
  "case_type": "mixed_success_failure",
  "trajectory_contrast": {{
    "brief_description": "What differs between the paired trajectories.",
    "success_failure_interpretation": "How the success/failure statuses relate to the observed behaviors.",
    "important_procedural_difference": "The main procedural difference a summarizer should preserve."
  }},
  "summary_model_comparison": {{
    "gpt_5_5": {{
      "strengths": [],
      "weaknesses": [],
      "failure_awareness": "good|partial|poor|not_applicable",
      "specificity_assessment": "good|partial|poor",
      "overall_assessment": "Brief assessment."
    }},
    "claude_sonnet_4_6": {{
      "strengths": [],
      "weaknesses": [],
      "failure_awareness": "good|partial|poor|not_applicable",
      "specificity_assessment": "good|partial|poor",
      "overall_assessment": "Brief assessment."
    }}
  }},
  "failure_awareness": {{
    "which_model_better_preserved_failure": "gpt_5_5|claude_sonnet_4_6|tie|not_applicable",
    "explanation": "Explain whether the summaries correctly represented failure or partial completion."
  }},
  "main_qualitative_findings": [
    {{
      "finding": "Concise qualitative finding.",
      "evidence": "Specific evidence from the paired summaries or scores.",
      "importance": "Why this matters for trajectory summarization."
    }}
  ],
  "recommended_paper_use": "high|medium|low",
  "paper_ready_takeaway": "One or two sentences that could be adapted into the paper."
}}

Task-level metadata:
- trajectory_id: {pair_record.get("trajectory_id")}
- domain: {pair_record.get("domain")}
- pair_outcome: {pair_record.get("pair_outcome")}
- success_pattern: {pair_record.get("success_pattern")}

Task instruction:
{pair_record.get("instruction")}

Paired case data:
{chr(10).join(source_blocks)}
""".strip()


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
        "max_tokens": generation_config.get("max_tokens", 6000),
    }

    temperature = generation_config.get("temperature", None)
    top_p = generation_config.get("top_p", None)

    openai_default_sampling_only_models = (
        litellm_model.startswith("openai/gpt-5")
        or litellm_model.startswith("openai/o")
    )

    if openai_default_sampling_only_models:
        return kwargs

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
        f"LiteLLM qualitative analysis failed after "
        f"{retries + 1} attempts: {last_error}"
    )


def run_task(
    pair_record: dict[str, Any],
    analyst_name: str,
    analyst_litellm_model: str,
    generation_config: dict[str, Any],
    retries: int,
    sleep_seconds: float,
    max_summary_chars: int,
) -> dict[str, Any]:
    trajectory_id = pair_record["trajectory_id"]

    try:
        prompt = build_prompt(
            pair_record=pair_record,
            max_summary_chars=max_summary_chars,
        )

        raw_response = call_model(
            litellm_model=analyst_litellm_model,
            prompt=prompt,
            generation_config=generation_config,
            retries=retries,
            sleep_seconds=sleep_seconds,
        )

        analysis_json = extract_json_from_response(raw_response)
        validate_analysis_json(analysis_json)

        return {
            "trajectory_id": trajectory_id,
            "domain": pair_record.get("domain"),
            "pair_outcome": pair_record.get("pair_outcome"),
            "success_pattern": pair_record.get("success_pattern"),
            "analyst_name": analyst_name,
            "analyst_litellm_model": analyst_litellm_model,
            "analysis_json": analysis_json,
            "raw_response": raw_response,
            "status": "OK",
        }

    except Exception as e:
        return {
            "trajectory_id": trajectory_id,
            "domain": pair_record.get("domain"),
            "pair_outcome": pair_record.get("pair_outcome"),
            "success_pattern": pair_record.get("success_pattern"),
            "analyst_name": analyst_name,
            "analyst_litellm_model": analyst_litellm_model,
            "analysis_json": None,
            "raw_response": None,
            "status": "ERROR",
            "error": str(e),
        }


def summarize_results(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    ok_records = [
        record
        for record in records
        if record.get("status") == "OK"
    ]

    paper_use_counter = Counter()
    case_type_counter = Counter()
    better_failure_counter = Counter()

    for record in ok_records:
        analysis = record["analysis_json"]

        paper_use_counter[analysis.get("recommended_paper_use")] += 1
        case_type_counter[analysis.get("case_type")] += 1

        failure = analysis.get("failure_awareness", {})

        if isinstance(failure, dict):
            better_failure_counter[
                failure.get("which_model_better_preserved_failure")
            ] += 1

    return {
        "num_records": len(records),
        "num_ok": len(ok_records),
        "num_error": len(records) - len(ok_records),
        "recommended_paper_use_counts": dict(
            sorted(paper_use_counter.items())
        ),
        "case_type_counts": dict(
            sorted(case_type_counter.items())
        ),
        "better_failure_awareness_counts": dict(
            sorted(better_failure_counter.items())
        ),
    }


def write_markdown_report(
    records: list[dict[str, Any]],
    path: Path,
):
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("# LLM Qualitative Pair Analysis")
    lines.append("")

    ok_records = [
        record
        for record in records
        if record.get("status") == "OK"
    ]

    def sort_key(record):
        analysis = record.get("analysis_json", {})
        use = analysis.get("recommended_paper_use")

        rank = {
            "high": 0,
            "medium": 1,
            "low": 2,
        }.get(use, 3)

        return (
            rank,
            record.get("domain") or "",
            record.get("trajectory_id") or "",
        )

    for record in sorted(ok_records, key=sort_key):
        analysis = record["analysis_json"]

        lines.append(f"## {record['trajectory_id']}")
        lines.append("")
        lines.append(f"- Domain: `{record.get('domain')}`")
        lines.append(f"- Pair outcome: `{record.get('pair_outcome')}`")
        lines.append(
            f"- Recommended paper use: "
            f"`{analysis.get('recommended_paper_use')}`"
        )
        lines.append("")

        lines.append("### Paper-ready takeaway")
        lines.append("")
        lines.append(
            safe_text(analysis.get("paper_ready_takeaway"))
        )
        lines.append("")

        contrast = analysis.get("trajectory_contrast", {})
        if isinstance(contrast, dict):
            lines.append("### Trajectory contrast")
            lines.append("")
            lines.append(
                safe_text(contrast.get("brief_description"))
            )
            lines.append("")
            lines.append(
                safe_text(
                    contrast.get("success_failure_interpretation")
                )
            )
            lines.append("")

        lines.append("### Main qualitative findings")
        lines.append("")

        findings = analysis.get("main_qualitative_findings", [])

        if isinstance(findings, list):
            for finding in findings:
                if not isinstance(finding, dict):
                    continue

                lines.append(
                    f"- **Finding:** {safe_text(finding.get('finding'))}"
                )
                lines.append(
                    f"  - Evidence: {safe_text(finding.get('evidence'))}"
                )
                lines.append(
                    f"  - Importance: {safe_text(finding.get('importance'))}"
                )

        lines.append("")

    path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
        help=(
            "Path to qualitative pair cases JSONL, e.g. "
            "qualitative_pair_success_failure_cases.jsonl or "
            "qualitative_pair_cases_for_paper.jsonl"
        ),
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Path to qualitative_analysis.yaml",
    )

    parser.add_argument(
        "--cache",
        default="outputs/llm_qualitative_pair_analysis_cache.jsonl",
    )

    parser.add_argument(
        "--output",
        default="outputs/llm_qualitative_pair_analysis.jsonl",
    )

    parser.add_argument(
        "--summary-output",
        default="outputs/llm_qualitative_pair_analysis_summary.json",
    )

    parser.add_argument(
        "--report-output",
        default="outputs/llm_qualitative_pair_analysis_report.md",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--retries",
        type=int,
        default=2,
    )

    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=10.0,
    )

    parser.add_argument(
        "--retry-errors",
        action="store_true",
    )

    parser.add_argument(
        "--overwrite-cache",
        action="store_true",
    )

    parser.add_argument(
        "--max-summary-chars",
        type=int,
        default=6000,
        help=(
            "Maximum characters kept from each gold/model summary block "
            "inside the qualitative analysis prompt."
        ),
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    config_path = Path(args.config)
    cache_path = Path(args.cache)
    output_path = Path(args.output)
    summary_output_path = Path(args.summary_output)
    report_output_path = Path(args.report_output)

    config = load_yaml(config_path)
    analyst_cfg = config["analyst"]
    analyst_name = analyst_cfg["name"]
    analyst_litellm_model = analyst_cfg["litellm_model"]
    generation_config = config.get("generation", {})

    pair_records = list(load_jsonl(input_path))

    if args.limit is not None:
        pair_records = pair_records[: args.limit]

    if args.overwrite_cache and cache_path.exists():
        cache_path.unlink()

    existing_cache_records = load_cache_records(cache_path)

    existing_index = latest_cache_index(
        existing_cache_records,
        retry_errors=args.retry_errors,
    )

    tasks = []

    for pair_record in pair_records:
        key = make_case_id(pair_record)

        if key in existing_index:
            continue

        tasks.append(pair_record)

    print()
    print("=" * 60)
    print("LLM qualitative pair analysis")
    print("=" * 60)
    print(f"Input cases: {len(pair_records)}")
    print(f"Pending API calls: {len(tasks)}")
    print(f"Analyst: {analyst_name}")
    print(f"Analyst model: {analyst_litellm_model}")
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
                    pair_record,
                    analyst_name,
                    analyst_litellm_model,
                    generation_config,
                    args.retries,
                    args.sleep_seconds,
                    args.max_summary_chars,
                )
                for pair_record in tasks
            ]

            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="Qualitative analysis",
            ):
                cache_record = future.result()

                append_jsonl_threadsafe(
                    cache_path,
                    cache_record,
                    cache_lock,
                )

    final_records = list(
        latest_cache_index(
            load_cache_records(cache_path),
            retry_errors=False,
        ).values()
    )

    selected_records = [
        record
        for record in final_records
        if record["trajectory_id"]
        in {
            pair_record["trajectory_id"]
            for pair_record in pair_records
        }
    ]

    write_jsonl(
        output_path,
        selected_records,
    )

    summary = summarize_results(selected_records)

    write_json(
        summary_output_path,
        summary,
    )

    write_markdown_report(
        selected_records,
        report_output_path,
    )

    print()
    print("=" * 60)
    print("LLM qualitative pair analysis completed")
    print("=" * 60)
    print(f"Output: {output_path}")
    print(f"Summary: {summary_output_path}")
    print(f"Report: {report_output_path}")
    print(f"OK: {summary['num_ok']}")
    print(f"ERROR: {summary['num_error']}")

    print()
    print("Recommended paper use")
    print("---------------------")

    for label, count in summary["recommended_paper_use_counts"].items():
        print(f"{label}: {count}")

    print()
    print("Better failure awareness")
    print("------------------------")

    for label, count in summary["better_failure_awareness_counts"].items():
        print(f"{label}: {count}")

    print("=" * 60)


if __name__ == "__main__":
    main()