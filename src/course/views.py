from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from exam.models import Exam
from exam.serializers import ExamSerializer
from subscription.access import user_has_course_access

from .models import Course
from .serializers import CourseSerializer


class CourseListView(generics.ListAPIView):
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Course.objects.filter(is_active=True).prefetch_related("units")


class CourseDetailView(generics.RetrieveAPIView):
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Course.objects.filter(is_active=True).prefetch_related("units")


class CourseExamListView(generics.ListAPIView):
    serializer_class = ExamSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        course = get_object_or_404(Course, pk=self.kwargs["course_id"], is_active=True)
        if not user_has_course_access(self.request.user, course):
            return Exam.objects.none()
        return Exam.objects.filter(course=course, is_active=True).order_by("order", "created")
