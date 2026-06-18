#!/usr/bin/env python3
"""Evaluation harness and simple keyword baseline for the India runs ranker.

Commands:
- baseline: generate a baseline `baseline_submission.csv` (top-100)
- compare: compare two submission CSVs and show overlap/top-10 diffs
- metrics: compute Precision@k, NDCG@k, MRR if a labels file is provided

Built with Python stdlib only so it runs offline.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import os
import re
import sys
from zipfile import ZipFile


def load_candidates(path):
    with open(path, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def extract_docx_text(path: str) -> str:
    if not os.path.exists(path):
        return ""
    try:
        with ZipFile(path) as z:
            name = 'word/document.xml'
            if name not in z.namelist():
                return ''
            data = z.read(name).decode('utf-8', errors='ignore')
            # strip tags but keep word boundaries
            text = re.sub(r'<(/?w:r.*?)>', ' ', data)
            text = re.sub(r'<.*?>', ' ', text)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()
    except Exception:
        return ''


def baseline_score(candidate: dict, job_text: str, job_skills: list[str]) -> float:
    score = 0.0
    raw_skills = candidate.get('skills', []) or []
    cand_skills = set()
    for sk in raw_skills:
        if isinstance(sk, str):
            cand_skills.add(sk.lower())
        elif isinstance(sk, dict):
            # common key names used in JSONL skill objects
            for key in ('name', 'skill', 'text'):
                if key in sk and isinstance(sk[key], str):
                    cand_skills.add(sk[key].lower())
                    break
            else:
                cand_skills.add(str(sk).lower())
    # match explicit skills
    for s in job_skills:
        if s.lower() in cand_skills:
            score += 1.0
    # title keyword overlap (short heuristics)
    title = (candidate.get('title') or '').lower()
    for tok in re.findall(r"\w+", job_text.lower()):
        if len(tok) <= 3:
            continue
        if tok in title:
            score += 0.15
    # small boost for years experience if present
    yrs = candidate.get('years_experience') or candidate.get('years') or 0
    try:
        yrs = float(yrs)
    except Exception:
        yrs = 0.0
    if yrs >= 5:
        score += 0.2
    return score


def generate_baseline_submission(candidates_path: str, out_path: str, job_docx: str | None = None, job_skills: list[str] | None = None, topk: int = 100):
    job_text = ''
    if job_docx:
        job_text = extract_docx_text(job_docx)
    job_skills = job_skills or []

    scored = []
    for c in load_candidates(candidates_path):
        s = baseline_score(c, job_text, job_skills)
        scored.append((c.get('candidate_id'), s, c))

    # sort by score desc, then candidate_id for deterministic tie-break
    scored.sort(key=lambda x: (-x[1], x[0] or ''))

    top = scored[:topk]
    # assign monotonic non-increasing scores derived from rank (ensures validator accepts)
    rows = []
    for i, (cid, raw_score, c) in enumerate(top, start=1):
        score = 1.0 - (i - 1) * 1e-6
        reasoning = f"baseline:raw={raw_score:.3f}" if raw_score is not None else "baseline"
        rows.append((cid, i, f"{score:.6f}", reasoning))

    with open(out_path, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.writer(fh)
        writer.writerow(['candidate_id', 'rank', 'score', 'reasoning'])
        for cid, rank, score, reasoning in rows:
            writer.writerow([cid, rank, score, reasoning])

    print(f'Wrote baseline top-{topk} to {out_path}')


def read_submission(path: str) -> list[str]:
    ids = []
    with open(path, 'r', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            ids.append(row['candidate_id'])
    return ids


def compare_submissions(a_path: str, b_path: str, topk: int = 10):
    a = read_submission(a_path)
    b = read_submission(b_path)
    set_a = set(a[:topk])
    set_b = set(b[:topk])
    overlap = len(set_a & set_b)
    print(f'Top-{topk} overlap: {overlap}/{topk} ({overlap/topk:.2%})')
    print('\nTop differences (A not in B):')
    for cid in a[:topk]:
        if cid not in set_b:
            print('-', cid)
    print('\nTop differences (B not in A):')
    for cid in b[:topk]:
        if cid not in set_a:
            print('-', cid)


def read_labels(path: str) -> dict:
    # labels CSV: candidate_id,relevance (int, higher is more relevant)
    d = {}
    with open(path, 'r', encoding='utf-8') as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row:
                continue
            cid = row[0]
            try:
                rel = float(row[1])
            except Exception:
                rel = 0.0
            d[cid] = rel
    return d


def precision_at_k(pred, labels, k):
    pred_k = pred[:k]
    rels = [1 if labels.get(cid, 0) > 0 else 0 for cid in pred_k]
    return sum(rels) / k


def dcg_at_k(pred, labels, k):
    dcg = 0.0
    for i, cid in enumerate(pred[:k], start=1):
        rel = labels.get(cid, 0.0)
        dcg += (2**rel - 1) / math.log2(i + 1)
    return dcg


def idcg_at_k(labels, k):
    ideal = sorted(labels.values(), reverse=True)
    idcg = 0.0
    for i, rel in enumerate(ideal[:k], start=1):
        idcg += (2**rel - 1) / math.log2(i + 1)
    return idcg


def ndcg_at_k(pred, labels, k):
    dcg = dcg_at_k(pred, labels, k)
    idcg = idcg_at_k(labels, k)
    return dcg / idcg if idcg > 0 else 0.0


def mrr(pred, labels):
    for i, cid in enumerate(pred, start=1):
        if labels.get(cid, 0) > 0:
            return 1.0 / i
    return 0.0


def compute_metrics(submission_path: str, labels_path: str):
    pred = read_submission(submission_path)
    labels = read_labels(labels_path)
    ks = [1, 5, 10]
    for k in ks:
        p = precision_at_k(pred, labels, k)
        ndcg = ndcg_at_k(pred, labels, k)
        print(f'Precision@{k}: {p:.4f}   NDCG@{k}: {ndcg:.4f}')
    print(f'MRR: {mrr(pred, labels):.4f}')


def main(argv=None):
    p = argparse.ArgumentParser(description='Evaluation harness + simple baseline')
    sp = p.add_subparsers(dest='cmd')

    sb = sp.add_parser('baseline', help='Generate simple keyword baseline submission')
    sb.add_argument('--candidates', required=True)
    sb.add_argument('--job-docx', default=None)
    sb.add_argument('--job-skills', default=None, help='Comma-separated skills')
    sb.add_argument('--out', default='baseline_submission.csv')
    sb.add_argument('--topk', type=int, default=100)

    sc = sp.add_parser('compare', help='Compare two submissions')
    sc.add_argument('--a', required=True)
    sc.add_argument('--b', required=True)
    sc.add_argument('--topk', type=int, default=10)

    sm = sp.add_parser('metrics', help='Compute metrics given labels file')
    sm.add_argument('--submission', required=True)
    sm.add_argument('--labels', required=True)

    args = p.parse_args(argv)
    if args.cmd == 'baseline':
        job_skills = []
        if args.job_skills:
            job_skills = [s.strip() for s in args.job_skills.split(',') if s.strip()]
        generate_baseline_submission(args.candidates, args.out, job_docx=args.job_docx, job_skills=job_skills, topk=args.topk)
    elif args.cmd == 'compare':
        compare_submissions(args.a, args.b, topk=args.topk)
    elif args.cmd == 'metrics':
        compute_metrics(args.submission, args.labels)
    else:
        p.print_help()


if __name__ == '__main__':
    main()
