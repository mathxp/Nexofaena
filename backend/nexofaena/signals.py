from django.db.models.signals import post_save
from django.dispatch import receiver

from nexofaena.models.alerta import Alerta
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
