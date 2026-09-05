"""Authenticated, explicit-action UI for read-only financial connectors."""

import hmac
import secrets

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from FundBoard.forms import ConnectorForm, ConnectorImportForm
from FundBoard.integrations.connectors import get_connector
from FundBoard.integrations.connectors.base import ConnectorError
from FundBoard.integrations.connectors.secrets import default_secret_reference
from FundBoard.models import Connection, FinancialAuditEvent
from FundBoard.services.audit import record_financial_event
from FundBoard.services.connectors import (
    disconnect_connection,
    import_connection_file,
    institution_for_provider,
    sync_connection,
    test_connection,
)


def user_connection(request, pk):
    return get_object_or_404(Connection, pk=pk, user=request.user)


class ConnectionsView(LoginRequiredMixin, TemplateView):
    template_name = "fundboard/connections.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["connections"] = Connection.objects.filter(user=self.request.user).select_related(
            "institution"
        )
        context["form"] = kwargs.get("form") or ConnectorForm()
        return context

    def post(self, request):
        form = ConnectorForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form), status=400)
        provider = form.cleaned_data["connector_provider"]
        configuration = form.cleaned_data["configuration"]
        institution_name = (
            configuration.get("bank_name")
            or ("Binance" if provider == "binance" else form.cleaned_data["display_name"])
        )
        institution = institution_for_provider(
            provider,
            institution_name,
            country=configuration.get("country", ""),
        )
        connection = Connection(
            user=request.user,
            institution=institution,
            provider=provider,
            display_name=form.cleaned_data["display_name"],
            configuration=configuration,
            secret_reference=default_secret_reference(provider),
        )
        connection.full_clean()
        connection.save()
        record_financial_event(
            request.user,
            FinancialAuditEvent.Type.CONNECTOR_CREATE,
            connection,
            details={"provider": provider},
        )
        messages.success(request, "Connexion créée sans enregistrer aucun identifiant secret.")
        return redirect("fundboard:connection_detail", pk=connection.pk)


class ConnectionDetailView(LoginRequiredMixin, TemplateView):
    template_name = "fundboard/connection_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        connection = user_connection(self.request, self.kwargs["pk"])
        context.update(
            {
                "connection": connection,
                "runs": connection.sync_runs.all()[:20],
                "accounts": connection.accounts.all(),
                "import_form": ConnectorImportForm(),
            }
        )
        return context


class ConnectionTestView(LoginRequiredMixin, View):
    def post(self, request, pk):
        connection = user_connection(request, pk)
        try:
            test_connection(connection)
        except ConnectorError as exc:
            messages.error(request, exc.public_message)
        else:
            messages.success(request, "Accès en lecture vérifié.")
        return redirect("fundboard:connection_detail", pk=pk)


class ConnectionSyncView(LoginRequiredMixin, View):
    def post(self, request, pk):
        connection = user_connection(request, pk)
        if get_connector(connection.provider).import_only:
            messages.error(request, "Ce connecteur se synchronise par import de fichier.")
            return redirect("fundboard:connection_detail", pk=pk)
        try:
            run = sync_connection(connection)
        except ConnectorError as exc:
            messages.error(request, exc.public_message)
        else:
            messages.success(
                request,
                f"Synchronisation terminée : {run.created_count} créé(s), "
                f"{run.updated_count} mis à jour, {run.rejected_count} ignoré(s).",
            )
        return redirect("fundboard:connection_detail", pk=pk)


class ConnectionImportView(LoginRequiredMixin, View):
    def post(self, request, pk):
        connection = user_connection(request, pk)
        form = ConnectorImportForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "Fichier absent, invalide ou supérieur à 5 Mio.")
            return redirect("fundboard:connection_detail", pk=pk)
        upload = form.cleaned_data["file"]
        try:
            run = import_connection_file(connection, upload.read(), upload.name)
        except ConnectorError as exc:
            messages.error(request, exc.public_message)
        else:
            messages.success(
                request,
                f"Import terminé : {run.created_count} créé(s), "
                f"{run.rejected_count} ligne(s) invalide(s) non importée(s).",
            )
        return redirect("fundboard:connection_detail", pk=pk)


class ConnectionDisconnectView(LoginRequiredMixin, View):
    def post(self, request, pk):
        connection = user_connection(request, pk)
        try:
            disconnect_connection(connection)
        except ConnectorError as exc:
            messages.error(request, f"Déconnexion distante impossible : {exc.public_message}")
        else:
            messages.success(
                request,
                "Connexion locale désactivée et historique conservé. "
                "Révoquez aussi la clé chez le fournisseur lorsqu'il ne permet pas la révocation API.",
            )
        return redirect("fundboard:connection_detail", pk=pk)


class EnableBankingAuthorizeView(LoginRequiredMixin, View):
    def post(self, request, pk):
        connection = user_connection(request, pk)
        if connection.provider != "enable_banking":
            return HttpResponseBadRequest("Connecteur incompatible.")
        state = secrets.token_urlsafe(32)
        request.session["enable_banking_authorization"] = {
            "state": state,
            "connection_id": connection.pk,
        }
        callback = request.build_absolute_uri(reverse("fundboard:enable_banking_callback"))
        try:
            url, authorization_id = get_connector("enable_banking").start_authorization(
                connection,
                redirect_url=callback,
                state=state,
            )
        except ConnectorError as exc:
            request.session.pop("enable_banking_authorization", None)
            messages.error(request, exc.public_message)
            return redirect("fundboard:connection_detail", pk=pk)
        request.session["enable_banking_authorization"]["authorization_id"] = authorization_id
        request.session.modified = True
        return redirect(url)


class EnableBankingCallbackView(LoginRequiredMixin, View):
    def get(self, request):
        pending = request.session.pop("enable_banking_authorization", {})
        supplied_state = request.GET.get("state", "")
        code = request.GET.get("code", "")
        connection = get_object_or_404(
            Connection,
            pk=pending.get("connection_id"),
            user=request.user,
            provider="enable_banking",
        )
        if not code or not hmac.compare_digest(str(pending.get("state", "")), supplied_state):
            messages.error(request, "Le retour d'autorisation bancaire est invalide ou expiré.")
            return redirect("fundboard:connection_detail", pk=connection.pk)
        try:
            session_id, _ = get_connector("enable_banking").complete_authorization(
                connection,
                code=code,
            )
        except ConnectorError as exc:
            messages.error(request, exc.public_message)
        else:
            connection.external_id = session_id
            connection.status = Connection.Status.PENDING
            connection.last_error = ""
            connection.save(update_fields=["external_id", "status", "last_error", "updated_at"])
            messages.success(request, "Consentement enregistré. Vous pouvez tester puis synchroniser.")
        return redirect("fundboard:connection_detail", pk=connection.pk)
