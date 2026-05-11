from django.db import models


class Course(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="courses/", null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Unit(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="units")
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.course.name} - {self.name}"


class File(models.Model):
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="files")
    title = models.CharField(max_length=150)
    file = models.FileField(upload_to="unit_files/")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
