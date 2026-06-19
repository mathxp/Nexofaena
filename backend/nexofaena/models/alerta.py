from django.db import models
from .inventario import Inventario
from .bodega import Bodega

class Alerta(models.Model):
    TIPOS_ALERTA = (
        ('STOCK_BAJO', 'Stock Bajo'),
        ('STOCK_CRITICO', 'Stock Crítico'),
        ('VENCIMIENTO_EPP', 'Vencimiento EPP'),
        ('SISTEMA', 'Sistema'),
    )

    # Pueden ser nulos porque una alerta podría ser general del sistema, no solo de un producto
    inventario = models.ForeignKey(Inventario, on_delete=models.CASCADE, null=True, blank=True)
    bodega = models.ForeignKey(Bodega, on_delete=models.CASCADE, null=True, blank=True)
    
    tipo_alerta = models.CharField(max_length=50, choices=TIPOS_ALERTA)
    mensaje = models.TextField()
    fecha_alerta = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False) # Para saber si el admin ya revisó la alerta

    class Meta:
        db_table = "alerta"
        verbose_name = "Alerta"
        verbose_name_plural = "Alertas"

    def __str__(self):
        return f"[{self.tipo_alerta}] {self.mensaje}"