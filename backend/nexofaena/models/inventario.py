from django.db import models
from .bodega import Bodega
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

    # Identificación y Catálogo
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código SKU")
    nombre = models.CharField(max_length=150, verbose_name="Nombre del Producto")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción técnica")
    
    marca = models.CharField(max_length=100, blank=True, null=True, verbose_name="Marca")
    modelo = models.CharField(max_length=100, blank=True, null=True, verbose_name="Modelo")
    unidad_medida = models.CharField(max_length=20, default="UN", verbose_name="Unidad de Medida")

    # Variante de producto (ej. Guantes anticorte talla M/L/XL): mismo `nombre`,
    # `talla` distinta, cada una con su propio stock y código. Evita crear
    # productos separados tipo "Guantes L" que rompen el agrupamiento por nombre.
    talla = models.CharField(
        max_length=20, blank=True, null=True, verbose_name="Talla",
        help_text="Solo para productos con variantes de talla (guantes, buzos, zapatos). Vacío si no aplica.",
    )

    # Control de Stock (DecimalField para precisión contable)
    stock_actual = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'), verbose_name="Stock Actual")
    stock_minimo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'), verbose_name="Stock Mínimo")
    stock_maximo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'), verbose_name="Stock Máximo")

    # Valorización (seguimiento del dinero entregado por pañol)
    precio_unitario = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name="Precio Unitario (CLP)",
        help_text="Precio real de costo/reposición por unidad. Se usa para valorizar el stock y las entregas de pañol.",
    )

    # Metodología 5S (filtro de clasificación de bodega)
    CLASIFICACIONES_5S = (
        ('SEIRI', 'Seiri - Clasificar'),
        ('SEITON', 'Seiton - Ordenar'),
        ('SEISO', 'Seiso - Limpiar'),
        ('SEIKETSU', 'Seiketsu - Estandarizar'),
        ('SHITSUKE', 'Shitsuke - Disciplina'),
    )
    clasificacion_5s = models.CharField(
        max_length=20, choices=CLASIFICACIONES_5S, blank=True, null=True,
        verbose_name="Clasificación 5S",
        help_text="Etapa de la metodología 5S asignada a este ítem/ubicación, usada como filtro de inventario.",
    )


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

    @property
    def valor_stock(self):
        """Valorización del stock actual al precio unitario vigente (seguimiento de dinero)."""
        return self.stock_actual * self.precio_unitario