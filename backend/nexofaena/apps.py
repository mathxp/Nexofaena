import os
import sys
import threading

from django.apps import AppConfig


class NexofaenaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'nexofaena'

    def ready(self):
        from nexofaena import signals  # noqa: F401  (registra el receptor post_save de Alerta -> bot Telegram)

        # Precalienta el dashboard (Random Forest + Regresión Logística +
        # K-Means) al arrancar el servidor, no cuando el primer usuario del
        # día entra al sistema. numpy/scikit-learn pagan un costo de
        # "arranque en frío" de varios segundos la primera vez que se
        # entrena algo en un proceso nuevo (no depende de cuántos datos
        # haya); sin esto, esa demora la paga el primer usuario que carga
        # el dashboard después de cada reinicio del servidor.
        es_runserver = "runserver" in sys.argv
        # servir_produccion.py (Waitress) marca esta variable antes de
        # levantar la app: sin esto, el precalentamiento nunca corría bajo
        # Waitress (solo miraba sys.argv, y ahí no aparece "runserver"), así
        # que el primer usuario que abriera el Dashboard después de cada
        # reinicio pagaba el arranque en frío que este precalentamiento
        # existe justamente para evitar.
        es_produccion = os.environ.get("NEXOFAENA_SERVIDOR") == "waitress"

        if not (es_runserver or es_produccion):
            return

        # El autoreloader de runserver ejecuta ready() dos veces (proceso
        # vigilante + proceso hijo real que sirve requests): solo tiene
        # sentido precalentar en el hijo. Waitress no tiene autoreloader,
        # así que esta comprobación solo aplica al camino de runserver.
        if es_runserver and os.environ.get("RUN_MAIN") != "true":
            return

        def _precalentar():
            try:
                from nexofaena.services.dashboard_service import DashboardService
                DashboardService.obtener_dashboard()
                DashboardService.obtener_ml_avanzado()
            except Exception:
                # BD recién creada sin datos, o cualquier otro problema
                # transitorio: no debe impedir que el servidor arranque.
                pass

        threading.Thread(target=_precalentar, daemon=True).start()