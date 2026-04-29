# ======================
# DJANGO MODELS IMPORTS
# ======================
from django.db import models
from django.contrib.auth.models import User

# ======================
# MODELOS INTERNOS
# ======================
from inventario.models import Insumo


# =========================================================
# 📌 MODELO: SOLICITUD (CABECERA)
# =========================================================
class Solicitud(models.Model):

    # ======================
    # ESTADOS DE SOLICITUD
    # ======================
    ESTADOS = (
        ('pendiente', 'Pendiente'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
    )

    # ======================
    # RELACIONES
    # ======================
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    area = models.ForeignKey('inventario.Area', on_delete=models.CASCADE)

    # ======================
    # CAMPOS PRINCIPALES
    # ======================
    fecha = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='pendiente'
    )

    observacion = models.TextField(blank=True, null=True)

    # ======================
    # REPRESENTACIÓN TEXTO
    # ======================
    def __str__(self):
        return f"Solicitud #{self.id} - {self.area} - {self.estado}"


# =========================================================
# 📌 MODELO: DETALLE SOLICITUD
# =========================================================
class DetalleSolicitud(models.Model):

    # ======================
    # RELACIONES
    # ======================
    solicitud = models.ForeignKey(
        Solicitud,
        on_delete=models.CASCADE,
        related_name='detalles'
    )

    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)

    # ======================
    # CAMPOS
    # ======================
    cantidad = models.PositiveIntegerField()

    # ======================
    # REPRESENTACIÓN TEXTO
    # ======================
    def __str__(self):
        return f"{self.insumo.nombre} x {self.cantidad}"