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


# Otro rostro claramente distinto de DESCRIPTOR_VALIDO (distancia ~3.3).
DESCRIPTOR_OTRA_PERSONA = [0.5 - 0.01 * i for i in range(128)]


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False)
class ProteccionEnrolamientoTests(APITestCase):
    """El RUT no es secreto: el kiosco no puede dejar que cualquiera que lo
    conozca reemplace o duplique el rostro de otra persona."""

    def setUp(self):
        self.trabajador = crear_trabajador()
        self.client.force_authenticate(crear_usuario(username="bodeguero1", rol_nombre="Bodeguero"))

    def _enrolar(self, trabajador, descriptor):
        return self.client.post(
            f"/api/trabajadores/{trabajador.id}/enrolar-rostro/", {"face_descriptor": descriptor}, format="json",
        )

    def test_no_reemplaza_un_rostro_ya_registrado(self):
        self._enrolar(self.trabajador, DESCRIPTOR_VALIDO)

        respuesta = self._enrolar(self.trabajador, DESCRIPTOR_OTRA_PERSONA)

        self.assertEqual(respuesta.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(respuesta.data["codigo"], "ROSTRO_YA_REGISTRADO")
        self.trabajador.refresh_from_db()
        self.assertEqual(self.trabajador.face_descriptor, DESCRIPTOR_VALIDO)
        self.assertTrue(Alerta.objects.filter(tipo_alerta=TipoAlerta.INTENTO_SUPLANTACION).exists())

    def test_rechaza_rostro_que_ya_es_de_otro_trabajador(self):
        otro = crear_trabajador(rut="22222222-2", nombres="Ana")
        self._enrolar(otro, DESCRIPTOR_VALIDO)

        casi_igual = [v + 0.001 for v in DESCRIPTOR_VALIDO]
        respuesta = self._enrolar(self.trabajador, casi_igual)

        self.assertEqual(respuesta.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(respuesta.data["codigo"], "ROSTRO_DE_OTRO_TRABAJADOR")
        self.trabajador.refresh_from_db()
        self.assertIsNone(self.trabajador.face_descriptor)
        alerta = Alerta.objects.get(tipo_alerta=TipoAlerta.INTENTO_SUPLANTACION)
        self.assertIn(otro.rut, alerta.mensaje)

    def test_acepta_rostro_distinto_al_de_otros_trabajadores(self):
        otro = crear_trabajador(rut="22222222-2", nombres="Ana")
        self._enrolar(otro, DESCRIPTOR_VALIDO)

        respuesta = self._enrolar(self.trabajador, DESCRIPTOR_OTRA_PERSONA)

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)

    def test_rostro_de_trabajador_inactivo_no_bloquea(self):
        otro = crear_trabajador(rut="22222222-2", nombres="Ana")
        self._enrolar(otro, DESCRIPTOR_VALIDO)
        otro.activo = False
        otro.save(update_fields=["activo"])

        respuesta = self._enrolar(self.trabajador, DESCRIPTOR_VALIDO)

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)

    def test_registro_exitoso_genera_alerta_para_el_bodeguero(self):
        self._enrolar(self.trabajador, DESCRIPTOR_VALIDO)

        alerta = Alerta.objects.get(tipo_alerta=TipoAlerta.ENROLAMIENTO_ROSTRO)
        self.assertIn(self.trabajador.rut, alerta.mensaje)


@override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False)
class ReiniciarRostroTests(APITestCase):
    def setUp(self):
        self.trabajador = crear_trabajador(face_descriptor=DESCRIPTOR_VALIDO)

    def _url(self):
        return f"/api/trabajadores/{self.trabajador.id}/reiniciar-rostro/"

    def test_administrador_reinicia_y_el_trabajador_puede_volver_a_enrolarse(self):
        self.client.force_authenticate(crear_usuario(username="admin1", rol_nombre="Administrador"))

        respuesta = self.client.post(self._url(), {}, format="json")

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.trabajador.refresh_from_db()
        self.assertIsNone(self.trabajador.face_descriptor)
        self.assertIsNone(self.trabajador.face_enrolado_en)

        self.client.force_authenticate(crear_usuario(username="bodeguero1", rol_nombre="Bodeguero"))
        reenrolar = self.client.post(
            f"/api/trabajadores/{self.trabajador.id}/enrolar-rostro/",
            {"face_descriptor": DESCRIPTOR_OTRA_PERSONA}, format="json",
        )
        self.assertEqual(reenrolar.status_code, status.HTTP_200_OK)

    def test_bodeguero_no_puede_reiniciar(self):
        self.client.force_authenticate(crear_usuario(username="bodeguero1", rol_nombre="Bodeguero"))

        respuesta = self.client.post(self._url(), {}, format="json")

        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)
        self.trabajador.refresh_from_db()
        self.assertEqual(self.trabajador.face_descriptor, DESCRIPTOR_VALIDO)
