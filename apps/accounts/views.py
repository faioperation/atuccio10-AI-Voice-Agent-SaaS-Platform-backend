from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate, get_user_model
from django.conf import settings
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from apps.accounts import serializers
from apps.accounts.models import OTPCode, Business
from apps.accounts.services import utils, schemas
from apps.accounts.services.utils import set_auth_cookies
from apps.accounts.services.permissions import IsVerifiedUser

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = serializers.RegisterSerializer

    @swagger_auto_schema(**schemas.register_schema)
    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        OTPCode.clean_expired()

        otp = utils.generate_otp(user, OTPCode.OTPType.EMAIL_VERIFY)
        utils.send_otp_email(user, otp, OTPCode.OTPType.EMAIL_VERIFY)
        utils.update_otp_rate_limit(user)

        response = Response(
            {
                "user": serializers.UserSerializer(user).data,
                "message": "Registration successful. Please verify your email.",
            },
            status=status.HTTP_201_CREATED,
        )
        return set_auth_cookies(response, user)


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    serializer_class = serializers.VerifyEmailSerializer

    @swagger_auto_schema(**schemas.verify_email_schema)
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]

        OTPCode.clean_expired()

        user = User.objects.filter(email=email).first()
        if not user:
            return Response(
                {"error": "User not found", "code": "user_not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.is_verified:
            return Response(
                {"error": "Email already verified", "code": "already_verified"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_obj = OTPCode.objects.filter(
            user=user,
            code=otp,
            type=OTPCode.OTPType.EMAIL_VERIFY,
            expires_at__gt=timezone.now(),
        ).first()

        if not otp_obj:
            return Response(
                {"error": "Invalid or expired OTP", "code": "invalid_otp"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_verified = True
        user.save()

        otp_obj.delete()

        utils.reset_otp_rate_limit(user)

        return Response({"message": "Email verified successfully!"})


class ResendOTPView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(**schemas.resend_otp_schema)
    def post(self, request):
        email = request.data.get("email")
        otp_type = request.data.get("type", OTPCode.OTPType.EMAIL_VERIFY)

        OTPCode.clean_expired()

        user = User.objects.filter(email=email).first()
        if not user:
            return Response(
                {"error": "User not found", "code": "user_not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.is_verified and otp_type == OTPCode.OTPType.EMAIL_VERIFY:
            return Response(
                {"error": "Email already verified", "code": "already_verified"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = "OTP sent successfully!"

        allowed, wait_time = utils.check_otp_rate_limit(user)
        if not allowed:
            return Response(
                {
                    "error": f"Please wait {wait_time} seconds before requesting another OTP.",
                    "code": "rate_limit_exceeded",
                    "wait_time": wait_time,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        otp = utils.generate_otp(user, otp_type)
        utils.send_otp_email(user, otp, otp_type)
        utils.update_otp_rate_limit(user)

        return Response({"message": message})


class LoginView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(**schemas.login_schema)
    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        user = authenticate(email=email, password=password)

        if user:
            if not user.is_verified:
                return Response(
                    {"error": "Email not verified", "code": "email_not_verified"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            response = Response(
                {
                    "user": serializers.UserSerializer(user).data,
                    "message": "Login successful",
                }
            )
            return set_auth_cookies(response, user)

        return Response(
            {"error": "Invalid Credentials", "code": "invalid_credentials"},
            status=status.HTTP_401_UNAUTHORIZED,
        )


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    serializer_class = serializers.ForgotPasswordSerializer

    @swagger_auto_schema(**schemas.forgot_password_schema)
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        OTPCode.clean_expired()

        email = serializer.validated_data["email"]
        user = User.objects.filter(email=email).first()

        if user:
            allowed, wait_time = utils.check_otp_rate_limit(user)
            if not allowed:
                return Response(
                    {
                        "error": f"Please wait {wait_time} seconds.",
                        "wait_time": wait_time,
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            otp = utils.generate_otp(user, OTPCode.OTPType.PASSWORD_RESET)
            utils.send_otp_email(user, otp, OTPCode.OTPType.PASSWORD_RESET)
            utils.update_otp_rate_limit(user)

        return Response(
            {
                "message": "If an account exists with this email, a reset code has been sent."
            }
        )


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    serializer_class = serializers.ResetPasswordSerializer

    @swagger_auto_schema(**schemas.reset_password_schema)
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        OTPCode.clean_expired()

        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]
        new_password = serializer.validated_data["new_password"]

        user = User.objects.filter(email=email).first()
        if not user:
            return Response(
                {"error": "Invalid request", "code": "invalid_request"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_obj = OTPCode.objects.filter(
            user=user,
            code=otp,
            type=OTPCode.OTPType.PASSWORD_RESET,
            expires_at__gt=timezone.now(),
        ).first()

        if not otp_obj:
            return Response(
                {"error": "Invalid or expired OTP", "code": "invalid_otp"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()

        otp_obj.delete()

        utils.reset_otp_rate_limit(user)

        return Response({"message": "Password reset successful!"})


class LogoutView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(**schemas.logout_schema)
    def post(self, request):
        jwt = settings.SIMPLE_JWT
        response = Response({"message": "Logout successful"})
        response.delete_cookie(
            jwt["AUTH_COOKIE"],
            path=jwt["AUTH_COOKIE_PATH"],
            samesite=jwt["AUTH_COOKIE_SAMESITE"],
        )
        response.delete_cookie(
            jwt["AUTH_COOKIE_REFRESH"],
            path=jwt["AUTH_COOKIE_PATH"],
            samesite=jwt["AUTH_COOKIE_SAMESITE"],
        )
        return response


class ChangePasswordView(APIView):
    permission_classes = [IsVerifiedUser]
    serializer_class = serializers.ChangePasswordSerializer

    @swagger_auto_schema(**schemas.change_password_schema)
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response(
                {"error": "Invalid old password."}, status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(serializer.validated_data["new_password"])
        user.save()

        return Response({"message": "Password updated successfully!"})


class UserProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsVerifiedUser]
    serializer_class = serializers.UserSerializer

    @swagger_auto_schema(**schemas.user_profile_schema)
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    @swagger_auto_schema(**schemas.user_profile_schema)
    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    @swagger_auto_schema(**schemas.user_profile_schema)
    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def get_object(self):
        return (
            User.objects.select_related("business")
            .prefetch_related(
                "user_roles__role",
                "business__subscriptions__plan_price__plan",
            )
            .get(pk=self.request.user.pk)
        )


class BusinessProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsVerifiedUser]
    serializer_class = serializers.BusinessSerializer

    @swagger_auto_schema(**schemas.business_profile_schema)
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    @swagger_auto_schema(**schemas.business_profile_schema)
    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    @swagger_auto_schema(**schemas.business_profile_schema)
    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def get_object(self):
        return self.request.user.business
