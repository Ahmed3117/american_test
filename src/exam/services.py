import random
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from subscription.access import student_has_course_access

from .models import (
    DifficultyLevel,
    ExamConfig,
    Question,
    QuestionType,
    ResultTrial,
    TempExam,
    UnsubscribedExamConfig,
)


def trial_quota_status(student, at=None):
    """Return calendar-period usage for all main-exam trial starts."""
    at = timezone.localtime(at or timezone.now())
    day_start = at.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = day_start - timedelta(days=day_start.weekday())
    month_start = day_start.replace(day=1)

    usage = ResultTrial.objects.filter(
        result__student=student,
        result__exam__student=student,
        submitted_by_unsubscribed_user=False,
    ).aggregate(
        daily=Count('id', filter=Q(student_started_exam_at__gte=day_start)),
        weekly=Count('id', filter=Q(student_started_exam_at__gte=week_start)),
        monthly=Count('id', filter=Q(student_started_exam_at__gte=month_start)),
    )
    config = ExamConfig.load()
    limits = {
        'daily': config.max_trials_per_day,
        'weekly': config.max_trials_per_week,
        'monthly': config.max_trials_per_month,
    }
    remaining = {
        period: max(limits[period] - usage[period], 0)
        for period in limits
    }
    reached = [period for period in limits if usage[period] >= limits[period]]
    return {
        'limits': limits,
        'usage': usage,
        'remaining': remaining,
        'reached_limits': reached,
        'can_start': not reached,
    }


def temp_exam_quota_status(student, at=None):
    """Use ExamConfig's calendar limits for temp-exam creations."""
    at = timezone.localtime(at or timezone.now())
    day_start = at.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = day_start - timedelta(days=day_start.weekday())
    month_start = day_start.replace(day=1)

    usage = TempExam.objects.filter(student=student).aggregate(
        daily=Count('id', filter=Q(created__gte=day_start)),
        weekly=Count('id', filter=Q(created__gte=week_start)),
        monthly=Count('id', filter=Q(created__gte=month_start)),
    )
    config = ExamConfig.load()
    limits = {
        'daily': config.max_trials_per_day,
        'weekly': config.max_trials_per_week,
        'monthly': config.max_trials_per_month,
    }
    remaining = {
        period: max(limits[period] - usage[period], 0)
        for period in limits
    }
    reached = [period for period in limits if usage[period] >= limits[period]]
    return {
        'limits': limits,
        'usage': usage,
        'remaining': remaining,
        'reached_limits': reached,
        'can_start': not reached,
    }


def unsubscribed_trial_quota_status(student):
    """Return lifetime main-exam usage for trials started unsubscribed."""
    config = UnsubscribedExamConfig.load()
    custom_limit = student.unsubscribed_exam_max_trials
    limit = config.max_trials if custom_limit is None else custom_limit
    usage = ResultTrial.objects.filter(
        result__student=student,
        result__exam__student=student,
        submitted_by_unsubscribed_user=True,
    ).count()
    remaining = max(limit - usage, 0)
    return {
        'limits': {
            'total': limit,
            'max_questions_per_exam': config.max_questions_per_exam,
        },
        'usage': {'total': usage},
        'remaining': {'total': remaining},
        'reached_limits': ['total'] if usage >= limit else [],
        'can_start': usage < limit,
        'uses_custom_trial_limit': custom_limit is not None,
    }


def main_exam_quota_status(student, course, number_of_questions=None, at=None):
    """Choose subscribed calendar quotas or unsubscribed lifetime quotas."""
    if student_has_course_access(student, course):
        quota = trial_quota_status(student, at=at)
        quota['access_type'] = 'subscribed'
        return quota

    quota = unsubscribed_trial_quota_status(student)
    quota['access_type'] = 'unsubscribed'
    if (
        number_of_questions is not None
        and number_of_questions > quota['limits']['max_questions_per_exam']
    ):
        quota['can_start'] = False
        quota['reached_limits'] = [
            *quota['reached_limits'],
            'max_questions_per_exam',
        ]
    return quota


def select_exam_question_ids(*, course, unit, category, years, difficulty_counts):
    """Select unique active MCQs matching the student's requested breakdown."""
    queryset = Question.objects.filter(
        course=course,
        is_active=True,
        question_type=QuestionType.MCQ,
        difficulty__in=[
            difficulty for difficulty, count in difficulty_counts.items() if count
        ],
    )
    if unit:
        queryset = queryset.filter(unit=unit)
    if category:
        queryset = queryset.filter(category=category)
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
