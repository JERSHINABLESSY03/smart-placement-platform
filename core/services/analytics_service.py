from datetime import timedelta

from django.utils import timezone

from core.models import MockTestAttempt, TestAttempt
from core.services.performance_metrics import get_performance_metrics, percentage


def get_performance_analytics(user, now=None, metrics=None):
    now = now or timezone.now()
    start_date = now.date() - timedelta(days=6)
    if metrics is None:
        metrics = get_performance_metrics(user)
    weekly_totals = {
        start_date + timedelta(days=offset): {"attempted": 0, "correct": 0, "tests": 0}
        for offset in range(7)
    }

    for record in metrics["question_records"]:
        activity_date = record["activity_date"]
        if activity_date in weekly_totals:
            weekly_totals[activity_date]["attempted"] += 1
            weekly_totals[activity_date]["correct"] += int(record["is_correct"])

    for activity_date in metrics["completed_test_dates"]:
        if activity_date in weekly_totals:
            weekly_totals[activity_date]["tests"] += 1
    for completed_at in metrics["legacy_test_dates"]:
        completed_date = timezone.localtime(completed_at).date()
        if completed_date in weekly_totals:
            weekly_totals[completed_date]["tests"] += 1

    recent_completed_test_attempts = list(
        TestAttempt.objects.filter(
            user=user,
            status__in=[TestAttempt.Status.SUBMITTED, TestAttempt.Status.EXPIRED],
            submitted_at__isnull=False,
        )
        .select_related("test")
        .order_by("-submitted_at")[:8]
    )
    legacy_test_attempts = list(
        MockTestAttempt.objects.filter(user=user)
        .select_related("test")
        .order_by("-completed_at")[:8]
    )

    weekly_progress = [
        {
            "date": day.isoformat(),
            "label": day.strftime("%a"),
            "attempted": totals["attempted"],
            "correct": totals["correct"],
            "accuracy": percentage(totals["correct"], totals["attempted"]),
            "tests": totals["tests"],
        }
        for day, totals in weekly_totals.items()
    ]
    recent_scores = [
        {
            "test": attempt.test.title,
            "score": attempt.score,
            "total_marks": attempt.total_marks,
            "percentage": (
                percentage(attempt.score, attempt.total_marks)
                if attempt.total_marks and attempt.total_marks > 0
                else None
            ),
            "submitted_at": timezone.localtime(attempt.submitted_at),
            "status": attempt.get_status_display(),
        }
        for attempt in recent_completed_test_attempts
    ]
    recent_scores.extend(
        {
            "test": attempt.test.title,
            "score": attempt.score,
            "total_marks": None,
            "percentage": None,
            "submitted_at": timezone.localtime(attempt.completed_at),
            "status": "Completed",
        }
        for attempt in legacy_test_attempts
    )
    recent_scores.sort(key=lambda item: item["submitted_at"], reverse=True)

    return {
        "overall_preparation_score": metrics["overall_preparation_score"],
        "accuracy": metrics["accuracy"],
        "questions_attempted": metrics["questions_attempted"],
        "questions_solved": metrics["questions_solved"],
        "mock_tests_completed": metrics["tests_completed"],
        "coding_problems_attempted": metrics["coding_problems_attempted"],
        "coding_problems_solved": metrics["coding_problems_solved"],
        "coding_success_rate": metrics["coding_success_rate"],
        "timed_test_average": metrics["timed_test_average"],
        "topic_performance": metrics["topic_performance"],
        "category_performance": metrics["category_performance"],
        "weekly_progress": weekly_progress,
        "recent_test_scores": recent_scores[:8],
        "strong_topics": metrics["strong_topics"],
        "weak_topics": metrics["weak_topics"],
    }
