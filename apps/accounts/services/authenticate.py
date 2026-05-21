from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.conf import settings


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        raw_token = request.COOKIES.get(settings.SIMPLE_JWT["AUTH_COOKIE"])
        if raw_token is None:
            print(f"[AUTH] no access cookie on {request.path}")
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
            user = self.get_user(validated_token)
            print(f"[AUTH] authenticated user={user.email} on {request.path}")
            return user, validated_token
        except (InvalidToken, TokenError) as e:
            print(f"[AUTH] invalid token on {request.path} — {e}")
            return None
