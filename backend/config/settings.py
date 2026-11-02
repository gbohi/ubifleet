"""
UbiFleet — Django Settings
Ubipharm Fleet Management System
"""

from pathlib import Path
from decouple import config
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = config('DEBUG', default=False, cast=bool)

# Clé secrète : obligatoire hors mode debug (signature des jetons de connexion)
SECRET_KEY = config('SECRET_KEY', default='')
if not DEBUG and SECRET_KEY.startswith('django-insecure'):
    # Clé de démonstration publiée dans le code : n'importe qui pourrait
    # fabriquer des jetons de connexion valides.
    SECRET_KEY = ''
if not SECRET_KEY:
    if not DEBUG:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "SECRET_KEY doit être défini dans .env, et pas avec la clé de démonstration (générer avec : "
            "python -c \"import secrets; print(secrets.token_urlsafe(50))\").")
    SECRET_KEY = 'django-insecure-dev-uniquement'


ALLOWED_HOSTS = [h.strip() for h in config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'drf_spectacular',

    # UbiFleet apps
    'apps.accounts.apps.AccountsConfig',
    'apps.vehicules.apps.VehiculesConfig',
    'apps.carburant.apps.CarburantConfig',
    'apps.entretien.apps.EntretienConfig',
    'apps.sinistres.apps.SinistresConfig',
    'apps.budget.apps.BudgetConfig',
    'apps.chauffeurs.apps.ChauffeursConfig',
    'apps.alertes.apps.AlertesConfig',
    'apps.rapports.apps.RapportsConfig',
    'apps.controle.apps.ControleConfig',
    'apps.demandes.apps.DemandesConfig',
    'apps.core.apps.CoreConfig',
    'apps.parametrage.apps.ParametrageConfig',
    'apps.total_import',
    'apps.grand_livre',
    'apps.faits_marquants.apps.FaitsMarquantsConfig',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='ubifleet_db'),
        'USER': config('DB_USER', default='ubifleet_user'),
        'PASSWORD': config('DB_PASSWORD', default='ubifleet_pass'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Abidjan'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── REST FRAMEWORK ──
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'apps.core.pagination.UbiFleetPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # Conserver les Decimal comme strings pour éviter la perte de précision float
    'COERCE_DECIMAL_TO_STRING': True,
    # Limite les tentatives de connexion (mots de passe devinés)
    'DEFAULT_THROTTLE_RATES': {'connexion': config('THROTTLE_CONNEXION', default='10/min')},
    # Derrière nginx, l'adresse du client est dans X-Forwarded-For : sans cela,
    # tous les utilisateurs partageraient la limite de connexion de nginx.
    'NUM_PROXIES': config('NUM_PROXIES', default=1, cast=int),
}

# ── JWT ──
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ── CORS ──
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:4200,http://127.0.0.1:4200'
).split(',')
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [o.strip() for o in config('CSRF_TRUSTED_ORIGINS', default='').split(',') if o.strip()]

# ── Sécurité ─────────────────────────────────────────────────────────
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_HTTPONLY = True

# HTTPS (certificat installé sur le serveur web en frontal) : HTTPS=True dans .env
HTTPS = config('HTTPS', default=False, cast=bool)
if HTTPS:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')   # le proxy transmet le protocole
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Redirection HTTP → HTTPS : faite par le serveur web ; à activer ici si besoin
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
    # HSTS : le navigateur refuse ensuite tout accès HTTP. Ne l'activer qu'une
    # fois HTTPS stable (ex. HSTS_SECONDS=31536000).
    SECURE_HSTS_SECONDS = config('HSTS_SECONDS', default=0, cast=int)

# Taille maximale d'un envoi (imports, pièces jointes) : 25 Mo
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# ── Journalisation (sortie standard, lue par Docker) ─────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'simple': {'format': '{asctime} {levelname} {name} : {message}', 'style': '{'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'}},
    'root': {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {'django.request': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False}},
}

# ── DRF SPECTACULAR (OpenAPI/Swagger) ──
SPECTACULAR_SETTINGS = {
    'TITLE': 'UbiFleet API',
    'DESCRIPTION': 'API REST — Gestion de Flotte Automobile Ubipharm',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
}

# ── REDIS & CELERY ──
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TIMEZONE = TIME_ZONE
