from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

class Student(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student",
    )
    name = models.CharField(max_length=100)
    parent_phone = models.CharField(max_length=20, null=True, blank=True)
    code = models.CharField(max_length=30, blank=True, null=True, unique=True)
    unsubscribed_exam_max_trials = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Optional lifetime trial limit override for main exams taken without "
            "a course subscription. Leave empty to use the global configuration."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name or self.user.username


class StudentFavorite(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="favorites")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "content_type", "object_id")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student} favorite {self.content_type}:{self.object_id}"
