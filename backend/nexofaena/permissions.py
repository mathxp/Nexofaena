from rest_framework.permissions import BasePermission


class IsAdministrador(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and hasattr(request.user, "rol")
            and request.user.rol.nombre == "Administrador"
        )


class IsSupervisor(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and hasattr(request.user, "rol")
            and request.user.rol.nombre in [
                "Administrador",
                "Supervisor",
            ]
        )


class IsBodeguero(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and hasattr(request.user, "rol")
            and request.user.rol.nombre in [
                "Administrador",
                "Supervisor",
                "Bodeguero",
            ]
        )