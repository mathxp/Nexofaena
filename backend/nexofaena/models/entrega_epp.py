from django.db import models
from .trabajador import Trabajador
from .usuario import Usuario
from .epp import EPP

class EntregaEPP(models.Model):
    ESTADOS_ENTREGA = (
        ('PENDIENTE', 'Pendiente'),
        ('COMPLETADA', 'Completada'),
        ('ANULADA', 'Anulada'),
    )

    trabajador = models.ForeignKey(Trabajador, on_delete=models.PROTECT, related_name="entregas_epp")
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="entregas_registradas")
    
    fecha_entrega = models.DateTimeField(auto_now_add=True)
    observacion = models.TextField(blank=True, null=True)
    firma_base64 = models.TextField(blank=True, null=True) # Aquí guardaremos la firma digital
    estado = models.CharField(max_length=20, choices=ESTADOS_ENTREGA, default='PENDIENTE')

    class Meta:
        db_table = "entrega_epp"
        verbose_name = "Entrega EPP"
        verbose_name_plural = "Entregas EPP"

    def __str__(self):
        return f"Entrega #{self.id} - {self.trabajador.rut}"


class DetalleEntregaEPP(models.Model):
    entrega = models.ForeignKey(EntregaEPP, on_delete=models.CASCADE, related_name="detalles")
    epp = models.ForeignKey(EPP, on_delete=models.PROTECT)
    
    cantidad = models.DecimalField(max_digits=12, decimal_places=2)
    talla = models.CharField(max_length=20, blank=True, null=True)
    observacion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "detalle_entrega_epp"
        verbose_name = "Detalle Entrega EPP"
        verbose_name_plural = "Detalles Entrega EPP"

    def __str__(self):
        return f"{self.cantidad} x {self.epp.nombre}"