from django.core.management.base import BaseCommand
from django.utils.text import slugify

from core.models import CodingProblem, CodingTopic, Question


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
            arrays, _ = CodingTopic.objects.get_or_create(
                slug="arrays",
                defaults={"name": "Arrays"},
            )
            strings, _ = CodingTopic.objects.get_or_create(
                slug="strings",
                defaults={"name": "Strings"},
            )
            CodingProblem.objects.create(
                title="Two Sum",
                slug=slugify("Two Sum"),
                topic=arrays,
                category="Arrays",
                difficulty="Easy",
                problem_statement="Given an array of integers and a target, return indices of the two numbers that add up to the target.",
                description="Given an array of integers and a target, return indices of the two numbers that add up to the target.",
                starter_code="def two_sum(nums, target):\n    pass\n",
                sample_input="nums = [2, 7, 11, 15], target = 9",
                sample_output="[0, 1]",
                constraints="Each input has exactly one solution.",
                input_format="An integer array and an integer target.",
                output_format="The indices of the two values that sum to the target.",
                explanation="Use a hash map to store previously seen values and their indices.",
                tags=["array", "hashing"],
            )
            CodingProblem.objects.create(
                title="Reverse a String",
                slug=slugify("Reverse a String"),
                topic=strings,
                category="Strings",
                difficulty="Easy",
                problem_statement="Write a function to reverse a given string.",
                description="Write a function to reverse a given string.",
                starter_code="def reverse_string(s):\n    pass\n",
                sample_input="s = 'hello'",
                sample_output="'olleh'",
                constraints="Use in-place or built-in logic as needed.",
                input_format="A string.",
                output_format="The input string in reverse order.",
                explanation="Return the characters in the opposite order.",
                tags=["string"],
            )
        self.stdout.write(self.style.SUCCESS("Seed data loaded successfully."))
