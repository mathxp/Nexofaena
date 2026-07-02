from django.db import models
from .bodega import Bodega
from .inventario import Inventario
from .usuario import Usuario
from .trabajador import Trabajador # Necesario para trazar quién recibió el EPP
from .entrega import EntregaEPP # Para vincular salidas automáticas

class MovimientoInventario(models.Model):
    """
    Registro inmutable de cada cambio en el stock.
    Cada instancia es una foto del estado de la bodega en ese instante.
    """
    TIPOS_MOVIMIENTO = (
        ('INGRESO', 'Ingreso'),
        ('SALIDA', 'Salida'),
        ('AJUSTE', 'Ajuste'),
    )

    # Relaciones obligatorias
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="movimientos", verbose_name="Responsable")
    bodega = models.ForeignKey(Bodega, on_delete=models.PROTECT, verbose_name="Bodega")
    inventario = models.ForeignKey(Inventario, on_delete=models.PROTECT, verbose_name="Producto")
    
    # Vinculación opcional con entregas (Solo para SALIDAS automáticas)
    entrega = models.ForeignKey(
        EntregaEPP, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="movimientos",
        verbose_name="Entrega Asociada"
    )
    
    # Vinculación opcional con trabajador (Para salidas)
    trabajador = models.ForeignKey(
        Trabajador, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Trabajador Recibió"
    )

    tipo_movimiento = models.CharField(max_length=20, choices=TIPOS_MOVIMIENTO, verbose_name="Tipo")
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad")
    
    # Campos de trazabilidad (Cruciales para auditoría)
    stock_anterior = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Stock Antes")
    stock_actual = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Stock Después")
    
    fecha = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora")
    observacion = models.TextField(blank=True, null=True, verbose_name="Observación")

    class Meta:
        db_table = "movimiento_inventario"
        verbose_name = "Movimiento de Inventario"
        verbose_name_plural = "Movimientos de Inventario"
        ordering = ['-fecha'] # Siempre ver los últimos movimientos primero
        indexes = [
            models.Index(fields=['fecha', 'tipo_movimiento']),
            models.Index(fields=['inventario', 'bodega']),
        ]

    def __str__(self):
        return f"{self.tipo_movimiento} | {self.inventario.nombre} | {self.cantidad} unidades"