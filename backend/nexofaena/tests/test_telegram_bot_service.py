from decimal import Decimal

from django.test import TestCase

from nexofaena.models.alerta import Alerta, TipoAlerta
from nexofaena.models.telegram_bot import TelegramCodigoVinculacion, TelegramVinculo
from nexofaena.services.telegram_bot_service import TelegramBotService
from nexofaena.tests.base import crear_bodega, crear_producto, crear_usuario

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
        self.assertIsNone(teclado)

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
