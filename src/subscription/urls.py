from django.urls import path

from . import views

app_name = "subscription"

urlpatterns = [
    path("", views.PlanListView.as_view(), name="plan-list"),
    path("my-subscriptions/", views.MyPlanSubscriptionsView.as_view(), name="my-plan-subscriptions"),
    path("<int:plan_id>/subscribe/", views.SubscribePlanView.as_view(), name="subscribe-plan"),
    path("subscriptions/<int:subscription_id>/manual-confirm/", views.ManualConfirmPlanSubscriptionView.as_view(), name="manual-confirm-plan-subscription"),
]
