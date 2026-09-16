from django.contrib import admin
from django.db import transaction

from .models import Course


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'order', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')

    @staticmethod
    def _detach_preserved_question_data(course_ids):
        """Detach reusable question data before obsolete courses are deleted."""
        from exam.models import Question, QuestionCategory

        Question.objects.filter(course_id__in=course_ids).update(course=None)
        QuestionCategory.objects.filter(course_id__in=course_ids).update(course=None)

    def get_deleted_objects(self, objs, request):
        deleted_objects, model_count, perms_needed, protected = (
            super().get_deleted_objects(objs, request)
        )
        if (
            request.user.is_active
            and request.user.is_staff
            and request.user.is_superuser
        ):
            # Course deletion intentionally cleans dependent exams and
            # subscription-course join rows. Their admins are otherwise
            # read-only, so their custom delete permissions must not block
            # this explicit superuser-only parent cleanup.
            perms_needed.clear()
        return deleted_objects, model_count, perms_needed, protected

    def delete_model(self, request, obj):
        with transaction.atomic():
            self._detach_preserved_question_data([obj.pk])
            super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        course_ids = list(queryset.values_list('pk', flat=True))
        with transaction.atomic():
            self._detach_preserved_question_data(course_ids)
            super().delete_queryset(request, queryset)
