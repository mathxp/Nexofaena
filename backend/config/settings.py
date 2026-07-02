from pathlib import Path
import os
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
]

# ==========================================
# CORS
# ==========================================
CORS_ALLOW_ALL_ORIGINS = True

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

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@nexofaena.cl"

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
}

SPECTACULAR_SETTINGS = {
    "TITLE": "NexoFaena SGI API",
    "DESCRIPTION": "API para gestión de inventario, bodegas, entregas, movimientos, alertas y dashboard.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}
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