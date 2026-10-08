from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone

from core.models import (
    StudentActivity,
    StudentProfile,
    TestAttempt,
)
from core.services.performance_metrics import get_performance_metrics, percentage

SUBJECT_GROUPS = {
    "Aptitude": [
        "Aptitude",
        "Quantitative Aptitude",
        "Logical Reasoning",
        "Verbal Ability",
    ],
    "DBMS": ["DBMS", "SQL"],
    "Operating Systems": ["Operating Systems"],
    "Computer Networks": ["Computer Networks"],
    "Coding": [],
}


def _build_subject_scores(metrics: dict[str, Any]):
    category_totals = {item["name"]: item for item in metrics["category_performance"]}
    subject_scores = []
    for subject_name, category_names in SUBJECT_GROUPS.items():
        if subject_name == "Coding":
            subject_scores.append({
                "name": subject_name,
                "value": metrics["coding_success_rate"],
                "attempts": metrics["coding_problems_attempted"],
                "solved": metrics["coding_problems_solved"],
            })
            continue

        attempts = 0
        solved = 0
        for category_name in category_names:
            totals = category_totals.get(category_name, {"attempted": 0, "correct": 0})
            attempts += totals["attempted"]
            solved += totals["correct"]

        subject_scores.append({
            "name": subject_name,
            "value": percentage(solved, attempts),
            "attempts": attempts,
            "solved": solved,
        })

    return subject_scores


def _build_recommendations(weakest_topic: str | None, metrics: dict[str, Any]):
    recommendations = []

    if weakest_topic:
        recommendations.append({
            "title": f"Focus on {weakest_topic}",
            "description": f"This is your lowest current performance area. Review key concepts and complete a focused practice round.",
            "priority": "High",
            "url": "/practice/",
        })

    if metrics["coding_success_rate"] < 50:
        recommendations.append({
            "title": "Solve 2 coding problems",
            "description": "Build confidence in your coding fundamentals with a quick problem-solving sprint.",
            "priority": "Medium",
            "url": "/coding/",
        })

    if metrics["tests_completed"] == 0:
        recommendations.append({
            "title": "Take a mock test",
            "description": "A timed mock test will reveal your readiness and highlight weak sections for revision.",
            "priority": "Medium",
            "url": "/mock-tests/",
        })

    if not recommendations:
        recommendations.append({
            "title": "Continue streak momentum",
            "description": "Keep your practice rhythm going and review your weakest topic for the next milestone.",
            "priority": "Low",
            "url": "/analytics/",
        })

    return recommendations[:3]


def _build_current_streak(user: Any) -> int:
    activity_dates = set(
        StudentActivity.objects.filter(user=user)
        .values_list("created_at__date", flat=True)
        .distinct()
        .order_by("-created_at__date")
    )

    if not activity_dates:
        return 0

    today = timezone.now().date()
    streak = 0
    cursor = today
    while cursor in activity_dates:
        streak += 1
        cursor -= timedelta(days=1)

    return streak


def get_dashboard_summary(user: Any):
    profile = StudentProfile.objects.filter(user=user).first()
    metrics = get_performance_metrics(user)
    recent_activity = StudentActivity.objects.filter(user=user).order_by("-created_at")[:5]
    topic_progress = metrics["topic_performance"][:6]

    strongest_topic = None
    weakest_topic = None
    if topic_progress:
        strongest_topic = topic_progress[0]
        weakest_topic = metrics["weak_topics"][0]

    subject_scores = _build_subject_scores(metrics)
    recommended_actions = _build_recommendations(
        weakest_topic["topic"] if weakest_topic else None,
        metrics,
    )
    is_empty = not (
        metrics["questions_attempted"]
        or metrics["coding_problems_attempted"]
        or metrics["tests_completed"]
        or TestAttempt.objects.filter(user=user).exists()
        or recent_activity.exists()
    )

    return {
        "profile": profile,
        "questions_attempted": metrics["questions_attempted"],
        "questions_solved": metrics["questions_solved"],
        "tests_completed": metrics["tests_completed"],
        "accuracy": metrics["accuracy"],
        "current_streak": _build_current_streak(user),
        "overall_preparation_score": metrics["overall_preparation_score"],
        "coding_problems_attempted": metrics["coding_problems_attempted"],
        "coding_problems_solved": metrics["coding_problems_solved"],
        "coding_success_rate": metrics["coding_success_rate"],
        "category_performance": metrics["category_performance"],
        "topic_performance": metrics["topic_performance"],
        "subject_scores": subject_scores,
        "topic_progress": topic_progress,
        "strongest_topic": strongest_topic,
        "weakest_topic": weakest_topic,
        "recent_activity": recent_activity,
        "recommended_actions": recommended_actions,
        "is_empty": is_empty,
    }
