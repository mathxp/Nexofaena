import logging
import threading
import time

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.models import Count, F, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from nexofaena.models.trabajador import Trabajador
from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario
from nexofaena.models.entrega import DetalleEntregaEPP, EntregaEPP
from nexofaena.models.alerta import Alerta
from nexofaena.services.ml_service import MLService

CACHE_KEY_DASHBOARD = "nexofaena:dashboard:resumen"
CACHE_KEY_ML_AVANZADO = "nexofaena:dashboard:ml_avanzado"
CACHE_KEY_SUCIO = "nexofaena:dashboard:sucio"
CACHE_KEY_RECALCULANDO = "nexofaena:dashboard:recalculando"

# Cada cuánto se recalcula aunque nadie haya cambiado datos (ej. ediciones
# directas en el admin, o el paso del tiempo en las ventanas de los modelos).
CACHE_TTL_SEGUNDOS = 600

# Si un recálculo en segundo plano muere sin liberar el candado, otro puede
# empezar pasado este tiempo.
CANDADO_RECALCULO_SEGUNDOS = 300

logger = logging.getLogger("nexofaena")


class DashboardService:

    # ------------------------------------------------------------------
    # Caché "stale-while-revalidate"
    #
    # Antes, cada entrega o movimiento BORRABA el caché, y el siguiente en
    # abrir el panel esperaba que se reentrenaran todos los modelos (~7 s con
    # 4 meses de datos; bastante más en el plan gratuito de Render). Ahora el
    # caché nunca se borra: un cambio solo lo marca "sucio", el panel responde
    # al instante con el último cálculo y el recálculo corre en un hilo aparte.
    # ------------------------------------------------------------------

    @staticmethod
    def invalidar_cache():
        """
        Se llama desde cualquier operación que cambie stock, entregas o
        alertas. Marca los datos como desactualizados; el próximo GET del
        panel los sirve igual y dispara el recálculo en segundo plano.
        """
        cache.set(CACHE_KEY_SUCIO, True, None)

    @staticmethod
    def _guardar(clave, datos):
        cache.set(clave, {"datos": datos, "ts": time.time()}, None)

    @staticmethod
    def _obtener(clave, calcular):
        entrada = cache.get(clave)
        if not isinstance(entrada, dict) or "datos" not in entrada:
            # Primera vez (o formato antiguo del caché): no hay nada que
            # mostrar todavía, así que se calcula en la request. Se recalcula
            # todo (no solo esta clave) para que la marca de "sucio" quede
            # limpia y la siguiente carga no vuelva a recalcular.
            DashboardService.recalcular_cache()
            return cache.get(clave)["datos"]

        vencido = time.time() - entrada.get("ts", 0) > CACHE_TTL_SEGUNDOS
        if vencido or cache.get(CACHE_KEY_SUCIO):
            DashboardService._recalcular_en_segundo_plano()
        return entrada["datos"]

    @staticmethod
    def _recalcular_en_segundo_plano():
        if not getattr(settings, "DASHBOARD_RECALCULO_EN_SEGUNDO_PLANO", True):
            DashboardService.recalcular_cache()
            return

        # cache.add es atómico: si otro proceso ya está recalculando, no se
        # lanza un segundo entrenamiento en paralelo.
        if not cache.add(CACHE_KEY_RECALCULANDO, True, CANDADO_RECALCULO_SEGUNDOS):
            return

        def recalcular():
            try:
                DashboardService.recalcular_cache()
            except Exception:
                logger.exception("Falló el recálculo del panel en segundo plano.")
            finally:
                cache.delete(CACHE_KEY_RECALCULANDO)
                connection.close()  # el hilo abrió su propia conexión a la BD

        threading.Thread(target=recalcular, daemon=True).start()

    @staticmethod
    def _calcular_dashboard():
        """Cómputo puro (sin tocar el cache): entrena Random Forest,
        Regresión Logística y K-Means. Lo llaman tanto obtener_dashboard()
        (cache-miss) como recalcular_cache() (cron)."""
        analitica_stock = MLService.analitica_stock()

        return {
            "kpis": DashboardService.obtener_kpis(),
            "entregas_mensuales": DashboardService.obtener_entregas_mensuales(),
            "top_productos": DashboardService.obtener_top_productos(),
            "consumo_bodega": DashboardService.obtener_consumo_por_bodega(),
            "alertas": DashboardService.obtener_alertas(),
            "stock_estado": DashboardService.obtener_stock_estado(),
            "prediccion_consumo": MLService.predecir_consumo_semanal(),
            "prediccion_consumo_producto": analitica_stock["prediccion_consumo_producto"],
            "presupuesto_proyectado": analitica_stock["presupuesto_proyectado"],
            "anomalias_consumo": MLService.detectar_anomalias(),
            "quiebre_stock": analitica_stock["quiebre_stock"],
            "recomendaciones_reposicion": analitica_stock["recomendaciones_reposicion"],
            "capital_inmovilizado": analitica_stock["capital_inmovilizado"],
            "entregas_por_canal": DashboardService.obtener_entregas_por_canal(),
            "calculado_en": timezone.now().isoformat(),
        }

    @staticmethod
    def obtener_dashboard():
        """Datos del panel: siempre responde al instante salvo la primera vez."""
        return DashboardService._obtener(CACHE_KEY_DASHBOARD, DashboardService._calcular_dashboard)

    @staticmethod
    def _calcular_ml_avanzado():
        """Cómputo puro del bloque ML "extendido" (clasificación ABC)."""
        return {
            "clasificacion_abc": MLService.clasificacion_abc_dinamica(),
        }

    @staticmethod
    def obtener_ml_avanzado():
        """Clasificación ABC del panel, con el mismo caché que obtener_dashboard()."""
        return DashboardService._obtener(CACHE_KEY_ML_AVANZADO, DashboardService._calcular_ml_avanzado)

    @staticmethod
    def recalcular_cache():
        """
        Reentrena y repuebla el caché. La marca de "sucio" se borra ANTES de
        calcular: si llega un cambio mientras se entrena, vuelve a quedar
        marcada y el próximo GET lanza otro recálculo.
        """
        cache.delete(CACHE_KEY_SUCIO)
        DashboardService._guardar(CACHE_KEY_DASHBOARD, DashboardService._calcular_dashboard())
        DashboardService._guardar(CACHE_KEY_ML_AVANZADO, DashboardService._calcular_ml_avanzado())

    @staticmethod
    def obtener_operativo():
        """
        Resumen operativo para todos los roles: solo conteos baratos (no
        entrena modelos ni usa el caché del panel). Reemplaza descargar el
        inventario, los trabajadores y las alertas completos solo para
        contarlos en el navegador.
        """
        alertas_abiertas = Alerta.objects.filter(leida=False)

        return {
            "trabajadores_activos": Trabajador.objects.filter(activo=True).count(),
            "productos_bajo_minimo": Inventario.objects.filter(
                estado=True, stock_minimo__gt=0, stock_actual__lte=F("stock_minimo"),
            ).count(),
            "alertas_abiertas": alertas_abiertas.count(),
            "radios_por_devolver": DetalleEntregaEPP.objects.filter(
                unidad_activo__isnull=False, devuelto=False, entrega__estado="COMPLETADA",
            ).count(),
            "alertas_recientes": [
                {
                    "id": alerta.id,
                    "tipo_alerta": alerta.tipo_alerta,
                    "tipo_nombre": alerta.get_tipo_alerta_display(),
                    "mensaje": alerta.mensaje,
                    "fecha_alerta": alerta.fecha_alerta.isoformat(),
                }
                for alerta in alertas_abiertas.order_by("-fecha_alerta")[:5]
            ],
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
    def obtener_entregas_por_canal():
        """
        Cuántas entregas del mes vinieron del kiosco de autoservicio vs. las
        que registró un bodeguero a mano — la métrica que le importa a
        quien evalúa si el kiosco realmente bajó la carga del pañol. Solo
        cuenta entregas COMPLETADA (una PENDIENTE/ANULADA no es una entrega
        real todavía).
        """
        inicio_mes = timezone.now().replace(day=1)

        conteo = dict(
            EntregaEPP.objects.filter(estado="COMPLETADA", fecha_entrega__gte=inicio_mes)
            .values("canal")
            .annotate(total=Count("id"))
            .values_list("canal", "total")
        )

        return {
            "kiosco": conteo.get("KIOSCO", 0),
            "bodega": conteo.get("BODEGA", 0),
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