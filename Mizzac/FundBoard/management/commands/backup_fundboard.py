from django.core.management.base import BaseCommand, CommandError

from FundBoard.services.backups import BackupError, create_database_backup, manifest_path


class Command(BaseCommand):
    help = "Crée une sauvegarde cohérente, privée et accompagnée d'un manifeste SHA-256."

    def add_arguments(self, parser):
        parser.add_argument("--destination", required=True)
        parser.add_argument("--label", default="mizzac")

    def handle(self, *args, **options):
        try:
            backup = create_database_backup(
                options["destination"],
                label=options["label"],
            )
        except BackupError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Sauvegarde créée : {backup}")
        self.stdout.write(f"Manifeste : {manifest_path(backup)}")

