from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from course.models import Course

from .models import Plan, PlanSubscription
from .serializers import PlanSerializer, PlanSubscriptionSerializer, SubscribePlanSerializer
from .services import create_plan_subscription_invoice


class PlanListView(generics.ListAPIView):
    serializer_class = PlanSerializer
    permission_classes = [IsAuthenticated]
    queryset = Plan.objects.all()


class MyPlanSubscriptionsView(generics.ListAPIView):
    serializer_class = PlanSubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PlanSubscription.objects.filter(student=self.request.user.student).prefetch_related("courses")


class SubscribePlanView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, plan_id):
        plan = get_object_or_404(Plan, pk=plan_id, is_active=True)
        serializer = SubscribePlanSerializer(data=request.data, context={"plan": plan})
        serializer.is_valid(raise_exception=True)

        course_ids = serializer.validated_data["course_ids"]

        with transaction.atomic():
            active_subscriptions = [
                subscription
                for subscription in PlanSubscription.objects.select_for_update()
                .filter(
                    student=request.user.student,
                    plan=plan,
                    payment_status__in=[
                        PlanSubscription.PAYMENT_PAID,
                        PlanSubscription.PAYMENT_MANUAL,
                    ],
                )
                .prefetch_related("courses", "plan")
                if subscription.has_access_now
            ]

            if active_subscriptions:
                subscription = active_subscriptions[0]
                selected_course_ids = set(course_ids)
                existing_course_ids = set()
                for active_subscription in active_subscriptions:
                    existing_course_ids.update(active_subscription.courses.values_list("id", flat=True))

                if selected_course_ids & existing_course_ids:
                    return Response(
                        {"course_ids": ["أنت مشترك بالفعل في مادة أو أكثر من المواد المحددة داخل هذه الباقة"]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                current_count = subscription.courses.count()
                remaining_count = plan.number_of_allowed_courses_to_subscribe - current_count
                if remaining_count <= 0:
                    return Response(
                        {"course_ids": ["لقد وصلت إلى الحد الأقصى للمواد المسموح بها في هذه الباقة"]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if len(course_ids) > remaining_count:
                    return Response(
                        {
                            "course_ids": [
                                f"لا يمكن إضافة {len(course_ids)} مادة/مواد. المتبقي في هذه الباقة {remaining_count} مادة/مواد فقط"
                            ]
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                subscription.courses.add(*Course.objects.filter(id__in=course_ids))
                subscription.sync_course_subscriptions()
                response = PlanSubscriptionSerializer(subscription, context={"request": request}).data
                response["message"] = "تمت إضافة المواد الجديدة إلى اشتراكك الحالي بنجاح"
                response["added_course_ids"] = course_ids
                response["payment"] = None
                return Response(response, status=status.HTTP_200_OK)

            subscription = PlanSubscription.objects.create(student=request.user.student, plan=plan)
            subscription.courses.set(Course.objects.filter(id__in=course_ids))

        invoice_result = create_plan_subscription_invoice(subscription)
        response = PlanSubscriptionSerializer(subscription, context={"request": request}).data
        response["payment"] = invoice_result
        return Response(response, status=status.HTTP_201_CREATED)


class ManualConfirmPlanSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, subscription_id):
        if not request.user.is_staff:
            return Response({"error": " يلزم وجود صلاحية المسؤول"}, status=status.HTTP_403_FORBIDDEN)
        subscription = get_object_or_404(PlanSubscription, pk=subscription_id)
        subscription.mark_paid(status=PlanSubscription.PAYMENT_MANUAL)
        return Response(PlanSubscriptionSerializer(subscription, context={"request": request}).data)
