import csv
from io import StringIO

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, TemplateView

from FundBoard.exports.service import csv_export_bytes, excel_export_bytes, json_export_bytes
from FundBoard.forms import ImportUploadForm
from FundBoard.imports.parser import ImportDocumentError, parse_document
from FundBoard.imports.service import (
    DuplicateImportError,
    RollbackRefusedError,
    commit_import,
    preview_import,
    rollback_import,
)
from FundBoard.imports.templates import excel_template_bytes, json_template_bytes
from FundBoard.models import FinancialAuditEvent, ImportBatch
from FundBoard.services.audit import record_financial_event

EXPORT_RESOURCES = {"all", "accounts", "instruments", "positions", "transactions", "real_estate", "loans"}


def _download(content, content_type, file_name):
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


class ImportExportView(LoginRequiredMixin, TemplateView):
    template_name = "fundboard/import_export.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("form", ImportUploadForm())
        context["batches"] = ImportBatch.objects.filter(user=self.request.user)[:10]
        return context

    def post(self, request, *args, **kwargs):
        form = ImportUploadForm(request.POST, request.FILES)
        context = self.get_context_data(form=form)
        if not form.is_valid():
            return self.render_to_response(context, status=400)
        upload = form.cleaned_data["file"]
        content = upload.read()
        try:
            document, file_format = parse_document(content, upload.name)
            if request.POST.get("action") == "preview":
                context["report"] = preview_import(request.user, document)
                context["preview_only"] = True
                return self.render_to_response(context)
            report = commit_import(
                request.user,
                document,
                file_name=upload.name,
                file_format=file_format,
                content=content,
            )
        except ImportDocumentError as exc:
            form.add_error("file", str(exc))
            return self.render_to_response(context, status=400)
        except DuplicateImportError as exc:
            messages.warning(request, "Ce fichier a déjà été traité ; aucun doublon créé.")
            return redirect("fundboard:import_batch", pk=exc.batch.pk)
        messages.success(
            request,
            f"Import terminé : {report.created_rows} création(s), "
            f"{report.updated_rows} mise(s) à jour et {report.invalid_rows} ligne(s) ignorée(s).",
        )
        return redirect("fundboard:import_batch", pk=report.batch.pk)


class ImportBatchDetailView(LoginRequiredMixin, DetailView):
    model = ImportBatch
    template_name = "fundboard/import_batch.html"
    context_object_name = "batch"

    def get_queryset(self):
        return ImportBatch.objects.filter(user=self.request.user).prefetch_related("issues")


class ImportIssuesCsvView(LoginRequiredMixin, View):
    def get(self, request, pk):
        batch = get_object_or_404(ImportBatch.objects.filter(user=request.user), pk=pk)
        output = StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["sheet", "row", "column", "code", "message", "value_preview"])
        for issue in batch.issues.all():
            writer.writerow(
                [
                    issue.sheet,
                    issue.row_number,
                    issue.column,
                    issue.code,
                    issue.message,
                    issue.value_preview,
                ]
            )
        return _download(
            output.getvalue().encode("utf-8-sig"),
            "text/csv; charset=utf-8",
            f"mizzac-import-{batch.pk}-errors.csv",
        )


class RollbackImportView(LoginRequiredMixin, View):
    def post(self, request, pk):
        batch = get_object_or_404(ImportBatch.objects.filter(user=request.user), pk=pk)
        try:
            rollback_import(batch)
        except RollbackRefusedError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Le lot a été annulé sans toucher aux autres données.")
        return redirect("fundboard:import_batch", pk=batch.pk)


class JsonTemplateView(LoginRequiredMixin, View):
    def get(self, request):
        return _download(
            json_template_bytes(),
            "application/json; charset=utf-8",
            "mizzac-import-v1.0.json",
        )


class ExcelTemplateView(LoginRequiredMixin, View):
    def get(self, request):
        return _download(
            excel_template_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "mizzac-import-v1.0.xlsx",
        )


class ExportView(LoginRequiredMixin, View):
    def get(self, request, file_format):
        resource = request.GET.get("resource", "all")
        if resource not in EXPORT_RESOURCES:
            return HttpResponse("Ressource d'export inconnue.", status=400)
        if file_format == "json":
            content = json_export_bytes(request.user, resource)
            self.record_export(request, file_format, resource)
            return _download(
                content,
                "application/json; charset=utf-8",
                f"mizzac-{resource}-v1.0.json",
            )
        if file_format == "xlsx":
            content = excel_export_bytes(request.user, resource)
            self.record_export(request, file_format, resource)
            return _download(
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                f"mizzac-{resource}-v1.0.xlsx",
            )
        if file_format == "csv" and resource != "all":
            content = csv_export_bytes(request.user, resource)
            self.record_export(request, file_format, resource)
            return _download(
                content,
                "text/csv; charset=utf-8",
                f"mizzac-{resource}-v1.0.csv",
            )
        return HttpResponse("Format d'export invalide ou ressource CSV manquante.", status=400)

    @staticmethod
    def record_export(request, file_format, resource):
        record_financial_event(
            request.user,
            FinancialAuditEvent.Type.EXPORT,
            details={"format": file_format, "resource": resource},
        )
