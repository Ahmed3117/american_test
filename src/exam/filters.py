from django_filters.rest_framework import DjangoFilterBackend

class RelatedCourseFilterBackend(DjangoFilterBackend):
    def filter_queryset(self, request, queryset, view):
        course_id = request.query_params.get('course')
        if course_id:
            queryset = queryset.filter(exam__course_id=course_id)
        return queryset
