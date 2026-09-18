import random
import string
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from nexofaena.models.alerta import Alerta, TipoAlerta
from nexofaena.models.entrega import EntregaEPP
from nexofaena.models.inventario import Inventario
from nexofaena.models.telegram_bot import TelegramCodigoVinculacion, TelegramVinculo
from nexofaena.models.trabajador import Trabajador
from nexofaena.services.notificacion_service import escapar_html

MAX_RESULTADOS = 8


def _r(texto, teclado=None):
    """Toda respuesta del bot viaja como (texto HTML, teclado inline u
    None), para que el transporte (management command) solo tenga que
    llamar a NotificationService.enviar_telegram(*respuesta, chat_id=...)
    sin conocer los detalles de cada comando."""
    return (texto, teclado)


class TelegramBotService:
    """
    Lógica del bot conversacional de Telegram: qué responde a cada comando
    (o botón) que usa un supervisor/prevencionista ya vinculado. Separado
    del transporte (long-polling en management/commands/telegram_bot.py)
    para poder probarlo sin red y para no depender de si el día de mañana
    se cambia a webhook.

    Todo el texto que sale de acá va en HTML (parse_mode="HTML") con los
    valores dinámicos pasados por escapar_html — así un nombre de producto
    o una observación con "&", "<" o cualquier símbolo no puede romper el
    envío, a diferencia del Markdown clásico que se usó al principio.
    """

    # --- Generación de código (llamado desde la vista autenticada) ---

    @staticmethod
    def generar_codigo_vinculacion(usuario):
        TelegramCodigoVinculacion.objects.filter(usuario=usuario, usado=False).delete()

        codigo = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        ttl_minutos = getattr(settings, "TELEGRAM_CODIGO_TTL_MINUTOS", 10)

        return TelegramCodigoVinculacion.objects.create(
            usuario=usuario,
            codigo=codigo,
            expira_en=timezone.now() + timedelta(minutes=ttl_minutos),
        )

    # --- Punto de entrada del bot: mensajes de texto ---

    @staticmethod
    def procesar_mensaje(chat_id, texto, telegram_username=None):
        texto = (texto or "").strip()
        if not texto:
            return None

        partes = texto.split(maxsplit=1)
        comando = partes[0].lower().split("@")[0]  # "/stock@MiBot" -> "/stock"
        argumento = partes[1].strip() if len(partes) > 1 else ""

        if comando in ("/start", "/vincular"):
            return TelegramBotService._vincular(chat_id, argumento, telegram_username)

        usuario = TelegramBotService._usuario_vinculado(chat_id)
        if not usuario:
            return _r(
                "🔒 Esta cuenta de Telegram todavía no está vinculada a NexoFaena.\n"
                "Genera un código desde la app (Alertas → Vincular Telegram) y envíamelo con:\n"
                "<code>/vincular CODIGO</code>"
            )

        if comando in ("/ayuda", "/help"):
            return TelegramBotService._ayuda()
        if comando == "/stock":
            return TelegramBotService._stock(argumento)
        if comando == "/alertas":
            return TelegramBotService._alertas()
        if comando == "/historial":
            return TelegramBotService._historial(argumento)
        if comando == "/atender":
            return TelegramBotService._atender(argumento, usuario)

        return _r(f"No reconozco «{escapar_html(comando)}». Escribe /ayuda para ver los comandos disponibles.")

    # --- Punto de entrada del bot: botones inline (callback_query) ---

    @staticmethod
    def procesar_callback(chat_id, callback_data):
        """
        callback_data viaja como "accion:argumento" (ej. "atender:142"),
        generado por _alertas() al armar el teclado. Devuelve
        (toast_para_answerCallbackQuery, respuesta_como_mensaje_nuevo).
        """
        usuario = TelegramBotService._usuario_vinculado(chat_id)
        if not usuario:
            return "Vincula tu cuenta primero con /vincular.", None

        accion, _, argumento = (callback_data or "").partition(":")

        if accion == "atender":
            respuesta = TelegramBotService._atender(argumento, usuario)
            return "Listo ✅", respuesta

        return "Acción no reconocida.", None

    # --- Comandos ---

    @staticmethod
    def _usuario_vinculado(chat_id):
        vinculo = (
            TelegramVinculo.objects.select_related("usuario")
            .filter(chat_id=chat_id)
            .first()
        )
        return vinculo.usuario if vinculo else None

    @staticmethod
    def _vincular(chat_id, codigo, telegram_username):
        if not codigo:
            return _r(
                "👋 <b>Bienvenido al bot de NexoFaena SGI.</b>\n"
                "Para usarlo, primero vincula tu cuenta: genera un código desde la app "
                "(sección Alertas → Vincular Telegram) y envíamelo así:\n"
                "<code>/vincular CODIGO</code>"
            )

        ya_vinculado = TelegramVinculo.objects.filter(chat_id=chat_id).select_related("usuario").first()
        if ya_vinculado:
            return _r(f"Esta cuenta de Telegram ya está vinculada a <b>{escapar_html(ya_vinculado.usuario.username)}</b>.")

        codigo = codigo.strip().upper()
        entrada = TelegramCodigoVinculacion.objects.filter(codigo=codigo, usado=False).first()

        if not entrada or not entrada.vigente:
            return _r("❌ Código inválido o expirado. Genera uno nuevo desde la app e inténtalo de nuevo.")

        TelegramVinculo.objects.update_or_create(
            usuario=entrada.usuario,
            defaults={"chat_id": chat_id, "telegram_username": telegram_username},
        )

        entrada.usado = True
        entrada.save(update_fields=["usado"])

        nombre = entrada.usuario.first_name or entrada.usuario.username

        return _r(
            f"✅ Cuenta vinculada correctamente, <b>{escapar_html(nombre)}</b>.\n"
            "Escribe /ayuda para ver qué puedo hacer por ti."
        )

    @staticmethod
    def _ayuda():
        return _r(
            "🤖 <b>Comandos disponibles</b>\n\n"
            "<code>/stock &lt;texto&gt;</code> — stock de un producto por bodega\n"
            "<code>/alertas</code> — alertas críticas abiertas (stock crítico y anomalías)\n"
            "<code>/historial &lt;rut&gt;</code> — últimas entregas de EPP de un trabajador\n"
            "<code>/atender &lt;id&gt;</code> — marca una alerta como atendida\n\n"
            "Ejemplos:\n"
            "<code>/stock casco</code>\n"
            "<code>/historial 12345678-9</code>"
        )

    @staticmethod
    def _stock(argumento):
        if not argumento:
            return _r("Uso: <code>/stock &lt;nombre o código del producto&gt;</code>. Ej: <code>/stock casco</code>")

        coincidencias = Inventario.objects.select_related("bodega").filter(
            Q(nombre__icontains=argumento) | Q(codigo__icontains=argumento)
        ).order_by("nombre")

        total = coincidencias.count()
        productos = list(coincidencias[:MAX_RESULTADOS])

        if not productos:
            return _r(f"No encontré productos que coincidan con «{escapar_html(argumento)}».")

        lineas = [f"📦 <b>Stock para «{escapar_html(argumento)}»</b>"]
        for producto in productos:
            icono = "🔴" if producto.stock_actual <= producto.stock_minimo else "🟢"
            lineas.append(
                f"{icono} {escapar_html(producto.nombre)} [{escapar_html(producto.codigo)}] — "
                f"{escapar_html(producto.bodega.nombre)}: <b>{producto.stock_actual}</b> (mín. {producto.stock_minimo})"
            )

        if total > MAX_RESULTADOS:
            lineas.append(f"\n… y {total - MAX_RESULTADOS} más. Afina la búsqueda para verlos.")

        return _r("\n".join(lineas))

    @staticmethod
    def _alertas():
        base = Alerta.objects.filter(
            leida=False,
            tipo_alerta__in=[TipoAlerta.STOCK_CRITICO, TipoAlerta.ANOMALIA_CONSUMO, TipoAlerta.INTENTO_SUPLANTACION],
        ).order_by("-fecha_alerta")

        total = base.count()
        abiertas = list(base[:MAX_RESULTADOS])

        if not abiertas:
            return _r("✅ No hay alertas críticas abiertas.")

        lineas = ["🚨 <b>Alertas críticas abiertas</b>"]
        teclado = []
        for alerta in abiertas:
            fecha = timezone.localtime(alerta.fecha_alerta).strftime("%d-%m %H:%M")
            lineas.append(f"<b>#{alerta.id}</b> [{fecha}] {escapar_html(alerta.mensaje)}")
            teclado.append([{"text": f"✅ Atender #{alerta.id}", "callback_data": f"atender:{alerta.id}"}])

        if total > MAX_RESULTADOS:
            lineas.append(f"\n… y {total - MAX_RESULTADOS} más. Revisa el Dashboard para verlas todas.")

        return _r("\n".join(lineas), teclado)

    @staticmethod
    def _historial(rut):
        if not rut:
            return _r("Uso: <code>/historial &lt;RUT&gt;</code>. Ej: <code>/historial 12345678-9</code>")

        trabajador = Trabajador.objects.filter(rut__icontains=rut.strip()).first()
        if not trabajador:
            return _r(f"No encontré ningún trabajador con RUT «{escapar_html(rut)}».")

        entregas = (
            EntregaEPP.objects.filter(trabajador=trabajador)
            .prefetch_related("detalles__inventario")
            .order_by("-fecha_entrega")[:5]
        )

        nombre_trabajador = escapar_html(f"{trabajador.nombres} {trabajador.apellido_paterno}")

        if not entregas:
            return _r(f"{nombre_trabajador} no tiene entregas registradas.")

        lineas = [f"📋 <b>Últimas entregas de {nombre_trabajador}</b> ({escapar_html(trabajador.rut)})"]
        for entrega in entregas:
            fecha = timezone.localtime(entrega.fecha_entrega).strftime("%d-%m-%Y")
            items = ", ".join(f"{d.cantidad}x {escapar_html(d.inventario.nombre)}" for d in entrega.detalles.all())
            lineas.append(f"• {fecha} — {items or 'sin ítems'}")

        return _r("\n".join(lineas))

    @staticmethod
    def _atender(argumento, usuario):
        if not argumento or not argumento.strip().isdigit():
            return _r("Uso: <code>/atender &lt;id&gt;</code>. El id aparece en /alertas. Ej: <code>/atender 142</code>")

        alerta = Alerta.objects.filter(id=int(argumento.strip())).first()
        if not alerta:
            return _r(f"No encontré ninguna alerta con id {argumento}.")

        if alerta.leida:
            return _r(f"La alerta #{alerta.id} ya estaba atendida.")

        alerta.leida = True
        alerta.save(update_fields=["leida"])

        return _r(f"✅ Alerta #{alerta.id} marcada como atendida por <b>{escapar_html(usuario.username)}</b>.")
