import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from FundBoard.services.health import operational_health


class Command(BaseCommand):
    help = "Contrôle en lecture seule base, migrations, jobs bloqués et échéances."

    def add_arguments(self, parser):
        parser.add_argument("--username")
        parser.add_argument("--json", action="store_true")
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Retour non nul pour WARNING comme pour ERROR.",
        )

    def handle(self, *args, **options):
        user = None
        if options["username"]:
            try:
                user = get_user_model().objects.get(username=options["username"])
            except get_user_model().DoesNotExist as exc:
                raise CommandError("Utilisateur introuvable.") from exc
        result = operational_health(user=user)
        if options["json"]:
            self.stdout.write(json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True))
        else:
            self.stdout.write(f"FundBoard : {result.status}")
            for message in result.messages:
                self.stdout.write(f"- {message}")
        if result.status == "ERROR" or (options["strict"] and result.status != "OK"):
            raise CommandError(f"État opérationnel : {result.status}")
