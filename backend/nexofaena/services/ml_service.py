"""
Motor de Machine Learning / Inteligencia Artificial de NexoFaena SGI.

Toda la matemática vive aquí (Regla de Oro: "Frontend tonto, backend
inteligente"). El frontend solo debe pintar lo que este service entrega.

Seis modelos, cada uno resolviendo un problema de negocio distinto:

1. Regresión Lineal / Random Forest -> Planificación y Compras.
2. Regresión Logística              -> Prevención de quiebre de stock.
3. K-Means                          -> Auditoría de consumo ("robo hormiga").
4. Reglas de Asociación             -> Cross-selling de EPP en el pañol.
5. Random Forest Classifier         -> Perfil de riesgo operativo del trabajador.
6. TF-IDF + Similitud de Coseno     -> Búsqueda semántica de KPIs en texto plano.
"""

import math
from collections import Counter
from datetime import timedelta
from difflib import SequenceMatcher
from itertools import combinations
from statistics import mean, pstdev

import numpy as np
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

from django.db.models import Count, Sum
from django.db.models.functions import TruncWeek
from django.utils import timezone

from nexofaena.models.entrega import DetalleEntregaEPP
from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario
from nexofaena.models.trabajador import Trabajador

SEMANAS_HISTORICO = 12
MIN_SEMANAS_RANDOM_FOREST = 4
TOP_N_PRODUCTOS_PLANIFICACION = 8

DIAS_VENTANA_CONSUMO = 30
MIN_FILAS_REGRESION_LOGISTICA = 40
DIAS_VENTANA_ENTRENAMIENTO = 180
MAX_FILAS_ENTRENAMIENTO = 5000

MIN_TRABAJADORES_KMEANS = 6

MIN_ENTREGAS_ASOCIACION = 20
MIN_SOPORTE_ASOCIACION = 0.02
MIN_CONFIANZA_ASOCIACION = 0.3
TOP_N_ASOCIACION = 3
TOP_N_ASOCIACION_DASHBOARD = 8

MIN_TRABAJADORES_RIESGO = 10
UMBRAL_TASA_RIESGO_MEDIO = 0.15
UMBRAL_TASA_RIESGO_ALTO = 0.35

MIN_PRODUCTOS_TFIDF = 5
TOP_N_BUSQUEDA_SEMANTICA = 5
UMBRAL_SIMILITUD_MINIMA = 0.1


class MLService:

    # ==================================================================
    # MÓDULO 1 · Regresión Lineal / Random Forest — Planificación y Compras
    # ==================================================================
    @staticmethod
    def predecir_consumo_semanal():
        """Regresión Lineal sobre la serie histórica global de salidas semanales."""
        hoy = timezone.now()
        desde = hoy - timedelta(weeks=SEMANAS_HISTORICO)

        qs = (
            MovimientoInventario.objects
            .filter(tipo_movimiento="SALIDA", fecha__gte=desde)
            .annotate(semana=TruncWeek("fecha"))
            .values("semana")
            .annotate(total=Sum("cantidad"))
            .order_by("semana")
        )

        semanas = list(qs)

        if len(semanas) < 2:
            return {
                "historico": {"labels": [], "data": []},
                "proyeccion_proxima_semana": 0,
                "confiable": False,
            }

        X = np.array([[i] for i in range(len(semanas))])
        y = np.array([float(s["total"] or 0) for s in semanas])

        modelo = LinearRegression()
        modelo.fit(X, y)

        prediccion = modelo.predict(np.array([[len(semanas)]]))[0]

        return {
            "historico": {
                "labels": [s["semana"].strftime("%d-%b") for s in semanas],
                "data": [float(v) for v in y],
            },
            "proyeccion_proxima_semana": max(0, round(float(prediccion), 1)),
            "confiable": len(semanas) >= 4,
        }

    @staticmethod
    def _series_semanales_por_producto():
        desde = timezone.now() - timedelta(weeks=SEMANAS_HISTORICO)

        qs = (
            MovimientoInventario.objects
            .filter(tipo_movimiento="SALIDA", fecha__gte=desde)
            .annotate(semana=TruncWeek("fecha"))
            .values("inventario_id", "semana")
            .annotate(total=Sum("cantidad"))
            .order_by("inventario_id", "semana")
        )

        series = {}
        for fila in qs:
            series.setdefault(fila["inventario_id"], []).append(float(fila["total"] or 0))

        return series

    @staticmethod
    def _calcular_proyecciones_producto():
        """
        Proyecta cuánto se espera consumir de cada producto la próxima semana.
        Usa Random Forest cuando hay suficiente historial semanal; si el
        producto es muy nuevo, cae a un promedio simple (no hay tendencia que
        un bosque de árboles pueda aprender con 1-3 puntos).

        Devuelve la lista completa (sin ordenar ni recortar) para que pueda
        reutilizarse tanto en el listado de planificación como en el cálculo
        de riesgo de quiebre, sin reentrenar los modelos dos veces.
        """
        series = MLService._series_semanales_por_producto()

        if not series:
            return []

        productos = {
            p.id: p
            for p in Inventario.objects.filter(
                id__in=series.keys(), estado=True, es_despacho_rapido=False,
            ).select_related("bodega")
        }

        proyecciones = []

        for inventario_id, valores in series.items():
            producto = productos.get(inventario_id)
            if not producto:
                continue

            if len(valores) >= MIN_SEMANAS_RANDOM_FOREST:
                X = np.array([[i] for i in range(len(valores))])
                y = np.array(valores)

                modelo = RandomForestRegressor(n_estimators=150, random_state=42)
                modelo.fit(X, y)

                proyeccion_semana = float(modelo.predict(np.array([[len(valores)]]))[0])
                algoritmo = "Random Forest"
            else:
                proyeccion_semana = mean(valores)
                algoritmo = "Promedio histórico"

            proyeccion_semana = max(0, round(proyeccion_semana, 1))

            proyecciones.append({
                "inventario_id": producto.id,
                "producto_nombre": producto.nombre,
                "bodega_nombre": producto.bodega.nombre,
                "proyeccion_semana": proyeccion_semana,
                "proyeccion_mes": round(proyeccion_semana * 4, 1),
                "algoritmo": algoritmo,
            })

        return proyecciones

    @staticmethod
    def predecir_consumo_por_producto(top_n=TOP_N_PRODUCTOS_PLANIFICACION):
        proyecciones = sorted(
            MLService._calcular_proyecciones_producto(),
            key=lambda p: p["proyeccion_mes"],
            reverse=True,
        )

        return proyecciones[:top_n]

    # ==================================================================
    # MÓDULO 2 · Regresión Logística — Prevención de Quiebre de Stock
    # ==================================================================
    @staticmethod
    def _consumo_diario_reciente():
        desde = timezone.now() - timedelta(days=DIAS_VENTANA_CONSUMO)

        return {
            item["inventario_id"]: float(item["total"] or 0) / DIAS_VENTANA_CONSUMO
            for item in (
                MovimientoInventario.objects
                .filter(tipo_movimiento="SALIDA", fecha__gte=desde)
                .values("inventario_id")
                .annotate(total=Sum("cantidad"))
            )
        }

    @staticmethod
    def _entrenar_regresion_logistica(consumo_diario):
        """
        Entrena una Regresión Logística real sobre los movimientos históricos:
        para cada movimiento registrado, ¿el stock resultante quedó en o bajo
        el mínimo del producto? El modelo aprende a asociar
        [stock_actual, consumo_diario, tiempo_reposición] con ese riesgo.

        El consumo diario histórico se aproxima con el promedio actual del
        producto (no se reconstruye la velocidad de consumo exacta de cada
        fecha pasada); es una simplificación razonable dado el volumen de
        datos disponible.
        """
        desde = timezone.now() - timedelta(days=DIAS_VENTANA_ENTRENAMIENTO)

        movimientos = (
            MovimientoInventario.objects
            .filter(fecha__gte=desde)
            .select_related("inventario")
            .values("inventario_id", "stock_actual", "inventario__stock_minimo",
                     "inventario__tiempo_reposicion_dias")
            .order_by("-fecha")[:MAX_FILAS_ENTRENAMIENTO]
        )

        X, y = [], []

        for mov in movimientos:
            diario = consumo_diario.get(mov["inventario_id"], 0)

            X.append([
                float(mov["stock_actual"]),
                diario,
                mov["inventario__tiempo_reposicion_dias"] or 7,
            ])
            y.append(1 if float(mov["stock_actual"]) <= float(mov["inventario__stock_minimo"]) else 0)

        if len(y) < MIN_FILAS_REGRESION_LOGISTICA or len(set(y)) < 2:
            return None, None

        scaler = StandardScaler()
        X_escalado = scaler.fit_transform(np.array(X))

        modelo = LogisticRegression(max_iter=1000)
        modelo.fit(X_escalado, y)

        return modelo, scaler

    @staticmethod
    def _probabilidad_quiebre_fallback(dias_restantes, tiempo_reposicion):
        """Función logística clásica aplicada directamente cuando no hay
        datos suficientes para entrenar el modelo (fallback matemático, no
        estadístico ingenuo: sigue siendo la misma función sigmoide)."""
        k = 0.35
        z = k * (tiempo_reposicion - dias_restantes)
        return 1 / (1 + math.exp(-z))

    @staticmethod
    def _analizar_riesgo_quiebre(proyecciones_producto=None):
        consumo_diario = MLService._consumo_diario_reciente()
        modelo, scaler = MLService._entrenar_regresion_logistica(consumo_diario)

        if proyecciones_producto is None:
            proyecciones_producto = MLService._calcular_proyecciones_producto()

        proyecciones_rf = {
            p["inventario_id"]: p["proyeccion_semana"] / 7
            for p in proyecciones_producto
        }

        hoy = timezone.now().date()
        productos = Inventario.objects.filter(estado=True, es_despacho_rapido=False).select_related("bodega")

        quiebre_stock = []
        recomendaciones = []

        for producto in productos:
            diario = proyecciones_rf.get(producto.id, consumo_diario.get(producto.id, 0))

            if diario <= 0:
                continue

            stock_actual = float(producto.stock_actual)
            dias_restantes = stock_actual / diario
            tiempo_reposicion = producto.tiempo_reposicion_dias or 7

            if modelo is not None:
                entrada = scaler.transform([[stock_actual, diario, tiempo_reposicion]])
                probabilidad = float(modelo.predict_proba(entrada)[0][1]) * 100
                algoritmo = "Regresión Logística"
            else:
                probabilidad = MLService._probabilidad_quiebre_fallback(dias_restantes, tiempo_reposicion) * 100
                algoritmo = "Regresión Logística (fórmula base)"

            probabilidad = round(min(100, probabilidad), 1)

            if probabilidad < 15:
                continue

            quiebre_stock.append({
                "inventario_id": producto.id,
                "producto_nombre": producto.nombre,
                "producto_codigo": producto.codigo,
                "bodega_nombre": producto.bodega.nombre,
                "stock_actual": stock_actual,
                "consumo_diario_promedio": round(diario, 2),
                "dias_restantes_estimados": round(dias_restantes, 1),
                "tiempo_reposicion_dias": tiempo_reposicion,
                "probabilidad_quiebre": probabilidad,
                "algoritmo": algoritmo,
            })

            if probabilidad < 40:
                continue

            dias_para_pedir = max(0, round(dias_restantes - tiempo_reposicion))
            fecha_sugerida = hoy + timedelta(days=dias_para_pedir)

            consumo_cobertura = diario * tiempo_reposicion * 2
            objetivo_stock = float(producto.stock_maximo) if producto.stock_maximo > 0 else consumo_cobertura
            cantidad_sugerida = max(objetivo_stock - stock_actual, consumo_cobertura)

            recomendaciones.append({
                "inventario_id": producto.id,
                "producto_nombre": producto.nombre,
                "bodega_nombre": producto.bodega.nombre,
                "fecha_sugerida_pedido": fecha_sugerida.isoformat(),
                "cantidad_sugerida": round(max(cantidad_sugerida, 1), 0),
                "probabilidad_quiebre": probabilidad,
            })

        quiebre_stock.sort(key=lambda r: r["probabilidad_quiebre"], reverse=True)
        recomendaciones.sort(key=lambda r: r["probabilidad_quiebre"], reverse=True)

        return quiebre_stock, recomendaciones

    @staticmethod
    def analitica_stock():
        """
        Punto de entrada único para el dashboard: calcula las proyecciones
        de consumo por producto (Random Forest) una sola vez y las reutiliza
        tanto para el listado de planificación como para el riesgo de
        quiebre, evitando reentrenar los modelos dos veces por request.
        """
        proyecciones_producto = sorted(
            MLService._calcular_proyecciones_producto(),
            key=lambda p: p["proyeccion_mes"],
            reverse=True,
        )

        quiebre_stock, recomendaciones = MLService._analizar_riesgo_quiebre(proyecciones_producto)

        return {
            "prediccion_consumo_producto": proyecciones_producto[:TOP_N_PRODUCTOS_PLANIFICACION],
            "quiebre_stock": quiebre_stock,
            "recomendaciones_reposicion": recomendaciones,
        }

    @staticmethod
    def predecir_quiebre_stock():
        quiebre_stock, _ = MLService._analizar_riesgo_quiebre()
        return quiebre_stock

    @staticmethod
    def recomendar_reposicion():
        _, recomendaciones = MLService._analizar_riesgo_quiebre()
        return recomendaciones

    # ==================================================================
    # MÓDULO 3 · K-Means — Auditoría de Consumo ("Robo Hormiga")
    # ==================================================================
    @staticmethod
    def detectar_anomalias():
        inicio_mes = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        consumos = (
            MovimientoInventario.objects
            .filter(tipo_movimiento="SALIDA", fecha__gte=inicio_mes, trabajador__isnull=False)
            .exclude(inventario__es_despacho_rapido=True)
            .values("trabajador_id", "trabajador__nombres", "trabajador__apellido_paterno")
            .annotate(
                total=Sum("cantidad"),
                num_entregas=Count("id"),
                productos_distintos=Count("inventario_id", distinct=True),
            )
            .order_by("-total")
        )

        registros = list(consumos)

        if len(registros) < 3:
            return []

        if len(registros) >= MIN_TRABAJADORES_KMEANS:
            anomalias = MLService._detectar_anomalias_kmeans(registros)
        else:
            anomalias = MLService._detectar_anomalias_fallback(registros)

        return MLService._enriquecer_anomalias(anomalias, inicio_mes)

    @staticmethod
    def _detectar_anomalias_kmeans(registros):
        """
        Agrupa a los trabajadores por su patrón de consumo del mes
        (total retirado, N° de entregas, variedad de productos). Al
        trabajador que cae en el clúster de consumo elevado -y que además
        se aleja claramente del promedio general- se le marca como anómalo.
        """
        X = np.array([
            [float(r["total"]), r["num_entregas"], r["productos_distintos"]]
            for r in registros
        ])

        scaler = StandardScaler()
        X_escalado = scaler.fit_transform(X)

        k = min(3, max(2, len(registros) // 4))
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        etiquetas = kmeans.fit_predict(X_escalado)

        totales = X[:, 0]
        promedio_global = float(mean(totales))
        desviacion_global = float(pstdev(totales)) if len(totales) > 1 else 0

        promedio_por_cluster = {
            c: float(mean(totales[etiquetas == c])) for c in set(etiquetas)
        }
        cluster_alto = max(promedio_por_cluster, key=promedio_por_cluster.get)

        umbral = promedio_global + max(1, 0.5 * desviacion_global)

        if promedio_por_cluster[cluster_alto] <= umbral:
            return []

        anomalos = []
        for registro, etiqueta, total in zip(registros, etiquetas, totales):
            if etiqueta == cluster_alto and total > umbral:
                anomalos.append({**registro, "algoritmo": "K-Means"})

        return anomalos

    @staticmethod
    def _detectar_anomalias_fallback(registros):
        """Fallback estadístico (Z-score) cuando hay muy pocos trabajadores
        activos este mes como para formar clústeres representativos."""
        totales = [float(r["total"]) for r in registros]
        promedio = mean(totales)
        desviacion = pstdev(totales) if len(totales) > 1 else 0
        umbral = promedio + 2 * desviacion

        return [
            {**r, "algoritmo": "Estadístico (Z-score)"}
            for r, total in zip(registros, totales)
            if total > umbral
        ]

    @staticmethod
    def _enriquecer_anomalias(anomalos, inicio_mes):
        """Añade el producto que más retiró cada trabajador anómalo, para
        que la alerta sea concreta (ej. '3 cascos') y no solo un total.

        Se resuelve con una única consulta agrupada (en vez de una por
        trabajador anómalo) para evitar N+1 cuando hay varias anomalías.
        """
        if not anomalos:
            return []

        trabajador_ids = [registro["trabajador_id"] for registro in anomalos]

        filas = (
            MovimientoInventario.objects
            .filter(
                tipo_movimiento="SALIDA",
                fecha__gte=inicio_mes,
                trabajador_id__in=trabajador_ids,
            )
            .exclude(inventario__es_despacho_rapido=True)
            .values("trabajador_id", "inventario_id", "inventario__nombre", "bodega__nombre")
            .annotate(total=Sum("cantidad"))
            .order_by("trabajador_id", "-total")
        )

        top_producto_por_trabajador = {}
        for fila in filas:
            top_producto_por_trabajador.setdefault(fila["trabajador_id"], fila)

        anomalias = []

        for registro in anomalos:
            top_producto = top_producto_por_trabajador.get(registro["trabajador_id"])

            if not top_producto:
                continue

            nombre_trabajador = f"{registro['trabajador__nombres']} {registro['trabajador__apellido_paterno']}"

            anomalias.append({
                "trabajador_id": registro["trabajador_id"],
                "trabajador_nombre": nombre_trabajador,
                "inventario_id": top_producto["inventario_id"],
                "producto_nombre": top_producto["inventario__nombre"],
                "bodega_nombre": top_producto["bodega__nombre"],
                "cantidad_mes": float(registro["total"]),
                "num_entregas": registro["num_entregas"],
                "productos_distintos": registro["productos_distintos"],
                "algoritmo": registro["algoritmo"],
                "mensaje": (
                    f"{nombre_trabajador} retiró {float(registro['total']):.0f} unidades en total este mes "
                    f"({registro['num_entregas']} entregas, {registro['productos_distintos']} productos distintos), "
                    f"destacando {top_producto['inventario__nombre']}. Consumo fuera del patrón normal del grupo."
                ),
            })

        return anomalias

    # ==================================================================
    # MÓDULO 4 · Reglas de Asociación — Cross-selling de EPP
    # ==================================================================
    @staticmethod
    def _construir_canastas_epp():
        """
        Cada entrega (EntregaEPP) es una "canasta": el conjunto de productos
        distintos que un trabajador se llevó en una misma visita al pañol.
        Es el insumo estándar para reglas de asociación tipo market-basket.
        """
        filas = (
            DetalleEntregaEPP.objects
            .filter(entrega__estado="COMPLETADA")
            .values("entrega_id", "inventario_id")
            .distinct()
        )

        canastas = {}
        for fila in filas:
            canastas.setdefault(fila["entrega_id"], set()).add(fila["inventario_id"])

        return list(canastas.values())

    @staticmethod
    def _calcular_reglas_asociacion():
        """
        Soporte / confianza / lift calculados a mano sobre pares de
        productos: el catálogo de un pañol es chico, así que no vale la
        pena traer una librería de Apriori aparte solo para esto.

        Devuelve {inventario_id: [reglas hacia otros productos]} y el
        total de canastas usado (para poder decidir si hay masa crítica
        de datos antes de confiar en las reglas).
        """
        canastas = MLService._construir_canastas_epp()
        total_canastas = len(canastas)

        if total_canastas < MIN_ENTREGAS_ASOCIACION:
            return {}, total_canastas

        conteo_individual = Counter()
        conteo_pares = Counter()

        for canasta in canastas:
            for producto in canasta:
                conteo_individual[producto] += 1
            for a, b in combinations(sorted(canasta), 2):
                conteo_pares[(a, b)] += 1

        reglas = {}

        for (a, b), conteo_ab in conteo_pares.items():
            soporte_ab = conteo_ab / total_canastas
            if soporte_ab < MIN_SOPORTE_ASOCIACION:
                continue

            soporte_a = conteo_individual[a] / total_canastas
            soporte_b = conteo_individual[b] / total_canastas
            lift = soporte_ab / (soporte_a * soporte_b)

            if lift <= 1:
                continue  # sin lift > 1 la combinación no dice nada por sobre el azar

            confianza_a_b = conteo_ab / conteo_individual[a]
            if confianza_a_b >= MIN_CONFIANZA_ASOCIACION:
                reglas.setdefault(a, []).append({
                    "inventario_id": b, "confianza": confianza_a_b,
                    "soporte": soporte_ab, "lift": lift,
                })

            confianza_b_a = conteo_ab / conteo_individual[b]
            if confianza_b_a >= MIN_CONFIANZA_ASOCIACION:
                reglas.setdefault(b, []).append({
                    "inventario_id": a, "confianza": confianza_b_a,
                    "soporte": soporte_ab, "lift": lift,
                })

        return reglas, total_canastas

    @staticmethod
    def recomendar_epp_asociado(inventario_id, top_n=TOP_N_ASOCIACION):
        """
        Punto de entrada para la tablet del pañolero: al agregar el
        "Producto A" a una entrega, sugiere qué otros productos suelen
        entregarse junto a él (ej. Arnés -> Cabo de vida), ordenados por
        lift (cuánto aumenta la combinación la probabilidad por sobre el
        azar, no solo qué tan seguido aparece).
        """
        try:
            reglas, total_canastas = MLService._calcular_reglas_asociacion()
        except Exception:
            return {
                "sugerencias": [], "confiable": False,
                "motivo": "Error inesperado al calcular las reglas de asociación.",
            }

        if total_canastas < MIN_ENTREGAS_ASOCIACION:
            return {
                "sugerencias": [], "confiable": False,
                "motivo": (
                    f"Aún no hay suficiente historial de entregas "
                    f"({total_canastas}/{MIN_ENTREGAS_ASOCIACION}) para calcular asociaciones confiables."
                ),
            }

        candidatas = sorted(
            reglas.get(inventario_id, []),
            key=lambda r: r["lift"],
            reverse=True,
        )[:top_n]

        if not candidatas:
            return {
                "sugerencias": [], "confiable": True,
                "motivo": "Sin asociaciones relevantes registradas para este producto.",
            }

        productos = {
            p.id: p for p in Inventario.objects.filter(
                id__in=[c["inventario_id"] for c in candidatas]
            )
        }

        sugerencias = []
        for candidata in candidatas:
            producto = productos.get(candidata["inventario_id"])
            if not producto:
                continue

            confianza_pct = round(candidata["confianza"] * 100, 1)

            sugerencias.append({
                "inventario_id": producto.id,
                "producto_nombre": producto.nombre,
                "producto_codigo": producto.codigo,
                "confianza": confianza_pct,
                "soporte": round(candidata["soporte"] * 100, 1),
                "lift": round(candidata["lift"], 2),
                "mensaje": (
                    f"El {confianza_pct:.0f}% de quienes reciben este producto "
                    f"también se llevan {producto.nombre}."
                ),
            })

        return {
            "sugerencias": sugerencias,
            "confiable": True,
            "algoritmo": "Reglas de Asociación (soporte / confianza / lift)",
        }

    @staticmethod
    def top_reglas_asociacion(top_n=TOP_N_ASOCIACION_DASHBOARD):
        """
        Vista agregada para el Dashboard Gerencial: a diferencia de
        recomendar_epp_asociado (pensado para la tablet del pañolero
        durante una entrega puntual), expone las reglas más fuertes de
        todo el catálogo para mostrar el panorama general de qué EPP se
        repiten juntos.
        """
        try:
            reglas_por_producto, total_canastas = MLService._calcular_reglas_asociacion()
        except Exception:
            return {
                "reglas": [], "confiable": False,
                "motivo": "Error inesperado al calcular las reglas de asociación.",
            }

        if total_canastas < MIN_ENTREGAS_ASOCIACION:
            return {
                "reglas": [], "confiable": False,
                "motivo": (
                    f"Aún no hay suficiente historial de entregas "
                    f"({total_canastas}/{MIN_ENTREGAS_ASOCIACION}) para calcular asociaciones confiables."
                ),
            }

        todas = sorted(
            (
                {
                    "inventario_a_id": producto_a_id,
                    "inventario_b_id": regla["inventario_id"],
                    "confianza": regla["confianza"],
                    "soporte": regla["soporte"],
                    "lift": regla["lift"],
                }
                for producto_a_id, reglas in reglas_por_producto.items()
                for regla in reglas
            ),
            key=lambda r: r["lift"],
            reverse=True,
        )[:top_n]

        if not todas:
            return {
                "reglas": [], "confiable": True,
                "motivo": "Sin asociaciones relevantes registradas todavía.",
            }

        ids_productos = {r["inventario_a_id"] for r in todas} | {r["inventario_b_id"] for r in todas}
        productos = {p.id: p for p in Inventario.objects.filter(id__in=ids_productos)}

        reglas_salida = []
        for r in todas:
            producto_a = productos.get(r["inventario_a_id"])
            producto_b = productos.get(r["inventario_b_id"])
            if not producto_a or not producto_b:
                continue

            confianza_pct = round(r["confianza"] * 100, 1)

            reglas_salida.append({
                "producto_origen": producto_a.nombre,
                "producto_sugerido": producto_b.nombre,
                "confianza": confianza_pct,
                "soporte": round(r["soporte"] * 100, 1),
                "lift": round(r["lift"], 2),
                "mensaje": (
                    f"Trabajadores que sacan {producto_a.nombre} tienen {confianza_pct:.0f}% de "
                    f"probabilidad de necesitar también {producto_b.nombre}."
                ),
            })

        return {
            "reglas": reglas_salida,
            "confiable": True,
            "algoritmo": "Reglas de Asociación (soporte / confianza / lift)",
        }

    # ==================================================================
    # MÓDULO 5 · Random Forest Classifier — Perfil de Riesgo Operativo
    # ==================================================================
    @staticmethod
    def _construir_features_riesgo():
        """
        Por cada trabajador con al menos una entrega de un activo crítico,
        arma las variables que explican su "tasa de reposición": cuántas
        veces tuvo que pedir de nuevo el mismo activo crítico (proxy de
        pérdida/rotura, no hay un campo explícito de "incidente") y qué
        proporción de sus devoluciones llegaron dañadas.
        """
        entregas_criticas = (
            DetalleEntregaEPP.objects
            .filter(entrega__estado="COMPLETADA", inventario__es_activo_critico=True)
            .values("entrega__trabajador_id", "inventario_id")
        )

        por_trabajador = {}
        for fila in entregas_criticas:
            trabajador_id = fila["entrega__trabajador_id"]
            stats = por_trabajador.setdefault(trabajador_id, {"total": 0, "productos": Counter()})
            stats["total"] += 1
            stats["productos"][fila["inventario_id"]] += 1

        if not por_trabajador:
            return []

        dañados_por_trabajador = dict(
            DetalleEntregaEPP.objects
            .filter(entrega__trabajador_id__in=por_trabajador.keys(), estado_devolucion="DAÑADA")
            .values("entrega__trabajador_id")
            .annotate(total=Count("id"))
            .values_list("entrega__trabajador_id", "total")
        )

        devueltos_por_trabajador = dict(
            DetalleEntregaEPP.objects
            .filter(entrega__trabajador_id__in=por_trabajador.keys(), devuelto=True)
            .values("entrega__trabajador_id")
            .annotate(total=Count("id"))
            .values_list("entrega__trabajador_id", "total")
        )

        filas = []
        for trabajador_id, stats in por_trabajador.items():
            productos_distintos = len(stats["productos"])
            reposiciones = stats["total"] - productos_distintos
            tasa_reposicion = reposiciones / stats["total"] if stats["total"] else 0

            devueltos = devueltos_por_trabajador.get(trabajador_id, 0)
            dañados = dañados_por_trabajador.get(trabajador_id, 0)
            tasa_dañados = dañados / devueltos if devueltos else 0

            filas.append({
                "trabajador_id": trabajador_id,
                "entregas_criticas": stats["total"],
                "productos_criticos_distintos": productos_distintos,
                "reposiciones_criticas": reposiciones,
                "tasa_reposicion": tasa_reposicion,
                "tasa_danados": tasa_dañados,
            })

        return filas

    @staticmethod
    def _nivel_riesgo_por_regla(tasa_reposicion):
        if tasa_reposicion >= UMBRAL_TASA_RIESGO_ALTO:
            return "Alto"
        if tasa_reposicion >= UMBRAL_TASA_RIESGO_MEDIO:
            return "Medio"
        return "Bajo"

    @staticmethod
    def perfil_riesgo_operativo():
        """
        Clasifica a los trabajadores en Bajo/Medio/Alto riesgo según su
        tasa de reposición de activos críticos.

        El sistema aún no tiene sanciones o incidentes cargados a mano, así
        que el label de entrenamiento se deriva con la misma regla de
        negocio del fallback (igual que la Regresión Logística del Módulo
        2: el label sale de una regla, no de un humano). El Random Forest
        no memoriza esa regla tal cual, aprende a generalizarla combinando
        las tres variables, y de paso entrega una confianza por caso en
        vez de un corte binario duro.
        """
        try:
            filas = MLService._construir_features_riesgo()
        except Exception:
            return []

        if len(filas) < MIN_TRABAJADORES_RIESGO:
            return MLService._enriquecer_riesgo(MLService._perfil_riesgo_fallback(filas))

        X = np.array([
            [f["tasa_reposicion"], f["entregas_criticas"], f["tasa_danados"]]
            for f in filas
        ])
        y = np.array([MLService._nivel_riesgo_por_regla(f["tasa_reposicion"]) for f in filas])

        if len(set(y)) < 2:
            # Todos los trabajadores cayeron en el mismo nivel: no hay nada
            # que un clasificador pueda aprender a separar todavía.
            return MLService._enriquecer_riesgo(MLService._perfil_riesgo_fallback(filas))

        try:
            modelo = RandomForestClassifier(n_estimators=200, random_state=42, max_depth=4)
            modelo.fit(X, y)
            probabilidades = modelo.predict_proba(X)
            clases = list(modelo.classes_)
        except Exception:
            return MLService._enriquecer_riesgo(MLService._perfil_riesgo_fallback(filas))

        resultados = []
        for fila, probas in zip(filas, probabilidades):
            idx_predicho = int(np.argmax(probas))

            resultados.append({
                **fila,
                "nivel_riesgo": clases[idx_predicho],
                "confianza": round(float(probas[idx_predicho]) * 100, 1),
                "bandera_roja": clases[idx_predicho] == "Alto",
                "algoritmo": "Random Forest Classifier",
            })

        return MLService._enriquecer_riesgo(resultados)

    @staticmethod
    def _perfil_riesgo_fallback(filas):
        """Regla de negocio directa (sin entrenar) cuando aún no hay
        suficientes trabajadores con historial de activos críticos como
        para separar clases de forma representativa."""
        return [
            {
                **fila,
                "nivel_riesgo": MLService._nivel_riesgo_por_regla(fila["tasa_reposicion"]),
                "confianza": None,
                "bandera_roja": fila["tasa_reposicion"] >= UMBRAL_TASA_RIESGO_ALTO,
                "algoritmo": "Regla de negocio (fallback: historial insuficiente para entrenar)",
            }
            for fila in filas
        ]

    @staticmethod
    def _enriquecer_riesgo(resultados):
        if not resultados:
            return []

        trabajadores = {
            t.id: t for t in Trabajador.objects.filter(
                id__in=[r["trabajador_id"] for r in resultados]
            )
        }

        salida = []
        for r in resultados:
            trabajador = trabajadores.get(r["trabajador_id"])
            if not trabajador:
                continue

            salida.append({
                "trabajador_id": trabajador.id,
                "trabajador_nombre": trabajador.nombre_completo,
                "cargo": trabajador.cargo,
                "entregas_criticas": r["entregas_criticas"],
                "reposiciones_criticas": r["reposiciones_criticas"],
                "tasa_reposicion": round(r["tasa_reposicion"] * 100, 1),
                "tasa_danados": round(r["tasa_danados"] * 100, 1),
                "nivel_riesgo": r["nivel_riesgo"],
                "confianza": r["confianza"],
                "bandera_roja": r["bandera_roja"],
                "algoritmo": r["algoritmo"],
            })

        salida.sort(key=lambda r: r["tasa_reposicion"], reverse=True)
        return salida

    @staticmethod
    def evaluar_riesgo_entrega(trabajador_id):
        """
        Punto de entrada puntual para el flujo de entrega: antes de
        despachar otro activo crítico, consulta si el trabajador tiene
        bandera roja para que el pañolero decida con contexto. No bloquea
        la entrega automáticamente, es una alerta informativa.
        """
        try:
            perfiles = MLService.perfil_riesgo_operativo()
        except Exception:
            return {
                "trabajador_id": trabajador_id,
                "nivel_riesgo": "Sin datos",
                "bandera_roja": False,
                "mensaje": "Error inesperado al calcular el perfil de riesgo.",
            }

        perfil = next((p for p in perfiles if p["trabajador_id"] == trabajador_id), None)

        if not perfil:
            return {
                "trabajador_id": trabajador_id,
                "nivel_riesgo": "Sin datos",
                "bandera_roja": False,
                "mensaje": "Sin historial de activos críticos registrado para este trabajador.",
            }

        return perfil

    # ==================================================================
    # MÓDULO 6 · TF-IDF + Similitud de Coseno — Búsqueda Semántica de KPIs
    # ==================================================================
    @staticmethod
    def _corpus_inventario():
        productos = list(Inventario.objects.filter(estado=True).select_related("bodega"))

        documentos = [
            " ".join(filter(None, [
                p.nombre, p.codigo, p.marca, p.modelo, p.bodega.nombre, p.ubicacion,
            ]))
            for p in productos
        ]

        return productos, documentos

    @staticmethod
    def _similitud_tfidf(consulta, documentos):
        vectorizador = TfidfVectorizer(strip_accents="unicode", lowercase=True)
        matriz = vectorizador.fit_transform(documentos + [consulta])

        vector_consulta = matriz[-1]
        vector_documentos = matriz[:-1]

        puntajes = cosine_similarity(vector_consulta, vector_documentos)[0]
        orden = np.argsort(puntajes)[::-1]

        return orden, puntajes[orden]

    @staticmethod
    def _similitud_difflib(consulta, documentos):
        """Fallback sin vocabulario: similitud de secuencias de caracteres
        directa (fuzzy-match), útil cuando el catálogo es tan chico que el
        TF-IDF no tiene señal suficiente para ser confiable."""
        consulta_normalizada = consulta.lower()

        puntajes = np.array([
            SequenceMatcher(None, consulta_normalizada, doc.lower()).ratio()
            for doc in documentos
        ])
        orden = np.argsort(puntajes)[::-1]

        return orden, puntajes[orden]

    @staticmethod
    def _kpi_producto(producto, puntaje_similitud, consumo_diario_map):
        consumo_diario = consumo_diario_map.get(producto.id, 0)

        return {
            "inventario_id": producto.id,
            "producto_nombre": producto.nombre,
            "producto_codigo": producto.codigo,
            "bodega_nombre": producto.bodega.nombre,
            "stock_actual": float(producto.stock_actual),
            "stock_minimo": float(producto.stock_minimo),
            "necesita_reposicion": producto.necesita_reposicion,
            "consumo_diario_promedio": round(consumo_diario, 2),
            "consumo_mensual_estimado": round(consumo_diario * 30, 1),
            "similitud": round(float(puntaje_similitud) * 100, 1),
        }

    @staticmethod
    def buscar_kpi_por_texto(consulta, top_n=TOP_N_BUSQUEDA_SEMANTICA):
        """
        Motor de búsqueda semántica minimalista para consultas gerenciales
        en texto plano (ej. "consumo de cascos"): vectoriza nombre / código
        / marca / modelo de cada producto con TF-IDF y compara contra la
        consulta por similitud de coseno, para devolver directamente sus
        KPIs sin pasar por filtros de UI.
        """
        consulta = (consulta or "").strip()
        if not consulta:
            return {"consulta": consulta, "resultados": [], "confiable": False, "motivo": "Consulta vacía."}

        try:
            productos, documentos = MLService._corpus_inventario()
        except Exception:
            return {
                "consulta": consulta, "resultados": [], "confiable": False,
                "motivo": "Error inesperado al leer el catálogo de inventario.",
            }

        if not productos:
            return {
                "consulta": consulta, "resultados": [], "confiable": False,
                "motivo": "No hay productos activos en el inventario.",
            }

        if len(productos) >= MIN_PRODUCTOS_TFIDF:
            try:
                indices, puntajes = MLService._similitud_tfidf(consulta, documentos)
                algoritmo = "TF-IDF + Similitud de Coseno"
            except Exception:
                indices, puntajes = MLService._similitud_difflib(consulta, documentos)
                algoritmo = "difflib (fallback por error en TF-IDF)"
        else:
            indices, puntajes = MLService._similitud_difflib(consulta, documentos)
            algoritmo = "difflib (fallback: catálogo pequeño)"

        try:
            consumo_diario_map = MLService._consumo_diario_reciente()
        except Exception:
            consumo_diario_map = {}

        resultados = []
        for idx, puntaje in zip(indices, puntajes):
            if puntaje < UMBRAL_SIMILITUD_MINIMA:
                continue

            resultados.append(MLService._kpi_producto(productos[idx], puntaje, consumo_diario_map))

            if len(resultados) >= top_n:
                break

        return {
            "consulta": consulta,
            "resultados": resultados,
            "confiable": len(resultados) > 0,
            "algoritmo": algoritmo,
        }
