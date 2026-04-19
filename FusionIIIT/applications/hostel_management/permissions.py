"""
Hostel Management Permissions

Hostel-scoped permission classes for the setup foundation chunk.
These enforce role-based access control across all hostel setup endpoints.
"""

from rest_framework.permissions import BasePermission
from .models import HostelStaffAssignment
from . import selectors


class IsHostelSuperAdmin(BasePermission):
    """
    Permission for Super Admin role.

    Grants full CRUD on hostels, staff assignment, and status changes.
    Checks request.user.is_superuser (consistent with existing IsSuperAdmin pattern).
    """
    message = "Only Super Admins can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.is_superuser
        )


class IsAssignedToHostel(BasePermission):
    """
    Permission for Warden/Caretaker scoped to a specific hostel.

    Checks HostelStaffAssignment for the requesting user with is_active=True
    on the hostel identified by the `pk` URL kwarg.

    Wardens and Caretakers get read-only access to hostel config
    within their assigned hostel.
    """
    message = "You are not assigned to this hostel."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        # Super admins always pass
        if request.user.is_superuser:
            return True

        hostel_id = view.kwargs.get('pk')
        if not hostel_id:
            return False

        # Check robust list of assigned hostels for the user
        assigned_hostels = selectors.list_assigned_hostels(request.user)
        return assigned_hostels.filter(hall_id=hostel_id).exists()
