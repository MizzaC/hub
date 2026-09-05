import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("FundBoard", "0007_phase9_paper_trading"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MaintenanceRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("correlation_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("trigger", models.CharField(choices=[("MANUAL", "Manuelle"), ("SCHEDULED", "Planifiée")], default="SCHEDULED", max_length=20)),
                ("status", models.CharField(choices=[("RUNNING", "En cours"), ("SUCCEEDED", "Réussie"), ("PARTIAL", "Partielle"), ("FAILED", "Échouée")], default="RUNNING", max_length=20)),
                ("include_network", models.BooleanField(default=False)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("snapshot_created_count", models.PositiveIntegerField(default=0)),
                ("snapshot_existing_count", models.PositiveIntegerField(default=0)),
                ("virtual_portfolio_count", models.PositiveIntegerField(default=0)),
                ("virtual_order_executed_count", models.PositiveIntegerField(default=0)),
                ("virtual_order_rejected_count", models.PositiveIntegerField(default=0)),
                ("market_refresh_count", models.PositiveIntegerField(default=0)),
                ("market_failure_count", models.PositiveIntegerField(default=0)),
                ("fx_refresh_succeeded", models.BooleanField(default=False)),
                ("connector_run_count", models.PositiveIntegerField(default=0)),
                ("connector_failure_count", models.PositiveIntegerField(default=0)),
                ("public_message", models.CharField(blank=True, max_length=255)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="financial_maintenance_runs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-started_at", "-pk"],
                "indexes": [models.Index(fields=["user", "-started_at"], name="maintenance_user_time_idx")],
                "constraints": [models.UniqueConstraint(condition=models.Q(status="RUNNING"), fields=("user",), name="uniq_running_maintenance_user")],
            },
        ),
        migrations.AddIndex(
            model_name="connection",
            index=models.Index(fields=["user", "next_sync_at"], name="conn_user_next_sync_idx"),
        ),
    ]
