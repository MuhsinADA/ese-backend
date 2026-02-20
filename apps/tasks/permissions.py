"""Custom permissions for enforcing object-level ownership."""

from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """
    Object-level permission: only the owner of an object may access it.

    Expects the object to have a `user` attribute pointing to the owning User.
    """

    def has_object_permission(self, request, view, obj):
        return obj.user == request.user
