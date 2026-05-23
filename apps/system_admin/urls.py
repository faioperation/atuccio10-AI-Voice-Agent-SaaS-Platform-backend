from django.urls import path
from apps.system_admin.views import (
    SystemUserListView,
    BusinessAdminListView,
    SystemAdminCreateView,
    SystemAdminDeleteView,
    SystemAdminStatsView,
    AdminAllInvoicesView,
    AdminAllSubscriptionsView,
    BusinessAdminDetailView,
)

urlpatterns = [
    path("stats/", SystemAdminStatsView.as_view(), name="system_admin_stats"),
    path("system-admins/", SystemUserListView.as_view(), name="system_user_list"),
    path(
        "business-admins/", BusinessAdminListView.as_view(), name="business_admin_list"
    ),
    path(
        "business-admins/<uuid:user_id>/",
        BusinessAdminDetailView.as_view(),
        name="business_admin_detail",
    ),
    path("create/", SystemAdminCreateView.as_view(), name="system_admin_create"),
    path(
        "delete/<uuid:pk>/", SystemAdminDeleteView.as_view(), name="system_admin_delete"
    ),
    path("invoices/", AdminAllInvoicesView.as_view(), name="admin_all_invoices"),
    path(
        "subscriptions/",
        AdminAllSubscriptionsView.as_view(),
        name="admin_all_subscriptions",
    ),
]
