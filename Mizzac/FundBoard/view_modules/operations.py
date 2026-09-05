"""Personal, read-only operational dashboard and local maintenance trigger."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from FundBoard.models import ConnectorSyncRun, MaintenanceRun
from FundBoard.services.health import operational_health
from FundBoard.services.maintenance import (
    MaintenanceAlreadyRunning,
    run_user_maintenance,
)


class OperationsView(LoginRequiredMixin, TemplateView):
    template_name = "fundboard/operations.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context.update(
            {
                "health": operational_health(user=user),
                "maintenance_runs": MaintenanceRun.objects.filter(user=user)[:30],
                "connector_runs": ConnectorSyncRun.objects.filter(
                    connection__user=user
                ).select_related("connection")[:30],
            }
        )
        return context


class RunLocalMaintenanceView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            run = run_user_maintenance(
                request.user,
                include_network=False,
                trigger=MaintenanceRun.Trigger.MANUAL,
            )
        except MaintenanceAlreadyRunning as exc:
            messages.warning(request, str(exc))
        except Exception:
            messages.error(request, "La maintenance locale a échoué ; consultez son journal.")
        else:
            if run.status == MaintenanceRun.Status.PARTIAL:
                messages.warning(request, run.public_message)
            else:
                messages.success(request, run.public_message)
        return redirect("fundboard:operations")
