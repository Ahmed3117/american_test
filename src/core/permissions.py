from rest_framework.permissions import BasePermission, DjangoModelPermissions, IsAdminUser
from rest_framework_api_key.permissions import HasAPIKey


class CustomDjangoModelPermissions(DjangoModelPermissions):
    def has_permission(self, request, view):
        if request.user and request.user.is_staff:
            return True
        return super().has_permission(request, view)


class IsSuperUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)


class HasValidAPIKey(HasAPIKey):
    pass


DashboardStaffPermission = IsAdminUser
