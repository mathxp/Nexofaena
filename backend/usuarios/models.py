# ======================
# DJANGO IMPORTS
# ======================
from django.db import models
from django.contrib.auth.models import User, Group
from django.db.models.signals import post_save
from django.dispatch import receiver

# ======================
# MODELOS INTERNOS
# ======================
from inventario.models import Area


# =========================================================
# 📌 MODELO: PERFIL DE USUARIO
# =========================================================
class Perfil(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='perfil'
    )

    area = models.ForeignKey(
        Area,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    telefono = models.CharField(max_length=20, blank=True)
    rut = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.user.username


# =========================================================
# 🔥 SIGNAL: CREAR PERFIL AUTOMÁTICO
# =========================================================
@receiver(post_save, sender=User)
def crear_perfil(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(user=instance)


# =========================================================
# 🔥 SIGNAL: GUARDAR PERFIL
# =========================================================
@receiver(post_save, sender=User)
def guardar_perfil(sender, instance, **kwargs):
    # asegura que el perfil se sincronice con el usuario
    if hasattr(instance, 'perfil'):
        instance.perfil.save()


# =========================================================
# 🔥 SIGNAL: ASIGNAR ROL Y PERMISOS AUTOMÁTICOS
# =========================================================
@receiver(post_save, sender=User)
def asignar_permisos(sender, instance, created, **kwargs):

    if created:

        grupo = instance.groups.first()

        if grupo:

            if grupo.name == "Administrador":
                instance.is_staff = True
                instance.is_superuser = True

            elif grupo.name == "Bodega":
                instance.is_staff = True
                instance.is_superuser = False

            elif grupo.name == "Clinico":
                instance.is_staff = False
                instance.is_superuser = False

            instance.save()