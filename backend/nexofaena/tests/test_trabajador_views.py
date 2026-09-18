from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from nexofaena.models.alerta import Alerta, TipoAlerta
from nexofaena.tests.base import crear_trabajador, crear_usuario

DESCRIPTOR_VALIDO = [0.01 * i for i in range(128)]


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False)
class EnrolarRostroTests(APITestCase):
    def setUp(self):
        self.trabajador = crear_trabajador()

    def _url(self):
        return f"/api/trabajadores/{self.trabajador.id}/enrolar-rostro/"

    def test_bodeguero_puede_enrolar(self):
        usuario = crear_usuario(username="bodeguero1", rol_nombre="Bodeguero")
        self.client.force_authenticate(usuario)

        respuesta = self.client.post(self._url(), {"face_descriptor": DESCRIPTOR_VALIDO}, format="json")

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.trabajador.refresh_from_db()
        self.assertEqual(len(self.trabajador.face_descriptor), 128)
        self.assertIsNotNone(self.trabajador.face_enrolado_en)

    def test_operador_no_puede_enrolar(self):
        usuario = crear_usuario(username="operador1", rol_nombre="Operador")
        self.client.force_authenticate(usuario)

        respuesta = self.client.post(self._url(), {"face_descriptor": DESCRIPTOR_VALIDO}, format="json")

        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_rechaza_descriptor_con_largo_incorrecto(self):
        usuario = crear_usuario(username="bodeguero1", rol_nombre="Bodeguero")
        self.client.force_authenticate(usuario)

        respuesta = self.client.post(self._url(), {"face_descriptor": [0.1, 0.2]}, format="json")

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.trabajador.refresh_from_db()
        self.assertIsNone(self.trabajador.face_descriptor)

    def test_rechaza_descriptor_no_numerico(self):
        usuario = crear_usuario(username="bodeguero1", rol_nombre="Bodeguero")
        self.client.force_authenticate(usuario)

        descriptor_malo = ["a"] * 128
        respuesta = self.client.post(self._url(), {"face_descriptor": descriptor_malo}, format="json")

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anonimo_no_puede_enrolar(self):
        respuesta = self.client.post(self._url(), {"face_descriptor": DESCRIPTOR_VALIDO}, format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False)
class ReportarSuplantacionTests(APITestCase):
    def setUp(self):
        self.trabajador = crear_trabajador()
        self.usuario = crear_usuario(username="bodeguero1", rol_nombre="Bodeguero")
        self.client.force_authenticate(self.usuario)

    def test_crea_alerta_de_intento_de_suplantacion(self):
        respuesta = self.client.post(
            f"/api/trabajadores/{self.trabajador.id}/reportar-suplantacion/", {}, format="json",
        )

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)

        alerta = Alerta.objects.filter(tipo_alerta=TipoAlerta.INTENTO_SUPLANTACION).first()
        self.assertIsNotNone(alerta)
        self.assertIn(self.trabajador.rut, alerta.mensaje)
