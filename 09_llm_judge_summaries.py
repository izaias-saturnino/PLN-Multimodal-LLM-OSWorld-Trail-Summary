#!/usr/bin/env python3

"""
09_llm_judge_summaries.py

Runs blind LLM-as-a-judge evaluation of model-generated trajectory
summaries.

Input:
    outputs/model_summaries.jsonl
    outputs/trajectory_texts/

Output:
    outputs/judge_cache.jsonl
    outputs/judge_results.jsonl
    outputs/judge_results_by_model.jsonl
    outputs/judge_summary.json

Judge sees:
    - Task instruction
    - Sanitized trajectory text
    - Human-revised gold summary
    - Candidate summaries anonymized as Summary A, Summary B, ...

Judge does NOT see:
    - eval model names
    - source agent name
    - success_binary / success_raw
    - hidden model mapping

The hidden mapping is saved only in the output for analysis.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import yaml
from litellm import completion
from tqdm import tqdm


REMOVE_HEADER_LINE_PATTERNS = [
    re.compile(r"^Source Model\s*:.*$", re.IGNORECASE),
    re.compile(r"^Success Binary\s*:.*$", re.IGNORECASE),
    re.compile(r"^Success Raw\s*:.*$", re.IGNORECASE),
]


CANDIDATE_LABELS = [
    "A",
    "B",
    "C",
    "D",
    "E",
]


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


def is_valid_model_summary(record: dict[str, Any]) -> bool:
    if record.get("model_summary_status") != "OK":
        return False

    if not isinstance(record.get("model_summary"), str):
        return False

    if not record["model_summary"].strip():
        return False

    if not isinstance(record.get("gold_summary"), str):
        return False

    if not record["gold_summary"].strip():
        return False

    return True


def group_by_example(
    records: list[dict[str, Any]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped = defaultdict(list)

    for record in records:
        key = (
            record["trajectory_id"],
            record["source_model"],
        )

        grouped[key].append(record)

    return grouped


def make_judge_example_id(
    trajectory_id: str,
    source_model: str,
) -> str:
    return f"{source_model}__{trajectory_id}"


def make_cache_key(
    trajectory_id: str,
    source_model: str,
) -> tuple[str, str]:
    return (
        trajectory_id,
        source_model,
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
        key = make_cache_key(
            record["trajectory_id"],
            record["source_model"],
        )

        has_parsed_judgment = isinstance(
            record.get("judge_json"),
            dict,
        )
        has_error = "error" in record

        if retry_errors and (has_error or not has_parsed_judgment):
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
        raise RuntimeError("Could not find JSON object in judge response.")

    json_text = match.group(0)

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Could not parse JSON object from judge response: {e}"
        )


def validate_score(value: Any, field_name: str, candidate_label: str):
    if not isinstance(value, int):
        raise RuntimeError(
            f"Candidate {candidate_label} field '{field_name}' must be an integer."
        )

    if value < 1 or value > 5:
        raise RuntimeError(
            f"Candidate {candidate_label} field '{field_name}' must be between 1 and 5."
        )


def validate_severity(value: Any, field_name: str, candidate_label: str):
    allowed = {
        "none",
        "minor",
        "major",
        "critical",
    }

    if value not in allowed:
        raise RuntimeError(
            f"Candidate {candidate_label} field '{field_name}' must be one of {sorted(allowed)}."
        )


def validate_main_errors(value: Any, candidate_label: str):
    allowed_error_types = {
        "omission",
        "hallucination",
        "wrong_order",
        "wrong_outcome",
        "wrong_application_or_file",
        "loss_of_specificity",
        "overgeneralization",
        "misleading_framing",
        "other",
    }

    allowed_severities = {
        "minor",
        "major",
        "critical",
    }

    if not isinstance(value, list):
        raise RuntimeError(
            f"Candidate {candidate_label} field 'main_errors' must be a list."
        )

    for idx, error in enumerate(value):
        if not isinstance(error, dict):
            raise RuntimeError(
                f"Candidate {candidate_label} main_errors[{idx}] must be an object."
            )

        required_fields = [
            "error_type",
            "description",
            "why_it_matters",
            "severity",
        ]

        for field in required_fields:
            if field not in error:
                raise RuntimeError(
                    f"Candidate {candidate_label} main_errors[{idx}] missing '{field}'."
                )

        if error["error_type"] not in allowed_error_types:
            raise RuntimeError(
                f"Candidate {candidate_label} main_errors[{idx}] has invalid error_type."
            )

        if error["severity"] not in allowed_severities:
            raise RuntimeError(
                f"Candidate {candidate_label} main_errors[{idx}] has invalid severity."
            )

        if not isinstance(error["description"], str):
            raise RuntimeError(
                f"Candidate {candidate_label} main_errors[{idx}].description must be a string."
            )

        if not isinstance(error["why_it_matters"], str):
            raise RuntimeError(
                f"Candidate {candidate_label} main_errors[{idx}].why_it_matters must be a string."
            )


def validate_judge_json(
    judge_json: dict[str, Any],
    candidate_labels: list[str],
):
    if not isinstance(judge_json, dict):
        raise RuntimeError("Judge output is not a JSON object.")

    if "candidates" not in judge_json:
        raise RuntimeError("Judge JSON missing 'candidates'.")

    if not isinstance(judge_json["candidates"], dict):
        raise RuntimeError("'candidates' must be an object.")

    for label in candidate_labels:
        if label not in judge_json["candidates"]:
            raise RuntimeError(
                f"Judge JSON missing candidate '{label}'."
            )

        candidate = judge_json["candidates"][label]

        required_fields = [
            "coverage_score",
            "factuality_score",
            "temporal_order_score",
            "specificity_score",
            "procedural_usefulness_score",
            "omission_severity",
            "hallucination_severity",
            "main_errors",
        ]

        for field in required_fields:
            if field not in candidate:
                raise RuntimeError(
                    f"Candidate {label} missing field '{field}'."
                )

        score_fields = [
            "coverage_score",
            "factuality_score",
            "temporal_order_score",
            "specificity_score",
            "procedural_usefulness_score",
        ]

        for field in score_fields:
            validate_score(
                candidate[field],
                field,
                label,
            )

        validate_severity(
            candidate["omission_severity"],
            "omission_severity",
            label,
        )

        validate_severity(
            candidate["hallucination_severity"],
            "hallucination_severity",
            label,
        )

        validate_main_errors(
            candidate["main_errors"],
            label,
        )

    if "best_summary" not in judge_json:
        raise RuntimeError("Judge JSON missing 'best_summary'.")

    allowed_best = set(candidate_labels) | {"tie"}

    if judge_json["best_summary"] not in allowed_best:
        raise RuntimeError(
            "best_summary must be one candidate label or 'tie'."
        )

    if "rationale" not in judge_json:
        raise RuntimeError("Judge JSON missing 'rationale'.")

    if not isinstance(judge_json["rationale"], str):
        raise RuntimeError("Judge JSON field 'rationale' must be a string.")

    if "gold_reference_issues" not in judge_json:
        raise RuntimeError("Judge JSON missing 'gold_reference_issues'.")

    if not isinstance(judge_json["gold_reference_issues"], list):
        raise RuntimeError(
            "Judge JSON field 'gold_reference_issues' must be a list."
        )


def build_prompt(
    task_instruction: str,
    sanitized_trajectory_text: str,
    gold_summary: str,
    anonymized_candidates: list[dict[str, str]],
) -> str:
    candidate_blocks = []
    candidate_labels = []

    for item in anonymized_candidates:
        label = item["label"]
        summary = item["summary"]

        candidate_labels.append(label)

        candidate_blocks.append(
            f"Candidate Summary {label}:\n{summary}"
        )

    candidate_label_text = ", ".join(candidate_labels)

    return f"""
You are judging summaries of a computer-use agent trajectory.

You will receive:
1. The task instruction.
2. The actual trajectory evidence.
3. A human-revised reference summary.
4. Several anonymized candidate summaries.

Your job is to evaluate how well each candidate summary describes what the agent actually did.

Use the trajectory as the primary evidence. Use the human reference summary as an additional reference, but do not require exact wording. A candidate can be good even if it phrases events differently from the reference, as long as it is faithful, complete, and procedurally useful.

The trajectory may contain Chinese thoughts and Python automation code. Understand it directly.

Important judging criteria:
- Coverage: Does the candidate include the important actions, decisions, repeated attempts, corrections, application switches, and final outcome?
- Factuality: Does it avoid inventing actions, intentions, corrections, file edits, outcomes, or success claims not supported by the trajectory?
- Temporal order: Does it preserve the order and causal structure of the procedure?
- Specificity: Does it preserve task-relevant details such as applications, file names, cell ranges, URLs, document edits, or visible content?
- Failure awareness: If the agent failed, partially completed the task, or made a subtle mistake, does the summary describe that accurately rather than turning it into a successful ideal solution?
- Procedural usefulness: Could a reader reconstruct the agent's behavior from the summary?

Do not use stylistic preference alone to choose the winner. Prefer the summary that is more faithful, complete, and procedurally useful.

Be objective and concise, but do not be superficial. For every substantive mistake, describe:
1. what the mistake is;
2. why it is a mistake given the trajectory or reference;
3. how severe it is.

Do not list trivial wording differences as errors.

The candidate summaries are anonymized as: {candidate_label_text}.
You do not know which model produced which summary.

Return only valid JSON. Do not include markdown or commentary outside the JSON.

Use exactly this JSON structure:

{{
  "candidates": {{
    "A": {{
      "coverage_score": 1,
      "factuality_score": 1,
      "temporal_order_score": 1,
      "specificity_score": 1,
      "procedural_usefulness_score": 1,
      "omission_severity": "none",
      "hallucination_severity": "none",
      "main_errors": [
        {{
          "error_type": "omission",
          "description": "Concise description of the error.",
          "why_it_matters": "Why this error affects faithfulness, completeness, or procedural usefulness.",
          "severity": "minor"
        }}
      ]
    }}
  }},
  "best_summary": "A",
  "rationale": "Objective comparison of the candidates.",
  "gold_reference_issues": []
}}

Scoring:
- Scores are integers from 1 to 5.
- 5 = excellent.
- 4 = good with minor issues.
- 3 = usable but missing or distorting some important details.
- 2 = poor with major omissions or factual errors.
- 1 = very poor or misleading.

Severity labels:
- "none"
- "minor"
- "major"
- "critical"

Allowed error_type values:
- "omission"
- "hallucination"
- "wrong_order"
- "wrong_outcome"
- "wrong_application_or_file"
- "loss_of_specificity"
- "overgeneralization"
- "misleading_framing"
- "other"

For main_errors:
- Include all substantive errors needed for a useful diagnosis.
- Prefer 1 to 5 errors per candidate.
- Use an empty list if there are no substantive errors.
- Do not include trivial paraphrase differences.

For rationale:
- Explain why the winning summary is better.
- If there is a tie, explain why the differences are not decisive.

For gold_reference_issues:
- Usually use an empty list.
- Only mention issues if the human reference itself appears inconsistent with the trajectory evidence.

For best_summary:
- Use one of the candidate labels or "tie".

Task instruction:
{task_instruction}

Trajectory evidence:
{sanitized_trajectory_text}

Human-revised reference summary:
{gold_summary}

{chr(10).join(candidate_blocks)}
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

    # Anthropic may reject temperature and top_p together for some models.
    # Keep temperature and omit top_p for Anthropic.
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
                raise RuntimeError("Empty judge response.")

            return content

        except Exception as e:
            last_error = e

            if attempt < retries:
                time.sleep(sleep_seconds)

    raise RuntimeError(
        f"LiteLLM judge call failed after {retries + 1} attempts: {last_error}"
    )


def build_task(
    group_records: list[dict[str, Any]],
    trajectory_texts_dir: Path,
    rng: random.Random,
) -> dict[str, Any] | None:
    first = group_records[0]

    trajectory_id = first["trajectory_id"]
    source_model = first["source_model"]

    text_path = trajectory_text_path(
        trajectory_texts_dir,
        first,
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

    valid_records = [
        record
        for record in group_records
        if is_valid_model_summary(record)
    ]

    if len(valid_records) < 2:
        print(
            "[WARNING] Need at least two candidate summaries for judge: "
            f"{trajectory_id} / {source_model}"
        )
        return None

    shuffled = list(valid_records)
    rng.shuffle(shuffled)

    if len(shuffled) > len(CANDIDATE_LABELS):
        raise RuntimeError(
            f"Too many candidate summaries: {len(shuffled)}"
        )

    anonymized_candidates = []
    hidden_model_mapping = {}

    for idx, record in enumerate(shuffled):
        label = CANDIDATE_LABELS[idx]

        anonymized_candidates.append(
            {
                "label": label,
                "summary": record["model_summary"].strip(),
            }
        )

        hidden_model_mapping[label] = {
            "eval_model_name": record["eval_model_name"],
            "eval_litellm_model": record.get("eval_litellm_model"),
        }

    prompt = build_prompt(
        task_instruction=first.get("instruction", ""),
        sanitized_trajectory_text=sanitized_text,
        gold_summary=first["gold_summary"].strip(),
        anonymized_candidates=anonymized_candidates,
    )

    return {
        "trajectory_id": trajectory_id,
        "source_model": source_model,
        "example_id": make_judge_example_id(
            trajectory_id,
            source_model,
        ),
        "domain": first.get("domain"),
        "success_binary": first.get("success_binary"),
        "success_raw": first.get("success_raw"),
        "num_steps": first.get("num_steps"),
        "candidate_labels": [
            item["label"]
            for item in anonymized_candidates
        ],
        "hidden_model_mapping": hidden_model_mapping,
        "prompt": prompt,
        "trajectory_text_path": str(text_path),
    }


def run_task(
    task: dict[str, Any],
    judge_name: str,
    judge_litellm_model: str,
    generation_config: dict[str, Any],
    retries: int,
    sleep_seconds: float,
) -> dict[str, Any]:
    try:
        raw_response = call_model(
            litellm_model=judge_litellm_model,
            prompt=task["prompt"],
            generation_config=generation_config,
            retries=retries,
            sleep_seconds=sleep_seconds,
        )

        judge_json = extract_json_from_response(
            raw_response
        )

        validate_judge_json(
            judge_json,
            task["candidate_labels"],
        )

        return {
            "trajectory_id": task["trajectory_id"],
            "source_model": task["source_model"],
            "example_id": task["example_id"],
            "domain": task["domain"],
            "success_binary": task["success_binary"],
            "success_raw": task["success_raw"],
            "num_steps": task["num_steps"],
            "judge_name": judge_name,
            "judge_litellm_model": judge_litellm_model,
            "candidate_labels": task["candidate_labels"],
            "hidden_model_mapping": task["hidden_model_mapping"],
            "judge_json": judge_json,
            "raw_response": raw_response,
            "trajectory_text_path": task["trajectory_text_path"],
            "status": "OK",
        }

    except Exception as e:
        return {
            "trajectory_id": task["trajectory_id"],
            "source_model": task["source_model"],
            "example_id": task["example_id"],
            "domain": task["domain"],
            "success_binary": task["success_binary"],
            "success_raw": task["success_raw"],
            "num_steps": task["num_steps"],
            "judge_name": judge_name,
            "judge_litellm_model": judge_litellm_model,
            "candidate_labels": task["candidate_labels"],
            "hidden_model_mapping": task["hidden_model_mapping"],
            "judge_json": None,
            "raw_response": None,
            "trajectory_text_path": task["trajectory_text_path"],
            "status": "ERROR",
            "error": str(e),
        }


def explode_judge_results_by_model(
    judge_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []

    for record in judge_records:
        if record.get("status") != "OK":
            continue

        judge_json = record["judge_json"]
        candidates = judge_json["candidates"]
        hidden_mapping = record["hidden_model_mapping"]
        best_summary = judge_json.get("best_summary")

        for label, scores in candidates.items():
            model_info = hidden_mapping[label]
            eval_model_name = model_info["eval_model_name"]

            rows.append(
                {
                    "trajectory_id": record["trajectory_id"],
                    "source_model": record["source_model"],
                    "example_id": record["example_id"],
                    "domain": record["domain"],
                    "success_binary": record["success_binary"],
                    "success_raw": record["success_raw"],
                    "num_steps": record["num_steps"],
                    "judge_name": record["judge_name"],
                    "eval_model_name": eval_model_name,
                    "eval_litellm_model": model_info.get(
                        "eval_litellm_model"
                    ),
                    "candidate_label": label,
                    "coverage_score": scores.get("coverage_score"),
                    "factuality_score": scores.get("factuality_score"),
                    "temporal_order_score": scores.get(
                        "temporal_order_score"
                    ),
                    "specificity_score": scores.get(
                        "specificity_score"
                    ),
                    "procedural_usefulness_score": scores.get(
                        "procedural_usefulness_score"
                    ),
                    "omission_severity": scores.get(
                        "omission_severity"
                    ),
                    "hallucination_severity": scores.get(
                        "hallucination_severity"
                    ),
                    "main_errors": scores.get("main_errors"),
                    "is_best": best_summary == label,
                    "is_tie": best_summary == "tie",
                    "best_summary_label": best_summary,
                    "judge_rationale": judge_json.get("rationale"),
                    "gold_reference_issues": judge_json.get(
                        "gold_reference_issues",
                        [],
                    ),
                }
            )

    return rows


def mean(values: list[float]) -> float | None:
    values = [
        value
        for value in values
        if isinstance(value, (int, float))
    ]

    if not values:
        return None

    return sum(values) / len(values)


def severity_counter(
    rows: list[dict[str, Any]],
    field: str,
) -> dict[str, int]:
    counter = Counter()

    for row in rows:
        counter[row.get(field)] += 1

    return dict(sorted(counter.items()))


def error_type_counter(
    rows: list[dict[str, Any]],
) -> dict[str, int]:
    counter = Counter()

    for row in rows:
        errors = row.get("main_errors")

        if not isinstance(errors, list):
            continue

        for error in errors:
            if isinstance(error, dict):
                counter[error.get("error_type")] += 1

    return dict(sorted(counter.items()))


def error_severity_counter(
    rows: list[dict[str, Any]],
) -> dict[str, int]:
    counter = Counter()

    for row in rows:
        errors = row.get("main_errors")

        if not isinstance(errors, list):
            continue

        for error in errors:
            if isinstance(error, dict):
                counter[error.get("severity")] += 1

    return dict(sorted(counter.items()))


def summarize_by_model(
    exploded_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    grouped = defaultdict(list)

    for row in exploded_rows:
        grouped[row["eval_model_name"]].append(row)

    summary = {}

    score_fields = [
        "coverage_score",
        "factuality_score",
        "temporal_order_score",
        "specificity_score",
        "procedural_usefulness_score",
    ]

    for model_name, rows in sorted(grouped.items()):
        summary[model_name] = {
            "n": len(rows),
            "best_count": sum(
                1
                for row in rows
                if row.get("is_best") is True
            ),
            "tie_count": sum(
                1
                for row in rows
                if row.get("is_tie") is True
            ),
            "mean_scores": {
                field: mean(
                    [
                        row.get(field)
                        for row in rows
                    ]
                )
                for field in score_fields
            },
            "omission_severity_counts": severity_counter(
                rows,
                "omission_severity",
            ),
            "hallucination_severity_counts": severity_counter(
                rows,
                "hallucination_severity",
            ),
            "main_error_type_counts": error_type_counter(
                rows,
            ),
            "main_error_severity_counts": error_severity_counter(
                rows,
            ),
        }

    return summary


def summarize_by_model_and_field(
    exploded_rows: list[dict[str, Any]],
    field: str,
) -> dict[str, Any]:
    grouped = defaultdict(list)

    for row in exploded_rows:
        key = (
            row["eval_model_name"],
            str(row.get(field)),
        )

        grouped[key].append(row)

    score_fields = [
        "coverage_score",
        "factuality_score",
        "temporal_order_score",
        "specificity_score",
        "procedural_usefulness_score",
    ]

    summary = {}

    for (model_name, field_value), rows in sorted(grouped.items()):
        summary_key = f"{model_name} | {field}={field_value}"

        summary[summary_key] = {
            "eval_model_name": model_name,
            field: field_value,
            "n": len(rows),
            "best_count": sum(
                1
                for row in rows
                if row.get("is_best") is True
            ),
            "tie_count": sum(
                1
                for row in rows
                if row.get("is_tie") is True
            ),
            "mean_scores": {
                metric: mean(
                    [
                        row.get(metric)
                        for row in rows
                    ]
                )
                for metric in score_fields
            },
            "main_error_type_counts": error_type_counter(
                rows,
            ),
        }

    return summary


def summarize_pairwise_winners(
    judge_records: list[dict[str, Any]],
) -> dict[str, Any]:
    counter = Counter()

    for record in judge_records:
        if record.get("status") != "OK":
            continue

        judge_json = record["judge_json"]
        best = judge_json.get("best_summary")

        if best == "tie":
            counter["tie"] += 1
            continue

        hidden_mapping = record["hidden_model_mapping"]
        model_name = hidden_mapping[best]["eval_model_name"]
        counter[model_name] += 1

    return dict(sorted(counter.items()))


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
        help="Path to model_summaries.jsonl",
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
        default="outputs/judge_cache.jsonl",
    )

    parser.add_argument(
        "--output",
        default="outputs/judge_results.jsonl",
    )

    parser.add_argument(
        "--exploded-output",
        default="outputs/judge_results_by_model.jsonl",
    )

    parser.add_argument(
        "--summary-output",
        default="outputs/judge_summary.json",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
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
        default=2,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of grouped examples for testing.",
    )

    parser.add_argument(
        "--retry-errors",
        action="store_true",
    )

    parser.add_argument(
        "--overwrite-cache",
        action="store_true",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    trajectory_texts_dir = Path(args.trajectory_texts_dir)
    config_path = Path(args.config)
    cache_path = Path(args.cache)
    output_path = Path(args.output)
    exploded_output_path = Path(args.exploded_output)
    summary_output_path = Path(args.summary_output)

    config = load_yaml(config_path)

    judge_cfg = config["judge"]
    judge_name = judge_cfg["name"]
    judge_litellm_model = judge_cfg["litellm_model"]
    generation_config = config.get("generation", {})

    rng = random.Random(args.seed)

    records = [
        record
        for record in load_jsonl(input_path)
        if is_valid_model_summary(record)
    ]

    grouped = group_by_example(records)

    group_items = list(grouped.items())

    if args.limit is not None:
        group_items = group_items[: args.limit]

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

    skipped_cached = 0

    for (trajectory_id, source_model), group_records in group_items:
        key = make_cache_key(
            trajectory_id,
            source_model,
        )

        if key in existing_index:
            skipped_cached += 1
            continue

        task = build_task(
            group_records=group_records,
            trajectory_texts_dir=trajectory_texts_dir,
            rng=rng,
        )

        if task is not None:
            tasks.append(task)

    print()
    print("=" * 60)
    print("LLM judge")
    print("=" * 60)
    print(f"Valid model-summary records: {len(records)}")
    print(f"Grouped examples: {len(group_items)}")
    print(f"Pending judge calls: {len(tasks)}")
    print(f"Skipped cached examples: {skipped_cached}")
    print(f"Judge: {judge_name}")
    print(f"Judge model: {judge_litellm_model}")
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
                    judge_name,
                    judge_litellm_model,
                    generation_config,
                    args.retries,
                    args.sleep_seconds,
                )
                for task in tasks
            ]

            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="Judge calls",
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

    write_jsonl(
        output_path,
        final_cache_records,
    )

    exploded_rows = explode_judge_results_by_model(
        final_cache_records,
    )

    write_jsonl(
        exploded_output_path,
        exploded_rows,
    )

    ok = sum(
        1
        for record in final_cache_records
        if record.get("status") == "OK"
    )

    error = sum(
        1
        for record in final_cache_records
        if record.get("status") == "ERROR"
    )

    summary = {
        "input_file": str(input_path),
        "judge_results_file": str(output_path),
        "exploded_results_file": str(exploded_output_path),
        "judge_name": judge_name,
        "judge_litellm_model": judge_litellm_model,
        "num_valid_model_summary_records": len(records),
        "num_grouped_examples": len(group_items),
        "num_judge_records": len(final_cache_records),
        "num_judge_ok": ok,
        "num_judge_error": error,
        "pairwise_winners": summarize_pairwise_winners(
            final_cache_records,
        ),
        "by_model": summarize_by_model(
            exploded_rows,
        ),
        "by_model_and_domain": summarize_by_model_and_field(
            exploded_rows,
            "domain",
        ),
        "by_model_and_source_agent": summarize_by_model_and_field(
            exploded_rows,
            "source_model",
        ),
        "by_model_and_success": summarize_by_model_and_field(
            exploded_rows,
            "success_binary",
        ),
    }

    write_json(
        summary_output_path,
        summary,
    )

    print()
    print("=" * 60)
    print("LLM judge completed")
    print("=" * 60)
    print(f"Judge results: {output_path}")
    print(f"Exploded by-model results: {exploded_output_path}")
    print(f"Summary: {summary_output_path}")
    print(f"OK: {ok}")
    print(f"ERROR: {error}")

    print()
    print("Pairwise winners")
    print("----------------")

    for winner, count in summary["pairwise_winners"].items():
        print(f"{winner}: {count}")

    print("=" * 60)


if __name__ == "__main__":
    main()