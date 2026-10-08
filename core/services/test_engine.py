from datetime import timedelta

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from core.models import (
    AptitudeQuestionOption,
    Test,
    TestAnswer,
    TestAttempt,
    TestQuestion,
    StudentActivity,
)


class TestUnavailableError(Exception):
    pass


class AttemptUnavailableError(Exception):
    pass


def get_test_questions(test):
    return list(
        TestQuestion.objects.filter(
            test=test,
            question__is_active=True,
            question__topic__is_active=True,
            question__topic__category__is_active=True,
        )
        .select_related("question", "question__topic", "question__topic__category")
        .prefetch_related("question__options")
        .order_by("position")
    )


@transaction.atomic
def start_test(user, test_id):
    test = Test.objects.select_for_update().filter(pk=test_id, is_published=True).first()
    if test is None:
        raise TestUnavailableError("This test is not available.")

    questions = get_test_questions(test)
    if not questions:
        raise TestUnavailableError("This test has no active questions yet.")
    for item in questions:
        options = list(item.question.options.all())
        if len(options) != 4 or sum(option.is_correct for option in options) != 1:
            raise TestUnavailableError(
                "This test contains a question that is not configured with four choices and one correct answer."
            )

    active_attempt = (
        TestAttempt.objects.select_for_update()
        .filter(user=user, test=test, status=TestAttempt.Status.IN_PROGRESS)
        .order_by("-started_at")
        .first()
    )
    now = timezone.now()
    if active_attempt and active_attempt.deadline_at > now:
        return active_attempt
    if active_attempt:
        finalize_attempt(active_attempt, expired=True, now=now)

    duration_seconds = test.duration_minutes * 60
    attempt = TestAttempt.objects.create(
        user=user,
        test=test,
        started_at=now,
        deadline_at=now + timedelta(seconds=duration_seconds),
        duration_seconds=duration_seconds,
        total_questions=len(questions),
        total_marks=sum(item.marks for item in questions),
    )
    TestAnswer.objects.bulk_create(
        [
            TestAnswer(
                attempt=attempt,
                test_question=item,
                correct_option=next(
                    option for option in item.question.options.all() if option.is_correct
                ),
                marks_possible=item.marks,
            )
            for item in questions
        ]
    )
    return attempt


@transaction.atomic
def save_test_answer(user, attempt_id, test_question_id, selected_option_id, marked_for_review):
    attempt = (
        TestAttempt.objects.select_for_update()
        .filter(pk=attempt_id, user=user)
        .first()
    )
    if attempt is None:
        raise AttemptUnavailableError("Test attempt not found.")
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        raise AttemptUnavailableError("This test attempt is already closed.")
    now = timezone.now()
    if now >= attempt.deadline_at:
        finalize_attempt(attempt, expired=True, now=now)
        return None

    answer = (
        TestAnswer.objects.select_for_update()
        .filter(attempt=attempt, test_question_id=test_question_id)
        .select_related("test_question__question")
        .first()
    )
    if answer is None:
        raise AttemptUnavailableError("Question does not belong to this test attempt.")

    selected_option = None
    if selected_option_id not in (None, ""):
        try:
            selected_option = AptitudeQuestionOption.objects.get(
                pk=selected_option_id,
                question_id=answer.test_question.question_id,
            )
        except (AptitudeQuestionOption.DoesNotExist, ValueError, TypeError):
            raise AttemptUnavailableError("Choose an answer belonging to this question.")

    answer.selected_option = selected_option
    answer.marked_for_review = marked_for_review
    answer.save(update_fields=["selected_option", "marked_for_review", "updated_at"])
    return answer


@transaction.atomic
def finalize_attempt(attempt, expired=False, now=None):
    attempt = (
        TestAttempt.objects.select_for_update()
        .select_related("test")
        .get(pk=attempt.pk)
    )
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return attempt

    now = now or timezone.now()
    answers = list(
        TestAnswer.objects.select_for_update()
        .filter(attempt=attempt)
        .select_related("test_question__question")
        .prefetch_related(
            Prefetch(
                "test_question__question__options",
                queryset=AptitudeQuestionOption.objects.all(),
            )
        )
    )
    correct_count = 0
    wrong_count = 0
    score = 0
    for answer in answers:
        if answer.selected_option_id is None:
            answer.is_correct = None
            answer.marks_awarded = 0
        else:
            correct_option_id = answer.correct_option_id
            if correct_option_id is None:
                correct_option_id = next(
                    (
                        option.pk
                        for option in answer.test_question.question.options.all()
                        if option.is_correct
                    ),
                    None,
                )
            answer.is_correct = bool(
                correct_option_id
                and answer.selected_option_id == correct_option_id
            )
            if answer.is_correct:
                correct_count += 1
                answer.marks_awarded = (
                    answer.marks_possible
                    if answer.marks_possible is not None
                    else answer.test_question.marks
                )
                score += answer.marks_awarded
            else:
                wrong_count += 1
                answer.marks_awarded = 0

    if answers:
        TestAnswer.objects.bulk_update(answers, ["is_correct", "marks_awarded"])

    answered_count = correct_count + wrong_count
    attempt.score = score
    attempt.correct_count = correct_count
    attempt.wrong_count = wrong_count
    attempt.skipped_count = max(0, attempt.total_questions - answered_count)
    attempt.accuracy = round(correct_count * 100 / answered_count, 1) if answered_count else 0.0
    attempt.time_taken_seconds = min(
        attempt.duration_seconds,
        max(0, int((now - attempt.started_at).total_seconds())),
    )
    attempt.submitted_at = now
    attempt.status = (
        TestAttempt.Status.EXPIRED if expired else TestAttempt.Status.SUBMITTED
    )
    attempt.save(
        update_fields=[
            "score",
            "correct_count",
            "wrong_count",
            "skipped_count",
            "accuracy",
            "time_taken_seconds",
            "submitted_at",
            "status",
        ]
    )
    StudentActivity.objects.create(
        user=attempt.user,
        title="Mock test completed",
        detail=f"{attempt.test.title}: {attempt.score}/{attempt.total_marks}",
    )
    return attempt


def get_attempt_performance(attempt):
    rows = (
        TestAnswer.objects.filter(attempt=attempt)
        .select_related(
            "test_question__question__topic__category",
            "test_question__question__topic",
        )
        .order_by("test_question__position")
    )
    category_data = {}
    topic_data = {}
    for answer in rows:
        question = answer.test_question.question
        category_name = question.topic.category.name
        topic_name = question.topic.name
        for key, name, bucket in (
            ("category", category_name, category_data),
            ("topic", topic_name, topic_data),
        ):
            stats = bucket.setdefault(
                name,
                {"name": name, "total": 0, "answered": 0, "correct": 0, "marks": 0, "possible_marks": 0},
            )
            stats["total"] += 1
            stats["possible_marks"] += (
                answer.marks_possible
                if answer.marks_possible is not None
                else answer.test_question.marks
            )
            stats["marks"] += answer.marks_awarded
            if answer.selected_option_id:
                stats["answered"] += 1
            if answer.is_correct:
                stats["correct"] += 1

    for bucket in (category_data, topic_data):
        for stats in bucket.values():
            stats["accuracy"] = (
                round(stats["correct"] * 100 / stats["answered"], 1)
                if stats["answered"]
                else 0.0
            )
    return {
        "categories": sorted(category_data.values(), key=lambda item: item["name"]),
        "topics": sorted(topic_data.values(), key=lambda item: item["name"]),
    }
