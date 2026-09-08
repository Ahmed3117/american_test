import random
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from subscription.access import student_has_course_access

from .models import (
    DifficultyLevel,
    ExamConfig,
    ExamMode,
    Question,
    QuestionType,
    ResultTrial,
    StudentAccessType,
    StudentExamQuotaOverride,
    TempExam,
)


TRIAL_PERIODS = ('daily', 'weekly', 'monthly')


def student_access_type(student, course):
    """Resolve course-specific access; a missing course is unsubscribed."""
    if course and student_has_course_access(student, course):
        return StudentAccessType.SUBSCRIBED
    return StudentAccessType.UNSUBSCRIBED


def effective_exam_limits(student, exam_type, access_type):
    """Return global question cap plus effective personal calendar limits."""
    config = ExamConfig.load(access_type)
    override = StudentExamQuotaOverride.objects.filter(
        student=student,
        exam_type=exam_type,
        student_type=access_type,
    ).first()
    custom = {
        'daily': getattr(override, 'max_trials_per_day', None),
        'weekly': getattr(override, 'max_trials_per_week', None),
        'monthly': getattr(override, 'max_trials_per_month', None),
    }
    global_limits = {
        'daily': config.max_trials_per_day,
        'weekly': config.max_trials_per_week,
        'monthly': config.max_trials_per_month,
    }
    limits = {
        period: global_limits[period] if custom[period] is None else custom[period]
        for period in TRIAL_PERIODS
    }
    limits['max_questions_per_exam'] = config.max_questions_per_exam
    return {
        'limits': limits,
        'custom_limits': custom,
        'uses_custom_trial_limits': any(value is not None for value in custom.values()),
    }


def trial_quota_period_starts(at=None):
    """Return local calendar boundaries used by every exam quota."""
    at = timezone.localtime(at or timezone.now())
    day_start = at.replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        'daily': day_start,
        'weekly': day_start - timedelta(days=day_start.weekday()),
        'monthly': day_start.replace(day=1),
    }


def exam_quota_status(
    student,
    *,
    exam_type,
    access_type,
    number_of_questions=None,
    at=None,
):
    """Return quota status for one main/temp and access-type combination."""
    period_starts = trial_quota_period_starts(at)
    if exam_type == ExamMode.MAIN:
        usage_queryset = ResultTrial.objects.filter(
            result__student=student,
            result__exam__student=student,
            submitted_by_unsubscribed_user=(
                access_type == StudentAccessType.UNSUBSCRIBED
            ),
        )
        date_field = 'student_started_exam_at'
    elif exam_type == ExamMode.TEMP:
        usage_queryset = TempExam.objects.filter(
            student=student,
            student_type=access_type,
        )
        date_field = 'created'
    else:
        raise ValueError(f'Unsupported exam type: {exam_type}')

    usage = usage_queryset.aggregate(**{
        period: Count(
            'id',
            filter=Q(**{f'{date_field}__gte': period_starts[period]}),
        )
        for period in TRIAL_PERIODS
    })
    effective = effective_exam_limits(student, exam_type, access_type)
    limits = effective['limits']
    remaining = {
        period: max(limits[period] - usage[period], 0)
        for period in TRIAL_PERIODS
    }
    reached = [
        period for period in TRIAL_PERIODS if usage[period] >= limits[period]
    ]
    if (
        number_of_questions is not None
        and number_of_questions > limits['max_questions_per_exam']
    ):
        reached.append('max_questions_per_exam')
    return {
        'exam_type': exam_type,
        'access_type': access_type,
        'limits': limits,
        'usage': usage,
        'remaining': remaining,
        'reached_limits': reached,
        'can_start': not reached,
        'custom_limits': effective['custom_limits'],
        'uses_custom_trial_limits': effective['uses_custom_trial_limits'],
    }


def trial_quota_status(student, at=None):
    """Compatibility helper for subscribed main-exam quota status."""
    return exam_quota_status(
        student,
        exam_type=ExamMode.MAIN,
        access_type=StudentAccessType.SUBSCRIBED,
        at=at,
    )


def unsubscribed_trial_quota_status(student, at=None):
    """Compatibility helper for unsubscribed main-exam quota status."""
    return exam_quota_status(
        student,
        exam_type=ExamMode.MAIN,
        access_type=StudentAccessType.UNSUBSCRIBED,
        at=at,
    )


def temp_exam_quota_status(student, course=None, number_of_questions=None, at=None):
    access_type = student_access_type(student, course)
    return exam_quota_status(
        student,
        exam_type=ExamMode.TEMP,
        access_type=access_type,
        number_of_questions=number_of_questions,
        at=at,
    )


def main_exam_quota_status(student, course, number_of_questions=None, at=None):
    access_type = student_access_type(student, course)
    return exam_quota_status(
        student,
        exam_type=ExamMode.MAIN,
        access_type=access_type,
        number_of_questions=number_of_questions,
        at=at,
    )


def select_exam_question_ids(*, course, categories, years, difficulty_counts):
    """Select unique active MCQs matching the student's requested breakdown."""
    queryset = Question.objects.filter(
        course=course,
        is_active=True,
        question_type=QuestionType.MCQ,
        difficulty__in=[
            difficulty for difficulty, count in difficulty_counts.items() if count
        ],
    )
    if categories:
        queryset = queryset.filter(category__in=categories)
    if years:
        queryset = queryset.filter(years__in=years)

    available = {difficulty: [] for difficulty, count in difficulty_counts.items() if count}
    for question_id, difficulty in queryset.values_list('id', 'difficulty').distinct():
        if difficulty in available:
            available[difficulty].append(question_id)

    missing = {
        difficulty: {'requested': count, 'available': len(available.get(difficulty, []))}
        for difficulty, count in difficulty_counts.items()
        if len(available.get(difficulty, [])) < count
    }
    if missing:
        return [], missing

    selected = []
    for difficulty in (
        DifficultyLevel.EASY,
        DifficultyLevel.MEDIUM,
        DifficultyLevel.HARD,
    ):
        count = difficulty_counts.get(difficulty, 0)
        if count:
            selected.extend(random.sample(available[difficulty], count))
    random.shuffle(selected)
    return selected, {}
