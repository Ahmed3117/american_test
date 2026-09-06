import calendar
import secrets
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.utils import timezone

from course.models import Course
from student.models import Student


def generate_discount_coupon_code():
    """Return a ten-digit coupon code without zeroes."""
    return "".join(secrets.choice("123456789") for _ in range(10))


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


class DiscountCoupon(models.Model):
    plan = models.ForeignKey(
        Plan,
        on_delete=models.CASCADE,
        related_name="discount_coupons",
        null=True,
        blank=True,
    )
    coupon = models.CharField(
        max_length=10,
        unique=True,
        default=generate_discount_coupon_code,
        editable=False,
    )
    discount_percentage = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    max_using_number = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.coupon} - {self.plan or 'All plans'}"

    def clean(self):
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValidationError({"valid_to": "valid_to must be later than valid_from."})

    def is_valid_at(self, current_time=None):
        current_time = current_time or timezone.now()
        return self.is_active and self.valid_from <= current_time <= self.valid_to


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
    discount_coupon = models.ForeignKey(
        DiscountCoupon,
        on_delete=models.SET_NULL,
        related_name="subscriptions",
        null=True,
        blank=True,
    )
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payable_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    coupon_applied_at = models.DateTimeField(null=True, blank=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_PENDING)
    easypay_invoice_uid = models.CharField(max_length=120, blank=True, null=True)
    easypay_invoice_sequence = models.CharField(max_length=120, blank=True, null=True)
    easypay_payment_url = models.URLField(blank=True, null=True)
    easypay_payload = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    access_starts_on = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Concrete start date captured for this subscription's plan cycle.",
    )
    access_ends_on = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Concrete end date captured for this subscription's plan cycle.",
    )
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
        today = timezone.localdate()
        start, end = self.access_period
        return self.is_paid and self.plan.is_active and start <= today <= end

    @property
    def access_period(self):
        """Return this purchase's fixed plan occurrence, never a future cycle."""
        if self.access_starts_on and self.access_ends_on:
            return self.access_starts_on, self.access_ends_on

        reference_date = timezone.localdate()
        if self.created_at:
            created_at = self.created_at
            if timezone.is_aware(created_at):
                created_at = timezone.localtime(created_at)
            reference_date = created_at.date()
        return self.plan.period_for(reference_date)

    @property
    def invoice_amount(self):
        return self.payable_amount if self.payable_amount is not None else self.plan.price

    def apply_discount_coupon(self, coupon):
        original_price = self.plan.price
        discount_amount = (
            original_price * Decimal(coupon.discount_percentage) / Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.discount_coupon = coupon
        self.original_price = original_price
        self.discount_amount = discount_amount
        self.payable_amount = max(original_price - discount_amount, Decimal("0.00"))
        self.coupon_applied_at = timezone.now()
        self.save(
            update_fields=[
                "discount_coupon",
                "original_price",
                "discount_amount",
                "payable_amount",
                "coupon_applied_at",
                "updated_at",
            ]
        )

    def clean(self):
        if self.access_starts_on and self.access_ends_on:
            if self.access_ends_on < self.access_starts_on:
                raise ValidationError(
                    {"access_ends_on": "Access end date cannot be before its start date."}
                )
        if self.plan and self.pk:
            max_allowed = self.plan.number_of_allowed_courses_to_subscribe
            current_count = self.courses.count()
            if current_count > max_allowed:
                raise ValidationError(f"Selected courses ({current_count}) exceed the plan course limit ({max_allowed}).")

    def mark_paid(self, status=None):
        self.payment_status = status or self.PAYMENT_PAID
        self.paid_at = self.paid_at or timezone.now()
        update_fields = ["payment_status", "paid_at", "updated_at"]
        if not self.access_starts_on or not self.access_ends_on:
            self.access_starts_on, self.access_ends_on = self.access_period
            update_fields.extend(["access_starts_on", "access_ends_on"])
        self.save(update_fields=update_fields)


class PlanSubscriptionCourse(models.Model):
    subscription = models.ForeignKey(PlanSubscription, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("subscription", "course")

    def __str__(self):
        return f"{self.subscription} -> {self.course}"

    def clean(self):
        super().clean()
        if not self.subscription_id:
            return

        subscription = self.subscription
        if not subscription.is_paid:
            return

        original = None
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
        if original and (
            original.subscription_id == self.subscription_id
            and original.course_id == self.course_id
        ):
            return
        raise ValidationError(
            "Courses cannot be added to or changed on a paid subscription."
        )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.subscription.is_paid:
            raise ValidationError(
                "Courses cannot be removed from a paid subscription."
            )
        return super().delete(*args, **kwargs)


@receiver(m2m_changed, sender=PlanSubscription.courses.through)
def prevent_paid_subscription_course_changes(
    sender, instance, action, reverse, pk_set, **kwargs
):
    """Keep a paid purchase's selected-course snapshot immutable."""
    if action not in {"pre_add", "pre_remove", "pre_clear"}:
        return

    if not reverse:
        has_paid_target = instance.is_paid
    elif action == "pre_clear":
        has_paid_target = instance.plan_subscriptions.filter(
            payment_status__in=[
                PlanSubscription.PAYMENT_PAID,
                PlanSubscription.PAYMENT_MANUAL,
            ]
        ).exists()
    else:
        has_paid_target = PlanSubscription.objects.filter(
            pk__in=pk_set or [],
            payment_status__in=[
                PlanSubscription.PAYMENT_PAID,
                PlanSubscription.PAYMENT_MANUAL,
            ],
        ).exists()

    if has_paid_target:
        raise ValidationError(
            "Courses cannot be changed on a paid subscription."
        )
