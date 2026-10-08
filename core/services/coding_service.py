from dataclasses import dataclass

from django.db import transaction

from core.models import (
    CodingAttempt,
    CodingProblem,
    CodingSubmission,
    StudentActivity,
)


@dataclass(frozen=True)
class SampleValidationResult:
    status: str
    message: str


class SampleTestValidator:
    """Non-executing placeholder for a future isolated code-runner integration."""

    def validate(self, problem: CodingProblem, source_code: str, language: str) -> SampleValidationResult:
        del problem, source_code, language
        return SampleValidationResult(
            status=CodingSubmission.ValidationStatus.NOT_RUN,
            message=(
                "Submission saved. Sample tests were not run because code execution "
                "is disabled in this version."
            ),
        )


@transaction.atomic
def record_submission(user, problem: CodingProblem, language: str, source_code: str):
    validation = SampleTestValidator().validate(problem, source_code, language)
    submission = CodingSubmission.objects.create(
        user=user,
        problem=problem,
        language=language,
        source_code=source_code,
        status=CodingSubmission.Status.RECEIVED,
        sample_validation_status=validation.status,
        validation_message=validation.message,
    )
    CodingAttempt.objects.create(
        user=user,
        problem=problem,
        passed=False,
        notes=f"Submission #{submission.pk} received; sample validation not run.",
    )
    StudentActivity.objects.create(
        user=user,
        title="Coding solution submitted",
        detail=f"{problem.title} ({problem.difficulty}) - sample tests not run.",
    )
    return submission
