import random
import string
import os
import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils import timezone
from email.mime.image import MIMEImage
from rest_framework_simplejwt.tokens import RefreshToken
from ..models import OTPCode

logger = logging.getLogger(__name__)


def set_auth_cookies(response, user):
    refresh = RefreshToken.for_user(user)
    jwt = settings.SIMPLE_JWT
    response.set_cookie(
        key=jwt["AUTH_COOKIE"],
        value=str(refresh.access_token),
        max_age=int(jwt["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        secure=jwt["AUTH_COOKIE_SECURE"],
        httponly=jwt["AUTH_COOKIE_HTTP_ONLY"],
        samesite=jwt["AUTH_COOKIE_SAMESITE"],
        path=jwt["AUTH_COOKIE_PATH"],
    )
    response.set_cookie(
        key=jwt["AUTH_COOKIE_REFRESH"],
        value=str(refresh),
        max_age=int(jwt["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        secure=jwt["AUTH_COOKIE_SECURE"],
        httponly=jwt["AUTH_COOKIE_HTTP_ONLY"],
        samesite=jwt["AUTH_COOKIE_SAMESITE"],
        path=jwt["AUTH_COOKIE_PATH"],
    )
    return response


def generate_otp(user, otp_type):
    OTPCode.objects.filter(user=user, type=otp_type, is_used=False).delete()

    code = "".join(random.choices(string.digits, k=6))
    OTPCode.objects.create(user=user, code=code, type=otp_type)
    return code


def check_otp_rate_limit(user):
    """
    Checks if the user is allowed to request a new OTP using DB fields.
    Returns: (bool allowed, int wait_time_remaining)
    """
    if not user.last_otp_sent_at:
        return True, 0

    resend_count = user.otp_resend_count
    wait_time = 30 * (2 ** (resend_count - 1)) if resend_count > 0 else 30

    wait_time = min(wait_time, 86400)

    elapsed_time = (timezone.now() - user.last_otp_sent_at).total_seconds()

    if elapsed_time < wait_time:
        return False, int(wait_time - elapsed_time)

    return True, 0


def update_otp_rate_limit(user):
    """
    Updates the resend count and last sent time in DB.
    """
    user.otp_resend_count += 1
    user.last_otp_sent_at = timezone.now()
    user.save()


def reset_otp_rate_limit(user):
    """
    Resets the rate limit after a successful verification.
    """
    user.otp_resend_count = 0
    user.last_otp_sent_at = None
    user.save()


def send_otp_email(user, code, otp_type):
    subject = ""
    if otp_type == OTPCode.OTPType.EMAIL_VERIFY:
        subject = "Verify your email - Clinch SAAS"
    elif otp_type == OTPCode.OTPType.PASSWORD_RESET:
        subject = "Reset your password - Clinch SAAS"

    context = {
        "user_name": user.name,
        "otp": code,
    }

    html_content = render_to_string("accounts/emails/otp_email.html", context)
    text_content = strip_tags(html_content)

    try:
        msg = EmailMultiAlternatives(
            subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.mixed_subtype = "related"
        msg.send()
        return True
    except Exception as e:
        logger.error("Error sending email: %s", e)
        return False
