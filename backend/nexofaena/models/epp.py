from django.db import models

class EPP(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=150)
    categoria = models.CharField(max_length=100, blank=True, null=True)
    unidad_medida = models.CharField(max_length=20)
    
    stock_minimo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_actual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    estado = models.BooleanField(default=True)

    class Meta:
        db_table = "epp"
        verbose_name = "EPP"
        verbose_name_plural = "EPPs"

    def __str__(self):
        return f"[{self.codigo}] {self.nombre}"