import os
import sys


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_PACKAGES = os.path.join(BASE_DIR, ".python_packages")

if LOCAL_PACKAGES not in sys.path:
    sys.path.insert(0, LOCAL_PACKAGES)

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from django.core.management import execute_from_command_line


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "AppMwinda.settings")
    execute_from_command_line(sys.argv)
