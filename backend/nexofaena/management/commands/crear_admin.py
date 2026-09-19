from decouple import config
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from nexofaena.models.rol import Rol

# Mismos roles que crea seed.py para desarrollo local — se recrean acá
# porque el deploy en Render arranca con una base de datos (Neon) vacía y
# sin acceso a consola interactiva para correr el seed a mano.
ROLES_BASE = ["Administrador", "Supervisor", "Bodeguero", "Operador"]


class Command(BaseCommand):
    help = (
        "Crea los roles base y el superusuario inicial desde variables de "
        "entorno. Reemplaza a `createsuperuser --noinput` en el build de "
        "Render: ese comando falla porque Usuario exige `rut` y `rol_id` "
        "además de username/password (ver REQUIRED_FIELDS en "
        "models/usuario.py), y --noinput no tiene forma de pasarle el rol "
        "(es una FK, no un valor plano). Es idempotente: si el usuario ya "
        "existe, no falla ni lo duplica — así se puede dejar en build.sh "
        "para que corra en cada deploy sin problema."
    )

    def handle(self, *args, **options):
        Usuario = get_user_model()

        for nombre in ROLES_BASE:
            _, creado = Rol.objects.get_or_create(nombre=nombre)
            if creado:
                self.stdout.write(self.style.SUCCESS(f"Rol creado: {nombre}"))

        username = config("DJANGO_SUPERUSER_USERNAME", default="")
        email = config("DJANGO_SUPERUSER_EMAIL", default="")
        password = config("DJANGO_SUPERUSER_PASSWORD", default="")
        rut = config("DJANGO_SUPERUSER_RUT", default="11111111-1")
        rol_nombre = config("DJANGO_SUPERUSER_ROL", default="Administrador")

        if not username or not password:
            self.stdout.write(self.style.WARNING(
                "DJANGO_SUPERUSER_USERNAME/DJANGO_SUPERUSER_PASSWORD no están "
                "configurados en el entorno — no se crea superusuario. No es un "
                "error: permite dejar este comando en build.sh incluso en un "
                "entorno que no necesita uno (ej. una rama de prueba)."
            ))
            return

        if Usuario.objects.filter(username=username).exists():
            self.stdout.write(self.style.SUCCESS(
                f"El superusuario '{username}' ya existe — no se toca (comando idempotente)."
            ))
            return

        rol, _ = Rol.objects.get_or_create(nombre=rol_nombre)

        Usuario.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            rut=rut,
            rol=rol,
        )

        self.stdout.write(self.style.SUCCESS(f"Superusuario '{username}' creado correctamente (rol: {rol_nombre})."))
