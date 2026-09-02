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

    # Control de vida útil y devolución (Regla Minera Teck / Activos Diarios)
    vida_util_dias = models.PositiveIntegerField(
        blank=True, null=True,
        verbose_name="Vida Útil (días)",
        help_text="Días de uso permitidos antes de exigir recambio (ej. 365 para cascos/zapatos). Vacío = sin control de vencimiento."
    )
    es_devolutivo = models.BooleanField(
        default=False,
        verbose_name="¿Es un activo devolutivo?",
        help_text="Ej. radios de comunicación: se entregan al inicio del turno y deben devolverse al final."
    )
    tiempo_reposicion_dias = models.PositiveIntegerField(
        default=7,
        verbose_name="Tiempo de Reposición (días)",
        help_text="Días estimados que demora el proveedor en reponer stock una vez generado el pedido."
    )
    es_activo_critico = models.BooleanField(
        default=False,
        verbose_name="¿Activo crítico / de alto valor?",
        help_text="Si un conteo cíclico detecta faltante en este producto, se exige firma de autorización de un supervisor para ajustar el stock."
    )
    es_despacho_rapido = models.BooleanField(
        default=False,
        verbose_name="¿Despacho rápido?",
        help_text="Consumibles de alta rotación (ej. agua) que se descuentan con un clic, sin RUT ni firma, y quedan fuera de las alertas de anomalía de consumo."
    )

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