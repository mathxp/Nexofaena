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
from statistics import mean, pstdev

from django.db.models import Count, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date

from nexofaena.models.entrega import DetalleEntregaEPP

DIAS_PERIODO_POR_DEFECTO = 30

MIN_CUADRILLA_PARA_DESVIACION_ESTADISTICA = 3


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
        """
        Una fila por trabajador (no una por trabajador x turno x producto,
        que con 40 personas eran cientos de filas): cuánto retiró, en
        cuántas visitas al pañol, en qué turno y sus productos principales.

        "Revisar" se decide por el TOTAL del trabajador frente a su cargo, no
        producto por producto: comparar "3 guantes vs. un promedio de 2" en
        grupos de 2-3 personas marcaba a casi todos. Los equipos devolutivos
        (radios) no cuentan: se prestan y vuelven, no se consumen.
        """
        desde, hasta = ReporteService._resolver_periodo(fecha_desde, fecha_hasta)

        detalles = (
            DetalleEntregaEPP.objects
            .filter(
                entrega__estado="COMPLETADA",
                entrega__fecha_entrega__date__gte=desde,
                entrega__fecha_entrega__date__lte=hasta,
                inventario__es_devolutivo=False,
            )
        )
        if rut:
            detalles = detalles.filter(entrega__trabajador__rut__icontains=rut)
        if turno in ("dia", "noche"):
            detalles = detalles.filter(entrega__turno=turno)
        if producto:
            detalles = detalles.filter(inventario__nombre__icontains=producto)

        # Por nombre de producto, no por fila de Inventario: el mismo
        # producto puede existir en las dos bodegas (o en varias tallas).
        filas = (
            detalles
            .values(
                "entrega__trabajador_id", "entrega__trabajador__rut", "entrega__trabajador__nombres",
                "entrega__trabajador__apellido_paterno", "entrega__trabajador__cargo",
                "entrega__turno", "inventario__nombre",
            )
            .annotate(cantidad=Sum("cantidad"))
        )

        # Visitas al pañol contadas sobre los MISMOS detalles filtrados: así,
        # filtrando por producto o turno, las unidades por visita cuadran.
        visitas = {
            (fila["entrega__trabajador_id"], fila["entrega__turno"]): fila["visitas"]
            for fila in (
                detalles.values("entrega__trabajador_id", "entrega__turno")
                .annotate(visitas=Count("entrega_id", distinct=True))
            )
        }

        trabajadores = {}
        for fila in filas:
            trabajador_id = fila["entrega__trabajador_id"]
            rut_trabajador = fila["entrega__trabajador__rut"]
            datos = trabajadores.setdefault(trabajador_id, {
                "trabajador_id": trabajador_id,
                "trabajador_nombre": f"{fila['entrega__trabajador__nombres']} {fila['entrega__trabajador__apellido_paterno']}",
                "rut": rut_trabajador if mostrar_rut_completo else ReporteService.mascarar_rut(rut_trabajador),
                "cargo": fila["entrega__trabajador__cargo"] or "Sin cargo",
                "unidades_por_turno": {"dia": 0.0, "noche": 0.0},
                "productos": {},
            })
            cantidad = float(fila["cantidad"])
            datos["unidades_por_turno"][fila["entrega__turno"]] = (
                datos["unidades_por_turno"].get(fila["entrega__turno"], 0.0) + cantidad
            )
            datos["productos"][fila["inventario__nombre"]] = datos["productos"].get(fila["inventario__nombre"], 0.0) + cantidad

        if not trabajadores:
            return {
                "periodo": {"fecha_desde": desde.isoformat(), "fecha_hasta": hasta.isoformat()},
                "filtros": {"rut": rut, "turno": turno, "producto": producto},
                "resumen_por_trabajador": [],
                "por_turno": [],
                "resumen_general": {
                    "total_unidades": 0, "trabajadores_evaluados": 0, "promedio_por_trabajador": 0,
                    "total_visitas": 0, "a_revisar": 0,
                },
            }

        resumen = []
        for trabajador_id, datos in trabajadores.items():
            total = sum(datos["unidades_por_turno"].values())
            visitas_dia = visitas.get((trabajador_id, "dia"), 0)
            visitas_noche = visitas.get((trabajador_id, "noche"), 0)
            num_visitas = visitas_dia + visitas_noche
            resumen.append({
                "trabajador_id": trabajador_id,
                "trabajador_nombre": datos["trabajador_nombre"],
                "rut": datos["rut"],
                "cargo": datos["cargo"],
                "turno_principal": "noche" if visitas_noche > visitas_dia else "dia",
                "total_unidades": round(total, 1),
                "num_visitas": num_visitas,
                "unidades_por_visita": round(total / num_visitas, 1) if num_visitas else 0,
                "unidades_por_turno": {k: round(v, 1) for k, v in datos["unidades_por_turno"].items()},
                "desglose_por_producto": [
                    {"producto_nombre": nombre, "cantidad": round(cantidad, 1)}
                    for nombre, cantidad in sorted(datos["productos"].items(), key=lambda p: p[1], reverse=True)
                ],
            })

        ReporteService._comparar_con_cargo(resumen)
        resumen.sort(key=lambda r: (r["estado_revision"] != "revisar", -r["total_unidades"]))

        por_turno = []
        for clave in ("dia", "noche"):
            del_turno = [r for r in resumen if r["unidades_por_turno"].get(clave, 0) > 0]
            if not del_turno:
                continue
            por_turno.append({
                "turno": clave,
                "unidades": round(sum(r["unidades_por_turno"][clave] for r in del_turno), 1),
                "visitas": sum(visitas.get((r["trabajador_id"], clave), 0) for r in del_turno),
                "trabajadores": len(del_turno),
            })

        total_unidades = sum(r["total_unidades"] for r in resumen)
        return {
            "periodo": {"fecha_desde": desde.isoformat(), "fecha_hasta": hasta.isoformat()},
            "filtros": {"rut": rut, "turno": turno, "producto": producto},
            "resumen_por_trabajador": resumen,
            "por_turno": por_turno,
            "resumen_general": {
                "total_unidades": round(total_unidades, 1),
                "trabajadores_evaluados": len(resumen),
                "promedio_por_trabajador": round(total_unidades / len(resumen), 1),
                "total_visitas": sum(r["num_visitas"] for r in resumen),
                "a_revisar": sum(1 for r in resumen if r["estado_revision"] == "revisar"),
            },
        }

    @staticmethod
    def _comparar_con_cargo(resumen):
        """Marca "revisar" a quien retiró claramente más que su cargo: al
        menos una desviación estándar sobre el promedio Y 1,5 veces el
        promedio (misma regla que el Panel Gerencial). Con menos de
        MIN_CUADRILLA_PARA_DESVIACION_ESTADISTICA personas en el cargo no hay
        con quién comparar y queda "normal"."""
        por_cargo = {}
        for r in resumen:
            por_cargo.setdefault(r["cargo"], []).append(r)

        for grupo in por_cargo.values():
            totales = [r["total_unidades"] for r in grupo]
            promedio = mean(totales)
            umbral = max(promedio + pstdev(totales), promedio * 1.5)
            for r in grupo:
                r["promedio_cargo"] = round(promedio, 1)
                r["companeros_en_cargo"] = len(grupo)
                destaca = len(grupo) >= MIN_CUADRILLA_PARA_DESVIACION_ESTADISTICA and r["total_unidades"] > umbral
                r["estado_revision"] = "revisar" if destaca else "normal"

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
