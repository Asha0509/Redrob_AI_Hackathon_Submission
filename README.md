# Redrob AI Hackathon Submission

An explainable, deterministic candidate-ranking system built for the **India Runs Data & AI Challenge / Redrob AI Hackathon**.

The project ranks a large pool of candidate profiles against a supplied job description and produces a challenge-compliant top-100 CSV. Instead of relying on raw keyword counts, it combines skills, career history, title alignment, experience, platform activity, location, education, and evidence-based penalties into one auditable score.

## Table of contents

- [Problem statement](#problem-statement)
- [Challenge alignment](#challenge-alignment)
- [Solution overview](#solution-overview)
- [How the ranking works](#how-the-ranking-works)
- [Scoring formula](#scoring-formula)
- [Repository structure](#repository-structure)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Output format](#output-format)
- [Validation and testing](#validation-and-testing)
- [Evaluation utilities](#evaluation-utilities)
- [Design decisions](#design-decisions)
- [Limitations and future improvements](#limitations-and-future-improvements)
- [Privacy and responsible use](#privacy-and-responsible-use)

## Problem statement

Recruiters must find the right people in enormous talent pools, but traditional keyword filters often miss hidden gems whose experience, intent, and behavioral signals are buried in profile noise. This project addresses the challenge of building an intelligent ranking engine that moves beyond surface-level matching and turns structured candidate data into a precise, actionable shortlist.

The core objective is a robust, workable proof of concept that does not merely filter candidates—it ranks them by predicted relevance. The system must:

1. understand complex and nuanced job descriptions;
2. identify contextual and semantic fit beyond keyword overlap;
3. combine profile attributes, career metadata, and activity signals;
4. reduce obvious false positives and keyword stuffing;
5. explain why each candidate was selected;
6. produce a fast, valid, and reproducible ranked shortlist.

## Challenge alignment

The implementation maps directly to the three capabilities requested in the problem statement.

| Challenge objective | How this submission addresses it | Evidence |
|---|---|---|
| **Deep Job Understanding** | Parses the supplied DOCX, normalizes domain phrases, detects seniority, and builds must-have, nice-to-have, and negative concept groups | `build_job_profile()` and `_job_profile_from_text()` in `rank.py` |
| **Contextual Relevance** | Combines alias-aware skill depth, applied career evidence, title fit, experience fit, and skill-history synergy instead of counting isolated words | `score_candidate()` and the feature-scoring functions in `rank.py` |
| **Signal Integration** | Uses profile data, career history, skills, education, location, availability, responsiveness, activity, recruiter interest, and verification signals | `_signal_score()`, `_location_score()`, and `_education_score()` in `rank.py` |
| **Accurate Shortlist** | Scores every candidate, applies bounded false-positive penalties, sorts deterministically, and returns the best 100 profiles | `rank_candidates()` in `rank.py` |
| **Explainable Results** | Writes concise evidence and weighted feature contributions for every selected candidate | `make_reasoning()` and `submission_enhanced.csv` |
| **Workable POC** | Runs fully offline with the Python standard library and includes validation, tests, and evaluation utilities | `validate_submission.py`, `tests/test_rank.py`, and `evaluate.py` |

### Submission checklist

| Required deliverable | Included | Location |
|---|:---:|---|
| **The Code** — complete, organized implementation | Yes | `rank.py`, `evaluate.py`, validator, and tests |
| **The Blueprint** — methodology, technical choices, and architecture | Yes | This README |
| **The Results** — ranked output in the predefined format | Yes | `submission_enhanced.csv` |

This repository therefore contains all three requested artifacts: the ranking engine, its technical blueprint, and the generated candidate shortlist.

## Solution overview

The ranker is an offline Python pipeline with no third-party runtime dependencies.

```text
Job description (.docx) ──> job-profile extraction ───────────┐
                                                              │
Candidate profiles (.jsonl) ─> feature extraction ─> scoring ├─> sorting
                                                              │
                                   penalties + tie-breaking ──┘
                                                                    │
                                                                    v
                                                     top-100 submission CSV
```

For every candidate, the system:

- normalizes profile, skill, career, education, and platform text;
- measures role-specific skill depth using proficiency, endorsements, and duration;
- searches employment history for relevant applied work;
- scores current and historical title alignment;
- measures experience fit around the target seniority;
- incorporates engagement and availability signals;
- adds location, relocation, and education signals;
- subtracts penalties for weakly supported or mismatched profiles;
- creates a short, human-readable explanation;
- sorts by score, with `candidate_id` as the deterministic tie-breaker.

## How the ranking works

### 1. Job understanding

`rank.py` reads the Office Open XML content of `job_description.docx` using Python's standard library. It normalizes phrases such as “machine learning,” “learning to rank,” and “vector database,” then identifies:

- seniority indicators;
- search, retrieval, ranking, embeddings, production AI, LLM, and recommendation domains;
- must-have concepts;
- nice-to-have concepts;
- negative or weak-fit concepts.

### 2. Skill match

Skills are matched through aliases rather than a single exact spelling. For example, the vector-database signal recognizes technologies such as FAISS, Milvus, Pinecone, Qdrant, Weaviate, Elasticsearch, and OpenSearch.

Match strength also considers:

- stated proficiency;
- months of experience;
- endorsement count;
- whether the skill is must-have or nice-to-have.

### 3. Career-history fit

The ranker looks for evidence that relevant skills were used in actual roles. Search, ranking, retrieval, evaluation, deployment, serving, and production language contribute more than an isolated skill label.

### 4. Title and experience fit

Titles such as AI Engineer, ML Engineer, Search Engineer, Ranking Engineer, Retrieval Engineer, and Data Scientist receive role-specific fit values. Years of experience are scored around the target senior individual-contributor range rather than using a simple “more is always better” rule.

### 5. Redrob platform signals

The behavioral component combines:

- profile completeness;
- recruiter response rate;
- interview completion rate;
- GitHub activity;
- verified contact and LinkedIn status;
- open-to-work status;
- recent activity;
- recruiter search appearances and saves;
- notice period;
- application volume;
- historical offer acceptance.

These signals are supporting evidence, not a replacement for technical fit.

### 6. Location and education

Location scoring accounts for the job's India location preferences and relocation willingness. Education contributes a deliberately small portion of the final score so that demonstrated skills and work history remain dominant.

### 7. False-positive penalties

The ranker applies bounded penalties for:

- research-heavy profiles without production evidence;
- consulting-only histories without product or platform evidence;
- buzzword-heavy profiles without applied retrieval/ranking evidence;
- clearly mismatched current titles without relevant history;
- missing GitHub linkage, as a small signal only.

## Scoring formula

```text
base_score =
    0.31 × skill_match
  + 0.22 × career_history_fit
  + 0.16 × title_fit
  + 0.09 × experience_fit
  + 0.08 × platform_signals
  + 0.05 × location_fit
  + 0.04 × education
  + 0.05 × skill_history_synergy

final_score = clamp(base_score - penalties, 0.0, 1.0)
```

| Signal | Weight | Purpose |
|---|---:|---|
| Skill match | 31% | Measures required and preferred technical capability |
| Career-history fit | 22% | Finds evidence of relevant applied work |
| Title fit | 16% | Measures alignment with the target role |
| Experience fit | 9% | Rewards the intended seniority range |
| Platform signals | 8% | Adds activity, responsiveness, and availability evidence |
| Location fit | 5% | Reflects location and relocation compatibility |
| Education | 4% | Adds a small educational signal |
| Skill-history synergy | 5% | Rewards profiles strong in both claims and work evidence |

Scores are sorted in descending order. Exact ties are resolved by ascending `candidate_id`, making repeated runs deterministic.

## Repository structure

```text
.
├── README.md
├── .gitignore
├── evaluate.py
├── submission_enhanced.csv
├── validation_labels.csv
└── [PUB] India_runs_data_and_ai_challenge/
    └── India_runs_data_and_ai_challenge/
        ├── rank.py
        ├── validate_submission.py
        ├── tests/
        │   └── test_rank.py
        ├── candidate_schema.json
        ├── sample_candidates.json
        ├── sample_submission.csv
        ├── submission.csv
        ├── job_description.docx
        ├── redrob_signals_doc.docx
        ├── submission_spec.docx
        ├── submission_metadata_template.yaml
        └── candidates.jsonl        # local challenge dataset; ignored by Git
```

The full `candidates.jsonl` file is approximately 487 MB and exceeds GitHub's normal single-file limit. It is intentionally excluded from version control. Place the challenge-provided file at the path shown above before running the full ranking pipeline.

## Requirements

- Python 3.10 or newer
- No pip installation required
- Enough memory to load the challenge candidate JSONL into memory

The implementation uses only Python standard-library modules, including `argparse`, `csv`, `json`, `math`, `re`, `zipfile`, and `xml.etree.ElementTree`.

## Quick start

Clone the repository:

```bash
git clone https://github.com/Asha0509/Redrob_AI_Hackathon_Submission.git
cd Redrob_AI_Hackathon_Submission
```

Define the challenge directory for shorter commands.

PowerShell:

```powershell
$challenge = ".\[PUB] India_runs_data_and_ai_challenge\India_runs_data_and_ai_challenge"
```

Bash:

```bash
challenge="./[PUB] India_runs_data_and_ai_challenge/India_runs_data_and_ai_challenge"
```

### Run against the sample data

PowerShell:

```powershell
python "$challenge\rank.py" `
  --candidates "$challenge\sample_candidates.json" `
  --job-description "$challenge\job_description.docx" `
  --out sample_ranked.csv `
  --top-k 50
```

Bash:

```bash
python "$challenge/rank.py" \
  --candidates "$challenge/sample_candidates.json" \
  --job-description "$challenge/job_description.docx" \
  --out sample_ranked.csv \
  --top-k 50
```

### Generate the full top-100 submission

First copy the challenge-provided `candidates.jsonl` into the challenge directory. Then run:

PowerShell:

```powershell
python "$challenge\rank.py" `
  --candidates "$challenge\candidates.jsonl" `
  --job-description "$challenge\job_description.docx" `
  --out submission.csv
```

Bash:

```bash
python "$challenge/rank.py" \
  --candidates "$challenge/candidates.jsonl" \
  --job-description "$challenge/job_description.docx" \
  --out submission.csv
```

The default `--top-k` value is 100.

## Output format

The generated CSV contains exactly four columns:

| Column | Meaning |
|---|---|
| `candidate_id` | An anonymized ID in the form `CAND_XXXXXXX` |
| `rank` | Unique integer rank from 1 to 100 |
| `score` | Final relevance score, non-increasing by rank |
| `reasoning` | Concise evidence supporting the ranking |

Example:

```csv
candidate_id,rank,score,reasoning
CAND_0081846,1,0.986824,"Lead AI Engineer (6.7y) | skills:0.31 history:0.22 title:0.16; history: Lead AI Engineer @ Razorpay; skills: embeddings:embeddings, retrieval:information_retrieval, vector_db:qdrant; signals: activity:0.96/0.73/0.94, open_to_work; location: india"
```

`submission_enhanced.csv` contains the final ranked output included with this repository.

> **Final upload filename:** The hackathon specification requires the uploaded
> CSV filename to be your exact registered participant ID followed by `.csv`.
> Before uploading, copy the validated result without editing its contents:
>
> ```powershell
> Copy-Item .\submission_enhanced.csv .\<YOUR_REGISTERED_PARTICIPANT_ID>.csv
> ```
>
> Do not upload it under the development filename `submission_enhanced.csv`
> unless that is literally your registered participant ID.

## Validation and testing

### Validate the final CSV

```powershell
python "$challenge\validate_submission.py" .\submission_enhanced.csv
```

The validator checks:

- UTF-8 CSV format;
- exact header order;
- exactly 100 data rows;
- valid and unique candidate IDs;
- every rank from 1 through 100 exactly once;
- non-increasing score order;
- deterministic candidate-ID ordering for equal scores.

### Run unit tests

```powershell
python -m unittest discover -s "$challenge\tests" -p "test_*.py" -v
```

The current tests verify that:

- a candidate with applied ML/search evidence beats a keyword-stuffing profile;
- tied candidates are ordered deterministically by candidate ID.

## Evaluation utilities

`evaluate.py` provides a lightweight keyword baseline, submission comparison, and labeled ranking metrics.

### Generate a keyword baseline

```powershell
python .\evaluate.py baseline `
  --candidates "$challenge\candidates.jsonl" `
  --job-docx "$challenge\job_description.docx" `
  --job-skills "python,embeddings,retrieval,ranking,vector database" `
  --out baseline_submission.csv
```

### Compare two ranked lists

```powershell
python .\evaluate.py compare `
  --a .\submission_enhanced.csv `
  --b .\baseline_submission.csv `
  --topk 20
```

### Compute labeled metrics

```powershell
python .\evaluate.py metrics `
  --submission .\submission_enhanced.csv `
  --labels .\validation_labels.csv
```

The metric command reports Precision@1/5/10, NDCG@1/5/10, and mean reciprocal rank (MRR). The bundled labels are a small development aid and should not be interpreted as a statistically complete benchmark.

## Design decisions

### Explainability over opaque scoring

Each ranking includes the strongest available evidence. This helps reviewers inspect why a candidate surfaced and spot undesirable behavior quickly.

### Deterministic offline execution

The pipeline has no API calls, model downloads, random seeds, or online dependencies. The same inputs and code produce the same order.

### Evidence depth over keyword volume

Skill labels alone are insufficient. Proficiency, duration, endorsements, career descriptions, and production language help distinguish demonstrated experience from profile stuffing.

### Bounded behavioral influence

Platform activity can help identify responsive candidates, but it receives substantially less weight than skills and career history.

## Limitations and future improvements

The current approach is heuristic and tailored to the supplied role. Useful next steps include:

- deriving all weights and target concepts dynamically from arbitrary job descriptions;
- replacing alias matching with local dense embeddings;
- training a learning-to-rank model from recruiter judgments;
- adding calibration and fairness evaluation across non-sensitive cohorts;
- processing JSONL as a stream or bounded heap to reduce memory usage;
- expanding adversarial tests for keyword stuffing and missing data;
- adding cross-validation around the small labeled set;
- exposing feature-level diagnostics in a small review dashboard.

## Privacy and responsible use

The repository uses anonymized candidate IDs. The full challenge dataset is not committed because of both GitHub size constraints and data-minimization considerations.

This ranker should support human review, not make autonomous hiring decisions. Behavioral, location, education, and availability signals can encode structural bias. In a production setting, they should be legally reviewed, monitored for disparate impact, and made configurable or removable. Protected characteristics must never be inferred or used.

## License and challenge context

Created as a submission for the Redrob / India Runs Data & AI Challenge. Challenge-provided data and documents remain subject to their original terms.
