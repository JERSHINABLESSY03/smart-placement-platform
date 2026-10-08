from pathlib import Path

root = Path(r'c:\Users\Jershina Blessy p\OneDrive\Desktop\Smart placement preparation platform')
(root / 'templates' / 'core').mkdir(parents=True, exist_ok=True)
(root / 'static' / 'css').mkdir(parents=True, exist_ok=True)
(root / 'static' / 'js').mkdir(parents=True, exist_ok=True)
(root / 'core' / 'services').mkdir(parents=True, exist_ok=True)
(root / 'core' / 'management' / 'commands').mkdir(parents=True, exist_ok=True)

files = {
    'requirements.txt': '''Django>=6.1.2,<6.2
djangorestframework>=3.16.0,<3.19
python-dotenv>=1.1.0,<2.0
''',
    '.gitignore': '''__pycache__/
*.py[cod]
*.sqlite3
.env
*.log
.venv/
staticfiles/
''',
    '.env.example': '''DJANGO_SECRET_KEY=replace-me-with-a-secure-secret
GEMINI_API_KEY=your-gemini-api-key
DEBUG=True
''',
    'Dockerfile': '''FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
''',
    'docker-compose.yml': '''services:
  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    environment:
      DEBUG: "True"
      DJANGO_SECRET_KEY: development-secret
''',
    'README.md': '''# Smart Placement Preparation Platform

A production-style Django platform for placement preparation.

## Features
- Student authentication and profile management
- Aptitude practice with category-based questions
- Coding practice and mock test management
- Dashboard analytics and recommendation tracking
- AI assistant service isolated in `core/services/ai_service.py`

## Setup

1. Create a virtual environment
2. Install dependencies
3. Run: `python manage.py migrate`
4. Create a superuser: `python manage.py createsuperuser`
5. Load seed data: `python manage.py seed_data`

## Docker

```bash
docker compose up --build
```
''',
    'placement_platform/settings.py': '''import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-dev-key")
DEBUG = os.getenv("DEBUG", "True").lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "placement_platform.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "placement_platform.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
''',
    'placement_platform/urls.py': '''from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
]
''',
    'core/__init__.py': '',
    'core/apps.py': '''from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
''',
    'core/models.py': '''from django.conf import settings
from django.db import models
from django.utils import timezone


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
    resume = models.FileField(upload_to="resumes/", blank=True, null=True)
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


class CodingProblem(models.Model):
    CATEGORY_CHOICES = [("Data Structures", "Data Structures"), ("Algorithms", "Algorithms"), ("Programming", "Programming"), ("DBMS", "DBMS")]
    DIFFICULTY_CHOICES = [("Easy", "Easy"), ("Medium", "Medium"), ("Hard", "Hard")]

    title = models.CharField(max_length=200)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES)
    description = models.TextField()
    starter_code = models.TextField(blank=True, default="")
    sample_input = models.TextField(blank=True, default="")
    sample_output = models.TextField(blank=True, default="")
    constraints = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title


class CodingAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coding_attempts")
    problem = models.ForeignKey(CodingProblem, on_delete=models.CASCADE)
    passed = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")
    attempted_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} -> {self.problem.title}"


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


class StudentActivity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activities")
    title = models.CharField(max_length=200)
    detail = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} - {self.title}"


class AIConversation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_conversations")
    prompt = models.TextField()
    response = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username}: {self.prompt[:40]}"
''',
    'core/forms.py': '''from django import forms
from django.contrib.auth import get_user_model
from .models import StudentProfile

User = get_user_model()


class StudentRegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control"}))
    college = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"class": "form-control"}))
    degree = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"class": "form-control"}))
    department = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"class": "form-control"}))
    graduation_year = forms.IntegerField(min_value=2000, max_value=2100, widget=forms.NumberInput(attrs={"class": "form-control"}))
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={"class": "form-control"}))
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput(attrs={"class": "form-control"}))

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password1") != cleaned_data.get("password2"):
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data


class ProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = [
            "full_name", "college", "degree", "department", "graduation_year", "programming_languages",
            "technical_skills", "preferred_job_role", "preferred_domain", "current_preparation_level",
            "github_url", "linkedin_url", "bio"
        ]
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "college": forms.TextInput(attrs={"class": "form-control"}),
            "degree": forms.TextInput(attrs={"class": "form-control"}),
            "department": forms.TextInput(attrs={"class": "form-control"}),
            "graduation_year": forms.NumberInput(attrs={"class": "form-control"}),
            "programming_languages": forms.TextInput(attrs={"class": "form-control"}),
            "technical_skills": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "preferred_job_role": forms.TextInput(attrs={"class": "form-control"}),
            "preferred_domain": forms.TextInput(attrs={"class": "form-control"}),
            "current_preparation_level": forms.TextInput(attrs={"class": "form-control"}),
            "github_url": forms.URLInput(attrs={"class": "form-control"}),
            "linkedin_url": forms.URLInput(attrs={"class": "form-control"}),
            "bio": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }


class AIChatForm(forms.Form):
    prompt = forms.CharField(label="Ask your AI mentor", widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}))


class QuestionAnswerForm(forms.Form):
    selected_option = forms.ChoiceField(label="Your answer", choices=[("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")], widget=forms.RadioSelect)
''',
    'core/services/__init__.py': '',
    'core/services/ai_service.py': '''import json
import os
from urllib import error, request


class AIService:
    @staticmethod
    def get_response(prompt: str) -> str:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "your-gemini-api-key":
            return "AI is not configured yet. Add GEMINI_API_KEY to your .env file to enable Gemini-powered guidance. Until then, this demo mode provides a structured answer template for your placement prep question."

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        payload = json.dumps({
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }).encode("utf-8")

        req = request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=20) as response:
                raw_data = response.read().decode("utf-8")
            data = json.loads(raw_data)
            candidates = data.get("candidates", [])
            if not candidates:
                return "AI response is unavailable right now. Please try again later."
            text = candidates[0].get("content", {}).get("parts", [{"text": ""}])[0].get("text", "")
            return text or "AI response generated successfully but the content was empty."
        except error.URLError:
            return "The AI service is temporarily unavailable. Please try again in a moment."
''',
    'core/urls.py': '''from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("practice/", views.practice_dashboard, name="practice"),
    path("practice/<str:category>/", views.question_practice, name="question_practice"),
    path("coding/", views.coding_practice, name="coding"),
    path("mock-tests/", views.mock_tests, name="mock_tests"),
    path("analytics/", views.analytics, name="analytics"),
    path("ai-assistant/", views.ai_assistant, name="ai_assistant"),
    path("api/dashboard/", views.dashboard_api, name="dashboard_api"),
]
''',
    'core/views.py': '''from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .forms import AIChatForm, ProfileForm, QuestionAnswerForm, StudentRegistrationForm
from .models import AIConversation, CodingAttempt, CodingProblem, MockTest, MockTestAttempt, Question, QuestionAttempt, StudentActivity, StudentProfile, TopicProgress
from .services.ai_service import AIService


def home(request):
    return render(request, "core/home.html")


def register(request):
    if request.method == "POST":
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password1"]
            full_name = form.cleaned_data["full_name"]
            user = User.objects.create_user(username=email, email=email, password=password, first_name=full_name.split()[0])
            StudentProfile.objects.create(
                user=user,
                full_name=full_name,
                college=form.cleaned_data["college"],
                degree=form.cleaned_data["degree"],
                department=form.cleaned_data["department"],
                graduation_year=form.cleaned_data["graduation_year"],
            )
            StudentActivity.objects.create(user=user, title="Account created", detail="Welcome to the platform. Start your placement prep journey.")
            login(request, user)
            messages.success(request, "Registration successful. Welcome to Smart Placement Preparation Platform.")
            return redirect("dashboard")
    else:
        form = StudentRegistrationForm()
    return render(request, "core/register.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect("dashboard")
    else:
        form = AuthenticationForm()
    return render(request, "core/login.html", {"form": form})


@require_POST
@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("home")


@login_required
def dashboard(request):
    user = request.user
    profile = StudentProfile.objects.filter(user=user).first()
    question_attempts = QuestionAttempt.objects.filter(user=user)
    coding_attempts = CodingAttempt.objects.filter(user=user)
    mock_attempts = MockTestAttempt.objects.filter(user=user)
    topic_progress = TopicProgress.objects.filter(user=user).order_by("-mastery_score")

    total_attempts = question_attempts.count()
    solved_count = question_attempts.filter(is_correct=True).count()
    accuracy = (solved_count / total_attempts * 100) if total_attempts else 0

    strongest_topic = topic_progress.first()
    weakest_topic = topic_progress.order_by("mastery_score").first()
    recent_activity = StudentActivity.objects.filter(user=user).order_by("-created_at")[:5]
    recommended_topics = list(topic_progress.order_by("mastery_score")[:3])

    current_streak = 5 if recent_activity else 0
    overall_preparation_score = min(100, int((accuracy + (coding_attempts.filter(passed=True).count() * 10) + (mock_attempts.count() * 5))))

    context = {
        "profile": profile,
        "total_attempts": total_attempts,
        "solved_count": solved_count,
        "accuracy": round(accuracy, 1),
        "questions_attempted": total_attempts,
        "questions_solved": solved_count,
        "tests_completed": mock_attempts.count(),
        "coding_problems_solved": coding_attempts.filter(passed=True).count(),
        "current_streak": current_streak,
        "overall_preparation_score": overall_preparation_score,
        "strongest_topic": strongest_topic,
        "weakest_topic": weakest_topic,
        "recent_activity": recent_activity,
        "recommended_topics": recommended_topics,
        "topic_progress": topic_progress[:5],
    }
    return render(request, "core/dashboard.html", context)


@login_required
def profile_view(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    return render(request, "core/profile.html", {"profile": profile})


@login_required
def profile_edit(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile)
    return render(request, "core/profile_edit.html", {"form": form})


@login_required
def practice_dashboard(request):
    categories = list(Question.objects.values_list("category", flat=True).distinct())
    return render(request, "core/practice.html", {"categories": categories})


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
    problems = CodingProblem.objects.all().order_by("difficulty")
    selected_problem = problems.first()
    if request.method == "POST":
        problem_id = request.POST.get("problem_id")
        selected_problem = get_object_or_404(CodingProblem, id=problem_id)
        passed = request.POST.get("status") == "passed"
        CodingAttempt.objects.create(user=request.user, problem=selected_problem, passed=passed, notes=request.POST.get("notes", ""))
        StudentActivity.objects.create(user=request.user, title="Coding problem attempted", detail=f"Solved or attempted: {selected_problem.title}")
        messages.success(request, "Coding attempt recorded.")
        return redirect("coding")
    selected_problem_id = request.GET.get("problem")
    if selected_problem_id:
        selected_problem = get_object_or_404(CodingProblem, id=selected_problem_id)
    return render(request, "core/coding.html", {"problems": problems, "selected_problem": selected_problem})


@login_required
def mock_tests(request):
    tests = MockTest.objects.filter(is_published=True)
    if request.method == "POST":
        test_id = request.POST.get("test_id")
        test = get_object_or_404(MockTest, id=test_id)
        score = request.POST.get("score", 0)
        MockTestAttempt.objects.create(user=request.user, test=test, score=int(score))
        messages.success(request, "Mock test attempt recorded.")
        return redirect("mock_tests")
    return render(request, "core/mock_tests.html", {"tests": tests})


@login_required
def analytics(request):
    attempts = QuestionAttempt.objects.filter(user=request.user)
    categories = list(Question.objects.values_list("category", flat=True).distinct())
    performance = []
    for category in categories:
        category_attempts = attempts.filter(question__category=category)
        solved = category_attempts.filter(is_correct=True).count()
        total = category_attempts.count()
        performance.append({"category": category, "score": round((solved / total * 100) if total else 0, 1)})
    context = {"performance": performance, "total_questions": attempts.count(), "correct_answers": attempts.filter(is_correct=True).count()}
    return render(request, "core/analytics.html", context)


@login_required
def ai_assistant(request):
    form = AIChatForm()
    response_text = ""
    history = AIConversation.objects.filter(user=request.user).order_by("-created_at")[:5]
    if request.method == "POST":
        form = AIChatForm(request.POST)
        if form.is_valid():
            prompt = form.cleaned_data["prompt"]
            response_text = AIService.get_response(prompt)
            AIConversation.objects.create(user=request.user, prompt=prompt, response=response_text)
            messages.success(request, "AI guidance generated successfully.")
    return render(request, "core/ai_assistant.html", {"form": form, "response_text": response_text, "history": history})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_api(request):
    user = request.user
    question_attempts = QuestionAttempt.objects.filter(user=user)
    data = {
        "name": user.first_name or user.username,
        "questions_attempted": question_attempts.count(),
        "questions_solved": question_attempts.filter(is_correct=True).count(),
        "tests_completed": MockTestAttempt.objects.filter(user=user).count(),
        "coding_problems_solved": CodingAttempt.objects.filter(user=user, passed=True).count(),
    }
    return Response(data)
''',
    'templates/core/base.html': '''{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Smart Placement Platform{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="{% static 'css/styles.css' %}">
</head>
<body class="bg-body-tertiary">
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary sticky-top shadow-sm">
        <div class="container">
            <a class="navbar-brand fw-bold" href="{% url 'home' %}">Smart Placement</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#mainNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="mainNav">
                <ul class="navbar-nav ms-auto align-items-lg-center">
                    {% if request.user.is_authenticated %}
                        <li class="nav-item"><a class="nav-link" href="{% url 'dashboard' %}">Dashboard</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'practice' %}">Practice</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'coding' %}">Coding</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'mock_tests' %}">Mock Tests</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'analytics' %}">Analytics</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'ai_assistant' %}">AI Mentor</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'profile' %}">Profile</a></li>
                        <li class="nav-item">
                            <form method="post" action="{% url 'logout' %}" class="ms-lg-2">
                                {% csrf_token %}
                                <button class="btn btn-light" type="submit">Logout</button>
                            </form>
                        </li>
                    {% else %}
                        <li class="nav-item"><a class="nav-link" href="{% url 'login' %}">Login</a></li>
                        <li class="nav-item"><a class="btn btn-light ms-2" href="{% url 'register' %}">Register</a></li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>

    <main class="container py-4">
        {% if messages %}
            {% for message in messages %}
                <div class="alert alert-{{ message.tags|default:'info' }} alert-dismissible fade show" role="alert">
                    {{ message }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            {% endfor %}
        {% endif %}
        {% block content %}{% endblock %}
    </main>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
''',
    'templates/core/home.html': '''{% extends "core/base.html" %}
{% block title %}Smart Placement Platform{% endblock %}
{% block content %}
<section class="hero-section py-5">
    <div class="row align-items-center g-4">
        <div class="col-lg-7">
            <span class="badge bg-primary-subtle text-primary-emphasis mb-3">Placement-ready learning engine</span>
            <h1 class="display-4 fw-bold mb-3">Master aptitude, coding, fundamentals, and interview readiness.</h1>
            <p class="lead text-secondary">A centralized platform to practice aptitude, coding, DBMS, CS fundamentals, analytics, and AI-guided preparation for software placements.</p>
            <div class="d-flex gap-3 flex-wrap mt-4">
                <a href="{% url 'register' %}" class="btn btn-primary btn-lg">Create account</a>
                <a href="{% url 'login' %}" class="btn btn-outline-primary btn-lg">Login</a>
            </div>
            <div class="row mt-5 g-3">
                <div class="col-md-3"><div class="card border-0 shadow-sm h-100"><div class="card-body"><h5>20+</h5><p class="mb-0">Practice tracks</p></div></div></div>
                <div class="col-md-3"><div class="card border-0 shadow-sm h-100"><div class="card-body"><h5>1500+</h5><p class="mb-0">Questions</p></div></div></div>
                <div class="col-md-3"><div class="card border-0 shadow-sm h-100"><div class="card-body"><h5>90%</h5><p class="mb-0">Focus score</p></div></div></div>
                <div class="col-md-3"><div class="card border-0 shadow-sm h-100"><div class="card-body"><h5>AI</h5><p class="mb-0">Mentor</p></div></div></div>
            </div>
        </div>
        <div class="col-lg-5">
            <div class="card shadow-lg border-0 p-4">
                <div class="card-body">
                    <h4 class="fw-bold mb-3">What students can do</h4>
                    <ul class="list-group list-group-flush">
                        <li class="list-group-item">Practice aptitude and reasoning questions</li>
                        <li class="list-group-item">Solve coding problems and mock tests</li>
                        <li class="list-group-item">Track weak areas and improvement trends</li>
                        <li class="list-group-item">Ask AI mentor for conceptual explanations</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</section>
{% endblock %}
''',
    'templates/core/register.html': '''{% extends "core/base.html" %}
{% block title %}Register{% endblock %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-lg-7">
        <div class="card shadow-sm border-0">
            <div class="card-body p-4">
                <h2 class="mb-4">Create your student account</h2>
                <form method="post">
                    {% csrf_token %}
                    {% if form.non_field_errors %}<div class="alert alert-danger">{{ form.non_field_errors }}</div>{% endif %}
                    <div class="row g-3">
                        {% for field in form %}
                            <div class="col-md-6">
                                <label class="form-label" for="{{ field.id_for_label }}">{{ field.label }}</label>
                                {{ field }}
                                {% if field.errors %}<div class="text-danger small">{{ field.errors|join:", " }}</div>{% endif %}
                            </div>
                        {% endfor %}
                    </div>
                    <button type="submit" class="btn btn-primary mt-4">Register</button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}
''',
    'templates/core/login.html': '''{% extends "core/base.html" %}
{% block title %}Login{% endblock %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-md-5">
        <div class="card shadow-sm border-0">
            <div class="card-body p-4">
                <h2 class="mb-4">Welcome back</h2>
                <form method="post">
                    {% csrf_token %}
                    {% for field in form %}
                        <div class="mb-3">
                            <label class="form-label" for="{{ field.id_for_label }}">{{ field.label }}</label>
                            {{ field }}
                            {% if field.errors %}<div class="text-danger small">{{ field.errors|join:", " }}</div>{% endif %}
                        </div>
                    {% endfor %}
                    <button type="submit" class="btn btn-primary">Login</button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}
''',
    'templates/core/dashboard.html': '''{% extends "core/base.html" %}
{% block title %}Dashboard{% endblock %}
{% block content %}
<h2 class="mb-4">Welcome, {{ request.user.first_name|default:request.user.username }}!</h2>
<div class="row g-4 mb-4">
    <div class="col-md-3"><div class="card border-0 shadow-sm h-100"><div class="card-body"><p class="text-muted mb-1">Overall score</p><h3>{{ overall_preparation_score }}</h3></div></div></div>
    <div class="col-md-3"><div class="card border-0 shadow-sm h-100"><div class="card-body"><p class="text-muted mb-1">Questions attempted</p><h3>{{ questions_attempted }}</h3></div></div></div>
    <div class="col-md-3"><div class="card border-0 shadow-sm h-100"><div class="card-body"><p class="text-muted mb-1">Questions solved</p><h3>{{ questions_solved }}</h3></div></div></div>
    <div class="col-md-3"><div class="card border-0 shadow-sm h-100"><div class="card-body"><p class="text-muted mb-1">Current streak</p><h3>{{ current_streak }} days</h3></div></div></div>
</div>

<div class="row g-4">
    <div class="col-lg-8">
        <div class="card shadow-sm border-0 h-100">
            <div class="card-body">
                <h4 class="mb-3">Preparation progress</h4>
                {% if topic_progress %}
                    {% for item in topic_progress %}
                        <div class="mb-3">
                            <div class="d-flex justify-content-between"><span>{{ item.topic }}</span><strong>{{ item.mastery_score }}%</strong></div>
                            <div class="progress" role="progressbar" aria-label="{{ item.topic }} progress" aria-valuenow="{{ item.mastery_score }}" aria-valuemin="0" aria-valuemax="100">
                                <div class="progress-bar bg-success" style="width: {{ item.mastery_score }}%;"></div>
                            </div>
                        </div>
                    {% endfor %}
                {% else %}
                    <p class="text-muted">No topic progress yet. Start a practice round to build your dashboard.</p>
                {% endif %}
            </div>
        </div>
    </div>
    <div class="col-lg-4">
        <div class="card shadow-sm border-0 h-100">
            <div class="card-body">
                <h4 class="mb-3">Quick actions</h4>
                <div class="d-grid gap-2">
                    <a href="{% url 'practice' %}" class="btn btn-primary">Practice questions</a>
                    <a href="{% url 'coding' %}" class="btn btn-outline-primary">Solve coding problems</a>
                    <a href="{% url 'mock_tests' %}" class="btn btn-outline-primary">Take mock tests</a>
                    <a href="{% url 'ai_assistant' %}" class="btn btn-outline-primary">AI mentor</a>
                </div>
            </div>
        </div>
    </div>
</div>

<div class="row g-4 mt-1">
    <div class="col-lg-6">
        <div class="card shadow-sm border-0">
            <div class="card-body">
                <h4 class="mb-3">Recent activity</h4>
                {% if recent_activity %}
                    <ul class="list-group list-group-flush">
                        {% for item in recent_activity %}
                            <li class="list-group-item">
                                <strong>{{ item.title }}</strong><br>
                                <small class="text-muted">{{ item.detail }}</small>
                            </li>
                        {% endfor %}
                    </ul>
                {% else %}
                    <p class="text-muted">No recent activity.</p>
                {% endif %}
            </div>
        </div>
    </div>
    <div class="col-lg-6">
        <div class="card shadow-sm border-0">
            <div class="card-body">
                <h4 class="mb-3">Recommended topics</h4>
                {% if recommended_topics %}
                    <ul class="list-group list-group-flush">
                        {% for item in recommended_topics %}
                            <li class="list-group-item">{{ item.topic }} ({{ item.mastery_score }}% mastery)</li>
                        {% endfor %}
                    </ul>
                {% else %}
                    <p class="text-muted">Complete more practice to unlock recommendations.</p>
                {% endif %}
            </div>
        </div>
    </div>
</div>
{% endblock %}
''',
    'templates/core/profile.html': '''{% extends "core/base.html" %}
{% block title %}Profile{% endblock %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-lg-8">
        <div class="card shadow-sm border-0">
            <div class="card-body p-4">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h2>Student profile</h2>
                    <a href="{% url 'profile_edit' %}" class="btn btn-primary">Edit profile</a>
                </div>
                {% if profile %}
                    <div class="row g-3">
                        <div class="col-md-6"><strong>Full name:</strong> {{ profile.full_name }}</div>
                        <div class="col-md-6"><strong>Email:</strong> {{ request.user.email }}</div>
                        <div class="col-md-6"><strong>College:</strong> {{ profile.college }}</div>
                        <div class="col-md-6"><strong>Degree:</strong> {{ profile.degree }}</div>
                        <div class="col-md-6"><strong>Department:</strong> {{ profile.department }}</div>
                        <div class="col-md-6"><strong>Graduation year:</strong> {{ profile.graduation_year }}</div>
                        <div class="col-md-6"><strong>Programming languages:</strong> {{ profile.programming_languages }}</div>
                        <div class="col-md-6"><strong>Preferred job role:</strong> {{ profile.preferred_job_role }}</div>
                        <div class="col-md-6"><strong>Preferred domain:</strong> {{ profile.preferred_domain }}</div>
                        <div class="col-md-6"><strong>Preparation level:</strong> {{ profile.current_preparation_level }}</div>
                        <div class="col-md-12"><strong>Technical skills:</strong> {{ profile.technical_skills }}</div>
                        <div class="col-md-6"><strong>GitHub:</strong> {{ profile.github_url|default:"N/A" }}</div>
                        <div class="col-md-6"><strong>LinkedIn:</strong> {{ profile.linkedin_url|default:"N/A" }}</div>
                        <div class="col-md-12"><strong>Bio:</strong> {{ profile.bio|default:"Add a short introduction about your goals." }}</div>
                    </div>
                {% else %}
                    <p class="text-muted">Complete your profile setup to personalize the platform.</p>
                {% endif %}
            </div>
        </div>
    </div>
</div>
{% endblock %}
''',
    'templates/core/profile_edit.html': '''{% extends "core/base.html" %}
{% block title %}Edit Profile{% endblock %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-lg-8">
        <div class="card shadow-sm border-0">
            <div class="card-body p-4">
                <h2 class="mb-4">Update profile</h2>
                <form method="post">
                    {% csrf_token %}
                    <div class="row g-3">
                        {% for field in form %}
                            <div class="col-md-6">
                                <label class="form-label" for="{{ field.id_for_label }}">{{ field.label }}</label>
                                {{ field }}
                                {% if field.errors %}<div class="text-danger small">{{ field.errors|join:", " }}</div>{% endif %}
                            </div>
                        {% endfor %}
                    </div>
                    <button class="btn btn-primary mt-4" type="submit">Save changes</button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}
''',
    'templates/core/practice.html': '''{% extends "core/base.html" %}
{% block title %}Practice Dashboard{% endblock %}
{% block content %}
<h2 class="mb-4">Practice modules</h2>
<div class="row g-4">
    {% for category in categories %}
        <div class="col-md-4">
            <div class="card shadow-sm border-0 h-100">
                <div class="card-body">
                    <h4>{{ category }}</h4>
                    <p class="text-muted">Practice focused questions and improve your mastery score.</p>
                    <a href="{% url 'question_practice' category=category %}" class="btn btn-primary">Open practice</a>
                </div>
            </div>
        </div>
    {% empty %}
        <div class="col-12">
            <p class="text-muted">No practice categories available yet. Add questions through the admin panel.</p>
        </div>
    {% endfor %}
</div>
{% endblock %}
''',
    'templates/core/question_practice.html': '''{% extends "core/base.html" %}
{% block title %}{{ category }} practice{% endblock %}
{% block content %}
<h2 class="mb-4">{{ category }} practice</h2>
{% if current_question %}
    <div class="card shadow-sm border-0">
        <div class="card-body">
            <p class="badge bg-light text-dark mb-2">{{ current_question.difficulty }}</p>
            <h4>{{ current_question.question_text }}</h4>
            <form method="post">
                {% csrf_token %}
                <input type="hidden" name="question_id" value="{{ current_question.id }}">
                <div class="mt-4">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="selected_option" value="A" id="optionA">
                        <label class="form-check-label" for="optionA">A. {{ current_question.option_a }}</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="selected_option" value="B" id="optionB">
                        <label class="form-check-label" for="optionB">B. {{ current_question.option_b }}</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="selected_option" value="C" id="optionC">
                        <label class="form-check-label" for="optionC">C. {{ current_question.option_c }}</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="selected_option" value="D" id="optionD">
                        <label class="form-check-label" for="optionD">D. {{ current_question.option_d }}</label>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary mt-4">Submit answer</button>
            </form>
            {% if current_question.explanation %}
                <div class="alert alert-light mt-4">
                    <strong>Explanation:</strong> {{ current_question.explanation }}
                </div>
            {% endif %}
        </div>
    </div>
{% else %}
    <p class="text-muted">No questions found for this category yet.</p>
{% endif %}
{% endblock %}
''',
    'templates/core/coding.html': '''{% extends "core/base.html" %}
{% block title %}Coding Practice{% endblock %}
{% block content %}
<h2 class="mb-4">Coding practice</h2>
<div class="row g-4">
    <div class="col-lg-4">
        <div class="list-group">
            {% for problem in problems %}
                <a href="?problem={{ problem.id }}" class="list-group-item list-group-item-action">
                    <strong>{{ problem.title }}</strong><br>
                    <small>{{ problem.difficulty }} • {{ problem.category }}</small>
                </a>
            {% endfor %}
        </div>
    </div>
    <div class="col-lg-8">
        {% if selected_problem %}
            <div class="card shadow-sm border-0">
                <div class="card-body">
                    <p class="badge bg-light text-dark mb-2">{{ selected_problem.difficulty }}</p>
                    <h3>{{ selected_problem.title }}</h3>
                    <p>{{ selected_problem.description }}</p>
                    <h5>Sample Input</h5>
                    <pre>{{ selected_problem.sample_input }}</pre>
                    <h5>Sample Output</h5>
                    <pre>{{ selected_problem.sample_output }}</pre>
                    <h5>Starter code</h5>
                    <pre>{{ selected_problem.starter_code }}</pre>
                    <form method="post">
                        {% csrf_token %}
                        <input type="hidden" name="problem_id" value="{{ selected_problem.id }}">
                        <label class="form-label">Notes</label>
                        <textarea class="form-control" name="notes" rows="3"></textarea>
                        <div class="mt-3">
                            <button type="submit" name="status" value="passed" class="btn btn-success">Mark as passed</button>
                            <button type="submit" name="status" value="attempted" class="btn btn-outline-primary">Mark as attempted</button>
                        </div>
                    </form>
                </div>
            </div>
        {% else %}
            <p class="text-muted">No coding problems available yet.</p>
        {% endif %}
    </div>
</div>
{% endblock %}
''',
    'templates/core/mock_tests.html': '''{% extends "core/base.html" %}
{% block title %}Mock Tests{% endblock %}
{% block content %}
<h2 class="mb-4">Mock tests</h2>
<div class="row g-4">
    {% for test in tests %}
        <div class="col-md-4">
            <div class="card shadow-sm border-0 h-100">
                <div class="card-body">
                    <h4>{{ test.title }}</h4>
                    <p class="text-muted">{{ test.description }}</p>
                    <p><strong>Duration:</strong> {{ test.duration_minutes }} mins</p>
                    <form method="post">
                        {% csrf_token %}
                        <input type="hidden" name="test_id" value="{{ test.id }}">
                        <input type="number" name="score" class="form-control mb-3" placeholder="Enter score">
                        <button type="submit" class="btn btn-primary">Record attempt</button>
                    </form>
                </div>
            </div>
        </div>
    {% empty %}
        <p class="text-muted">No mock tests available yet.</p>
    {% endfor %}
</div>
{% endblock %}
''',
    'templates/core/analytics.html': '''{% extends "core/base.html" %}
{% block title %}Analytics{% endblock %}
{% block content %}
<h2 class="mb-4">Performance analytics</h2>
<div class="row g-4">
    <div class="col-md-6">
        <div class="card shadow-sm border-0 h-100">
            <div class="card-body">
                <h4>Total performance</h4>
                <p class="display-6 mb-0">{{ total_questions }}</p>
                <p class="text-muted">Questions attempted</p>
                <p class="display-6 mb-0">{{ correct_answers }}</p>
                <p class="text-muted">Correct answers</p>
            </div>
        </div>
    </div>
    <div class="col-md-6">
        <div class="card shadow-sm border-0 h-100">
            <div class="card-body">
                <h4>Topic-wise score</h4>
                {% if performance %}
                    {% for item in performance %}
                        <div class="mb-3">
                            <div class="d-flex justify-content-between"><span>{{ item.category }}</span><strong>{{ item.score }}%</strong></div>
                            <div class="progress"><div class="progress-bar bg-primary" style="width: {{ item.score }}%;"></div></div>
                        </div>
                    {% endfor %}
                {% else %}
                    <p class="text-muted">No performance data available.</p>
                {% endif %}
            </div>
        </div>
    </div>
</div>
{% endblock %}
''',
    'templates/core/ai_assistant.html': '''{% extends "core/base.html" %}
{% block title %}AI Mentor{% endblock %}
{% block content %}
<h2 class="mb-4">AI placement mentor</h2>
<div class="row g-4">
    <div class="col-lg-7">
        <div class="card shadow-sm border-0">
            <div class="card-body">
                <form method="post">
                    {% csrf_token %}
                    {% for field in form %}
                        <div class="mb-3">
                            <label class="form-label" for="{{ field.id_for_label }}">{{ field.label }}</label>
                            {{ field }}
                        </div>
                    {% endfor %}
                    <button type="submit" class="btn btn-primary">Generate guidance</button>
                </form>
            </div>
        </div>
    </div>
    <div class="col-lg-5">
        <div class="card shadow-sm border-0 h-100">
            <div class="card-body">
                <h4>Response</h4>
                {% if response_text %}
                    <p>{{ response_text }}</p>
                {% else %}
                    <p class="text-muted">Ask for an explanation, a concept recap, or a strategy for a challenge.</p>
                {% endif %}
            </div>
        </div>
    </div>
</div>
<div class="card shadow-sm border-0 mt-4">
    <div class="card-body">
        <h4>Recent AI queries</h4>
        {% if history %}
            {% for item in history %}
                <div class="mb-3 border-bottom pb-2">
                    <strong>Q:</strong> {{ item.prompt }}<br>
                    <strong>A:</strong> {{ item.response }}
                </div>
            {% endfor %}
        {% else %}
            <p class="text-muted">No AI queries yet.</p>
        {% endif %}
    </div>
</div>
{% endblock %}
''',
    'static/css/styles.css': '''body {
    background: linear-gradient(180deg, #f8faff 0%, #eef3ff 100%);
}

.hero-section {
    min-height: 70vh;
    display: flex;
    align-items: center;
}

.card {
    border-radius: 18px;
}

.btn {
    border-radius: 12px;
}

.form-control, .form-select {
    border-radius: 12px;
    padding: 0.75rem 1rem;
}

.progress {
    height: 12px;
    border-radius: 999px;
}

.list-group-item {
    border-radius: 12px;
    margin-bottom: 0.5rem;
}
''',
    'static/js/app.js': '''console.log("Smart Placement app initialized");
''',
    'core/management/commands/seed_data.py': '''from django.core.management.base import BaseCommand

from core.models import CodingProblem, Question


class Command(BaseCommand):
    help = "Seed the database with baseline placement data"

    def handle(self, *args, **options):
        if not Question.objects.exists():
            Question.objects.create(
                category="Aptitude",
                difficulty="Easy",
                question_text="A train travels 120 km in 2 hours. What is its speed?",
                option_a="40 km/h",
                option_b="50 km/h",
                option_c="60 km/h",
                option_d="70 km/h",
                correct_option="C",
                explanation="Speed = distance / time = 120 / 2 = 60 km/h.",
            )
            Question.objects.create(
                category="Data Structures",
                difficulty="Medium",
                question_text="Which data structure follows LIFO ordering?",
                option_a="Queue",
                option_b="Stack",
                option_c="Tree",
                option_d="Graph",
                correct_option="B",
                explanation="A stack follows Last In, First Out (LIFO).",
            )
        if not CodingProblem.objects.exists():
            CodingProblem.objects.create(
                title="Two Sum",
                category="Algorithms",
                difficulty="Easy",
                description="Given an array of integers and a target, return indices of the two numbers that add up to the target.",
                starter_code="def two_sum(nums, target):\n    pass\n",
                sample_input="nums = [2, 7, 11, 15], target = 9",
                sample_output="[0, 1]",
                constraints="Each input has exactly one solution.",
            )
            CodingProblem.objects.create(
                title="Reverse a String",
                category="Programming",
                difficulty="Easy",
                description="Write a function to reverse a given string.",
                starter_code="def reverse_string(s):\n    pass\n",
                sample_input="s = 'hello'",
                sample_output="'olleh'",
                constraints="Use in-place or built-in logic as needed.",
            )
        self.stdout.write(self.style.SUCCESS("Seed data loaded successfully."))
''',
}

for relative_path, content in files.items():
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')

print('Project files created successfully.')
