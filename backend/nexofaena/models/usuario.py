from django.contrib.auth.models import AbstractUser
from django.db import models

from .rol import Rol


class Usuario(AbstractUser):

    rut = models.CharField(
        max_length=12,
        unique=True
    )

    rol = models.ForeignKey(
        Rol,
        on_delete=models.PROTECT,
        related_name="usuarios"
    )

    telefono = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    # Agregamos esta lista para que createsuperuser los pida por consola
    REQUIRED_FIELDS = ['rut', 'rol_id']

    class Meta:
        db_table = "usuarios"

    def __str__(self):
        return self.username