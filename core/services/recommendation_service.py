from __future__ import annotations

from typing import Any

from django.urls import reverse

from core.models import AptitudeTopic
from core.services.performance_metrics import get_performance_metrics, percentage

THRESHOLDS = {
    "high": 50,
    "medium": 70,
    "strong": 85,
}

CATEGORY_ALIASES = {
    "Aptitude": {
        "aptitude",
        "quantitative aptitude",
        "logical reasoning",
        "verbal ability",
    },
    "DBMS": {"dbms", "sql"},
    "Operating Systems": {"os", "operating systems", "operating system"},
    "Computer Networks": {"cn", "computer networks", "computer network"},
    "OOP": {"oop", "object oriented programming", "object-oriented programming"},
    "Data Structures / Algorithms": {
        "data structures",
        "data structure",
        "algorithms",
        "algorithm",
        "arrays",
        "strings",
        "searching",
        "sorting",
        "linked lists",
        "stack",
        "queue",
        "trees",
        "graphs",
        "hashing",
        "recursion",
        "dynamic programming",
        "greedy",
        "two pointers",
        "sliding window",
        "prefix sum",
    },
    "Coding": {"basic programming", "programming"},
}

_PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _practice_url() -> str:
    return reverse("practice")


def _coding_url() -> str:
    return reverse("coding")


def _normalized(value: str) -> str:
    return " ".join(value.casefold().replace("&", "and").split())


def _category_for_name(name: str) -> str | None:
    normalized_name = _normalized(name)
    if "aptitude" in normalized_name or "quantitative" in normalized_name:
        return "Aptitude"
    if "logical reasoning" in normalized_name or "verbal ability" in normalized_name:
        return "Aptitude"
    if "database" in normalized_name or normalized_name.startswith("sql"):
        return "DBMS"
    if "operating system" in normalized_name or normalized_name == "os" or normalized_name.startswith("os "):
        return "Operating Systems"
    if "computer network" in normalized_name or normalized_name == "cn" or normalized_name.startswith("cn "):
        return "Computer Networks"
    if "object oriented" in normalized_name or normalized_name == "oop" or normalized_name.startswith("oop "):
        return "OOP"
    if normalized_name.startswith(("data structure", "algorithm")):
        return "Data Structures / Algorithms"
    for category, aliases in CATEGORY_ALIASES.items():
        if normalized_name in aliases:
            return category
    return None


def _priority_for(performance: float) -> tuple[str, str]:
    if performance < THRESHOLDS["high"]:
        return "HIGH", "Weak area"
    if performance < THRESHOLDS["medium"]:
        return "MEDIUM", "Needs improvement"
    if performance < THRESHOLDS["strong"]:
        return "LOW", "Good progress"
    return "LOW", "Strong area"


def _topic_url(category_name: str, topic_name: str) -> str:
    topic = (
        AptitudeTopic.objects.filter(
            name=topic_name,
            category__name=category_name,
            is_active=True,
            category__is_active=True,
        )
        .select_related("category")
        .first()
    )
    if topic:
        return reverse(
            "aptitude_topic",
            kwargs={"category_slug": topic.category.slug, "topic_slug": topic.slug},
        )
    return _practice_url()


def _recommendation_for_area(
    name: str,
    performance: float,
    attempted: int,
    *,
    is_coding: bool,
    weak_topics: list[dict[str, Any]],
) -> dict[str, Any]:
    priority, status = _priority_for(performance)
    weak_topics = sorted(
        weak_topics,
        key=lambda topic: (
            topic["accuracy"],
            -topic["attempted"],
            topic["name"].casefold(),
        ),
    )
    if is_coding and status == "Strong area":
        action = "Try harder coding problems"
        focus = "Build on your strong results with more challenging problems."
        quantity = 3
    elif is_coding:
        action = "Solve 10 coding problems"
        focus = "Review the problem-solving patterns where your results need work."
        quantity = 10
    elif status == "Strong area":
        action = "Try harder practice questions"
        focus = f"Extend your {name} strength with more challenging questions."
        quantity = 5
    elif status == "Good progress":
        action = "Practice 5 more questions"
        focus = f"Keep building consistency in {name}."
        quantity = 5
    elif status == "Needs improvement":
        action = f"Practice 10 {name} questions"
        focus = f"Revise your weaker {name} topics, then complete a focused practice set."
        quantity = 10
    else:
        action = f"Practice 15 {name} questions"
        focus = f"Review {name} fundamentals and practice the weakest topics first."
        quantity = 15

    recommended_topics = [
        {
            "name": topic["name"],
            "performance": topic["accuracy"],
            "attempted": topic["attempted"],
            "priority": _priority_for(topic["accuracy"])[0],
            "url": (
                _coding_url()
                if is_coding
                else _topic_url(topic["category"], topic["name"])
            ),
        }
        for topic in weak_topics
        if topic["accuracy"] < THRESHOLDS["medium"]
    ][:3]

    url = _coding_url() if is_coding else _practice_url()
    if recommended_topics:
        focus += " Start with " + ", ".join(
            topic["name"] for topic in recommended_topics
        ) + "."
        if not is_coding:
            url = recommended_topics[0]["url"]

    return {
        "name": name,
        "performance": performance,
        "attempted": attempted,
        "priority": priority,
        "status": status,
        "recommendation": action,
        "focus": focus,
        "practice_quantity": quantity,
        "url": url,
        "is_coding": is_coding,
        "weak_topics": recommended_topics,
    }


def get_recommendations(
    user: Any,
    *,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return rule-based study recommendations from canonical user metrics."""
    if metrics is None:
        metrics = get_performance_metrics(user)
    category_totals: dict[str, dict[str, int]] = {}

    def add_category(name: str, attempted: int, solved: int) -> None:
        group = _category_for_name(name)
        if not group:
            return
        totals = category_totals.setdefault(group, {"attempted": 0, "solved": 0})
        totals["attempted"] += attempted
        totals["solved"] += solved

    for item in metrics["category_performance"]:
        add_category(item["name"], item["attempted"], item["correct"])
    for item in metrics["coding_category_performance"]:
        if _category_for_name(item["name"]) != "Coding":
            add_category(item["name"], item["attempted"], item["solved"])
    if metrics["coding_problems_attempted"]:
        category_totals["Coding"] = {
            "attempted": metrics["coding_problems_attempted"],
            "solved": metrics["coding_problems_solved"],
        }

    topics_by_category: dict[str, list[dict[str, Any]]] = {}
    for topic in metrics["topic_performance"]:
        group = _category_for_name(topic["category"])
        if group:
            topics_by_category.setdefault(group, []).append(topic)
    for topic in metrics["coding_topic_performance"]:
        group = _category_for_name(topic["category"])
        topics_by_category.setdefault("Coding", []).append(topic)
        if group:
            if group != "Coding":
                topics_by_category.setdefault(group, []).append(topic)

    recommendations = []
    for name, totals in category_totals.items():
        attempted = totals["attempted"]
        if not attempted:
            continue
        performance = percentage(totals["solved"], attempted)
        recommendations.append(
            _recommendation_for_area(
                name,
                performance,
                attempted,
                is_coding=name == "Coding",
                weak_topics=topics_by_category.get(name, []),
            )
        )

    if recommendations and metrics["tests_completed"] == 0:
        recommendations.append({
            "name": "Mock tests",
            "performance": None,
            "attempted": 0,
            "priority": "MEDIUM",
            "status": "No completed tests yet",
            "recommendation": "Attempt a mock test",
            "focus": "Take a timed assessment to practice pacing and identify areas to review.",
            "practice_quantity": 1,
            "url": reverse("mock_tests"),
            "is_coding": False,
            "weak_topics": [],
        })

    recommendations.sort(
        key=lambda item: (
            _PRIORITY_ORDER[item["priority"]],
            item["performance"] if item["performance"] is not None else 101,
            item["name"].casefold(),
        )
    )

    return {
        "has_data": bool(recommendations),
        "message": (
            ""
            if recommendations
            else "Complete a few practice questions and mock tests to receive personalized recommendations."
        ),
        "recommendations": recommendations,
    }
