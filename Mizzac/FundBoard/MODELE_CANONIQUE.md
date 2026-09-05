# Modèle financier canonique FundBoard

## Portée du modèle

FundBoard normalise désormais les comptes, instruments, positions,
transactions, cours, taux et snapshots sans dépendre du schéma d'une banque.
Cette migration initiale remplace l'ancien prototype, conformément à la
décision de repartir d'une base vide.

La phase 4 ajoute les références manuelles privées, l'archivage, les biens
immobiliers, les prêts, les valorisations immobilières et les participations de
private equity. La phase 7 complète ces actifs avec les historiques de capital
restant dû et de valorisation private equity, ainsi que les charges, la vacance
et les rendements immobiliers. La phase 8 ajoute des scénarios de prêt et
d'intérêts composés privés, volontairement sans relation avec les comptes,
transactions, positions ou prêts réels.

## Relations et responsabilités

```text
Institution ──< Connection ──< Account ──< Position >── Instrument ──< Price
                        │          │                         │
                        ├──< ConnectorSyncRun                │
                        │          └──< Transaction          └──< ExternalIdentifier
                        │                    │
                        └──< ExternalIdentifier              └── linked_transfer

User ──< Account / Connection / Transaction / Snapshot / ExternalIdentifier
ExchangeRate                         Account ou Position ──< Snapshot

User ──< Loan ──< LoanBalanceSnapshot
             └──< RealEstate ──< RealEstateValuation
User ──< PrivateEquityHolding ──< PrivateEquityValuation
User ──< LoanSimulationScenario / CompoundInterestScenario
User ──< VirtualPortfolio ──< VirtualWatchlistEntry / VirtualPosition
                         ├──< VirtualOrder ── VirtualCashEvent
                         ├──< VirtualCorporateAction
                         └──< VirtualPortfolioSnapshot
User ──< ImportBatch ──< ImportIssue / ImportChange
User ──< FinancialAuditEvent
User ──< MaintenanceRun
```

- Une `Institution` décrit une banque, un courtier ou un dépositaire global.
- Une `Connection` appartient à un utilisateur et décrit l'état d'un
  fournisseur. `secret_reference` est uniquement une référence opaque ; aucun
  token, mot de passe, cookie, PIN ou code 2FA n'est stocké dans ces tables. Sa
  `configuration` est limitée aux valeurs non secrètes.
- Un `ConnectorSyncRun` trace un lancement manuel, planifié ou par import avec
  curseurs et compteurs expurgés. Une contrainte interdit deux runs actifs pour
  la même connexion.
- Un `Account` est le contenant juridique ou technique : compte courant, PEA,
  CTO, assurance-vie, portefeuille crypto, etc.
- Un `Instrument` est ce qui est détenu : action, ETF, fonds, obligation,
  cryptoactif, devise ou autre titre. Un PEA n'est donc jamais un instrument.
- Une `Position` relie un compte à un instrument avec une quantité précise, un
  coût et une valorisation datée.
- Une `Transaction` conserve les montants brut/net, frais, taxes, quantité,
  prix, dates, source et identifiants de déduplication.
- `Price` et `ExchangeRate` sont datés, sourcés et qualifiés. Aucun service de
  calcul ne déclenche d'appel réseau.
- Un `Snapshot` fige une valeur de compte, de position ou du patrimoine net,
  avec devise d'origine, valeur convertie, taux et date du taux.
- Un `Loan` décrit un passif et peut être lié à un compte puis à un bien.
- Un `LoanBalanceSnapshot` date et source chaque observation du capital restant
  dû sans recalculer un échéancier théorique.
- Un `RealEstate` conserve acquisition, quote-part, valeur manuelle datée,
  revenus, charges, assurance, vacance et prêt lié. La valeur nette n'est
  calculée directement que lorsque le bien et le prêt utilisent la même devise.
- Un `PrivateEquityHolding` distingue engagement, capital appelé,
  distributions et valeur liquidative datée.
- Un `PrivateEquityValuation` historise ensemble valeur liquidative, capital
  appelé et distributions pour rendre DPI, RVPI et TVPI reproductibles.
- Un `LoanSimulationScenario` et un `CompoundInterestScenario` ne stockent que
  des hypothèses privées. Les résultats sont recalculés par des services purs
  et ne modifient jamais le patrimoine réel.
- Un `VirtualPortfolio` porte un cash, une watchlist, des positions, des ordres,
  des événements et des snapshots exclusivement fictifs. Ces tables n'ont
  aucune relation avec `Account`, `Position`, `Transaction` ou `Connection`.
  Les ordres figent le cours local horodaté utilisé lors de leur exécution.
- Un `ImportBatch` porte l'empreinte, les compteurs, erreurs par ligne et
  changements nécessaires à une annulation prudente.
- Un `FinancialAuditEvent` trace les créations, modifications, archivages,
  imports, annulations et exports avec des métadonnées strictement limitées.
- Un `MaintenanceRun` résume snapshots, ordres virtuels, cours, change et
  connecteurs d'un passage planifié. Il ne contient que compteurs, état public
  et identifiant de corrélation. Une contrainte interdit deux passages actifs
  pour le même utilisateur.

## Propriété et confidentialité

Les objets financiers privés portent directement un utilisateur ou sont
accessibles via `Account.user`. Les vues filtrent toujours depuis
`request.user`. Les validations interdisent de rattacher un compte, une
connexion, un snapshot ou un identifiant externe au mauvais propriétaire.

`metadata`, `provider_identifiers`, `capabilities` et `sync_cursor` utilisent
le `JSONField` natif de Django. Ils ne doivent contenir ni secret ni charge
utile fournisseur sensible. Les données privées nécessaires à un connecteur
restent dans un gestionnaire de secrets externe.

La quote-part `Account.ownership_share` permet une première représentation de
la copropriété entre 0 (exclu) et 100 %. Un modèle multi-propriétaire détaillé
pourra être ajouté lorsque des cas réels le justifieront.

## Précision et devises

- quantités : 36 chiffres, dont 18 décimales ;
- prix et taux : 30 chiffres, dont 12 décimales ;
- valeurs monétaires : 30 chiffres, dont 8 décimales ;
- calculs : `Decimal`, arrondi commercial `ROUND_HALF_UP` à huit décimales ;
- codes devise : trois lettres ASCII normalisées en majuscules ;
- codes pays : deux lettres ASCII normalisées en majuscules.

PostgreSQL est requis en production pour garantir la précision `NUMERIC`
déclarée. SQLite reste pratique en développement mais son affinité numérique
peut convertir les nombres de très grande précision via un flottant et perdre
des chiffres significatifs à la lecture. Les services purs et leurs tests ne
subissent pas cette limite SQLite.

Une valeur convertie n'est valide qu'avec les quatre informations suivantes :
montant converti, devise cible, taux appliqué et date du taux. Une conversion
dans la même devise utilise exactement le taux 1.

## Convention de signe des transactions

`net_amount` représente l'effet signé sur la trésorerie du compte :

| Type | Signe attendu | Traitement de performance |
|---|---:|---|
| dépôt | positif | flux externe entrant |
| retrait | négatif | flux externe sortant |
| achat | négatif | changement de composition, pas un flux du portefeuille |
| vente | positif | changement de composition, pas un flux du portefeuille |
| dividende / intérêt | positif | revenu de performance |
| frais / taxe | négatif | composante distincte de performance |
| remboursement | positif | entrée à classifier selon sa source |
| transfert | positif ou négatif | interne uniquement si les deux jambes sont reliées |

`gross_amount` est le montant avant frais et taxes. `fees` et `taxes` sont
stockés comme valeurs positives détaillées ; leur effet est déjà inclus dans
`net_amount`. Les transactions annulées sont exclues des calculs.

Deux jambes `TRANSFER` reliées par `linked_transfer` sont un transfert interne
et ne sont comptées ni comme performance ni comme épargne nouvelle. Un
transfert non apparié reste, par prudence, un flux externe jusqu'à
réconciliation.

## Idempotence

- une opération fournisseur est unique par
  `(user, provider, external_id)` ;
- toute transaction importée ou synchronisée exige `idempotency_key`, unique
  par utilisateur ;
- un identifiant externe générique est unique par
  `(user, provider, external_id)` et cible exactement un compte, un instrument
  ou une connexion ;
- les positions sont uniques par `(account, instrument)` ;
- les cours, taux et snapshots ont des contraintes temporelles explicites.

La phase 4 réutilise ces contraintes pour le dry-run, la déduplication et le
succès partiel transactionnel par ligne. Une référence personnelle est unique
par utilisateur pour les comptes, instruments privés, biens et prêts. Un même
fichier ne peut pas être rejoué tant que son lot précédent n'a pas été annulé.

## Services de calcul

- `services/valuation.py` : valorisation d'une position, conversion explicite,
  quote-part, actifs, passifs, trésorerie et patrimoine net ;
- `services/performance.py` : rendement Modified Dietz et séparation marché,
  flux externes, revenus, frais, taxes et change ;
- `services/transactions.py` : insertion idempotente, appariement atomique des
  transferts internes et classement pour la performance ;
- `services/recurring.py` : annualisation des abonnements et revenus récurrents.
- `services/fx.py` : taux EUR/USD datés en cache et conversions sans réseau ;
- `services/display_currency.py` : préparation sûre des vues EUR/USD ;
- `services/pricing.py` : orchestration explicite des cours, historique,
  fraîcheur et mise à jour idempotente des positions ;
- `services/net_worth.py` : consolidation sourcée du patrimoine, avec refus de
  mélanger les devises dépourvues de taux ;
- `services/snapshots.py` : gel quotidien idempotent d'une valorisation complète ;
- `services/dashboard.py` : séries locales et performance portefeuille/benchmark.
- `services/connectors.py` : cycle de connexion, persistance idempotente,
  rejet isolé des données invalides, curseurs et audit expurgé.
- `services/assets.py` : métriques immobilières, progression des prêts et
  multiples private equity, en `Decimal` et par devise ;
- `services/asset_history.py` : écriture atomique et idempotente des historiques
  spécialisés, sans écraser l'état courant avec une observation plus ancienne.
- `services/loan_calculator.py` : mensualité ou durée, différés, assurance,
  remboursements anticipés et tableau d'amortissement à taux fixe ;
- `services/compound_interest.py` : projection mensuelle des versements,
  rendement nominal, frais, inflation et fiscalité finale simplifiée.
- `services/paper_trading.py` : ordres virtuels depuis les seuls cours déjà
  stockés, registre de cash et positions, événements, performance, clonage et
  remise à zéro, sans connecteur ni ordre réel.
- `services/maintenance.py` : orchestration idempotente des tâches locales et
  opt-in des appels réseau, avec verrou, reprise et compteurs expurgés ;
- `services/health.py` : contrôle en lecture seule de l'état opérationnel ;
- `services/backups.py` : sauvegarde, manifeste, vérification et restauration
  conservatrice vers une nouvelle base SQLite.

Ces modules sont déterministes, indépendants de toute API et refusent les
`float` binaires dans les chemins financiers. Les appels HTTP résident dans
`integrations/market_data/` et `integrations/connectors/` ; ils ne sont invoqués
que par des actions de collecte ou de consentement explicites. Les imports
Ledger et l'import de secours Trade Republic n'accèdent pas au réseau. Le compte
espèces Trade Republic peut emprunter le consentement PSD2 Enable Banking ; les
titres ne sont pas couverts par ce canal.
