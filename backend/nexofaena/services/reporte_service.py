"""
Reporte de consumo de EPP por trabajador y turno.

Requerimiento del stakeholder (Carlos Guerrero, RentaMaq): "no hay una
radiografía de lo que tiene y lo que se ha entregado". No captura datos
nuevos: agrega y expone lo que ya registra cada entrega (trabajador,
producto, cantidad, fecha/hora -> turno).

El reporte es informativo, no punitivo: un trabajador que se aleja del
promedio de su cuadrilla queda marcado como "revisar", nunca "sospechoso".
"cuadrilla" se aproxima con el campo Trabajador.cargo (no existe un modelo
de cuadrilla propio todavía y el requerimiento pide no capturar nada nuevo).
"""

from datetime import timedelta
from decimal import Decimal
from statistics import mean, pstdev

from django.db.models import Count, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date

from nexofaena.models.entrega import DetalleEntregaEPP, EntregaEPP

DIAS_PERIODO_POR_DEFECTO = 30

MIN_CUADRILLA_PARA_DESVIACION_ESTADISTICA = 3
FACTOR_DESVIACION_GRUPO_PEQUENO = 1.5  # 50% sobre el promedio cuando hay <3 pares


class ReporteService:

    @staticmethod
    def mascarar_rut(rut):
        """Oculta el cuerpo del RUT, dejando solo los últimos 4 caracteres
        visibles (ej. '12345678-9' -> '******78-9'). Se usa para cualquier
        rol sin permiso explícito para ver el RUT completo."""
        if not rut or len(rut) <= 4:
            return rut or ""
        return "*" * (len(rut) - 4) + rut[-4:]

    @staticmethod
    def _resolver_periodo(fecha_desde, fecha_hasta):
        hoy = timezone.localdate()

        desde = parse_date(fecha_desde) if fecha_desde else None
        hasta = parse_date(fecha_hasta) if fecha_hasta else None

        if not hasta:
            hasta = hoy
        if not desde:
            desde = hasta - timedelta(days=DIAS_PERIODO_POR_DEFECTO)

        if desde > hasta:
            desde, hasta = hasta, desde

        return desde, hasta

    @staticmethod
    def consumo_epp_por_turno(fecha_desde=None, fecha_hasta=None, rut=None,
                               turno=None, producto=None, mostrar_rut_completo=False):
        desde, hasta = ReporteService._resolver_periodo(fecha_desde, fecha_hasta)

        detalles = (
            DetalleEntregaEPP.objects
            .filter(
                entrega__estado="COMPLETADA",
                entrega__fecha_entrega__date__gte=desde,
                entrega__fecha_entrega__date__lte=hasta,
            )
        )

        if rut:
            detalles = detalles.filter(entrega__trabajador__rut__icontains=rut)
        if turno in ("dia", "noche"):
            detalles = detalles.filter(entrega__turno=turno)
        if producto:
            # Texto, no ID: el mismo producto puede existir como filas de
            # Inventario distintas por bodega y un trabajador puede recibirlo
            # de más de una.
            detalles = detalles.filter(inventario__nombre__icontains=producto)

        filas_agrupadas = (
            detalles
            .values(
                "entrega__trabajador_id",
                "entrega__trabajador__rut",
                "entrega__trabajador__nombres",
                "entrega__trabajador__apellido_paterno",
                "entrega__trabajador__cargo",
                "entrega__turno",
                "inventario_id",
                "inventario__nombre",
            )
            .annotate(cantidad=Sum("cantidad"))
            # trabajador_id después del apellido: mantiene el orden alfabético
            # para mostrar, pero garantiza que las filas de una misma persona
            # queden contiguas incluso si dos trabajadores comparten apellido
            # (el frontend agrupa visualmente por trabajador+turno asumiendo
            # que las filas de cada grupo vienen una detrás de otra).
            .order_by(
                "entrega__trabajador__apellido_paterno",
                "entrega__trabajador_id",
                "entrega__turno",
                "inventario__nombre",
            )
        )

        filas_crudas = list(filas_agrupadas)

        if not filas_crudas:
            return {
                "periodo": {"fecha_desde": desde.isoformat(), "fecha_hasta": hasta.isoformat()},
                "filtros": {"rut": rut, "turno": turno, "producto": producto},
                "filas": [],
                "resumen_por_trabajador": [],
                "resumen_general": {"total_unidades": 0, "trabajadores_evaluados": 0, "promedio_por_trabajador": 0},
            }

        # Promedio de la "cuadrilla" (mismo cargo) por producto + turno, para
        # poder comparar a cada trabajador contra sus pares equivalentes.
        cantidades_por_grupo = {}
        for fila in filas_crudas:
            clave = (fila["inventario_id"], fila["entrega__turno"], fila["entrega__trabajador__cargo"])
            cantidades_por_grupo.setdefault(clave, []).append(float(fila["cantidad"]))

        promedio_grupo = {}
        umbral_grupo = {}
        for clave, cantidades in cantidades_por_grupo.items():
            promedio = mean(cantidades)
            promedio_grupo[clave] = promedio

            if len(cantidades) >= MIN_CUADRILLA_PARA_DESVIACION_ESTADISTICA:
                desviacion = pstdev(cantidades)
                umbral_grupo[clave] = promedio + max(1, desviacion)
            else:
                # Muy pocos pares en la cuadrilla: la desviación estándar no es
                # confiable, se usa un umbral simple por sobre el promedio.
                umbral_grupo[clave] = promedio * FACTOR_DESVIACION_GRUPO_PEQUENO

        filas = []
        for fila in filas_crudas:
            clave = (fila["inventario_id"], fila["entrega__turno"], fila["entrega__trabajador__cargo"])
            cantidad = float(fila["cantidad"])
            promedio_cuadrilla = round(promedio_grupo[clave], 2)
            pares_en_cuadrilla = len(cantidades_por_grupo[clave])

            fuera_de_promedio = (
                pares_en_cuadrilla > 1
                and cantidad > umbral_grupo[clave]
            )

            rut_trabajador = fila["entrega__trabajador__rut"]

            filas.append({
                "trabajador_id": fila["entrega__trabajador_id"],
                "trabajador_nombre": f"{fila['entrega__trabajador__nombres']} {fila['entrega__trabajador__apellido_paterno']}",
                "rut": rut_trabajador if mostrar_rut_completo else ReporteService.mascarar_rut(rut_trabajador),
                "cargo": fila["entrega__trabajador__cargo"],
                "turno": fila["entrega__turno"],
                "inventario_id": fila["inventario_id"],
                "producto_nombre": fila["inventario__nombre"],
                "cantidad": cantidad,
                "promedio_cuadrilla": promedio_cuadrilla,
                "pares_en_cuadrilla": pares_en_cuadrilla,
                "estado_revision": "revisar" if fuera_de_promedio else "normal",
            })

        # Conteo de entregas (visitas) distintas por trabajador/turno, para
        # expresar el "promedio por turno" como unidades por visita al pañol.
        entregas_por_turno = (
            EntregaEPP.objects
            .filter(estado="COMPLETADA", fecha_entrega__date__gte=desde, fecha_entrega__date__lte=hasta)
            .values("trabajador_id", "turno")
            .annotate(num_entregas=Count("id", distinct=True))
        )
        num_entregas_map = {
            (fila["trabajador_id"], fila["turno"]): fila["num_entregas"]
            for fila in entregas_por_turno
        }

        resumen_por_trabajador = ReporteService._agregar_por_trabajador(filas, num_entregas_map)

        total_unidades = sum(f["cantidad"] for f in filas)
        trabajadores_evaluados = len(resumen_por_trabajador)

        return {
            "periodo": {"fecha_desde": desde.isoformat(), "fecha_hasta": hasta.isoformat()},
            "filtros": {"rut": rut, "turno": turno, "producto": producto},
            "filas": filas,
            "resumen_por_trabajador": resumen_por_trabajador,
            "resumen_general": {
                "total_unidades": round(total_unidades, 1),
                "trabajadores_evaluados": trabajadores_evaluados,
                "promedio_por_trabajador": round(total_unidades / trabajadores_evaluados, 2) if trabajadores_evaluados else 0,
            },
        }

    @staticmethod
    def _agregar_por_trabajador(filas, num_entregas_map):
        por_trabajador = {}

        for fila in filas:
            trabajador_id = fila["trabajador_id"]
            grupo = por_trabajador.setdefault(trabajador_id, {
                "trabajador_id": trabajador_id,
                "trabajador_nombre": fila["trabajador_nombre"],
                "rut": fila["rut"],
                "cargo": fila["cargo"],
                "total_unidades": 0.0,
                "productos": {},
                "unidades_por_turno": {"dia": 0.0, "noche": 0.0},
                "tiene_desviacion": False,
            })

            grupo["total_unidades"] += fila["cantidad"]
            grupo["unidades_por_turno"][fila["turno"]] = (
                grupo["unidades_por_turno"].get(fila["turno"], 0.0) + fila["cantidad"]
            )

            producto = grupo["productos"].setdefault(fila["inventario_id"], {
                "inventario_id": fila["inventario_id"],
                "producto_nombre": fila["producto_nombre"],
                "cantidad": 0.0,
            })
            producto["cantidad"] += fila["cantidad"]

            if fila["estado_revision"] == "revisar":
                grupo["tiene_desviacion"] = True

        resultado = []
        for trabajador_id, grupo in por_trabajador.items():
            promedio_por_turno = {}
            for turno in ("dia", "noche"):
                num_entregas = num_entregas_map.get((trabajador_id, turno), 0)
                total_turno = grupo["unidades_por_turno"].get(turno, 0.0)
                promedio_por_turno[turno] = round(total_turno / num_entregas, 2) if num_entregas else 0

            resultado.append({
                "trabajador_id": trabajador_id,
                "trabajador_nombre": grupo["trabajador_nombre"],
                "rut": grupo["rut"],
                "cargo": grupo["cargo"],
                "total_unidades": round(grupo["total_unidades"], 1),
                "desglose_por_producto": sorted(
                    grupo["productos"].values(), key=lambda p: p["cantidad"], reverse=True
                ),
                "promedio_por_turno": promedio_por_turno,
                "estado_revision": "revisar" if grupo["tiene_desviacion"] else "normal",
            })

        resultado.sort(key=lambda r: r["total_unidades"], reverse=True)
        return resultado

    @staticmethod
    def prestamos_pendientes(mostrar_rut_completo=False):
        """
        Requerimiento directo del stakeholder: "no saber quién tiene una
        radio que nunca devolvió". Reutiliza el mismo filtro que ya usa
        DetalleEntregaEPPViewSet (unidad_activo asignado y aún no devuelto),
        pero agregado por trabajador para un reporte de gestión en vez de un
        listado plano de ítems.
        """
        pendientes = (
            DetalleEntregaEPP.objects
            .filter(unidad_activo__isnull=False, devuelto=False, entrega__estado="COMPLETADA")
            .select_related("entrega__trabajador", "inventario", "unidad_activo", "entrega__bodega")
            .order_by("entrega__trabajador_id", "entrega__fecha_entrega")
        )

        por_trabajador = {}
        for detalle in pendientes:
            trabajador = detalle.entrega.trabajador
            grupo = por_trabajador.setdefault(trabajador.id, {
                "trabajador_id": trabajador.id,
                "trabajador_nombre": trabajador.nombre_completo,
                "rut": trabajador.rut if mostrar_rut_completo else ReporteService.mascarar_rut(trabajador.rut),
                "cargo": trabajador.cargo,
                "items": [],
            })

            dias_pendiente = (timezone.now() - detalle.entrega.fecha_entrega).days

            grupo["items"].append({
                "detalle_id": detalle.id,
                "producto_nombre": detalle.inventario.nombre,
                "unidad_codigo": detalle.unidad_activo.codigo,
                "bodega_nombre": detalle.entrega.bodega.nombre,
                "fecha_entrega": detalle.entrega.fecha_entrega.isoformat(),
                "dias_pendiente": dias_pendiente,
            })

        resultado = sorted(
            por_trabajador.values(),
            key=lambda g: max((i["dias_pendiente"] for i in g["items"]), default=0),
            reverse=True,
        )

        for grupo in resultado:
            grupo["items"].sort(key=lambda i: i["dias_pendiente"], reverse=True)
            grupo["total_pendientes"] = len(grupo["items"])

        return {
            "trabajadores": resultado,
            "total_trabajadores": len(resultado),
            "total_items": sum(g["total_pendientes"] for g in resultado),
        }
