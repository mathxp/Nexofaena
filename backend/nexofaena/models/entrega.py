from django.db import models
from .trabajador import Trabajador
from .usuario import Usuario
from .bodega import Bodega
from .inventario import Inventario  # Importamos Inventario en lugar de EPP directo

class EntregaEPP(models.Model):
    id = models.BigAutoField(primary_key=True)
    """
    Representa la cabecera de una entrega. 
    Ahora incluye la Bodega para soportar múltiples puntos de despacho.
    """
    ESTADOS_ENTREGA = (
        ('PENDIENTE', 'Pendiente'),
        ('COMPLETADA', 'Completada'),
        ('ANULADA', 'Anulada'),
    )

    trabajador = models.ForeignKey(Trabajador, on_delete=models.PROTECT, related_name="entregas_epp", verbose_name="Trabajador")
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="entregas_registradas", verbose_name="Bodeguero/Supervisor")
    bodega = models.ForeignKey(Bodega, on_delete=models.PROTECT, related_name="entregas", verbose_name="Bodega de Origen")
    
    fecha_entrega = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Entrega")
    observacion = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    firma_base64 = models.TextField(blank=True, null=True, verbose_name="Firma Digital")
    estado = models.CharField(max_length=20, choices=ESTADOS_ENTREGA, default='PENDIENTE', verbose_name="Estado")

    class Meta:
        db_table = "entrega_epp"
        verbose_name = "Entrega EPP"
        verbose_name_plural = "Entregas EPP"
        indexes = [models.Index(fields=['fecha_entrega', 'estado'])]

    def __str__(self):
        return f"Entrega #{self.id} - {self.trabajador.rut} ({self.bodega.nombre})"


class DetalleEntregaEPP(models.Model):
    id = models.BigAutoField(primary_key=True)
    """
    Detalle de los productos entregados.
    Vinculado directamente a 'Inventario' para afectar el stock de la bodega correcta.
    """
    entrega = models.ForeignKey(EntregaEPP, on_delete=models.CASCADE, related_name="detalles")
    inventario = models.ForeignKey(Inventario, on_delete=models.PROTECT, verbose_name="Producto en Inventario")
    
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad Entregada")
    talla = models.CharField(max_length=20, blank=True, null=True, verbose_name="Talla")
    observacion = models.TextField(blank=True, null=True, verbose_name="Observaciones del Ítem")

    class Meta:
        db_table = "detalle_entrega_epp"
        verbose_name = "Detalle Entrega EPP"
        verbose_name_plural = "Detalles Entrega EPP"

    def __str__(self):
        return f"{self.cantidad} x {self.inventario.nombre}"