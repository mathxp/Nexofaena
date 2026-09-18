from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from .trabajador import Trabajador
from .usuario import Usuario
from .bodega import Bodega
from .inventario import Inventario  # Importamos Inventario en lugar de EPP directo
from .unidad_activo import UnidadActivo

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

    # Geolocalización inmutable de auditoría (SERNAC/SERNATUR/MINSAL/Mandante):
    # coordenadas capturadas en el dispositivo al momento del acto de entrega,
    # no al momento de sincronizar. Por eso van junto con
    # geolocalizacion_capturada_en, que puede ser muy anterior a fecha_entrega
    # cuando la entrega se registró offline y se sincronizó más tarde.
    latitud = models.DecimalField(
        max_digits=10, decimal_places=7, blank=True, null=True, verbose_name="Latitud"
    )
    longitud = models.DecimalField(
        max_digits=10, decimal_places=7, blank=True, null=True, verbose_name="Longitud"
    )
    precision_metros = models.FloatField(
        blank=True, null=True, verbose_name="Precisión GPS (m)",
        help_text="Radio de incertidumbre reportado por el dispositivo (GPSPosition.coords.accuracy).",
    )
    geolocalizacion_capturada_en = models.DateTimeField(
        blank=True, null=True, verbose_name="Geolocalización capturada en",
        help_text="Momento real de la captura GPS en el dispositivo (distinto de fecha_entrega si la entrega se sincronizó después, en modo offline).",
    )

    # Radiografía de consumo por turno (reporte EPP por trabajador/turno):
    # se deriva solo de la hora de entrega, no exige capturar nada nuevo.
    TURNOS = (
        ('dia', 'Día'),
        ('noche', 'Noche'),
    )
    turno = models.CharField(
        max_length=10, choices=TURNOS, blank=True, editable=False,
        verbose_name="Turno",
        help_text="Calculado automáticamente desde la hora de entrega (umbral configurable en settings).",
    )

    class Meta:
        db_table = "entrega_epp"
        verbose_name = "Entrega EPP"
        verbose_name_plural = "Entregas EPP"
        indexes = [
            models.Index(fields=['fecha_entrega', 'estado']),
            models.Index(fields=['turno']),
        ]

    def __str__(self):
        return f"Entrega #{self.id} - {self.trabajador.rut} ({self.bodega.nombre})"

    @staticmethod
    def calcular_turno(momento):
        """Deriva 'dia'/'noche' desde la hora local de entrega, según el
        umbral configurable en settings (TURNO_HORA_INICIO_DIA/_NOCHE)."""
        hora = timezone.localtime(momento).hour if timezone.is_aware(momento) else momento.hour
        hora_inicio_dia = getattr(settings, "TURNO_HORA_INICIO_DIA", 8)
        hora_inicio_noche = getattr(settings, "TURNO_HORA_INICIO_NOCHE", 20)

        if hora_inicio_dia <= hora < hora_inicio_noche:
            return 'dia'
        return 'noche'

    def save(self, *args, **kwargs):
        if not self.turno:
            # fecha_entrega es auto_now_add: en la creación aún no tiene valor
            # propio en memoria, así que se usa el mismo reloj que usará el ORM.
            self.turno = self.calcular_turno(self.fecha_entrega or timezone.now())

        super().save(*args, **kwargs)


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

    # Precio congelado al momento de la entrega (independiente de cambios futuros
    # en Inventario.precio_unitario), para un seguimiento fiel del dinero entregado.
    precio_unitario = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name="Precio Unitario al Entregar (CLP)",
    )

    # Regla Minera Teck: caducidad de EPP críticos (cascos, zapatos, etc.)
    fecha_vencimiento_vida_util = models.DateField(
        blank=True, null=True,
        verbose_name="Vencimiento vida útil",
        help_text="Calculado automáticamente al entregar según la vida útil del producto."
    )

    # Módulo de Devoluciones: activos diarios (radios, etc.)
    ESTADOS_DEVOLUCION = (
        ('OPERATIVA', 'Operativa'),
        ('DAÑADA', 'Dañada'),
    )

    devuelto = models.BooleanField(default=False, verbose_name="¿Devuelto?")
    fecha_devolucion = models.DateTimeField(blank=True, null=True, verbose_name="Fecha de Devolución")
    estado_devolucion = models.CharField(
        max_length=20,
        choices=ESTADOS_DEVOLUCION,
        blank=True, null=True,
        verbose_name="Estado al Devolver",
        help_text="Condición reportada por el pañolero al recibir de vuelta el activo devolutivo.",
    )

    # Trazabilidad individual: qué unidad física específica se entregó
    # (obligatorio para productos devolutivos, ej. RADIO-S001).
    unidad_activo = models.ForeignKey(
        UnidadActivo,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name="entregas_detalle",
        verbose_name="Unidad Entregada",
    )

    class Meta:
        db_table = "detalle_entrega_epp"
        verbose_name = "Detalle Entrega EPP"
        verbose_name_plural = "Detalles Entrega EPP"

    def __str__(self):
        return f"{self.cantidad} x {self.inventario.nombre}"

    @property
    def subtotal(self):
        """Valor en dinero de este ítem entregado (cantidad x precio congelado)."""
        return self.cantidad * self.precio_unitario