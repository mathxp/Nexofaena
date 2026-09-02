from django.db import models

from .inventario import Inventario
from .bodega import Bodega
from .entrega import DetalleEntregaEPP


class TipoAlerta(models.TextChoices):
    STOCK_BAJO = "STOCK_BAJO", "Stock Bajo"
    STOCK_CRITICO = "STOCK_CRITICO", "Stock Crítico"
    VENCIMIENTO = "VENCIMIENTO", "Vencimiento"
    ANOMALIA_CONSUMO = "ANOMALIA_CONSUMO", "Anomalía de Consumo"
    MANTENIMIENTO = "MANTENIMIENTO", "Mantenimiento"
    CIERRE_TURNO = "CIERRE_TURNO", "Cierre de Turno"
    SISTEMA = "SISTEMA", "Sistema"


class Alerta(models.Model):
    inventario = models.ForeignKey(
        Inventario,
        on_delete=models.CASCADE,
        related_name="alertas",
        null=True,
        blank=True,
        verbose_name="Producto"
    )

    detalle_entrega = models.ForeignKey(
        DetalleEntregaEPP,
        on_delete=models.CASCADE,
        related_name="alertas",
        null=True,
        blank=True,
        verbose_name="Entrega Asociada",
        help_text="Vincula la alerta de vencimiento con la entrega específica que la originó."
    )

    bodega = models.ForeignKey(
        Bodega,
        on_delete=models.CASCADE,
        related_name="alertas",
        null=True,
        blank=True,
        verbose_name="Bodega"
    )

    tipo_alerta = models.CharField(
        max_length=30,
        choices=TipoAlerta.choices,
        default=TipoAlerta.SISTEMA,
        db_index=True,
        verbose_name="Tipo de alerta"
    )

    mensaje = models.TextField(
        verbose_name="Mensaje"
    )

    leida = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Leída"
    )

    fecha_alerta = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Fecha"
    )

    class Meta:
        db_table = "alerta"
        ordering = ["-fecha_alerta"]
        verbose_name = "Alerta"
        verbose_name_plural = "Alertas"

    def __str__(self):
        nombre_producto = (
            self.inventario.nombre
            if self.inventario
            else "Sistema"
        )

        return f"{self.tipo_alerta} - {nombre_producto}"