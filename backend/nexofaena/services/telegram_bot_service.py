import random
import re
import string
from datetime import date, timedelta

from django.conf import settings
from django.db.models import Q, Sum
from django.utils import timezone

from nexofaena.models.alerta import Alerta, TipoAlerta
from nexofaena.models.entrega import EntregaEPP
from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario
from nexofaena.models.telegram_bot import TelegramCodigoVinculacion, TelegramVinculo
from nexofaena.models.trabajador import Trabajador
from nexofaena.services.notificacion_service import escapar_html

MAX_RESULTADOS = 8
MAX_BOTONES_PRODUCTO = 5
LARGO_MAXIMO_MENSAJE_ALERTA = 180

# Mismo criterio que el Panel Gerencial (DashboardGerencial.jsx).
UMBRAL_RIESGO_ALTO = 70
UMBRAL_RIESGO_MEDIO = 40

TIPOS_ALERTA_BOT = [
    TipoAlerta.STOCK_CRITICO,
    TipoAlerta.ANOMALIA_CONSUMO,
    TipoAlerta.INTENTO_SUPLANTACION,
    TipoAlerta.ENROLAMIENTO_ROSTRO,
]

# "12.345.678-9", "12345678-9", "123456789", "12345678K": un mensaje así se
# interpreta como búsqueda de trabajador, no de producto.
PATRON_RUT = re.compile(r"^\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK]$")

BOTON_MENU = [{"text": "⬅️ Menú principal", "callback_data": "menu"}]

TECLADO_MENU = [
    [{"text": "📊 Resumen del día", "callback_data": "resumen"}, {"text": "🛒 Qué comprar", "callback_data": "comprar"}],
    [{"text": "🚨 Alertas", "callback_data": "alertas"}, {"text": "👷 Consumo inusual", "callback_data": "inusual"}],
    [{"text": "📻 Equipos sin devolver", "callback_data": "prestamos"}, {"text": "🔎 Buscar producto", "callback_data": "buscar"}],
]


def _r(texto, teclado=None):
    """Toda respuesta del bot viaja como (texto HTML, teclado inline u
    None), para que el transporte (telegram_transporte.py) solo tenga que
    llamar a NotificationService.enviar_telegram(*respuesta, chat_id=...)
    sin conocer los detalles de cada comando."""
    return (texto, teclado)


def _con_menu(texto, botones=None):
    """Respuesta con un botón para volver al menú al final: así nunca se
    queda la persona sin saber qué tocar a continuación."""
    return _r(texto, [*(botones or []), BOTON_MENU])


def _clp(valor):
    return f"${float(valor or 0):,.0f}".replace(",", ".")


def _cantidad(valor):
    """10.0 -> "10", 2.5 -> "2,5": los Decimal/float del stock se ven como números de persona."""
    numero = float(valor or 0)
    return f"{numero:.0f}" if numero == int(numero) else f"{numero:.1f}".replace(".", ",")


def _urgencia(probabilidad):
    if probabilidad >= UMBRAL_RIESGO_ALTO:
        return "🔴", "Urgente"
    if probabilidad >= UMBRAL_RIESGO_MEDIO:
        return "🟡", "Pronto"
    return "🔵", "Planificar"


def _fecha_corta(iso):
    return date.fromisoformat(str(iso)[:10]).strftime("%d-%m")


def _normalizar_rut(rut):
    return re.sub(r"[^0-9k]", "", (rut or "").lower())


def _datos_panel():
    """Mismos datos que el Panel Gerencial, desde su caché: el bot no
    reentrena los modelos en cada mensaje."""
    from nexofaena.services.dashboard_service import DashboardService

    return DashboardService.obtener_dashboard()


class TelegramBotService:
    """
    Lógica del bot conversacional de Telegram para supervisores y
    bodegueros vinculados. Se usa sobre todo con botones: /start o /menu
    muestran el menú principal, y cualquier texto libre se entiende como
    búsqueda (un RUT busca al trabajador; cualquier otra cosa, un producto).
    Los comandos clásicos (/stock, /alertas, /historial, /atender) siguen
    funcionando para quien ya los usa.

    Separado del transporte (telegram_transporte.py) para poder probarlo sin
    red. Todo el texto que sale de acá va en HTML (parse_mode="HTML") con
    los valores dinámicos pasados por escapar_html.
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

        usuario = TelegramBotService._usuario_vinculado(chat_id)

        if comando in ("/start", "/vincular"):
            if usuario and not argumento:
                return TelegramBotService._menu(usuario)
            return TelegramBotService._vincular(chat_id, argumento, telegram_username)

        if not usuario:
            return _r(
                "🔒 Esta cuenta de Telegram todavía no está vinculada a NexoFaena.\n"
                "Genera un código desde la app (Alertas → Vincular Telegram) y envíamelo con:\n"
                "<code>/vincular CODIGO</code>"
            )

        if not texto.startswith("/"):
            # Texto libre: no hace falta recordar ningún comando.
            if PATRON_RUT.match(texto):
                return TelegramBotService._historial(texto)
            return TelegramBotService._buscar(texto)

        acciones = {
            "/menu": lambda: TelegramBotService._menu(usuario),
            "/ayuda": TelegramBotService._ayuda,
            "/help": TelegramBotService._ayuda,
            "/resumen": TelegramBotService._resumen,
            "/comprar": TelegramBotService._comprar,
            "/alertas": TelegramBotService._alertas,
            "/inusual": TelegramBotService._inusual,
            "/prestamos": TelegramBotService._prestamos,
            "/stock": lambda: TelegramBotService._stock(argumento),
            "/historial": lambda: TelegramBotService._historial(argumento),
            "/atender": lambda: TelegramBotService._atender(argumento, usuario),
        }
        accion = acciones.get(comando)
        if accion:
            return accion()

        return _con_menu(f"No reconozco «{escapar_html(comando)}». Usa el menú o escribe /ayuda.")

    # --- Punto de entrada del bot: botones inline (callback_query) ---

    @staticmethod
    def procesar_callback(chat_id, callback_data):
        """
        callback_data viaja como "accion" o "accion:argumento" (ej.
        "atender:142", "producto:37"). Devuelve
        (toast_para_answerCallbackQuery, respuesta_como_mensaje_nuevo).
        """
        usuario = TelegramBotService._usuario_vinculado(chat_id)
        if not usuario:
            return "Vincula tu cuenta primero con /vincular.", None

        accion, _, argumento = (callback_data or "").partition(":")

        if accion == "atender":
            return "Listo ✅", TelegramBotService._atender(argumento, usuario)
        if accion == "producto":
            return None, TelegramBotService._ficha_producto(argumento)

        secciones = {
            "menu": lambda: TelegramBotService._menu(usuario),
            "resumen": TelegramBotService._resumen,
            "comprar": TelegramBotService._comprar,
            "alertas": TelegramBotService._alertas,
            "inusual": TelegramBotService._inusual,
            "prestamos": TelegramBotService._prestamos,
            "buscar": TelegramBotService._como_buscar,
        }
        seccion = secciones.get(accion)
        if seccion:
            return None, seccion()

        return "Acción no reconocida.", None

    # --- Vinculación ---

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
            return _con_menu(
                f"Esta cuenta de Telegram ya está vinculada a <b>{escapar_html(ya_vinculado.usuario.username)}</b>."
            )

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
            f"✅ Cuenta vinculada correctamente, <b>{escapar_html(nombre)}</b>.\n\n"
            "Desde ahora puedes consultar la bodega desde aquí. Toca una opción:",
            TECLADO_MENU,
        )

    # --- Menú y ayuda ---

    @staticmethod
    def _menu(usuario):
        nombre = escapar_html(usuario.first_name or usuario.username)
        return _r(
            f"👋 Hola, <b>{nombre}</b>. ¿Qué necesitas revisar?\n\n"
            "<i>Tip: escribe el nombre de un producto (ej. «casco») o el RUT de un "
            "trabajador y te respondo al tiro.</i>",
            TECLADO_MENU,
        )

    @staticmethod
    def _ayuda():
        return _con_menu(
            "🤖 <b>Cómo usar el bot</b>\n\n"
            "La forma más fácil es el <b>menú con botones</b> (/menu).\n"
            "También puedes escribir directamente:\n"
            "• el nombre de un producto → su stock y si conviene comprar\n"
            "• el RUT de un trabajador → sus últimas entregas\n\n"
            "<b>Comandos</b>\n"
            "/resumen — resumen del día\n"
            "/comprar — qué hay que comprar y cuándo\n"
            "/alertas — alertas abiertas, con botón para atenderlas\n"
            "/inusual — trabajadores con consumo fuera de lo normal\n"
            "/prestamos — radios y equipos sin devolver\n"
            "<code>/stock casco</code> — stock de un producto\n"
            "<code>/historial 12345678-9</code> — entregas de un trabajador\n"
            "<code>/atender 142</code> — marca una alerta como atendida"
        )

    @staticmethod
    def _como_buscar():
        return _con_menu(
            "🔎 <b>Buscar un producto</b>\n\n"
            "Escríbeme su nombre o código, sin comandos. Por ejemplo:\n"
            "<code>casco</code> · <code>guantes de nitrilo</code> · <code>DEMO-CASCO</code>"
        )

    # --- Secciones ---

    @staticmethod
    def _resumen():
        datos = _datos_panel()
        recomendaciones = datos.get("recomendaciones_reposicion", [])
        urgentes = sum(1 for r in recomendaciones if r["probabilidad_quiebre"] >= UMBRAL_RIESGO_ALTO)
        por_agotarse = sum(1 for q in datos.get("quiebre_stock", []) if q["probabilidad_quiebre"] >= UMBRAL_RIESGO_ALTO)
        anomalias = datos.get("anomalias_consumo", [])
        alertas_abiertas = Alerta.objects.filter(leida=False, tipo_alerta__in=TIPOS_ALERTA_BOT).count()

        inicio_dia = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        entregado_hoy = MovimientoInventario.objects.filter(
            tipo_movimiento="SALIDA", fecha__gte=inicio_dia,
        ).aggregate(total=Sum("cantidad"))["total"] or 0

        ahora = timezone.localtime().strftime("%d-%m %H:%M")
        lineas = [
            f"📊 <b>Resumen de la bodega</b> · {ahora}",
            "",
            f"{'🔴' if por_agotarse else '🟢'} <b>{por_agotarse}</b> producto(s) por agotarse",
            f"🛒 <b>{len(recomendaciones)}</b> compra(s) recomendada(s)" + (f" · {urgentes} urgente(s)" if urgentes else ""),
            f"{'🟡' if anomalias else '🟢'} <b>{len(anomalias)}</b> consumo(s) fuera de lo normal",
            f"{'🚨' if alertas_abiertas else '🟢'} <b>{alertas_abiertas}</b> alerta(s) sin atender",
            f"📦 <b>{_cantidad(entregado_hoy)}</b> unidades entregadas hoy",
            f"💰 Gasto estimado del mes: <b>{_clp(datos.get('presupuesto_proyectado', {}).get('mensual_clp'))}</b>",
        ]

        botones = []
        if recomendaciones:
            botones.append([{"text": "🛒 Ver qué comprar", "callback_data": "comprar"}])
        if alertas_abiertas:
            botones.append([{"text": "🚨 Ver alertas", "callback_data": "alertas"}])

        return _con_menu("\n".join(lineas), botones)

    @staticmethod
    def _comprar():
        recomendaciones = _datos_panel().get("recomendaciones_reposicion", [])
        if not recomendaciones:
            return _con_menu("✅ <b>Todo en orden.</b> No hay que comprar nada por ahora.")

        lineas = ["🛒 <b>Qué hay que comprar</b>", ""]
        for r in recomendaciones[:MAX_RESULTADOS]:
            icono, etiqueta = _urgencia(r["probabilidad_quiebre"])
            lineas.append(
                f"{icono} <b>{escapar_html(r['producto_nombre'])}</b> · {etiqueta}\n"
                f"    Pedir <b>{_cantidad(r['cantidad_sugerida'])} un.</b> antes del {_fecha_corta(r['fecha_sugerida_pedido'])}"
                f" · {escapar_html(r['bodega_nombre'])}"
            )

        if len(recomendaciones) > MAX_RESULTADOS:
            lineas.append(f"\n… y {len(recomendaciones) - MAX_RESULTADOS} más en el Panel Gerencial.")

        botones = [
            [{"text": f"📦 {r['producto_nombre'][:40]}", "callback_data": f"producto:{r['inventario_id']}"}]
            for r in recomendaciones[:MAX_BOTONES_PRODUCTO]
        ]
        return _con_menu("\n".join(lineas), botones)

    @staticmethod
    def _inusual():
        anomalias = _datos_panel().get("anomalias_consumo", [])
        if not anomalias:
            return _con_menu("✅ <b>Todo en orden.</b> Nadie se sale del consumo habitual de su cargo este mes.")

        lineas = [
            "👷 <b>Consumo fuera de lo normal este mes</b>",
            "<i>Comparado con otros trabajadores del mismo cargo. Es una señal para revisar, no una acusación.</i>",
            "",
        ]
        for a in anomalias[:MAX_RESULTADOS]:
            linea = (
                f"• <b>{escapar_html(a['trabajador_nombre'])}</b> ({escapar_html(a.get('cargo') or 'sin cargo')}): "
                f"{_cantidad(a['cantidad_mes'])} un., sobre todo {escapar_html(a['producto_nombre'])}"
            )
            if a.get("impacto_financiero_clp"):
                linea += f" · exceso ≈ {_clp(a['impacto_financiero_clp'])}"
            lineas.append(linea)

        return _con_menu("\n".join(lineas))

    @staticmethod
    def _prestamos():
        from nexofaena.services.reporte_service import ReporteService

        reporte = ReporteService.prestamos_pendientes(mostrar_rut_completo=False)
        if not reporte["trabajadores"]:
            return _con_menu("✅ <b>Todo devuelto.</b> No hay radios ni equipos pendientes.")

        lineas = [f"📻 <b>Equipos sin devolver</b> · {reporte['total_items']} en total", ""]
        for grupo in reporte["trabajadores"][:MAX_RESULTADOS]:
            items = ", ".join(
                f"{escapar_html(i['unidad_codigo'])} ({i['dias_pendiente']} d)" for i in grupo["items"]
            )
            lineas.append(f"• <b>{escapar_html(grupo['trabajador_nombre'])}</b>: {items}")

        if len(reporte["trabajadores"]) > MAX_RESULTADOS:
            lineas.append(f"\n… y {len(reporte['trabajadores']) - MAX_RESULTADOS} trabajadores más en Reportes.")

        return _con_menu("\n".join(lineas))

    @staticmethod
    def _alertas():
        base = Alerta.objects.filter(leida=False, tipo_alerta__in=TIPOS_ALERTA_BOT).order_by("-fecha_alerta")

        total = base.count()
        abiertas = list(base[:MAX_RESULTADOS])

        if not abiertas:
            return _con_menu("✅ No hay alertas abiertas.")

        lineas = [f"🚨 <b>Alertas abiertas</b> · {total}", ""]
        teclado = []
        for alerta in abiertas:
            fecha = timezone.localtime(alerta.fecha_alerta).strftime("%d-%m %H:%M")
            mensaje = alerta.mensaje
            if len(mensaje) > LARGO_MAXIMO_MENSAJE_ALERTA:
                mensaje = mensaje[:LARGO_MAXIMO_MENSAJE_ALERTA].rstrip() + "…"
            lineas.append(
                f"<b>#{alerta.id}</b> · {escapar_html(alerta.get_tipo_alerta_display())} · {fecha}\n"
                f"{escapar_html(mensaje)}\n"
            )
            teclado.append([{"text": f"✅ Atender #{alerta.id}", "callback_data": f"atender:{alerta.id}"}])

        if total > MAX_RESULTADOS:
            lineas.append(f"… y {total - MAX_RESULTADOS} más en la sección Alertas de la app.")

        return _con_menu("\n".join(lineas), teclado)

    # --- Productos ---

    @staticmethod
    def _buscar(texto):
        """Texto libre -> búsqueda inteligente del Panel Gerencial (tolera
        plurales y errores de tipeo: "cascos" encuentra "Casco")."""
        from nexofaena.services.ml_service import MLService

        resultado = MLService.buscar_kpi_por_texto(texto)
        encontrados = resultado.get("resultados", [])

        if not encontrados:
            motivo = resultado.get("motivo") or f"No encontré productos parecidos a «{texto}»."
            return _con_menu(f"🔎 {escapar_html(motivo)}\n\nPrueba con otro nombre, o con el código del producto.")

        if len(encontrados) == 1:
            return TelegramBotService._ficha_producto(encontrados[0]["inventario_id"])

        lineas = [f"🔎 <b>Resultados para «{escapar_html(texto)}»</b>", ""]
        for r in encontrados:
            icono = "🔴" if r["necesita_reposicion"] else "🟢"
            lineas.append(
                f"{icono} <b>{escapar_html(r['producto_nombre'])}</b> · {escapar_html(r['bodega_nombre'])}: "
                f"{_cantidad(r['stock_actual'])} en stock"
            )
        lineas.append("\nToca uno para ver su ficha:")

        botones = [
            [{"text": f"📦 {r['producto_nombre'][:40]}", "callback_data": f"producto:{r['inventario_id']}"}]
            for r in encontrados[:MAX_BOTONES_PRODUCTO]
        ]
        return _con_menu("\n".join(lineas), botones)

    @staticmethod
    def _ficha_producto(inventario_id):
        """Todo lo que importa de un producto en un mensaje: cuánto queda,
        para cuántos días alcanza y si conviene comprar."""
        from nexofaena.services.ml_service import MLService

        if not str(inventario_id).isdigit():
            return _con_menu("No encontré ese producto.")

        producto = Inventario.objects.select_related("bodega").filter(id=int(inventario_id)).first()
        if not producto:
            return _con_menu("No encontré ese producto (puede haber sido eliminado).")

        stock = float(producto.stock_actual)
        minimo = float(producto.stock_minimo)
        diario = MLService._consumo_diario_reciente().get(producto.id, 0)
        icono_stock = "🔴" if stock <= minimo else "🟢"

        lineas = [
            f"📦 <b>{escapar_html(producto.nombre)}</b>",
            f"<code>{escapar_html(producto.codigo)}</code> · {escapar_html(producto.bodega.nombre)}",
            "",
            f"{icono_stock} Stock: <b>{_cantidad(stock)}</b> (mínimo {_cantidad(minimo)})",
        ]

        if diario > 0:
            dias = stock / diario
            lineas.append(f"📉 Se entregan ~<b>{_cantidad(round(diario, 1))}</b> por día")
            lineas.append(
                f"⏳ Alcanza para ~<b>{_cantidad(round(dias))}</b> día(s) · "
                f"el proveedor tarda {producto.tiempo_reposicion_dias or 7}"
            )
        else:
            lineas.append("📉 Sin entregas en los últimos 30 días")

        recomendacion = next(
            (r for r in _datos_panel().get("recomendaciones_reposicion", []) if r["inventario_id"] == producto.id),
            None,
        )
        if recomendacion:
            icono, etiqueta = _urgencia(recomendacion["probabilidad_quiebre"])
            lineas += [
                "",
                f"🛒 {icono} <b>{etiqueta}:</b> pedir {_cantidad(recomendacion['cantidad_sugerida'])} un. "
                f"antes del {_fecha_corta(recomendacion['fecha_sugerida_pedido'])}",
            ]
        else:
            lineas += ["", "✅ No hace falta comprar por ahora."]

        return _con_menu("\n".join(lineas))

    @staticmethod
    def _stock(argumento):
        if not argumento:
            return _con_menu("Uso: <code>/stock &lt;nombre o código del producto&gt;</code>. Ej: <code>/stock casco</code>")

        coincidencias = Inventario.objects.select_related("bodega").filter(
            Q(nombre__icontains=argumento) | Q(codigo__icontains=argumento)
        ).order_by("nombre")

        total = coincidencias.count()
        productos = list(coincidencias[:MAX_RESULTADOS])

        if not productos:
            # Sin coincidencia literal: se intenta la búsqueda inteligente
            # (plurales, errores de tipeo) antes de rendirse.
            return TelegramBotService._buscar(argumento)

        lineas = [f"📦 <b>Stock para «{escapar_html(argumento)}»</b>", ""]
        for producto in productos:
            icono = "🔴" if producto.stock_actual <= producto.stock_minimo else "🟢"
            lineas.append(
                f"{icono} {escapar_html(producto.nombre)} [{escapar_html(producto.codigo)}] — "
                f"{escapar_html(producto.bodega.nombre)}: <b>{_cantidad(producto.stock_actual)}</b> "
                f"(mín. {_cantidad(producto.stock_minimo)})"
            )

        if total > MAX_RESULTADOS:
            lineas.append(f"\n… y {total - MAX_RESULTADOS} más. Afina la búsqueda para verlos.")

        botones = [
            [{"text": f"📦 {p.nombre[:40]}", "callback_data": f"producto:{p.id}"}]
            for p in productos[:MAX_BOTONES_PRODUCTO]
        ]
        return _con_menu("\n".join(lineas), botones)

    # --- Trabajadores ---

    @staticmethod
    def _historial(rut):
        if not rut:
            return _con_menu("Uso: <code>/historial &lt;RUT&gt;</code>. Ej: <code>/historial 12345678-9</code>")

        # Coincidencia exacta del RUT normalizado: con "contiene", un RUT
        # incompleto podía mostrar el historial de otra persona.
        buscado = _normalizar_rut(rut)
        # Prefiltro por los 3 últimos dígitos del cuerpo: calzan esté el RUT
        # guardado con o sin puntos; la comparación exacta va después.
        candidatos = Trabajador.objects.filter(rut__icontains=buscado[:-1][-3:]) if len(buscado) > 3 else []
        trabajador = next((t for t in candidatos if _normalizar_rut(t.rut) == buscado), None)

        if not trabajador:
            return _con_menu(f"No encontré ningún trabajador con RUT «{escapar_html(rut)}».")

        entregas = (
            EntregaEPP.objects.filter(trabajador=trabajador)
            .prefetch_related("detalles__inventario")
            .order_by("-fecha_entrega")[:5]
        )

        nombre_trabajador = escapar_html(f"{trabajador.nombres} {trabajador.apellido_paterno}")
        encabezado = (
            f"👷 <b>{nombre_trabajador}</b>\n"
            f"{escapar_html(trabajador.cargo or 'Sin cargo')} · {escapar_html(trabajador.rut)}"
        )

        if not entregas:
            return _con_menu(f"{encabezado}\n\nNo tiene entregas registradas.")

        lineas = [encabezado, "", "<b>Últimas entregas</b>"]
        for entrega in entregas:
            fecha = timezone.localtime(entrega.fecha_entrega).strftime("%d-%m-%Y")
            items = ", ".join(
                f"{_cantidad(d.cantidad)}× {escapar_html(d.inventario.nombre)}" for d in entrega.detalles.all()
            )
            lineas.append(f"• {fecha} — {items or 'sin ítems'}")

        return _con_menu("\n".join(lineas))

    # --- Acciones ---

    @staticmethod
    def _atender(argumento, usuario):
        if not argumento or not argumento.strip().isdigit():
            return _con_menu("Uso: <code>/atender &lt;id&gt;</code>. El id aparece en /alertas. Ej: <code>/atender 142</code>")

        alerta = Alerta.objects.filter(id=int(argumento.strip())).first()
        if not alerta:
            return _con_menu(f"No encontré ninguna alerta con id {escapar_html(argumento)}.")

        if alerta.leida:
            return _con_menu(f"La alerta #{alerta.id} ya estaba atendida.")

        alerta.leida = True
        alerta.save(update_fields=["leida"])

        quedan = Alerta.objects.filter(leida=False, tipo_alerta__in=TIPOS_ALERTA_BOT).count()
        botones = [[{"text": f"🚨 Ver alertas restantes ({quedan})", "callback_data": "alertas"}]] if quedan else []

        return _con_menu(
            f"✅ Alerta #{alerta.id} marcada como atendida por <b>{escapar_html(usuario.username)}</b>.",
            botones,
        )
