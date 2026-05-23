from rest_framework.permissions import BasePermission


class IsAIAgent(BasePermission):
    """
    Grants access only to requests authenticated via X-API-Key.
    request.auth will be the Business instance.
    """

    def has_permission(self, request, view):
        from apps.accounts.models import Business
        return isinstance(request.auth, Business)
