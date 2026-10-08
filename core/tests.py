import json
import os
import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.test import Client, TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from .models import (
    AIConversation,
    AIMessage,
    AptitudeCategory,
    AptitudeQuestion,
    AptitudeQuestionAttempt,
    AptitudeQuestionOption,
    AptitudeTopic,
    CodingAttempt,
    CodingProblem,
    CodingSubmission,
    CodingTopic,
    MockTest,
    MockTestAttempt,
    Question,
    QuestionAttempt,
    Test as AssessmentTest,
    TestAnswer,
    TestAttempt,
    TestQuestion,
    StudentProfile,
)
from .services.analytics_service import get_performance_analytics
from .services.dashboard_service import get_dashboard_summary
from .services.gemini_service import GeminiService, GeminiServiceError


class HealthCheckTests(TestCase):
    def test_health_check_reports_database_readiness(self):
        response = self.client.get(reverse("health_check"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})

    @patch("core.views.connection.cursor", side_effect=OperationalError("database unavailable"))
    def test_health_check_returns_service_unavailable_if_database_is_down(self, _cursor):
        response = self.client.get(reverse("health_check"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"status": "unhealthy", "database": "unavailable"},
        )


class LogoutSecurityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="logoutstudent",
            email="logout@example.com",
            password="logout-password-123",
        )

    def test_authenticated_user_can_logout_with_post(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("home"))
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_get_logout_is_rejected_without_logging_user_out(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("logout"))

        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.client.session.get("_auth_user_id"), str(self.user.pk))

    def test_unauthenticated_logout_post_redirects_to_login(self):
        response = self.client.post(reverse("logout"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('logout')}",
        )

    def test_logout_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)

        response = client.post(reverse("logout"))

        self.assertEqual(response.status_code, 403)


class ProfileUploadSecurityTests(TestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.media_settings = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.media_settings.enable()
        self.user = get_user_model().objects.create_user(
            username="uploadstudent",
            email="upload@example.com",
            password="upload-password-123",
        )
        self.profile = StudentProfile.objects.create(
            user=self.user,
            full_name="Upload Student",
        )
        self.url = reverse("profile_edit")

    def tearDown(self):
        self.media_settings.disable()
        self.media_directory.cleanup()

    def profile_data(self):
        return {
            "full_name": "Upload Student",
            "college": "",
            "degree": "",
            "department": "",
            "graduation_year": "2027",
            "programming_languages": "",
            "technical_skills": "",
            "preferred_job_role": "",
            "preferred_domain": "",
            "current_preparation_level": "Intermediate",
            "github_url": "",
            "linkedin_url": "",
            "bio": "",
        }

    def post_profile(self, resume):
        data = self.profile_data()
        data["resume"] = resume
        return self.client.post(self.url, data)

    def test_authenticated_user_can_upload_valid_pdf_resume_safely(self):
        self.client.force_login(self.user)
        upload = SimpleUploadedFile(
            "My Resume.pdf",
            b"%PDF-1.7\nValid test PDF content",
            content_type="application/pdf",
        )

        response = self.post_profile(upload)

        self.assertRedirects(response, reverse("profile"))
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.resume.name.startswith("resumes/"))
        self.assertTrue(self.profile.resume.name.endswith(".pdf"))
        self.assertNotIn("My Resume", self.profile.resume.name)

        file_response = self.client.get(reverse("profile_file", args=["resume"]))
        self.assertEqual(file_response.status_code, 200)
        self.assertEqual(file_response["Content-Type"], "application/pdf")
        self.assertIn("attachment", file_response["Content-Disposition"])
        self.assertEqual(file_response["X-Content-Type-Options"], "nosniff")
        file_response.close()

    def test_resume_rejects_invalid_extension(self):
        self.client.force_login(self.user)
        upload = SimpleUploadedFile("payload.exe", b"%PDF-1.7\npayload")

        response = self.post_profile(upload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resume must be a PDF file.")
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.resume)

    def test_resume_rejects_oversized_file(self):
        self.client.force_login(self.user)
        upload = SimpleUploadedFile("large.pdf", b"%PDF-" + b"x" * (5 * 1024 * 1024))

        response = self.post_profile(upload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "resume file must be no larger than 5 MB.")
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.resume)

    def test_resume_rejects_empty_and_forged_pdf_uploads(self):
        self.client.force_login(self.user)
        for upload in (
            SimpleUploadedFile("empty.pdf", b""),
            SimpleUploadedFile("not-really-a-pdf.pdf", b"<html>not a PDF</html>"),
        ):
            with self.subTest(filename=upload.name):
                response = self.post_profile(upload)
                self.assertEqual(response.status_code, 200)
                self.profile.refresh_from_db()
                self.assertFalse(self.profile.resume)

    def test_unauthenticated_user_cannot_upload_or_read_profile_files(self):
        response = self.post_profile(
            SimpleUploadedFile("resume.pdf", b"%PDF-1.7\nvalid")
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        self.assertEqual(
            self.client.get(reverse("profile_file", args=["resume"])).status_code,
            302,
        )
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.resume)

    def test_another_authenticated_user_cannot_download_resume(self):
        self.profile.resume.save(
            "resume.pdf",
            SimpleUploadedFile("resume.pdf", b"%PDF-1.7\nvalid"),
        )
        other_user = get_user_model().objects.create_user(
            username="otheruploadstudent",
            email="other-upload@example.com",
            password="other-upload-password-123",
        )
        self.client.force_login(other_user)

        response = self.client.get(reverse("profile_file", args=["resume"]))

        self.assertEqual(response.status_code, 404)


class AptitudePracticeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="aptitudestudent",
            email="aptitude@example.com",
            password="StrongPass123!",
        )
        cls.category = AptitudeCategory.objects.create(
            name="Quantitative Aptitude Test",
            slug="quantitative-test",
        )
        cls.topic = AptitudeTopic.objects.create(
            category=cls.category,
            name="Percentages",
            slug="percentages-test",
        )
        cls.question = AptitudeQuestion.objects.create(
            topic=cls.topic,
            question_text="What is 20% of 150?",
            difficulty=AptitudeQuestion.Difficulty.EASY,
            marks=3,
            explanation="20% is one fifth, and one fifth of 150 is 30.",
        )
        cls.options = [
            AptitudeQuestionOption.objects.create(
                question=cls.question,
                position=position,
                text=text,
                is_correct=(position == 2),
            )
            for position, text in enumerate(["25", "30", "35", "40"], start=1)
        ]

    def setUp(self):
        self.client.force_login(self.user)

    def test_practice_landing_lists_the_seeded_tracks(self):
        response = self.client.get(reverse("practice"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Quantitative Aptitude")
        self.assertContains(response, "Logical Reasoning")
        self.assertContains(response, "Verbal Ability")

    def test_question_is_loaded_from_database(self):
        response = self.client.get(
            reverse("aptitude_question", args=[self.question.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "What is 20% of 150?")
        for option in self.options:
            self.assertContains(response, option.text)

    def test_correct_answer_is_stored_with_score_and_time(self):
        self.client.get(reverse("aptitude_question", args=[self.question.pk]))
        session = self.client.session
        session[f"aptitude_question_started_{self.question.pk}"] = timezone.now().timestamp() - 47
        session.save()
        response = self.client.post(
            reverse("aptitude_question", args=[self.question.pk]),
            {"selected_option": str(self.options[1].pk)},
        )

        attempt = AptitudeQuestionAttempt.objects.get(user=self.user)
        self.assertRedirects(
            response,
            reverse("aptitude_attempt_result", args=[attempt.pk]),
        )
        self.assertTrue(attempt.is_correct)
        self.assertEqual(attempt.marks_awarded, 3)
        self.assertGreaterEqual(attempt.time_taken_seconds, 47)
        self.assertEqual(attempt.selected_option, self.options[1])

        result = self.client.get(
            reverse("aptitude_attempt_result", args=[attempt.pk])
        )
        self.assertContains(result, "Correct answer")
        self.assertContains(result, "one fifth of 150 is 30")

    def test_wrong_answer_scores_zero_and_accuracy_uses_all_attempts(self):
        question_url = reverse("aptitude_question", args=[self.question.pk])
        self.client.get(question_url)
        self.client.post(question_url, {"selected_option": str(self.options[1].pk)})
        self.client.get(question_url)
        response = self.client.post(
            question_url,
            {"selected_option": str(self.options[0].pk)},
        )

        attempt = AptitudeQuestionAttempt.objects.latest("attempted_at")
        self.assertFalse(attempt.is_correct)
        self.assertEqual(attempt.marks_awarded, 0)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            sorted(
                AptitudeQuestionAttempt.objects.filter(user=self.user).values_list(
                    "marks_awarded",
                    flat=True,
                )
            ),
            [0, 3],
        )

        topic_response = self.client.get(
            reverse(
                "aptitude_topic",
                args=[self.category.slug, self.topic.slug],
            )
        )
        self.assertContains(topic_response, "50.0%")
        self.assertContains(topic_response, "<strong>3</strong>")
        self.assertContains(topic_response, "2")

    def test_an_option_from_another_question_is_rejected(self):
        other_question = AptitudeQuestion.objects.create(
            topic=self.topic,
            question_text="Separate question?",
            explanation="Separate explanation.",
        )
        foreign_option = AptitudeQuestionOption.objects.create(
            question=other_question,
            position=1,
            text="Foreign option",
            is_correct=True,
        )

        response = self.client.post(
            reverse("aptitude_question", args=[self.question.pk]),
            {"selected_option": str(foreign_option.pk)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(AptitudeQuestionAttempt.objects.exists())
        self.assertContains(response, "Select a valid choice.")

    def test_aptitude_pages_require_authentication(self):
        self.client.logout()
        urls = [
            reverse("practice"),
            reverse("aptitude_category", args=[self.category.slug]),
            reverse("aptitude_topic", args=[self.category.slug, self.topic.slug]),
            reverse("aptitude_question", args=[self.question.pk]),
            reverse("aptitude_attempt_result", args=[1]),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("login"), response.url)


class AptitudeAdminTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            username="aptitudeadmin",
            email="admin@example.com",
            password="StrongPass123!",
        )
        self.category = AptitudeCategory.objects.create(
            name="Logical Reasoning Test",
            slug="logical-admin-test",
        )
        self.topic = AptitudeTopic.objects.create(
            category=self.category,
            name="Series",
            slug="series-admin-test",
        )
        self.client.force_login(self.admin_user)

    def test_admin_can_create_a_question_with_four_options(self):
        url = reverse("admin:core_aptitudequestion_add")
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        formset_prefix = page.context["inline_admin_formsets"][0].formset.prefix
        data = {
            "topic": str(self.topic.pk),
            "question_text": "Find the next number: 2, 4, 6, ?",
            "difficulty": "easy",
            "marks": "2",
            "explanation": "The sequence increases by two.",
            "is_active": "on",
            f"{formset_prefix}-TOTAL_FORMS": "4",
            f"{formset_prefix}-INITIAL_FORMS": "0",
            f"{formset_prefix}-MIN_NUM_FORMS": "4",
            f"{formset_prefix}-MAX_NUM_FORMS": "4",
        }
        for position in range(1, 5):
            prefix = f"{formset_prefix}-{position - 1}"
            data[f"{prefix}-position"] = str(position)
            data[f"{prefix}-text"] = str(position * 2)
            if position == 2:
                data[f"{prefix}-is_correct"] = "on"

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        question = AptitudeQuestion.objects.get(question_text__startswith="Find the next number")
        self.assertEqual(question.options.count(), 4)
        self.assertEqual(question.options.filter(is_correct=True).count(), 1)

    def test_admin_rejects_question_with_multiple_correct_options(self):
        url = reverse("admin:core_aptitudequestion_add")
        page = self.client.get(url)
        prefix = page.context["inline_admin_formsets"][0].formset.prefix
        data = {
            "topic": str(self.topic.pk),
            "question_text": "Which option is correct?",
            "difficulty": "medium",
            "marks": "1",
            "explanation": "There is one correct answer.",
            "is_active": "on",
            f"{prefix}-TOTAL_FORMS": "4",
            f"{prefix}-INITIAL_FORMS": "0",
            f"{prefix}-MIN_NUM_FORMS": "4",
            f"{prefix}-MAX_NUM_FORMS": "4",
        }
        for position in range(1, 5):
            row = f"{prefix}-{position - 1}"
            data[f"{row}-position"] = str(position)
            data[f"{row}-text"] = f"Option {position}"
            if position < 3:
                data[f"{row}-is_correct"] = "on"

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(AptitudeQuestion.objects.filter(question_text="Which option is correct?").exists())
        self.assertContains(response, "Mark exactly one option as the correct answer.")


class CodingPracticeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="codingstudent",
            email="coding@example.com",
            password="StrongPass123!",
        )
        cls.topic = CodingTopic.objects.get_or_create(
            slug="coding-test-arrays",
            defaults={"name": "Coding Test Arrays"},
        )[0]
        cls.problem = CodingProblem.objects.create(
            title="Maximum Pair Sum",
            slug="maximum-pair-sum-test",
            topic=cls.topic,
            category="Arrays",
            difficulty=CodingProblem.Difficulty.EASY,
            problem_statement="Find the maximum sum of two values.",
            description="Find the maximum sum of two values.",
            input_format="An array of integers.",
            output_format="An integer.",
            constraints="2 <= n <= 100",
            sample_input="[2, 7, 1]",
            sample_output="9",
            explanation="Select the two largest values.",
            tags=["array", "easy"],
            starter_code="def solve(values):\n    pass\n",
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_problem_browsing_and_details_are_database_backed(self):
        browse = self.client.get(reverse("coding"))
        self.assertEqual(browse.status_code, 200)
        self.assertContains(browse, self.problem.title)
        self.assertContains(browse, "Dynamic Programming")

        detail = self.client.get(
            reverse("coding_problem_detail", args=[self.problem.slug])
        )
        self.assertEqual(detail.status_code, 200)
        for content in (
            "Find the maximum sum",
            "An array of integers",
            "An integer.",
            "2 &lt;= n &lt;= 100",
            "[2, 7, 1]",
            "def solve(values):",
            "Python 3",
            "JavaScript",
        ):
            self.assertContains(detail, content)

    def test_submission_is_saved_without_running_code_and_updates_tracking(self):
        source_code = "import os\nprint(os.environ)"
        response = self.client.post(
            reverse("coding_problem_detail", args=[self.problem.slug]),
            {"language": "python", "source_code": source_code},
        )

        submission = CodingSubmission.objects.get(user=self.user)
        self.assertRedirects(
            response,
            reverse("coding_submission_result", args=[submission.pk]),
        )
        self.assertEqual(submission.source_code, source_code)
        self.assertEqual(submission.status, CodingSubmission.Status.RECEIVED)
        self.assertEqual(
            submission.sample_validation_status,
            CodingSubmission.ValidationStatus.NOT_RUN,
        )
        self.assertIn("not run", submission.validation_message)
        self.assertEqual(CodingProblem.objects.count(), 1)
        self.assertEqual(self.user.coding_attempts.count(), 1)
        self.assertFalse(self.user.coding_attempts.first().passed)

        result = self.client.get(
            reverse("coding_submission_result", args=[submission.pk])
        )
        self.assertContains(result, "not executed")
        self.assertContains(result, source_code)

        browse = self.client.get(reverse("coding"))
        self.assertContains(browse, "Received")
        self.assertEqual(browse.context["problems_attempted"], 1)
        self.assertEqual(browse.context["problems_solved"], 0)
        arrays_performance = next(
            item for item in browse.context["topic_performance"]
            if item["topic"] == self.topic
        )
        self.assertEqual(arrays_performance["attempted"], 1)
        self.assertEqual(arrays_performance["solved"], 0)

    def test_submission_form_rejects_unknown_language_and_empty_source(self):
        url = reverse("coding_problem_detail", args=[self.problem.slug])
        response = self.client.post(
            url,
            {"language": "shell", "source_code": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CodingSubmission.objects.exists())
        self.assertContains(response, "Select a valid choice")
        self.assertContains(response, "This field is required.")

    def test_problem_pages_require_login_and_submission_result_is_private(self):
        submission = CodingSubmission.objects.create(
            user=self.user,
            problem=self.problem,
            language="python",
            source_code="print(1)",
            validation_message="Not run.",
        )
        other_user = get_user_model().objects.create_user(
            username="othercodingstudent",
            password="StrongPass123!",
        )
        self.client.force_login(other_user)
        response = self.client.get(
            reverse("coding_submission_result", args=[submission.pk])
        )
        self.assertEqual(response.status_code, 404)

        self.client.logout()
        for url in (
            reverse("coding"),
            reverse("coding_problem_detail", args=[self.problem.slug]),
            reverse("coding_submission_result", args=[submission.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("login"), response.url)


class CodingAdminTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            username="codingadmin",
            email="codingadmin@example.com",
            password="StrongPass123!",
        )
        self.topic = CodingTopic.objects.get_or_create(
            slug="coding-admin-arrays",
            defaults={"name": "Coding Admin Arrays"},
        )[0]
        self.client.force_login(self.admin_user)

    def test_admin_can_create_problem_with_requested_fields(self):
        response = self.client.post(
            reverse("admin:core_codingproblem_add"),
            {
                "title": "Admin Added Array",
                "slug": "admin-added-array-test",
                "topic": str(self.topic.pk),
                "category": "Arrays",
                "difficulty": "Medium",
                "problem_statement": "Add two values.",
                "input_format": "Two integers.",
                "output_format": "Their sum.",
                "constraints": "Integers fit in 32 bits.",
                "sample_input": "2 3",
                "sample_output": "5",
                "explanation": "Use addition.",
                "tags": '["arrays", "math"]',
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        problem = CodingProblem.objects.get(slug="admin-added-array-test")
        self.assertEqual(problem.topic, self.topic)
        self.assertEqual(problem.tags, ["arrays", "math"])
        self.assertEqual(problem.input_format, "Two integers.")


class MockTestEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="testtaker",
            email="testtaker@example.com",
            password="StrongPass123!",
        )
        cls.category_quant = AptitudeCategory.objects.create(
            name="Assessment Quant",
            slug="assessment-quant",
        )
        cls.topic_percent = AptitudeTopic.objects.create(
            category=cls.category_quant,
            name="Assessment Percentages",
            slug="assessment-percentages",
        )
        cls.category_reasoning = AptitudeCategory.objects.create(
            name="Assessment Reasoning",
            slug="assessment-reasoning",
        )
        cls.topic_series = AptitudeTopic.objects.create(
            category=cls.category_reasoning,
            name="Assessment Series",
            slug="assessment-series",
        )
        cls.questions = [
            AptitudeQuestion.objects.create(
                topic=cls.topic_percent,
                question_text="Question one",
                difficulty=AptitudeQuestion.Difficulty.EASY,
                marks=2,
                explanation="Explanation one.",
            ),
            AptitudeQuestion.objects.create(
                topic=cls.topic_series,
                question_text="Question two",
                difficulty=AptitudeQuestion.Difficulty.MEDIUM,
                marks=3,
                explanation="Explanation two.",
            ),
            AptitudeQuestion.objects.create(
                topic=cls.topic_percent,
                question_text="Question three",
                difficulty=AptitudeQuestion.Difficulty.HARD,
                marks=1,
                explanation="Explanation three.",
            ),
        ]
        cls.options = []
        for index, question in enumerate(cls.questions):
            options = [
                AptitudeQuestionOption.objects.create(
                    question=question,
                    position=position,
                    text=f"Q{index + 1} option {position}",
                    is_correct=position == 1,
                )
                for position in range(1, 5)
            ]
            cls.options.append(options)
        cls.assessment = AssessmentTest.objects.create(
            title="Multi-category placement test",
            slug="multi-category-placement-test",
            description="A short test across quantitative and reasoning questions.",
            duration_minutes=30,
            is_published=True,
        )
        for position, question in enumerate(cls.questions, start=1):
            TestQuestion.objects.create(
                test=cls.assessment,
                question=question,
                position=position,
            )

    def setUp(self):
        self.client.force_login(self.user)

    def _start_attempt(self):
        response = self.client.post(
            reverse("mock_tests"),
            {"test_id": self.assessment.pk},
        )
        attempt = TestAttempt.objects.get(user=self.user, test=self.assessment)
        return response, attempt

    def _save_answer(self, attempt, position, selected_option_id, marked_for_review=False):
        test_question = TestQuestion.objects.get(test=self.assessment, position=position)
        return self.client.post(
            reverse("save_test_answer", args=[attempt.pk]),
            data=json.dumps(
                {
                    "test_question_id": test_question.pk,
                    "selected_option_id": selected_option_id,
                    "marked_for_review": marked_for_review,
                }
            ),
            content_type="application/json",
        )

    def test_database_test_listing_and_attempt_start_resume(self):
        listing = self.client.get(reverse("mock_tests"))
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, self.assessment.title)
        self.assertContains(listing, "Assessment Quant")
        self.assertContains(listing, "Assessment Reasoning")
        self.assertEqual(listing.context["test_cards"][0]["question_count"], 3)
        self.assertEqual(listing.context["test_cards"][0]["total_marks"], 6)

        response, attempt = self._start_attempt()
        self.assertRedirects(response, reverse("test_attempt", args=[attempt.pk]))
        self.assertEqual(attempt.total_questions, 3)
        self.assertEqual(attempt.total_marks, 6)
        self.assertEqual(attempt.answers.count(), 3)

        resume_response = self.client.post(
            reverse("mock_tests"),
            {"test_id": self.assessment.pk},
        )
        self.assertRedirects(
            resume_response,
            reverse("test_attempt", args=[attempt.pk]),
        )
        self.assertEqual(TestAttempt.objects.filter(user=self.user).count(), 1)

        attempt_page = self.client.get(reverse("test_attempt", args=[attempt.pk]))
        self.assertContains(attempt_page, "Navigate")
        self.assertContains(attempt_page, "Mark for review")
        self.assertContains(attempt_page, "Clear answer")
        self.assertContains(attempt_page, "Question one")

    def test_answer_autosave_review_clear_grading_and_performance(self):
        _, attempt = self._start_attempt()
        first = self._save_answer(
            attempt,
            1,
            self.options[0][0].pk,
            marked_for_review=True,
        )
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["saved"])
        answer = TestAnswer.objects.get(attempt=attempt, test_question__position=1)
        self.assertEqual(answer.selected_option, self.options[0][0])
        self.assertTrue(answer.marked_for_review)

        cleared = self._save_answer(attempt, 1, None)
        self.assertEqual(cleared.status_code, 200)
        answer.refresh_from_db()
        self.assertIsNone(answer.selected_option)

        self._save_answer(attempt, 1, self.options[0][0].pk)
        self._save_answer(attempt, 2, self.options[1][1].pk)
        AptitudeQuestionOption.objects.filter(pk=self.options[0][0].pk).update(is_correct=False)
        AptitudeQuestionOption.objects.filter(pk=self.options[0][1].pk).update(is_correct=True)
        submit = self.client.post(reverse("submit_test_attempt", args=[attempt.pk]))
        attempt.refresh_from_db()

        self.assertEqual(submit.status_code, 200)
        self.assertEqual(attempt.status, TestAttempt.Status.SUBMITTED)
        self.assertEqual(attempt.score, 2)
        self.assertEqual(attempt.correct_count, 1)
        self.assertEqual(attempt.wrong_count, 1)
        self.assertEqual(attempt.skipped_count, 1)
        self.assertEqual(attempt.accuracy, 50.0)
        self.assertGreaterEqual(attempt.time_taken_seconds, 0)
        answers = list(attempt.answers.order_by("test_question__position"))
        self.assertTrue(answers[0].is_correct)
        self.assertEqual(answers[0].correct_option, self.options[0][0])
        self.assertFalse(answers[1].is_correct)
        self.assertIsNone(answers[2].is_correct)

        result = self.client.get(reverse("test_result", args=[attempt.pk]))
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, "Category performance")
        self.assertContains(result, "Topic performance")
        self.assertContains(result, "Assessment Quant")
        self.assertContains(result, "Assessment Reasoning")
        self.assertContains(result, "Skipped")
        self.assertEqual(len(result.context["performance"]["categories"]), 2)
        self.assertEqual(len(result.context["performance"]["topics"]), 2)
        dashboard = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard.context["tests_completed"], 1)

    def test_foreign_option_rejected_and_foreign_attempt_is_private(self):
        _, attempt = self._start_attempt()
        foreign_question = AptitudeQuestion.objects.create(
            topic=self.topic_percent,
            question_text="Outside assessment question",
            explanation="Not included.",
        )
        foreign_option = AptitudeQuestionOption.objects.create(
            question=foreign_question,
            position=1,
            text="Foreign",
            is_correct=True,
        )
        test_question = TestQuestion.objects.get(test=self.assessment, position=1)
        response = self.client.post(
            reverse("save_test_answer", args=[attempt.pk]),
            data=json.dumps(
                {
                    "test_question_id": test_question.pk,
                    "selected_option_id": foreign_option.pk,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)

        other_user = get_user_model().objects.create_user(
            username="differenttesttaker",
            password="StrongPass123!",
        )
        self.client.force_login(other_user)
        self.assertEqual(
            self.client.get(reverse("test_attempt", args=[attempt.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("test_result", args=[attempt.pk])).status_code,
            404,
        )

    def test_deadline_expiration_finalizes_automatically(self):
        _, attempt = self._start_attempt()
        self._save_answer(attempt, 1, self.options[0][0].pk)
        attempt.deadline_at = timezone.now() - timedelta(seconds=1)
        attempt.save(update_fields=["deadline_at"])

        response = self.client.get(reverse("test_attempt", args=[attempt.pk]))
        attempt.refresh_from_db()
        self.assertRedirects(response, reverse("test_result", args=[attempt.pk]))
        self.assertEqual(attempt.status, TestAttempt.Status.EXPIRED)
        self.assertEqual(attempt.score, 2)
        self.assertEqual(attempt.skipped_count, 2)
        self.assertLessEqual(attempt.time_taken_seconds, attempt.duration_seconds)

        late_save = self._save_answer(attempt, 2, self.options[1][0].pk)
        self.assertEqual(late_save.status_code, 409)

    def test_test_routes_require_authentication(self):
        _, attempt = self._start_attempt()
        self.client.logout()
        for url in (
            reverse("mock_tests"),
            reverse("test_attempt", args=[attempt.pk]),
            reverse("test_result", args=[attempt.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("login"), response.url)

        response = self.client.post(
            reverse("save_test_answer", args=[attempt.pk]),
            data="{}",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        response = self.client.post(
            reverse("submit_test_attempt", args=[attempt.pk]),
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)


class PerformanceAnalyticsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="analyticsstudent",
            email="analytics@example.com",
            password="analytics-password",
        )
        self.client.force_login(self.user)
        self.now = timezone.now()
        self.category = AptitudeCategory.objects.create(
            name="Analytics Quantitative",
            slug="analytics-quantitative",
        )
        self.topic = AptitudeTopic.objects.create(
            category=self.category,
            name="Analytics Percentages",
            slug="analytics-percentages",
        )
        self.question = AptitudeQuestion.objects.create(
            topic=self.topic,
            question_text="Analytics sample question",
            explanation="Sample explanation.",
        )
        self.options = [
            AptitudeQuestionOption.objects.create(
                question=self.question,
                position=position,
                text=f"Analytics option {position}",
                is_correct=position == 1,
            )
            for position in range(1, 5)
        ]

    def test_empty_analytics_returns_zeroes_and_seven_days(self):
        analytics = get_performance_analytics(self.user, now=self.now)
        dashboard = get_dashboard_summary(self.user)

        self.assertEqual(analytics["overall_preparation_score"], 0.0)
        self.assertEqual(analytics["accuracy"], 0.0)
        self.assertEqual(analytics["questions_attempted"], 0)
        self.assertEqual(analytics["questions_solved"], 0)
        self.assertEqual(analytics["mock_tests_completed"], 0)
        self.assertEqual(analytics["coding_problems_solved"], 0)
        self.assertEqual(len(analytics["weekly_progress"]), 7)
        self.assertEqual(analytics["topic_performance"], [])
        self.assertEqual(analytics["recent_test_scores"], [])
        self.assertEqual(
            dashboard["overall_preparation_score"],
            analytics["overall_preparation_score"],
        )
        self.assertEqual(dashboard["questions_attempted"], analytics["questions_attempted"])
        self.assertEqual(dashboard["questions_solved"], analytics["questions_solved"])
        self.assertEqual(dashboard["accuracy"], analytics["accuracy"])
        self.assertEqual(dashboard["coding_problems_solved"], analytics["coding_problems_solved"])
        self.assertEqual(dashboard["tests_completed"], analytics["mock_tests_completed"])

    def test_dashboard_analytics_and_api_share_all_performance_metrics(self):
        AptitudeQuestionAttempt.objects.create(
            user=self.user,
            question=self.question,
            selected_option=self.options[0],
            is_correct=True,
            attempted_at=self.now,
        )
        AptitudeQuestionAttempt.objects.create(
            user=self.user,
            question=self.question,
            selected_option=self.options[1],
            is_correct=False,
            attempted_at=self.now,
        )

        legacy_question = Question.objects.create(
            category="Legacy Fundamentals",
            difficulty="Easy",
            question_text="Legacy question",
            option_a="A",
            option_b="B",
            option_c="C",
            option_d="D",
            correct_option="A",
        )
        QuestionAttempt.objects.create(
            user=self.user,
            question=legacy_question,
            selected_option="A",
            is_correct=True,
            attempted_at=self.now,
        )

        assessment = AssessmentTest.objects.create(
            title="Analytics assessment",
            slug="analytics-assessment",
            duration_minutes=10,
            is_published=True,
        )
        test_question = TestQuestion.objects.create(
            test=assessment,
            question=self.question,
            position=1,
        )
        test_attempt = TestAttempt.objects.create(
            user=self.user,
            test=assessment,
            status=TestAttempt.Status.SUBMITTED,
            started_at=self.now - timedelta(minutes=5),
            deadline_at=self.now + timedelta(minutes=5),
            submitted_at=self.now,
            duration_seconds=600,
            total_questions=1,
            total_marks=2,
            score=1,
            correct_count=0,
            wrong_count=1,
            skipped_count=0,
        )
        TestAnswer.objects.create(
            attempt=test_attempt,
            test_question=test_question,
            selected_option=self.options[1],
            correct_option=self.options[0],
            marks_possible=2,
            is_correct=False,
        )

        legacy_test = MockTest.objects.create(
            title="Legacy analytics test",
            duration_minutes=10,
        )
        MockTestAttempt.objects.create(
            user=self.user,
            test=legacy_test,
            score=3,
            completed_at=self.now,
        )

        coding_topic = CodingTopic.objects.create(
            name="Analytics arrays",
            slug="analytics-arrays",
        )
        coding_problem = CodingProblem.objects.create(
            title="Analytics coding problem",
            slug="analytics-coding-problem",
            topic=coding_topic,
            problem_statement="Solve a sample task.",
        )
        CodingAttempt.objects.create(
            user=self.user,
            problem=coding_problem,
            passed=False,
            attempted_at=self.now,
        )
        CodingSubmission.objects.create(
            user=self.user,
            problem=coding_problem,
            language=CodingSubmission.Language.PYTHON,
            source_code="print('done')",
            status=CodingSubmission.Status.ACCEPTED,
        )

        analytics = get_performance_analytics(self.user, now=self.now)
        dashboard = get_dashboard_summary(self.user)

        self.assertEqual(analytics["questions_attempted"], 4)
        self.assertEqual(analytics["questions_solved"], 2)
        self.assertEqual(analytics["accuracy"], 50.0)
        self.assertEqual(analytics["mock_tests_completed"], 2)
        self.assertEqual(analytics["coding_problems_solved"], 1)
        self.assertEqual(analytics["coding_problems_attempted"], 1)
        self.assertEqual(analytics["coding_success_rate"], 100.0)
        self.assertEqual(analytics["overall_preparation_score"], 66.7)
        for dashboard_key, analytics_key in (
            ("overall_preparation_score", "overall_preparation_score"),
            ("questions_attempted", "questions_attempted"),
            ("questions_solved", "questions_solved"),
            ("accuracy", "accuracy"),
            ("coding_problems_solved", "coding_problems_solved"),
            ("coding_problems_attempted", "coding_problems_attempted"),
            ("coding_success_rate", "coding_success_rate"),
            ("tests_completed", "mock_tests_completed"),
        ):
            self.assertEqual(dashboard[dashboard_key], analytics[analytics_key])
        dashboard_coding_score = next(
            item["value"] for item in dashboard["subject_scores"] if item["name"] == "Coding"
        )
        self.assertEqual(dashboard_coding_score, analytics["coding_success_rate"])

        api_response = self.client.get(reverse("dashboard_api"))
        self.assertEqual(api_response.status_code, 200)
        api_data = api_response.json()
        self.assertEqual(api_data["overall_preparation_score"], analytics["overall_preparation_score"])
        self.assertEqual(api_data["questions_attempted"], analytics["questions_attempted"])
        self.assertEqual(api_data["questions_solved"], analytics["questions_solved"])
        self.assertEqual(api_data["accuracy"], analytics["accuracy"])
        self.assertEqual(api_data["coding_problems_solved"], analytics["coding_problems_solved"])
        self.assertEqual(api_data["coding_success_rate"], analytics["coding_success_rate"])
        self.assertEqual(api_data["tests_completed"], analytics["mock_tests_completed"])

        self.assertEqual(len(analytics["category_performance"]), 2)
        percentage_topic = next(
            item
            for item in analytics["topic_performance"]
            if item["name"] == "Analytics Percentages"
        )
        self.assertEqual(percentage_topic["attempted"], 3)
        self.assertEqual(percentage_topic["correct"], 1)
        self.assertEqual(percentage_topic["accuracy"], 33.3)
        today = next(
            item
            for item in analytics["weekly_progress"]
            if item["date"] == self.now.date().isoformat()
        )
        self.assertEqual(today["attempted"], 4)
        self.assertEqual(today["correct"], 2)
        self.assertEqual(today["tests"], 2)
        self.assertEqual(len(analytics["recent_test_scores"]), 2)
        timed_score = next(
            item
            for item in analytics["recent_test_scores"]
            if item["test"] == "Analytics assessment"
        )
        self.assertEqual(timed_score["percentage"], 50.0)
        self.assertEqual(timed_score["total_marks"], 2)

    def test_aptitude_only_activity_uses_available_preparation_component(self):
        AptitudeQuestionAttempt.objects.create(
            user=self.user,
            question=self.question,
            selected_option=self.options[0],
            is_correct=True,
            attempted_at=self.now,
        )

        analytics = get_performance_analytics(self.user, now=self.now)
        dashboard = get_dashboard_summary(self.user)

        self.assertEqual(analytics["overall_preparation_score"], 100.0)
        self.assertEqual(analytics["questions_attempted"], 1)
        self.assertEqual(dashboard["questions_attempted"], 1)
        self.assertEqual(dashboard["overall_preparation_score"], 100.0)

    def test_coding_only_activity_deduplicates_problem_attempts_and_submissions(self):
        coding_topic = CodingTopic.objects.create(
            name="Deduplicated arrays",
            slug="deduplicated-arrays",
        )
        problem = CodingProblem.objects.create(
            title="One unique problem",
            slug="one-unique-problem",
            topic=coding_topic,
            problem_statement="Solve one task.",
        )
        CodingAttempt.objects.create(
            user=self.user,
            problem=problem,
            passed=False,
            attempted_at=self.now,
        )
        for _ in range(2):
            CodingSubmission.objects.create(
                user=self.user,
                problem=problem,
                language=CodingSubmission.Language.PYTHON,
                source_code="print('done')",
                status=CodingSubmission.Status.ACCEPTED,
            )

        analytics = get_performance_analytics(self.user, now=self.now)
        dashboard = get_dashboard_summary(self.user)

        self.assertEqual(analytics["coding_problems_attempted"], 1)
        self.assertEqual(analytics["coding_problems_solved"], 1)
        self.assertEqual(analytics["coding_success_rate"], 100.0)
        self.assertEqual(analytics["overall_preparation_score"], 100.0)
        self.assertEqual(dashboard["coding_problems_attempted"], 1)
        self.assertEqual(dashboard["coding_problems_solved"], 1)
        self.assertEqual(dashboard["coding_success_rate"], 100.0)

    def test_expired_tests_count_and_selected_answers_are_included(self):
        assessment = AssessmentTest.objects.create(
            title="Expired analytics assessment",
            slug="expired-analytics-assessment",
            duration_minutes=10,
            is_published=True,
        )
        test_question = TestQuestion.objects.create(
            test=assessment,
            question=self.question,
            position=1,
        )
        expired_attempt = TestAttempt.objects.create(
            user=self.user,
            test=assessment,
            status=TestAttempt.Status.EXPIRED,
            started_at=self.now - timedelta(minutes=10),
            deadline_at=self.now,
            submitted_at=self.now,
            duration_seconds=600,
            total_questions=1,
            total_marks=4,
            score=2,
            correct_count=1,
            wrong_count=0,
            skipped_count=0,
        )
        TestAnswer.objects.create(
            attempt=expired_attempt,
            test_question=test_question,
            selected_option=self.options[0],
            correct_option=self.options[0],
            marks_possible=4,
            is_correct=True,
        )
        TestAttempt.objects.create(
            user=self.user,
            test=assessment,
            status=TestAttempt.Status.IN_PROGRESS,
            started_at=self.now,
            deadline_at=self.now + timedelta(minutes=10),
            duration_seconds=600,
            total_questions=1,
            total_marks=4,
        )

        analytics = get_performance_analytics(self.user, now=self.now)
        dashboard = get_dashboard_summary(self.user)

        self.assertEqual(analytics["questions_attempted"], 1)
        self.assertEqual(analytics["questions_solved"], 1)
        self.assertEqual(analytics["mock_tests_completed"], 1)
        self.assertEqual(analytics["timed_test_average"], 50.0)
        self.assertEqual(analytics["overall_preparation_score"], 75.0)
        self.assertEqual(dashboard["tests_completed"], 1)
        self.assertEqual(dashboard["overall_preparation_score"], 75.0)

    def test_repeated_question_attempts_are_counted_and_user_data_is_private(self):
        for is_correct in (True, False):
            AptitudeQuestionAttempt.objects.create(
                user=self.user,
                question=self.question,
                selected_option=self.options[0 if is_correct else 1],
                is_correct=is_correct,
                attempted_at=self.now,
            )
        other_user = get_user_model().objects.create_user(
            username="otheranalyticsstudent",
            email="other-analytics@example.com",
            password="test-password-456",
        )
        AptitudeQuestionAttempt.objects.create(
            user=other_user,
            question=self.question,
            selected_option=self.options[0],
            is_correct=True,
            attempted_at=self.now,
        )

        analytics = get_performance_analytics(self.user, now=self.now)
        dashboard = get_dashboard_summary(self.user)
        api_response = self.client.get(reverse("dashboard_api"))

        self.assertEqual(analytics["questions_attempted"], 2)
        self.assertEqual(analytics["questions_solved"], 1)
        self.assertEqual(analytics["accuracy"], 50.0)
        self.assertEqual(dashboard["questions_attempted"], 2)
        self.assertEqual(api_response.json()["questions_attempted"], 2)
        self.assertEqual(get_performance_analytics(other_user, now=self.now)["questions_attempted"], 1)

    def test_page_and_api_only_expose_authenticated_users_own_analytics(self):
        other_user = get_user_model().objects.create_user(
            username="otheranalyticsstudent",
            email="other-analytics@example.com",
            password="other-analytics-password",
        )
        other_category = AptitudeCategory.objects.create(
            name="Private Other Category",
            slug="private-other-category",
        )
        other_topic = AptitudeTopic.objects.create(
            category=other_category,
            name="Private Other Topic",
            slug="private-other-topic",
        )
        other_question = AptitudeQuestion.objects.create(
            topic=other_topic,
            question_text="Another student's question",
            explanation="Private.",
        )
        other_option = AptitudeQuestionOption.objects.create(
            question=other_question,
            position=1,
            text="Private option",
            is_correct=True,
        )
        AptitudeQuestionAttempt.objects.create(
            user=other_user,
            question=other_question,
            selected_option=other_option,
            is_correct=True,
        )

        page = self.client.get(reverse("analytics"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Weekly progress")
        self.assertContains(page, "category-performance-data")
        self.assertNotContains(page, "Private Other Topic")
        self.assertEqual(page.context["analytics"]["questions_attempted"], 0)

        api_response = self.client.get(reverse("analytics_api"))
        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(api_response.json()["questions_attempted"], 0)
        self.assertEqual(api_response.json()["topic_performance"], [])

        self.client.logout()
        page_response = self.client.get(reverse("analytics"))
        self.assertEqual(page_response.status_code, 302)
        api_unauthenticated = self.client.get(reverse("analytics_api"))
        self.assertIn(api_unauthenticated.status_code, (401, 403))


class AIAssistantTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="aitutorstudent",
            email="aitutor@example.com",
            password="ai-tutor-password",
        )
        self.client.force_login(self.user)
        self.conversation = AIConversation.objects.create(
            user=self.user,
            title="New conversation",
        )

    def _send_message(self, conversation=None, prompt="Explain SQL joins.", mode="sql"):
        conversation = conversation or self.conversation
        return self.client.post(
            reverse("ai_messages_api", args=[conversation.pk]),
            data=json.dumps({"prompt": prompt, "mode": mode}),
            content_type="application/json",
        )

    def test_chat_page_and_conversation_history_are_user_scoped(self):
        AIMessage.objects.create(
            conversation=self.conversation,
            role=AIMessage.Role.USER,
            mode=AIMessage.Mode.SQL,
            content="Explain SQL joins.",
        )
        response = self.client.get(reverse("ai_assistant"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI Tutor")
        self.assertContains(response, "Clear conversation")
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertNotContains(response, "GEMINI_API_KEY")

        history = self.client.get(reverse("ai_conversations_api"))
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()[0]["id"], self.conversation.pk)
        self.assertEqual(history.json()[0]["title"], "New conversation")

        message_history = self.client.get(
            reverse("ai_messages_api", args=[self.conversation.pk])
        )
        self.assertEqual(message_history.status_code, 200)
        self.assertEqual(message_history.json()[0]["content"], "Explain SQL joins.")

    def test_student_can_create_a_new_conversation(self):
        response = self.client.post(
            reverse("ai_conversations_api"),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        created = AIConversation.objects.get(pk=response.json()["id"])
        self.assertEqual(created.user, self.user)
        self.assertEqual(created.title, "New conversation")
        self.assertEqual(created.messages.count(), 0)

    @patch("core.views.GeminiService.generate_reply", return_value="A join combines rows.")
    def test_message_is_sent_to_service_and_both_messages_are_saved(self, generate_reply):
        response = self._send_message()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["messages"][1]["content"], "A join combines rows.")
        self.assertEqual(response.json()["conversation"]["title"], "Explain SQL joins.")
        self.assertEqual(
            list(self.conversation.messages.values_list("role", "content", "mode")),
            [
                (AIMessage.Role.USER, "Explain SQL joins.", AIMessage.Mode.SQL),
                (AIMessage.Role.ASSISTANT, "A join combines rows.", ""),
            ],
        )
        generate_reply.assert_called_once_with(
            mode="sql",
            prompt="Explain SQL joins.",
            history=[],
        )

    @patch(
        "core.views.GeminiService.generate_reply",
        side_effect=["First response.", "Second response."],
    )
    def test_follow_up_sends_recent_conversation_context(self, generate_reply):
        self._send_message(prompt="What is a primary key?")
        response = self._send_message(prompt="Give me an example.")

        self.assertEqual(response.status_code, 201)
        second_call_history = generate_reply.call_args_list[1].kwargs["history"]
        self.assertEqual(
            second_call_history,
            [
                {"role": "user", "content": "What is a primary key?"},
                {"role": "assistant", "content": "First response."},
            ],
        )

    @patch(
        "core.views.GeminiService.generate_reply",
        side_effect=GeminiServiceError("The AI provider is temporarily unavailable."),
    )
    def test_provider_error_is_reported_and_user_question_remains_in_history(self, _generate_reply):
        response = self._send_message()

        self.assertEqual(response.status_code, 503)
        self.assertIn("temporarily unavailable", response.json()["error"])
        self.assertEqual(self.conversation.messages.count(), 1)
        self.assertEqual(
            self.conversation.messages.first().role,
            AIMessage.Role.USER,
        )

    @patch("core.views.GeminiService.generate_reply")
    def test_per_user_rate_limit_and_input_validation(self, generate_reply):
        now = timezone.now()
        AIMessage.objects.bulk_create(
            [
                AIMessage(
                    conversation=self.conversation,
                    role=AIMessage.Role.USER,
                    content=f"Recent message {index}",
                    mode=AIMessage.Mode.CONCEPT,
                    created_at=now,
                )
                for index in range(5)
            ]
        )
        limited = self._send_message()
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(self.conversation.messages.count(), 5)
        generate_reply.assert_not_called()

        invalid = self._send_message(prompt="x")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(self.conversation.messages.count(), 5)

    def test_users_cannot_read_or_delete_another_users_conversation(self):
        other_user = get_user_model().objects.create_user(
            username="otheraitutorstudent",
            email="other-ai@example.com",
            password="other-ai-password",
        )
        self.client.force_login(other_user)

        read_response = self.client.get(
            reverse("ai_messages_api", args=[self.conversation.pk])
        )
        delete_response = self.client.delete(
            reverse("ai_conversation_delete_api", args=[self.conversation.pk])
        )
        self.assertEqual(read_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        self.assertTrue(AIConversation.objects.filter(pk=self.conversation.pk).exists())

    def test_clear_conversation_deletes_its_messages(self):
        AIMessage.objects.create(
            conversation=self.conversation,
            role=AIMessage.Role.USER,
            content="Delete this chat.",
        )
        response = self.client.delete(
            reverse("ai_conversation_delete_api", args=[self.conversation.pk])
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(AIConversation.objects.filter(pk=self.conversation.pk).exists())
        self.assertFalse(AIMessage.objects.exists())

    def test_ai_api_requires_authentication(self):
        self.client.logout()
        for url in (
            reverse("ai_assistant"),
            reverse("ai_conversations_api"),
            reverse("ai_messages_api", args=[self.conversation.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn(response.status_code, (302, 401, 403))


class GeminiServiceTests(TestCase):
    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-server-secret"}, clear=False)
    @patch("core.services.gemini_service.request.urlopen")
    def test_gemini_key_is_sent_in_backend_header_and_tutor_instruction_is_used(self, urlopen):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(
                    {
                        "candidates": [
                            {
                                "content": {
                                    "parts": [{"text": "A row is a record."}],
                                },
                            },
                        ],
                    }
                ).encode("utf-8")

        urlopen.return_value = FakeResponse()
        reply = GeminiService.generate_reply(
            mode="dbms",
            prompt="What is a row?",
            history=[{"role": "user", "content": "What is a table?"}],
        )

        request_object = urlopen.call_args.args[0]
        sent_payload = json.loads(request_object.data.decode("utf-8"))
        self.assertEqual(reply, "A row is a record.")
        self.assertNotIn("test-server-secret", request_object.full_url)
        self.assertEqual(
            request_object.get_header("X-goog-api-key"),
            "test-server-secret",
        )
        self.assertIn(
            "placement interviews",
            sent_payload["systemInstruction"]["parts"][0]["text"],
        )
        self.assertIn(
            "DBMS",
            sent_payload["systemInstruction"]["parts"][0]["text"],
        )
        self.assertEqual(sent_payload["contents"][0]["role"], "user")

    @patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False)
    def test_missing_api_key_raises_explicit_configuration_error(self):
        with self.assertRaisesRegex(GeminiServiceError, "not configured"):
            GeminiService.generate_reply(mode="concept", prompt="Explain stacks.", history=[])

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-server-secret"}, clear=False)
    @patch("core.services.gemini_service.request.urlopen")
    def test_provider_rate_limit_is_converted_to_safe_error(self, urlopen):
        from urllib.error import HTTPError

        urlopen.side_effect = HTTPError(
            "https://generativelanguage.googleapis.com/",
            429,
            "rate limited",
            None,
            None,
        )
        with self.assertRaises(GeminiServiceError) as raised:
            GeminiService.generate_reply(mode="hint", prompt="Give a hint.", history=[])
        self.assertEqual(raised.exception.status_code, 429)
        self.assertIn("wait a moment", str(raised.exception))


class MockTestAdminTests(TestCase):
    def test_admin_can_create_test_with_multiple_categories(self):
        User = get_user_model()
        admin_user = User.objects.create_superuser(
            username="testengineadmin",
            email="testengineadmin@example.com",
            password="StrongPass123!",
        )
        question_one = AptitudeQuestion.objects.create(
            topic=AptitudeTopic.objects.create(
                category=AptitudeCategory.objects.create(
                    name="Admin Quant",
                    slug="admin-quant",
                ),
                name="Admin Percent",
                slug="admin-percent",
            ),
            question_text="Admin question one",
            explanation="Answer one.",
        )
        question_two = AptitudeQuestion.objects.create(
            topic=AptitudeTopic.objects.create(
                category=AptitudeCategory.objects.create(
                    name="Admin Verbal",
                    slug="admin-verbal",
                ),
                name="Admin Grammar",
                slug="admin-grammar",
            ),
            question_text="Admin question two",
            explanation="Answer two.",
        )
        for question in (question_one, question_two):
            for position in range(1, 5):
                AptitudeQuestionOption.objects.create(
                    question=question,
                    position=position,
                    text=f"Choice {position}",
                    is_correct=(position == 1),
                )
        self.client.force_login(admin_user)
        url = reverse("admin:core_test_add")
        page = self.client.get(url)
        prefix = page.context["inline_admin_formsets"][0].formset.prefix
        response = self.client.post(
            url,
            {
                "title": "Admin mixed test",
                "slug": "admin-mixed-test",
                "description": "Question bank mix.",
                "duration_minutes": "25",
                "difficulty": "medium",
                "is_published": "on",
                f"{prefix}-TOTAL_FORMS": "2",
                f"{prefix}-INITIAL_FORMS": "0",
                f"{prefix}-MIN_NUM_FORMS": "0",
                f"{prefix}-MAX_NUM_FORMS": "1000",
                f"{prefix}-0-position": "1",
                f"{prefix}-0-question": str(question_one.pk),
                f"{prefix}-0-marks_override": "",
                f"{prefix}-1-position": "2",
                f"{prefix}-1-question": str(question_two.pk),
                f"{prefix}-1-marks_override": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        assessment = AssessmentTest.objects.get(slug="admin-mixed-test")
        self.assertEqual(assessment.test_questions.count(), 2)
        self.assertEqual(
            assessment.test_questions.values_list(
                "question__topic__category__name",
                flat=True,
            ).distinct().count(),
            2,
        )
