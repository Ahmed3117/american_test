from rest_framework import serializers

from .models import Course


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = [
            "id",
            "name",
            "description",
            "image",
            "order",
            "is_active",
        ]


class StudentCourseSerializer(CourseSerializer):
    has_active_subscription = serializers.SerializerMethodField()

    class Meta(CourseSerializer.Meta):
        fields = CourseSerializer.Meta.fields + ["has_active_subscription"]

    def get_has_active_subscription(self, obj):
        accessible_course_ids = self.context.get("accessible_course_ids")
        if accessible_course_ids is None:
            request = self.context.get("request")
            accessible_course_ids = getattr(request, "accessible_course_ids", set()) if request else set()
        return obj.id in accessible_course_ids
