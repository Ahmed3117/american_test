from django.urls import path

from . import views

app_name = "subscription"

urlpatterns = [
    path("", views.PlanListView.as_view(), name="plan-list"),
    path("my-subscriptions/", views.MyPlanSubscriptionsView.as_view(), name="my-plan-subscriptions"),
    path("<int:plan_id>/subscribe/", views.SubscribePlanView.as_view(), name="subscribe-plan"),
    path("<int:plan_id>/has-paid-subscription/", views.HasPaidPlanSubscriptionView.as_view(), name="has-paid-plan-subscription"),
    path("subscriptions/<int:subscription_id>/create-invoice/", views.CreatePlanSubscriptionInvoiceView.as_view(), name="create-plan-subscription-invoice"),
    path("subscriptions/<int:subscription_id>/apply-coupon/", views.ApplyDiscountCouponView.as_view(), name="apply-discount-coupon"),
    path("subscriptions/<int:subscription_id>/payment-status/", views.PlanSubscriptionPaymentStatusView.as_view(), name="plan-subscription-payment-status"),
    path("subscriptions/<int:subscription_id>/manual-confirm/", views.ManualConfirmPlanSubscriptionView.as_view(), name="manual-confirm-plan-subscription"),
]
