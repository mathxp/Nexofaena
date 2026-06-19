from django.db import models
from .bodega import Bodega

class Inventario(models.Model):
    # Relacionado con la tabla Bodega
    bodega = models.ForeignKey(Bodega, on_delete=models.PROTECT, related_name="inventarios")
    
    # Nota: Omití id_categoria temporalmente para no causar otro error si no tienes ese modelo creado aún.
    
    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    unidad_medida = models.CharField(max_length=20)
    
    # NUMERIC(12,2) en tu MER equivale a DecimalField en Django
    stock_minimo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_actual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    estado = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventario"
        verbose_name = "Inventario"
        verbose_name_plural = "Inventarios"

    def __str__(self):
        return f"[{self.codigo}] {self.nombre}"