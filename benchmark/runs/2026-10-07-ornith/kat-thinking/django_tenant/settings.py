SECRET_KEY = "isolated-benchmark-only"
INSTALLED_APPS = ["django.contrib.contenttypes", "django.contrib.auth", "billing"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
REST_FRAMEWORK = {"UNAUTHENTICATED_USER": None, "DEFAULT_AUTHENTICATION_CLASSES": []}
