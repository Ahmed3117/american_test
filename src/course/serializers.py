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
