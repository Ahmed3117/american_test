from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Student


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def sync_student_profile(sender, instance, **kwargs):
    if getattr(instance, "user_type", None) != "student":
        return

    Student.objects.update_or_create(
        user=instance,
        defaults={
            "name": instance.name or instance.username,
            "parent_phone": instance.parent_phone,
        },
    )
