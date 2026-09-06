from django.contrib import admin

from .models import DiscountCoupon, Plan, PlanSubscription, PlanSubscriptionCourse


admin.site.register(Plan)
admin.site.register(DiscountCoupon)


@admin.register(PlanSubscription)
class PlanSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "student",
        "plan",
        "payment_status",
        "access_starts_on",
        "access_ends_on",
        "created_at",
    )
    list_filter = ("payment_status", "plan", "access_starts_on", "access_ends_on")
    search_fields = ("student__name", "student__user__username", "plan__title")

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_paid:
            return tuple(field.name for field in obj._meta.fields)
        return ("created_at", "updated_at", "paid_at")


@admin.register(PlanSubscriptionCourse)
class PlanSubscriptionCourseAdmin(admin.ModelAdmin):
    list_display = ("id", "subscription", "course", "created_at")
    raw_id_fields = ("subscription", "course")
    readonly_fields = ("created_at",)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.subscription.is_paid:
            return ("subscription", "course", "created_at")
        return super().get_readonly_fields(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.subscription.is_paid:
            return False
        return super().has_delete_permission(request, obj)
