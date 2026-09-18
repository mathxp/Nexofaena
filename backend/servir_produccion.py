"""
Sirve el backend con Waitress en vez de `manage.py runserver`.

`runserver` es el servidor de desarrollo de Django: recarga el código en
cada cambio, no está pensado para uso sostenido, y no maneja bien varias
conexiones a la vez (justo lo que necesita un kiosco corriendo todo el
turno + el staff usando la app al mismo tiempo). Waitress es un servidor
WSGI liviano, sin dependencias nativas, que corre igual en Windows y Linux
— gunicorn (ya en requirements.txt) no funciona en Windows porque necesita
fork(), propio de Unix.

Antes de la primera vez, corre `python manage.py collectstatic --noinput`
(whitenoise necesita el manifiesto de archivos estáticos para servir el
admin de Django y la documentación de la API).

Uso: python servir_produccion.py
"""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
# Le avisa a NexofaenaConfig.ready() que este es un proceso de servidor de
# verdad (no un management command de un solo uso como migrate/test/seed),
# para que precaliente el Dashboard igual que hace runserver.
os.environ.setdefault("NEXOFAENA_SERVIDOR", "waitress")

from waitress import serve  # noqa: E402
from config.wsgi import application  # noqa: E402

PUERTO = 8000

if __name__ == "__main__":
    print(f"NexoFaena SGI (Waitress) escuchando en http://0.0.0.0:{PUERTO}")
    serve(application, host="0.0.0.0", port=PUERTO, threads=8)
