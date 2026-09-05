"""Create idempotent daily snapshots from the local valuation cache."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from FundBoard.services.snapshots import IncompleteValuationError, create_daily_snapshots


class Command(BaseCommand):
    help = "Crée les snapshots patrimoniaux quotidiens sans appel réseau."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            help="Limiter la création à un utilisateur actif.",
        )

    def handle(self, *args, **options):
        users = get_user_model().objects.filter(is_active=True)
        if options["username"]:
            users = users.filter(username=options["username"])
            if not users.exists():
                raise CommandError("Utilisateur actif introuvable.")

        failed = 0
        for user in users.iterator():
            try:
                result = create_daily_snapshots(user)
            except IncompleteValuationError as exc:
                failed += 1
                self.stderr.write(
                    self.style.WARNING(
                        f"{user.username}: ignoré ({len(exc.issues)} donnée(s) incomplète(s))."
                    )
                )
                continue
            self.stdout.write(
                f"{user.username}: {result.created} créé(s), {result.existing} déjà présent(s)."
            )
        if failed:
            self.stderr.write(self.style.WARNING(f"{failed} utilisateur(s) ignoré(s)."))
