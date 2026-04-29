from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ======================
# CATEGORÍAS Y ÁREAS
# ======================

class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()

    def __str__(self):
        return self.nombre


class Area(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()

    def __str__(self):
        return self.nombre


# ======================
# PROVEEDORES
# ======================

class Proveedor(models.Model):
    nombre = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20)
    correo = models.EmailField()
    direccion = models.CharField(max_length=200)

    def __str__(self):
        return self.nombre


# ======================
# INSUMOS
# ======================

class Insumo(models.Model):
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField()
    unidad_medida = models.CharField(max_length=50)

    stock_minimo = models.IntegerField(default=0)
    stock_actual = models.IntegerField(default=0)  # ⚠️ cache (no fuente real)

    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    area = models.ForeignKey(Area, on_delete=models.CASCADE)

    def __str__(self):
        return self.nombre


# ======================
# COMPRAS
# ======================

class Compra(models.Model):
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, null=True, blank=True)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)

    fecha = models.DateField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # 📎 Comprobante (PDF, imagen, etc.)
    comprobante = models.FileField(
        upload_to='comprobantes/',
        null=True,
        blank=True
    )

    def __str__(self):
        return f"Compra #{self.id}"


class DetalleCompra(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE)
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)

    cantidad = models.IntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.insumo.nombre} x {self.cantidad}"


# ======================
# LOTES (FEFO)
# ======================

class Lote(models.Model):
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    numero_lote = models.CharField(max_length=100)

    cantidad = models.IntegerField()
    fecha_vencimiento = models.DateField()

    # 🔴 Validaciones de vencimiento
    def esta_vencido(self):
        return self.fecha_vencimiento < timezone.now().date()

    def dias_para_vencer(self):
        return (self.fecha_vencimiento - timezone.now().date()).days

    def __str__(self):
        return f"{self.insumo.nombre} - {self.numero_lote}"


# ======================
# CONSUMO
# ======================

class Consumo(models.Model):
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)

    cantidad = models.IntegerField()
    fecha = models.DateField()

    def __str__(self):
        return f"Consumo {self.insumo.nombre}"


# ======================
# PREDICCIÓN
# ======================

class Prediccion(models.Model):
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)

    consumo_estimado = models.IntegerField()
    fecha = models.DateField(auto_now_add=True)

    # 📊 Datos calculados
    stock_actual = models.FloatField(null=True, blank=True)
    dias_restantes = models.FloatField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)
    accion = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"Predicción {self.insumo.nombre}"


# ======================
# ALERTAS
# ======================

class Alerta(models.Model):
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=50)
    mensaje = models.TextField()

    class Meta:
        unique_together = ['insumo', 'tipo']  # 🔒 evita duplicados

    def __str__(self):
        return f"{self.tipo} - {self.insumo.nombre}"


# ======================
# MOVIMIENTOS (AUDITORÍA)
# ======================

class Movimiento(models.Model):

    TIPO_CHOICES = [
        ('entrada', 'Entrada'),
        ('salida', 'Salida'),
    ]

    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    cantidad = models.IntegerField()

    fecha = models.DateTimeField(auto_now_add=True)

    # 🔗 Relación con lote (opcional)
    lote = models.ForeignKey(
        Lote,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.tipo} - {self.insumo.nombre} ({self.cantidad})"

    # ⚠️ Validación básica
    def clean(self):
        if self.tipo == 'salida' and self.cantidad <= 0:
            raise ValueError("Cantidad inválida para salida")