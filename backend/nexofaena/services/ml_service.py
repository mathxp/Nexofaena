"""
Motor de Machine Learning / Inteligencia Artificial de NexoFaena SGI.

Toda la matemática vive aquí (Regla de Oro: "Frontend tonto, backend
inteligente"). El frontend solo debe pintar lo que este service entrega.

Modelos, cada uno resolviendo un problema de negocio distinto:

1. Regresión Lineal / Random Forest -> Planificación y Compras.
2. Regresión Logística              -> Prevención de quiebre de stock.
3. K-Means                          -> Auditoría de consumo ("robo hormiga").
6. TF-IDF + Similitud de Coseno     -> Búsqueda semántica de KPIs en texto plano.
7. K-Means                          -> Clasificación ABC dinámica del inventario (valor x rotación).
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
from django.utils.dateparse import parse_date

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

UMBRAL_DIAS_SOBRESTOCK = 180  # ~6 meses de cobertura
UMBRAL_PROBABILIDAD_SOBRESTOCK = 5  # % de riesgo de quiebre considerado prácticamente nulo

MIN_TRABAJADORES_KMEANS = 6

MIN_PRODUCTOS_TFIDF = 5
TOP_N_BUSQUEDA_SEMANTICA = 5
UMBRAL_SIMILITUD_MINIMA = 0.1

MIN_PRODUCTOS_ABC = 6
DIAS_VENTANA_ROTACION_ABC = 90

MIN_ENTREGAS_HISTORICO_PROPIO = 3
UMBRAL_Z_HISTORICO = 2.0


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
                id__in=series.keys(), estado=True,
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
            proyeccion_mes = round(proyeccion_semana * 4, 1)
            precio_unitario = float(producto.precio_unitario)

            proyecciones.append({
                "inventario_id": producto.id,
                "producto_nombre": producto.nombre,
                "bodega_nombre": producto.bodega.nombre,
                "proyeccion_semana": proyeccion_semana,
                "proyeccion_mes": proyeccion_mes,
                "precio_unitario": precio_unitario,
                # Valorización financiera: cuánto costará reponer lo que se proyecta consumir.
                "proyeccion_gasto_clp": round(proyeccion_semana * precio_unitario, 2),
                "proyeccion_gasto_mensual_clp": round(proyeccion_mes * precio_unitario, 2),
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
        productos = Inventario.objects.filter(estado=True).select_related("bodega")

        quiebre_stock = []
        recomendaciones = []
        capital_inmovilizado = []

        for producto in productos:
            diario = proyecciones_rf.get(producto.id, consumo_diario.get(producto.id, 0))
            stock_actual = float(producto.stock_actual)
            precio_unitario = float(producto.precio_unitario)

            if diario <= 0:
                # Sin consumo reciente: si además hay stock valorizado, es capital
                # dormido (0% de riesgo de quiebre porque nadie lo está pidiendo).
                if stock_actual > 0 and precio_unitario > 0:
                    capital_inmovilizado.append({
                        "inventario_id": producto.id,
                        "producto_nombre": producto.nombre,
                        "bodega_nombre": producto.bodega.nombre,
                        "stock_actual": stock_actual,
                        "dias_cobertura_estimados": None,
                        "precio_unitario": precio_unitario,
                        "capital_inmovilizado_clp": round(stock_actual * precio_unitario, 2),
                        "motivo": "Sin consumo registrado en el período reciente (posible obsolescencia).",
                    })
                continue

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

            # Optimización de capital: riesgo de quiebre ~nulo + cobertura de
            # varios meses = dinero inmovilizado en sobre-stock, no en riesgo.
            if (
                probabilidad <= UMBRAL_PROBABILIDAD_SOBRESTOCK
                and dias_restantes >= UMBRAL_DIAS_SOBRESTOCK
                and precio_unitario > 0
            ):
                capital_inmovilizado.append({
                    "inventario_id": producto.id,
                    "producto_nombre": producto.nombre,
                    "bodega_nombre": producto.bodega.nombre,
                    "stock_actual": stock_actual,
                    "dias_cobertura_estimados": round(dias_restantes, 1),
                    "precio_unitario": precio_unitario,
                    "capital_inmovilizado_clp": round(stock_actual * precio_unitario, 2),
                    "motivo": "Sobre-stock: más de 6 meses de cobertura con riesgo de quiebre prácticamente nulo.",
                })

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

        return quiebre_stock, recomendaciones, capital_inmovilizado

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

        quiebre_stock, recomendaciones, capital_inmovilizado = MLService._analizar_riesgo_quiebre(proyecciones_producto)

        presupuesto_proyectado = {
            "semanal_clp": round(sum(p["proyeccion_gasto_clp"] for p in proyecciones_producto), 2),
            "mensual_clp": round(sum(p["proyeccion_gasto_mensual_clp"] for p in proyecciones_producto), 2),
        }

        capital_inmovilizado_ordenado = sorted(
            capital_inmovilizado, key=lambda c: c["capital_inmovilizado_clp"], reverse=True
        )

        return {
            "prediccion_consumo_producto": proyecciones_producto[:TOP_N_PRODUCTOS_PLANIFICACION],
            "presupuesto_proyectado": presupuesto_proyectado,
            "quiebre_stock": quiebre_stock,
            "recomendaciones_reposicion": recomendaciones,
            "capital_inmovilizado": {
                "items": capital_inmovilizado_ordenado[:TOP_N_PRODUCTOS_PLANIFICACION],
                "total_clp": round(sum(c["capital_inmovilizado_clp"] for c in capital_inmovilizado), 2),
                "cantidad_items": len(capital_inmovilizado),
            },
        }

    @staticmethod
    def predecir_quiebre_stock():
        quiebre_stock, _, _ = MLService._analizar_riesgo_quiebre()
        return quiebre_stock

    @staticmethod
    def recomendar_reposicion():
        _, recomendaciones, _ = MLService._analizar_riesgo_quiebre()
        return recomendaciones

    @staticmethod
    def capital_inmovilizado():
        """Punto de entrada standalone: dinero congelado en sobre-stock (probabilidad
        de quiebre ~nula y cobertura mayor a UMBRAL_DIAS_SOBRESTOCK días)."""
        _, _, capital_inmovilizado = MLService._analizar_riesgo_quiebre()
        capital_inmovilizado.sort(key=lambda c: c["capital_inmovilizado_clp"], reverse=True)
        return capital_inmovilizado

    # ==================================================================
    # MÓDULO 3 · K-Means — Auditoría de Consumo ("Robo Hormiga")
    # ==================================================================
    @staticmethod
    def detectar_anomalias():
        """
        La comparación es SIEMPRE dentro del mismo cargo: un soldador no se
        compara contra un geólogo ni contra "toda la faena", porque los
        consumos no son comparables entre oficios distintos (requerimiento
        directo del stakeholder). Se agrupa por cargo primero y el
        clustering/estadístico corre por separado dentro de cada grupo.
        """
        inicio_mes = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        consumos = (
            MovimientoInventario.objects
            .filter(tipo_movimiento="SALIDA", fecha__gte=inicio_mes, trabajador__isnull=False)
            .values("trabajador_id", "trabajador__nombres", "trabajador__apellido_paterno", "trabajador__cargo")
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

        por_cargo = {}
        for registro in registros:
            por_cargo.setdefault(registro["trabajador__cargo"], []).append(registro)

        anomalias = []
        for registros_cargo in por_cargo.values():
            if len(registros_cargo) < 3:
                continue  # sin suficientes pares del mismo cargo para comparar

            if len(registros_cargo) >= MIN_TRABAJADORES_KMEANS:
                anomalias.extend(MLService._detectar_anomalias_kmeans(registros_cargo))
            else:
                anomalias.extend(MLService._detectar_anomalias_fallback(registros_cargo))

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
        # n_init=3 (no 10): con grupos de una decena de trabajadores por
        # cargo, 10 reinicios aleatorios no cambian el resultado pero sí
        # multiplican el costo — esto se llama una vez POR CADA cargo en
        # detectar_anomalias(), así que el ahorro se repite por grupo.
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=3)
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

        mascara_normal = etiquetas != cluster_alto
        promedio_normal = float(mean(totales[mascara_normal])) if mascara_normal.any() else promedio_global

        anomalos = []
        for registro, etiqueta, total in zip(registros, etiquetas, totales):
            if etiqueta == cluster_alto and total > umbral:
                anomalos.append({**registro, "algoritmo": "K-Means", "promedio_referencia": promedio_normal})

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
            {**r, "algoritmo": "Estadístico (Z-score)", "promedio_referencia": promedio}
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
            .values("trabajador_id", "inventario_id", "inventario__nombre", "inventario__precio_unitario", "bodega__nombre")
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

            # Traducción financiera del "robo hormiga": el exceso de unidades por
            # sobre el consumo normal del grupo, valorizado al precio del producto
            # que más retiró (proxy razonable cuando el exceso es multi-producto).
            precio_referencia = float(top_producto["inventario__precio_unitario"] or 0)
            promedio_referencia = registro.get("promedio_referencia", 0)
            exceso_unidades = max(0.0, float(registro["total"]) - promedio_referencia)
            impacto_financiero_clp = round(exceso_unidades * precio_referencia, 2)

            anomalias.append({
                "trabajador_id": registro["trabajador_id"],
                "trabajador_nombre": nombre_trabajador,
                "cargo": registro.get("trabajador__cargo"),
                "inventario_id": top_producto["inventario_id"],
                "producto_nombre": top_producto["inventario__nombre"],
                "bodega_nombre": top_producto["bodega__nombre"],
                "cantidad_mes": float(registro["total"]),
                "num_entregas": registro["num_entregas"],
                "productos_distintos": registro["productos_distintos"],
                "exceso_unidades": round(exceso_unidades, 1),
                "impacto_financiero_clp": impacto_financiero_clp,
                "algoritmo": registro["algoritmo"],
                "mensaje": (
                    f"{nombre_trabajador} ({registro.get('trabajador__cargo') or 'sin cargo'}) retiró "
                    f"{float(registro['total']):.0f} unidades en total este mes "
                    f"({registro['num_entregas']} entregas, {registro['productos_distintos']} productos distintos), "
                    f"destacando {top_producto['inventario__nombre']}. "
                    f"Consumo fuera del patrón normal de su mismo cargo."
                    + (
                        f" Impacto financiero estimado: ${impacto_financiero_clp:,.0f} CLP en exceso sobre lo esperado."
                        .replace(",", ".")
                        if impacto_financiero_clp > 0 else ""
                    )
                ),
            })

        return anomalias

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

    # ==================================================================
    # MÓDULO 7 · K-Means — Clasificación ABC Dinámica de Inventario
    # ==================================================================
    @staticmethod
    def _rotacion_mensual_por_producto():
        """Promedio mensual de unidades que salieron de cada producto en la
        ventana reciente (rotación real, no la proyección de RF del Módulo 1),
        para no acoplar la clasificación ABC a productos con historial semanal
        insuficiente para entrenar un bosque de árboles."""
        desde = timezone.now() - timedelta(days=DIAS_VENTANA_ROTACION_ABC)
        meses_ventana = DIAS_VENTANA_ROTACION_ABC / 30

        filas = (
            MovimientoInventario.objects
            .filter(tipo_movimiento="SALIDA", fecha__gte=desde)
            .values("inventario_id")
            .annotate(total=Sum("cantidad"))
        )

        return {
            fila["inventario_id"]: float(fila["total"] or 0) / meses_ventana
            for fila in filas
        }

    @staticmethod
    def _construir_features_abc():
        rotacion_mensual = MLService._rotacion_mensual_por_producto()
        productos = Inventario.objects.filter(estado=True).select_related("bodega")

        return [
            {
                "producto": producto,
                "precio_unitario": float(producto.precio_unitario),
                "rotacion_mensual": rotacion_mensual.get(producto.id, 0.0),
            }
            for producto in productos
        ]

    @staticmethod
    def _clasificacion_abc_pareto(filas):
        """Regla de Pareto 80/15/5 clásica (sin entrenar) cuando el catálogo
        es demasiado chico para que K-Means forme 3 clústeres representativos."""
        ordenado = sorted(filas, key=lambda f: f["precio_unitario"] * f["rotacion_mensual"], reverse=True)
        valor_total = sum(f["precio_unitario"] * f["rotacion_mensual"] for f in ordenado)

        acumulado = 0.0
        clasificadas = []

        for f in ordenado:
            acumulado += f["precio_unitario"] * f["rotacion_mensual"]
            porcentaje_acumulado = (acumulado / valor_total * 100) if valor_total > 0 else 100

            if porcentaje_acumulado <= 80:
                clase = "A"
            elif porcentaje_acumulado <= 95:
                clase = "B"
            else:
                clase = "C"

            clasificadas.append({**f, "clase_abc": clase})

        return clasificadas, "Regla de Pareto 80/15/5 (fallback: catálogo pequeño)"

    @staticmethod
    def _clasificacion_abc_kmeans(filas):
        """
        K-Means con dos variables (precio_unitario, rotación_mensual) sobre
        el catálogo completo. Los 3 clústeres no nacen con nombre, así que se
        etiquetan post-hoc por su centroide: el de mayor precio promedio es
        Clase A (alto valor/crítico); entre los dos restantes, el de mayor
        rotación promedio es Clase C (consumo masivo); el que queda es B.
        """
        X = np.array([[f["precio_unitario"], f["rotacion_mensual"]] for f in filas])

        scaler = StandardScaler()
        X_escalado = scaler.fit_transform(X)

        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        etiquetas = kmeans.fit_predict(X_escalado)

        precios = X[:, 0]
        rotaciones = X[:, 1]

        promedio_precio_cluster = {c: float(mean(precios[etiquetas == c])) for c in set(etiquetas)}
        cluster_a = max(promedio_precio_cluster, key=promedio_precio_cluster.get)

        clusters_restantes = [c for c in set(etiquetas) if c != cluster_a]
        promedio_rotacion_cluster = {c: float(mean(rotaciones[etiquetas == c])) for c in clusters_restantes}
        cluster_c = max(promedio_rotacion_cluster, key=promedio_rotacion_cluster.get)

        mapa_clase = {cluster_a: "A"}
        for c in clusters_restantes:
            mapa_clase[c] = "C" if c == cluster_c else "B"

        clasificadas = [
            {**fila, "clase_abc": mapa_clase[etiqueta]}
            for fila, etiqueta in zip(filas, etiquetas)
        ]

        return clasificadas, "K-Means (precio unitario x rotación mensual)"

    @staticmethod
    def clasificacion_abc_dinamica():
        """
        Punto de entrada para el Dashboard Gerencial: agrupa el catálogo de
        inventario por precio unitario y rotación mensual para etiquetar
        automáticamente Clase A (alto valor/crítico, exige firma), Clase B
        (valor medio) y Clase C (consumo masivo) — sin
        depender de que alguien marque manualmente qué producto es
        "importante".
        """
        try:
            filas = MLService._construir_features_abc()
        except Exception:
            return {
                "items": [], "resumen": {}, "confiable": False,
                "motivo": "Error inesperado al calcular la clasificación ABC.",
            }

        filas = [f for f in filas if f["precio_unitario"] > 0]

        if not filas:
            return {
                "items": [], "resumen": {}, "confiable": False,
                "motivo": "Sin productos con precio unitario cargado todavía.",
            }

        if len(filas) < MIN_PRODUCTOS_ABC:
            clasificadas, algoritmo = MLService._clasificacion_abc_pareto(filas)
        else:
            try:
                clasificadas, algoritmo = MLService._clasificacion_abc_kmeans(filas)
            except Exception:
                clasificadas, algoritmo = MLService._clasificacion_abc_pareto(filas)

        items = []
        for f in clasificadas:
            producto = f["producto"]
            stock_actual = float(producto.stock_actual)

            items.append({
                "inventario_id": producto.id,
                "producto_nombre": producto.nombre,
                "bodega_nombre": producto.bodega.nombre,
                "precio_unitario": f["precio_unitario"],
                "rotacion_mensual": round(f["rotacion_mensual"], 1),
                "stock_actual": stock_actual,
                "valor_stock_clp": round(stock_actual * f["precio_unitario"], 2),
                "valor_movido_mensual_clp": round(f["precio_unitario"] * f["rotacion_mensual"], 2),
                "clase_abc": f["clase_abc"],
                "es_activo_critico": producto.es_activo_critico,
                "algoritmo": algoritmo,
            })

        items.sort(key=lambda i: (i["clase_abc"], -i["valor_stock_clp"]))

        resumen = {
            clase: {
                "cantidad": sum(1 for i in items if i["clase_abc"] == clase),
                "valor_stock_clp": round(sum(i["valor_stock_clp"] for i in items if i["clase_abc"] == clase), 2),
            }
            for clase in ("A", "B", "C")
        }

        return {
            "items": items,
            "resumen": resumen,
            "confiable": True,
            "algoritmo": algoritmo,
        }

    # ==================================================================
    # MÓDULO 8 · Z-score — Consumo Atípico Respecto de la Propia Historia
    # ==================================================================
    @staticmethod
    def detectar_consumo_atipico_historico(fecha_desde, fecha_hasta, rut=None,
                                            producto=None, mostrar_rut_completo=False):
        """
        A diferencia del Módulo 3 (K-Means, compara contra el grupo del mes
        actual), este módulo compara a cada trabajador contra SU PROPIA
        historia: ¿retiró en el período consultado más unidades por visita
        al pañol de lo que acostumbra para ese mismo producto?

        Es el "módulo ML" del reporte de consumo por turno: la salida es un
        listado de casos a "revisar", nunca bloquea la entrega ni etiqueta a
        nadie como sospechoso.
        """
        from nexofaena.services.reporte_service import ReporteService  # import local: evita ciclo de módulos

        desde = parse_date(fecha_desde) if isinstance(fecha_desde, str) else fecha_desde
        hasta = parse_date(fecha_hasta) if isinstance(fecha_hasta, str) else fecha_hasta

        periodo_qs = DetalleEntregaEPP.objects.filter(
            entrega__estado="COMPLETADA",
            entrega__fecha_entrega__date__gte=desde,
            entrega__fecha_entrega__date__lte=hasta,
        )

        if rut:
            periodo_qs = periodo_qs.filter(entrega__trabajador__rut__icontains=rut)
        if producto:
            periodo_qs = periodo_qs.filter(inventario__nombre__icontains=producto)

        pares = (
            periodo_qs
            .values("entrega__trabajador_id", "inventario_id")
            .annotate(total_periodo=Sum("cantidad"), num_entregas_periodo=Count("entrega_id", distinct=True))
        )

        candidatos = []
        for par in pares:
            num_entregas_periodo = par["num_entregas_periodo"] or 1
            promedio_periodo = float(par["total_periodo"]) / num_entregas_periodo

            historial = list(
                DetalleEntregaEPP.objects
                .filter(
                    entrega__estado="COMPLETADA",
                    entrega__trabajador_id=par["entrega__trabajador_id"],
                    inventario_id=par["inventario_id"],
                    entrega__fecha_entrega__date__lt=desde,
                )
                .values_list("cantidad", flat=True)
            )

            if len(historial) < MIN_ENTREGAS_HISTORICO_PROPIO:
                continue  # sin historial previo suficiente para juzgar (ej. trabajador nuevo)

            historial_f = [float(h) for h in historial]
            promedio_historico = mean(historial_f)
            desviacion_historica = pstdev(historial_f) if len(historial_f) > 1 else 0

            denominador = max(desviacion_historica, promedio_historico * 0.25, 0.5)
            z_score = (promedio_periodo - promedio_historico) / denominador

            if z_score < UMBRAL_Z_HISTORICO:
                continue

            candidatos.append({
                "trabajador_id": par["entrega__trabajador_id"],
                "inventario_id": par["inventario_id"],
                "promedio_periodo": round(promedio_periodo, 2),
                "promedio_historico": round(promedio_historico, 2),
                "z_score": round(z_score, 2),
                "num_entregas_periodo": num_entregas_periodo,
                "num_entregas_historicas": len(historial_f),
            })

        if not candidatos:
            return []

        trabajadores = {
            t.id: t for t in Trabajador.objects.filter(id__in=[c["trabajador_id"] for c in candidatos])
        }
        productos = {
            p.id: p for p in Inventario.objects.filter(id__in=[c["inventario_id"] for c in candidatos])
        }

        resultados = []
        for c in candidatos:
            trabajador = trabajadores.get(c["trabajador_id"])
            producto = productos.get(c["inventario_id"])
            if not trabajador or not producto:
                continue

            rut = trabajador.rut if mostrar_rut_completo else ReporteService.mascarar_rut(trabajador.rut)

            resultados.append({
                "trabajador_id": trabajador.id,
                "trabajador_nombre": trabajador.nombre_completo,
                "rut": rut,
                "cargo": trabajador.cargo,
                "inventario_id": producto.id,
                "producto_nombre": producto.nombre,
                "promedio_periodo": c["promedio_periodo"],
                "promedio_historico": c["promedio_historico"],
                "z_score": c["z_score"],
                "num_entregas_periodo": c["num_entregas_periodo"],
                "num_entregas_historicas": c["num_entregas_historicas"],
                "estado_revision": "revisar",
                "algoritmo": "Z-score respecto al historial propio",
            })

        resultados.sort(key=lambda r: r["z_score"], reverse=True)
        return resultados
