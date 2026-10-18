from rest_framework import permissions

class IsAdminUserOrReadOnly(permissions.BasePermission):
    """
    Allows read-only access to everyone, but requires admin permissions for modifications.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser))

class IsAdminRoleUser(permissions.BasePermission):
    """
    Allows access only to authenticated admin/staff users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser))

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or admin users to access/edit it.
    """
    def has_object_permission(self, request, view, obj):
        if request.user and (request.user.is_staff or request.user.is_superuser):
            return True
        # Check if obj has user attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False

class IsVerifiedUser(permissions.BasePermission):
    """
    Requires the user to be authenticated and verified (or staff/superuser/admin).
    Prevents unverified customer accounts from accessing protected customer resources.
    """
    message = "Email verification is required to access this service. Please verify your email with the OTP sent to you."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_staff or request.user.is_superuser or getattr(request.user, 'role', '') == 'admin':
            return True
        return bool(request.user.is_verified)
