from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class BusinessApiKeyAuthentication(BaseAuthentication):
    """
    AI → Backend requests use X-API-Key header.
    Resolves to the Business object (not a user).
    Views access the business via request.business.
    """

    def authenticate(self, request):
        api_key = request.META.get("HTTP_X_API_KEY")
        if not api_key:
            return None  # let other authenticators try

        from apps.accounts.models import Business

        try:
            business = Business.objects.get(api_key=api_key, is_active=True)
        except Business.DoesNotExist:
            raise AuthenticationFailed("Invalid or inactive API key.")

        # Return (user=None, auth=business) — views use request.auth
        return (None, business)

    def authenticate_header(self, request):
        return "X-API-Key"
