# Challenge workspace

This directory contains the challenge-provided data specification, job description, sample files, ranking implementation, validator, and tests.

For complete project documentation—including the ranking architecture, scoring formula, setup instructions, validation commands, evaluation utilities, limitations, and responsible-use notes—see the repository's [main README](../../README.md).

## Main commands

From the repository root in PowerShell:

```powershell
$challenge = ".\[PUB] India_runs_data_and_ai_challenge\India_runs_data_and_ai_challenge"

python "$challenge\rank.py" `
  --candidates "$challenge\candidates.jsonl" `
  --job-description "$challenge\job_description.docx" `
  --out submission.csv

python "$challenge\validate_submission.py" .\submission.csv

python -m unittest discover -s "$challenge\tests" -p "test_*.py" -v
```

The full `candidates.jsonl` dataset is intentionally excluded from Git because it exceeds GitHub's normal single-file size limit.

The final portal upload must be renamed to the team's exact registered
participant ID, for example `team_xxx.csv`. Renaming must not change the CSV
contents.
