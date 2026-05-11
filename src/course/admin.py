from django.contrib import admin

from .models import Course, File, Unit


admin.site.register(Course)
admin.site.register(Unit)
admin.site.register(File)
