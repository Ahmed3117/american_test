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
