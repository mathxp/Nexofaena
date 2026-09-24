import time

from django.core.management.base import BaseCommand

from nexofaena.services.dashboard_service import DashboardService


class Command(BaseCommand):
    """
    Reentrena Random Forest, Regresión Logística y K-Means (los tres modelos
    del Dashboard Gerencial) y repuebla el cache, sin esperar a que lo pida
    un usuario ni a que el TTL expire.

    Pensado para correr como Render Cron Job cada 8 minutos (el cache dura
    10 min — CACHE_TTL_SEGUNDOS en dashboard_service.py — así que 8 min deja
    margen de sobra para que el cron gane la carrera): en Render, Dashboard
    -> New -> Cron Job, mismo repo, mismo build command que el servicio web
    (pip install -r requirements.txt), y como comando:
        python manage.py recalcular_dashboard
    con el schedule: */8 * * * *

    Ej: python manage.py recalcular_dashboard
    """

    help = "Reentrena los modelos ML del Dashboard Gerencial y repuebla el cache (pensado para Render Cron Job)."

    def handle(self, *args, **kwargs):
        inicio = time.monotonic()

        DashboardService.recalcular_cache()

        duracion = time.monotonic() - inicio

        self.stdout.write(
            self.style.SUCCESS(
                f"Cache del Dashboard Gerencial recalculado en {duracion:.1f}s."
            )
        )
