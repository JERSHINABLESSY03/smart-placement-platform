from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

MAX_RESUME_SIZE = 5 * 1024 * 1024
MAX_PROFILE_PICTURE_SIZE = 2 * 1024 * 1024


def validate_file_size(upload, *, max_size, label):
    if upload.size == 0:
        raise ValidationError(f"The {label} file cannot be empty.")
    if upload.size > max_size:
        max_size_mb = max_size // (1024 * 1024)
        raise ValidationError(f"The {label} file must be no larger than {max_size_mb} MB.")


def validate_resume_size(upload):
    validate_file_size(upload, max_size=MAX_RESUME_SIZE, label="resume")


def validate_profile_picture_size(upload):
    validate_file_size(
        upload,
        max_size=MAX_PROFILE_PICTURE_SIZE,
        label="profile picture",
    )


def validate_pdf_signature(upload):
    position = upload.tell()
    try:
        header = upload.read(1024)
    finally:
        upload.seek(position)
    if not header.startswith(b"%PDF-"):
        raise ValidationError("Upload a valid PDF resume.")


validate_resume_extension = FileExtensionValidator(
    allowed_extensions=["pdf"],
    message="Resume must be a PDF file.",
)
validate_profile_picture_extension = FileExtensionValidator(
    allowed_extensions=["jpg", "jpeg", "png", "webp"],
    message="Profile picture must be a JPG, PNG, or WebP image.",
)
