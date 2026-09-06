from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend

from .models import StudentBank


class NumberInFilter(filters.BaseInFilter, filters.NumberFilter):
    pass


class StudentBankFilter(filters.FilterSet):
    """Student-facing aliases for filtering mistake-bank question metadata."""

    course = filters.NumberFilter(field_name='question__course_id')
    unit = filters.NumberFilter(field_name='question__unit_id')
    category = filters.NumberFilter(field_name='question__category_id')
    year = filters.NumberFilter(field_name='question__years__id')
    years = NumberInFilter(field_name='question__years__id', lookup_expr='in')
    question_type = filters.CharFilter(field_name='question__question_type')

    class Meta:
        model = StudentBank
        fields = [
            'add_reason',
            'is_solved_now',
            'course',
            'unit',
            'category',
            'year',
            'years',
            'question_type',
        ]

class RelatedCourseFilterBackend(DjangoFilterBackend):
    def filter_queryset(self, request, queryset, view):
        course_id = request.query_params.get('course')
        if course_id:
            queryset = queryset.filter(exam__course_id=course_id)
        return queryset
