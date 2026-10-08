from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def migrate_legacy_conversations(apps, schema_editor):
    AIConversation = apps.get_model("core", "AIConversation")
    AIMessage = apps.get_model("core", "AIMessage")
    database = schema_editor.connection.alias

    for conversation in AIConversation.objects.using(database).all().iterator():
        prompt = conversation.prompt.strip()
        response = conversation.response.strip()
        if prompt:
            AIMessage.objects.using(database).create(
                conversation_id=conversation.pk,
                role="user",
                content=prompt,
                mode="concept",
                created_at=conversation.created_at,
            )
        if response:
            AIMessage.objects.using(database).create(
                conversation_id=conversation.pk,
                role="assistant",
                content=response,
                mode="",
                created_at=conversation.created_at,
            )
        if prompt:
            conversation.title = prompt[:120]
        conversation.updated_at = conversation.created_at
        conversation.save(using=database, update_fields=["title", "updated_at"])


def restore_legacy_conversations(apps, schema_editor):
    AIConversation = apps.get_model("core", "AIConversation")
    AIMessage = apps.get_model("core", "AIMessage")
    database = schema_editor.connection.alias

    for conversation in AIConversation.objects.using(database).all().iterator():
        messages = AIMessage.objects.using(database).filter(
            conversation_id=conversation.pk,
        ).order_by("created_at", "pk")
        conversation.prompt = next(
            (message.content for message in messages if message.role == "user"),
            "",
        )
        conversation.response = next(
            (message.content for message in messages if message.role == "assistant"),
            "",
        )
        conversation.save(using=database, update_fields=["prompt", "response"])


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0010_testanswer_correct_option_testanswer_marks_possible"),
    ]

    operations = [
        migrations.AddField(
            model_name="aiconversation",
            name="title",
            field=models.CharField(default="New conversation", max_length=120),
        ),
        migrations.AddField(
            model_name="aiconversation",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name="AIMessage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[("user", "Student"), ("assistant", "AI tutor")],
                        max_length=12,
                    ),
                ),
                ("content", models.TextField()),
                (
                    "mode",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("concept", "Concept explanation"),
                            ("coding", "Coding explanation"),
                            ("aptitude", "Aptitude explanation"),
                            ("dbms", "DBMS explanation"),
                            ("sql", "SQL explanation"),
                            ("practice", "Practice questions"),
                            ("hint", "Hint"),
                            ("mistake", "Mistake explanation"),
                            ("recommendation", "Study recommendation"),
                        ],
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "conversation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="core.aiconversation",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at", "id"],
                "indexes": [
                    models.Index(
                        fields=["conversation", "created_at"],
                        name="core_aimess_convers_e34911_idx",
                    ),
                ],
            },
        ),
        migrations.RunPython(migrate_legacy_conversations, restore_legacy_conversations),
        migrations.RemoveField(model_name="aiconversation", name="prompt"),
        migrations.RemoveField(model_name="aiconversation", name="response"),
        migrations.AlterField(
            model_name="aiconversation",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterModelOptions(
            name="aiconversation",
            options={"ordering": ["-updated_at"]},
        ),
    ]
