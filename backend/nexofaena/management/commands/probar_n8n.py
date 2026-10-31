"""
Envía a n8n un aviso de stock crítico de prueba, con un producto real del
inventario, sin modificar la base (no crea alertas ni toca el stock). Sirve
para armar y probar el flujo en n8n con datos reales.

Uso:
    python manage.py probar_n8n                      # producto con menos stock
    python manage.py probar_n8n --codigo RM-0003     # un producto puntual
    python manage.py probar_n8n --solo-mostrar       # imprime el JSON, no envía

Necesita N8N_WEBHOOK_URL y N8N_TOKEN (por variable de entorno o .env).
"""
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F
from django.utils import timezone

from nexofaena.models.alerta import Alerta, TipoAlerta
from nexofaena.models.inventario import Inventario
from nexofaena.services.n8n_service import _enviar, armar_aviso_stock_critico


class Command(BaseCommand):
    help = "Envía a n8n un aviso de stock crítico de prueba (sin modificar la base)."

    def add_arguments(self, parser):
        parser.add_argument("--codigo", help="Código del producto (ej. RM-0003). Por defecto, el de menor stock relativo.")
        parser.add_argument("--solo-mostrar", action="store_true", help="Solo imprime el JSON, no lo envía.")

    def handle(self, *args, **options):
        productos = Inventario.objects.select_related("bodega").filter(estado=True, es_devolutivo=False)
        if options["codigo"]:
            producto = productos.filter(codigo=options["codigo"]).first()
        else:
            producto = (
                productos.filter(stock_minimo__gt=0)
                .annotate(margen=F("stock_actual") - F("stock_minimo"))
                .order_by("margen")
                .first()
            )
        if producto is None:
            raise CommandError("No encontré ese producto (o el inventario está vacío).")

        # Alerta en memoria (no se guarda): id 0 marca que es una prueba.
        alerta = Alerta(
            id=0, inventario=producto, bodega=producto.bodega, tipo_alerta=TipoAlerta.STOCK_CRITICO,
            fecha_alerta=timezone.now(),
            mensaje=f"[PRUEBA] {producto.nombre}: stock {producto.stock_actual}, mínimo {producto.stock_minimo}.",
        )
        aviso = armar_aviso_stock_critico(alerta)
        aviso["prueba"] = True

        self.stdout.write(json.dumps(aviso, ensure_ascii=False, indent=2))
        if options["solo_mostrar"]:
            return

        if not settings.N8N_WEBHOOK_URL:
            raise CommandError("Falta N8N_WEBHOOK_URL (la URL del nodo Webhook de n8n).")

        if _enviar(aviso):
            self.stdout.write(self.style.SUCCESS("Aviso enviado a n8n correctamente."))
        else:
            raise CommandError("n8n no respondió OK. Revisa la URL, que el flujo esté activo o en modo de prueba, y el token.")
