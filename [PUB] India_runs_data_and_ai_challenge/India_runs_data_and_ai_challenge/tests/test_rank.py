from __future__ import annotations

import unittest
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rank import _job_profile_from_text, rank_candidates, score_candidate


def make_candidate(
    candidate_id: str,
    current_title: str,
    skills: list[dict],
    history: list[dict],
    signals: dict,
    years: float = 7.0,
) -> dict:
    return {
        "candidate_id": candidate_id,
        "profile": {
            "anonymized_name": "Test Person",
            "headline": current_title,
            "summary": "",
            "location": "Pune",
            "country": "India",
            "years_of_experience": years,
            "current_title": current_title,
            "current_company": "TestCo",
            "current_company_size": "51-200",
            "current_industry": "Technology",
        },
        "skills": skills,
        "career_history": history,
        "education": [],
        "redrob_signals": signals,
    }


class RankerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.job = _job_profile_from_text(
            "Senior AI Engineer needs embeddings, retrieval, ranking, vector database, Python, NDCG, MRR, and hybrid search."
        )

    def test_relevant_candidate_beats_keyword_stuffer(self) -> None:
        strong = make_candidate(
            "CAND_0000001",
            "Machine Learning Engineer",
            [
                {"name": "Python", "proficiency": "expert", "endorsements": 24, "duration_months": 48},
                {"name": "Milvus", "proficiency": "advanced", "endorsements": 8, "duration_months": 24},
                {"name": "Ranking", "proficiency": "advanced", "endorsements": 10, "duration_months": 30},
            ],
            [
                {
                    "title": "Search Engineer",
                    "company": "ProductCo",
                    "industry": "Technology",
                    "description": "Built retrieval and ranking systems in production.",
                }
            ],
            {
                "profile_completeness_score": 92,
                "recruiter_response_rate": 0.8,
                "interview_completion_rate": 0.9,
                "open_to_work_flag": True,
                "verified_email": True,
                "verified_phone": True,
                "linkedin_connected": True,
                "github_activity_score": 75,
                "last_active_date": "2026-06-10",
                "search_appearance_30d": 40,
                "saved_by_recruiters_30d": 6,
                "notice_period_days": 15,
                "applications_submitted_30d": 1,
                "offer_acceptance_rate": 0.7,
            },
        )
        weak = make_candidate(
            "CAND_0000002",
            "Marketing Manager",
            [
                {"name": "Pinecone", "proficiency": "expert", "endorsements": 1, "duration_months": 1},
                {"name": "LangChain", "proficiency": "expert", "endorsements": 1, "duration_months": 1},
                {"name": "OpenAI", "proficiency": "expert", "endorsements": 1, "duration_months": 1},
            ],
            [
                {
                    "title": "Marketing Manager",
                    "company": "AgencyCo",
                    "industry": "Marketing",
                    "description": "Built decks and campaigns.",
                }
            ],
            {
                "profile_completeness_score": 85,
                "recruiter_response_rate": 0.2,
                "interview_completion_rate": 0.4,
                "open_to_work_flag": False,
                "verified_email": True,
                "verified_phone": False,
                "linkedin_connected": False,
                "github_activity_score": -1,
                "last_active_date": "2025-10-10",
                "search_appearance_30d": 1,
                "saved_by_recruiters_30d": 0,
                "notice_period_days": 90,
                "applications_submitted_30d": 18,
                "offer_acceptance_rate": -1,
            },
            years=12.0,
        )

        strong_score, strong_evidence = score_candidate(strong, self.job)
        weak_score, weak_evidence = score_candidate(weak, self.job)
        self.assertGreater(strong_score, weak_score)
        self.assertGreater(strong_score, 0.4)
        self.assertLess(weak_score, 0.4)
        self.assertTrue(strong_evidence["skill_evidence"])
        self.assertIn("open_to_work", strong_evidence["signal_evidence"])

    def test_ranker_breaks_ties_by_candidate_id(self) -> None:
        candidate_a = make_candidate(
            "CAND_0000001",
            "Software Engineer",
            [],
            [],
            {
                "profile_completeness_score": 50,
                "recruiter_response_rate": 0.5,
                "interview_completion_rate": 0.5,
                "open_to_work_flag": False,
                "verified_email": True,
                "verified_phone": True,
                "linkedin_connected": True,
                "github_activity_score": 10,
                "last_active_date": "2026-01-01",
                "search_appearance_30d": 0,
                "saved_by_recruiters_30d": 0,
                "notice_period_days": 30,
                "applications_submitted_30d": 0,
                "offer_acceptance_rate": -1,
            },
        )
        candidate_b = make_candidate(
            "CAND_0000002",
            "Software Engineer",
            [],
            [],
            {
                "profile_completeness_score": 50,
                "recruiter_response_rate": 0.5,
                "interview_completion_rate": 0.5,
                "open_to_work_flag": False,
                "verified_email": True,
                "verified_phone": True,
                "linkedin_connected": True,
                "github_activity_score": 10,
                "last_active_date": "2026-01-01",
                "search_appearance_30d": 0,
                "saved_by_recruiters_30d": 0,
                "notice_period_days": 30,
                "applications_submitted_30d": 0,
                "offer_acceptance_rate": -1,
            },
        )

        ranked = rank_candidates([candidate_b, candidate_a], self.job, top_k=2)
        self.assertEqual([row["candidate_id"] for row in ranked], ["CAND_0000001", "CAND_0000002"])

    def test_inconsistent_experience_is_penalized(self) -> None:
        consistent = make_candidate(
            "CAND_0000001",
            "Machine Learning Engineer",
            [{"name": "Python", "proficiency": "expert", "endorsements": 10, "duration_months": 60}],
            [{
                "title": "Search Engineer",
                "company": "ProductCo",
                "industry": "Technology",
                "description": "Built retrieval systems in production.",
                "duration_months": 72,
            }],
            {},
            years=6.0,
        )
        consistent["profile"]["summary"] = "ML engineer with 6 years of production experience."

        inconsistent = make_candidate(
            "CAND_0000002",
            "Machine Learning Engineer",
            [{"name": "Python", "proficiency": "expert", "endorsements": 10, "duration_months": 60}],
            [{
                "title": "Search Engineer",
                "company": "ProductCo",
                "industry": "Technology",
                "description": "Built retrieval systems in production.",
                "duration_months": 72,
            }],
            {},
            years=16.0,
        )
        inconsistent["profile"]["summary"] = "ML engineer with 6 years of production experience."

        consistent_score, _ = score_candidate(consistent, self.job)
        inconsistent_score, evidence = score_candidate(inconsistent, self.job)
        self.assertGreater(consistent_score, inconsistent_score)
        self.assertIn("experience_inconsistent", evidence["penalty_labels"])

    def test_zero_duration_expert_claims_are_penalized(self) -> None:
        candidate = make_candidate(
            "CAND_0000003",
            "Machine Learning Engineer",
            [
                {"name": "Python", "proficiency": "expert", "endorsements": 5, "duration_months": 0},
                {"name": "Ranking", "proficiency": "expert", "endorsements": 5, "duration_months": 0},
                {"name": "FAISS", "proficiency": "expert", "endorsements": 5, "duration_months": 0},
            ],
            [{
                "title": "Search Engineer",
                "company": "ProductCo",
                "industry": "Technology",
                "description": "Built retrieval systems.",
                "duration_months": 72,
            }],
            {},
            years=6.0,
        )
        _, evidence = score_candidate(candidate, self.job)
        self.assertIn("impossible_skill_claims", evidence["penalty_labels"])


if __name__ == "__main__":
    unittest.main()
