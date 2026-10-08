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
from core.services.recommendation_service import get_recommendations

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
    recommendation_data = get_recommendations(user, metrics=metrics)
    recommended_actions = [
        {
            "title": item["recommendation"],
            "description": item["focus"],
            "priority": item["priority"].title(),
            "url": item["url"],
        }
        for item in recommendation_data["recommendations"]
    ]
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
        "recommendation_data": recommendation_data,
        "recommended_actions": recommended_actions,
        "is_empty": is_empty,
    }
