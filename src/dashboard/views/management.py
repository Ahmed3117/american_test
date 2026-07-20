from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from course.models import Course, Unit
from course.serializers import CourseSerializer, UnitSerializer
from subscription.models import DiscountCoupon, Plan, PlanSubscription
from subscription.serializers import (
    DiscountCouponSerializer,
    PlanSerializer,
    PlanSubscriptionSerializer,
)


class StaffOnlyMixin:
    permission_classes = [IsAdminUser]


class PlanListCreateView(StaffOnlyMixin, generics.ListCreateAPIView):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer


class PlanDetailView(StaffOnlyMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer


class DiscountCouponListCreateView(StaffOnlyMixin, generics.ListCreateAPIView):
    queryset = DiscountCoupon.objects.select_related("plan").prefetch_related("subscriptions")
    serializer_class = DiscountCouponSerializer


class DiscountCouponDetailView(StaffOnlyMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = DiscountCoupon.objects.select_related("plan").prefetch_related("subscriptions")
    serializer_class = DiscountCouponSerializer


class PlanSubscriptionListView(StaffOnlyMixin, generics.ListAPIView):
    serializer_class = PlanSubscriptionSerializer

    def get_queryset(self):
        return PlanSubscription.objects.select_related("student", "plan").prefetch_related("courses")


class ConfirmPlanSubscriptionView(StaffOnlyMixin, APIView):
    def post(self, request, subscription_id):
        subscription = get_object_or_404(PlanSubscription, pk=subscription_id)
        subscription.mark_paid(status=PlanSubscription.PAYMENT_MANUAL)
        return Response(PlanSubscriptionSerializer(subscription, context={"request": request}).data)


class CourseListCreateView(StaffOnlyMixin, generics.ListCreateAPIView):
    queryset = Course.objects.prefetch_related("units")
    serializer_class = CourseSerializer


class CourseDetailView(StaffOnlyMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Course.objects.prefetch_related("units")
    serializer_class = CourseSerializer


class UnitListCreateView(StaffOnlyMixin, generics.ListCreateAPIView):
    serializer_class = UnitSerializer

    def get_queryset(self):
        return Unit.objects.filter(course_id=self.kwargs["course_id"])

    def perform_create(self, serializer):
        serializer.save(course_id=self.kwargs["course_id"])


class UnitDetailView(StaffOnlyMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
