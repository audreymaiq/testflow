"""Server-side role checks for protected API views."""

from rest_framework.permissions import BasePermission


class IsReviewer(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (
                user.is_superuser
                or user.groups.filter(name="Reviewer").exists()
                or (user.is_staff and user.groups.filter(name="Admin").exists())
            )
        )


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_staff
            and (user.is_superuser or user.groups.filter(name="Admin").exists())
        )
