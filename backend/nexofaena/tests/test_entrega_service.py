from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from nexofaena.models.entrega import DetalleEntregaEPP
from nexofaena.services.entrega_service import EntregaService
from nexofaena.tests.base import (
    crear_bodega, crear_producto, crear_trabajador, crear_unidad_activo, crear_usuario,
)


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False)
class CrearEntregaTests(TestCase):
    def setUp(self):
        self.usuario = crear_usuario()
        self.bodega = crear_bodega()
        self.trabajador = crear_trabajador()
        self.producto = crear_producto(self.bodega, stock=Decimal("10"))

    def test_descuenta_stock_correctamente(self):
        EntregaService.crear_entrega(
            trabajador_id=self.trabajador.id,
            usuario_id=self.usuario.id,
            bodega_id=self.bodega.id,
            detalles=[{"inventario": self.producto.id, "cantidad": 3}],
        )

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, Decimal("7"))

    def test_rechaza_si_no_hay_stock_suficiente(self):
        with self.assertRaises(ValidationError):
            EntregaService.crear_entrega(
                trabajador_id=self.trabajador.id,
                usuario_id=self.usuario.id,
                bodega_id=self.bodega.id,
                detalles=[{"inventario": self.producto.id, "cantidad": 999}],
            )

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, Decimal("10"), "el stock no debe tocarse si la entrega se rechaza")

    def test_rechaza_sin_detalles(self):
        with self.assertRaises(ValidationError):
            EntregaService.crear_entrega(
                trabajador_id=self.trabajador.id,
                usuario_id=self.usuario.id,
                bodega_id=self.bodega.id,
                detalles=[],
            )

    def test_devolutivo_exige_unidad_especifica(self):
        radio = crear_producto(self.bodega, nombre="Radio", es_devolutivo=True, stock=Decimal("5"))

        with self.assertRaises(ValidationError):
            EntregaService.crear_entrega(
                trabajador_id=self.trabajador.id,
                usuario_id=self.usuario.id,
                bodega_id=self.bodega.id,
                detalles=[{"inventario": radio.id, "cantidad": 1}],
            )

    def test_devolutivo_marca_unidad_como_entregada(self):
        radio = crear_producto(self.bodega, nombre="Radio", es_devolutivo=True, stock=Decimal("5"))
        unidad = crear_unidad_activo(radio, "RADIO-T01")

        EntregaService.crear_entrega(
            trabajador_id=self.trabajador.id,
            usuario_id=self.usuario.id,
            bodega_id=self.bodega.id,
            detalles=[{"inventario": radio.id, "cantidad": 1, "unidad_activo": unidad.id}],
        )

        unidad.refresh_from_db()
        self.assertEqual(unidad.estado, "ENTREGADA")

    def test_no_puede_retirar_segundo_devolutivo_si_debe_uno(self):
        """
        Regla de negocio agregada para el kiosco de autoservicio: un
        trabajador no puede llevarse un segundo equipo devolutivo mientras
        tenga uno pendiente de devolver.
        """
        radio = crear_producto(self.bodega, nombre="Radio", es_devolutivo=True, stock=Decimal("5"))
        unidad1 = crear_unidad_activo(radio, "RADIO-T01")
        unidad2 = crear_unidad_activo(radio, "RADIO-T02")

        EntregaService.crear_entrega(
            trabajador_id=self.trabajador.id,
            usuario_id=self.usuario.id,
            bodega_id=self.bodega.id,
            detalles=[{"inventario": radio.id, "cantidad": 1, "unidad_activo": unidad1.id}],
        )

        with self.assertRaises(ValidationError) as ctx:
            EntregaService.crear_entrega(
                trabajador_id=self.trabajador.id,
                usuario_id=self.usuario.id,
                bodega_id=self.bodega.id,
                detalles=[{"inventario": radio.id, "cantidad": 1, "unidad_activo": unidad2.id}],
            )

        self.assertIn("pendiente de devolver", " ".join(ctx.exception.messages))

        unidad2.refresh_from_db()
        self.assertEqual(unidad2.estado, "DISPONIBLE", "la segunda unidad no debe quedar reservada/entregada")

    def test_puede_retirar_devolutivo_de_nuevo_tras_devolver(self):
        radio = crear_producto(self.bodega, nombre="Radio", es_devolutivo=True, stock=Decimal("5"))
        unidad1 = crear_unidad_activo(radio, "RADIO-T01")
        unidad2 = crear_unidad_activo(radio, "RADIO-T02")

        EntregaService.crear_entrega(
            trabajador_id=self.trabajador.id,
            usuario_id=self.usuario.id,
            bodega_id=self.bodega.id,
            detalles=[{"inventario": radio.id, "cantidad": 1, "unidad_activo": unidad1.id}],
        )

        detalle = DetalleEntregaEPP.objects.get(unidad_activo=unidad1)
        EntregaService.registrar_devolucion(detalle_id=detalle.id, usuario_id=self.usuario.id)

        # No debe lanzar: ya devolvió el primero.
        EntregaService.crear_entrega(
            trabajador_id=self.trabajador.id,
            usuario_id=self.usuario.id,
            bodega_id=self.bodega.id,
            detalles=[{"inventario": radio.id, "cantidad": 1, "unidad_activo": unidad2.id}],
        )

        unidad2.refresh_from_db()
        self.assertEqual(unidad2.estado, "ENTREGADA")


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False)
class RegistrarDevolucionTests(TestCase):
    def setUp(self):
        self.usuario = crear_usuario()
        self.bodega = crear_bodega()
        self.trabajador = crear_trabajador()
        self.radio = crear_producto(self.bodega, nombre="Radio", es_devolutivo=True, stock=Decimal("5"))
        self.unidad = crear_unidad_activo(self.radio, "RADIO-T01")

        EntregaService.crear_entrega(
            trabajador_id=self.trabajador.id,
            usuario_id=self.usuario.id,
            bodega_id=self.bodega.id,
            detalles=[{"inventario": self.radio.id, "cantidad": 1, "unidad_activo": self.unidad.id}],
        )
        self.detalle = DetalleEntregaEPP.objects.get(unidad_activo=self.unidad)

    def test_devolucion_repone_stock_y_libera_unidad(self):
        self.radio.refresh_from_db()  # setUp ya descontó 1 al crear la entrega
        stock_antes = self.radio.stock_actual

        EntregaService.registrar_devolucion(
            detalle_id=self.detalle.id, usuario_id=self.usuario.id, estado_devolucion="OPERATIVA",
        )

        self.radio.refresh_from_db()
        self.unidad.refresh_from_db()
        self.detalle.refresh_from_db()

        self.assertEqual(self.radio.stock_actual, stock_antes + 1)
        self.assertEqual(self.unidad.estado, "DISPONIBLE")
        self.assertTrue(self.detalle.devuelto)

    def test_devolucion_dañada_deja_unidad_en_mantencion_no_disponible(self):
        EntregaService.registrar_devolucion(
            detalle_id=self.detalle.id, usuario_id=self.usuario.id, estado_devolucion="DAÑADA",
        )

        self.unidad.refresh_from_db()
        self.assertEqual(self.unidad.estado, "EN_MANTENCION")

    def test_no_permite_devolver_dos_veces(self):
        EntregaService.registrar_devolucion(detalle_id=self.detalle.id, usuario_id=self.usuario.id)

        with self.assertRaises(ValidationError):
            EntregaService.registrar_devolucion(detalle_id=self.detalle.id, usuario_id=self.usuario.id)
