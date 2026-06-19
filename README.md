# Factual Summarization of Multimodal Agent Trajectories in OSWorld

This repository contains the code and derived artifacts for a project on factual summarization of multimodal agent trajectories derived from OSWorld. The project constructs a paired dataset of OSWorld task executions, creates human-revised gold summaries, and evaluates two language models as trajectory summarizers.

The final dataset used in the paper contains:

- 69 paired OSWorld tasks;
- 138 trajectories;
- one human-revised gold summary per trajectory;
- paired executions from two source agents: Doubao and UI-TARS.

The evaluated summarizers are GPT-5.5 and Claude Sonnet 4.6. The evaluation uses ROUGE-L, BERTScore-F1, an anonymized LLM judge, and qualitative analysis.

## Important data note

Raw OSWorld and OSWorld-Verified trajectories are **not included** in this repository.

The raw trajectory folders, screenshots, result files, runtime logs, and task files are not authored by this repository and should be downloaded separately from the original OSWorld or OSWorld-Verified sources. This repository is intended to contain the project code, derived small outputs, paper tables, and reproduction instructions.

Do not commit raw trajectory folders such as:

```text
doubao-1-5-thinking-vision-pro-250428-100step/
UI-TARS-0717-100step/
````

or other raw OSWorld trajectory directories.

## Repository structure

A suggested repository layout is:

```text
.
├── README.md
├── requirements.txt
├── .gitignore
├── scripts/
│   ├── 01_build_manifest.py
│   ├── 01b_manifest_stats.py
│   ├── 02_extract_trajectory_text.py
│   ├── 03_complexity_screening.py
│   ├── 04_select_balanced_subset.py
│   ├── 05_generate_gold_drafts.py
│   ├── 06_collect_revised_gold.py
│   ├── 06b_clean_gold_pairs.py
│   ├── 07_generate_model_summaries.py
│   ├── 08_compute_reference_metrics.py
│   ├── 09_llm_judge_summaries.py
│   ├── 10_analyze_judge_results.py
│   ├── 11_qualitative_pair_analysis.py
│   ├── 11b_llm_qualitative_pair_analysis.py
│   └── 12_export_paper_tables.py
├── data/
│   ├── raw/
│   │   └── README.md
│   ├── intermediate/
│   └── final/
├── outputs/
│   ├── tables/
│   ├── summaries/
│   ├── metrics/
│   └── qualitative_analysis/
└── paper/
    ├── main.tex
    ├── references.bib
    └── figures/
```

The exact structure can be adjusted. The important point is that `data/raw/` should not contain committed OSWorld trajectory data.

## External data

This project assumes access to OSWorld task definitions and OSWorld-Verified trajectory resources.

Expected raw inputs include:

* task metadata and instructions;
* trajectory files;
* screenshots;
* result files;
* runtime logs;
* execution metadata.

Place the downloaded raw data locally in a directory excluded from version control, for example:

```text
data/raw/
├── doubao-1-5-thinking-vision-pro-250428-100step/
└── UI-TARS-0717-100step/
```

The scripts expect the two source-agent folders to be available locally. If your local directory names differ, update the corresponding script configuration or path arguments.

## Environment setup

Create and activate a Python environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

If `requirements.txt` is not available yet, generate it from the environment used for the project after cleaning unused packages:

```bash
pip freeze > requirements.txt
```

## API keys

Some stages use external model APIs. This project used command-line or shell-provided API credentials rather than a committed `.env` file.

Example:

```bash
export OPENAI_API_KEY="..."
export ANTHROPIC_API_KEY="..."
export GOOGLE_API_KEY="..."
```

Use only the keys required for the stages you run. Do not commit API keys, logs containing keys, local credentials, or private configuration files.

## Pipeline

The project pipeline is organized as numbered scripts. The intended execution order is:

```bash
python scripts/01_build_manifest.py
python scripts/01b_manifest_stats.py
python scripts/02_extract_trajectory_text.py
python scripts/03_complexity_screening.py
python scripts/04_select_balanced_subset.py
python scripts/05_generate_gold_drafts.py
python scripts/06_collect_revised_gold.py
python scripts/06b_clean_gold_pairs.py
python scripts/07_generate_model_summaries.py
python scripts/08_compute_reference_metrics.py
python scripts/09_llm_judge_summaries.py
python scripts/10_analyze_judge_results.py
python scripts/11_qualitative_pair_analysis.py
python scripts/11b_llm_qualitative_pair_analysis.py
python scripts/12_export_paper_tables.py
```

### 1. Manifest construction

`01_build_manifest.py` builds a manifest of available trajectories and aligns trajectory folders with OSWorld task metadata.

`01b_manifest_stats.py` produces initial descriptive statistics for the manifest.

### 2. Trajectory text extraction

`02_extract_trajectory_text.py` converts structured trajectory files into normalized textual representations. The extracted text includes task instruction, domain, step sequence, agent thoughts, and actions. Repetitive or uninformative fields are removed.

Screenshots remain part of the raw OSWorld data but are not used as model input in this project.

### 3. Complexity screening

`03_complexity_screening.py` applies a complexity screening step before gold summary generation. Three models are used as independent screeners:

* Gemini 2.5 Flash;
* GPT-4.1 Mini;
* Claude Haiku.

A trajectory is kept if at least two screeners classify it as complex or uncertain.

### 4. Paired subset selection

`04_select_balanced_subset.py` selects paired tasks. A task is eligible only if it has one Doubao trajectory and one UI-TARS trajectory. The selected subset is balanced with respect to domain and success status where possible.

### 5. Gold summary drafting and revision

`05_generate_gold_drafts.py` generates draft gold summaries using Gemini 2.5 Pro.

`06_collect_revised_gold.py` collects manually revised gold summaries.

`06b_clean_gold_pairs.py` filters the revised summaries and keeps only complete pairs.

The final cleaned paired dataset contains 69 tasks and 138 trajectories.

### 6. Model summary generation

`07_generate_model_summaries.py` generates summaries with the evaluated summarizers:

* GPT-5.5;
* Claude Sonnet 4.6.

The models receive the same normalized trajectory input and prompt. Gold summaries and final success labels are not included in the summarization input.

### 7. Reference-based metrics

`08_compute_reference_metrics.py` computes reference-based metrics by comparing each generated summary with the corresponding human-revised gold summary.

The reported metrics are:

* ROUGE-L;
* BERTScore-F1.

### 8. LLM judge

`09_llm_judge_summaries.py` runs an anonymized LLM judge using Claude Opus 4.6. The judge receives:

* the normalized trajectory;
* the human-revised gold summary;
* two anonymized candidate summaries.

Candidate order is randomized and model names are hidden.

The judge records scores for:

* coverage;
* factuality;
* temporal order;
* specificity;
* procedural usefulness.

It also records omission severity, hallucination severity, main error types, and pairwise preference.

`10_analyze_judge_results.py` aggregates the judge outputs.

### 9. Qualitative analysis

`11_qualitative_pair_analysis.py` performs qualitative case selection and analysis.

`11b_llm_qualitative_pair_analysis.py` supports additional LLM-assisted qualitative analysis. The qualitative analysis is reviewed by the author and is used as interpretive evidence, not as independent ground truth.

### 10. Paper table export

`12_export_paper_tables.py` exports the tables used in the paper.

## Main results

The final paired dataset contains:

* 69 paired tasks;
* 138 trajectories;
* 87 failures;
* 48 successes;
* 3 non-binary or unknown outcomes.

Reference-based metrics favor GPT-5.5:

| Model             | ROUGE-L | BERTScore-F1 |
| ----------------- | ------: | -----------: |
| Claude Sonnet 4.6 |   0.398 |        0.888 |
| GPT-5.5           |   0.472 |        0.908 |

The LLM judge assigns higher scores to Claude Sonnet 4.6 on coverage, temporal order, specificity, and procedural usefulness. GPT-5.5 receives a slightly higher factuality score.

The qualitative analysis suggests that Claude Sonnet 4.6 tends to preserve more concrete procedural details, while GPT-5.5 tends to produce shorter and more conservative summaries. Both models may describe local actions correctly while omitting or understating the final trajectory outcome under a descriptive factual summarization prompt.

## Reproducing the paper tables

After running the full pipeline, export the paper tables with:

```bash
python scripts/12_export_paper_tables.py
```

The generated tables should include:

* dataset construction summary;
* final paired outcome distribution;
* reference-based metrics;
* LLM judge results;
* qualitative findings.

## Files that should not be committed

Before pushing to GitHub, verify that the following are excluded:

```text
data/raw/
**/screenshots/
**/runtime.log
**/traj.jsonl
**/result.*
.env
*.key
*.pem
__pycache__/
.venv/
```

Raw OSWorld and OSWorld-Verified trajectory data should remain outside the repository. Users should download those resources separately and place them in the expected local paths.

## Suggested `.gitignore`

```gitignore
# Python
__pycache__/
*.pyc
.venv/
venv/

# Secrets
.env
*.key
*.pem

# Raw external data
data/raw/
**/screenshots/
**/runtime.log
**/traj.jsonl
**/result.*

# Large local outputs
outputs/raw_model_calls/
outputs/cache/
outputs/tmp/

# LaTeX
*.aux
*.bbl
*.blg
*.log
*.out
*.toc
*.synctex.gz
```

Adjust this list if any derived files need to be committed for grading or reproducibility.

## Paper

The paper source is in `paper/`.

The paper describes:

* the motivation for factual summarization of agent trajectories;
* dataset construction from OSWorld-derived trajectories;
* LLM-assisted gold summary drafting and manual revision;
* reference-based evaluation;
* anonymized LLM judging;
* qualitative analysis;
* limitations and threats to validity.

## Generative AI use

Generative AI tools were used in several stages of the project:

* Gemini 2.5 Pro was used to generate draft gold summaries;
* GPT-5.5 and Claude Sonnet 4.6 were used as evaluated summarizers;
* Claude Opus 4.6 was used as an LLM judge;
* additional AI assistance was used for code development, qualitative analysis organization, brainstorming, and text revision.

All code, summaries, analyses, and written content were reviewed and assumed as the responsibility of the author.

## License and data terms

Add the appropriate license for the code if allowed by the course and by the dependencies used in the project.

This repository does not redistribute raw OSWorld or OSWorld-Verified trajectory data. Users are responsible for obtaining those resources from their original sources and following their licenses or terms of use.

## Citation

If you use this repository, cite the course paper or repository as appropriate:

```bibtex
@misc{saturnino2026trajectory_summarization,
  title = {Factual Summarization of Multimodal Agent Trajectories in OSWorld},
  author = {Saturnino, Izaias},
  year = {2026},
  note = {Course project, Universidade Federal do Rio Grande do Sul}
}
```

```
```
