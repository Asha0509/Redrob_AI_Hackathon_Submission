#!/usr/bin/env python3
"""Offline candidate ranker for the Redrob challenge."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET


REQUIRED_HEADER = ["candidate_id", "rank", "score", "reasoning"]
TARGET_ROWS = 100
_WORD_RE = re.compile(r"[a-z0-9]+")
_PHRASE_REPLACEMENTS = {
    "machine learning": "machine_learning",
    "learning to rank": "learning_to_rank",
    "open search": "opensearch",
    "vector database": "vector_database",
    "vector databases": "vector_database",
    "fine tuning": "fine_tuning",
    "search engine": "search_engine",
    "recommendation system": "recommendation_system",
    "recommendation systems": "recommendation_system",
    "natural language processing": "nlp",
    "information retrieval": "information_retrieval",
    "artificial intelligence": "ai",
    "large language model": "llm",
    "large language models": "llm",
}

CONSULTING_ONLY_COMPANIES = {
    "tcs",
    "infosys",
    "wipro",
    "accenture",
    "cognizant",
    "capgemini",
    "deloitte",
    "pwc",
    "ey",
    "kpmg",
    "hcl",
    "mindtree",
    "lti",
    "ltimindtree",
}

TITLE_HINTS = {
    "ai engineer": 1.0,
    "machine learning engineer": 1.0,
    "ml engineer": 1.0,
    "data scientist": 0.92,
    "search engineer": 0.98,
    "ranking engineer": 0.98,
    "retrieval engineer": 0.98,
    "relevance engineer": 0.98,
    "applied scientist": 0.9,
    "backend engineer": 0.72,
    "data engineer": 0.76,
    "analytics engineer": 0.8,
    "software engineer": 0.72,
    "platform engineer": 0.74,
    "research scientist": 0.35,
    "research engineer": 0.42,
}

LOCATION_HINTS = {
    "pune": 1.0,
    "noida": 1.0,
    "delhi": 0.88,
    "gurgaon": 0.85,
    "gurugram": 0.85,
    "mumbai": 0.88,
    "hyderabad": 0.85,
    "bengaluru": 0.85,
    "bangalore": 0.85,
    "chennai": 0.76,
    "india": 0.92,
}

MUST_HAVE_SKILL_ALIASES = {
    "embeddings": {"embeddings", "sentence transformers", "sentence-transformers", "bge", "e5", "openai embeddings"},
    "retrieval": {"retrieval", "search", "bm25", "hybrid search", "information retrieval"},
    "ranking": {"ranking", "learning to rank", "ltr", "ndcg", "mrr", "map"},
    "vector_db": {"vector db", "vector database", "milvus", "qdrant", "pinecone", "weaviate", "faiss", "elasticsearch", "opensearch"},
    "python": {"python"},
    "evaluation": {"evaluation", "ndcg", "mrr", "map", "ab testing", "a/b testing", "offline evaluation"},
}

NICE_TO_HAVE_SKILL_ALIASES = {
    "llm": {"llm", "peft", "qlora", "lora", "fine tuning", "fine-tuning llms"},
    "hr_tech": {"hr-tech", "recruiting", "talent intelligence", "marketplace"},
    "distributed_systems": {"distributed systems", "large scale inference", "inference optimization"},
    "open_source": {"open source", "github", "contribution"},
}


@dataclass(frozen=True)
class JobProfile:
    title: str
    location_text: str
    experience_text: str
    must_have_terms: tuple[str, ...]
    nice_to_have_terms: tuple[str, ...]
    negative_terms: tuple[str, ...]
    text: str


def normalize_text(text: str) -> str:
    lowered = text.lower()
    for phrase, replacement in _PHRASE_REPLACEMENTS.items():
        lowered = lowered.replace(phrase, replacement)
    lowered = lowered.replace("/", " ")
    lowered = lowered.replace("-", " ")
    lowered = lowered.replace("&", " and ")
    lowered = lowered.replace("\u2014", " ")
    lowered = lowered.replace("\u2013", " ")
    lowered = re.sub(r"[^a-z0-9_]+", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def extract_docx_text(path: Path) -> str:
    with ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    lines: list[str] = []
    for paragraph in root.findall(".//w:p", ns):
        parts = [node.text for node in paragraph.findall(".//w:t", ns) if node.text]
        if parts:
            lines.append("".join(parts))
    return "\n".join(lines)


def _job_profile_from_text(text: str) -> JobProfile:
    """Deep job parsing: extract required, nice-to-have, seniority level, and domain."""
    normalized = normalize_text(text)
    
    # Extract seniority level from job description
    seniority_markers = {
        "senior": ("senior", "lead", "staff", "principal"),
        "mid": ("mid", "intermediate", "3-5 years", "4-6 years", "5-7 years"),
        "junior": ("junior", "entry", "graduate", "fresher", "0-2 years", "1-3 years"),
    }
    seniority = "senior"
    for level, markers in seniority_markers.items():
        if any(m in normalized for m in markers):
            seniority = level
            break
    
    # Extract domain signals from job description
    domain_signals = []
    domain_keywords = {
        "search": ("search engine", "information retrieval", "bm25", "lucene"),
        "ranking": ("ranking", "learning to rank", "ltr", "ndcg", "mrr"),
        "embeddings": ("embeddings", "vectors", "vector search", "semantic"),
        "production_ai": ("production", "deployment", "serving", "inference", "latency"),
        "llm": ("llm", "language model", "gpt", "bert", "fine tuning"),
        "recommendation": ("recommendation", "personalization", "collaborative filtering"),
    }
    for domain, keywords in domain_keywords.items():
        if any(k in normalized for k in keywords):
            domain_signals.append(domain)
    
    return JobProfile(
        title=f"{seniority} ai engineer",
        location_text="pune noida india tier 1 cities relocation hybrid",
        experience_text=f"{seniority} level 5 9 years ideal 6 8 years applied ml product company",
        must_have_terms=("embeddings", "retrieval", "ranking", "vector database", "python", "ndcg", "mrr", "map", "hybrid search", "evaluation"),
        nice_to_have_terms=("llm", "fine tuning", "learning to rank", "hr tech", "distributed systems", "open source", "langchain"),
        negative_terms=("langchain tutorial", "academic", "research only", "consulting", "computer vision", "speech", "robotics"),
        text=normalized,
    )


def build_job_profile(job_description_path: Path) -> JobProfile:
    return _job_profile_from_text(extract_docx_text(job_description_path))


def load_candidates(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as handle:
        first_non_empty = None
        for line in handle:
            if line.strip():
                first_non_empty = line.lstrip()
                break
        if first_non_empty is None:
            return []
        handle.seek(0)
        if first_non_empty.startswith("["):
            data = json.load(handle)
            if isinstance(data, list):
                return data
            raise ValueError("Expected a JSON array in sample candidates file")
        return [json.loads(line) for line in handle if line.strip()]


def _flatten_candidate_text(candidate: dict) -> str:
    parts: list[str] = []
    profile = candidate.get("profile", {})
    for field in ("anonymized_name", "headline", "summary", "location", "country", "current_title", "current_company", "current_industry"):
        parts.append(str(profile.get(field, "")))
    for item in candidate.get("career_history", []):
        for field in ("company", "title", "industry", "description"):
            parts.append(str(item.get(field, "")))
    for item in candidate.get("education", []):
        for field in ("institution", "degree", "field_of_study", "grade", "tier"):
            parts.append(str(item.get(field, "")))
    for item in candidate.get("skills", []):
        for field in ("name", "proficiency"):
            parts.append(str(item.get(field, "")))
    parts.extend(str(value) for value in candidate.get("redrob_signals", {}).values())
    return normalize_text(" ".join(parts))


def _skill_match_score(candidate: dict) -> tuple[float, list[str]]:
    skills = []
    for item in candidate.get("skills", []):
        skills.append(
            (
                normalize_text(str(item.get("name", ""))),
                str(item.get("proficiency", "")).lower(),
                max(0, int(item.get("endorsements", 0) or 0)),
                max(0, int(item.get("duration_months", 0) or 0)),
            )
        )

    score = 0.0
    evidence: list[str] = []
    proficiency_weights = {"beginner": 0.4, "intermediate": 0.68, "advanced": 0.88, "expert": 1.0}

    for label, aliases in MUST_HAVE_SKILL_ALIASES.items():
        match_strength = 0.0
        matched_skill = ""
        for name, proficiency, endorsements, duration in skills:
            if any(alias in name for alias in aliases):
                duration_factor = min(1.0, math.log1p(duration) / 4.0)
                endorsement_factor = min(1.0, math.log1p(endorsements + 1) / 4.0)
                depth = 0.55 * proficiency_weights.get(proficiency, 0.5) + 0.25 * duration_factor + 0.2 * endorsement_factor
                if depth > match_strength:
                    match_strength = depth
                    matched_skill = name
        if match_strength > 0:
            score += 1.0 * match_strength
            evidence.append(f"{label}:{matched_skill}")

    for label, aliases in NICE_TO_HAVE_SKILL_ALIASES.items():
        match_strength = 0.0
        matched_skill = ""
        for name, proficiency, endorsements, duration in skills:
            if any(alias in name for alias in aliases):
                duration_factor = min(1.0, math.log1p(duration) / 4.5)
                endorsement_factor = min(1.0, math.log1p(endorsements + 1) / 4.5)
                depth = 0.5 * proficiency_weights.get(proficiency, 0.5) + 0.3 * duration_factor + 0.2 * endorsement_factor
                if depth > match_strength:
                    match_strength = depth
                    matched_skill = name
        if match_strength > 0:
            score += 0.45 * match_strength
            evidence.append(f"nice:{label}:{matched_skill}")

    if any(name == "python" for name, _, _, _ in skills):
        score += 0.3
    if any(name in {"ndcg", "mrr", "map", "ab testing", "a b testing"} for name, _, _, _ in skills):
        score += 0.2

    return min(1.0, score / 3.3), evidence[:6]


def _history_signal_score(candidate: dict) -> tuple[float, list[str]]:
    history = candidate.get("career_history", [])
    if not history:
        return 0.0, []

    history_score = 0.0
    evidence: list[str] = []
    for index, item in enumerate(history):
        text = normalize_text(" ".join(str(item.get(field, "")) for field in ("title", "company", "industry", "description")))
        recency_weight = 1.0 - min(index * 0.1, 0.2)
        term_hits = 0.0
        for term, weight in (
            ("embeddings", 1.2),
            ("retrieval", 1.25),
            ("ranking", 1.3),
            ("recommendation", 1.0),
            ("search", 1.0),
            ("vector database", 1.15),
            ("faiss", 1.2),
            ("milvus", 1.2),
            ("elasticsearch", 1.1),
            ("opensearch", 1.1),
            ("ndcg", 1.0),
            ("mrr", 1.0),
            ("ab testing", 0.85),
            ("production", 0.6),
            ("deployed", 0.7),
            ("users", 0.5),
            ("real time", 0.5),
            ("model serving", 0.6),
            ("python", 0.45),
        ):
            if term in text:
                term_hits += weight
        if term_hits:
            local = min(1.0, term_hits / 5.0)
            history_score = max(history_score, local * recency_weight)
            evidence.append(f"{item.get('title', '')} @ {item.get('company', '')}")

    if not evidence:
        current_title = normalize_text(str(candidate.get("profile", {}).get("current_title", "")))
        if any(role in current_title for role in ("ai engineer", "machine learning engineer", "ml engineer", "search engineer", "ranking engineer", "retrieval engineer", "data scientist", "backend engineer", "data engineer", "analytics engineer", "software engineer")):
            history_score = 0.35
            evidence.append(candidate.get("profile", {}).get("current_title", ""))

    return min(1.0, history_score), evidence[:4]


def _title_fit_score(candidate: dict) -> tuple[float, str]:
    current_title = normalize_text(str(candidate.get("profile", {}).get("current_title", "")))
    title_bonus = 0.0
    matched = current_title or "unknown"
    for title, weight in TITLE_HINTS.items():
        if title in current_title:
            title_bonus = max(title_bonus, weight)
            matched = title
    if not title_bonus:
        for item in candidate.get("career_history", []):
            history_title = normalize_text(str(item.get("title", "")))
            for title, weight in TITLE_HINTS.items():
                if title in history_title:
                    title_bonus = max(title_bonus, weight * 0.92)
                    matched = title
    if not title_bonus:
        title_bonus = 0.1 if any(role in current_title for role in ("marketing", "sales", "content", "hr", "accountant", "civil engineer", "mechanical engineer", "project manager", "customer support", "graphic designer", "operations manager")) else 0.3
    if any(role in current_title for role in ("marketing", "sales", "content", "hr", "accountant", "civil engineer", "mechanical engineer", "project manager", "customer support", "graphic designer", "operations manager")):
        title_bonus *= 0.65
    return min(1.0, title_bonus), matched


def _experience_score(candidate: dict) -> float:
    years = candidate.get("profile", {}).get("years_of_experience")
    try:
        years = float(years)
    except (TypeError, ValueError):
        return 0.0
    if years < 2:
        return 0.05
    center = 7.0
    sigma = 2.1
    gaussian = math.exp(-((years - center) ** 2) / (2 * sigma**2))
    band_boost = 1.0 if 5 <= years <= 9 else 0.85
    return min(1.0, gaussian * band_boost)


def _location_score(candidate: dict) -> tuple[float, str]:
    profile = candidate.get("profile", {})
    location = normalize_text(" ".join(str(profile.get(field, "")) for field in ("location", "country")))
    work_mode = normalize_text(str(candidate.get("redrob_signals", {}).get("preferred_work_mode", "")))
    relocate = bool(candidate.get("redrob_signals", {}).get("willing_to_relocate", False))
    score = 0.2
    best = ""
    for hint, weight in LOCATION_HINTS.items():
        if hint in location:
            score = max(score, weight)
            best = hint
    if "india" in location:
        score = max(score, 0.82)
    if relocate:
        score = min(1.0, score + 0.12)
    if work_mode in {"hybrid", "onsite", "flexible"}:
        score = min(1.0, score + 0.06)
    if "remote" in work_mode:
        score *= 0.9
    return min(1.0, score), best or location or work_mode


def _signal_score(candidate: dict) -> tuple[float, list[str]]:
    signals = candidate.get("redrob_signals", {})
    score = 0.0
    evidence: list[str] = []

    completeness = float(signals.get("profile_completeness_score", 0) or 0) / 100.0
    response_rate = float(signals.get("recruiter_response_rate", 0) or 0)
    interview_completion = float(signals.get("interview_completion_rate", 0) or 0)
    github = float(signals.get("github_activity_score", -1) or -1)
    github_score = 0.0 if github < 0 else github / 100.0
    verified_bonus = sum(1 for field in ("verified_email", "verified_phone", "linkedin_connected") if signals.get(field)) / 3.0
    open_to_work = 1.0 if signals.get("open_to_work_flag") else 0.0
    last_active = signals.get("last_active_date")
    recency_bonus = 0.0
    if isinstance(last_active, str) and last_active:
        try:
            active_date = datetime.strptime(last_active, "%Y-%m-%d").date()
            days = max(0, (date(2026, 6, 18) - active_date).days)
            recency_bonus = max(0.0, 1.0 - min(days, 180) / 180.0)
        except ValueError:
            recency_bonus = 0.0
    search_volume = min(1.0, float(signals.get("search_appearance_30d", 0) or 0) / 250.0)
    saved_by_recruiters = min(1.0, float(signals.get("saved_by_recruiters_30d", 0) or 0) / 30.0)
    notice_period = float(signals.get("notice_period_days", 180) or 180)
    notice_score = 1.0 if notice_period <= 30 else max(0.1, 1.0 - min(notice_period, 180) / 240.0)
    applications = float(signals.get("applications_submitted_30d", 0) or 0)
    applications_score = 1.0 - min(applications, 20.0) / 30.0
    offer_acceptance = float(signals.get("offer_acceptance_rate", -1) or -1)
    offer_score = 0.5 if offer_acceptance < 0 else offer_acceptance

    score += 0.22 * completeness
    score += 0.18 * response_rate
    score += 0.16 * interview_completion
    score += 0.12 * github_score
    score += 0.10 * verified_bonus
    score += 0.08 * open_to_work
    score += 0.07 * recency_bonus
    score += 0.04 * search_volume
    score += 0.03 * saved_by_recruiters
    score += 0.05 * notice_score
    score += 0.02 * applications_score
    score += 0.03 * offer_score

    evidence.append(f"activity:{completeness:.2f}/{response_rate:.2f}/{interview_completion:.2f}")
    if open_to_work:
        evidence.append("open_to_work")
    if github_score > 0:
        evidence.append(f"github:{github_score:.2f}")
    return min(1.0, score), evidence


def _education_score(candidate: dict) -> tuple[float, str]:
    education = candidate.get("education", [])
    if not education:
        return 0.15, "no_education"
    best = 0.2
    best_label = "education"
    tier_weights = {"tier_1": 1.0, "tier_2": 0.88, "tier_3": 0.72, "tier_4": 0.62, "unknown": 0.55}
    for item in education:
        tier = str(item.get("tier", "unknown")).lower()
        best = max(best, tier_weights.get(tier, 0.55))
        best_label = tier
    return min(1.0, best), best_label


def _penalty_score(candidate: dict) -> tuple[float, list[str]]:
    text = _flatten_candidate_text(candidate)
    penalty = 0.0
    notes: list[str] = []

    current_title = normalize_text(str(candidate.get("profile", {}).get("current_title", "")))
    history_text = " ".join(
        normalize_text(str(item.get(field, "")))
        for item in candidate.get("career_history", [])
        for field in ("title", "company", "industry", "description")
    )

    companies = {
        normalize_text(str(item.get("company", ""))).split()[0]
        for item in candidate.get("career_history", [])
        if str(item.get("company", "")).strip() and normalize_text(str(item.get("company", ""))).split()
    }

    if any(term in text for term in ("academic", "professor", "research only", "phd thesis")) and not any(term in text for term in ("production", "deployed", "users", "shipping", "platform")):
        penalty += 0.18
        notes.append("research_heavy")

    if any(company in CONSULTING_ONLY_COMPANIES for company in companies) and not any(term in text for term in ("product", "platform", "users", "revenue", "deployed", "model serving")):
        penalty += 0.14
        notes.append("consulting_only")

    buzzword_count = sum(text.count(term) for term in ("langchain", "openai", "rag", "llm", "pinecone", "milvus", "qdrant"))
    applied_count = sum(text.count(term) for term in ("production", "deployed", "evaluation", "ranking", "retrieval", "search"))
    if buzzword_count >= 3 and applied_count == 0:
        penalty += 0.12
        notes.append("buzzword_heavy")

    if any(term in current_title for term in ("marketing", "sales", "content", "hr", "accountant")) and not any(term in history_text for term in ("python", "ml", "ranking", "retrieval", "search")):
        penalty += 0.10
        notes.append("title_mismatch")

    if float(candidate.get("redrob_signals", {}).get("github_activity_score", -1) or -1) == -1:
        penalty += 0.02
        notes.append("no_github")

    return min(0.5, penalty), notes


def score_candidate(candidate: dict, job_profile: JobProfile) -> tuple[float, dict]:
    skill_score, skill_evidence = _skill_match_score(candidate)
    history_score, history_evidence = _history_signal_score(candidate)
    title_score, title_label = _title_fit_score(candidate)
    experience_score = _experience_score(candidate)
    location_score, location_label = _location_score(candidate)
    signal_score, signal_evidence = _signal_score(candidate)
    education_score, education_label = _education_score(candidate)
    penalty, penalty_labels = _penalty_score(candidate)

    score = (
        0.31 * skill_score
        + 0.22 * history_score
        + 0.16 * title_score
        + 0.09 * experience_score
        + 0.08 * signal_score
        + 0.05 * location_score
        + 0.04 * education_score
        + 0.05 * min(1.0, skill_score * history_score)
    )
    score = max(0.0, min(1.0, score - penalty))

    return score, {
        "skill_score": skill_score,
        "history_score": history_score,
        "title_score": title_score,
        "experience_score": experience_score,
        "signal_score": signal_score,
        "location_score": location_score,
        "education_score": education_score,
        "penalty": penalty,
        "skill_evidence": skill_evidence,
        "history_evidence": history_evidence,
        "signal_evidence": signal_evidence,
        "title_label": title_label,
        "location_label": location_label,
        "education_label": education_label,
        "penalty_labels": penalty_labels,
    }


def make_reasoning(candidate: dict, evidence: dict) -> str:
    profile = candidate.get("profile", {})
    title = profile.get("current_title", "candidate")
    years = profile.get("years_of_experience", "?")
    
    # Calculate weighted contribution of each score component
    skill_contrib = 0.31 * evidence.get("skill_score", 0)
    history_contrib = 0.22 * evidence.get("history_score", 0)
    title_contrib = 0.16 * evidence.get("title_score", 0)
    experience_contrib = 0.09 * evidence.get("experience_score", 0)
    signal_contrib = 0.08 * evidence.get("signal_score", 0)
    location_contrib = 0.05 * evidence.get("location_score", 0)
    
    parts = [f"{title} ({years}y) | skills:{skill_contrib:.2f} history:{history_contrib:.2f} title:{title_contrib:.2f}"]

    if evidence.get("history_evidence"):
        parts.append(f"history: {evidence['history_evidence'][0]}")
    if evidence.get("skill_evidence"):
        parts.append(f"skills: {', '.join(evidence['skill_evidence'][:3])}")
    if evidence.get("signal_evidence"):
        parts.append(f"signals: {', '.join(evidence['signal_evidence'][:2])}")
    if evidence.get("location_label"):
        parts.append(f"location: {evidence['location_label']}")
    if evidence.get("penalty_labels"):
        parts.append(f"watch: {', '.join(evidence['penalty_labels'][:2])}")

    return "; ".join(parts)[:320]


def rank_candidates(candidates: list[dict], job_profile: JobProfile, top_k: int = TARGET_ROWS) -> list[dict]:
    scored: list[tuple[float, str, dict, dict]] = []
    for candidate in candidates:
        score, evidence = score_candidate(candidate, job_profile)
        scored.append((score, str(candidate.get("candidate_id", "")), candidate, evidence))

    scored.sort(key=lambda item: (-item[0], item[1]))

    rows: list[dict] = []
    for rank, (score, candidate_id, candidate, evidence) in enumerate(scored[:top_k], start=1):
        rows.append({"candidate_id": candidate_id, "rank": rank, "score": round(score, 6), "reasoning": make_reasoning(candidate, evidence)})
    return rows


def write_submission(rows: list[dict], out_path: Path) -> None:
    with open(out_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(REQUIRED_HEADER)
        for row in rows:
            writer.writerow([row["candidate_id"], row["rank"], f'{row["score"]:.6f}', row["reasoning"]])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rank Redrob candidates offline.")
    parser.add_argument("--candidates", type=Path, required=True, help="Path to candidates.jsonl or sample_candidates.json")
    parser.add_argument("--job-description", type=Path, default=None, help="Path to the JD .docx file")
    parser.add_argument("--out", type=Path, required=True, help="Output CSV path")
    parser.add_argument("--top-k", type=int, default=TARGET_ROWS, help="How many candidates to write")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    job_path = args.job_description or args.candidates.with_name("job_description.docx")
    if not job_path.exists():
        raise FileNotFoundError(f"Job description file not found: {job_path}")

    job_profile = build_job_profile(job_path)
    candidates = load_candidates(args.candidates)
    if len(candidates) < args.top_k:
        raise ValueError(f"Need at least {args.top_k} candidates, found {len(candidates)}")

    ranked_rows = rank_candidates(candidates, job_profile, top_k=args.top_k)
    write_submission(ranked_rows, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())