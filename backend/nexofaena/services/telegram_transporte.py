"""
Despacha un Update crudo de Telegram (mismo formato venga por webhook o por
getUpdates/long-polling) hacia TelegramBotService y responde. Vive separado
del management command (telegram_bot, para LAN/desarrollo) y de la vista
de webhook (para producción en la nube) para que ambos compartan
exactamente la misma lógica de despacho sin duplicarla.
"""
from nexofaena.services.notificacion_service import NotificationService
from nexofaena.services.telegram_bot_service import TelegramBotService


def procesar_update(update):
    if "callback_query" in update:
        _procesar_callback(update["callback_query"])
        return

    mensaje = update.get("message")
    if not mensaje or "text" not in mensaje:
        return

    chat = mensaje.get("chat", {})
    if chat.get("type") != "private":
        # Comandos interactivos solo por DM: el grupo de TELEGRAM_CHAT_ID
        # es de solo lectura (alertas automáticas de NotificationService).
        return

    chat_id = chat["id"]
    texto = mensaje["text"]
    username = mensaje.get("from", {}).get("username")

    NotificationService.enviar_accion_escribiendo(chat_id)
    respuesta = TelegramBotService.procesar_mensaje(chat_id, texto, username)
    _enviar_respuesta(chat_id, respuesta)


def _procesar_callback(callback_query):
    mensaje = callback_query.get("message") or {}
    chat_id = (mensaje.get("chat") or {}).get("id")

    if not chat_id:
        return

    toast, respuesta = TelegramBotService.procesar_callback(chat_id, callback_query.get("data"))
    NotificationService.responder_callback(callback_query["id"], toast)
    _enviar_respuesta(chat_id, respuesta)


def _enviar_respuesta(chat_id, respuesta):
    if not respuesta:
        return

    texto, teclado = respuesta
    NotificationService.enviar_telegram(texto, chat_id=chat_id, parse_mode="HTML", teclado=teclado)
