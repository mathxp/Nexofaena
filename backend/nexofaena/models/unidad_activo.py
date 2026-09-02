from django.db import models
from .inventario import Inventario


class UnidadActivo(models.Model):
    """
    Unidad física individual y serializada de un producto devolutivo
    (ej. cada radio de comunicación por separado: RADIO-S001, RADIO-S002...).

    Permite saber exactamente qué unidad se entregó a quién y controlar su
    devolución una por una, en vez de manejar solo una cantidad agregada.
    """

    ESTADOS_UNIDAD = (
        ('DISPONIBLE', 'Disponible en bodega'),
        ('ENTREGADA', 'Entregada'),
        ('EN_MANTENCION', 'En mantención'),
        ('DE_BAJA', 'De baja'),
    )

    inventario = models.ForeignKey(
        Inventario,
        on_delete=models.PROTECT,
        related_name="unidades",
        verbose_name="Producto"
    )
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código de Unidad")
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_UNIDAD,
        default='DISPONIBLE',
        verbose_name="Estado",
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Alta")

    class Meta:
        db_table = "unidad_activo"
        verbose_name = "Unidad de Activo"
        verbose_name_plural = "Unidades de Activo"
        ordering = ["codigo"]
        indexes = [models.Index(fields=['inventario', 'estado'])]

    def __str__(self):
        return f"{self.codigo} ({self.get_estado_display()})"
