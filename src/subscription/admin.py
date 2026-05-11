from django.contrib import admin

from .models import CourseSubscription, Plan, PlanSubscription, PlanSubscriptionCourse


admin.site.register(Plan)
admin.site.register(PlanSubscription)
admin.site.register(PlanSubscriptionCourse)
admin.site.register(CourseSubscription)
