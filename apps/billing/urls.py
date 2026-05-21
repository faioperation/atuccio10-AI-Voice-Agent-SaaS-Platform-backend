from django.urls import path
from apps.billing.views import (
    PlanListView,
    PlanDetailView,
    AdminPlanCreateView,
    AdminPlanUpdateView,
    AdminPlanDeleteView,
    SubscribeView,
    SwitchPlanView,
    MySubscriptionView,
    CancelSubscriptionView,
    MyInvoiceListView,
    PaymentSuccessView,
    VerifySessionView,
    InvoiceDownloadView,
    StripeWebhookView,
)

urlpatterns = [
    path("plans/", PlanListView.as_view(), name="billing-plan-list"),
    path("plans/<int:pk>/", PlanDetailView.as_view(), name="billing-plan-detail"),
    path(
        "admin/plans/", AdminPlanCreateView.as_view(), name="billing-admin-plan-create"
    ),
    path(
        "admin/plans/<int:pk>/",
        AdminPlanUpdateView.as_view(),
        name="billing-admin-plan-update",
    ),
    path(
        "admin/plans/<int:pk>/delete/",
        AdminPlanDeleteView.as_view(),
        name="billing-admin-plan-delete",
    ),
    path("subscribe/", SubscribeView.as_view(), name="billing-subscribe"),
    path("subscription/", MySubscriptionView.as_view(), name="billing-subscription"),
    path(
        "subscription/cancel/",
        CancelSubscriptionView.as_view(),
        name="billing-subscription-cancel",
    ),
    path(
        "subscription/switch/",
        SwitchPlanView.as_view(),
        name="billing-subscription-switch",
    ),
    path("invoices/", MyInvoiceListView.as_view(), name="billing-invoice-list"),
    path("success/", PaymentSuccessView.as_view(), name="billing-payment-success"),
    path("verify-session/", VerifySessionView.as_view(), name="billing-verify-session"),
    path(
        "invoices/<int:pk>/",
        InvoiceDownloadView.as_view(),
        name="billing-invoice-download",
    ),
    path("stripe/webhook/", StripeWebhookView.as_view(), name="billing-stripe-webhook"),
]
