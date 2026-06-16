from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# ========================
# SÉCURITÉ
# ========================

SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-j^xrdlgae+#q(mc1+%chqnqw%hu3so-1qh6gampd_a0a1b%0ar'
)

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

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
]

# ========================
# MIDDLEWARE
# ========================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
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
    DATABASES['default'] = dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        ssl_require=True
    )

# ========================
# VALIDATION MOT DE PASSE
# ========================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ========================
# INTERNATIONALISATION
# ========================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ========================
# FICHIERS STATIQUES (FIX CRITIQUE)
# ========================

STATIC_URL = '/static/'

# dossier où tu mets tes fichiers (images, css, js)
STATICFILES_DIRS = [BASE_DIR / "static"]

# dossier généré automatiquement
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# ========================
# AUTHENTIFICATION
# ========================

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
AUTH_USER_MODEL = 'users.User'
