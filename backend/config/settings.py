from pathlib import Path
import os
from datetime import timedelta  # <-- IMPORTANTE: Necesario para definir los tiempos del Token

# ==========================================
# BASE
# ==========================================
BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================
# SEGURIDAD
# ==========================================
SECRET_KEY = "django-insecure-c0m3dlp_a%wc+!2q+#n^xcs)f6-8va@-kzart07+ubj02ws3pq"

DEBUG = True

ALLOWED_HOSTS = []

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
]

# ==========================================
# MIDDLEWARE
# ==========================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "nexofaena_db",
        "USER": "postgres",
        "PASSWORD": "Maty04082002.",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

# ==========================================
# USUARIO PERSONALIZADO
# ==========================================
AUTH_USER_MODEL = "nexofaena.Usuario"

# ==========================================
# DJANGO REST FRAMEWORK
# ==========================================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    # <-- AGREGADO: Esto obliga a que todos los endpoints requieran token por defecto, a menos que especifiques lo contrario en la vista.
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated", 
    )
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

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "../frontend/static"),
]

STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# ==========================================
# DEFAULT PK
# ==========================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"