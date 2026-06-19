#!/usr/bin/env python3

"""
01_build_manifest.py

Builds a unified manifest for OSWorld trajectory summarization.

Expected trajectory structure:

trajectories/
├── model_name/
│   ├── chrome/
│   │   ├── task_id/
│   │   │   ├── traj.jsonl
│   │   │   ├── result.txt
│   │   │   ├── recording.mp4
│   │   │   ├── step_*.png
│   │   │   └── ...

Expected OSWorld structure:

examples/
├── chrome/
│   ├── task_id.json
│   └── ...

Output:
    manifest.jsonl

One JSON object per trajectory.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


MANIFEST_VERSION = "1.0"
TIMESTAMP_FORMAT = "%Y%m%d@%H%M%S"


def read_result(result_path: Path):
    """
    Returns:
    {
        "success_raw": ...,
        "success_binary": ...
    }
    """

    if not result_path.exists():
        return {
            "success_raw": None,
            "success_binary": None,
        }

    try:
        value = result_path.read_text(
            encoding="utf-8"
        ).strip()

        try:
            numeric_value = float(value)

            if numeric_value == 1.0:
                return {
                    "success_raw": numeric_value,
                    "success_binary": True,
                }

            if numeric_value == 0.0:
                return {
                    "success_raw": numeric_value,
                    "success_binary": False,
                }

            return {
                "success_raw": numeric_value,
                "success_binary": None,
            }

        except ValueError:
            return {
                "success_raw": value,
                "success_binary": None,
            }

    except Exception:
        return {
            "success_raw": None,
            "success_binary": None,
        }


def count_screenshots(trajectory_dir: Path) -> int:
    return len(list(trajectory_dir.glob("step_*.png")))


def load_json(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def parse_trail_metadata(trail_file: Path):
    default = {
        "num_steps": None,
        "first_timestamp": None,
        "last_timestamp": None,
        "duration_seconds": None,
        "contains_done_action": False,
        "done_flag": False,
        "final_reward": None,
    }

    if not trail_file.exists():
        return default

    num_steps = 0
    first_timestamp = None
    last_timestamp = None

    contains_done_action = False
    done_flag = False
    final_reward = None

    try:
        with open(trail_file, "r", encoding="utf-8") as f:

            for line in f:
                line = line.strip()

                if not line:
                    continue

                step = json.loads(line)

                num_steps += 1

                timestamp = step.get("action_timestamp")

                if timestamp:
                    if first_timestamp is None:
                        first_timestamp = timestamp

                    last_timestamp = timestamp

                action = step.get("action", "")

                if isinstance(action, str):
                    if action.strip() == "DONE":
                        contains_done_action = True

                done_flag = step.get("done", False)
                final_reward = step.get("reward")

    except Exception as e:
        print(f"[WARNING] Failed to parse trail: {trail_file}")
        print(f"          {e}")
        return default

    duration_seconds = None

    try:
        if first_timestamp and last_timestamp:

            start_dt = datetime.strptime(
                first_timestamp,
                TIMESTAMP_FORMAT,
            )

            end_dt = datetime.strptime(
                last_timestamp,
                TIMESTAMP_FORMAT,
            )

            duration_seconds = int(
                (end_dt - start_dt).total_seconds()
            )

    except Exception:
        pass

    return {
        "num_steps": num_steps,
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
        "duration_seconds": duration_seconds,
        "contains_done_action": contains_done_action,
        "done_flag": done_flag,
        "final_reward": final_reward,
    }


def build_record(
    source_model: str,
    domain: str,
    trajectory_dir: Path,
    task_json_path: Path,
):
    task = load_json(task_json_path)

    if task is None:
        return None

    trajectory_id = trajectory_dir.name

    trail_file = trajectory_dir / "traj.jsonl"
    result_file = trajectory_dir / "result.txt"
    recording_file = trajectory_dir / "recording.mp4"

    trail_metadata = parse_trail_metadata(trail_file)

    result_info = read_result(result_file)

    duration_seconds = trail_metadata["duration_seconds"]
    num_steps = trail_metadata["num_steps"]

    steps_per_minute = None

    if (
        duration_seconds
        and duration_seconds > 0
        and num_steps is not None
    ):
        steps_per_minute = round(
            num_steps / (duration_seconds / 60),
            3,
        )

    record = {
        "manifest_version": MANIFEST_VERSION,

        "trajectory_id": trajectory_id,

        "source_model": source_model,
        "domain": domain,

        "instruction": task.get("instruction"),
        "source_url": task.get("source"),

        "related_apps": task.get("related_apps", []),

        "success_raw": result_info["success_raw"],

        "success_binary": result_info["success_binary"],

        "trajectory_dir": str(
            trajectory_dir.resolve()
        ),

        "num_screenshots": count_screenshots(
            trajectory_dir
        ),

        "steps_per_minute": steps_per_minute,

        **trail_metadata,

        "task_json": str(
            task_json_path.resolve()
        ),

        "trail_file": str(
            trail_file.resolve()
        ),

        "result_file": str(
            result_file.resolve()
        ),

        "recording_file": str(
            recording_file.resolve()
        ),

        "trail_exists": trail_file.exists(),
        "result_exists": result_file.exists(),
        "recording_exists": recording_file.exists(),
    }

    return record


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--trajectories-root",
        required=True,
        help="Root directory containing trajectories.",
    )

    parser.add_argument(
        "--examples-root",
        required=True,
        help="OSWorld examples directory.",
    )

    parser.add_argument(
        "--output",
        default="manifest.jsonl",
        help="Output manifest file.",
    )

    args = parser.parse_args()

    trajectories_root = Path(
        args.trajectories_root
    )

    examples_root = Path(
        args.examples_root
    )

    output_path = Path(
        args.output
    )

    total_records = 0
    missing_tasks = 0

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as fout:

        for model_dir in sorted(
            trajectories_root.iterdir()
        ):

            if not model_dir.is_dir():
                continue

            source_model = model_dir.name

            for domain_dir in sorted(
                model_dir.iterdir()
            ):

                if not domain_dir.is_dir():
                    continue

                domain = domain_dir.name

                for trajectory_dir in sorted(
                    domain_dir.iterdir()
                ):

                    if not trajectory_dir.is_dir():
                        continue

                    trajectory_id = (
                        trajectory_dir.name
                    )

                    task_json_path = (
                        examples_root
                        / domain
                        / f"{trajectory_id}.json"
                    )

                    if not task_json_path.exists():

                        missing_tasks += 1

                        print(
                            "[WARNING] Missing task JSON:"
                        )
                        print(
                            f"          {task_json_path}"
                        )

                        continue

                    record = build_record(
                        source_model=source_model,
                        domain=domain,
                        trajectory_dir=trajectory_dir,
                        task_json_path=task_json_path,
                    )

                    if record is None:
                        continue

                    fout.write(
                        json.dumps(
                            record,
                            ensure_ascii=False,
                        )
                        + "\n"
                    )

                    total_records += 1

    print()
    print("=" * 60)
    print("Manifest generation completed")
    print("=" * 60)
    print(f"Output file: {output_path}")
    print(f"Records: {total_records}")
    print(
        f"Missing task JSONs: {missing_tasks}"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()