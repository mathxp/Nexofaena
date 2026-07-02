from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone

from nexofaena.models.trabajador import Trabajador
from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario
from nexofaena.models.entrega import EntregaEPP
from nexofaena.models.alerta import Alerta


class DashboardService:

    @staticmethod
    def obtener_dashboard():
        return {
            "kpis": DashboardService.obtener_kpis(),
            "entregas_mensuales": DashboardService.obtener_entregas_mensuales(),
            "top_productos": DashboardService.obtener_top_productos(),
            "consumo_bodega": DashboardService.obtener_consumo_por_bodega(),
            "alertas": DashboardService.obtener_alertas(),
            "stock_estado": DashboardService.obtener_stock_estado(),
        }

    @staticmethod
    def obtener_kpis():
        inicio_mes = timezone.now().replace(day=1)

        productos_activos = Inventario.objects.filter(estado=True)

        productos_criticos = sum(
            1 for producto in productos_activos
            if producto.stock_actual < producto.stock_minimo
        )

        productos_bajo_minimo = sum(
            1 for producto in productos_activos
            if producto.stock_actual <= producto.stock_minimo
        )

        productos_sobre_stock = sum(
            1 for producto in productos_activos
            if producto.stock_maximo > 0 and producto.stock_actual > producto.stock_maximo
        )

        return {
            "trabajadores_activos": Trabajador.objects.filter(activo=True).count(),
            "productos_inventariados": productos_activos.count(),
            "stock_total": float(
                productos_activos.aggregate(total=Sum("stock_actual"))["total"] or 0
            ),
            "salidas_mes": float(
                MovimientoInventario.objects.filter(
                    tipo_movimiento="SALIDA",
                    fecha__gte=inicio_mes,
                ).aggregate(total=Sum("cantidad"))["total"] or 0
            ),
            "alertas_activas": Alerta.objects.filter(leida=False).count(),
            "productos_criticos": productos_criticos,
            "productos_bajo_minimo": productos_bajo_minimo,
            "productos_sobre_stock": productos_sobre_stock,
        }

    @staticmethod
    def obtener_consumo_por_bodega():
        qs = (
            MovimientoInventario.objects.filter(tipo_movimiento="SALIDA")
            .values("bodega__nombre")
            .annotate(total=Sum("cantidad"))
            .order_by("-total")
        )

        return DashboardService.formato_chart(
            labels=[item["bodega__nombre"] or "Sin bodega" for item in qs],
            data=[float(item["total"] or 0) for item in qs],
        )

    @staticmethod
    def obtener_top_productos():
        qs = (
            MovimientoInventario.objects.filter(tipo_movimiento="SALIDA")
            .values("inventario__nombre")
            .annotate(total=Sum("cantidad"))
            .order_by("-total")[:5]
        )

        return DashboardService.formato_chart(
            labels=[item["inventario__nombre"] or "Sin nombre" for item in qs],
            data=[float(item["total"] or 0) for item in qs],
        )

    @staticmethod
    def obtener_entregas_mensuales():
        qs = (
            EntregaEPP.objects.annotate(mes=TruncMonth("fecha_entrega"))
            .values("mes")
            .annotate(total=Count("id"))
            .order_by("mes")
        )

        return DashboardService.formato_chart(
            labels=[
                item["mes"].strftime("%b %Y") if item["mes"] else "Sin fecha"
                for item in qs
            ],
            data=[int(item["total"] or 0) for item in qs],
        )

    @staticmethod
    def obtener_alertas():
        qs = (
            Alerta.objects.annotate(mes=TruncMonth("fecha_alerta"))
            .values("mes")
            .annotate(total=Count("id"))
            .order_by("mes")
        )

        return DashboardService.formato_chart(
            labels=[
                item["mes"].strftime("%b %Y") if item["mes"] else "Sin fecha"
                for item in qs
            ],
            data=[int(item["total"] or 0) for item in qs],
        )

    @staticmethod
    def obtener_stock_estado():
        productos = Inventario.objects.filter(estado=True)

        critico = 0
        bajo = 0
        optimo = 0
        sobre_stock = 0

        for producto in productos:
            if producto.stock_actual < producto.stock_minimo:
                critico += 1
            elif producto.stock_actual == producto.stock_minimo:
                bajo += 1
            elif producto.stock_maximo > 0 and producto.stock_actual > producto.stock_maximo:
                sobre_stock += 1
            else:
                optimo += 1

        return DashboardService.formato_chart(
            labels=["Crítico", "Bajo", "Óptimo", "Sobre stock"],
            data=[critico, bajo, optimo, sobre_stock],
        )

    @staticmethod
    def formato_chart(labels, data):
        clean_labels = []
        clean_data = []

        for label, value in zip(labels, data):
            clean_labels.append(str(label) if label else "Sin dato")

            try:
                clean_data.append(float(value or 0))
            except (TypeError, ValueError):
                clean_data.append(0)

        return {
            "labels": clean_labels,
            "data": clean_data,
        }