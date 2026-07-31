"""
Update Breeze session in AppSettings/Redis (no .env edit).

Usage:
  python manage.py update_breeze_session
  python manage.py update_breeze_session --session-key YOUR_SESSION_KEY
"""
from django.core.management.base import BaseCommand

from coredata.utils.breeze_session import get_breeze_session, set_breeze_session


class Command(BaseCommand):
    help = "Update Breeze session token in AppSettings/Redis (not .env)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--session-key",
            type=str,
            help="Breeze API session key to set",
        )
        parser.add_argument(
            "--status",
            action="store_true",
            help="Show whether a session is stored (masked)",
        )

    def handle(self, *args, **options):
        from coredata.utils.breeze_session import session_status

        if options.get("status"):
            status = session_status()
            self.stdout.write(f"configured: {status['configured']}")
            self.stdout.write(f"source: {status['source']}")
            self.stdout.write(f"preview: {status['preview'] or '(none)'}")
            return

        self.stdout.write(self.style.SUCCESS("Breeze API Session Key Updater"))
        self.stdout.write("=" * 50)

        session_key = options.get("session_key")
        if not session_key:
            self.stdout.write("\nPreferred flow (no manual copy):")
            self.stdout.write("1. Set redirect URL in ICICI API portal to your site root")
            self.stdout.write("   e.g. https://idjango.rbynex.in/")
            self.stdout.write("2. Open https://api.icicidirect.com/apiuser/home and login")
            self.stdout.write("3. ICICI redirects with ?apisession=<session>; app stores it automatically\n")
            self.stdout.write("Or paste the session key manually:")
            session_key = input("Enter Breeze API Session Key: ").strip()

        if not session_key:
            self.stdout.write(self.style.ERROR("Session key cannot be empty!"))
            return

        try:
            set_breeze_session(session_key)
        except ValueError as exc:
            self.stdout.write(self.style.ERROR(str(exc)))
            return

        stored = get_breeze_session()
        if stored == session_key:
            self.stdout.write(self.style.SUCCESS("\nSession stored in AppSettings/Redis."))
            self.stdout.write("No .env change and no server restart required.")
        else:
            self.stdout.write(self.style.WARNING("Stored, but verification mismatch."))
