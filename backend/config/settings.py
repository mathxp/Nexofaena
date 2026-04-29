from pathlib import Path
import os

# ======================
# BASE
# ======================
BASE_DIR = Path(__file__).resolve().parent.parent

# ======================
# SEGURIDAD
# ======================
SECRET_KEY = 'django-insecure-c0m3dlp_a%wc+!2q+#n^xcs)f6-8va@-kzart07+ubj02ws3pq'
DEBUG = True
ALLOWED_HOSTS = []

# ======================
# AUTENTICACIÓN
# ======================
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = 'login'

# ======================
# APLICACIONES
# ======================
INSTALLED_APPS = [
    # Django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Apps del proyecto
    'inventario.apps.InventarioConfig',
    'usuarios',
    'solicitudes',
]

# ======================
# MIDDLEWARE
# ======================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ======================
# URLS / WSGI
# ======================
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

# ======================
# TEMPLATES
# ======================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',

        # 👇 tu frontend separado (correcto)
        'DIRS': [os.path.join(BASE_DIR, '../frontend/templates')],

        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ======================
# BASE DE DATOS
# ======================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'hospital_db',
        'USER': 'postgres',
        'PASSWORD': 'Maty04082002.',  # ⚠️ ojo con el punto final
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# ======================
# VALIDADORES DE PASSWORD
# ======================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ======================
# INTERNACIONALIZACIÓN
# ======================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'  # 🔥 puedes cambiar a 'America/Santiago' si quieres

USE_I18N = True
USE_TZ = True

# ======================
# ARCHIVOS ESTÁTICOS
# ======================
STATIC_URL = '/static/'

# 🔍 Carpeta donde están tus archivos estáticos (frontend)
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, '../frontend/static'),
]

# 📦 Carpeta donde Django recopila archivos (deploy)
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# ======================
# CONFIGURACIÓN DEFAULT
# ======================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'