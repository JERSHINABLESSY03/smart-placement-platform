from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .validators import (
    validate_pdf_signature,
    validate_profile_picture_extension,
    validate_profile_picture_size,
    validate_resume_extension,
    validate_resume_size,
)


def profile_picture_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"profile_pics/{uuid4().hex}{extension}"


def resume_upload_path(instance, filename):
    return f"resumes/{uuid4().hex}.pdf"


class StudentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student_profile")
    full_name = models.CharField(max_length=200)
    college = models.CharField(max_length=200, blank=True)
    degree = models.CharField(max_length=200, blank=True)
    department = models.CharField(max_length=200, blank=True)
    graduation_year = models.PositiveIntegerField(default=2026)
    programming_languages = models.CharField(max_length=300, blank=True, default="Python, Java")
    technical_skills = models.TextField(blank=True, default="")
    preferred_job_role = models.CharField(max_length=200, blank=True, default="Software Engineer")
    preferred_domain = models.CharField(max_length=200, blank=True, default="Product Engineering")
    current_preparation_level = models.CharField(max_length=200, blank=True, default="Intermediate")
    github_url = models.URLField(blank=True, default="")
    linkedin_url = models.URLField(blank=True, default="")
    profile_picture = models.ImageField(
        upload_to=profile_picture_upload_path,
        blank=True,
        null=True,
        validators=[validate_profile_picture_extension, validate_profile_picture_size],
    )
    resume = models.FileField(
        upload_to=resume_upload_path,
        blank=True,
        null=True,
        validators=[
            validate_resume_extension,
            validate_resume_size,
            validate_pdf_signature,
        ],
    )
    bio = models.TextField(blank=True, default="")

    def __str__(self):
        return self.full_name or self.user.username


class TopicProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="topic_progress")
    topic = models.CharField(max_length=120)
    category = models.CharField(max_length=120, default="General")
    mastery_score = models.PositiveIntegerField(default=0)
    attempts = models.PositiveIntegerField(default=0)
    solved = models.PositiveIntegerField(default=0)
    accuracy = models.FloatField(default=0.0)
    last_practiced = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("user", "topic")

    def __str__(self):
        return f"{self.user.username} - {self.topic}"


class Question(models.Model):
    CATEGORY_CHOICES = [
        ("Aptitude", "Aptitude"),
        ("Logical Reasoning", "Logical Reasoning"),
        ("Verbal Ability", "Verbal Ability"),
        ("Computer Fundamentals", "Computer Fundamentals"),
        ("DBMS", "DBMS"),
        ("SQL", "SQL"),
        ("OOP", "OOP"),
        ("Operating Systems", "Operating Systems"),
        ("Computer Networks", "Computer Networks"),
        ("Data Structures", "Data Structures"),
        ("Algorithms", "Algorithms"),
        ("Programming", "Programming"),
    ]
    DIFFICULTY_CHOICES = [("Easy", "Easy"), ("Medium", "Medium"), ("Hard", "Hard")]

    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default="Medium")
    question_text = models.TextField()
    option_a = models.CharField(max_length=300)
    option_b = models.CharField(max_length=300)
    option_c = models.CharField(max_length=300)
    option_d = models.CharField(max_length=300)
    correct_option = models.CharField(max_length=10, default="A")
    explanation = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.category} - {self.question_text[:40]}"


class QuestionAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="question_attempts")
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.CharField(max_length=10)
    is_correct = models.BooleanField(default=False)
    attempted_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} -> {self.question.id}: {self.is_correct}"


class AptitudeCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Aptitude categories"

    def __str__(self):
        return self.name


class AptitudeTopic(models.Model):
    category = models.ForeignKey(
        AptitudeCategory,
        on_delete=models.CASCADE,
        related_name="topics",
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=130)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["category", "slug"], name="unique_aptitude_topic_slug_per_category"),
        ]

    def __str__(self):
        return f"{self.category.name}: {self.name}"


class AptitudeQuestion(models.Model):
    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    topic = models.ForeignKey(
        AptitudeTopic,
        on_delete=models.PROTECT,
        related_name="questions",
    )
    question_text = models.TextField()
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, default=Difficulty.MEDIUM)
    marks = models.PositiveSmallIntegerField(default=1)
    explanation = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["topic", "is_active", "difficulty"]),
        ]

    def __str__(self):
        return f"{self.topic.name}: {self.question_text[:60]}"


class AptitudeQuestionOption(models.Model):
    question = models.ForeignKey(
        AptitudeQuestion,
        on_delete=models.CASCADE,
        related_name="options",
    )
    position = models.PositiveSmallIntegerField()
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["question", "position"], name="unique_aptitude_option_position"),
            models.CheckConstraint(condition=models.Q(position__gte=1, position__lte=4), name="aptitude_option_position_1_to_4"),
        ]

    @property
    def label(self):
        return "ABCD"[self.position - 1]

    def __str__(self):
        return f"{self.question_id} - {self.label}: {self.text[:60]}"


class AptitudeQuestionAttempt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="aptitude_question_attempts",
    )
    question = models.ForeignKey(
        AptitudeQuestion,
        on_delete=models.PROTECT,
        related_name="attempts",
    )
    selected_option = models.ForeignKey(
        AptitudeQuestionOption,
        on_delete=models.PROTECT,
        related_name="attempts",
    )
    is_correct = models.BooleanField()
    marks_awarded = models.PositiveSmallIntegerField(default=0)
    time_taken_seconds = models.PositiveIntegerField(default=0)
    attempted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-attempted_at"]
        indexes = [
            models.Index(fields=["user", "attempted_at"]),
            models.Index(fields=["user", "question"]),
        ]

    def __str__(self):
        return f"{self.user.username} -> aptitude question {self.question_id}: {self.is_correct}"


class CodingTopic(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CodingProblem(models.Model):
    class Difficulty(models.TextChoices):
        EASY = "Easy", "Easy"
        MEDIUM = "Medium", "Medium"
        HARD = "Hard", "Hard"

    LEGACY_CATEGORY_CHOICES = [
        ("Basic Programming", "Basic Programming"),
        ("Arrays", "Arrays"),
        ("Strings", "Strings"),
        ("Searching", "Searching"),
        ("Sorting", "Sorting"),
        ("Linked Lists", "Linked Lists"),
        ("Stack", "Stack"),
        ("Queue", "Queue"),
        ("Trees", "Trees"),
        ("Graphs", "Graphs"),
        ("Hashing", "Hashing"),
        ("Recursion", "Recursion"),
        ("Dynamic Programming", "Dynamic Programming"),
        ("Greedy", "Greedy"),
        ("Two Pointers", "Two Pointers"),
        ("Sliding Window", "Sliding Window"),
        ("Prefix Sum", "Prefix Sum"),
        ("Data Structures", "Data Structures"),
        ("Algorithms", "Algorithms"),
        ("Programming", "Programming"),
        ("DBMS", "DBMS"),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    topic = models.ForeignKey(
        CodingTopic,
        on_delete=models.PROTECT,
        related_name="problems",
    )
    category = models.CharField(max_length=80, choices=LEGACY_CATEGORY_CHOICES, default="Basic Programming")
    difficulty = models.CharField(max_length=20, choices=Difficulty.choices, default=Difficulty.MEDIUM)
    problem_statement = models.TextField()
    description = models.TextField(blank=True, default="")
    input_format = models.TextField(blank=True, default="")
    output_format = models.TextField(blank=True, default="")
    constraints = models.TextField(blank=True, default="")
    sample_input = models.TextField(blank=True, default="")
    sample_output = models.TextField(blank=True, default="")
    explanation = models.TextField(blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    starter_code = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]
        indexes = [
            models.Index(fields=["topic", "is_active", "difficulty"]),
        ]

    @property
    def statement(self):
        return self.problem_statement or self.description

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if not isinstance(self.tags, list) or any(
            not isinstance(tag, str) or not tag.strip()
            for tag in self.tags
        ):
            raise ValidationError({"tags": "Tags must be a list of non-empty strings."})


class CodingAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coding_attempts")
    problem = models.ForeignKey(CodingProblem, on_delete=models.CASCADE)
    passed = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")
    attempted_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} -> {self.problem.title}"


class CodingSubmission(models.Model):
    class Language(models.TextChoices):
        PYTHON = "python", "Python 3"
        JAVASCRIPT = "javascript", "JavaScript"
        JAVA = "java", "Java"
        CPP = "cpp", "C++"

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        ERROR = "error", "Error"

    class ValidationStatus(models.TextChoices):
        NOT_RUN = "not_run", "Not run"
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="coding_submissions",
    )
    problem = models.ForeignKey(
        CodingProblem,
        on_delete=models.PROTECT,
        related_name="submissions",
    )
    language = models.CharField(max_length=30, choices=Language.choices)
    source_code = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RECEIVED,
    )
    sample_validation_status = models.CharField(
        max_length=20,
        choices=ValidationStatus.choices,
        default=ValidationStatus.NOT_RUN,
    )
    validation_message = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["user", "problem", "status"]),
        ]

    def __str__(self):
        return f"{self.user.username} -> {self.problem.title} ({self.status})"


class MockTest(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    category = models.CharField(max_length=80, default="Mock")
    duration_minutes = models.PositiveIntegerField(default=45)
    is_published = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_tests")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title


class MockTestAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mock_attempts")
    test = models.ForeignKey(MockTest, on_delete=models.CASCADE)
    score = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} - {self.test.title}"


class Test(models.Model):
    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveSmallIntegerField(default=60)
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, default=Difficulty.MEDIUM)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    @property
    def total_questions(self):
        return self.test_questions.count()

    @property
    def total_marks(self):
        return sum(item.marks for item in self.test_questions.all())

    def __str__(self):
        return self.title


class TestQuestion(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="test_questions")
    question = models.ForeignKey(
        AptitudeQuestion,
        on_delete=models.PROTECT,
        related_name="test_entries",
    )
    position = models.PositiveSmallIntegerField()
    marks_override = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["test", "question"], name="unique_question_per_test"),
            models.UniqueConstraint(fields=["test", "position"], name="unique_test_question_position"),
        ]

    @property
    def marks(self):
        return self.marks_override if self.marks_override is not None else self.question.marks

    def clean(self):
        super().clean()
        if self.test_id and TestAttempt.objects.filter(test_id=self.test_id).exists():
            if not self.pk:
                raise ValidationError("Questions cannot be added after a test attempt has started.")
            original = TestQuestion.objects.filter(pk=self.pk).values(
                "question_id",
                "position",
                "marks_override",
            ).first()
            if original and (
                original["question_id"] != self.question_id
                or original["position"] != self.position
                or original["marks_override"] != self.marks_override
            ):
                raise ValidationError("Questions cannot be changed after a test attempt has started.")

    def __str__(self):
        return f"{self.test.title} - Q{self.position}"


class TestAttempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        SUBMITTED = "submitted", "Submitted"
        EXPIRED = "expired", "Expired"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="test_attempts",
    )
    test = models.ForeignKey(Test, on_delete=models.PROTECT, related_name="attempts")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    started_at = models.DateTimeField(default=timezone.now)
    deadline_at = models.DateTimeField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField()
    total_questions = models.PositiveSmallIntegerField()
    total_marks = models.PositiveSmallIntegerField()
    score = models.PositiveSmallIntegerField(default=0)
    correct_count = models.PositiveSmallIntegerField(default=0)
    wrong_count = models.PositiveSmallIntegerField(default=0)
    skipped_count = models.PositiveSmallIntegerField(default=0)
    accuracy = models.FloatField(default=0.0)
    time_taken_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "test"],
                condition=models.Q(status="in_progress"),
                name="unique_active_test_attempt_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "submitted_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.test.title} ({self.status})"


class TestAnswer(models.Model):
    attempt = models.ForeignKey(TestAttempt, on_delete=models.CASCADE, related_name="answers")
    test_question = models.ForeignKey(
        TestQuestion,
        on_delete=models.PROTECT,
        related_name="answers",
    )
    selected_option = models.ForeignKey(
        AptitudeQuestionOption,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="test_answers",
    )
    correct_option = models.ForeignKey(
        AptitudeQuestionOption,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="correct_test_answers",
    )
    marks_possible = models.PositiveSmallIntegerField(null=True, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    marks_awarded = models.PositiveSmallIntegerField(default=0)
    marked_for_review = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["test_question__position"]
        constraints = [
            models.UniqueConstraint(fields=["attempt", "test_question"], name="unique_answer_per_test_question"),
        ]

    def __str__(self):
        return f"{self.attempt} - Q{self.test_question.position}"


class StudentActivity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activities")
    title = models.CharField(max_length=200)
    detail = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} - {self.title}"


class AIConversation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_conversations",
    )
    title = models.CharField(max_length=120, default="New conversation")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user.username}: {self.title}"


class AIMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Student"
        ASSISTANT = "assistant", "AI tutor"

    class Mode(models.TextChoices):
        CONCEPT = "concept", "Concept explanation"
        CODING = "coding", "Coding explanation"
        APTITUDE = "aptitude", "Aptitude explanation"
        DBMS = "dbms", "DBMS explanation"
        SQL = "sql", "SQL explanation"
        PRACTICE = "practice", "Practice questions"
        HINT = "hint", "Hint"
        MISTAKE = "mistake", "Mistake explanation"
        RECOMMENDATION = "recommendation", "Study recommendation"

    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=12, choices=Role.choices)
    content = models.TextField()
    mode = models.CharField(max_length=20, choices=Mode.choices, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["conversation", "created_at"])]

    def __str__(self):
        return f"{self.conversation_id} {self.role}: {self.content[:40]}"
