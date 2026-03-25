import os
import environ
import dj_database_url
from pathlib import Path

# 1. Initialisation de django-environ
env = environ.Env(
    DEBUG=(bool, False)
)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# 2. Lecture du fichier .env
# On cherche le fichier .env à la racine du projet
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# 3. Récupération des secrets depuis le .env
SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')

ALLOWED_HOSTS = ['*'] # Adapté pour GitHub Codespaces


# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "pgvector",
    # DRF
    "rest_framework",
    # Apps métier
    "accounts",
    "attendance",
    "alerts",
    "core",
    "dashboard",
    "Employee",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.ThreadLocalMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "BioAttend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "BioAttend.wsgi.application"

DATABASES = {
    'default': dj_database_url.config(
        default=env('DATABASE_URL'), 
        conn_max_age=600,
    )
}

DATABASES['default']['OPTIONS'] = {
    'options': '-c search_path=public,extensions'
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization
LANGUAGE_CODE = "fr-fr" 
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# User model personnalisé
AUTH_USER_MODEL = "accounts.Utilisateur"

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard:index'
LOGOUT_REDIRECT_URL = 'login'

# ─── Django REST Framework ───────────────────────────────────────────────────
REST_FRAMEWORK = {
    # L'API est consommée par le Raspberry Pi (pas de session Django)
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

# ─── Seuil de reconnaissance faciale ─────────────────────────────────────────
# Distance cosinus en dessous de laquelle on considère un visage comme reconnu.
# Valeur entre 0 (identique) et 2 (opposé). 0.5 est un bon point de départ.
FACE_MATCH_THRESHOLD = 0.5
