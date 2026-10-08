"""Canonical, user-scoped performance metrics shared by dashboard and analytics."""

from collections import defaultdict

from django.utils import timezone

from core.models import (
    AptitudeQuestionAttempt,
    CodingAttempt,
    CodingSubmission,
    MockTestAttempt,
    QuestionAttempt,
    TestAnswer,
    TestAttempt,
)


def percentage(numerator, denominator):
    return round(numerator * 100 / denominator, 1) if denominator else 0.0


def _local_date(value):
    if value is None:
        return None
    if timezone.is_aware(value):
        return timezone.localtime(value).date()
    return value.date()


def get_performance_metrics(user):
    """Return all canonical performance counts and breakdowns for one user.

    Preparation score is the arithmetic mean of available components:
    question accuracy, unique-problem coding success rate, and the average
    percentage score of completed timed tests with a positive maximum mark.
    Components without recorded data are omitted; with no available
    components, the score is 0.
    """
    topic_totals = defaultdict(lambda: {"attempted": 0, "correct": 0})
    category_totals = defaultdict(lambda: {"attempted": 0, "correct": 0})
    question_records = []

    def record_question(category_name, topic_name, is_correct, attempted_at):
        was_correct = bool(is_correct)
        activity_date = _local_date(attempted_at)
        category_totals[category_name]["attempted"] += 1
        category_totals[category_name]["correct"] += int(was_correct)
        topic_totals[(category_name, topic_name)]["attempted"] += 1
        topic_totals[(category_name, topic_name)]["correct"] += int(was_correct)
        question_records.append({
            "category": category_name,
            "topic": topic_name,
            "is_correct": was_correct,
            "activity_date": activity_date,
        })

    for attempt in (
        QuestionAttempt.objects.filter(user=user)
        .select_related("question")
        .only("is_correct", "attempted_at", "question__category")
    ):
        record_question(
            attempt.question.category,
            attempt.question.category,
            attempt.is_correct,
            attempt.attempted_at,
        )

    for attempt in (
        AptitudeQuestionAttempt.objects.filter(user=user)
        .select_related("question__topic__category")
        .only(
            "is_correct",
            "attempted_at",
            "question__topic__name",
            "question__topic__category__name",
        )
    ):
        record_question(
            attempt.question.topic.category.name,
            attempt.question.topic.name,
            attempt.is_correct,
            attempt.attempted_at,
        )

    completed_attempts = list(
        TestAttempt.objects.filter(
            user=user,
            status__in=[TestAttempt.Status.SUBMITTED, TestAttempt.Status.EXPIRED],
        ).only("pk", "status", "score", "total_marks", "submitted_at")
    )
    completed_attempt_ids = [attempt.pk for attempt in completed_attempts]
    completed_test_dates = [
        _local_date(attempt.submitted_at)
        for attempt in completed_attempts
        if attempt.submitted_at is not None
    ]
    for answer in (
        TestAnswer.objects.filter(
            attempt_id__in=completed_attempt_ids,
            selected_option__isnull=False,
        )
        .select_related(
            "attempt",
            "test_question__question__topic__category",
            "test_question__question__topic",
        )
        .only(
            "is_correct",
            "updated_at",
            "attempt__submitted_at",
            "test_question__question__topic__name",
            "test_question__question__topic__category__name",
        )
    ):
        question = answer.test_question.question
        record_question(
            question.topic.category.name,
            question.topic.name,
            answer.is_correct,
            answer.attempt.submitted_at or answer.updated_at,
        )

    questions_attempted = len(question_records)
    questions_solved = sum(record["is_correct"] for record in question_records)
    accuracy = percentage(questions_solved, questions_attempted)

    coding_attempts = CodingAttempt.objects.filter(user=user)
    coding_submissions = CodingSubmission.objects.filter(user=user)
    attempted_problem_ids = set(coding_attempts.values_list("problem_id", flat=True))
    attempted_problem_ids.update(coding_submissions.values_list("problem_id", flat=True))
    solved_problem_ids = set(
        coding_attempts.filter(passed=True).values_list("problem_id", flat=True)
    )
    solved_problem_ids.update(
        coding_submissions.filter(status=CodingSubmission.Status.ACCEPTED)
        .values_list("problem_id", flat=True)
    )
    coding_problems_attempted = len(attempted_problem_ids)
    coding_problems_solved = len(solved_problem_ids)
    coding_success_rate = percentage(coding_problems_solved, coding_problems_attempted)

    legacy_test_attempts = MockTestAttempt.objects.filter(user=user)
    tests_completed = legacy_test_attempts.count() + len(completed_attempts)
    timed_test_percentages = [
        attempt.score * 100 / attempt.total_marks
        for attempt in completed_attempts
        if attempt.total_marks and attempt.total_marks > 0
    ]
    timed_test_average = (
        round(sum(timed_test_percentages) / len(timed_test_percentages), 1)
        if timed_test_percentages
        else None
    )

    score_components = []
    if questions_attempted:
        score_components.append(accuracy)
    if coding_problems_attempted:
        score_components.append(coding_success_rate)
    if timed_test_average is not None:
        score_components.append(timed_test_average)
    preparation_score = (
        round(sum(score_components) / len(score_components), 1)
        if score_components
        else 0.0
    )

    topics = [
        {
            "name": name,
            "topic": name,
            "category": category_name,
            "attempted": totals["attempted"],
            "correct": totals["correct"],
            "solved": totals["correct"],
            "accuracy": percentage(totals["correct"], totals["attempted"]),
            "mastery_score": percentage(totals["correct"], totals["attempted"]),
        }
        for (category_name, name), totals in topic_totals.items()
    ]
    topics.sort(
        key=lambda item: (
            -item["accuracy"],
            -item["attempted"],
            item["category"].lower(),
            item["name"].lower(),
        )
    )
    weak_topics = sorted(
        topics,
        key=lambda item: (
            item["accuracy"],
            -item["attempted"],
            item["category"].lower(),
            item["name"].lower(),
        ),
    )
    categories = [
        {
            "name": name,
            "attempted": totals["attempted"],
            "correct": totals["correct"],
            "accuracy": percentage(totals["correct"], totals["attempted"]),
        }
        for name, totals in category_totals.items()
    ]
    categories.sort(key=lambda item: item["name"].lower())

    return {
        "questions_attempted": questions_attempted,
        "questions_solved": questions_solved,
        "accuracy": accuracy,
        "coding_problems_attempted": coding_problems_attempted,
        "coding_problems_solved": coding_problems_solved,
        "coding_success_rate": coding_success_rate,
        "tests_completed": tests_completed,
        "timed_test_average": timed_test_average,
        "overall_preparation_score": preparation_score,
        "category_performance": categories,
        "topic_performance": topics,
        "strong_topics": topics[:3],
        "weak_topics": weak_topics[:3],
        "question_records": question_records,
        "completed_test_dates": completed_test_dates,
        "legacy_test_dates": list(legacy_test_attempts.values_list("completed_at", flat=True)),
    }
