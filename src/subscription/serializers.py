from rest_framework import serializers

from course.models import Course
from course.serializers import CourseSerializer

from .models import Plan, PlanSubscription


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


class PlanSubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    courses = CourseSerializer(many=True, read_only=True)
    has_access_now = serializers.BooleanField(read_only=True)

    class Meta:
        model = PlanSubscription
        fields = [
            "id",
            "plan",
            "courses",
            "payment_status",
            "has_access_now",
            "easypay_invoice_uid",
            "easypay_invoice_sequence",
            "easypay_payment_url",
            "paid_at",
            "created_at",
        ]


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
