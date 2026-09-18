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
                "Encargado de Bodega",
            ]
        )


class IsEncargadoBodega(BasePermission):
    """
    Para las acciones que el pañol real de RentaMaq exige reservar al
    Encargado de Bodega (o Administrador): ajustar stock según auditoría,
    cerrar/anular auditorías, y autorizar traspasos entre bodegas. Un
    Bodeguero o Supervisor no debe poder ejecutar estas acciones.
    """
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and hasattr(request.user, "rol")
            and request.user.rol.nombre in [
                "Administrador",
                "Encargado de Bodega",
            ]
        )