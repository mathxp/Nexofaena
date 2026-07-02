import uuid
from django.db import models
from django.utils import timezone


class InvitacionRegistro(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    correo = models.EmailField(blank=True, null=True)
    usado = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_expiracion = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "invitacion_registro"
        verbose_name = "Invitación de Registro"
        verbose_name_plural = "Invitaciones de Registro"

    def esta_vigente(self):
        if self.usado:
            return False

        if self.fecha_expiracion and timezone.now() > self.fecha_expiracion:
            return False

        return True

    def __str__(self):
        return str(self.token)