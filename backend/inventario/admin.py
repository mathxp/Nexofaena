from django.contrib import admin
from .models import *

# ======================
# MODELOS BÁSICOS
# ======================
admin.site.register(Categoria)   # Categorías de insumos
admin.site.register(Area)        # Áreas del hospital
admin.site.register(Proveedor)   # Proveedores

# ======================
# INVENTARIO
# ======================
admin.site.register(Insumo)      # Insumos del sistema
admin.site.register(Lote)        # Lotes de insumos

# ======================
# COMPRAS
# ======================
admin.site.register(Compra)          # Compra principal
admin.site.register(DetalleCompra)   # Detalle de cada compra

# ======================
# MOVIMIENTOS
# ======================
admin.site.register(Movimiento)  # Entradas y salidas de stock
admin.site.register(Consumo)     # Consumo registrado

# ======================
# ANALÍTICA
# ======================
admin.site.register(Prediccion)  # Predicciones de consumo
admin.site.register(Alerta)      # Alertas del sistema