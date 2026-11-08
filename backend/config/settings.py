from pathlib import Path
import os
import sys
from datetime import timedelta  # <-- IMPORTANTE: Necesario para definir los tiempos del Token
import dj_database_url
from decouple import config
# ==========================================
# BASE
# ==========================================
BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================
# SEGURIDAD
# ==========================================
SECRET_KEY = config("SECRET_KEY", default="django-insecure-local")

DEBUG = config("DEBUG", default=True, cast=bool)

ALLOWED_HOSTS_RAW = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1",
    cast=str,
)

ALLOWED_HOSTS = [host.strip() for host in str(ALLOWED_HOSTS_RAW).split(",")]

# ==========================================
# SENTRY (monitoreo de errores en producción)
# ==========================================
# Sin SENTRY_DSN configurado (dev local, o si nunca se agrega en Render)
# esto no hace nada: no manda eventos ni cambia el comportamiento normal.
SENTRY_DSN = config("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        environment="development" if DEBUG else "production",
        # 10% de las requests con traza de performance: suficiente para ver
        # cuellos de botella sin agotar la cuota gratuita.
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
# ==========================================
# APLICACIONES INSTALADAS
# ==========================================
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Terceros
    "rest_framework",
    "rest_framework_simplejwt", # <-- AGREGADO para el Sprint 1
    "corsheaders",

    # Proyecto
    "nexofaena",
    "drf_spectacular",
]

# ==========================================
# MIDDLEWARE
# ==========================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",

    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
]

# ==========================================
# CORS
# ==========================================
# Antes era CORS_ALLOW_ALL_ORIGINS = True (cualquier sitio podía llamar a la
# API) — el CORS_ALLOWED_ORIGINS de abajo, que ya se configuraba en .env, no
# se estaba usando en absoluto. Con el backend expuesto a internet real
# (no solo LAN) conviene restringirlo a los orígenes reales del frontend.
CORS_ALLOWED_ORIGINS_RAW = config("CORS_ALLOWED_ORIGINS", default="http://localhost:5173", cast=str)
CORS_ALLOWED_ORIGINS = [origen.strip() for origen in str(CORS_ALLOWED_ORIGINS_RAW).split(",") if origen.strip()]

# ==========================================
# URLS
# ==========================================
ROOT_URLCONF = "config.urls"

# ==========================================
# TEMPLATES
# ==========================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(BASE_DIR, "../frontend/templates")
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ==========================================
# WSGI
# ==========================================
WSGI_APPLICATION = "config.wsgi.application"

# ==========================================
# BASE DE DATOS
# ==========================================
DATABASES = {
    "default": dj_database_url.config(
        default="postgresql://postgres:Maty04082002.@localhost:5432/nexofaena_db",
        conn_max_age=600,
    )
}

# ==========================================
# CACHE (Dashboard Gerencial)
# ==========================================
# DatabaseCache sobre la misma Postgres: sin esto, Django cae al backend
# por defecto (LocMemCache), que vive en memoria DE UN SOLO PROCESO — el
# cron que repuebla el cache (comando recalcular_dashboard) correría en su
# propio proceso y ese resultado nunca llegaría a los workers de gunicorn
# que sirven el Dashboard. DatabaseCache sí es compartido entre procesos,
# y para un cache de 10 min (CACHE_TTL_SEGUNDOS en dashboard_service.py)
# el rendimiento de Postgres sobra — no amerita levantar Redis solo para
# esto. La tabla se crea con "python manage.py createcachetable" (ver
# build.sh).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "nexofaena_cache",
    }
}

# El panel se recalcula en un hilo aparte cuando sus datos quedan
# desactualizados (ver DashboardService). En los tests se hace en el mismo
# hilo: uno aparte no vería los datos de la transacción de prueba.
DASHBOARD_RECALCULO_EN_SEGUNDO_PLANO = config(
    "DASHBOARD_RECALCULO_EN_SEGUNDO_PLANO", default="test" not in sys.argv, cast=bool,
)

# ==========================================
# REPORTES OPERATIVOS
# ==========================================
# Umbral configurable para derivar el turno (día/noche) desde la hora de
# entrega, sin tocar código: TURNO_HORA_INICIO_DIA <= hora < TURNO_HORA_INICIO_NOCHE = "dia".
TURNO_HORA_INICIO_DIA = int(os.environ.get("TURNO_HORA_INICIO_DIA", 8))
TURNO_HORA_INICIO_NOCHE = int(os.environ.get("TURNO_HORA_INICIO_NOCHE", 20))

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@nexofaena.cl"

# ==========================================
# BOT DE NOTIFICACIONES (TELEGRAM)
# ==========================================
# Token del bot (@BotFather) y chat_id del grupo/canal de gerencia/supervisores
# que debe recibir las alertas críticas (stock crítico, robo hormiga, etc.).
# Sin TELEGRAM_BOT_TOKEN configurado, NotificationService.enviar_alerta() no
# hace nada (falla silenciosa, no debe romper el flujo que generó la alerta).
TELEGRAM_BOT_TOKEN = config("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_CHAT_ID = config("TELEGRAM_CHAT_ID", default="")
TELEGRAM_NOTIFICACIONES_ACTIVAS = config("TELEGRAM_NOTIFICACIONES_ACTIVAS", default=True, cast=bool)

# Bot conversacional (comandos /stock, /alertas, /historial, /atender por DM).
# TELEGRAM_BOT_USERNAME (sin @, ej. "nexofaena_alertas_bot") arma el enlace
# directo "Vincular Telegram" del frontend; sin él, igual funciona pero el
# usuario debe buscar el bot manualmente en Telegram.
TELEGRAM_BOT_USERNAME = config("TELEGRAM_BOT_USERNAME", default="")
TELEGRAM_CODIGO_TTL_MINUTOS = config("TELEGRAM_CODIGO_TTL_MINUTOS", default=10, cast=int)

# Solo se usa si el bot corre por webhook (despliegue en la nube) en vez de
# long-polling (telegram_bot, pensado para LAN). Vacío = la vista del
# webhook rechaza todo con 404 — no hace nada raro por default.
TELEGRAM_WEBHOOK_SECRET = config("TELEGRAM_WEBHOOK_SECRET", default="")

# ==========================================
# INTEGRACIÓN CON N8N (reposición automática)
# ==========================================
# Integración TEMPORAL de evaluación (prueba de 14 días de n8n Cloud, no se
# contratará). Para desactivarla basta con borrar estas dos variables.
# Cuando un producto entra en stock crítico se envía un POST a
# N8N_WEBHOOK_URL (el nodo Webhook del flujo en n8n). N8N_TOKEN es la clave
# compartida en ambos sentidos: viaja en el header X-NexoFaena-Token del
# aviso, y n8n debe mandarla de vuelta al informar la orden de compra.
# Sin N8N_WEBHOOK_URL no se envía nada; sin N8N_TOKEN el endpoint de
# respuesta rechaza todo.
N8N_WEBHOOK_URL = config("N8N_WEBHOOK_URL", default="")
N8N_TOKEN = config("N8N_TOKEN", default="")

# ==========================================
# USUARIO PERSONALIZADO
# ==========================================
AUTH_USER_MODEL = "nexofaena.Usuario"

# ==========================================
# DJANGO REST FRAMEWORK
# ==========================================
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    # Solo JSON: la vista HTML navegable de DRF mostraba el docstring de cada
    # endpoint (detalles internos) a cualquiera, incluso sin sesión.
    "DEFAULT_RENDERER_CLASSES": (
        ("rest_framework.renderers.JSONRenderer", "rest_framework.renderers.BrowsableAPIRenderer")
        if DEBUG else ("rest_framework.renderers.JSONRenderer",)
    ),
    # Sin respuestas a OPTIONS: devolvían el docstring de la vista (por ejemplo,
    # cómo se autentica la integración con n8n) sin pedir login. El preflight
    # CORS no se ve afectado: lo responde CorsMiddleware antes de llegar aquí.
    "DEFAULT_METADATA_CLASS": None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "NexoFaena SGI API",
    "DESCRIPTION": "API para gestión de inventario, bodegas, entregas, movimientos, alertas y dashboard.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # El esquema y /api/docs/ describen toda la API: solo para administradores
    # con sesión iniciada en /admin/ (antes eran públicos).
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
    "SERVE_AUTHENTICATION": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
}

# ==========================================
# CABECERAS DE SEGURIDAD
# ==========================================
from django.utils.csp import CSP  # noqa: E402

# La API solo devuelve JSON, así que la política es estricta. Se permite lo
# mínimo para el panel /admin/ y la documentación (Swagger carga desde jsDelivr).
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, "https://cdn.jsdelivr.net"],
    "style-src": [CSP.SELF, CSP.UNSAFE_INLINE, "https://cdn.jsdelivr.net"],
    "img-src": [CSP.SELF, "data:", "https://cdn.jsdelivr.net"],
    "connect-src": [CSP.SELF],
    "object-src": [CSP.NONE],
    "base-uri": [CSP.NONE],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
}
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    # Render termina el HTTPS y avisa con X-Forwarded-Proto: sin esto Django
    # cree que la petición es http y no envía HSTS.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # HSTS: el navegador recordará usar solo HTTPS durante un año.
    SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
# ==========================================
# SIMPLE JWT (Configuración del Token)
# ==========================================
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60), # El token dura 1 hora
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),    # Permite renovar el token hasta por 1 día
    "ROTATE_REFRESH_TOKENS": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ==========================================
# AUTENTICACIÓN TRADICIONAL (Mantener por si acaso)
# ==========================================
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "login"

# ==========================================
# VALIDADORES DE CONTRASEÑA
# ==========================================
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# ==========================================
# INTERNACIONALIZACIÓN
# ==========================================
LANGUAGE_CODE = "es-cl"

TIME_ZONE = "America/Santiago"

USE_I18N = True
USE_TZ = True

# ==========================================
# ARCHIVOS ESTÁTICOS
# ==========================================
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

STATICFILES_DIRS = []

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
# ==========================================
# DEFAULT PK
# ==========================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOG_DIR = BASE_DIR / "logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
    },

    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "nexofaena.log",
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },

    "loggers": {
        "nexofaena": {
            "handlers": ["file", "console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}