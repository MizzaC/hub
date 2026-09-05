from django.core.management.base import BaseCommand, CommandError

from FundBoard.services.backups import BackupError, restore_sqlite_backup

CONFIRMATION = "RESTORE_TO_NEW_DATABASE"


class Command(BaseCommand):
    help = "Restaure une sauvegarde SQLite vérifiée vers un nouveau fichier uniquement."

    def add_arguments(self, parser):
        parser.add_argument("--backup", required=True)
        parser.add_argument("--destination", required=True)
        parser.add_argument("--confirm", required=True)

    def handle(self, *args, **options):
        if options["confirm"] != CONFIRMATION:
            raise CommandError(f"Confirmation requise : --confirm {CONFIRMATION}")
        try:
            destination = restore_sqlite_backup(
                options["backup"],
                options["destination"],
            )
        except BackupError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Restauration vérifiée créée : {destination}")
