import calendar
from datetime import date

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from course.models import Course
from student.models import Student


class Plan(models.Model):
    title = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    start_day = models.PositiveSmallIntegerField()
    start_month = models.PositiveSmallIntegerField()
    end_day = models.PositiveSmallIntegerField()
    end_month = models.PositiveSmallIntegerField()
    number_of_allowed_courses_to_subscribe = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_month", "start_day", "title"]

    def __str__(self):
        return self.title

    def clean(self):
        self._validate_month_day(self.start_month, self.start_day, "start_date")
        self._validate_month_day(self.end_month, self.end_day, "end_date")
        if self.number_of_allowed_courses_to_subscribe < 1:
            raise ValidationError("A plan must allow at least one course.")

    @staticmethod
    def _validate_month_day(month, day, label):
        if not 1 <= int(month) <= 12:
            raise ValidationError({label: "Month must be between 1 and 12."})
        max_day = calendar.monthrange(2024, int(month))[1]
        if not 1 <= int(day) <= max_day:
            raise ValidationError({label: f"Day must be between 1 and {max_day}."})

    @property
    def start_date(self):
        return f"{self.start_day:02d}/{self.start_month:02d}"

    @property
    def end_date(self):
        return f"{self.end_day:02d}/{self.end_month:02d}"

    def _date_for_year(self, year, month, day):
        return date(year, month, min(day, calendar.monthrange(year, month)[1]))

    def period_for(self, current_date=None):
        current_date = current_date or timezone.localdate()
        start_current = self._date_for_year(current_date.year, self.start_month, self.start_day)
        end_current = self._date_for_year(current_date.year, self.end_month, self.end_day)

        if (self.start_month, self.start_day) <= (self.end_month, self.end_day):
            return start_current, end_current

        if current_date >= start_current:
            return start_current, self._date_for_year(current_date.year + 1, self.end_month, self.end_day)
        return self._date_for_year(current_date.year - 1, self.start_month, self.start_day), end_current

    def has_started(self, current_date=None):
        current_date = current_date or timezone.localdate()
        start, _ = self.period_for(current_date)
        return current_date >= start

    def is_currently_available(self, current_date=None):
        current_date = current_date or timezone.localdate()
        start, end = self.period_for(current_date)
        return self.is_active and start <= current_date <= end


class PlanSubscription(models.Model):
    PAYMENT_PENDING = "pending"
    PAYMENT_PAID = "paid"
    PAYMENT_FAILED = "failed"
    PAYMENT_CANCELLED = "cancelled"
    PAYMENT_MANUAL = "manual"

    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_PENDING, "Pending"),
        (PAYMENT_PAID, "Paid"),
        (PAYMENT_FAILED, "Failed"),
        (PAYMENT_CANCELLED, "Cancelled"),
        (PAYMENT_MANUAL, "Manual"),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="plan_subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    courses = models.ManyToManyField(Course, through="PlanSubscriptionCourse", related_name="plan_subscriptions")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_PENDING)
    easypay_invoice_uid = models.CharField(max_length=120, blank=True, null=True)
    easypay_invoice_sequence = models.CharField(max_length=120, blank=True, null=True)
    easypay_payment_url = models.URLField(blank=True, null=True)
    easypay_payload = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student} - {self.plan}"

    @property
    def is_paid(self):
        return self.payment_status in {self.PAYMENT_PAID, self.PAYMENT_MANUAL}

    @property
    def has_access_now(self):
        return self.is_paid and self.plan.is_currently_available()

    def clean(self):
        if self.plan and self.pk:
            max_allowed = self.plan.number_of_allowed_courses_to_subscribe
            current_count = self.courses.count()
            if current_count > max_allowed:
                raise ValidationError(f"Selected courses ({current_count}) exceed the plan course limit ({max_allowed}).")

    def mark_paid(self, status=None):
        self.payment_status = status or self.PAYMENT_PAID
        self.paid_at = self.paid_at or timezone.now()
        self.save(update_fields=["payment_status", "paid_at", "updated_at"])
        self.sync_course_subscriptions()

    def sync_course_subscriptions(self):
        for course in self.courses.all():
            CourseSubscription.objects.update_or_create(
                student=self.student,
                course=course,
                plan_subscription=self,
                defaults={"active": self.has_access_now},
            )


class PlanSubscriptionCourse(models.Model):
    subscription = models.ForeignKey(PlanSubscription, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("subscription", "course")

    def __str__(self):
        return f"{self.subscription} -> {self.course}"


class CourseSubscriptionQuerySet(models.QuerySet):
    def currently_accessible(self):
        ids = [
            item.id
            for item in self.select_related("plan_subscription__plan")
            if item.has_access_now
        ]
        return self.filter(id__in=ids)


class CourseSubscription(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="course_subscriptions")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="course_subscriptions")
    plan_subscription = models.ForeignKey(
        PlanSubscription,
        on_delete=models.CASCADE,
        related_name="course_subscriptions",
        null=True,
        blank=True,
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CourseSubscriptionQuerySet.as_manager()

    class Meta:
        unique_together = ("student", "course", "plan_subscription")
        ordering = ["-created_at"]

    @property
    def has_access_now(self):
        if not self.active or not self.plan_subscription:
            return False
        return self.plan_subscription.has_access_now

    def __str__(self):
        return f"{self.student} -> {self.course}"
