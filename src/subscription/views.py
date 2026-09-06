from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from course.models import Course
from services.easypay_service import easypay_service
from student.models import Student

from .models import DiscountCoupon, Plan, PlanSubscription
from .serializers import (
    ApplyDiscountCouponSerializer,
    PlanSerializer,
    PlanSubscriptionSerializer,
    StudentPlanSerializer,
    SubscribePlanSerializer,
)
from .services import create_plan_subscription_invoice


class HasStudentProfile(BasePermission):
    message = "A student account is required."

    def has_permission(self, request, view):
        return hasattr(request.user, "student")


class PlanListView(generics.ListAPIView):
    serializer_class = StudentPlanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # `is_available_now` is a Python property that depends on
        # `period_for(today)`, so we can't push it to SQL. We narrow to
        # `is_active=True` at the DB level and then filter in Python by the
        # computed property.
        plans = [
            plan
            for plan in Plan.objects.filter(is_active=True)
            if plan.is_currently_available()
        ]
        self.visible_plan_ids = [plan.id for plan in plans]
        return plans

    def get_serializer_context(self):
        context = super().get_serializer_context()
        subscriptions = PlanSubscription.objects.filter(
            student__user_id=self.request.user.id,
            plan_id__in=getattr(self, "visible_plan_ids", []),
        ).select_related("plan")
        context["pending_plan_ids"] = {
            subscription.plan_id
            for subscription in subscriptions
            if subscription.payment_status == PlanSubscription.PAYMENT_PENDING
        }
        context["accessible_plan_ids"] = {
            subscription.plan_id
            for subscription in subscriptions
            if subscription.has_access_now
        }
        return context


class MyPlanSubscriptionsView(generics.ListAPIView):
    serializer_class = PlanSubscriptionSerializer
    permission_classes = [IsAuthenticated, HasStudentProfile]

    def get_queryset(self):
        return PlanSubscription.objects.filter(student=self.request.user.student).prefetch_related("courses")


class HasPaidPlanSubscriptionView(APIView):
    permission_classes = [IsAuthenticated, HasStudentProfile]

    def get(self, request, plan_id):
        plan = get_object_or_404(Plan, pk=plan_id)
        paid_subscriptions = (
            PlanSubscription.objects.filter(
                student=request.user.student,
                plan=plan,
                payment_status__in=[
                    PlanSubscription.PAYMENT_PAID,
                    PlanSubscription.PAYMENT_MANUAL,
                ],
            )
            .select_related("plan")
            .order_by("-created_at")
        )
        paid_subscription = next(
            (subscription for subscription in paid_subscriptions if subscription.has_access_now),
            None,
        )
        has_paid = paid_subscription is not None
        return Response(
            {
                "plan_id": plan.id,
                "has_paid_subscription": has_paid,
                "subscription_id": paid_subscription.id if has_paid else None,
            }
        )


class PlanSubscriptionPaymentStatusView(APIView):
    permission_classes = [IsAuthenticated, HasStudentProfile]

    def get(self, request, subscription_id):
        subscription = get_object_or_404(
            PlanSubscription.objects.select_related("plan", "student"),
            pk=subscription_id,
        )
        if subscription.student_id != request.user.student.id:
            return Response({"error": "غير مصرح"}, status=status.HTTP_403_FORBIDDEN)

        remote_status = None
        remote_error = None
        if subscription.easypay_invoice_uid and subscription.easypay_invoice_sequence:
            result = easypay_service.check_payment_status(
                subscription.easypay_invoice_uid,
                subscription.easypay_invoice_sequence,
            )
            if result.get("success"):
                remote_status = (result.get("data") or {}).get("payment_status")
            else:
                remote_error = result.get("error")

        return Response(
            {
                "subscription_id": subscription.id,
                "plan_id": subscription.plan_id,
                "local_payment_status": subscription.payment_status,
                "is_paid": subscription.is_paid,
                "has_access_now": subscription.has_access_now,
                "remote_payment_status": remote_status,
                "remote_error": remote_error,
                "payment_url": subscription.easypay_payment_url,
                "paid_at": subscription.paid_at,
                "access_starts_on": subscription.access_starts_on,
                "access_ends_on": subscription.access_ends_on,
            }
        )


class SubscribePlanView(APIView):
    permission_classes = [IsAuthenticated, HasStudentProfile]

    def post(self, request, plan_id):
        plan = get_object_or_404(Plan, pk=plan_id, is_active=True)
        if not plan.is_currently_available():
            raise ValidationError(
                {"plan": ["This plan is outside its current subscription window."]}
            )
        serializer = SubscribePlanSerializer(data=request.data, context={"plan": plan})
        serializer.is_valid(raise_exception=True)

        course_ids = serializer.validated_data["course_ids"]

        with transaction.atomic():
            # Lock one stable parent row so two first-time requests for the
            # same student cannot both create a subscription concurrently.
            Student.objects.select_for_update().get(pk=request.user.student.pk)
            plan_subscriptions = list(
                PlanSubscription.objects.select_for_update()
                .filter(student=request.user.student, plan=plan)
                .select_related("plan")
                .order_by("-created_at")
            )
            active_paid_subscription = next(
                (
                    subscription
                    for subscription in plan_subscriptions
                    if subscription.has_access_now
                ),
                None,
            )
            if active_paid_subscription:
                raise ValidationError(
                    {
                        "plan": [
                            "You already have an active paid subscription to this plan. "
                            "Subscribe to it again after the current access period ends."
                        ]
                    }
                )

            existing_subscription = plan_subscriptions[0] if plan_subscriptions else None
            access_starts_on, access_ends_on = plan.period_for()

            if existing_subscription and not existing_subscription.is_paid:
                # Create the new one first, then remove the old unpaid one
                new_subscription = PlanSubscription.objects.create(
                    student=request.user.student,
                    plan=plan,
                    access_starts_on=access_starts_on,
                    access_ends_on=access_ends_on,
                )
                new_subscription.courses.set(Course.objects.filter(id__in=course_ids))
                existing_subscription.delete()
            else:
                # No existing subscription, or the existing one is paid:
                # create a new one and keep the old paid one untouched.
                new_subscription = PlanSubscription.objects.create(
                    student=request.user.student,
                    plan=plan,
                    access_starts_on=access_starts_on,
                    access_ends_on=access_ends_on,
                )
                new_subscription.courses.set(Course.objects.filter(id__in=course_ids))

        response = PlanSubscriptionSerializer(new_subscription, context={"request": request}).data
        return Response(response, status=status.HTTP_201_CREATED)


class CreatePlanSubscriptionInvoiceView(APIView):
    permission_classes = [IsAuthenticated, HasStudentProfile]

    def post(self, request, subscription_id):
        subscription = get_object_or_404(
            PlanSubscription.objects.select_related("plan", "student"),
            pk=subscription_id,
        )
        if subscription.student_id != request.user.student.id:
            return Response({"error": "غير مصرح"}, status=status.HTTP_403_FORBIDDEN)

        if subscription.is_paid:
            return Response(
                {"error": "هذا الاشتراك مدفوع بالفعل"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if subscription.payment_status == PlanSubscription.PAYMENT_MANUAL:
            return Response(
                {"error": "لا يمكن إنشاء فاتورة لاشتراك تم تأكيده يدوياً"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice_result = create_plan_subscription_invoice(subscription)
        response = PlanSubscriptionSerializer(subscription, context={"request": request}).data
        response["payment"] = invoice_result
        status_code = status.HTTP_200_OK if invoice_result.get("success") else status.HTTP_502_BAD_GATEWAY
        return Response(response, status=status_code)


class ApplyDiscountCouponView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, subscription_id):
        serializer = ApplyDiscountCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            # Keep nullable relations out of this locked query. PostgreSQL
            # rejects FOR UPDATE when it targets the nullable side of the
            # outer join produced by select_related("discount_coupon").
            subscription = get_object_or_404(
                PlanSubscription.objects.select_for_update().select_related(
                    "plan", "student"
                ),
                pk=subscription_id,
            )
            request_student = getattr(request.user, "student", None)
            if not request_student or subscription.student_id != request_student.id:
                return Response({"error": "غير مصرح"}, status=status.HTTP_403_FORBIDDEN)

            if subscription.is_paid:
                raise ValidationError({"coupon": ["A coupon cannot be applied to a paid subscription."]})
            if subscription.easypay_invoice_uid or subscription.easypay_invoice_sequence:
                raise ValidationError({"coupon": ["A coupon cannot be applied after invoice generation."]})

            coupon_code = serializer.validated_data["coupon"]
            if subscription.discount_coupon_id:
                if subscription.discount_coupon.coupon == coupon_code:
                    response = PlanSubscriptionSerializer(
                        subscription, context={"request": request}
                    ).data
                    return Response(response)
                raise ValidationError({"coupon": ["A coupon has already been applied to this subscription."]})

            coupon = (
                DiscountCoupon.objects.select_for_update()
                .filter(coupon=coupon_code)
                .first()
            )
            if not coupon:
                raise ValidationError({"coupon": ["Invalid coupon."]})
            if coupon.plan_id is not None and coupon.plan_id != subscription.plan_id:
                raise ValidationError({"coupon": ["This coupon does not apply to the selected plan."]})
            if not coupon.is_valid_at():
                raise ValidationError({"coupon": ["This coupon is inactive or outside its validity period."]})
            if coupon.subscriptions.count() >= coupon.max_using_number:
                raise ValidationError({"coupon": ["This coupon has reached its maximum usage limit."]})

            subscription.apply_discount_coupon(coupon)

        response = PlanSubscriptionSerializer(subscription, context={"request": request}).data
        return Response(response)


class ManualConfirmPlanSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, subscription_id):
        if not request.user.is_staff:
            return Response({"error": " يلزم وجود صلاحية المسؤول"}, status=status.HTTP_403_FORBIDDEN)
        subscription = get_object_or_404(PlanSubscription, pk=subscription_id)
        subscription.mark_paid(status=PlanSubscription.PAYMENT_MANUAL)
        return Response(PlanSubscriptionSerializer(subscription, context={"request": request}).data)
