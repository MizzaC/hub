import FundBoard.validators
import django.db.models.deletion
import django.utils.timezone
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Institution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('slug', models.SlugField(max_length=255, unique=True)),
                ('institution_type', models.CharField(choices=[('BANK', 'Banque'), ('BROKER', 'Courtier'), ('CRYPTO', 'Plateforme crypto'), ('CUSTODIAN', 'Dépositaire'), ('OTHER', 'Autre')], default='BANK', max_length=20)),
                ('country_code', models.CharField(blank=True, max_length=2, validators=[FundBoard.validators.validate_country_code])),
                ('logo_url', models.URLField(blank=True)),
                ('capabilities', models.JSONField(blank=True, default=list)),
                ('status', models.CharField(choices=[('ACTIVE', 'Active'), ('UNAVAILABLE', 'Indisponible'), ('RETIRED', 'Retirée')], default='ACTIVE', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Connection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(max_length=50)),
                ('external_id', models.CharField(blank=True, max_length=255)),
                ('display_name', models.CharField(blank=True, max_length=255)),
                ('status', models.CharField(choices=[('PENDING', 'À configurer'), ('ACTIVE', 'Active'), ('STALE', 'À resynchroniser'), ('ERROR', 'En erreur'), ('REVOKED', 'Révoquée')], default='PENDING', max_length=20)),
                ('last_synced_at', models.DateTimeField(blank=True, null=True)),
                ('next_sync_at', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.TextField(blank=True)),
                ('sync_cursor', models.JSONField(blank=True, default=dict)),
                ('capabilities', models.JSONField(blank=True, default=list)),
                ('secret_reference', models.CharField(blank=True, help_text='Référence opaque vers un gestionnaire de secrets, jamais le secret lui-même.', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='financial_connections', to=settings.AUTH_USER_MODEL)),
                ('institution', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='connections', to='FundBoard.institution')),
            ],
            options={
                'ordering': ['provider', 'display_name', 'pk'],
            },
        ),
        migrations.CreateModel(
            name='Account',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('category', models.CharField(choices=[('CURRENT', 'Compte courant'), ('SAVINGS', 'Livret / Épargne'), ('CTO', 'Compte Titres Ordinaire'), ('PEA', 'Plan d’Épargne en Actions'), ('LIFE_INS', 'Assurance-vie'), ('RETIREMENT', 'Épargne retraite'), ('CRYPTO', 'Portefeuille Crypto'), ('CASH', 'Espèces'), ('OTHER', 'Autre')], max_length=20)),
                ('subtype', models.CharField(blank=True, max_length=50)),
                ('currency', models.CharField(default='EUR', max_length=3, validators=[FundBoard.validators.validate_currency_code])),
                ('balance', models.DecimalField(decimal_places=12, default=Decimal('0'), max_digits=30)),
                ('ownership_share', models.DecimalField(decimal_places=2, default=Decimal('100'), help_text='Quote-part détenue, en pourcentage.', max_digits=5)),
                ('iban_masked', models.CharField(blank=True, max_length=34)),
                ('external_id', models.CharField(blank=True, max_length=255)),
                ('status', models.CharField(choices=[('ACTIVE', 'Actif'), ('CLOSED', 'Clôturé'), ('ARCHIVED', 'Archivé')], default='ACTIVE', max_length=20)),
                ('source', models.CharField(choices=[('MANUAL', 'Manuel'), ('IMPORT', 'Import'), ('PROVIDER', 'Synchronisé')], default='MANUAL', max_length=20)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='financial_accounts', to=settings.AUTH_USER_MODEL)),
                ('connection', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='accounts', to='FundBoard.connection')),
                ('institution', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='accounts', to='FundBoard.institution')),
            ],
            options={
                'ordering': ['category', 'name'],
            },
        ),
        migrations.CreateModel(
            name='ExchangeRate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('base_currency', models.CharField(max_length=3, validators=[FundBoard.validators.validate_currency_code])),
                ('quote_currency', models.CharField(max_length=3, validators=[FundBoard.validators.validate_currency_code])),
                ('rate', models.DecimalField(decimal_places=12, max_digits=30)),
                ('rate_date', models.DateField()),
                ('source', models.CharField(max_length=50)),
                ('collected_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('quality', models.CharField(choices=[('FRESH', 'À jour'), ('STALE', 'Périmé'), ('ERROR', 'Erreur')], default='FRESH', max_length=10)),
            ],
            options={
                'ordering': ['-rate_date', 'base_currency', 'quote_currency'],
                'constraints': [models.UniqueConstraint(fields=('base_currency', 'quote_currency', 'rate_date', 'source'), name='uniq_fx_pair_date_source'), models.CheckConstraint(condition=models.Q(('rate__gt', 0)), name='exchange_rate_positive'), models.CheckConstraint(condition=models.Q(('base_currency', models.F('quote_currency')), _negated=True), name='exchange_rate_distinct_pair')],
            },
        ),
        migrations.CreateModel(
            name='Income',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('amount', models.DecimalField(decimal_places=8, max_digits=30)),
                ('currency', models.CharField(default='EUR', max_length=3, validators=[FundBoard.validators.validate_currency_code])),
                ('freq', models.CharField(choices=[('DAILY', 'Quotidien'), ('WEEKLY', 'Hebdomadaire'), ('MONTHLY', 'Mensuel'), ('YEARLY', 'Annuel'), ('PERSONALIZED', 'Personnalisé')], max_length=20)),
                ('freq_custom', models.PositiveIntegerField(blank=True, help_text='Nombre de jours entre chaque échéance si la fréquence est personnalisée.', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('next_payday', models.DateField()),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['next_payday', 'name'],
            },
        ),
        migrations.CreateModel(
            name='Instrument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('instrument_type', models.CharField(choices=[('STOCK', 'Action'), ('ETF', 'ETF'), ('FUND', 'Fonds'), ('BOND', 'Obligation'), ('CRYPTO', 'Cryptomonnaie'), ('CURRENCY', 'Devise'), ('COMMODITY', 'Matière première'), ('PRIVATE_EQ', 'Private equity'), ('OTHER', 'Autre')], max_length=20)),
                ('ticker', models.CharField(blank=True, max_length=30)),
                ('isin', models.CharField(blank=True, max_length=12)),
                ('market_mic', models.CharField(blank=True, max_length=4)),
                ('currency', models.CharField(max_length=3, validators=[FundBoard.validators.validate_currency_code])),
                ('country_code', models.CharField(blank=True, max_length=2, validators=[FundBoard.validators.validate_country_code])),
                ('sector', models.CharField(blank=True, max_length=100)),
                ('provider_identifiers', models.JSONField(blank=True, default=dict)),
                ('blockchain', models.CharField(blank=True, max_length=50)),
                ('contract_address', models.CharField(blank=True, max_length=255)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name', 'ticker'],
                'constraints': [models.UniqueConstraint(condition=models.Q(('isin', ''), _negated=True), fields=('isin',), name='uniq_instrument_isin'), models.UniqueConstraint(condition=models.Q(models.Q(('blockchain', ''), _negated=True), models.Q(('contract_address', ''), _negated=True)), fields=('blockchain', 'contract_address'), name='uniq_instrument_chain_contract')],
            },
        ),
        migrations.CreateModel(
            name='ExternalIdentifier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(max_length=50)),
                ('external_id', models.CharField(max_length=255)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='external_identifiers', to='FundBoard.account')),
                ('connection', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='external_identifiers', to='FundBoard.connection')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='financial_external_identifiers', to=settings.AUTH_USER_MODEL)),
                ('instrument', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='external_identifiers', to='FundBoard.instrument')),
            ],
            options={
                'ordering': ['provider', 'external_id'],
            },
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('read', models.BooleanField(default=False)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created'],
            },
        ),
        migrations.CreateModel(
            name='Position',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=18, max_digits=36)),
                ('average_unit_cost', models.DecimalField(blank=True, decimal_places=12, max_digits=30, null=True)),
                ('cost_basis', models.DecimalField(blank=True, decimal_places=8, max_digits=30, null=True)),
                ('current_unit_price', models.DecimalField(blank=True, decimal_places=12, max_digits=30, null=True)),
                ('current_value', models.DecimalField(blank=True, decimal_places=8, max_digits=30, null=True)),
                ('value_currency', models.CharField(max_length=3, validators=[FundBoard.validators.validate_currency_code])),
                ('converted_value', models.DecimalField(blank=True, decimal_places=8, max_digits=30, null=True)),
                ('converted_currency', models.CharField(blank=True, max_length=3, validators=[FundBoard.validators.validate_currency_code])),
                ('exchange_rate', models.DecimalField(blank=True, decimal_places=12, max_digits=30, null=True)),
                ('exchange_rate_date', models.DateField(blank=True, null=True)),
                ('valued_at', models.DateTimeField(blank=True, null=True)),
                ('source', models.CharField(choices=[('MANUAL', 'Manuelle'), ('IMPORT', 'Import'), ('PROVIDER', 'Fournisseur')], default='MANUAL', max_length=20)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='positions', to='FundBoard.account')),
                ('instrument', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='positions', to='FundBoard.instrument')),
            ],
            options={
                'ordering': ['account', 'instrument'],
            },
        ),
        migrations.CreateModel(
            name='Price',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('observed_at', models.DateTimeField()),
                ('open_price', models.DecimalField(blank=True, decimal_places=12, max_digits=30, null=True)),
                ('high_price', models.DecimalField(blank=True, decimal_places=12, max_digits=30, null=True)),
                ('low_price', models.DecimalField(blank=True, decimal_places=12, max_digits=30, null=True)),
                ('close_price', models.DecimalField(decimal_places=12, max_digits=30)),
                ('volume', models.DecimalField(blank=True, decimal_places=12, max_digits=36, null=True)),
                ('currency', models.CharField(max_length=3, validators=[FundBoard.validators.validate_currency_code])),
                ('source', models.CharField(max_length=50)),
                ('collected_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('is_delayed', models.BooleanField(default=False)),
                ('quality', models.CharField(choices=[('FRESH', 'À jour'), ('STALE', 'Périmé'), ('ERROR', 'Erreur')], default='FRESH', max_length=10)),
                ('instrument', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prices', to='FundBoard.instrument')),
            ],
            options={
                'ordering': ['-observed_at'],
            },
        ),
        migrations.CreateModel(
            name='Snapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scope', models.CharField(choices=[('NET_WORTH', 'Patrimoine net'), ('ACCOUNT', 'Compte'), ('POSITION', 'Position')], max_length=20)),
                ('observed_at', models.DateTimeField()),
                ('original_value', models.DecimalField(decimal_places=8, max_digits=30)),
                ('original_currency', models.CharField(max_length=3, validators=[FundBoard.validators.validate_currency_code])),
                ('converted_value', models.DecimalField(decimal_places=8, max_digits=30)),
                ('converted_currency', models.CharField(max_length=3, validators=[FundBoard.validators.validate_currency_code])),
                ('exchange_rate', models.DecimalField(decimal_places=12, max_digits=30)),
                ('exchange_rate_date', models.DateField()),
                ('source', models.CharField(choices=[('CALCULATED', 'Calculé'), ('MANUAL', 'Manuel'), ('PROVIDER', 'Fournisseur')], default='CALCULATED', max_length=20)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='snapshots', to='FundBoard.account')),
                ('position', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='snapshots', to='FundBoard.position')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='financial_snapshots', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-observed_at'],
            },
        ),
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('amount', models.DecimalField(decimal_places=8, max_digits=30)),
                ('currency', models.CharField(default='EUR', max_length=3, validators=[FundBoard.validators.validate_currency_code])),
                ('freq', models.CharField(choices=[('DAILY', 'Quotidien'), ('WEEKLY', 'Hebdomadaire'), ('MONTHLY', 'Mensuel'), ('YEARLY', 'Annuel'), ('PERSONALIZED', 'Personnalisé')], max_length=20)),
                ('freq_custom', models.PositiveIntegerField(blank=True, help_text='Nombre de jours entre chaque échéance si la fréquence est personnalisée.', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('next_due', models.DateField()),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['next_due', 'name'],
            },
        ),
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('external_id', models.CharField(blank=True, max_length=255)),
                ('provider', models.CharField(blank=True, max_length=50)),
                ('transaction_type', models.CharField(choices=[('DEPOSIT', 'Dépôt'), ('WITHDRAWAL', 'Retrait'), ('BUY', 'Achat'), ('SELL', 'Vente'), ('TRANSFER', 'Transfert'), ('DIVIDEND', 'Dividende'), ('INTEREST', 'Intérêt'), ('FEE', 'Frais'), ('TAX', 'Taxe'), ('REFUND', 'Remboursement'), ('OTHER', 'Autre')], max_length=20)),
                ('subtype', models.CharField(blank=True, max_length=50)),
                ('quantity', models.DecimalField(blank=True, decimal_places=18, max_digits=36, null=True)),
                ('unit_price', models.DecimalField(blank=True, decimal_places=12, max_digits=30, null=True)),
                ('gross_amount', models.DecimalField(blank=True, decimal_places=8, max_digits=30, null=True)),
                ('fees', models.DecimalField(decimal_places=8, default=Decimal('0'), max_digits=30)),
                ('taxes', models.DecimalField(decimal_places=8, default=Decimal('0'), max_digits=30)),
                ('net_amount', models.DecimalField(decimal_places=8, max_digits=30)),
                ('currency', models.CharField(max_length=3, validators=[FundBoard.validators.validate_currency_code])),
                ('executed_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('value_date', models.DateField(blank=True, null=True)),
                ('label', models.CharField(blank=True, max_length=500)),
                ('status', models.CharField(choices=[('PENDING', 'En attente'), ('BOOKED', 'Comptabilisée'), ('CANCELLED', 'Annulée')], default='BOOKED', max_length=20)),
                ('source', models.CharField(choices=[('MANUAL', 'Manuelle'), ('IMPORT', 'Import'), ('PROVIDER', 'Fournisseur')], default='MANUAL', max_length=20)),
                ('idempotency_key', models.CharField(blank=True, max_length=255)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='FundBoard.account')),
                ('instrument', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transactions', to='FundBoard.instrument')),
                ('linked_transfer', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reverse_linked_transfer', to='FundBoard.transaction')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='financial_transactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-executed_at', '-pk'],
            },
        ),
        migrations.CreateModel(
            name='Watchlist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='financial_watchlists', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='WatchInstrument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('instrument', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='FundBoard.instrument')),
                ('watchlist', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='FundBoard.watchlist')),
            ],
        ),
        migrations.AddIndex(
            model_name='connection',
            index=models.Index(fields=['user', 'status'], name='conn_user_status_idx'),
        ),
        migrations.AddConstraint(
            model_name='connection',
            constraint=models.UniqueConstraint(condition=models.Q(('external_id', ''), _negated=True), fields=('user', 'provider', 'external_id'), name='uniq_connection_user_provider_external'),
        ),
        migrations.AddIndex(
            model_name='account',
            index=models.Index(fields=['user', 'status'], name='account_user_status_idx'),
        ),
        migrations.AddConstraint(
            model_name='account',
            constraint=models.CheckConstraint(condition=models.Q(('ownership_share__gt', 0), ('ownership_share__lte', 100)), name='account_valid_ownership_share'),
        ),
        migrations.AddConstraint(
            model_name='account',
            constraint=models.UniqueConstraint(condition=models.Q(('connection__isnull', False), models.Q(('external_id', ''), _negated=True)), fields=('user', 'connection', 'external_id'), name='uniq_account_user_connection_external'),
        ),
        migrations.AddConstraint(
            model_name='externalidentifier',
            constraint=models.UniqueConstraint(fields=('user', 'provider', 'external_id'), name='uniq_external_identifier_user_provider'),
        ),
        migrations.AddConstraint(
            model_name='externalidentifier',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('account__isnull', False), ('connection__isnull', True), ('instrument__isnull', True)), models.Q(('account__isnull', True), ('connection__isnull', True), ('instrument__isnull', False)), models.Q(('account__isnull', True), ('connection__isnull', False), ('instrument__isnull', True)), _connector='OR'), name='external_identifier_exactly_one_target'),
        ),
        migrations.AddConstraint(
            model_name='position',
            constraint=models.UniqueConstraint(fields=('account', 'instrument'), name='uniq_position_account_instrument'),
        ),
        migrations.AddConstraint(
            model_name='position',
            constraint=models.CheckConstraint(condition=models.Q(('quantity', 0), _negated=True), name='position_quantity_non_zero'),
        ),
        migrations.AddIndex(
            model_name='price',
            index=models.Index(fields=['instrument', '-observed_at'], name='price_instrument_time_idx'),
        ),
        migrations.AddConstraint(
            model_name='price',
            constraint=models.UniqueConstraint(fields=('instrument', 'observed_at', 'source'), name='uniq_price_instrument_observed_source'),
        ),
        migrations.AddIndex(
            model_name='snapshot',
            index=models.Index(fields=['user', 'scope', '-observed_at'], name='snapshot_user_scope_idx'),
        ),
        migrations.AddConstraint(
            model_name='snapshot',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('account__isnull', True), ('position__isnull', True), ('scope', 'NET_WORTH')), models.Q(('account__isnull', False), ('position__isnull', True), ('scope', 'ACCOUNT')), models.Q(('account__isnull', True), ('position__isnull', False), ('scope', 'POSITION')), _connector='OR'), name='snapshot_scope_matches_target'),
        ),
        migrations.AddConstraint(
            model_name='snapshot',
            constraint=models.CheckConstraint(condition=models.Q(('exchange_rate__gt', 0)), name='snapshot_rate_positive'),
        ),
        migrations.AddConstraint(
            model_name='snapshot',
            constraint=models.UniqueConstraint(condition=models.Q(('scope', 'NET_WORTH')), fields=('user', 'observed_at', 'source'), name='uniq_networth_snapshot'),
        ),
        migrations.AddConstraint(
            model_name='snapshot',
            constraint=models.UniqueConstraint(condition=models.Q(('scope', 'ACCOUNT')), fields=('account', 'observed_at', 'source'), name='uniq_account_snapshot'),
        ),
        migrations.AddConstraint(
            model_name='snapshot',
            constraint=models.UniqueConstraint(condition=models.Q(('scope', 'POSITION')), fields=('position', 'observed_at', 'source'), name='uniq_position_snapshot'),
        ),
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(fields=['user', '-executed_at'], name='trx_user_executed_idx'),
        ),
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(fields=['account', '-executed_at'], name='trx_account_executed_idx'),
        ),
        migrations.AddConstraint(
            model_name='transaction',
            constraint=models.UniqueConstraint(condition=models.Q(models.Q(('provider', ''), _negated=True), models.Q(('external_id', ''), _negated=True)), fields=('user', 'provider', 'external_id'), name='uniq_transaction_user_provider_external'),
        ),
        migrations.AddConstraint(
            model_name='transaction',
            constraint=models.UniqueConstraint(condition=models.Q(('idempotency_key', ''), _negated=True), fields=('user', 'idempotency_key'), name='uniq_transaction_user_idempotency'),
        ),
        migrations.AddConstraint(
            model_name='transaction',
            constraint=models.CheckConstraint(condition=models.Q(('net_amount', 0), _negated=True), name='transaction_net_non_zero'),
        ),
        migrations.AddConstraint(
            model_name='transaction',
            constraint=models.CheckConstraint(condition=models.Q(('fees__gte', 0)), name='transaction_fees_positive'),
        ),
        migrations.AddConstraint(
            model_name='transaction',
            constraint=models.CheckConstraint(condition=models.Q(('taxes__gte', 0)), name='transaction_taxes_positive'),
        ),
        migrations.AddConstraint(
            model_name='watchlist',
            constraint=models.UniqueConstraint(fields=('user', 'name'), name='uniq_watchlist_user_name'),
        ),
        migrations.AddConstraint(
            model_name='watchinstrument',
            constraint=models.UniqueConstraint(fields=('watchlist', 'instrument'), name='uniq_watchlist_instrument'),
        ),
    ]
