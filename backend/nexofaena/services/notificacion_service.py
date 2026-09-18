import html
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{metodo}"

ICONOS_POR_TIPO = {
    "STOCK_CRITICO": "🔴",
    "ANOMALIA_CONSUMO": "🕵️",
    "INTENTO_SUPLANTACION": "🚫",
}

# Menú de comandos que Telegram muestra al tocar "/" en el chat con el bot
# (setMyCommands). Vive aquí, junto al resto del transporte, para que quede
# en un solo lugar si mañana se agrega/renombra un comando.
COMANDOS_BOT = [
    {"command": "vincular", "description": "Vincula tu cuenta NexoFaena con un código"},
    {"command": "stock", "description": "Stock de un producto por bodega"},
    {"command": "alertas", "description": "Alertas críticas abiertas"},
    {"command": "historial", "description": "Últimas entregas de un trabajador (por RUT)"},
    {"command": "atender", "description": "Marca una alerta como atendida"},
    {"command": "ayuda", "description": "Lista de comandos disponibles"},
]


def escapar_html(texto):
    """
    Todo texto dinámico (nombre de producto, RUT, mensaje de alerta) debe
    pasar por acá antes de insertarse en un mensaje con parse_mode HTML: a
    diferencia del Markdown clásico de Telegram —que rompía con un solo "_"
    suelto, como pasó en producción—, HTML solo exige escapar &, < y >, así
    que es imposible que un nombre de producto cualquiera vuelva a tumbar un
    envío.
    """
    return html.escape(str(texto), quote=False)


class NotificationService:
    """
    Cliente de la API de Telegram: notificaciones push del motor de alertas
    (AlertaService) y transporte de respuestas del bot conversacional
    (telegram_bot_service.py). Se usa Telegram y no WhatsApp Business (Meta)
    porque solo requiere un bot token gratuito (@BotFather), sin
    verificación de cuenta de negocio ni aprobación previa de plantillas.

    Sin TELEGRAM_BOT_TOKEN configurado, todo método es un no-op silencioso:
    el resto del sistema debe seguir funcionando igual aunque el bot no
    esté configurado todavía.
    """

    # Tipos de Alerta que ameritan interrumpir a un humano fuera del
    # sistema. El resto (vencimiento, mantención, cierre de turno) ya se ve
    # en el Dashboard/Alertas y no necesita empujar una notificación.
    TIPOS_NOTIFICABLES = {"STOCK_CRITICO", "ANOMALIA_CONSUMO", "INTENTO_SUPLANTACION"}

    @staticmethod
    def notificar_alerta(alerta):
        if alerta.tipo_alerta not in NotificationService.TIPOS_NOTIFICABLES:
            return False

        icono = ICONOS_POR_TIPO.get(alerta.tipo_alerta, "⚠️")
        texto = f"{icono} <b>{escapar_html(alerta.get_tipo_alerta_display())}</b>\n{escapar_html(alerta.mensaje)}"

        return NotificationService.enviar_telegram(texto, parse_mode="HTML")

    @staticmethod
    def enviar_telegram(texto, chat_id=None, parse_mode=None, teclado=None):
        """
        chat_id=None envía al canal/grupo de alertas configurado
        (TELEGRAM_CHAT_ID); el bot conversacional pasa el chat_id privado
        de quien escribió, para responderle a esa persona y no al grupo.

        teclado: lista de filas de botones inline, ej.
        [[{"text": "✅ Atender #142", "callback_data": "atender:142"}]].
        """
        payload = {"text": texto}

        if parse_mode:
            payload["parse_mode"] = parse_mode
        if teclado:
            payload["reply_markup"] = {"inline_keyboard": teclado}

        return NotificationService._llamar("sendMessage", chat_id=chat_id, **payload)

    @staticmethod
    def responder_callback(callback_query_id, texto=None):
        """
        Toda pulsación de un botón inline (callback_query) DEBE contestarse
        con answerCallbackQuery, aunque sea vacía: si no, Telegram deja la
        rueda de "cargando" girando sobre el botón indefinidamente en el
        celular del usuario.
        """
        payload = {"callback_query_id": callback_query_id}
        if texto:
            payload["text"] = texto

        return NotificationService._llamar("answerCallbackQuery", **payload)

    @staticmethod
    def enviar_accion_escribiendo(chat_id):
        """Muestra 'escribiendo...' mientras se arma la respuesta (consultas
        con varias tablas involucradas, ej. /historial). Puramente
        cosmético: si falla, no importa."""
        return NotificationService._llamar("sendChatAction", chat_id=chat_id, action="typing")

    @staticmethod
    def configurar_comandos_bot():
        """
        Registra el menú de comandos (setMyCommands) para que aparezca el
        autocompletado nativo de Telegram al escribir "/". Se llama al
        arrancar el management command telegram_bot: idempotente, así que
        no hace daño repetirlo cada vez que el bot se reinicia, y mantiene
        el menú sincronizado si se agrega o renombra un comando en código.
        """
        return NotificationService._llamar("setMyCommands", commands=COMANDOS_BOT)

    @staticmethod
    def _llamar(metodo, chat_id=None, **campos):
        token = settings.TELEGRAM_BOT_TOKEN

        if not settings.TELEGRAM_NOTIFICACIONES_ACTIVAS or not token:
            return False

        # sendMessage/sendChatAction necesitan chat_id; setMyCommands y
        # answerCallbackQuery no.
        cuerpo = dict(campos)
        if chat_id is not None or metodo in ("sendMessage", "sendChatAction"):
            cuerpo["chat_id"] = chat_id or settings.TELEGRAM_CHAT_ID
            if not cuerpo["chat_id"]:
                return False

        payload = json.dumps(cuerpo).encode("utf-8")

        request = urllib.request.Request(
            TELEGRAM_API_URL.format(token=token, metodo=metodo),
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status == 200
        except urllib.error.HTTPError as err:
            # Telegram manda el motivo real en el body (ej. grupo migrado a
            # supergrupo, con el chat_id nuevo) — sin leerlo, el log solo
            # dice "Bad Request" y hay que adivinar por qué falló.
            detalle = err.read().decode("utf-8", errors="replace")
            logger.warning("Fallo llamando a Telegram %s (%s): %s", metodo, err.code, detalle)
            return False
        except urllib.error.URLError as err:
            # Un fallo de red nunca debe tumbar el flujo que generó el
            # envío (una entrega, un ajuste de auditoría, un comando del bot).
            logger.warning("Fallo llamando a Telegram %s: %s", metodo, err)
            return False
