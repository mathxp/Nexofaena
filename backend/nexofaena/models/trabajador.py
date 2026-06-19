from django.db import models


class Trabajador(models.Model):
    rut = models.CharField(max_length=12, unique=True)

    nombres = models.CharField(max_length=100)

    apellido_paterno = models.CharField(max_length=100)

    apellido_materno = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    cargo = models.CharField(max_length=100)

    telefono = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    correo = models.EmailField(
        blank=True,
        null=True
    )

    activo = models.BooleanField(default=True)

    fecha_ingreso = models.DateField(
        blank=True,
        null=True
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "trabajadores"
        verbose_name = "Trabajador"
        verbose_name_plural = "Trabajadores"

    def __str__(self):
        return f"{self.nombres} {self.apellido_paterno}"