from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from exam.models import Exam
from exam.serializers import ExamSerializer
from subscription.access import get_accessible_course_ids_for_student, user_has_course_access

from .models import Course
from .serializers import StudentCourseSerializer


class CourseListView(generics.ListAPIView):
    serializer_class = StudentCourseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Course.objects.filter(is_active=True).prefetch_related("units")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["accessible_course_ids"] = get_accessible_course_ids_for_student(getattr(self.request.user, "student", None))
        return context


class CourseDetailView(generics.RetrieveAPIView):
    serializer_class = StudentCourseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Course.objects.filter(is_active=True).prefetch_related("units")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["accessible_course_ids"] = get_accessible_course_ids_for_student(getattr(self.request.user, "student", None))
        return context


class MyAccessibleCoursesView(CourseListView):
    def get_queryset(self):
        course_ids = get_accessible_course_ids_for_student(getattr(self.request.user, "student", None))
        return Course.objects.filter(id__in=course_ids, is_active=True).prefetch_related("units")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["accessible_course_ids"] = set(self.get_queryset().values_list("id", flat=True))
        return context


class CourseExamListView(generics.ListAPIView):
    serializer_class = ExamSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        course = get_object_or_404(Course, pk=self.kwargs["course_id"], is_active=True)
        if not user_has_course_access(self.request.user, course):
            return Exam.objects.none()
        return Exam.objects.filter(course=course, is_active=True).order_by("order", "created")

    def list(self, request, *args, **kwargs):
        course = get_object_or_404(Course, pk=self.kwargs["course_id"], is_active=True)
        if not user_has_course_access(request.user, course):
            return Response(
                {
                    "error": "ليس لديك صلاحية الوصول إلى هذه المادة. اشترك في باقة تتضمن هذه المادة أولاً.",
                    "course_id": course.id,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)
