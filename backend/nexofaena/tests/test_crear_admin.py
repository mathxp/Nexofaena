from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from nexofaena.models.rol import Rol

Usuario = get_user_model()


@override_settings(
    DJANGO_SUPERUSER_USERNAME="admin_test",
    DJANGO_SUPERUSER_EMAIL="admin_test@nexofaena.cl",
    DJANGO_SUPERUSER_PASSWORD="clave-super-segura-123",
)
class CrearAdminTests(TestCase):
    """
    Cubre el comando usado en el build de Render para crear el superusuario
    inicial sin consola interactiva (createsuperuser --noinput no sirve acá
    porque Usuario exige rut y rol_id, que --noinput no sabe completar).
    """

    def _correr(self, **env):
        # decouple.config lee os.environ antes que settings/override_settings,
        # así que las variables van por environ (monkeypatch), no por Django
        # settings — override_settings de arriba queda solo como documentación
        # de qué variables usa el comando.
        import os
        anteriores = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            salida = StringIO()
            call_command("crear_admin", stdout=salida)
            return salida.getvalue()
        finally:
            for k, v in anteriores.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_crea_roles_base(self):
        self._correr(
            DJANGO_SUPERUSER_USERNAME="admin_test",
            DJANGO_SUPERUSER_EMAIL="admin_test@nexofaena.cl",
            DJANGO_SUPERUSER_PASSWORD="clave-super-segura-123",
        )

        for nombre in ["Administrador", "Supervisor", "Bodeguero", "Operador"]:
            self.assertTrue(Rol.objects.filter(nombre=nombre).exists(), f"falta el rol {nombre}")

    def test_crea_superusuario_con_rut_y_rol(self):
        self._correr(
            DJANGO_SUPERUSER_USERNAME="admin_test",
            DJANGO_SUPERUSER_EMAIL="admin_test@nexofaena.cl",
            DJANGO_SUPERUSER_PASSWORD="clave-super-segura-123",
            DJANGO_SUPERUSER_RUT="12345678-9",
        )

        usuario = Usuario.objects.get(username="admin_test")
        self.assertTrue(usuario.is_superuser)
        self.assertTrue(usuario.is_staff)
        self.assertEqual(usuario.rut, "12345678-9")
        self.assertEqual(usuario.rol.nombre, "Administrador")
        self.assertTrue(usuario.check_password("clave-super-segura-123"))

    def test_es_idempotente_no_duplica_ni_falla(self):
        env = dict(
            DJANGO_SUPERUSER_USERNAME="admin_test",
            DJANGO_SUPERUSER_EMAIL="admin_test@nexofaena.cl",
            DJANGO_SUPERUSER_PASSWORD="clave-super-segura-123",
        )
        self._correr(**env)
        salida_segunda_vez = self._correr(**env)

        self.assertEqual(Usuario.objects.filter(username="admin_test").count(), 1)
        self.assertIn("ya existe", salida_segunda_vez.lower())

    def test_sin_variables_no_falla_y_no_crea_nada(self):
        # Se pisan con "" en vez de sacarlas del entorno: si backend/.env
        # tiene DJANGO_SUPERUSER_* configurado (como en desarrollo local),
        # decouple.config() cae a ese archivo apenas la variable no está en
        # os.environ — sacarlas con pop() no alcanza para simular "no
        # configuradas" en ese caso.
        usuarios_antes = Usuario.objects.count()

        salida = self._correr(
            DJANGO_SUPERUSER_USERNAME="",
            DJANGO_SUPERUSER_EMAIL="",
            DJANGO_SUPERUSER_PASSWORD="",
        )

        self.assertEqual(Usuario.objects.count(), usuarios_antes)
        self.assertIn("no están configurados", salida.lower())
