from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from nexofaena.models.alerta import Alerta, TipoAlerta
from nexofaena.models.telegram_bot import TelegramCodigoVinculacion, TelegramVinculo
from nexofaena.services.telegram_bot_service import BOTON_MENU, TECLADO_MENU, TelegramBotService
from nexofaena.tests.base import crear_bodega, crear_producto, crear_trabajador, crear_usuario

CHAT_ID = 999999999


class VinculacionTests(TestCase):
    def setUp(self):
        self.usuario = crear_usuario()

    def test_start_sin_codigo_pide_vincular(self):
        texto, teclado = TelegramBotService.procesar_mensaje(CHAT_ID, "/start")
        self.assertIn("vincular", texto.lower())
        self.assertIsNone(teclado)

    def test_vincular_con_codigo_valido(self):
        codigo = TelegramBotService.generar_codigo_vinculacion(self.usuario)

        texto, _ = TelegramBotService.procesar_mensaje(CHAT_ID, f"/vincular {codigo.codigo}")

        self.assertIn("vinculada correctamente", texto.lower())
        self.assertTrue(TelegramVinculo.objects.filter(chat_id=CHAT_ID, usuario=self.usuario).exists())

        codigo.refresh_from_db()
        self.assertTrue(codigo.usado)

    def test_vincular_con_codigo_invalido(self):
        texto, _ = TelegramBotService.procesar_mensaje(CHAT_ID, "/vincular NOEXISTE")
        self.assertIn("inválido", texto.lower())
        self.assertFalse(TelegramVinculo.objects.filter(chat_id=CHAT_ID).exists())

    def test_vincular_dos_veces_no_duplica(self):
        codigo1 = TelegramBotService.generar_codigo_vinculacion(self.usuario)
        TelegramBotService.procesar_mensaje(CHAT_ID, f"/vincular {codigo1.codigo}")

        codigo2 = TelegramBotService.generar_codigo_vinculacion(self.usuario)
        texto, _ = TelegramBotService.procesar_mensaje(CHAT_ID, f"/vincular {codigo2.codigo}")

        self.assertIn("ya está vinculada", texto.lower())
        self.assertEqual(TelegramVinculo.objects.filter(chat_id=CHAT_ID).count(), 1)

    def test_generar_codigo_invalida_el_anterior(self):
        codigo1 = TelegramBotService.generar_codigo_vinculacion(self.usuario)
        TelegramBotService.generar_codigo_vinculacion(self.usuario)

        self.assertFalse(TelegramCodigoVinculacion.objects.filter(id=codigo1.id).exists())


class ComandosSinVincularTests(TestCase):
    def test_comando_sin_vinculo_pide_vincular(self):
        texto, _ = TelegramBotService.procesar_mensaje(CHAT_ID, "/stock casco")
        self.assertIn("no está vinculada", texto.lower())


class ComandosVinculadosTests(TestCase):
    def setUp(self):
        self.usuario = crear_usuario()
        TelegramVinculo.objects.create(usuario=self.usuario, chat_id=CHAT_ID)
        self.bodega = crear_bodega()

    def test_ayuda(self):
        texto, _ = TelegramBotService.procesar_mensaje(CHAT_ID, "/ayuda")
        self.assertIn("/stock", texto)
        self.assertIn("/alertas", texto)

    def test_comando_desconocido(self):
        texto, _ = TelegramBotService.procesar_mensaje(CHAT_ID, "/no_existe")
        self.assertIn("no reconozco", texto.lower())

    def test_stock_sin_argumento(self):
        texto, _ = TelegramBotService.procesar_mensaje(CHAT_ID, "/stock")
        self.assertIn("uso:", texto.lower())

    def test_stock_encuentra_producto(self):
        crear_producto(self.bodega, nombre="Casco de seguridad", codigo="CASCO-01", stock=Decimal("5"))

        texto, _ = TelegramBotService.procesar_mensaje(CHAT_ID, "/stock casco")

        self.assertIn("Casco de seguridad", texto)
        self.assertIn("CASCO-01", texto)

    def test_stock_escapa_html_del_texto_buscado(self):
        # Un texto de búsqueda con "<" no debe filtrarse crudo al HTML de
        # salida (mismo bug que rompió las notificaciones de Telegram antes).
        texto, _ = TelegramBotService.procesar_mensaje(CHAT_ID, "/stock <script>")
        self.assertNotIn("<script>", texto)

    def test_alertas_vacio(self):
        texto, teclado = TelegramBotService.procesar_mensaje(CHAT_ID, "/alertas")
        self.assertIn("no hay alertas", texto.lower())
        self.assertEqual(teclado, [BOTON_MENU])

    def test_alertas_con_pendientes_trae_boton_atender(self):
        alerta = Alerta.objects.create(tipo_alerta=TipoAlerta.STOCK_CRITICO, mensaje="Prueba")

        texto, teclado = TelegramBotService.procesar_mensaje(CHAT_ID, "/alertas")

        self.assertIn(f"#{alerta.id}", texto)
        self.assertIsNotNone(teclado)
        self.assertEqual(teclado[0][0]["callback_data"], f"atender:{alerta.id}")

    def test_atender_marca_alerta_como_leida(self):
        alerta = Alerta.objects.create(tipo_alerta=TipoAlerta.STOCK_CRITICO, mensaje="Prueba")

        texto, _ = TelegramBotService.procesar_mensaje(CHAT_ID, f"/atender {alerta.id}")

        alerta.refresh_from_db()
        self.assertTrue(alerta.leida)
        self.assertIn("marcada como atendida", texto.lower())

    def test_atender_dos_veces_avisa_que_ya_estaba(self):
        alerta = Alerta.objects.create(tipo_alerta=TipoAlerta.STOCK_CRITICO, mensaje="Prueba", leida=True)

        texto, _ = TelegramBotService.procesar_mensaje(CHAT_ID, f"/atender {alerta.id}")

        self.assertIn("ya estaba atendida", texto.lower())

    def test_callback_atender_boton(self):
        alerta = Alerta.objects.create(tipo_alerta=TipoAlerta.STOCK_CRITICO, mensaje="Prueba")

        toast, respuesta = TelegramBotService.procesar_callback(CHAT_ID, f"atender:{alerta.id}")

        self.assertEqual(toast, "Listo ✅")
        alerta.refresh_from_db()
        self.assertTrue(alerta.leida)
        self.assertIn("marcada como atendida", respuesta[0].lower())


DATOS_PANEL = {
    "recomendaciones_reposicion": [
        {"inventario_id": 1, "producto_nombre": "Casco de seguridad", "bodega_nombre": "Bodega Central",
         "fecha_sugerida_pedido": "2026-11-02", "cantidad_sugerida": 50.0, "probabilidad_quiebre": 92.0},
        {"inventario_id": 2, "producto_nombre": "Lentes de seguridad", "bodega_nombre": "Bodega Central",
         "fecha_sugerida_pedido": "2026-11-15", "cantidad_sugerida": 80.0, "probabilidad_quiebre": 45.0},
    ],
    "quiebre_stock": [{"probabilidad_quiebre": 92.0}, {"probabilidad_quiebre": 45.0}],
    "anomalias_consumo": [
        {"trabajador_nombre": "Pedro Rojas", "cargo": "Rigger", "cantidad_mes": 112.0,
         "producto_nombre": "Guantes de nitrilo", "impacto_financiero_clp": 54000},
    ],
    "presupuesto_proyectado": {"mensual_clp": 1201000},
}


@patch("nexofaena.services.telegram_bot_service._datos_panel", return_value=DATOS_PANEL)
class MenuYSeccionesTests(TestCase):
    def setUp(self):
        self.usuario = crear_usuario(first_name="Matías")
        TelegramVinculo.objects.create(usuario=self.usuario, chat_id=CHAT_ID)

    def test_start_vinculado_muestra_menu(self, _panel):
        texto, teclado = TelegramBotService.procesar_mensaje(CHAT_ID, "/start")

        self.assertIn("Matías", texto)
        self.assertEqual(teclado, TECLADO_MENU)

    def test_callback_menu(self, _panel):
        toast, (texto, teclado) = TelegramBotService.procesar_callback(CHAT_ID, "menu")

        self.assertIsNone(toast)
        self.assertEqual(teclado, TECLADO_MENU)

    def test_resumen(self, _panel):
        _, (texto, teclado) = TelegramBotService.procesar_callback(CHAT_ID, "resumen")

        self.assertIn("<b>1</b> producto(s) por agotarse", texto)
        self.assertIn("2</b> compra(s) recomendada(s) · 1 urgente(s)", texto)
        self.assertIn("$1.201.000", texto)
        self.assertIn({"text": "🛒 Ver qué comprar", "callback_data": "comprar"}, teclado[0])
        self.assertEqual(teclado[-1], BOTON_MENU)

    def test_comprar_muestra_urgencia_y_botones_de_producto(self, _panel):
        texto, teclado = TelegramBotService.procesar_mensaje(CHAT_ID, "/comprar")

        self.assertIn("🔴 <b>Casco de seguridad</b> · Urgente", texto)
        self.assertIn("🟡 <b>Lentes de seguridad</b> · Pronto", texto)
        self.assertIn("Pedir <b>50 un.</b> antes del 02-11", texto)
        self.assertEqual(teclado[0][0]["callback_data"], "producto:1")

    def test_inusual(self, _panel):
        texto, _ = TelegramBotService.procesar_mensaje(CHAT_ID, "/inusual")

        self.assertIn("Pedro Rojas", texto)
        self.assertIn("Rigger", texto)
        self.assertIn("$54.000", texto)

    def test_prestamos_vacio(self, _panel):
        texto, _ = TelegramBotService.procesar_mensaje(CHAT_ID, "/prestamos")
        self.assertIn("todo devuelto", texto.lower())

    def test_texto_libre_busca_producto_y_muestra_su_ficha(self, panel):
        bodega = crear_bodega()
        productos = [
            crear_producto(bodega, nombre=nombre, codigo=f"EPP-{i}", stock=Decimal("14"), stock_minimo=Decimal("20"))
            for i, nombre in enumerate(["Casco de seguridad", "Guantes de nitrilo", "Lentes de seguridad",
                                        "Zapato de seguridad", "Chaleco reflectante"])
        ]
        panel.return_value = {"recomendaciones_reposicion": [
            {**DATOS_PANEL["recomendaciones_reposicion"][0], "inventario_id": productos[0].id},
        ]}

        texto, _ = TelegramBotService.procesar_mensaje(CHAT_ID, "cascos")

        self.assertIn("📦 <b>Casco de seguridad</b>", texto)
        self.assertIn("🔴 Stock: <b>14</b> (mínimo 20)", texto)
        self.assertIn("<b>Urgente:</b> pedir 50 un. antes del 02-11", texto)

    def test_texto_libre_con_rut_muestra_historial(self, _panel):
        crear_trabajador(rut="12345678-5", nombres="Ana", apellido_paterno="Soto")

        texto, _ = TelegramBotService.procesar_mensaje(CHAT_ID, "12.345.678-5")

        self.assertIn("Ana Soto", texto)

    def test_historial_no_acepta_rut_incompleto(self, _panel):
        crear_trabajador(rut="12345678-5", nombres="Ana", apellido_paterno="Soto")

        texto, _ = TelegramBotService.procesar_mensaje(CHAT_ID, "/historial 5678-5")

        self.assertNotIn("Ana Soto", texto)

    def test_atender_ofrece_ver_las_restantes(self, _panel):
        primera = Alerta.objects.create(tipo_alerta=TipoAlerta.STOCK_CRITICO, mensaje="Uno")
        Alerta.objects.create(tipo_alerta=TipoAlerta.STOCK_CRITICO, mensaje="Dos")

        _, (texto, teclado) = TelegramBotService.procesar_callback(CHAT_ID, f"atender:{primera.id}")

        self.assertIn("marcada como atendida", texto)
        self.assertEqual(teclado[0][0]["callback_data"], "alertas")

