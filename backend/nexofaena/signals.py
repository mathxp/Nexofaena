from django.db.models.signals import post_save
from django.dispatch import receiver

from nexofaena.models.alerta import Alerta
from nexofaena.services import n8n_service
from nexofaena.services.notificacion_service import NotificationService


@receiver(post_save, sender=Alerta)
def notificar_alerta_critica(sender, instance, created, **kwargs):
    """
    Engancha el bot de Telegram al motor de alertas existente
    (AlertaService) sin tocar sus puntos de creación: cualquier Alerta
    nueva de tipo crítico dispara una notificación automáticamente.
    """
    if not created:
        return

    NotificationService.notificar_alerta(instance)
    # Stock crítico: además se avisa a n8n para iniciar la reposición
    # automática (no hace nada si N8N_WEBHOOK_URL no está configurado).
    n8n_service.notificar_stock_critico(instance)
