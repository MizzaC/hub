"""Canonical financial data model for FundBoard.

Provider payloads are normalized into these models. Credentials never belong
here: a connection only stores an opaque reference to a secret managed by the
deployment environment.
"""

import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .validators import validate_country_code, validate_currency_code

VALUE_QUANTUM = Decimal("0.00000001")


def _quantized_value(value):
    return value.quantize(VALUE_QUANTUM, rounding=ROUND_HALF_UP)


class Institution(models.Model):
    class Type(models.TextChoices):
        BANK = "BANK", "Banque"
        BROKER = "BROKER", "Courtier"
        CRYPTO_EXCHANGE = "CRYPTO", "Plateforme crypto"
        CUSTODIAN = "CUSTODIAN", "Dépositaire"
        OTHER = "OTHER", "Autre"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        UNAVAILABLE = "UNAVAILABLE", "Indisponible"
        RETIRED = "RETIRED", "Retirée"

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    institution_type = models.CharField(max_length=20, choices=Type, default=Type.BANK)
    country_code = models.CharField(
        max_length=2,
        blank=True,
        validators=[validate_country_code],
    )
    logo_url = models.URLField(blank=True)
    capabilities = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=Status, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Connection(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "À configurer"
        ACTIVE = "ACTIVE", "Active"
        STALE = "STALE", "À resynchroniser"
        ERROR = "ERROR", "En erreur"
        REVOKED = "REVOKED", "Révoquée"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="financial_connections",
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.PROTECT,
        related_name="connections",
        null=True,
        blank=True,
    )
    provider = models.CharField(max_length=50)
    external_id = models.CharField(max_length=255, blank=True)
    display_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status, default=Status.PENDING)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    next_sync_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    sync_cursor = models.JSONField(default=dict, blank=True)
    capabilities = models.JSONField(default=list, blank=True)
    configuration = models.JSONField(
        default=dict,
        blank=True,
        help_text="Configuration non secrète du connecteur.",
    )
    secret_reference = models.CharField(
        max_length=255,
        blank=True,
        help_text="Référence opaque vers un gestionnaire de secrets, jamais le secret lui-même.",
    )
    last_tested_at = models.DateTimeField(null=True, blank=True)
    consent_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["provider", "display_name", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "provider", "external_id"],
                condition=~Q(external_id=""),
                name="uniq_connection_user_provider_external",
            )
        ]
        indexes = [
            models.Index(fields=["user", "status"], name="conn_user_status_idx"),
            models.Index(fields=["user", "next_sync_at"], name="conn_user_next_sync_idx"),
        ]

    def clean(self):
        super().clean()
        self.provider = self.provider.strip().lower()

    def __str__(self):
        return self.display_name or f"{self.provider} ({self.user})"


class ConnectorSyncRun(models.Model):
    """Observable, secret-free trace of one connector synchronization."""

    class Trigger(models.TextChoices):
        MANUAL = "MANUAL", "Manuelle"
        SCHEDULED = "SCHEDULED", "Planifiée"
        IMPORT = "IMPORT", "Import de fichier"

    class Status(models.TextChoices):
        RUNNING = "RUNNING", "En cours"
        SUCCEEDED = "SUCCEEDED", "Réussie"
        PARTIAL = "PARTIAL", "Partielle"
        FAILED = "FAILED", "Échouée"

    connection = models.ForeignKey(
        Connection,
        on_delete=models.CASCADE,
        related_name="sync_runs",
    )
    trigger = models.CharField(max_length=20, choices=Trigger, default=Trigger.MANUAL)
    status = models.CharField(max_length=20, choices=Status, default=Status.RUNNING)
    initial_sync = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    received_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    rejected_count = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=50, blank=True)
    public_message = models.CharField(max_length=255, blank=True)
    cursor_before = models.JSONField(default=dict, blank=True)
    cursor_after = models.JSONField(default=dict, blank=True)
    correlation_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        ordering = ["-started_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["connection"],
                condition=Q(status="RUNNING"),
                name="uniq_running_sync_per_connection",
            )
        ]
        indexes = [
            models.Index(fields=["connection", "-started_at"], name="sync_conn_started_idx")
        ]

    def __str__(self):
        return f"{self.connection} – {self.get_status_display()}"


class Account(models.Model):
    class Type(models.TextChoices):
        CURRENT = "CURRENT", "Compte courant"
        SAVINGS = "SAVINGS", "Livret / Épargne"
        CTO = "CTO", "Compte Titres Ordinaire"
        PEA = "PEA", "Plan d’Épargne en Actions"
        LIFE_INSURANCE = "LIFE_INS", "Assurance-vie"
        RETIREMENT = "RETIREMENT", "Épargne retraite"
        CRYPTO = "CRYPTO", "Portefeuille Crypto"
        CASH = "CASH", "Espèces"
        OTHER = "OTHER", "Autre"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Actif"
        CLOSED = "CLOSED", "Clôturé"
        ARCHIVED = "ARCHIVED", "Archivé"

    class Source(models.TextChoices):
        MANUAL = "MANUAL", "Manuel"
        IMPORT = "IMPORT", "Import"
        PROVIDER = "PROVIDER", "Synchronisé"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="financial_accounts",
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.PROTECT,
        related_name="accounts",
        null=True,
        blank=True,
    )
    connection = models.ForeignKey(
        Connection,
        on_delete=models.SET_NULL,
        related_name="accounts",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=Type)
    subtype = models.CharField(max_length=50, blank=True)
    currency = models.CharField(
        max_length=3,
        default="EUR",
        validators=[validate_currency_code],
    )
    balance = models.DecimalField(max_digits=30, decimal_places=12, default=Decimal("0"))
    ownership_share = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("100"),
        help_text="Quote-part détenue, en pourcentage.",
    )
    iban_masked = models.CharField(max_length=34, blank=True)
    manual_reference = models.CharField(max_length=100, blank=True)
    external_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status, default=Status.ACTIVE)
    source = models.CharField(max_length=20, choices=Source, default=Source.MANUAL)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(ownership_share__gt=0) & Q(ownership_share__lte=100),
                name="account_valid_ownership_share",
            ),
            models.UniqueConstraint(
                fields=["user", "connection", "external_id"],
                condition=Q(connection__isnull=False) & ~Q(external_id=""),
                name="uniq_account_user_connection_external",
            ),
            models.UniqueConstraint(
                fields=["user", "manual_reference"],
                condition=~Q(manual_reference=""),
                name="uniq_account_user_manual_ref",
            ),
        ]
        indexes = [models.Index(fields=["user", "status"], name="account_user_status_idx")]

    def clean(self):
        super().clean()
        self.currency = self.currency.strip().upper()
        self.manual_reference = self.manual_reference.strip()
        if (
            self.connection_id
            and self.user_id
            and Connection.objects.filter(pk=self.connection_id)
            .exclude(user_id=self.user_id)
            .exists()
        ):
            raise ValidationError(
                {"connection": "La connexion et le compte doivent avoir le même propriétaire."}
            )
        if self.connection_id and self.institution_id:
            connection_institution_id = (
                Connection.objects.filter(pk=self.connection_id)
                .values_list("institution_id", flat=True)
                .first()
            )
            if connection_institution_id and connection_institution_id != self.institution_id:
                raise ValidationError(
                    {"institution": "L'institution doit correspondre à celle de la connexion."}
                )

    @property
    def is_synchronized(self):
        return self.source == self.Source.PROVIDER and self.connection_id is not None

    def __str__(self):
        return f"{self.name} – {self.get_category_display()} ({self.user})"


class Instrument(models.Model):
    class Type(models.TextChoices):
        STOCK = "STOCK", "Action"
        ETF = "ETF", "ETF"
        FUND = "FUND", "Fonds"
        INDEX = "INDEX", "Indice"
        BOND = "BOND", "Obligation"
        CRYPTO = "CRYPTO", "Cryptomonnaie"
        CURRENCY = "CURRENCY", "Devise"
        COMMODITY = "COMMODITY", "Matière première"
        PRIVATE_EQUITY = "PRIVATE_EQ", "Private equity"
        OTHER = "OTHER", "Autre"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Actif"
        ARCHIVED = "ARCHIVED", "Archivé"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="private_instruments",
        null=True,
        blank=True,
        help_text="Vide pour un référentiel partagé, renseigné pour un instrument privé.",
    )
    name = models.CharField(max_length=255)
    instrument_type = models.CharField(max_length=20, choices=Type)
    ticker = models.CharField(max_length=30, blank=True)
    isin = models.CharField(max_length=12, blank=True)
    market_mic = models.CharField(max_length=4, blank=True)
    currency = models.CharField(max_length=3, validators=[validate_currency_code])
    country_code = models.CharField(
        max_length=2,
        blank=True,
        validators=[validate_country_code],
    )
    sector = models.CharField(max_length=100, blank=True)
    provider_identifiers = models.JSONField(default=dict, blank=True)
    blockchain = models.CharField(max_length=50, blank=True)
    contract_address = models.CharField(max_length=255, blank=True)
    manual_reference = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status, default=Status.ACTIVE)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "ticker"]
        constraints = [
            models.UniqueConstraint(
                fields=["isin"],
                condition=~Q(isin=""),
                name="uniq_instrument_isin",
            ),
            models.UniqueConstraint(
                fields=["blockchain", "contract_address"],
                condition=~Q(blockchain="") & ~Q(contract_address=""),
                name="uniq_instrument_chain_contract",
            ),
            models.UniqueConstraint(
                fields=["owner", "manual_reference"],
                condition=Q(owner__isnull=False) & ~Q(manual_reference=""),
                name="uniq_instrument_owner_manual_ref",
            ),
        ]

    def clean(self):
        super().clean()
        self.currency = self.currency.strip().upper()
        self.country_code = self.country_code.strip().upper()
        self.isin = self.isin.strip().upper()
        self.market_mic = self.market_mic.strip().upper()
        if self.instrument_type == self.Type.CRYPTO:
            if self.contract_address and not self.blockchain:
                raise ValidationError(
                    {
                        "contract_address": (
                            "La chaîne est obligatoire lorsqu'un contrat est renseigné."
                        )
                    }
                )
        elif self.blockchain or self.contract_address:
            raise ValidationError(
                {"blockchain": "Les informations de chaîne sont réservées aux cryptoactifs."}
            )

    def __str__(self):
        suffix = f" ({self.ticker})" if self.ticker else ""
        return f"{self.name}{suffix}"


class Position(models.Model):
    class Source(models.TextChoices):
        MANUAL = "MANUAL", "Manuelle"
        IMPORT = "IMPORT", "Import"
        PROVIDER = "PROVIDER", "Fournisseur"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        ARCHIVED = "ARCHIVED", "Archivée"

    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="positions")
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.PROTECT,
        related_name="positions",
    )
    quantity = models.DecimalField(max_digits=36, decimal_places=18)
    average_unit_cost = models.DecimalField(
        max_digits=30,
        decimal_places=12,
        null=True,
        blank=True,
    )
    cost_basis = models.DecimalField(max_digits=30, decimal_places=8, null=True, blank=True)
    current_unit_price = models.DecimalField(
        max_digits=30,
        decimal_places=12,
        null=True,
        blank=True,
    )
    current_value = models.DecimalField(max_digits=30, decimal_places=8, null=True, blank=True)
    value_currency = models.CharField(max_length=3, validators=[validate_currency_code])
    converted_value = models.DecimalField(
        max_digits=30,
        decimal_places=8,
        null=True,
        blank=True,
    )
    converted_currency = models.CharField(
        max_length=3,
        blank=True,
        validators=[validate_currency_code],
    )
    exchange_rate = models.DecimalField(
        max_digits=30,
        decimal_places=12,
        null=True,
        blank=True,
    )
    exchange_rate_date = models.DateField(null=True, blank=True)
    valued_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=20, choices=Source, default=Source.MANUAL)
    status = models.CharField(max_length=20, choices=Status, default=Status.ACTIVE)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["account", "instrument"]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "instrument"],
                name="uniq_position_account_instrument",
            ),
            models.CheckConstraint(condition=~Q(quantity=0), name="position_quantity_non_zero"),
        ]

    def clean(self):
        super().clean()
        self.value_currency = self.value_currency.strip().upper()
        self.converted_currency = self.converted_currency.strip().upper()
        conversion_fields = (
            self.converted_value,
            self.converted_currency,
            self.exchange_rate,
            self.exchange_rate_date,
        )
        if any(value not in (None, "") for value in conversion_fields) and any(
            value in (None, "") for value in conversion_fields
        ):
            raise ValidationError(
                {"converted_value": "La valeur convertie exige devise, taux et date du taux."}
            )
        if self.converted_value is not None:
            if self.current_value is None:
                raise ValidationError(
                    {"current_value": "Une valeur d'origine est requise avant conversion."}
                )
            if self.value_currency == self.converted_currency and self.exchange_rate != 1:
                raise ValidationError(
                    {"exchange_rate": "Une conversion dans la même devise doit utiliser le taux 1."}
                )
            expected = _quantized_value(self.current_value * self.exchange_rate)
            if _quantized_value(self.converted_value) != expected:
                raise ValidationError(
                    {"converted_value": "La valeur convertie ne correspond pas au taux appliqué."}
                )

    def __str__(self):
        return f"{self.instrument} dans {self.account}"


class Transaction(models.Model):
    class Type(models.TextChoices):
        DEPOSIT = "DEPOSIT", "Dépôt"
        WITHDRAWAL = "WITHDRAWAL", "Retrait"
        BUY = "BUY", "Achat"
        SELL = "SELL", "Vente"
        TRANSFER = "TRANSFER", "Transfert"
        DIVIDEND = "DIVIDEND", "Dividende"
        INTEREST = "INTEREST", "Intérêt"
        FEE = "FEE", "Frais"
        TAX = "TAX", "Taxe"
        REFUND = "REFUND", "Remboursement"
        OTHER = "OTHER", "Autre"

    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        BOOKED = "BOOKED", "Comptabilisée"
        CANCELLED = "CANCELLED", "Annulée"

    class Source(models.TextChoices):
        MANUAL = "MANUAL", "Manuelle"
        IMPORT = "IMPORT", "Import"
        PROVIDER = "PROVIDER", "Fournisseur"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="financial_transactions",
    )
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="transactions")
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.PROTECT,
        related_name="transactions",
        null=True,
        blank=True,
    )
    external_id = models.CharField(max_length=255, blank=True)
    provider = models.CharField(max_length=50, blank=True)
    transaction_type = models.CharField(max_length=20, choices=Type)
    subtype = models.CharField(max_length=50, blank=True)
    quantity = models.DecimalField(
        max_digits=36,
        decimal_places=18,
        null=True,
        blank=True,
    )
    unit_price = models.DecimalField(
        max_digits=30,
        decimal_places=12,
        null=True,
        blank=True,
    )
    gross_amount = models.DecimalField(max_digits=30, decimal_places=8, null=True, blank=True)
    fees = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    taxes = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    net_amount = models.DecimalField(max_digits=30, decimal_places=8)
    currency = models.CharField(max_length=3, validators=[validate_currency_code])
    executed_at = models.DateTimeField(default=timezone.now)
    value_date = models.DateField(null=True, blank=True)
    label = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=Status, default=Status.BOOKED)
    source = models.CharField(max_length=20, choices=Source, default=Source.MANUAL)
    idempotency_key = models.CharField(max_length=255, blank=True)
    linked_transfer = models.OneToOneField(
        "self",
        on_delete=models.SET_NULL,
        related_name="reverse_linked_transfer",
        null=True,
        blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-executed_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "provider", "external_id"],
                condition=~Q(provider="") & ~Q(external_id=""),
                name="uniq_transaction_user_provider_external",
            ),
            models.UniqueConstraint(
                fields=["user", "idempotency_key"],
                condition=~Q(idempotency_key=""),
                name="uniq_transaction_user_idempotency",
            ),
            models.CheckConstraint(condition=~Q(net_amount=0), name="transaction_net_non_zero"),
            models.CheckConstraint(condition=Q(fees__gte=0), name="transaction_fees_positive"),
            models.CheckConstraint(condition=Q(taxes__gte=0), name="transaction_taxes_positive"),
        ]
        indexes = [
            models.Index(fields=["user", "-executed_at"], name="trx_user_executed_idx"),
            models.Index(fields=["account", "-executed_at"], name="trx_account_executed_idx"),
        ]

    def clean(self):
        super().clean()
        self.currency = self.currency.strip().upper()
        self.provider = self.provider.strip().lower()
        if (
            self.account_id
            and self.user_id
            and Account.objects.filter(pk=self.account_id)
            .exclude(user_id=self.user_id)
            .exists()
        ):
            raise ValidationError(
                {"account": "Le compte et la transaction doivent avoir le même propriétaire."}
            )
        if self.source != self.Source.MANUAL and not self.idempotency_key:
            raise ValidationError(
                {"idempotency_key": "Une clé d'idempotence est requise hors saisie manuelle."}
            )
        positive_types = {
            self.Type.DEPOSIT,
            self.Type.SELL,
            self.Type.DIVIDEND,
            self.Type.INTEREST,
            self.Type.REFUND,
        }
        negative_types = {
            self.Type.WITHDRAWAL,
            self.Type.BUY,
            self.Type.FEE,
            self.Type.TAX,
        }
        if self.transaction_type in positive_types and self.net_amount <= 0:
            raise ValidationError(
                {"net_amount": "Ce type de transaction exige un montant net positif."}
            )
        if self.transaction_type in negative_types and self.net_amount >= 0:
            raise ValidationError(
                {"net_amount": "Ce type de transaction exige un montant net négatif."}
            )
        if self.linked_transfer_id:
            linked = Transaction.objects.filter(pk=self.linked_transfer_id).first()
            if linked and (
                linked.user_id != self.user_id
                or linked.transaction_type != self.Type.TRANSFER
                or self.transaction_type != self.Type.TRANSFER
                or linked.account_id == self.account_id
                or linked.net_amount * self.net_amount >= 0
            ):
                raise ValidationError(
                    {
                        "linked_transfer": (
                            "Un transfert interne relie deux comptes du même utilisateur avec des signes opposés."
                        )
                    }
                )

    @property
    def is_internal_transfer(self):
        if self.transaction_type != self.Type.TRANSFER:
            return False
        if self.linked_transfer_id is not None:
            return True
        return bool(self.pk) and Transaction.objects.filter(linked_transfer_id=self.pk).exists()

    def __str__(self):
        return (
            f"{self.get_transaction_type_display()} – {self.net_amount} {self.currency} – "
            f"{self.executed_at:%d/%m/%Y}"
        )


class Price(models.Model):
    class Quality(models.TextChoices):
        FRESH = "FRESH", "À jour"
        STALE = "STALE", "Périmé"
        ERROR = "ERROR", "Erreur"

    class MarketState(models.TextChoices):
        PRE = "PRE", "Préouverture"
        REGULAR = "REGULAR", "Séance"
        POST = "POST", "Après séance"
        CLOSED = "CLOSED", "Marché fermé"
        UNKNOWN = "UNKNOWN", "Inconnu"

    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="prices")
    observed_at = models.DateTimeField()
    open_price = models.DecimalField(max_digits=30, decimal_places=12, null=True, blank=True)
    high_price = models.DecimalField(max_digits=30, decimal_places=12, null=True, blank=True)
    low_price = models.DecimalField(max_digits=30, decimal_places=12, null=True, blank=True)
    close_price = models.DecimalField(max_digits=30, decimal_places=12)
    volume = models.DecimalField(max_digits=36, decimal_places=12, null=True, blank=True)
    currency = models.CharField(max_length=3, validators=[validate_currency_code])
    source = models.CharField(max_length=50)
    collected_at = models.DateTimeField(default=timezone.now)
    is_delayed = models.BooleanField(default=False)
    quality = models.CharField(max_length=10, choices=Quality, default=Quality.FRESH)
    market_state = models.CharField(
        max_length=10,
        choices=MarketState,
        default=MarketState.UNKNOWN,
    )
    market_timezone = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["-observed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["instrument", "observed_at", "source"],
                name="uniq_price_instrument_observed_source",
            )
        ]
        indexes = [
            models.Index(fields=["instrument", "-observed_at"], name="price_instrument_time_idx")
        ]

    def clean(self):
        super().clean()
        self.currency = self.currency.strip().upper()
        self.source = self.source.strip().lower()

    def __str__(self):
        return f"{self.instrument} – {self.close_price} {self.currency}"


class ExchangeRate(models.Model):
    class Quality(models.TextChoices):
        FRESH = "FRESH", "À jour"
        STALE = "STALE", "Périmé"
        ERROR = "ERROR", "Erreur"

    base_currency = models.CharField(max_length=3, validators=[validate_currency_code])
    quote_currency = models.CharField(max_length=3, validators=[validate_currency_code])
    rate = models.DecimalField(max_digits=30, decimal_places=12)
    rate_date = models.DateField()
    source = models.CharField(max_length=50)
    collected_at = models.DateTimeField(default=timezone.now)
    quality = models.CharField(max_length=10, choices=Quality, default=Quality.FRESH)

    class Meta:
        ordering = ["-rate_date", "base_currency", "quote_currency"]
        constraints = [
            models.UniqueConstraint(
                fields=["base_currency", "quote_currency", "rate_date", "source"],
                name="uniq_fx_pair_date_source",
            ),
            models.CheckConstraint(condition=Q(rate__gt=0), name="exchange_rate_positive"),
            models.CheckConstraint(
                condition=~Q(base_currency=models.F("quote_currency")),
                name="exchange_rate_distinct_pair",
            ),
        ]

    def clean(self):
        super().clean()
        self.base_currency = self.base_currency.strip().upper()
        self.quote_currency = self.quote_currency.strip().upper()
        self.source = self.source.strip().lower()
        if self.base_currency == self.quote_currency:
            raise ValidationError("Les devises de base et de cotation doivent être différentes.")

    def __str__(self):
        return f"{self.base_currency}/{self.quote_currency} {self.rate} ({self.rate_date})"


class MarketDataPreference(models.Model):
    class Currency(models.TextChoices):
        EUR = "EUR", "Euro (EUR)"
        USD = "USD", "Dollar américain (USD)"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="market_data_preference",
    )
    reporting_currency = models.CharField(
        max_length=3,
        choices=Currency,
        default=Currency.EUR,
    )
    equity_display_currency = models.CharField(
        max_length=3,
        choices=Currency,
        default=Currency.EUR,
    )
    crypto_display_currency = models.CharField(
        max_length=3,
        choices=Currency,
        default=Currency.USD,
    )
    benchmark_symbol = models.CharField(max_length=30, default="^STOXX50E")
    benchmark_instrument = models.ForeignKey(
        Instrument,
        on_delete=models.SET_NULL,
        related_name="benchmark_preferences",
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        self.reporting_currency = self.reporting_currency.strip().upper()
        self.equity_display_currency = self.equity_display_currency.strip().upper()
        self.crypto_display_currency = self.crypto_display_currency.strip().upper()
        self.benchmark_symbol = self.benchmark_symbol.strip().upper()
        if self.benchmark_instrument_id:
            owner_id = (
                Instrument.objects.filter(pk=self.benchmark_instrument_id)
                .values_list("owner_id", flat=True)
                .first()
            )
            if owner_id not in {None, self.user_id}:
                raise ValidationError(
                    {"benchmark_instrument": "Le benchmark appartient à un autre utilisateur."}
                )

    def __str__(self):
        return f"Préférences de marché de {self.user}"


class MarketDataStatus(models.Model):
    class State(models.TextChoices):
        PENDING = "PENDING", "Jamais synchronisé"
        FRESH = "FRESH", "À jour"
        STALE = "STALE", "Périmé"
        ERROR = "ERROR", "En erreur"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="market_data_statuses",
    )
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.CASCADE,
        related_name="market_data_statuses",
    )
    provider = models.CharField(max_length=50)
    state = models.CharField(max_length=10, choices=State, default=State.PENDING)
    last_attempted_at = models.DateTimeField(null=True, blank=True)
    last_succeeded_at = models.DateTimeField(null=True, blank=True)
    last_price_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["state", "instrument__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "instrument", "provider"],
                name="uniq_market_status_user_instrument_provider",
            )
        ]
        indexes = [
            models.Index(fields=["user", "state"], name="market_user_state_idx"),
        ]

    def clean(self):
        super().clean()
        self.provider = self.provider.strip().lower()
        if self.instrument_id:
            has_access = Instrument.objects.filter(pk=self.instrument_id).filter(
                Q(owner_id=self.user_id) | Q(owner__isnull=True)
            ).exists()
            if not has_access:
                raise ValidationError(
                    {"instrument": "L’instrument n’est pas accessible à cet utilisateur."}
                )

    def __str__(self):
        return f"{self.instrument} — {self.provider} — {self.get_state_display()}"


class Snapshot(models.Model):
    class Scope(models.TextChoices):
        NET_WORTH = "NET_WORTH", "Patrimoine net"
        ACCOUNT = "ACCOUNT", "Compte"
        POSITION = "POSITION", "Position"

    class Source(models.TextChoices):
        CALCULATED = "CALCULATED", "Calculé"
        MANUAL = "MANUAL", "Manuel"
        PROVIDER = "PROVIDER", "Fournisseur"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="financial_snapshots",
    )
    scope = models.CharField(max_length=20, choices=Scope)
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name="snapshots",
        null=True,
        blank=True,
    )
    position = models.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        related_name="snapshots",
        null=True,
        blank=True,
    )
    observed_at = models.DateTimeField()
    original_value = models.DecimalField(max_digits=30, decimal_places=8)
    original_currency = models.CharField(max_length=3, validators=[validate_currency_code])
    converted_value = models.DecimalField(max_digits=30, decimal_places=8)
    converted_currency = models.CharField(max_length=3, validators=[validate_currency_code])
    exchange_rate = models.DecimalField(max_digits=30, decimal_places=12)
    exchange_rate_date = models.DateField()
    source = models.CharField(max_length=20, choices=Source, default=Source.CALCULATED)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-observed_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(scope="NET_WORTH", account__isnull=True, position__isnull=True)
                    | Q(scope="ACCOUNT", account__isnull=False, position__isnull=True)
                    | Q(scope="POSITION", account__isnull=True, position__isnull=False)
                ),
                name="snapshot_scope_matches_target",
            ),
            models.CheckConstraint(condition=Q(exchange_rate__gt=0), name="snapshot_rate_positive"),
            models.UniqueConstraint(
                fields=["user", "observed_at", "source"],
                condition=Q(scope="NET_WORTH"),
                name="uniq_networth_snapshot",
            ),
            models.UniqueConstraint(
                fields=["account", "observed_at", "source"],
                condition=Q(scope="ACCOUNT"),
                name="uniq_account_snapshot",
            ),
            models.UniqueConstraint(
                fields=["position", "observed_at", "source"],
                condition=Q(scope="POSITION"),
                name="uniq_position_snapshot",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "scope", "-observed_at"], name="snapshot_user_scope_idx")
        ]

    def clean(self):
        super().clean()
        self.original_currency = self.original_currency.strip().upper()
        self.converted_currency = self.converted_currency.strip().upper()
        if self.original_currency == self.converted_currency and self.exchange_rate != 1:
            raise ValidationError(
                {"exchange_rate": "Une conversion dans la même devise doit utiliser le taux 1."}
            )
        expected = _quantized_value(self.original_value * self.exchange_rate)
        if _quantized_value(self.converted_value) != expected:
            raise ValidationError(
                {"converted_value": "La valeur convertie ne correspond pas au taux appliqué."}
            )
        if self.account_id:
            account_user_id = (
                Account.objects.filter(pk=self.account_id).values_list("user_id", flat=True).first()
            )
            if account_user_id and account_user_id != self.user_id:
                raise ValidationError(
                    {"account": "Le snapshot et le compte doivent avoir le même propriétaire."}
                )
        if self.position_id:
            position_user_id = (
                Position.objects.filter(pk=self.position_id)
                .values_list("account__user_id", flat=True)
                .first()
            )
            if position_user_id and position_user_id != self.user_id:
                raise ValidationError(
                    {"position": "Le snapshot et la position doivent avoir le même propriétaire."}
                )

    def __str__(self):
        return f"{self.get_scope_display()} – {self.converted_value} {self.converted_currency}"


class ExternalIdentifier(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="financial_external_identifiers",
    )
    provider = models.CharField(max_length=50)
    external_id = models.CharField(max_length=255)
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name="external_identifiers",
        null=True,
        blank=True,
    )
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.CASCADE,
        related_name="external_identifiers",
        null=True,
        blank=True,
    )
    connection = models.ForeignKey(
        Connection,
        on_delete=models.CASCADE,
        related_name="external_identifiers",
        null=True,
        blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["provider", "external_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "provider", "external_id"],
                name="uniq_external_identifier_user_provider",
            ),
            models.CheckConstraint(
                condition=(
                    Q(account__isnull=False, instrument__isnull=True, connection__isnull=True)
                    | Q(account__isnull=True, instrument__isnull=False, connection__isnull=True)
                    | Q(account__isnull=True, instrument__isnull=True, connection__isnull=False)
                ),
                name="external_identifier_exactly_one_target",
            ),
        ]

    def clean(self):
        super().clean()
        self.provider = self.provider.strip().lower()
        if self.account_id:
            account_user_id = (
                Account.objects.filter(pk=self.account_id).values_list("user_id", flat=True).first()
            )
            if account_user_id and account_user_id != self.user_id:
                raise ValidationError(
                    {"account": "L'identifiant et le compte doivent avoir le même propriétaire."}
                )
        if self.connection_id:
            connection_user_id = (
                Connection.objects.filter(pk=self.connection_id)
                .values_list("user_id", flat=True)
                .first()
            )
            if connection_user_id and connection_user_id != self.user_id:
                raise ValidationError(
                    {
                        "connection": (
                            "L'identifiant et la connexion doivent avoir le même propriétaire."
                        )
                    }
                )

    def __str__(self):
        return f"{self.provider}:{self.external_id}"


class Watchlist(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="financial_watchlists",
    )
    name = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="uniq_watchlist_user_name")
        ]

    def __str__(self):
        return f"{self.name} ({self.user})"


class WatchInstrument(models.Model):
    watchlist = models.ForeignKey(Watchlist, on_delete=models.CASCADE, related_name="items")
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["watchlist", "instrument"],
                name="uniq_watchlist_instrument",
            )
        ]

    def __str__(self):
        return f"{self.watchlist.name} – {self.instrument}"


class Frequency(models.TextChoices):
    DAILY = "DAILY", "Quotidien"
    WEEKLY = "WEEKLY", "Hebdomadaire"
    MONTHLY = "MONTHLY", "Mensuel"
    YEARLY = "YEARLY", "Annuel"
    PERSONALIZED = "PERSONALIZED", "Personnalisé"


class RecurringEntry(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=30, decimal_places=8)
    currency = models.CharField(
        max_length=3,
        default="EUR",
        validators=[validate_currency_code],
    )
    freq = models.CharField(max_length=20, choices=Frequency)
    freq_custom = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Nombre de jours entre chaque échéance si la fréquence est personnalisée.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        self.currency = self.currency.strip().upper()
        if self.freq == Frequency.PERSONALIZED and not self.freq_custom:
            raise ValidationError({"freq_custom": "Nombre de jours positif requis."})
        if self.freq != Frequency.PERSONALIZED and self.freq_custom is not None:
            raise ValidationError({"freq_custom": "Doit être vide si la fréquence est standard."})


class Subscription(RecurringEntry):
    next_due = models.DateField()

    class Meta:
        ordering = ["next_due", "name"]

    def __str__(self):
        return f"{self.name} – {self.amount} {self.currency}"


class Income(RecurringEntry):
    next_payday = models.DateField()

    class Meta:
        ordering = ["next_payday", "name"]

    def __str__(self):
        return f"{self.name} – {self.amount} {self.currency}"


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"Notification {self.user} – {self.created:%Y-%m-%d %H:%M}"


class Loan(models.Model):
    class Type(models.TextChoices):
        AMORTIZING_FIXED = "AMORT_FIXED", "Amortissable à taux fixe"
        VARIABLE = "VARIABLE", "Taux variable"
        INTEREST_ONLY = "INTEREST_ONLY", "In fine"
        CONSUMER = "CONSUMER", "Crédit à la consommation"
        OTHER = "OTHER", "Autre"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loans",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        related_name="loans",
        null=True,
        blank=True,
    )
    manual_reference = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    loan_type = models.CharField(max_length=20, choices=Type, default=Type.AMORTIZING_FIXED)
    currency = models.CharField(max_length=3, default="EUR", validators=[validate_currency_code])
    original_principal = models.DecimalField(max_digits=30, decimal_places=8)
    outstanding_principal = models.DecimalField(max_digits=30, decimal_places=8)
    balance_date = models.DateField(
        default=timezone.localdate,
        help_text="Date d'observation du capital restant dû.",
    )
    nominal_rate = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        help_text="Taux nominal annuel en pourcentage.",
    )
    apr = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    duration_months = models.PositiveIntegerField()
    start_date = models.DateField()
    maturity_date = models.DateField(null=True, blank=True)
    payment_amount = models.DecimalField(max_digits=30, decimal_places=8, null=True, blank=True)
    insurance_amount = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    insurance_rate = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    initial_fees = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    deferred_months = models.PositiveIntegerField(default=0)
    archived = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["archived", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "manual_reference"],
                name="uniq_loan_user_manual_ref",
            ),
            models.CheckConstraint(
                condition=Q(original_principal__gt=0),
                name="loan_original_principal_positive",
            ),
            models.CheckConstraint(
                condition=Q(outstanding_principal__gte=0),
                name="loan_outstanding_principal_positive",
            ),
            models.CheckConstraint(condition=Q(nominal_rate__gte=0), name="loan_rate_positive"),
            models.CheckConstraint(condition=Q(duration_months__gt=0), name="loan_duration_positive"),
            models.CheckConstraint(
                condition=Q(outstanding_principal__lte=models.F("original_principal")),
                name="loan_outstanding_lte_original",
            ),
            models.CheckConstraint(condition=Q(initial_fees__gte=0), name="loan_fees_positive"),
            models.CheckConstraint(
                condition=Q(insurance_amount__gte=0),
                name="loan_insurance_positive",
            ),
        ]
        indexes = [models.Index(fields=["user", "archived"], name="loan_user_archived_idx")]

    def clean(self):
        super().clean()
        self.currency = self.currency.strip().upper()
        self.manual_reference = self.manual_reference.strip()
        if (
            self.account_id
            and self.user_id
            and Account.objects.filter(pk=self.account_id)
            .exclude(user_id=self.user_id)
            .exists()
        ):
            raise ValidationError(
                {"account": "Le prêt et le compte doivent avoir le même propriétaire."}
            )
        if self.maturity_date and self.maturity_date < self.start_date:
            raise ValidationError({"maturity_date": "L'échéance ne peut pas précéder le début."})
        if self.outstanding_principal > self.original_principal:
            raise ValidationError(
                {"outstanding_principal": "Le capital restant ne peut pas dépasser le capital initial."}
            )
        if self.deferred_months >= self.duration_months:
            raise ValidationError(
                {"deferred_months": "Le différé doit être inférieur à la durée du prêt."}
            )

    def __str__(self):
        return f"{self.name} – {self.outstanding_principal} {self.currency}"


class LoanBalanceSnapshot(models.Model):
    loan = models.ForeignKey(
        Loan,
        on_delete=models.CASCADE,
        related_name="balance_snapshots",
    )
    outstanding_principal = models.DecimalField(max_digits=30, decimal_places=8)
    observed_on = models.DateField()
    source = models.CharField(max_length=100, default="manual")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-observed_on", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["loan", "observed_on", "source"],
                name="uniq_loan_balance_date_source",
            ),
            models.CheckConstraint(
                condition=Q(outstanding_principal__gte=0),
                name="loan_snapshot_balance_positive",
            ),
        ]

    def clean(self):
        super().clean()
        self.source = self.source.strip().lower()
        if self.loan_id and self.outstanding_principal > self.loan.original_principal:
            raise ValidationError(
                {"outstanding_principal": "Le solde ne peut pas dépasser le capital initial."}
            )

    def __str__(self):
        return f"{self.loan.name} – {self.outstanding_principal} ({self.observed_on})"


class RealEstate(models.Model):
    class Type(models.TextChoices):
        APARTMENT = "APARTMENT", "Appartement"
        HOUSE = "HOUSE", "Maison"
        LAND = "LAND", "Terrain"
        SCPI = "SCPI", "SCPI"
        COMMERCIAL = "COMMERCIAL", "Local commercial"
        OTHER = "OTHER", "Autre"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="real_estate_assets",
    )
    linked_loan = models.ForeignKey(
        Loan,
        on_delete=models.SET_NULL,
        related_name="properties",
        null=True,
        blank=True,
    )
    manual_reference = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    property_type = models.CharField(max_length=20, choices=Type)
    address = models.TextField(blank=True)
    surface_sqm = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    ownership_share = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("100"))
    currency = models.CharField(max_length=3, default="EUR", validators=[validate_currency_code])
    purchase_price = models.DecimalField(max_digits=30, decimal_places=8)
    purchase_costs = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    renovation_costs = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    estimated_value = models.DecimalField(max_digits=30, decimal_places=8)
    valuation_date = models.DateField()
    valuation_source = models.CharField(max_length=100, default="manual")
    monthly_rent = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    monthly_charges = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    annual_property_tax = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    annual_insurance = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    annual_other_costs = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    vacancy_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Hypothèse annuelle de vacance locative, en pourcentage.",
    )
    archived = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["archived", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "manual_reference"],
                name="uniq_realestate_user_manual_ref",
            ),
            models.CheckConstraint(
                condition=Q(ownership_share__gt=0) & Q(ownership_share__lte=100),
                name="realestate_valid_ownership_share",
            ),
            models.CheckConstraint(
                condition=Q(purchase_price__gte=0),
                name="realestate_purchase_positive",
            ),
            models.CheckConstraint(
                condition=Q(estimated_value__gte=0),
                name="realestate_value_positive",
            ),
            models.CheckConstraint(
                condition=Q(surface_sqm__isnull=True) | Q(surface_sqm__gt=0),
                name="realestate_surface_positive",
            ),
            models.CheckConstraint(condition=Q(purchase_costs__gte=0), name="realestate_costs_positive"),
            models.CheckConstraint(
                condition=Q(renovation_costs__gte=0),
                name="realestate_renovation_positive",
            ),
            models.CheckConstraint(condition=Q(monthly_rent__gte=0), name="realestate_rent_positive"),
            models.CheckConstraint(
                condition=Q(monthly_charges__gte=0),
                name="realestate_charges_positive",
            ),
            models.CheckConstraint(
                condition=Q(annual_property_tax__gte=0),
                name="realestate_tax_positive",
            ),
            models.CheckConstraint(
                condition=Q(annual_insurance__gte=0),
                name="realestate_insurance_positive",
            ),
            models.CheckConstraint(
                condition=Q(annual_other_costs__gte=0),
                name="realestate_other_costs_positive",
            ),
            models.CheckConstraint(
                condition=Q(vacancy_rate__gte=0) & Q(vacancy_rate__lte=100),
                name="realestate_vacancy_rate_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "archived"], name="realestate_user_archived_idx")
        ]

    def clean(self):
        super().clean()
        self.currency = self.currency.strip().upper()
        self.manual_reference = self.manual_reference.strip()
        if (
            self.linked_loan_id
            and self.user_id
            and Loan.objects.filter(pk=self.linked_loan_id)
            .exclude(user_id=self.user_id)
            .exists()
        ):
            raise ValidationError(
                {"linked_loan": "Le bien et le prêt doivent avoir le même propriétaire."}
            )

    @property
    def owned_value(self):
        return _quantized_value(self.estimated_value * self.ownership_share / Decimal("100"))

    @property
    def net_value(self):
        if self.linked_loan_id and self.linked_loan.currency != self.currency:
            return None
        liability = self.linked_loan.outstanding_principal if self.linked_loan_id else Decimal("0")
        return _quantized_value(self.owned_value - liability)

    def __str__(self):
        return f"{self.name} – {self.estimated_value} {self.currency}"


class RealEstateValuation(models.Model):
    real_estate = models.ForeignKey(
        RealEstate,
        on_delete=models.CASCADE,
        related_name="valuations",
    )
    value = models.DecimalField(max_digits=30, decimal_places=8)
    valuation_date = models.DateField()
    source = models.CharField(max_length=100, default="manual")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-valuation_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["real_estate", "valuation_date", "source"],
                name="uniq_realestate_valuation_date_source",
            ),
            models.CheckConstraint(condition=Q(value__gte=0), name="realestate_valuation_positive"),
        ]

    def __str__(self):
        return f"{self.real_estate.name} – {self.value} ({self.valuation_date})"


class PrivateEquityHolding(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="private_equity_holdings",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        related_name="private_equity_holdings",
        null=True,
        blank=True,
    )
    manual_reference = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    company_or_fund = models.CharField(max_length=255)
    vintage_year = models.PositiveSmallIntegerField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="EUR", validators=[validate_currency_code])
    commitment = models.DecimalField(max_digits=30, decimal_places=8)
    called_capital = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    distributions = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    net_asset_value = models.DecimalField(max_digits=30, decimal_places=8)
    valuation_date = models.DateField()
    valuation_source = models.CharField(max_length=100, default="manual")
    ownership_share = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("100"))
    archived = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["archived", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "manual_reference"],
                name="uniq_privateequity_user_manual_ref",
            ),
            models.CheckConstraint(
                condition=Q(ownership_share__gt=0) & Q(ownership_share__lte=100),
                name="privateequity_valid_ownership_share",
            ),
            models.CheckConstraint(condition=Q(commitment__gte=0), name="pe_commitment_positive"),
            models.CheckConstraint(condition=Q(called_capital__gte=0), name="pe_called_positive"),
            models.CheckConstraint(condition=Q(distributions__gte=0), name="pe_distributions_positive"),
            models.CheckConstraint(condition=Q(net_asset_value__gte=0), name="pe_nav_positive"),
            models.CheckConstraint(
                condition=Q(called_capital__lte=models.F("commitment")),
                name="pe_called_lte_commitment",
            ),
        ]

    def clean(self):
        super().clean()
        self.currency = self.currency.strip().upper()
        self.manual_reference = self.manual_reference.strip()
        if (
            self.account_id
            and self.user_id
            and Account.objects.filter(pk=self.account_id)
            .exclude(user_id=self.user_id)
            .exists()
        ):
            raise ValidationError(
                {"account": "La participation et le compte doivent avoir le même propriétaire."}
            )
        if self.called_capital > self.commitment:
            raise ValidationError(
                {"called_capital": "Le capital appelé ne peut pas dépasser l'engagement."}
            )

    def __str__(self):
        return f"{self.name} – {self.net_asset_value} {self.currency}"


class PrivateEquityValuation(models.Model):
    holding = models.ForeignKey(
        PrivateEquityHolding,
        on_delete=models.CASCADE,
        related_name="valuations",
    )
    net_asset_value = models.DecimalField(max_digits=30, decimal_places=8)
    called_capital = models.DecimalField(max_digits=30, decimal_places=8)
    distributions = models.DecimalField(max_digits=30, decimal_places=8)
    valuation_date = models.DateField()
    source = models.CharField(max_length=100, default="manual")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-valuation_date", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["holding", "valuation_date", "source"],
                name="uniq_pe_valuation_date_source",
            ),
            models.CheckConstraint(condition=Q(net_asset_value__gte=0), name="pe_val_nav_positive"),
            models.CheckConstraint(condition=Q(called_capital__gte=0), name="pe_val_called_positive"),
            models.CheckConstraint(condition=Q(distributions__gte=0), name="pe_val_dist_positive"),
        ]

    def clean(self):
        super().clean()
        self.source = self.source.strip().lower()
        if self.holding_id and self.called_capital > self.holding.commitment:
            raise ValidationError(
                {"called_capital": "Le capital appelé ne peut pas dépasser l'engagement."}
            )

    def __str__(self):
        return f"{self.holding.name} – {self.net_asset_value} ({self.valuation_date})"


class LoanSimulationScenario(models.Model):
    """Private assumptions for a simulation, never a real financial liability."""

    class CalculationMode(models.TextChoices):
        PAYMENT = "PAYMENT", "Calculer la mensualité"
        DURATION = "DURATION", "Calculer la durée"

    class InsuranceMode(models.TextChoices):
        FIXED = "FIXED", "Montant mensuel fixe"
        PERCENT = "PERCENT", "Pourcentage annuel"

    class InsuranceBasis(models.TextChoices):
        INITIAL = "INITIAL", "Capital initial"
        OUTSTANDING = "OUTSTANDING", "Capital restant dû"

    class DefermentType(models.TextChoices):
        NONE = "NONE", "Aucun"
        PARTIAL = "PARTIAL", "Partiel — intérêts payés"
        TOTAL = "TOTAL", "Total — intérêts capitalisés"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loan_simulation_scenarios",
    )
    name = models.CharField(max_length=255)
    currency = models.CharField(max_length=3, default="EUR", validators=[validate_currency_code])
    principal = models.DecimalField(max_digits=30, decimal_places=8)
    annual_rate = models.DecimalField(max_digits=9, decimal_places=6)
    calculation_mode = models.CharField(
        max_length=10,
        choices=CalculationMode,
        default=CalculationMode.PAYMENT,
    )
    duration_months = models.PositiveSmallIntegerField(null=True, blank=True)
    target_payment = models.DecimalField(
        max_digits=30,
        decimal_places=8,
        null=True,
        blank=True,
    )
    insurance_mode = models.CharField(
        max_length=10,
        choices=InsuranceMode,
        default=InsuranceMode.FIXED,
    )
    insurance_value = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    insurance_basis = models.CharField(
        max_length=12,
        choices=InsuranceBasis,
        default=InsuranceBasis.INITIAL,
    )
    initial_fees = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    deferment_months = models.PositiveSmallIntegerField(default=0)
    deferment_type = models.CharField(
        max_length=10,
        choices=DefermentType,
        default=DefermentType.NONE,
    )
    one_off_prepayment = models.DecimalField(
        max_digits=30,
        decimal_places=8,
        default=Decimal("0"),
    )
    one_off_prepayment_month = models.PositiveSmallIntegerField(null=True, blank=True)
    recurring_prepayment = models.DecimalField(
        max_digits=30,
        decimal_places=8,
        default=Decimal("0"),
    )
    recurring_prepayment_start_month = models.PositiveSmallIntegerField(null=True, blank=True)
    start_date = models.DateField(default=timezone.localdate)
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["archived", "name", "pk"]
        constraints = [
            models.CheckConstraint(condition=Q(principal__gt=0), name="loan_sim_principal_positive"),
            models.CheckConstraint(condition=Q(annual_rate__gte=0), name="loan_sim_rate_positive"),
            models.CheckConstraint(
                condition=Q(duration_months__isnull=True)
                | (Q(duration_months__gte=1) & Q(duration_months__lte=1200)),
                name="loan_sim_duration_valid",
            ),
            models.CheckConstraint(
                condition=Q(target_payment__isnull=True) | Q(target_payment__gt=0),
                name="loan_sim_payment_positive",
            ),
            models.CheckConstraint(
                condition=Q(insurance_value__gte=0),
                name="loan_sim_insurance_positive",
            ),
            models.CheckConstraint(
                condition=Q(initial_fees__gte=0),
                name="loan_sim_fees_positive",
            ),
            models.CheckConstraint(
                condition=Q(deferment_months__lte=1199),
                name="loan_sim_deferment_valid",
            ),
            models.CheckConstraint(
                condition=Q(one_off_prepayment__gte=0),
                name="loan_sim_oneoff_positive",
            ),
            models.CheckConstraint(
                condition=Q(recurring_prepayment__gte=0),
                name="loan_sim_recurring_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "archived"], name="loan_sim_user_archived_idx")
        ]

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        self.currency = self.currency.strip().upper()
        if self.calculation_mode == self.CalculationMode.PAYMENT:
            if not self.duration_months:
                raise ValidationError({"duration_months": "La durée est obligatoire."})
            if self.deferment_months >= self.duration_months:
                raise ValidationError(
                    {"deferment_months": "Le différé doit être inférieur à la durée totale."}
                )
        elif not self.target_payment or self.target_payment <= 0:
            raise ValidationError(
                {"target_payment": "La mensualité cible est obligatoire et positive."}
            )
        if self.deferment_type == self.DefermentType.NONE and self.deferment_months:
            raise ValidationError(
                {"deferment_months": "Choisissez un type de différé ou saisissez zéro."}
            )
        for amount_field, month_field in (
            ("one_off_prepayment", "one_off_prepayment_month"),
            ("recurring_prepayment", "recurring_prepayment_start_month"),
        ):
            amount = getattr(self, amount_field)
            month = getattr(self, month_field)
            if amount > 0 and not month:
                raise ValidationError({month_field: "Indiquez le mois de départ."})
            if amount == 0 and month:
                raise ValidationError({amount_field: "Indiquez un montant positif."})

    def __str__(self):
        return f"Simulation prêt — {self.name}"


class CompoundInterestScenario(models.Model):
    """Private investment projection, entirely separate from real accounts."""

    class ContributionFrequency(models.TextChoices):
        MONTHLY = "MONTHLY", "Mensuelle"
        QUARTERLY = "QUARTERLY", "Trimestrielle"
        SEMIANNUAL = "SEMIANNUAL", "Semestrielle"
        ANNUAL = "ANNUAL", "Annuelle"

    class ContributionTiming(models.TextChoices):
        BEGIN = "BEGIN", "Début de période"
        END = "END", "Fin de période"

    class TaxMode(models.TextChoices):
        NONE = "NONE", "Aucune fiscalité"
        FINAL_GAINS = "FINAL_GAINS", "Taux unique sur les gains finaux"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="compound_interest_scenarios",
    )
    name = models.CharField(max_length=255)
    currency = models.CharField(max_length=3, default="EUR", validators=[validate_currency_code])
    initial_capital = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    periodic_contribution = models.DecimalField(
        max_digits=30,
        decimal_places=8,
        default=Decimal("0"),
    )
    contribution_frequency = models.CharField(
        max_length=12,
        choices=ContributionFrequency,
        default=ContributionFrequency.MONTHLY,
    )
    contribution_timing = models.CharField(
        max_length=8,
        choices=ContributionTiming,
        default=ContributionTiming.END,
    )
    duration_years = models.PositiveSmallIntegerField(default=20)
    annual_return = models.DecimalField(max_digits=9, decimal_places=6, default=Decimal("5"))
    annual_fees = models.DecimalField(max_digits=9, decimal_places=6, default=Decimal("0"))
    annual_inflation = models.DecimalField(max_digits=9, decimal_places=6, default=Decimal("2"))
    tax_mode = models.CharField(max_length=12, choices=TaxMode, default=TaxMode.NONE)
    tax_rate = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0"))
    start_date = models.DateField(default=timezone.localdate)
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["archived", "name", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(initial_capital__gte=0),
                name="compound_sim_initial_positive",
            ),
            models.CheckConstraint(
                condition=Q(periodic_contribution__gte=0),
                name="compound_sim_contribution_positive",
            ),
            models.CheckConstraint(
                condition=Q(duration_years__gte=1) & Q(duration_years__lte=100),
                name="compound_sim_duration_valid",
            ),
            models.CheckConstraint(
                condition=Q(annual_return__gt=-100),
                name="compound_sim_return_valid",
            ),
            models.CheckConstraint(
                condition=Q(annual_fees__gte=0) & Q(annual_fees__lte=100),
                name="compound_sim_fees_valid",
            ),
            models.CheckConstraint(
                condition=Q(annual_inflation__gte=0),
                name="compound_sim_inflation_positive",
            ),
            models.CheckConstraint(
                condition=Q(tax_rate__gte=0) & Q(tax_rate__lte=100),
                name="compound_sim_tax_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "archived"], name="compound_user_archived_idx")
        ]

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        self.currency = self.currency.strip().upper()
        if self.initial_capital == 0 and self.periodic_contribution == 0:
            raise ValidationError(
                "Indiquez un capital initial ou un versement périodique positif."
            )
        if self.tax_mode == self.TaxMode.NONE and self.tax_rate:
            raise ValidationError(
                {"tax_rate": "Choisissez une fiscalité ou saisissez un taux nul."}
            )

    def __str__(self):
        return f"Simulation intérêts composés — {self.name}"


class VirtualPortfolio(models.Model):
    """Paper-trading account with no connector or real-account relationship."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="virtual_portfolios",
    )
    name = models.CharField(max_length=255)
    base_currency = models.CharField(
        max_length=3,
        default="EUR",
        validators=[validate_currency_code],
    )
    initial_cash = models.DecimalField(max_digits=30, decimal_places=8)
    cash_balance = models.DecimalField(max_digits=30, decimal_places=8)
    benchmark_instrument = models.ForeignKey(
        Instrument,
        on_delete=models.SET_NULL,
        related_name="virtual_benchmark_portfolios",
        null=True,
        blank=True,
    )
    proportional_fee_rate = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=Decimal("0"),
        help_text="Pourcentage appliqué au montant brut de chaque ordre.",
    )
    fixed_fee = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    spread_bps = models.DecimalField(max_digits=9, decimal_places=4, default=Decimal("0"))
    slippage_bps = models.DecimalField(max_digits=9, decimal_places=4, default=Decimal("0"))
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["archived", "name", "pk"]
        constraints = [
            models.CheckConstraint(condition=Q(initial_cash__gt=0), name="virtual_initial_cash_pos"),
            models.CheckConstraint(condition=Q(cash_balance__gte=0), name="virtual_cash_nonnegative"),
            models.CheckConstraint(
                condition=Q(proportional_fee_rate__gte=0)
                & Q(proportional_fee_rate__lte=100),
                name="virtual_fee_rate_valid",
            ),
            models.CheckConstraint(condition=Q(fixed_fee__gte=0), name="virtual_fixed_fee_pos"),
            models.CheckConstraint(condition=Q(spread_bps__gte=0), name="virtual_spread_pos"),
            models.CheckConstraint(condition=Q(slippage_bps__gte=0), name="virtual_slippage_pos"),
        ]
        indexes = [
            models.Index(fields=["user", "archived"], name="virtual_user_archived_idx")
        ]

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        self.base_currency = self.base_currency.strip().upper()
        if (
            self.benchmark_instrument_id
            and self.user_id
            and self.benchmark_instrument.owner_id not in {None, self.user_id}
        ):
            raise ValidationError(
                {"benchmark_instrument": "Ce benchmark appartient à un autre utilisateur."}
            )

    def __str__(self):
        return f"Portefeuille virtuel — {self.name}"


class VirtualWatchlistEntry(models.Model):
    portfolio = models.ForeignKey(
        VirtualPortfolio,
        on_delete=models.CASCADE,
        related_name="watchlist_entries",
    )
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.PROTECT,
        related_name="virtual_watchlist_entries",
    )
    allow_fractional = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["instrument__name", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "instrument"],
                name="uniq_virtual_watch_instrument",
            )
        ]

    def clean(self):
        super().clean()
        if (
            self.portfolio_id
            and self.instrument_id
            and self.instrument.owner_id not in {None, self.portfolio.user_id}
        ):
            raise ValidationError({"instrument": "Cet instrument est inaccessible."})

    def __str__(self):
        return f"{self.instrument} — {self.portfolio.name}"


class VirtualPosition(models.Model):
    portfolio = models.ForeignKey(
        VirtualPortfolio,
        on_delete=models.CASCADE,
        related_name="virtual_positions",
    )
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.PROTECT,
        related_name="virtual_positions",
    )
    quantity = models.DecimalField(max_digits=36, decimal_places=18, default=Decimal("0"))
    average_unit_cost = models.DecimalField(max_digits=30, decimal_places=12)
    realized_gain = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    dividend_income = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["instrument__name", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "instrument"],
                name="uniq_virtual_position_instrument",
            ),
            models.CheckConstraint(condition=Q(quantity__gte=0), name="virtual_position_qty_pos"),
            models.CheckConstraint(
                condition=Q(average_unit_cost__gte=0),
                name="virtual_position_cost_pos",
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.portfolio_id
            and self.instrument_id
            and self.instrument.owner_id not in {None, self.portfolio.user_id}
        ):
            raise ValidationError({"instrument": "Cet instrument est inaccessible."})

    def __str__(self):
        return f"{self.quantity} {self.instrument} — {self.portfolio.name}"


class VirtualOrder(models.Model):
    class Side(models.TextChoices):
        BUY = "BUY", "Achat"
        SELL = "SELL", "Vente"

    class OrderType(models.TextChoices):
        MARKET = "MARKET", "Au marché"
        LIMIT = "LIMIT", "À cours limité"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Ouvert"
        EXECUTED = "EXECUTED", "Exécuté"
        CANCELLED = "CANCELLED", "Annulé"
        REJECTED = "REJECTED", "Rejeté"

    client_order_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    portfolio = models.ForeignKey(
        VirtualPortfolio,
        on_delete=models.CASCADE,
        related_name="virtual_orders",
    )
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.PROTECT,
        related_name="virtual_orders",
    )
    side = models.CharField(max_length=4, choices=Side)
    order_type = models.CharField(max_length=6, choices=OrderType)
    quantity = models.DecimalField(max_digits=36, decimal_places=18)
    limit_price = models.DecimalField(max_digits=30, decimal_places=12, null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status, default=Status.OPEN)
    submitted_at = models.DateTimeField(default=timezone.now)
    executed_at = models.DateTimeField(null=True, blank=True)
    execution_unit_price = models.DecimalField(
        max_digits=30,
        decimal_places=12,
        null=True,
        blank=True,
    )
    gross_amount = models.DecimalField(max_digits=30, decimal_places=8, null=True, blank=True)
    fees = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    cash_effect = models.DecimalField(max_digits=30, decimal_places=8, null=True, blank=True)
    price_observed_at = models.DateTimeField(null=True, blank=True)
    price_source = models.CharField(max_length=50, blank=True)
    price_is_delayed = models.BooleanField(default=False)
    price_market_state = models.CharField(max_length=10, blank=True)
    status_message = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-submitted_at", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="virtual_order_qty_pos"),
            models.CheckConstraint(
                condition=Q(limit_price__isnull=True) | Q(limit_price__gt=0),
                name="virtual_order_limit_pos",
            ),
            models.CheckConstraint(condition=Q(fees__gte=0), name="virtual_order_fees_pos"),
        ]
        indexes = [
            models.Index(
                fields=["portfolio", "status", "submitted_at"],
                name="virtual_order_status_idx",
            )
        ]

    def clean(self):
        super().clean()
        if self.order_type == self.OrderType.LIMIT and self.limit_price is None:
            raise ValidationError({"limit_price": "Un cours limite est obligatoire."})
        if self.order_type == self.OrderType.MARKET and self.limit_price is not None:
            raise ValidationError({"limit_price": "Un ordre au marché n'a pas de limite."})
        if (
            self.portfolio_id
            and self.instrument_id
            and self.instrument.owner_id not in {None, self.portfolio.user_id}
        ):
            raise ValidationError({"instrument": "Cet instrument est inaccessible."})

    def __str__(self):
        return f"{self.get_side_display()} {self.quantity} {self.instrument} ({self.get_status_display()})"


class VirtualCashEvent(models.Model):
    class Type(models.TextChoices):
        INITIAL = "INITIAL", "Capital initial"
        BUY = "BUY", "Achat"
        SELL = "SELL", "Vente"
        DIVIDEND = "DIVIDEND", "Dividende"
        RESET = "RESET", "Remise à zéro"
        CLONE = "CLONE", "Clonage"

    portfolio = models.ForeignKey(
        VirtualPortfolio,
        on_delete=models.CASCADE,
        related_name="cash_events",
    )
    event_type = models.CharField(max_length=10, choices=Type)
    amount = models.DecimalField(max_digits=30, decimal_places=8)
    balance_after = models.DecimalField(max_digits=30, decimal_places=8)
    order = models.OneToOneField(
        VirtualOrder,
        on_delete=models.SET_NULL,
        related_name="cash_event",
        null=True,
        blank=True,
    )
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.SET_NULL,
        related_name="virtual_cash_events",
        null=True,
        blank=True,
    )
    label = models.CharField(max_length=255, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at", "-pk"]
        indexes = [
            models.Index(
                fields=["portfolio", "-occurred_at"],
                name="virtual_cash_time_idx",
            )
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} {self.amount} — {self.portfolio.name}"


class VirtualCorporateAction(models.Model):
    class Type(models.TextChoices):
        DIVIDEND = "DIVIDEND", "Dividende"
        SPLIT = "SPLIT", "Division d'actions"

    class Status(models.TextChoices):
        PENDING = "PENDING", "À appliquer"
        APPLIED = "APPLIED", "Appliqué"
        REJECTED = "REJECTED", "Rejeté"

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    portfolio = models.ForeignKey(
        VirtualPortfolio,
        on_delete=models.CASCADE,
        related_name="corporate_actions",
    )
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.PROTECT,
        related_name="virtual_corporate_actions",
    )
    action_type = models.CharField(max_length=10, choices=Type)
    effective_at = models.DateTimeField(default=timezone.now)
    dividend_per_unit = models.DecimalField(
        max_digits=30,
        decimal_places=12,
        null=True,
        blank=True,
    )
    split_ratio = models.DecimalField(
        max_digits=30,
        decimal_places=12,
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)
    status_message = models.CharField(max_length=255, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(dividend_per_unit__isnull=True) | Q(dividend_per_unit__gt=0),
                name="virtual_dividend_pos",
            ),
            models.CheckConstraint(
                condition=Q(split_ratio__isnull=True) | Q(split_ratio__gt=0),
                name="virtual_split_pos",
            ),
        ]

    def clean(self):
        super().clean()
        if self.action_type == self.Type.DIVIDEND:
            if self.dividend_per_unit is None or self.split_ratio is not None:
                raise ValidationError(
                    {"dividend_per_unit": "Renseignez uniquement le dividende par unité."}
                )
        elif self.split_ratio is None or self.dividend_per_unit is not None:
            raise ValidationError(
                {"split_ratio": "Renseignez uniquement le ratio de division."}
            )
        if (
            self.portfolio_id
            and self.instrument_id
            and self.instrument.owner_id not in {None, self.portfolio.user_id}
        ):
            raise ValidationError({"instrument": "Cet instrument est inaccessible."})

    def __str__(self):
        return f"{self.get_action_type_display()} {self.instrument} — {self.portfolio.name}"


class VirtualPortfolioSnapshot(models.Model):
    portfolio = models.ForeignKey(
        VirtualPortfolio,
        on_delete=models.CASCADE,
        related_name="performance_snapshots",
    )
    observed_at = models.DateTimeField(default=timezone.now)
    cash_value = models.DecimalField(max_digits=30, decimal_places=8)
    positions_value = models.DecimalField(max_digits=30, decimal_places=8)
    total_value = models.DecimalField(max_digits=30, decimal_places=8)
    realized_gain = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    unrealized_gain = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    dividend_income = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal("0"))
    benchmark_value = models.DecimalField(max_digits=30, decimal_places=8, null=True, blank=True)
    has_missing_prices = models.BooleanField(default=False)
    has_delayed_prices = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["observed_at", "pk"]
        indexes = [
            models.Index(
                fields=["portfolio", "observed_at"],
                name="virtual_snapshot_time_idx",
            )
        ]

    def __str__(self):
        return f"{self.portfolio.name} — {self.total_value} ({self.observed_at})"


class MaintenanceRun(models.Model):
    """Secret-free observability record for one user's scheduled maintenance."""

    class Trigger(models.TextChoices):
        MANUAL = "MANUAL", "Manuelle"
        SCHEDULED = "SCHEDULED", "Planifiée"

    class Status(models.TextChoices):
        RUNNING = "RUNNING", "En cours"
        SUCCEEDED = "SUCCEEDED", "Réussie"
        PARTIAL = "PARTIAL", "Partielle"
        FAILED = "FAILED", "Échouée"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="financial_maintenance_runs",
    )
    correlation_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    trigger = models.CharField(max_length=20, choices=Trigger, default=Trigger.SCHEDULED)
    status = models.CharField(max_length=20, choices=Status, default=Status.RUNNING)
    include_network = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    snapshot_created_count = models.PositiveIntegerField(default=0)
    snapshot_existing_count = models.PositiveIntegerField(default=0)
    virtual_portfolio_count = models.PositiveIntegerField(default=0)
    virtual_order_executed_count = models.PositiveIntegerField(default=0)
    virtual_order_rejected_count = models.PositiveIntegerField(default=0)
    market_refresh_count = models.PositiveIntegerField(default=0)
    market_failure_count = models.PositiveIntegerField(default=0)
    fx_refresh_succeeded = models.BooleanField(default=False)
    connector_run_count = models.PositiveIntegerField(default=0)
    connector_failure_count = models.PositiveIntegerField(default=0)
    public_message = models.CharField(max_length=255, blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status="RUNNING"),
                name="uniq_running_maintenance_user",
            )
        ]
        indexes = [
            models.Index(
                fields=["user", "-started_at"],
                name="maintenance_user_time_idx",
            )
        ]

    def __str__(self):
        return f"Maintenance {self.user} — {self.get_status_display()}"


class FinancialAuditEvent(models.Model):
    class Type(models.TextChoices):
        MANUAL_CREATE = "MANUAL_CREATE", "Création manuelle"
        MANUAL_UPDATE = "MANUAL_UPDATE", "Modification manuelle"
        MANUAL_ARCHIVE = "MANUAL_ARCHIVE", "Archivage manuel"
        IMPORT = "IMPORT", "Import"
        IMPORT_ROLLBACK = "IMPORT_ROLLBACK", "Annulation d'import"
        EXPORT = "EXPORT", "Export"
        MARKET_REFRESH = "MARKET_REFRESH", "Actualisation de cours"
        FX_REFRESH = "FX_REFRESH", "Actualisation du change"
        SNAPSHOT = "SNAPSHOT", "Snapshot patrimonial"
        SETTINGS_UPDATE = "SETTINGS_UPDATE", "Préférences de marché"
        CONNECTOR_CREATE = "CONNECTOR_CREATE", "Création de connexion"
        CONNECTOR_TEST = "CONNECTOR_TEST", "Test de connexion"
        CONNECTOR_SYNC = "CONNECTOR_SYNC", "Synchronisation de connexion"
        CONNECTOR_DISCONNECT = "CONNECTOR_DISCONNECT", "Déconnexion"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="financial_audit_events",
    )
    event_type = models.CharField(max_length=30, choices=Type)
    object_type = models.CharField(max_length=50, blank=True)
    object_pk = models.PositiveBigIntegerField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="audit_user_created_idx")
        ]

    def __str__(self):
        return f"{self.user} – {self.get_event_type_display()} – {self.created_at:%Y-%m-%d %H:%M}"


class ImportBatch(models.Model):
    class Format(models.TextChoices):
        JSON = "JSON", "JSON"
        XLSX = "XLSX", "Excel (.xlsx)"

    class Status(models.TextChoices):
        RUNNING = "RUNNING", "En cours"
        COMPLETED = "COMPLETED", "Terminé"
        PARTIAL = "PARTIAL", "Partiel"
        FAILED = "FAILED", "Échec"
        ROLLED_BACK = "ROLLED_BACK", "Annulé"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="financial_import_batches",
    )
    file_name = models.CharField(max_length=255)
    file_format = models.CharField(max_length=10, choices=Format)
    schema_version = models.CharField(max_length=20)
    file_sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=Status, default=Status.RUNNING)
    total_rows = models.PositiveIntegerField(default=0)
    created_rows = models.PositiveIntegerField(default=0)
    updated_rows = models.PositiveIntegerField(default=0)
    skipped_rows = models.PositiveIntegerField(default=0)
    invalid_rows = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    rolled_back_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "file_sha256"],
                condition=~Q(status="ROLLED_BACK"),
                name="uniq_import_batch_user_sha256",
            )
        ]

    def __str__(self):
        return f"{self.file_name} – {self.get_status_display()}"


class ImportIssue(models.Model):
    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="issues")
    sheet = models.CharField(max_length=50)
    row_number = models.PositiveIntegerField()
    column = models.CharField(max_length=100, blank=True)
    code = models.CharField(max_length=50)
    message = models.TextField()
    value_preview = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["sheet", "row_number", "column", "pk"]

    def __str__(self):
        return f"{self.sheet}:{self.row_number}:{self.column} – {self.message}"


class ImportChange(models.Model):
    class Action(models.TextChoices):
        CREATED = "CREATED", "Création"
        UPDATED = "UPDATED", "Mise à jour"

    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="changes")
    sheet = models.CharField(max_length=50)
    row_number = models.PositiveIntegerField()
    model_name = models.CharField(max_length=50)
    object_pk = models.PositiveBigIntegerField()
    action = models.CharField(max_length=10, choices=Action)
    before_data = models.JSONField(default=dict, blank=True)
    after_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "model_name", "object_pk"],
                name="uniq_import_change_object",
            )
        ]

    def __str__(self):
        return f"{self.batch_id}:{self.model_name}:{self.object_pk} ({self.action})"


ACCOUNT_CATEGORIES = Account.Type.choices
TRANSACTION_TYPES = Transaction.Type.choices
FREQUENCY_CHOICES = Frequency.choices
