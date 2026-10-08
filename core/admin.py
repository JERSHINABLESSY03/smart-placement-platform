from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

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
    StudentActivity,
    StudentProfile,
    Test,
    TestAnswer,
    TestAttempt,
    TestQuestion,
    TopicProgress,
)

admin.site.register(StudentProfile)
admin.site.register(TopicProgress)
admin.site.register(Question)
admin.site.register(QuestionAttempt)
admin.site.register(MockTest)
admin.site.register(MockTestAttempt)
admin.site.register(StudentActivity)
admin.site.register(AIConversation)


@admin.register(AIMessage)
class AIMessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "role", "mode", "created_at")
    list_filter = ("role", "mode", "created_at")
    search_fields = ("conversation__user__username", "conversation__title", "content")
    readonly_fields = ("conversation", "role", "content", "mode", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class TestQuestionInline(admin.TabularInline):
    model = TestQuestion
    extra = 1
    autocomplete_fields = ("question",)
    fields = ("position", "question", "marks_override")


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ("title", "difficulty", "duration_minutes", "is_published", "updated_at")
    list_filter = ("is_published", "difficulty", "duration_minutes")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
    inlines = [TestQuestionInline]


@admin.register(TestAttempt)
class TestAttemptAdmin(admin.ModelAdmin):
    list_display = ("user", "test", "status", "score", "total_marks", "started_at", "submitted_at")
    list_filter = ("status", "test", "started_at")
    search_fields = ("user__username", "user__email", "test__title")
    readonly_fields = (
        "user",
        "test",
        "status",
        "started_at",
        "deadline_at",
        "submitted_at",
        "duration_seconds",
        "total_questions",
        "total_marks",
        "score",
        "correct_count",
        "wrong_count",
        "skipped_count",
        "accuracy",
        "time_taken_seconds",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(TestAnswer)
class TestAnswerAdmin(admin.ModelAdmin):
    list_display = ("attempt", "test_question", "selected_option", "is_correct", "marks_awarded", "marked_for_review")
    list_filter = ("is_correct", "marked_for_review", "attempt__test")
    search_fields = ("attempt__user__username", "attempt__test__title", "test_question__question__question_text")
    readonly_fields = (
        "attempt",
        "test_question",
        "selected_option",
        "correct_option",
        "marks_possible",
        "is_correct",
        "marks_awarded",
        "marked_for_review",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CodingTopic)
class CodingTopicAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(CodingProblem)
class CodingProblemAdmin(admin.ModelAdmin):
    list_display = ("title", "topic", "difficulty", "is_active", "updated_at")
    list_filter = ("topic", "difficulty", "is_active")
    search_fields = ("title", "problem_statement", "description")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("topic",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("title", "slug", "topic", "difficulty", "tags", "is_active")}),
        ("Problem", {"fields": ("problem_statement", "input_format", "output_format", "constraints")}),
        ("Examples and solution notes", {"fields": ("sample_input", "sample_output", "explanation")}),
        ("Legacy compatibility", {"classes": ("collapse",), "fields": ("category", "description", "starter_code")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(CodingAttempt)
class CodingAttemptAdmin(admin.ModelAdmin):
    list_display = ("user", "problem", "passed", "attempted_at")
    list_filter = ("passed", "problem__topic", "attempted_at")
    search_fields = ("user__username", "user__email", "problem__title")
    readonly_fields = ("user", "problem", "passed", "notes", "attempted_at")


@admin.register(CodingSubmission)
class CodingSubmissionAdmin(admin.ModelAdmin):
    list_display = ("user", "problem", "language", "status", "sample_validation_status", "created_at")
    list_filter = ("language", "status", "sample_validation_status", "problem__topic")
    search_fields = ("user__username", "user__email", "problem__title")
    readonly_fields = (
        "user",
        "problem",
        "language",
        "source_code",
        "status",
        "sample_validation_status",
        "validation_message",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class AptitudeTopicInline(admin.TabularInline):
    model = AptitudeTopic
    extra = 1
    prepopulated_fields = {"slug": ("name",)}


@admin.register(AptitudeCategory)
class AptitudeCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [AptitudeTopicInline]


@admin.register(AptitudeTopic)
class AptitudeTopicAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_active", "created_at")
    list_filter = ("category", "is_active")
    search_fields = ("name", "category__name")
    prepopulated_fields = {"slug": ("name",)}


class AptitudeQuestionOptionFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        active_forms = [
            form for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False)
        ]
        correct_count = sum(form.cleaned_data.get("is_correct", False) for form in active_forms)
        if len(active_forms) != 4:
            raise ValidationError("Each aptitude question must have exactly four options.")
        if correct_count != 1:
            raise ValidationError("Mark exactly one option as the correct answer.")


class AptitudeQuestionOptionInline(admin.TabularInline):
    model = AptitudeQuestionOption
    extra = 0
    min_num = 4
    max_num = 4
    validate_min = True
    validate_max = True
    formset = AptitudeQuestionOptionFormSet
    fields = ("position", "text", "is_correct")


@admin.register(AptitudeQuestion)
class AptitudeQuestionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "topic", "difficulty", "marks", "is_active")
    list_filter = ("topic__category", "topic", "difficulty", "is_active")
    search_fields = ("question_text", "topic__name", "topic__category__name")
    autocomplete_fields = ("topic",)
    readonly_fields = ("created_at",)
    inlines = [AptitudeQuestionOptionInline]


@admin.register(AptitudeQuestionAttempt)
class AptitudeQuestionAttemptAdmin(admin.ModelAdmin):
    list_display = ("user", "question", "is_correct", "marks_awarded", "time_taken_seconds", "attempted_at")
    list_filter = ("is_correct", "question__topic__category", "attempted_at")
    search_fields = ("user__username", "user__email", "question__question_text")
    readonly_fields = (
        "user",
        "question",
        "selected_option",
        "is_correct",
        "marks_awarded",
        "time_taken_seconds",
        "attempted_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
