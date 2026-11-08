from rest_framework import serializers

from accounts.models import User
from course.models import Course
from course.serializers import CourseSerializer

from .models import DiscountCoupon, Plan, PlanSubscription


class PlanSerializer(serializers.ModelSerializer):
    start_date = serializers.CharField(required=False)
    end_date = serializers.CharField(required=False)
    has_started = serializers.SerializerMethodField()
    is_available_now = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = [
            "id",
            "title",
            "price",
            "start_day",
            "start_month",
            "start_date",
            "end_day",
            "end_month",
            "end_date",
            "number_of_allowed_courses_to_subscribe",
            "is_active",
            "has_started",
            "is_available_now",
        ]
        extra_kwargs = {
            "start_day": {"required": False},
            "start_month": {"required": False},
            "end_day": {"required": False},
            "end_month": {"required": False},
        }

    def get_has_started(self, obj):
        return obj.has_started()

    def get_is_available_now(self, obj):
        return obj.is_currently_available()

    def validate(self, attrs):
        self._apply_date(attrs, "start_date", "start_day", "start_month")
        self._apply_date(attrs, "end_date", "end_day", "end_month")
        instance = getattr(self, "instance", None)
        required_fields = ["start_day", "start_month", "end_day", "end_month"]
        missing = [
            field
            for field in required_fields
            if attrs.get(field) is None and (instance is None or getattr(instance, field) is None)
        ]
        if missing:
            raise serializers.ValidationError({field: "هذا الحقل مطلوب" for field in missing})
        start_month = attrs.get("start_month") or getattr(instance, "start_month", None)
        start_day = attrs.get("start_day") or getattr(instance, "start_day", None)
        end_month = attrs.get("end_month") or getattr(instance, "end_month", None)
        end_day = attrs.get("end_day") or getattr(instance, "end_day", None)
        try:
            Plan._validate_month_day(start_month, start_day, "start_date")
            Plan._validate_month_day(end_month, end_day, "end_date")
        except Exception as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else str(exc)) from exc
        return attrs

    def create(self, validated_data):
        validated_data.pop("start_date", None)
        validated_data.pop("end_date", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("start_date", None)
        validated_data.pop("end_date", None)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["start_date"] = instance.start_date
        data["end_date"] = instance.end_date
        return data

    def _apply_date(self, attrs, source_field, day_field, month_field):
        raw_value = attrs.get(source_field)
        if not raw_value:
            return
        parts = str(raw_value).replace("-", "/").split("/")
        if len(parts) != 2:
            raise serializers.ValidationError({source_field: "استخدم صيغة DD/MM أو DD-MM"})
        try:
            day = int(parts[0])
            month = int(parts[1])
        except ValueError as exc:
            raise serializers.ValidationError({source_field: "استخدم أرقاماً لليوم والشهر"}) from exc
        attrs[day_field] = day
        attrs[month_field] = month


class StudentPlanSerializer(PlanSerializer):
    """Plan response enriched with state for the authenticated student."""

    is_ordered = serializers.SerializerMethodField()
    has_access_now = serializers.SerializerMethodField()

    class Meta(PlanSerializer.Meta):
        fields = PlanSerializer.Meta.fields + [
            "is_ordered",
            "has_access_now",
        ]

    def get_is_ordered(self, obj):
        return obj.id in self.context.get("pending_plan_ids", set())

    def get_has_access_now(self, obj):
        return obj.id in self.context.get("accessible_plan_ids", set())


class DiscountCouponSerializer(serializers.ModelSerializer):
    usage_count = serializers.SerializerMethodField()
    remaining_uses = serializers.SerializerMethodField()

    class Meta:
        model = DiscountCoupon
        fields = [
            "id",
            "plan",
            "coupon",
            "discount_percentage",
            "valid_from",
            "valid_to",
            "is_active",
            "max_using_number",
            "usage_count",
            "remaining_uses",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["coupon", "created_at", "updated_at"]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        valid_from = attrs.get("valid_from", getattr(instance, "valid_from", None))
        valid_to = attrs.get("valid_to", getattr(instance, "valid_to", None))
        if valid_from and valid_to and valid_to <= valid_from:
            raise serializers.ValidationError({"valid_to": "valid_to must be later than valid_from."})

        max_using_number = attrs.get(
            "max_using_number", getattr(instance, "max_using_number", 1)
        )
        if instance and max_using_number < instance.subscriptions.count():
            raise serializers.ValidationError(
                {"max_using_number": "It cannot be less than the coupon's current usage count."}
            )
        return attrs

    def get_usage_count(self, obj):
        return obj.subscriptions.count()

    def get_remaining_uses(self, obj):
        return max(obj.max_using_number - obj.subscriptions.count(), 0)


class PlanSubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    courses = CourseSerializer(many=True, read_only=True)
    has_access_now = serializers.BooleanField(read_only=True)
    coupon = serializers.CharField(source="discount_coupon.coupon", read_only=True, allow_null=True)
    invoice_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = PlanSubscription
        fields = [
            "id",
            "plan",
            "courses",
            "payment_status",
            "has_access_now",
            "coupon",
            "original_price",
            "discount_amount",
            "payable_amount",
            "invoice_amount",
            "coupon_applied_at",
            "easypay_invoice_uid",
            "easypay_invoice_sequence",
            "easypay_payment_url",
            "paid_at",
            "access_starts_on",
            "access_ends_on",
            "created_at",
        ]


class DashboardPlanSubscriptionSerializer(PlanSubscriptionSerializer):
    """Add account identity to dashboard reads without changing student APIs."""

    student_user_id = serializers.IntegerField(source="student.user_id", read_only=True)
    student_username = serializers.CharField(source="student.user.username", read_only=True)
    student_name = serializers.CharField(source="student.user.name", read_only=True)

    class Meta(PlanSubscriptionSerializer.Meta):
        fields = PlanSubscriptionSerializer.Meta.fields + [
            "student_user_id", "student_username", "student_name",
        ]


class ApplyDiscountCouponSerializer(serializers.Serializer):
    coupon = serializers.RegexField(
        regex=r"^[1-9]{10}$",
        error_messages={"invalid": "Coupon must contain exactly 10 digits from 1 to 9."},
    )


class SubscribePlanSerializer(serializers.Serializer):
    course_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )

    def validate_course_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("لا يمكن اختيار نفس المادة أكثر من مرة")

        unique_ids = list(dict.fromkeys(value))
        plan = self.context["plan"]
        allowed_courses = plan.number_of_allowed_courses_to_subscribe
        if len(unique_ids) != allowed_courses:
            raise serializers.ValidationError(
                f"يجب اختيار {allowed_courses} مادة/مواد بالضبط لهذه الباقة"
            )
        courses_count = Course.objects.filter(id__in=unique_ids, is_active=True).count()
        if courses_count != len(unique_ids):
            raise serializers.ValidationError("مادة أو أكثر من المواد المحددة غير موجودة أو غير نشطة")
        return unique_ids


class DashboardSubscriptionCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)
    plan_id = serializers.IntegerField(min_value=1)
    course_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
    mark_paid = serializers.BooleanField(required=False, default=False)

    def validate_course_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("لا يمكن اختيار نفس المادة أكثر من مرة")

        return list(dict.fromkeys(value))

    def validate(self, attrs):
        plan = Plan.objects.filter(pk=attrs["plan_id"]).first()
        if plan is None:
            raise serializers.ValidationError({"plan_id": "الخطة غير موجودة"})
        if not plan.is_active:
            raise serializers.ValidationError({"plan_id": "هذه الخطة غير نشطة"})
        if not plan.is_currently_available():
            raise serializers.ValidationError({"plan_id": "هذه الخطة خارج فترة الاشتراك الحالية"})

        user = User.objects.filter(pk=attrs["user_id"], user_type="student").first()
        if user is None:
            raise serializers.ValidationError({"user_id": "الطالب غير موجود"})

        allowed_courses = plan.number_of_allowed_courses_to_subscribe
        if len(attrs["course_ids"]) != allowed_courses:
            raise serializers.ValidationError(
                {"course_ids": f"يجب اختيار {allowed_courses} مادة/مواد بالضبط لهذه الباقة"}
            )
        courses_count = Course.objects.filter(id__in=attrs["course_ids"], is_active=True).count()
        if courses_count != len(attrs["course_ids"]):
            raise serializers.ValidationError(
                {"course_ids": "مادة أو أكثر من المواد المحددة غير موجودة أو غير نشطة"}
            )

        attrs["plan"] = plan
        attrs["user"] = user
        return attrs


class SubscriptionCoursesSerializer(serializers.Serializer):
    course_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )

    def validate_course_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("لا يمكن اختيار نفس المادة أكثر من مرة")

        unique_ids = list(dict.fromkeys(value))
        subscription = self.context["subscription"]
        allowed_courses = subscription.plan.number_of_allowed_courses_to_subscribe
        if len(unique_ids) != allowed_courses:
            raise serializers.ValidationError(
                f"يجب اختيار {allowed_courses} مادة/مواد بالضبط لهذه الباقة"
            )
        courses_count = Course.objects.filter(id__in=unique_ids, is_active=True).count()
        if courses_count != len(unique_ids):
            raise serializers.ValidationError("مادة أو أكثر من المواد المحددة غير موجودة أو غير نشطة")
        return unique_ids
