"""Quiz schema — ``docs/domain-model.md`` §2.10.

Phase 1 creates these tables only: no endpoint reads or writes them, and the API inventory has
no quiz route. They exist now so Phase 2 adds behaviour without a destructive migration.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models

from academy.models.base import TenantManager, TenantModel
from academy.models.catalog import CourseVersion, Lesson
from academy.models.progress import Enrollment

TEXT_NOT_BLANK = r"\S"


class Quiz(TenantModel):
    """A quiz attached to a version, optionally to one lesson."""

    version = models.ForeignKey(CourseVersion, on_delete=models.RESTRICT, related_name="quizzes")
    lesson = models.ForeignKey(
        Lesson, on_delete=models.RESTRICT, related_name="quizzes", null=True, blank=True
    )
    title = models.CharField(max_length=200)
    pass_percent = models.PositiveSmallIntegerField(default=70)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    objects: TenantManager[Quiz] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(pass_percent__gte=0) & models.Q(pass_percent__lte=100),
                name="quiz_pass_percent_range",
            ),
            models.CheckConstraint(
                condition=models.Q(max_attempts__gte=1), name="quiz_max_attempts_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(title__regex=TEXT_NOT_BLANK), name="quiz_title_not_blank"
            ),
        ]

    def __str__(self) -> str:
        return self.title


class QuizQuestion(TenantModel):
    """One ordered question inside a quiz."""

    class Kind(models.TextChoices):
        SINGLE = "single", "Single choice"
        MULTIPLE = "multiple", "Multiple choice"

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    position = models.PositiveIntegerField()
    prompt = models.TextField()
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.SINGLE)
    objects: TenantManager[QuizQuestion] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["quiz", "position"], name="question_position_per_quiz"),
            models.CheckConstraint(
                condition=models.Q(position__gte=1), name="question_position_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=["single", "multiple"]), name="question_kind_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(prompt__regex=TEXT_NOT_BLANK),
                name="question_prompt_not_blank",
            ),
        ]

    def __str__(self) -> str:
        return self.prompt


class QuizChoice(TenantModel):
    """One ordered answer option of a question."""

    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name="choices")
    position = models.PositiveIntegerField()
    label = models.CharField(max_length=300)
    is_correct = models.BooleanField(default=False)
    objects: TenantManager[QuizChoice] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["question", "position"], name="choice_position_per_question"
            ),
            models.CheckConstraint(
                condition=models.Q(position__gte=1), name="choice_position_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(label__regex=TEXT_NOT_BLANK), name="choice_label_not_blank"
            ),
        ]

    def __str__(self) -> str:
        return self.label


class QuizAttempt(TenantModel):
    """One learner's attempt at one quiz, numbered per enrollment."""

    quiz = models.ForeignKey(Quiz, on_delete=models.RESTRICT, related_name="attempts")
    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.CASCADE, related_name="quiz_attempts"
    )
    attempt_number = models.PositiveIntegerField()
    started_at = models.DateTimeField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    score_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    passed = models.BooleanField(null=True, blank=True)
    objects: TenantManager[QuizAttempt] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["quiz", "enrollment", "attempt_number"],
                name="attempt_number_per_quiz_enrollment",
            ),
            models.CheckConstraint(
                condition=models.Q(attempt_number__gte=1), name="attempt_number_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(score_percent__isnull=True)
                | (
                    models.Q(score_percent__gte=Decimal("0"))
                    & models.Q(score_percent__lte=Decimal("100"))
                ),
                name="attempt_score_range",
            ),
        ]
        indexes = [
            models.Index(fields=["organization_id", "enrollment"], name="attempt_org_enrollment"),
        ]

    def __str__(self) -> str:
        return f"{self.quiz} · attempt {self.attempt_number}"


class QuizAttemptAnswer(TenantModel):
    """The choices a learner submitted for one question of one attempt."""

    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(QuizQuestion, on_delete=models.RESTRICT, related_name="answers")
    choice_ids = models.JSONField(default=list)
    correct = models.BooleanField(default=False)
    objects: TenantManager[QuizAttemptAnswer] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "question"], name="answer_per_attempt_question"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.attempt} · {self.question}"
