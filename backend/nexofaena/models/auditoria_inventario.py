from django.db import models

from .bodega import Bodega
from .inventario import Inventario
from .usuario import Usuario


class AuditoriaInventario(models.Model):
    id = models.BigAutoField(primary_key=True)

    ESTADOS = (
        ("ABIERTA", "Abierta"),
        ("CERRADA", "Cerrada"),
        ("ANULADA", "Anulada"),
    )

    bodega = models.ForeignKey(
        Bodega,
        on_delete=models.PROTECT,
        related_name="auditorias_inventario",
    )

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name="auditorias_inventario",
    )

    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_cierre = models.DateTimeField(blank=True, null=True)

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="ABIERTA",
    )

    observacion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "auditoria_inventario"
        ordering = ["-fecha_inicio"]

    def __str__(self):
        return f"Auditoría #{self.pk} - {self.bodega.nombre}"


class DetalleAuditoriaInventario(models.Model):
    id = models.BigAutoField(primary_key=True)

    auditoria = models.ForeignKey(
        AuditoriaInventario,
        on_delete=models.CASCADE,
        related_name="detalles",
    )

    inventario = models.ForeignKey(
        Inventario,
        on_delete=models.PROTECT,
    )

    stock_sistema = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    stock_fisico = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    diferencia = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    observacion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "detalle_auditoria_inventario"

    def __str__(self):
        return f"{self.inventario.nombre} | Dif: {self.diferencia}"