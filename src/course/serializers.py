from rest_framework import serializers

from .models import Course, Unit


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = [
            "id",
            "course",
            "name",
            "description",
            "order",
            "is_active",
        ]
        extra_kwargs = {"course": {"required": False}}


class CourseSerializer(serializers.ModelSerializer):
    units = UnitSerializer(many=True, read_only=True)

    class Meta:
        model = Course
        fields = [
            "id",
            "name",
            "description",
            "image",
            "order",
            "is_active",
            "units",
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
