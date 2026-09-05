"""Run idempotent local maintenance and optional read-only network syncs."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from FundBoard.models import MaintenanceRun
from FundBoard.services.maintenance import (
    MaintenanceAlreadyRunning,
    run_user_maintenance,
)


class Command(BaseCommand):
    help = (
        "Exécute snapshots et ordres virtuels, avec synchronisations réseau "
        "uniquement si --with-network est présent."
    )

    def add_arguments(self, parser):
        parser.add_argument("--username", help="Limiter à un utilisateur actif.")
        parser.add_argument(
            "--with-network",
            action="store_true",
            help="Activer les connecteurs distants en lecture seule arrivés à échéance.",
        )
        parser.add_argument(
            "--force-network",
            action="store_true",
            help="Ignorer next_sync_at ; exige aussi --with-network.",
        )
        parser.add_argument(
            "--fail-on-partial",
            action="store_true",
            help="Retourner un code d'erreur si au moins une maintenance est partielle.",
        )

    def handle(self, *args, **options):
        if options["force_network"] and not options["with_network"]:
            raise CommandError("--force-network exige --with-network.")
        users = get_user_model().objects.filter(is_active=True).order_by("pk")
        if options["username"]:
            users = users.filter(username=options["username"])
            if not users.exists():
                raise CommandError("Utilisateur actif introuvable.")

        failed = 0
        partial = 0
        for user in users.iterator():
            try:
                run = run_user_maintenance(
                    user,
                    include_network=options["with_network"],
                    force_network=options["force_network"],
                    trigger=MaintenanceRun.Trigger.SCHEDULED,
                )
            except MaintenanceAlreadyRunning as exc:
                failed += 1
                self.stderr.write(f"{user.username}: {exc}")
                continue
            except Exception:
                failed += 1
                self.stderr.write(f"{user.username}: échec interne, voir les journaux.")
                continue
            partial += int(run.status == MaintenanceRun.Status.PARTIAL)
            self.stdout.write(
                f"{user.username}: {run.status} · snapshots "
                f"{run.snapshot_created_count} créés/{run.snapshot_existing_count} existants · "
                f"ordres {run.virtual_order_executed_count} exécutés · "
                f"marché {run.market_refresh_count} actualisés/"
                f"{run.market_failure_count} à contrôler · "
                f"connecteurs {run.connector_run_count} réussis/"
                f"{run.connector_failure_count} à contrôler · id {run.correlation_id}"
            )
        if failed:
            raise CommandError(f"{failed} maintenance(s) en échec.")
        if partial and options["fail_on_partial"]:
            raise CommandError(f"{partial} maintenance(s) partielle(s).")
