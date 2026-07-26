from rest_framework import serializers

from .models import Student, StudentFavorite


class StudentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    gender = serializers.CharField(source="user.gender", read_only=True)

    class Meta:
        model = Student
        fields = ["id", "user_id", "username", "gender", "name", "parent_phone", "code", "created_at"]


class StudentFavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentFavorite
        fields = ["id", "student", "content_type", "object_id", "created_at"]
