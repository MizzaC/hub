from FundBoard.models import FinancialAuditEvent


def record_financial_event(user, event_type, instance=None, *, details=None):
    """Record only allowlisted metadata, never model payloads or request data."""
    return FinancialAuditEvent.objects.create(
        user=user,
        event_type=event_type,
        object_type=type(instance).__name__ if instance is not None else "",
        object_pk=instance.pk if instance is not None else None,
        details=details or {},
    )
