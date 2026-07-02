from django.db import models


class Bodega(models.Model):
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre"
    )

    ubicacion = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Ubicación"
    )

    responsable = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Responsable"
    )

    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descripción"
    )

    telefono = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Teléfono"
    )

    estado = models.BooleanField(
        default=True,
        verbose_name="Activa"
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True
    )

    fecha_actualizacion = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        db_table = "bodega"
        ordering = ["nombre"]
        verbose_name = "Bodega"
        verbose_name_plural = "Bodegas"

    def __str__(self):
        return self.nombre