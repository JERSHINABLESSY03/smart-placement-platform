import json
import mimetypes
from datetime import timedelta
from pathlib import Path

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import DatabaseError, connection
from django.http import FileResponse, Http404, JsonResponse
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .forms import (
    AIChatForm,
    AptitudeAnswerForm,
    CodingSubmissionForm,
    EmailAuthenticationForm,
    ProfileForm,
    QuestionAnswerForm,
    StudentRegistrationForm,
)
from .models import (
    AIConversation,
    AIMessage,
    AptitudeCategory,
    AptitudeQuestion,
    AptitudeQuestionAttempt,
    AptitudeTopic,
    CodingAttempt,
    CodingProblem,
    CodingSubmission,
    CodingTopic,
    MockTest,
    MockTestAttempt,
    Question,
    QuestionAttempt,
    StudentActivity,
    StudentProfile,
    Test,
    TestAnswer,
    TestAttempt,
    TestQuestion,
    TopicProgress,
)
from .services.analytics_service import get_performance_analytics
from .services.coding_service import record_submission
from .services.dashboard_service import get_dashboard_summary
from .services.gemini_service import GeminiService, GeminiServiceError
from .services.performance_metrics import get_performance_metrics
from .services.test_engine import (
    AttemptUnavailableError,
    TestUnavailableError,
    finalize_attempt,
    get_attempt_performance,
    get_test_questions,
    save_test_answer,
    start_test,
)


def home(request):
    return render(request, "core/home.html")


@require_GET
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({"status": "unhealthy", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})


def register(request):
    if request.method == "POST":
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password1"]
            full_name = form.cleaned_data["full_name"].strip()

            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=full_name.split()[0] if full_name else email,
            )

            StudentProfile.objects.create(
                user=user,
                full_name=full_name,
                college=form.cleaned_data["college"].strip(),
                degree=form.cleaned_data["degree"].strip(),
                department=form.cleaned_data["department"].strip(),
                graduation_year=form.cleaned_data["graduation_year"],
            )

            StudentActivity.objects.create(
                user=user,
                title="Account created",
                detail="Welcome to the platform. Start your placement prep journey.",
            )

            login(request, user)
            messages.success(request, "Registration successful. Your profile is ready.")
            return redirect("dashboard")
        messages.error(request, "Please correct the highlighted errors and try again.")
    else:
        form = StudentRegistrationForm()

    return render(request, "core/register.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = EmailAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, "You have been logged in successfully.")
            return redirect("dashboard")
        messages.error(request, "Invalid email or password.")
    else:
        form = EmailAuthenticationForm()
    return render(request, "core/login.html", {"form": form})


@require_POST
@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("home")


@login_required
def profile_file(request, file_kind):
    profile = StudentProfile.objects.filter(user=request.user).first()
    file_field = {
        "resume": profile.resume if profile else None,
        "profile_picture": profile.profile_picture if profile else None,
    }.get(file_kind)
    if not file_field or not file_field.name:
        raise Http404("File not found.")

    content_type = (
        "application/pdf"
        if file_kind == "resume"
        else mimetypes.guess_type(file_field.name)[0] or "application/octet-stream"
    )
    response = FileResponse(
        file_field.open("rb"),
        as_attachment=file_kind == "resume",
        filename=Path(file_field.name).name,
        content_type=content_type,
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response


@login_required
def dashboard(request):
    user = request.user
    profile = StudentProfile.objects.filter(user=user).first()
    if not profile:
        profile = StudentProfile.objects.create(
            user=user,
            full_name=user.get_full_name() or user.username,
        )

    context = get_dashboard_summary(user)
    context["profile"] = profile
    return render(request, "core/dashboard.html", context)


@login_required
def profile_view(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    if not profile:
        profile = StudentProfile.objects.create(
            user=request.user,
            full_name=request.user.get_full_name() or request.user.username,
        )
    return render(request, "core/profile.html", {"profile": profile})


@login_required
def profile_edit(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    if not profile:
        profile = StudentProfile.objects.create(
            user=request.user,
            full_name=request.user.get_full_name() or request.user.username,
        )

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            if request.user.get_full_name() != form.cleaned_data["full_name"]:
                request.user.first_name = form.cleaned_data["full_name"].split()[0]
                request.user.last_name = " ".join(form.cleaned_data["full_name"].split()[1:])
                request.user.save(update_fields=["first_name", "last_name"])
            messages.success(request, "Profile updated successfully.")
            return redirect("profile")
        messages.error(request, "There were some problems with your profile details.")
    else:
        form = ProfileForm(instance=profile)
    return render(request, "core/profile_edit.html", {"form": form})


@login_required
def practice_dashboard(request):
    categories = AptitudeCategory.objects.filter(is_active=True).annotate(
        topic_count=Count("topics", filter=Q(topics__is_active=True), distinct=True),
        question_count=Count(
            "topics__questions",
            filter=Q(topics__is_active=True, topics__questions__is_active=True),
            distinct=True,
        ),
    )
    attempts = AptitudeQuestionAttempt.objects.filter(user=request.user)
    return render(
        request,
        "core/practice.html",
        {
            "categories": categories,
            "total_attempts": attempts.count(),
            "total_correct": attempts.filter(is_correct=True).count(),
            "overall_accuracy": round(
                attempts.filter(is_correct=True).count() * 100 / attempts.count(),
                1,
            ) if attempts.exists() else 0,
        },
    )


def _topic_performance(user, topic):
    summary = AptitudeQuestionAttempt.objects.filter(
        user=user,
        question__topic=topic,
    ).aggregate(
        attempts=Count("pk"),
        correct=Count("pk", filter=Q(is_correct=True)),
        score=Sum("marks_awarded"),
        time_spent=Sum("time_taken_seconds"),
    )
    attempts = summary["attempts"] or 0
    correct = summary["correct"] or 0
    return {
        "attempts": attempts,
        "correct": correct,
        "accuracy": round(correct * 100 / attempts, 1) if attempts else 0,
        "score": summary["score"] or 0,
        "time_spent": summary["time_spent"] or 0,
    }


@login_required
def aptitude_category(request, category_slug):
    category = get_object_or_404(AptitudeCategory, slug=category_slug, is_active=True)
    topics = category.topics.filter(is_active=True).annotate(
        question_count=Count("questions", filter=Q(questions__is_active=True), distinct=True),
    )
    topic_summaries = []
    for topic in topics:
        topic_summaries.append(
            {
                "topic": topic,
                "performance": _topic_performance(request.user, topic),
            }
        )
    return render(
        request,
        "core/aptitude_category.html",
        {"category": category, "topic_summaries": topic_summaries},
    )


@login_required
def aptitude_topic(request, category_slug, topic_slug):
    topic = get_object_or_404(
        AptitudeTopic.objects.select_related("category"),
        slug=topic_slug,
        is_active=True,
        category__is_active=True,
        category__slug=category_slug,
    )
    questions = topic.questions.filter(is_active=True).annotate(
        attempts_count=Count("attempts", filter=Q(attempts__user=request.user)),
        correct_count=Count(
            "attempts",
            filter=Q(attempts__user=request.user, attempts__is_correct=True),
        ),
    )
    return render(
        request,
        "core/aptitude_topic.html",
        {
            "topic": topic,
            "questions": questions,
            "performance": _topic_performance(request.user, topic),
        },
    )


@login_required
def aptitude_question(request, question_id):
    question = get_object_or_404(
        AptitudeQuestion.objects.select_related("topic__category").prefetch_related("options"),
        pk=question_id,
        is_active=True,
        topic__is_active=True,
        topic__category__is_active=True,
    )
    timer_key = f"aptitude_question_started_{question.pk}"

    if request.method == "POST":
        form = AptitudeAnswerForm(request.POST, question=question)
        if form.is_valid():
            selected_option = form.cleaned_data["selected_option"]
            is_correct = selected_option.is_correct
            started_at = request.session.pop(timer_key, None)
            time_taken_seconds = 0
            if started_at is not None:
                time_taken_seconds = max(0, int(timezone.now().timestamp() - started_at))
            attempt = AptitudeQuestionAttempt.objects.create(
                user=request.user,
                question=question,
                selected_option=selected_option,
                is_correct=is_correct,
                marks_awarded=question.marks if is_correct else 0,
                time_taken_seconds=time_taken_seconds,
            )
            StudentActivity.objects.create(
                user=request.user,
                title="Aptitude question attempted",
                detail=f"{question.topic.category.name} / {question.topic.name}: "
                f"{'correct answer' if is_correct else 'incorrect answer'}",
            )
            return redirect("aptitude_attempt_result", attempt_id=attempt.pk)
    else:
        form = AptitudeAnswerForm(question=question)
        request.session[timer_key] = timezone.now().timestamp()

    return render(
        request,
        "core/aptitude_question.html",
        {"question": question, "form": form},
    )


@login_required
def aptitude_attempt_result(request, attempt_id):
    attempt = get_object_or_404(
        AptitudeQuestionAttempt.objects.select_related(
            "question__topic__category",
            "selected_option",
        ),
        pk=attempt_id,
        user=request.user,
    )
    performance = _topic_performance(request.user, attempt.question.topic)
    return render(
        request,
        "core/aptitude_result.html",
        {"attempt": attempt, "performance": performance},
    )


@login_required
def question_practice(request, category):
    questions = Question.objects.filter(category=category).order_by("difficulty")
    current_question = questions.first()
    form = QuestionAnswerForm()

    if request.method == "POST":
        question_id = request.POST.get("question_id")
        selected_option = request.POST.get("selected_option")
        question = get_object_or_404(Question, id=question_id)
        is_correct = selected_option == question.correct_option

        QuestionAttempt.objects.create(user=request.user, question=question, selected_option=selected_option or "", is_correct=is_correct)
        StudentActivity.objects.create(user=request.user, title="Question attempted", detail=f"{question.category} practice: {question.question_text[:80]}")

        topic_progress, _ = TopicProgress.objects.get_or_create(user=request.user, topic=question.category, defaults={"category": question.category})
        topic_progress.attempts += 1
        if is_correct:
            topic_progress.solved += 1
        if topic_progress.attempts:
            topic_progress.accuracy = (topic_progress.solved / topic_progress.attempts) * 100
        topic_progress.mastery_score = min(100, int(topic_progress.accuracy))
        topic_progress.last_practiced = timezone.now()
        topic_progress.save()

        messages.success(request, "Answer recorded. Review the explanation below to improve your understanding.")
        return redirect("question_practice", category=category)

    return render(request, "core/question_practice.html", {"category": category, "questions": questions, "current_question": current_question, "form": form})


@login_required
def coding_practice(request):
    topics = CodingTopic.objects.filter(is_active=True).annotate(
        problem_count=Count("problems", filter=Q(problems__is_active=True), distinct=True),
    )
    problems = CodingProblem.objects.filter(
        is_active=True,
        topic__is_active=True,
    ).select_related("topic")
    topic_slug = request.GET.get("topic", "").strip()
    difficulty = request.GET.get("difficulty", "").strip()
    if topic_slug:
        problems = problems.filter(topic__slug=topic_slug)
    if difficulty in CodingProblem.Difficulty.values:
        problems = problems.filter(difficulty=difficulty)

    user_attempts = CodingAttempt.objects.filter(user=request.user)
    accepted_submissions = CodingSubmission.objects.filter(
        user=request.user,
        status=CodingSubmission.Status.ACCEPTED,
    )
    attempted_problem_ids = user_attempts.values_list("problem_id", flat=True).distinct()
    solved_problem_ids = set(user_attempts.filter(passed=True).values_list("problem_id", flat=True))
    solved_problem_ids.update(accepted_submissions.values_list("problem_id", flat=True))
    topic_performance = []
    difficulty_performance = []
    for topic in topics:
        topic_attempts = user_attempts.filter(problem__topic=topic)
        solved_count = len(
            solved_problem_ids.intersection(
                topic.problems.values_list("pk", flat=True)
            )
        )
        attempted_count = topic_attempts.values("problem_id").distinct().count()
        topic_performance.append(
            {
                "topic": topic,
                "attempted": attempted_count,
                "solved": solved_count,
            }
        )
    for difficulty_value, difficulty_label in CodingProblem.Difficulty.choices:
        difficulty_problems = CodingProblem.objects.filter(difficulty=difficulty_value)
        difficulty_attempts = user_attempts.filter(problem__difficulty=difficulty_value)
        difficulty_solved_ids = solved_problem_ids.intersection(
            difficulty_problems.values_list("pk", flat=True)
        )
        difficulty_performance.append(
            {
                "label": difficulty_label,
                "attempted": difficulty_attempts.values("problem_id").distinct().count(),
                "solved": len(difficulty_solved_ids),
            }
        )

    recent_submissions = CodingSubmission.objects.filter(user=request.user).select_related(
        "problem",
        "problem__topic",
    )[:8]
    context = {
        "topics": topics,
        "topic_performance": topic_performance,
        "difficulty_performance": difficulty_performance,
        "problems": problems,
        "selected_topic": topic_slug,
        "selected_difficulty": difficulty,
        "problems_attempted": len(set(attempted_problem_ids)),
        "problems_solved": len(solved_problem_ids),
        "recent_submissions": recent_submissions,
        "difficulty_choices": CodingProblem.Difficulty.choices,
    }
    return render(request, "core/coding.html", context)


@login_required
def coding_problem_detail(request, slug):
    problem = get_object_or_404(
        CodingProblem.objects.select_related("topic"),
        slug=slug,
        is_active=True,
        topic__is_active=True,
    )
    if request.method == "POST":
        form = CodingSubmissionForm(request.POST)
        if form.is_valid():
            submission = record_submission(
                user=request.user,
                problem=problem,
                language=form.cleaned_data["language"],
                source_code=form.cleaned_data["source_code"],
            )
            return redirect("coding_submission_result", submission_id=submission.pk)
    else:
        form = CodingSubmissionForm(initial={"source_code": problem.starter_code})

    return render(
        request,
        "core/coding_problem.html",
        {
            "problem": problem,
            "form": form,
            "sample_cases": [
                {"input": problem.sample_input, "output": problem.sample_output}
            ] if problem.sample_input or problem.sample_output else [],
            "problem_attempts": CodingAttempt.objects.filter(
                user=request.user,
                problem=problem,
            ).count(),
        },
    )


@login_required
def coding_submission_result(request, submission_id):
    submission = get_object_or_404(
        CodingSubmission.objects.select_related("problem", "problem__topic"),
        pk=submission_id,
        user=request.user,
    )
    return render(
        request,
        "core/coding_submission_result.html",
        {"submission": submission},
    )


@login_required
def mock_tests(request):
    if request.method == "POST":
        test_id = request.POST.get("test_id")
        try:
            attempt = start_test(request.user, test_id)
        except (TestUnavailableError, ValueError, TypeError) as error:
            messages.error(request, str(error) or "This test is unavailable.")
            return redirect("mock_tests")
        return redirect("test_attempt", attempt_id=attempt.pk)

    tests = (
        Test.objects.filter(is_published=True)
        .annotate(
            question_count=Count(
                "test_questions",
                filter=Q(
                    test_questions__question__is_active=True,
                    test_questions__question__topic__is_active=True,
                    test_questions__question__topic__category__is_active=True,
                ),
                distinct=True,
            ),
        )
        .prefetch_related("test_questions__question__topic__category")
    )
    active_attempts = {}
    for attempt in TestAttempt.objects.filter(
        user=request.user,
        status=TestAttempt.Status.IN_PROGRESS,
    ).select_related("test"):
        if timezone.now() >= attempt.deadline_at:
            finalize_attempt(attempt, expired=True)
        else:
            active_attempts[attempt.test_id] = attempt
    test_cards = []
    for test in tests:
        if test.question_count == 0:
            continue
        questions = get_test_questions(test)
        categories = sorted({item.question.topic.category.name for item in questions})
        total_marks = sum(item.marks for item in questions)
        test_cards.append(
            {
                "test": test,
                "question_count": len(questions),
                "total_marks": total_marks,
                "categories": categories,
                "active_attempt": active_attempts.get(test.pk),
            }
        )
    history = (
        TestAttempt.objects.filter(
            user=request.user,
            status__in=[TestAttempt.Status.SUBMITTED, TestAttempt.Status.EXPIRED],
        )
        .select_related("test")
        .order_by("-submitted_at")[:10]
    )
    return render(request, "core/mock_tests.html", {"test_cards": test_cards, "history": history})


@login_required
def test_attempt(request, attempt_id):
    attempt = get_object_or_404(
        TestAttempt.objects.select_related("test"),
        pk=attempt_id,
        user=request.user,
    )
    if attempt.status != TestAttempt.Status.IN_PROGRESS:
        return redirect("test_result", attempt_id=attempt.pk)
    if timezone.now() >= attempt.deadline_at:
        finalize_attempt(attempt, expired=True)
        return redirect("test_result", attempt_id=attempt.pk)

    questions = get_test_questions(attempt.test)
    answer_map = {
        answer.test_question_id: answer
        for answer in TestAnswer.objects.filter(attempt=attempt).select_related("selected_option")
    }
    for item in questions:
        saved_answer = answer_map.get(item.pk)
        item.saved_option_id = saved_answer.selected_option_id if saved_answer else None
        item.marked_for_review = saved_answer.marked_for_review if saved_answer else False
    return render(
        request,
        "core/test_attempt.html",
        {
            "attempt": attempt,
            "test_questions": questions,
            "answer_map": answer_map,
            "deadline_iso": attempt.deadline_at.isoformat(),
        },
    )


@login_required
def save_test_answer_view(request, attempt_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST is required."}, status=405)
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON request."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Request data must be an object."}, status=400)
    test_question_id = payload.get("test_question_id")
    selected_option_id = payload.get("selected_option_id")
    marked_for_review = payload.get("marked_for_review", False)
    if not isinstance(test_question_id, int) or isinstance(test_question_id, bool):
        return JsonResponse({"error": "A valid test question is required."}, status=400)
    if not isinstance(marked_for_review, bool):
        return JsonResponse({"error": "Review status must be a boolean."}, status=400)
    if selected_option_id not in (None, "") and (
        isinstance(selected_option_id, bool)
        or not isinstance(selected_option_id, (int, str))
        or not str(selected_option_id).isdigit()
    ):
        return JsonResponse({"error": "A valid answer choice is required."}, status=400)

    try:
        answer = save_test_answer(
            user=request.user,
            attempt_id=attempt_id,
            test_question_id=test_question_id,
            selected_option_id=selected_option_id,
            marked_for_review=marked_for_review,
        )
    except AttemptUnavailableError as error:
        attempt = TestAttempt.objects.filter(pk=attempt_id, user=request.user).first()
        status_code = 404 if attempt is None else 409
        return JsonResponse({"error": str(error)}, status=status_code)
    if answer is None:
        return JsonResponse(
            {"error": "Time has expired. Your test was submitted automatically."},
            status=409,
        )
    return JsonResponse(
        {
            "saved": True,
            "selected_option_id": answer.selected_option_id,
            "marked_for_review": answer.marked_for_review,
        }
    )


@login_required
def submit_test_attempt(request, attempt_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST is required."}, status=405)
    attempt = get_object_or_404(
        TestAttempt.objects.select_related("test"),
        pk=attempt_id,
        user=request.user,
    )
    if attempt.status == TestAttempt.Status.IN_PROGRESS:
        expired = timezone.now() >= attempt.deadline_at
        finalize_attempt(attempt, expired=expired)
        attempt.refresh_from_db()
    return JsonResponse(
        {
            "submitted": True,
            "status": attempt.status,
            "result_url": redirect("test_result", attempt_id=attempt.pk).url,
        }
    )


@login_required
def test_result(request, attempt_id):
    attempt = get_object_or_404(
        TestAttempt.objects.select_related("test"),
        pk=attempt_id,
        user=request.user,
    )
    if attempt.status == TestAttempt.Status.IN_PROGRESS:
        if timezone.now() >= attempt.deadline_at:
            finalize_attempt(attempt, expired=True)
            attempt.refresh_from_db()
        else:
            return redirect("test_attempt", attempt_id=attempt.pk)
    answers = (
        TestAnswer.objects.filter(attempt=attempt)
        .select_related(
            "test_question__question__topic__category",
            "selected_option",
            "correct_option",
        )
        .prefetch_related("test_question__question__options")
        .order_by("test_question__position")
    )
    return render(
        request,
        "core/test_result.html",
        {
            "attempt": attempt,
            "answers": answers,
            "performance": get_attempt_performance(attempt),
        },
    )


@login_required
def analytics(request):
    return render(
        request,
        "core/analytics.html",
        {"analytics": get_performance_analytics(request.user)},
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_api(request):
    return Response(get_performance_analytics(request.user))


@login_required
def ai_assistant(request):
    return render(
        request,
        "core/ai_assistant.html",
        {
            "form": AIChatForm(),
            "conversation_api_url": reverse("ai_conversations_api"),
            "messages_api_url": reverse("ai_messages_api", args=[0]),
            "delete_api_url": reverse("ai_conversation_delete_api", args=[0]),
        },
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def ai_conversations_api(request):
    if request.method == "GET":
        conversations = AIConversation.objects.filter(user=request.user).values(
            "id",
            "title",
            "updated_at",
        )[:50]
        return Response(
            [
                {
                    "id": item["id"],
                    "title": item["title"],
                    "updated_at": item["updated_at"],
                }
                for item in conversations
            ]
        )

    conversation = AIConversation.objects.create(
        user=request.user,
        title="New conversation",
    )
    return Response(
        {"id": conversation.pk, "title": conversation.title},
        status=201,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def ai_messages_api(request, conversation_id):
    conversation = get_object_or_404(
        AIConversation,
        pk=conversation_id,
        user=request.user,
    )
    if request.method == "GET":
        message_data = conversation.messages.values(
            "id",
            "role",
            "content",
            "mode",
            "created_at",
        )
        return Response(list(message_data))

    form = AIChatForm(request.data)
    if not form.is_valid():
        return Response({"errors": form.errors.get_json_data()}, status=400)

    now = timezone.now()
    recent_message_count = AIMessage.objects.filter(
        conversation__user=request.user,
        role=AIMessage.Role.USER,
        created_at__gte=now - timedelta(seconds=60),
    ).count()
    if recent_message_count >= 5:
        return Response(
            {"error": "You have reached the tutor limit of 5 messages per minute. Please wait and try again."},
            status=429,
        )

    prompt = form.cleaned_data["prompt"]
    mode = form.cleaned_data["mode"]
    user_message = AIMessage.objects.create(
        conversation=conversation,
        role=AIMessage.Role.USER,
        content=prompt,
        mode=mode,
    )
    if conversation.title == "New conversation":
        conversation.title = prompt[:117] + ("..." if len(prompt) > 120 else "")
    conversation.save(update_fields=["title", "updated_at"])

    previous_messages = list(
        conversation.messages.exclude(pk=user_message.pk)
        .order_by("-created_at", "-pk")
        .values("role", "content")[:12]
    )
    previous_messages.reverse()
    try:
        reply = GeminiService.generate_reply(
            mode=mode,
            prompt=prompt,
            history=previous_messages,
        )
    except GeminiServiceError as exc:
        return Response(
            {"error": str(exc)},
            status=getattr(exc, "status_code", 503),
        )

    assistant_message = AIMessage.objects.create(
        conversation=conversation,
        role=AIMessage.Role.ASSISTANT,
        content=reply,
    )
    conversation.save(update_fields=["updated_at"])
    return Response(
        {
            "conversation": {
                "id": conversation.pk,
                "title": conversation.title,
                "updated_at": conversation.updated_at,
            },
            "messages": [
                {
                    "id": user_message.pk,
                    "role": user_message.role,
                    "content": user_message.content,
                    "mode": user_message.mode,
                    "created_at": user_message.created_at,
                },
                {
                    "id": assistant_message.pk,
                    "role": assistant_message.role,
                    "content": assistant_message.content,
                    "mode": assistant_message.mode,
                    "created_at": assistant_message.created_at,
                },
            ],
        },
        status=201,
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def ai_conversation_delete_api(request, conversation_id):
    conversation = get_object_or_404(
        AIConversation,
        pk=conversation_id,
        user=request.user,
    )
    conversation.delete()
    return Response(status=204)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_api(request):
    user = request.user
    metrics = get_performance_metrics(user)
    data = {
        "name": user.first_name or user.username,
        "questions_attempted": metrics["questions_attempted"],
        "questions_solved": metrics["questions_solved"],
        "accuracy": metrics["accuracy"],
        "overall_preparation_score": metrics["overall_preparation_score"],
        "tests_completed": metrics["tests_completed"],
        "coding_problems_attempted": metrics["coding_problems_attempted"],
        "coding_problems_solved": metrics["coding_problems_solved"],
        "coding_success_rate": metrics["coding_success_rate"],
        "category_performance": [
            {
                "name": item["name"],
                "attempted": item["attempted"],
                "correct": item["correct"],
                "accuracy": item["accuracy"],
            }
            for item in metrics["category_performance"]
        ],
        "topic_performance": [
            {
                "name": item["name"],
                "category": item["category"],
                "attempted": item["attempted"],
                "correct": item["correct"],
                "accuracy": item["accuracy"],
            }
            for item in metrics["topic_performance"]
        ],
    }
    return Response(data)
