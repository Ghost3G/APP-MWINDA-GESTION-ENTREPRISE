import time

from django.core.management.base import BaseCommand
from django.db import OperationalError, connection


class Command(BaseCommand):
    help = "Wait until the configured database accepts connections."

    def add_arguments(self, parser):
        parser.add_argument("--timeout", type=int, default=90)
        parser.add_argument("--interval", type=int, default=3)

    def handle(self, *args, **options):
        timeout = options["timeout"]
        interval = options["interval"]
        deadline = time.monotonic() + timeout
        attempt = 1
        last_error = None

        while time.monotonic() < deadline:
            try:
                connection.ensure_connection()
                self.stdout.write(self.style.SUCCESS("[OK] Database connection is ready"))
                return
            except OperationalError as exc:
                last_error = exc
                self.stdout.write(
                    self.style.WARNING(
                        f"[WAIT] Database not ready yet, attempt {attempt}: {exc}"
                    )
                )
                attempt += 1
                time.sleep(interval)

        raise OperationalError(f"Database did not become ready within {timeout}s: {last_error}")
