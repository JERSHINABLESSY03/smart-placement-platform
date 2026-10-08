from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health_check, name="health_check"),
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/files/<str:file_kind>/", views.profile_file, name="profile_file"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("practice/", views.practice_dashboard, name="practice"),
    path("practice/category/<slug:category_slug>/", views.aptitude_category, name="aptitude_category"),
    path(
        "practice/category/<slug:category_slug>/topic/<slug:topic_slug>/",
        views.aptitude_topic,
        name="aptitude_topic",
    ),
    path("practice/question/<int:question_id>/", views.aptitude_question, name="aptitude_question"),
    path(
        "practice/attempts/<int:attempt_id>/",
        views.aptitude_attempt_result,
        name="aptitude_attempt_result",
    ),
    path("practice/<str:category>/", views.question_practice, name="question_practice"),
    path("coding/", views.coding_practice, name="coding"),
    path("coding/problems/<slug:slug>/", views.coding_problem_detail, name="coding_problem_detail"),
    path(
        "coding/submissions/<int:submission_id>/",
        views.coding_submission_result,
        name="coding_submission_result",
    ),
    path("mock-tests/", views.mock_tests, name="mock_tests"),
    path("mock-tests/attempts/<int:attempt_id>/", views.test_attempt, name="test_attempt"),
    path(
        "mock-tests/attempts/<int:attempt_id>/answers/",
        views.save_test_answer_view,
        name="save_test_answer",
    ),
    path(
        "mock-tests/attempts/<int:attempt_id>/submit/",
        views.submit_test_attempt,
        name="submit_test_attempt",
    ),
    path(
        "mock-tests/attempts/<int:attempt_id>/result/",
        views.test_result,
        name="test_result",
    ),
    path("analytics/", views.analytics, name="analytics"),
    path("api/analytics/", views.analytics_api, name="analytics_api"),
    path("ai-assistant/", views.ai_assistant, name="ai_assistant"),
    path("api/ai/conversations/", views.ai_conversations_api, name="ai_conversations_api"),
    path(
        "api/ai/conversations/<int:conversation_id>/messages/",
        views.ai_messages_api,
        name="ai_messages_api",
    ),
    path(
        "api/ai/conversations/<int:conversation_id>/",
        views.ai_conversation_delete_api,
        name="ai_conversation_delete_api",
    ),
    path("api/dashboard/", views.dashboard_api, name="dashboard_api"),
]
