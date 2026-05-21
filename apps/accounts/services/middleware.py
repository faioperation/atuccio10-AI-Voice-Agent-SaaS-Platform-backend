from django.utils.deprecation import MiddlewareMixin
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from rest_framework_simplejwt.exceptions import TokenError


class JWTCookieMiddleware(MiddlewareMixin):
    def process_request(self, request):
        access_token = request.COOKIES.get(settings.SIMPLE_JWT['AUTH_COOKIE'])
        refresh_token = request.COOKIES.get(settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'])

        print(f"[JWT] path={request.path} access={'present' if access_token else 'MISSING'} refresh={'present' if refresh_token else 'MISSING'}")

        if not access_token and refresh_token:
            try:
                refresh = RefreshToken(refresh_token)
                new_access_token = str(refresh.access_token)
                request.COOKIES[settings.SIMPLE_JWT['AUTH_COOKIE']] = new_access_token
                request._new_access_token = new_access_token
                print(f"[JWT] refreshed access token for {request.path}")
            except TokenError as e:
                print(f"[JWT] refresh token invalid — {e}")

    def process_response(self, request, response):
        if hasattr(request, '_new_access_token'):
            jwt = settings.SIMPLE_JWT
            response.set_cookie(
                key=jwt['AUTH_COOKIE'],
                value=request._new_access_token,
                max_age=int(jwt['ACCESS_TOKEN_LIFETIME'].total_seconds()),
                secure=jwt['AUTH_COOKIE_SECURE'],
                httponly=jwt['AUTH_COOKIE_HTTP_ONLY'],
                samesite=jwt['AUTH_COOKIE_SAMESITE'],
                path=jwt['AUTH_COOKIE_PATH'],
            )
        return response
