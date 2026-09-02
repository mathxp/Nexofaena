from django.core.management.base import BaseCommand

from nexofaena.models.entrega import DetalleEntregaEPP
from nexofaena.services.alerta_service import AlertaService


class Command(BaseCommand):
    """
    Regla Minera Teck: recorre los EPP entregados con control de vida útil
    (cascos, zapatos, etc.) y genera/actualiza alertas de vencimiento.

    Pensado para ejecutarse periódicamente (cron / Programador de tareas de
    Windows), ej: python manage.py verificar_vencimientos
    """

    help = "Genera alertas de vencimiento de vida útil de EPP entregados (Regla Minera Teck)."

    def handle(self, *args, **kwargs):
        detalles = DetalleEntregaEPP.objects.filter(
            fecha_vencimiento_vida_util__isnull=False,
            devuelto=False,
        ).select_related("inventario", "entrega", "entrega__trabajador", "entrega__bodega")

        total_evaluados = 0
        alertas_generadas = 0

        for detalle in detalles:
            total_evaluados += 1
            alerta = AlertaService.verificar_vencimiento_detalle(detalle)
            if alerta:
                alertas_generadas += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Revisión de vencimientos completada. "
                f"Detalles evaluados: {total_evaluados} | Alertas activas: {alertas_generadas}."
            )
        )
