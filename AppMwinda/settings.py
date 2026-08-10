from pathlib import Path
import os
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# ========================
# SÉCURITÉ
# ========================

_DEFAULT_INSECURE_SECRET = 'django-insecure-j^xrdlgae+#q(mc1+%chqnqw%hu3so-1qh6gampd_a0a1b%0ar'
SECRET_KEY = os.environ.get('SECRET_KEY', _DEFAULT_INSECURE_SECRET)

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# Exiger une SECRET_KEY forte uniquement en environnement prod-like
_is_prod_like = bool(
    os.environ.get('DATABASE_URL')
    or os.environ.get('RENDER')
    or os.environ.get('RENDER_EXTERNAL_HOSTNAME')
)
if not DEBUG and _is_prod_like and (
    not SECRET_KEY
    or SECRET_KEY == _DEFAULT_INSECURE_SECRET
    or SECRET_KEY.startswith('django-insecure-')
    or SECRET_KEY in {'change-me-in-production', 'changeme'}
):
    raise ImproperlyConfigured(
        "SECRET_KEY de production manquant ou trop faible. "
        "Définissez une SECRET_KEY forte dans les variables d'environnement."
    )

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        'ALLOWED_HOSTS',
        'localhost,127.0.0.1,appmwinda.onrender.com,.onrender.com,testserver'
    ).split(',')
    if host.strip()
]

render_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)

csrf_origins = []
for host in ALLOWED_HOSTS:
    if host in {'localhost', '127.0.0.1', 'testserver'}:
        continue
    if host.startswith('.'):
        csrf_origins.append(f'https://*{host}')
    else:
        csrf_origins.append(f'https://{host}')

default_csrf_origins = ','.join(csrf_origins)

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        'CSRF_TRUSTED_ORIGINS',
        default_csrf_origins
    ).split(',')
    if origin.strip()
]

# ========================
# APPLICATIONS
# ========================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'whitenoise.runserver_nostatic',

    'users',
    'messaging',
    'projects',
    'reports',
    'inventory',
    'machines',
]

# ========================
# MIDDLEWARE
# ========================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'users.security_headers.SecurityHeadersMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'users.middleware.AgentSessionWorkdayMiddleware',
    'users.middleware.AuditLogMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'users.middleware.AgentWorkEndLogoutMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ========================
# URLS / TEMPLATES
# ========================

ROOT_URLCONF = 'AppMwinda.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'AppMwinda.context_processors.app_notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'AppMwinda.wsgi.application'

# ========================
# BASE DE DONNÉES
# ========================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    # Postgres Render : données durables entre les mises à jour / redeploys
    ssl_require = os.environ.get('DATABASE_SSL_REQUIRE', 'True').lower() in {'1', 'true', 'yes'}
    DATABASES['default'] = dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        ssl_require=ssl_require,
    )

# ========================
# VALIDATION MOT DE PASSE
# ========================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 10},
    },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ========================
# INTERNATIONALISATION
# ========================

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Kinshasa'
USE_I18N = True
USE_TZ = True

# Affichage des dates en français : jour / mois / année
DATE_FORMAT = 'd/m/Y'
DATETIME_FORMAT = 'd/m/Y H:i'
SHORT_DATE_FORMAT = 'd/m/Y'
SHORT_DATETIME_FORMAT = 'd/m/Y H:i'
MONTH_DAY_FORMAT = 'j F'
YEAR_MONTH_FORMAT = 'F Y'

# ========================
# FICHIERS STATIQUES (FIX CRITIQUE)
# ========================

STATIC_URL = '/static/'

# dossier où tu mets tes fichiers (images, css, js)
STATICFILES_DIRS = [BASE_DIR / "static"]

# dossier généré automatiquement
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Django 4.2+ / 5+ : backend staticfiles explicite
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Médias durables sur Render via Cloudinary (avatars, photos projets, PJ)
# Sans CLOUDINARY_URL, les fichiers uploadés peuvent disparaître à chaque redeploy.
if os.environ.get('CLOUDINARY_URL'):
    INSTALLED_APPS = [
        *INSTALLED_APPS[:INSTALLED_APPS.index('django.contrib.staticfiles') + 1],
        'cloudinary',
        'cloudinary_storage',
        *INSTALLED_APPS[INSTALLED_APPS.index('django.contrib.staticfiles') + 1:],
    ]
    # Normaliser l’URL (évite les guillemets / espaces collés depuis Render)
    raw_cloudinary = os.environ.get('CLOUDINARY_URL', '').strip().strip('"').strip("'")
    if raw_cloudinary.startswith('URL_CLOUDINARY='):
        raw_cloudinary = raw_cloudinary.split('=', 1)[1].strip()
    if raw_cloudinary and not raw_cloudinary.startswith('cloudinary://'):
        # Laisser Cloudinary échouer clairement plutôt qu’un 500 opaque
        import logging
        logging.getLogger(__name__).error(
            "CLOUDINARY_URL invalide (doit commencer par cloudinary://)."
        )
    else:
        os.environ['CLOUDINARY_URL'] = raw_cloudinary
        try:
            import cloudinary
            cloudinary.config(secure=True)
        except Exception:
            pass
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
    STORAGES['default'] = {
        'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage',
    }
    # Options django-cloudinary-storage
    CLOUDINARY_STORAGE = {
        'SECURE': True,
        # Pas de préfixe "media/" : sinon les public_id Cloudinary (avatars/user_x) cassent l’URL
        'PREFIX': '',
    }
elif not DEBUG:
    # Prod sans Cloudinary : on logue un rappel (pas bloquant)
    import logging
    logging.getLogger(__name__).warning(
        "CLOUDINARY_URL absent : les médias uploadés ne survivront pas aux redeploys Render."
    )

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True').lower() in {'1', 'true', 'yes'}
    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get('SECURE_HSTS_INCLUDE_SUBDOMAINS', 'True').lower() in {'1', 'true', 'yes'}
    SECURE_HSTS_PRELOAD = os.environ.get('SECURE_HSTS_PRELOAD', 'False').lower() in {'1', 'true', 'yes'}
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Limites d'upload (défense en profondeur côté serveur)
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 500

# ========================
# AUTHENTIFICATION
# ========================

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
AUTH_USER_MODEL = 'users.User'

# Session security defaults for enterprise usage
SESSION_COOKIE_AGE = 60 * 60 * 8  # 8 hours
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
# Doit rester lisible en JS pour les appels fetch (messages, tableau, notifs)
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
