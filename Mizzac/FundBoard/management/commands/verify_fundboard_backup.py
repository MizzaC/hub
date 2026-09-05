from django.core.management.base import BaseCommand, CommandError

from FundBoard.services.backups import BackupError, verify_database_backup


class Command(BaseCommand):
    help = "Vérifie empreinte, taille, intégrité et inventaire d'une sauvegarde FundBoard."

    def add_arguments(self, parser):
        parser.add_argument("--backup", required=True)

    def handle(self, *args, **options):
        try:
            result = verify_database_backup(options["backup"])
        except BackupError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            f"OK {result.engine} · SHA-256 {result.sha256} · {result.size} octets · "
            f"{result.table_count} tables · {result.migration_count} migrations"
        )

