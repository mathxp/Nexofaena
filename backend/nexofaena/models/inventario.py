from django.db import models
from .bodega import Bodega
# Descomenta esta línea cuando crees el modelo en models/categoria_producto.py
# from .categoria_producto import CategoriaProducto 
from decimal import Decimal
class Inventario(models.Model):
    """
    Modelo de Inventario centralizado.
    Gestiona el stock por bodega con trazabilidad de ubicación física y niveles de alerta.
    """
    # Relaciones base
    bodega = models.ForeignKey(
        Bodega, 
        on_delete=models.PROTECT, 
        related_name="inventarios",
        verbose_name="Bodega"
    )
    
    # Categorización (Prepárado para el modelo CategoriaProducto)
    # categoria = models.ForeignKey(
    #     CategoriaProducto, 
    #     on_delete=models.SET_NULL, 
    #     null=True, 
    #     blank=True,
    #     verbose_name="Categoría"
    # )

    # Identificación y Catálogo
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código SKU")
    nombre = models.CharField(max_length=150, verbose_name="Nombre del Producto")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción técnica")
    
    marca = models.CharField(max_length=100, blank=True, null=True, verbose_name="Marca")
    modelo = models.CharField(max_length=100, blank=True, null=True, verbose_name="Modelo")
    unidad_medida = models.CharField(max_length=20, default="UN", verbose_name="Unidad de Medida")

    # Control de Stock (DecimalField para precisión contable)
    stock_actual = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'), verbose_name="Stock Actual")
    stock_minimo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'), verbose_name="Stock Mínimo")
    stock_maximo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'), verbose_name="Stock Máximo")


    # Ubicación Física
    ubicacion = models.CharField(max_length=100, blank=True, null=True, verbose_name="Ubicación Física (Rack/Pasillo)")

    # Auditoría y Estado
    estado = models.BooleanField(default=True, verbose_name="¿Activo?")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    class Meta:
        db_table = "inventario"
        verbose_name = "Inventario"
        verbose_name_plural = "Inventarios"
        indexes = [
            models.Index(fields=['codigo', 'nombre']),
            models.Index(fields=['bodega']),
            models.Index(fields=['estado']),
        ]

    def __str__(self):
        return f"[{self.codigo}] {self.nombre} - {self.bodega.nombre}"

    @property
    def necesita_reposicion(self):
        """Lógica de negocio: Retorna True si el stock actual está en o por debajo del mínimo."""
        return self.stock_actual <= self.stock_minimo

    @property
    def exceso_stock(self):
        """Lógica de negocio: Retorna True si supera el stock máximo definido."""
        return self.stock_maximo > 0 and self.stock_actual > self.stock_maximo