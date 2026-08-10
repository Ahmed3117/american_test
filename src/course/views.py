from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

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
        queryset = Exam.objects.filter(course=course, is_active=True)
        if not user_has_course_access(self.request.user, course):
            queryset = queryset.filter(allow_unsubscribed_access=True)
        return queryset.order_by("order", "created")
