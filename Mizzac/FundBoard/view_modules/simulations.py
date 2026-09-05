"""Phase 8 scenario CRUD, comparison and deterministic exports."""

from types import SimpleNamespace

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.text import slugify
from django.views import View
from django.views.generic import CreateView, DetailView, TemplateView, UpdateView

from FundBoard.exports.simulations import simulation_excel_bytes, simulation_json_bytes
from FundBoard.forms import CompoundInterestSimulationForm, LoanSimulationForm
from FundBoard.models import (
    CompoundInterestScenario,
    FinancialAuditEvent,
    LoanSimulationScenario,
)
from FundBoard.services.audit import record_financial_event
from FundBoard.services.compound_interest import (
    calculate_compound_interest,
    compound_assumptions_from_scenario,
)
from FundBoard.services.loan_calculator import (
    calculate_loan,
    loan_assumptions_from_scenario,
)

from .manual import ArchiveObjectModal, DynamicModalMixin, OwnedQueryMixin, UserFormMixin


def _loan_result(scenario):
    return calculate_loan(loan_assumptions_from_scenario(scenario))


def _compound_result(scenario):
    return calculate_compound_interest(compound_assumptions_from_scenario(scenario))


class SimulationListView(LoginRequiredMixin, TemplateView):
    template_name = "fundboard/simulations.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loans = list(
            LoanSimulationScenario.objects.filter(
                user=self.request.user,
                archived=False,
            )
        )
        compounds = list(
            CompoundInterestScenario.objects.filter(
                user=self.request.user,
                archived=False,
            )
        )
        for scenario in loans:
            scenario.result = _loan_result(scenario)
        for scenario in compounds:
            scenario.result = _compound_result(scenario)
        context.update({"loan_scenarios": loans, "compound_scenarios": compounds})
        return context


class LoanSimulationDetailView(LoginRequiredMixin, OwnedQueryMixin, DetailView):
    model = LoanSimulationScenario
    template_name = "fundboard/loan_simulation_detail.html"
    context_object_name = "scenario"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result = _loan_result(self.object)
        context.update(
            {
                "result": result,
                "chart_labels": [row.payment_date.isoformat() for row in result.schedule],
                "chart_balances": [format(row.closing_balance, "f") for row in result.schedule],
            }
        )
        return context


class CompoundInterestDetailView(LoginRequiredMixin, OwnedQueryMixin, DetailView):
    model = CompoundInterestScenario
    template_name = "fundboard/compound_simulation_detail.html"
    context_object_name = "scenario"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result = _compound_result(self.object)
        context.update(
            {
                "result": result,
                "chart_labels": [row.period_date.isoformat() for row in result.timeline],
                "chart_nominal": [format(row.closing_value, "f") for row in result.timeline],
                "chart_real": [format(row.real_value, "f") for row in result.timeline],
            }
        )
        return context


class AddLoanSimulationModal(
    LoginRequiredMixin,
    DynamicModalMixin,
    UserFormMixin,
    CreateView,
):
    model = LoanSimulationScenario
    form_class = LoanSimulationForm
    owner_field = "user"
    modal_title = "Créer un scénario de prêt"
    success_message = "Scénario de prêt créé."

    def get_success_url(self):
        return reverse("fundboard:loan_simulation_detail", args=[self.object.pk])


class EditLoanSimulationModal(
    LoginRequiredMixin,
    DynamicModalMixin,
    UserFormMixin,
    OwnedQueryMixin,
    UpdateView,
):
    model = LoanSimulationScenario
    form_class = LoanSimulationForm
    modal_title = "Modifier le scénario de prêt"
    success_message = "Scénario de prêt mis à jour."

    def get_success_url(self):
        return reverse("fundboard:loan_simulation_detail", args=[self.object.pk])


class ArchiveLoanSimulationModal(ArchiveObjectModal):
    model = LoanSimulationScenario
    modal_title = "Archiver le scénario de prêt"
    success_url = "fundboard:simulations"


class AddCompoundSimulationModal(
    LoginRequiredMixin,
    DynamicModalMixin,
    UserFormMixin,
    CreateView,
):
    model = CompoundInterestScenario
    form_class = CompoundInterestSimulationForm
    owner_field = "user"
    modal_title = "Créer un scénario d'intérêts composés"
    success_message = "Scénario d'intérêts composés créé."

    def get_success_url(self):
        return reverse("fundboard:compound_simulation_detail", args=[self.object.pk])


class EditCompoundSimulationModal(
    LoginRequiredMixin,
    DynamicModalMixin,
    UserFormMixin,
    OwnedQueryMixin,
    UpdateView,
):
    model = CompoundInterestScenario
    form_class = CompoundInterestSimulationForm
    modal_title = "Modifier le scénario d'intérêts composés"
    success_message = "Scénario d'intérêts composés mis à jour."

    def get_success_url(self):
        return reverse("fundboard:compound_simulation_detail", args=[self.object.pk])


class ArchiveCompoundSimulationModal(ArchiveObjectModal):
    model = CompoundInterestScenario
    modal_title = "Archiver le scénario d'intérêts composés"
    success_url = "fundboard:simulations"


class ComparisonMixin(LoginRequiredMixin, TemplateView):
    model = None
    calculator = None
    context_object_name = "comparisons"

    def selected_scenarios(self):
        selected_ids = []
        for raw_id in self.request.GET.getlist("ids"):
            if raw_id.isdigit() and int(raw_id) not in selected_ids:
                selected_ids.append(int(raw_id))
        objects = {
            item.pk: item
            for item in self.model.objects.filter(
                user=self.request.user,
                archived=False,
                pk__in=selected_ids,
            )
        }
        return [objects[item_id] for item_id in selected_ids if item_id in objects]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scenarios = self.selected_scenarios()
        error = ""
        if not 2 <= len(scenarios) <= 4:
            error = "Sélectionnez entre deux et quatre scénarios accessibles."
        elif len({scenario.currency for scenario in scenarios}) != 1:
            error = "Comparez uniquement des scénarios utilisant la même devise."
        comparisons = (
            [SimpleNamespace(scenario=item, result=self.calculator(item)) for item in scenarios]
            if not error
            else []
        )
        context.update(
            {
                self.context_object_name: comparisons,
                "comparison_error": error,
                "currency": scenarios[0].currency if scenarios and not error else "",
            }
        )
        return context


class LoanComparisonView(ComparisonMixin):
    model = LoanSimulationScenario
    calculator = staticmethod(_loan_result)
    template_name = "fundboard/loan_simulation_compare.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["chart_series"] = [
            {
                "name": item.scenario.name,
                "data": [format(row.closing_balance, "f") for row in item.result.schedule],
            }
            for item in context["comparisons"]
        ]
        return context


class CompoundComparisonView(ComparisonMixin):
    model = CompoundInterestScenario
    calculator = staticmethod(_compound_result)
    template_name = "fundboard/compound_simulation_compare.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["chart_series"] = [
            {
                "name": item.scenario.name,
                "data": [format(row.closing_value, "f") for row in item.result.timeline],
            }
            for item in context["comparisons"]
        ]
        return context


class SimulationExportView(LoginRequiredMixin, View):
    model = None
    calculator = None
    simulation_type = ""

    def get(self, request, pk, file_format):
        scenario = get_object_or_404(self.model, user=request.user, pk=pk)
        result = self.calculator(scenario)
        filename = slugify(scenario.name) or f"scenario-{scenario.pk}"
        if file_format == "json":
            content = simulation_json_bytes(scenario, result, self.simulation_type)
            content_type = "application/json; charset=utf-8"
        elif file_format == "xlsx":
            content = simulation_excel_bytes(scenario, result, self.simulation_type)
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            return HttpResponse("Format d'export inconnu.", status=400)
        record_financial_event(
            request.user,
            FinancialAuditEvent.Type.EXPORT,
            scenario,
            details={"format": file_format, "resource": self.simulation_type},
        )
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = (
            f'attachment; filename="mizzac-{self.simulation_type}-{filename}.{file_format}"'
        )
        return response


class LoanSimulationExportView(SimulationExportView):
    model = LoanSimulationScenario
    calculator = staticmethod(_loan_result)
    simulation_type = "loan"


class CompoundSimulationExportView(SimulationExportView):
    model = CompoundInterestScenario
    calculator = staticmethod(_compound_result)
    simulation_type = "compound"
