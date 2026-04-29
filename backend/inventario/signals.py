# inventario/signals.py

from django.db.models.signals import post_migrate
from django.contrib.auth.models import Group
from django.dispatch import receiver


# =====================================================
# 🔐 CREACIÓN AUTOMÁTICA DE ROLES
# =====================================================

@receiver(post_migrate)
def crear_roles(sender, **kwargs):
    """
    Se ejecuta después de migraciones.
    Crea los grupos (roles) base del sistema si no existen.
    """

    roles = [
        "Administrador",
        "Bodeguero",
        "Médico",
        "Enfermero",
    ]

    for rol in roles:
        Group.objects.get_or_create(name=rol)