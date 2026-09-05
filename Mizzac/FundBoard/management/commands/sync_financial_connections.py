from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from FundBoard.integrations.connectors import get_connector
from FundBoard.integrations.connectors.base import ConnectorError
from FundBoard.models import Connection, ConnectorSyncRun
from FundBoard.services.connectors import sync_connection


class Command(BaseCommand):
    help = "Synchronise explicitement les connexions financières réseau (prévu pour cron)."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--provider", choices=("binance", "enable_banking"))

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(username=options["username"])
        except get_user_model().DoesNotExist as exc:
            raise CommandError("Utilisateur introuvable.") from exc
        connections = Connection.objects.filter(user=user).exclude(status=Connection.Status.REVOKED)
        if options.get("provider"):
            connections = connections.filter(provider=options["provider"])
        failures = 0
        for connection in connections:
            if get_connector(connection.provider).import_only:
                continue
            try:
                run = sync_connection(
                    connection,
                    trigger=ConnectorSyncRun.Trigger.SCHEDULED,
                )
            except ConnectorError as exc:
                failures += 1
                self.stderr.write(f"{connection.display_name}: {exc.public_message}")
            else:
                self.stdout.write(
                    f"{connection.display_name}: {run.status}, {run.created_count} créé(s)"
                )
        if failures:
            raise CommandError(f"{failures} synchronisation(s) en échec.")
