from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as filters
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from course.models import Course
from course.serializers import CourseSerializer
from student.models import Student
from subscription.models import DiscountCoupon, Plan, PlanSubscription, PlanSubscriptionCourse
from subscription.serializers import (
    DashboardSubscriptionCreateSerializer,
    DashboardPlanSubscriptionSerializer,
    DiscountCouponSerializer,
    PlanSerializer,
    PlanSubscriptionSerializer,
    SubscriptionCoursesSerializer,
)


class StaffOnlyMixin:
    permission_classes = [IsAdminUser]


class PlanListCreateView(StaffOnlyMixin, generics.ListCreateAPIView):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer


class PlanDetailView(StaffOnlyMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
        except ProtectedError:
            return Response(
                {
                    "error": (
                        "This plan cannot be deleted because it is used by one or "
                        "more subscriptions. Deactivate it instead."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class DiscountCouponListCreateView(StaffOnlyMixin, generics.ListCreateAPIView):
    queryset = DiscountCoupon.objects.select_related("plan").prefetch_related("subscriptions")
    serializer_class = DiscountCouponSerializer


class DiscountCouponDetailView(StaffOnlyMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = DiscountCoupon.objects.select_related("plan").prefetch_related("subscriptions")
    serializer_class = DiscountCouponSerializer


class PlanSubscriptionFilter(filters.FilterSet):
    username = filters.CharFilter(field_name="student__user__username", lookup_expr="icontains")
    name = filters.CharFilter(field_name="student__user__name", lookup_expr="icontains")
    payment_status = filters.ChoiceFilter(choices=[
        (PlanSubscription.PAYMENT_PAID, "Paid"),
        (PlanSubscription.PAYMENT_PENDING, "Pending"),
        (PlanSubscription.PAYMENT_MANUAL, "Manual"),
    ])

    class Meta:
        model = PlanSubscription
        fields = ["payment_status", "username", "name"]


class PlanSubscriptionListView(StaffOnlyMixin, generics.ListAPIView):
    serializer_class = DashboardPlanSubscriptionSerializer
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = PlanSubscriptionFilter

    def get_queryset(self):
        return PlanSubscription.objects.select_related(
            "student__user", "plan", "discount_coupon"
        ).prefetch_related("courses").order_by("-created_at", "-id")

    def post(self, request):
        serializer = DashboardSubscriptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            Student.objects.select_for_update().get(pk=data["user"].student.pk)
            plan_subscriptions = list(
                PlanSubscription.objects.select_for_update()
                .filter(student=data["user"].student, plan=data["plan"])
                .select_related("plan")
                .order_by("-created_at")
            )
            active_paid_subscription = next(
                (subscription for subscription in plan_subscriptions if subscription.has_access_now),
                None,
            )
            if active_paid_subscription:
                raise ValidationError({"plan": "يوجد بالفعل اشتراك مدفوع نشط لهذه الخطة للطالب"})

            access_starts_on, access_ends_on = data["plan"].period_for()
            subscription = PlanSubscription.objects.create(
                student=data["user"].student,
                plan=data["plan"],
                access_starts_on=access_starts_on,
                access_ends_on=access_ends_on,
            )
            subscription.courses.set(Course.objects.filter(id__in=data["course_ids"]))
            if data["mark_paid"]:
                subscription.mark_paid(status=PlanSubscription.PAYMENT_MANUAL)

        return Response(
            PlanSubscriptionSerializer(subscription, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class StudentPlanSubscriptionListView(PlanSubscriptionListView):
    """Subscription/payment history scoped by the student's accounts.User.id."""

    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        student = get_object_or_404(
            Student, user_id=self.kwargs["student_id"], user__user_type="student",
            user__is_staff=False, user__is_superuser=False,
        )
        return super().get_queryset().filter(student_id=student.pk)


class PlanSubscriptionDeleteView(StaffOnlyMixin, APIView):
    """Preserve the existing delete route; also expose dashboard detail GET."""

    def get(self, request, subscription_id):
        subscription = get_object_or_404(
            PlanSubscription.objects.select_related("student__user", "plan", "discount_coupon").prefetch_related("courses"),
            pk=subscription_id,
        )
        return Response(DashboardPlanSubscriptionSerializer(subscription, context={"request": request}).data)

    def delete(self, request, subscription_id):
        subscription = get_object_or_404(PlanSubscription, pk=subscription_id)
        subscription.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConfirmPlanSubscriptionView(StaffOnlyMixin, APIView):
    def post(self, request, subscription_id):
        subscription = get_object_or_404(PlanSubscription, pk=subscription_id)
        subscription.mark_paid(status=PlanSubscription.PAYMENT_MANUAL)
        return Response(PlanSubscriptionSerializer(subscription, context={"request": request}).data)


class SubscriptionCoursesView(StaffOnlyMixin, APIView):
    def patch(self, request, subscription_id):
        subscription = get_object_or_404(
            PlanSubscription.objects.select_related("plan"), pk=subscription_id
        )
        serializer = SubscriptionCoursesSerializer(
            data=request.data, context={"subscription": subscription}
        )
        serializer.is_valid(raise_exception=True)

        # Admin override: replace rows through the through-model directly so the
        # paid-subscription immutability signal/clean guards do not block this change.
        with transaction.atomic():
            PlanSubscriptionCourse.objects.filter(subscription=subscription).delete()
            PlanSubscriptionCourse.objects.bulk_create(
                PlanSubscriptionCourse(subscription=subscription, course_id=course_id)
                for course_id in serializer.validated_data["course_ids"]
            )
        return Response(PlanSubscriptionSerializer(subscription, context={"request": request}).data)


class CourseListCreateView(StaffOnlyMixin, generics.ListCreateAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer


class CourseDetailView(StaffOnlyMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
