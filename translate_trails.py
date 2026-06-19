import json
import re
from pathlib import Path

from openai import OpenAI

from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

ROOT_DIR = Path("osworld")
INPUT_NAME = "traj.jsonl"
OUTPUT_NAME = "traj_en.jsonl"

CACHE_FILE = Path("translation_cache.json")

MODEL = "gpt-5"
BATCH_SIZE = 100

client = OpenAI()

# ---------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------

if CACHE_FILE.exists():
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        cache = json.load(f)
else:
    cache = {}

# ---------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------

CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")

# Captures:
# Group 1 = "Thought:" label
# Group 2 = thought content
# Group 3 = end delimiter (next section or closing triple quote)
#
# Example:
#
# Thought:
# 当前页面是...
# '''
#
THOUGHT_RE = re.compile(
    r"(Thought:\s*\n)(.*?)(\n\s*''')",
    re.DOTALL,
)

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def contains_chinese(text: str) -> bool:
    return bool(CHINESE_RE.search(text))


def save_cache():
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def extract_thoughts(record):
    """
    Return all Chinese Thought contents from a record.
    """

    action = record.get("action")

    if not isinstance(action, str):
        return []

    thoughts = []

    for match in THOUGHT_RE.finditer(action):
        thought_text = match.group(2)

        if contains_chinese(thought_text):
            thoughts.append(thought_text)

    return thoughts


def collect_all_unique_thoughts(trail_files):
    """
    Collect unique Chinese Thought blocks across the dataset.
    """

    unique = set()

    for trail_file in trail_files:
        try:
            with open(trail_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()

                    if not line:
                        continue

                    record = json.loads(line)

                    for thought in extract_thoughts(record):
                        unique.add(thought)

        except Exception as e:
            print(f"[ERROR] {trail_file}: {e}")

    return sorted(unique)


def translate_batch(thoughts):
    """
    Returns:
        dict[original_thought] = translated_thought
    """

    try:
        return translate_batch_impl(thoughts)

    except Exception as e:
        print(f"Batch failed ({len(thoughts)} items): {e}")

        if len(thoughts) == 1:
            print("Skipping thought:")
            print(thoughts[0])
            return {}

        mid = len(thoughts) // 2

        left = translate_batch(thoughts[:mid])
        right = translate_batch(thoughts[mid:])

        left.update(right)
        return left

def translate_batch_impl(thoughts):
    payload = [
        {
            "id": str(i),
            "text": thought,
        }
        for i, thought in enumerate(thoughts)
    ]

    response = client.responses.create(
        model=MODEL,
        input=[
            {
                "role": "system",
                "content": (
                    "You are translating OSWorld agent reasoning.\n\n"
                    "Each input contains ONLY the contents that appear "
                    "AFTER a 'Thought:' label.\n\n"
                    "'Thought:' is a label and is NOT part of the text "
                    "being translated.\n\n"
                    "Translate the reasoning into natural English.\n"
                    "Preserve line breaks.\n"
                    "Do not add explanations.\n"
                    "Do not summarize.\n"
                    "Return JSON."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    payload,
                    ensure_ascii=False,
                ),
            },
        ],
    )

    result = json.loads(response.output_text)

    if isinstance(result, dict):
        items = result.get("translations", [])
    elif isinstance(result, list):
        items = result
    else:
        raise RuntimeError(
            f"Unexpected response type: {type(result)}"
        )

    translations = {}

    for item in items:
        translated_text = (
            item.get("translation")
            or item.get("text")
        )

        if translated_text is None:
            continue

        translations[item["id"]] = translated_text

    output = {}

    for i, original in enumerate(thoughts):
        translated = translations.get(str(i))

        if translated is not None:
            output[original] = translated

    return output


def translate_all_missing(
    unique_thoughts,
    max_workers=16,
):
    pending = [
        thought
        for thought in unique_thoughts
        if thought not in cache
    ]

    print(
        f"Found {len(unique_thoughts)} unique thoughts "
        f"({len(pending)} need translation)"
    )

    batches = [
        pending[i:i + BATCH_SIZE]
        for i in range(0, len(pending), BATCH_SIZE)
    ]

    print(
        f"Submitting {len(batches)} batches "
        f"with {max_workers} workers"
    )

    completed = 0

    with ThreadPoolExecutor(
        max_workers=max_workers
    ) as executor:

        futures = {
            executor.submit(
                translate_batch,
                batch,
            ): idx
            for idx, batch in enumerate(batches)
        }

        for future in as_completed(futures):
            idx = futures[future]

            try:
                results = future.result()

                cache.update(results)

                completed += 1

                if completed % 10 == 0:
                    save_cache()

                print(
                    f"Completed batch "
                    f"{idx + 1}/{len(batches)} "
                    f"({len(results)} translations)"
                )

            except Exception as e:
                print(
                    f"Batch {idx + 1} failed: {e}"
                )

    save_cache()


def translate_record(record):
    """
    Replace Thought contents with translated versions.
    """

    action = record.get("action")

    if not isinstance(action, str):
        return record

    def repl(match):
        thought_text = match.group(2)

        if not contains_chinese(thought_text):
            return match.group(0)

        translated = cache.get(thought_text)

        if translated is None:
            return match.group(0)

        return (
            match.group(1)
            + translated
            + match.group(3)
        )

    new_record = dict(record)

    new_record["action"] = THOUGHT_RE.sub(
        repl,
        action,
    )

    return new_record


def write_translated_file(trail_file):
    output_path = trail_file.with_name(OUTPUT_NAME)

    with open(trail_file, "r", encoding="utf-8") as fin, \
         open(output_path, "w", encoding="utf-8") as fout:

        for line in fin:
            line = line.strip()

            if not line:
                continue

            record = json.loads(line)

            translated_record = translate_record(record)

            fout.write(
                json.dumps(
                    translated_record,
                    ensure_ascii=False,
                )
                + "\n"
            )

    print(f"Wrote {output_path}")


def main():
    trail_files = sorted(ROOT_DIR.rglob(INPUT_NAME))

    print(f"Found {len(trail_files)} {INPUT_NAME} files")

    # Pass 1: Collect all unique Chinese thoughts
    unique_thoughts = collect_all_unique_thoughts(
        trail_files
    )

    # Pass 2: Translate uncached thoughts
    translate_all_missing(
        unique_thoughts,
        max_workers=16,
    )

    # Pass 3: Write translated files
    for trail_file in trail_files:
        write_translated_file(trail_file)

    save_cache()

    print(
        f"Done. Cache contains "
        f"{len(cache)} translated thoughts."
    )


if __name__ == "__main__":
    main()