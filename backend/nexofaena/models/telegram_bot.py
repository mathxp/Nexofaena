from django.db import models
from django.utils import timezone

from .usuario import Usuario


class TelegramVinculo(models.Model):
    """
    Une un chat privado de Telegram (DM con el bot) a una cuenta real de
    NexoFaena. Es la frontera de autorización del bot: solo alguien que ya
    tiene credenciales válidas del sistema puede generar un código y
    vincularse, así que no se necesita un control de rol aparte para usar
    los comandos.
    """
    usuario = models.OneToOneField(
        Usuario, on_delete=models.CASCADE, related_name="telegram_vinculo",
        verbose_name="Usuario NexoFaena",
    )
    chat_id = models.BigIntegerField(unique=True, verbose_name="Chat ID de Telegram")
    telegram_username = models.CharField(max_length=64, blank=True, null=True, verbose_name="@usuario de Telegram")
    vinculado_en = models.DateTimeField(auto_now_add=True, verbose_name="Vinculado en")

    class Meta:
        db_table = "telegram_vinculo"
        verbose_name = "Vínculo Telegram"
        verbose_name_plural = "Vínculos Telegram"

    def __str__(self):
        return f"{self.usuario.username} <-> chat {self.chat_id}"


class TelegramCodigoVinculacion(models.Model):
    """Código de un solo uso (TTL corto) que el usuario genera logueado en la
    app y luego envía al bot para probar que es dueño de ambas cuentas."""

    usuario = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name="telegram_codigos",
        verbose_name="Usuario NexoFaena",
    )
    codigo = models.CharField(max_length=8, unique=True, verbose_name="Código")
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Creado en")
    expira_en = models.DateTimeField(verbose_name="Expira en")
    usado = models.BooleanField(default=False, verbose_name="¿Usado?")

    class Meta:
        db_table = "telegram_codigo_vinculacion"
        verbose_name = "Código de Vinculación Telegram"
        verbose_name_plural = "Códigos de Vinculación Telegram"

    def __str__(self):
        return f"{self.codigo} ({self.usuario.username})"

    @property
    def vigente(self):
        return not self.usado and timezone.now() < self.expira_en


class TelegramEstadoBot(models.Model):
    """
    Fila única (pk=1): guarda el offset de `getUpdates` del long-polling
    para que un reinicio del comando `telegram_bot` no reprocese ni pierda
    mensajes que llegaron mientras estaba caído.
    """
    ultimo_update_id = models.BigIntegerField(default=0, verbose_name="Último update_id procesado")

    class Meta:
        db_table = "telegram_estado_bot"
        verbose_name = "Estado del Bot de Telegram"
        verbose_name_plural = "Estado del Bot de Telegram"
