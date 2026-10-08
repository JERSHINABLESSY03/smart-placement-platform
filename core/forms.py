from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password

from .models import AIMessage, AptitudeQuestionOption, CodingSubmission, StudentProfile
from .validators import (
    validate_pdf_signature,
    validate_profile_picture_extension,
    validate_profile_picture_size,
    validate_resume_extension,
    validate_resume_size,
)

User = get_user_model()


class StudentRegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control"}))
    college = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"class": "form-control"}))
    degree = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"class": "form-control"}))
    department = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"class": "form-control"}))
    graduation_year = forms.IntegerField(min_value=2000, max_value=2100, widget=forms.NumberInput(attrs={"class": "form-control"}))
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        help_text="Use at least 8 characters with letters and numbers.",
    )
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput(attrs={"class": "form-control"}))

    def clean_email(self):
        email = (self.cleaned_data["email"] or "").strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_password1(self):
        password = self.cleaned_data.get("password1")
        validate_password(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "you@example.com"}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Enter your password"}),
    )

    def clean(self):
        username = (self.cleaned_data.get("username") or "").strip().lower()
        password = self.cleaned_data.get("password")
        if username and password:
            self.user_cache = authenticate(username=username, password=password)
            if self.user_cache is None:
                raise forms.ValidationError("Invalid email or password. Please try again.")
            elif not self.user_cache.is_active:
                raise forms.ValidationError("This account is inactive.")
        return self.cleaned_data


class ProfileForm(forms.ModelForm):
    profile_picture = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={"class": "form-control"}),
        validators=[
            validate_profile_picture_extension,
            validate_profile_picture_size,
        ],
        help_text="JPG, PNG, or WebP; maximum size 2 MB.",
    )
    resume = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={"class": "form-control"}),
        validators=[
            validate_resume_extension,
            validate_resume_size,
            validate_pdf_signature,
        ],
        help_text="PDF only; maximum size 5 MB.",
    )

    class Meta:
        model = StudentProfile
        fields = [
            "full_name",
            "college",
            "degree",
            "department",
            "graduation_year",
            "programming_languages",
            "technical_skills",
            "preferred_job_role",
            "preferred_domain",
            "current_preparation_level",
            "github_url",
            "linkedin_url",
            "profile_picture",
            "resume",
            "bio",
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
            "current_preparation_level": forms.Select(
                attrs={"class": "form-select"},
                choices=[
                    ("Beginner", "Beginner"),
                    ("Intermediate", "Intermediate"),
                    ("Advanced", "Advanced"),
                ],
            ),
            "github_url": forms.URLInput(attrs={"class": "form-control"}),
            "linkedin_url": forms.URLInput(attrs={"class": "form-control"}),
            "profile_picture": forms.FileInput(attrs={"class": "form-control"}),
            "resume": forms.FileInput(attrs={"class": "form-control"}),
            "bio": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

class AIChatForm(forms.Form):
    mode = forms.ChoiceField(choices=AIMessage.Mode.choices)
    prompt = forms.CharField(
        label="Your question",
        min_length=2,
        max_length=6000,
        strip=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mode"].widget.attrs.update({"class": "form-select"})
        self.fields["prompt"].widget.attrs.update(
            {
                "class": "form-control",
                "rows": 3,
                "placeholder": "Ask about a concept, question, code snippet, or study goal...",
                "maxlength": 6000,
            }
        )


class QuestionAnswerForm(forms.Form):
    selected_option = forms.ChoiceField(label="Your answer", choices=[("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")], widget=forms.RadioSelect)


class AptitudeAnswerForm(forms.Form):
    selected_option = forms.ChoiceField(
        label="Choose your answer",
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, question, **kwargs):
        super().__init__(*args, **kwargs)
        self.question = question
        self.fields["selected_option"].choices = [
            (str(option.pk), f"{option.label}. {option.text}")
            for option in question.options.all()
        ]

    def clean_selected_option(self):
        option_id = self.cleaned_data["selected_option"]
        try:
            return AptitudeQuestionOption.objects.get(pk=option_id, question=self.question)
        except (AptitudeQuestionOption.DoesNotExist, ValueError):
            raise forms.ValidationError("Select one of the options for this question.")


class CodingSubmissionForm(forms.ModelForm):
    language = forms.ChoiceField(
        choices=CodingSubmission.Language.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = CodingSubmission
        fields = ["language", "source_code"]
        widgets = {
            "source_code": forms.Textarea(
                attrs={
                    "class": "form-control code-editor",
                    "rows": 18,
                    "spellcheck": "false",
                    "autocapitalize": "off",
                    "autocomplete": "off",
                    "maxlength": "20000",
                    "aria-label": "Code editor",
                }
            ),
        }

    def clean_source_code(self):
        source_code = self.cleaned_data["source_code"]
        if not source_code.strip():
            raise forms.ValidationError("Enter your solution before submitting.")
        if len(source_code) > 20_000:
            raise forms.ValidationError("Code must be 20,000 characters or fewer.")
        return source_code
