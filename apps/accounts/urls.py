from django.urls import path
from apps.accounts.views import (
    RegisterView,
    LoginView,
    UserProfileView,
    BusinessProfileView,
    LogoutView,
    VerifyEmailView,
    ResendOTPView,
    ForgotPasswordView,
    ResetPasswordView,
    ChangePasswordView,
)
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # Auth Core
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    # Verification & Password
    path("verify-email/", VerifyEmailView.as_view(), name="verify_email"),
    path("resend-otp/", ResendOTPView.as_view(), name="resend_otp"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot_password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset_password"),
    path("change-password/", ChangePasswordView.as_view(), name="change_password"),
    # Profiles
    path("user-profile/", UserProfileView.as_view(), name="user_profile"),
    path("business-profile/", BusinessProfileView.as_view(), name="business_profile"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
