from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from course.models import Course
from subscription.access import user_has_course_access
from subscription.models import Plan, PlanSubscription


class PlanAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="01012345678",
            password="password123",
            name="Student",
            user_type="student",
        )
        self.course = Course.objects.create(name="Math")

    def test_paid_plan_grants_access_inside_plan_window(self):
        today = timezone.localdate()
        plan = Plan.objects.create(
            title="Current Plan",
            start_day=today.day,
            start_month=today.month,
            end_day=today.day,
            end_month=today.month,
            number_of_allowed_courses_to_subscribe=1,
            is_active=True,
        )
        subscription = PlanSubscription.objects.create(student=self.user.student, plan=plan)
        subscription.courses.add(self.course)
        subscription.mark_paid()

        self.assertTrue(user_has_course_access(self.user, self.course))

    def test_paid_plan_does_not_grant_access_before_start_date(self):
        today = timezone.localdate()
        future_day = today.day + 1
        future_month = today.month
        if future_day > 28:
            future_day = 1
            future_month = 1 if today.month == 12 else today.month + 1

        plan = Plan.objects.create(
            title="Future Plan",
            start_day=future_day,
            start_month=future_month,
            end_day=future_day,
            end_month=future_month,
            number_of_allowed_courses_to_subscribe=1,
            is_active=True,
        )
        subscription = PlanSubscription.objects.create(student=self.user.student, plan=plan)
        subscription.courses.add(self.course)
        subscription.mark_paid()

        self.assertFalse(user_has_course_access(self.user, self.course))
