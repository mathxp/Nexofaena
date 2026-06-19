from django.db import models
from .bodega import Bodega
from .inventario import Inventario
from .usuario import Usuario

class MovimientoInventario(models.Model):
    TIPOS_MOVIMIENTO = (
        ('INGRESO', 'Ingreso'),
        ('SALIDA', 'Salida'),
        ('AJUSTE', 'Ajuste'),
    )

    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="movimientos")
    bodega = models.ForeignKey(Bodega, on_delete=models.PROTECT)
    inventario = models.ForeignKey(Inventario, on_delete=models.PROTECT)
    
    tipo_movimiento = models.CharField(max_length=20, choices=TIPOS_MOVIMIENTO)
    cantidad = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateTimeField(auto_now_add=True)
    observacion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "movimiento_inventario"
        verbose_name = "Movimiento de Inventario"
        verbose_name_plural = "Movimientos de Inventario"

    def __str__(self):
        return f"{self.tipo_movimiento} - {self.inventario.nombre} ({self.cantidad})"