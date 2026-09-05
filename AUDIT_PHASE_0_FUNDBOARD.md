# Audit Phase 0 — FundBoard / Mizzac

Date de l'audit : 3 septembre 2026  
Branche auditée : `mizeos-FundBoard-test`  
Commit audité : `d6d89f1` (`Added Subscription page`)  
Base distante correspondante : `origin/cazeva-devfundboard`  

## 1. Résumé exécutif

La branche demandée est bien la branche active et le worktree était propre au début de l'audit. Les applications `DashBoard`, `FundBoard`, `GameBoard`, `DrunkBoard` et `ToolBoard` sont présentes. Les cinq migrations FundBoard annoncées existent et l'état des modèles ne demande pas de nouvelle migration.

Le projet compile et `manage.py check` passe une fois les dépendances installées dans un environnement isolé. En revanche, la suite contient exactement **0 test** et plusieurs erreurs d'exécution ne sont donc pas détectées. Les plus importantes sont :

1. la migration FundBoard `0005` est destructive pour une base `0004` peuplée, inverse les valeurs OHLC haut/bas et échoue lorsque des transactions historiques existent ;
2. les pages de connexion et d'inscription ne se rendent pas, et les pages FundBoard utilisent une route de connexion inexistante ;
3. plusieurs vues modales sensibles ne requièrent pas d'authentification ;
4. le portefeuille n'a plus de template, la page des abonnements casse avec une fréquence personnalisée et la page des revenus utilise encore les anciens noms de champs ;
5. Django 4.2.3 est obsolète, hors support et n'est pas officiellement compatible avec Python 3.12 (la compatibilité Python 3.12 n'a été ajoutée qu'en Django 4.2.8) ;
6. aucune base SQLite utilisateur n'est fournie dans ce clone. La conservation des données réelles ne peut pas être certifiée avant de connaître la base déployée, son état de migration et les sauvegardes disponibles.

Conformément au plan maître, aucune phase de refonte n'a été commencée. Le seul fichier ajouté est ce rapport.

## 2. Périmètre et inventaire réel

### 2.1 Dépôt

- 100 fichiers suivis par Git au moment de l'audit.
- Aucun `AGENTS.md`, aucune configuration CI, aucun `pyproject.toml` et aucune configuration de linter ou de couverture.
- `README.md` documente une installation directe avec `pip` et la commande `python`, absente de l'environnement audité ; `python3` 3.12.3 est disponible.
- Aucun `db.sqlite3` n'était présent avant les contrôles.
- Node.js 18.19.1 et npm 9.2.0 sont disponibles, donc l'intégration reproductible de Tabler par npm et lockfile est possible en Phase 2.

### 2.2 Applications à préserver

| Application | Capacités actuellement visibles | État notable |
|---|---|---|
| `DashBoard` | accueil authentifié, login, logout, inscription, navbar/footer communs | login et inscription cassés par `{% extends 'base.html' %}` ; seul `common/base.html` existe |
| `FundBoard` | synthèse, comptes, transactions, abonnements, revenus, watchlists, historiques, notifications, dividendes | fonctions partielles et plusieurs erreurs détaillées plus bas |
| `GameBoard` | catalogue de jeux, détail, sauvegardes de parties, import/export SkyJo | page principale rendue ; plusieurs templates de jeux référencés sont absents |
| `DrunkBoard` | page d'accueil authentifiée | modèle vide, aucune migration métier nécessaire |
| `ToolBoard` | catalogue et outils IP, devises, TVA, mots de passe, Base64 | appel réseau de change directement dans la vue, sans timeout ; fonctionnalités à conserver pendant la migration UI |

### 2.3 Routes actuelles

- Racine : redirection permanente vers `/dashboard/`.
- Dashboard : accueil, connexion, déconnexion, inscription.
- FundBoard : accueil, portefeuille, transactions, abonnements, revenus, comptes et sept routes de modales compte/abonnement.
- GameBoard : catalogue, détail d'un jeu, affichage d'une sauvegarde.
- ToolBoard : catalogue, détail et cinq outils dédiés.
- DrunkBoard : accueil.

Les noms de routes existants doivent rester stables pendant les Phases 1 et 2, sauf remplacement coordonné avec leurs appelants et tests.

## 3. Fonctionnalités et données FundBoard à préserver

### 3.1 Fonctionnalités utiles

- séparation des comptes courants/épargne et des comptes d'investissement par catégorie ;
- solde et devise de compte, ainsi que les indicateurs historiques `api_service` et `api_connected` ;
- synthèse du nombre de comptes, transactions et abonnements, solde total et dernières transactions ;
- historique de transactions filtrable côté navigateur ;
- CRUD modal des comptes et abonnements ;
- validation des fréquences personnalisées des abonnements et revenus ;
- actifs, historique OHLCV, watchlists et actifs surveillés ;
- historique des soldes, notifications et dividendes ;
- navigation secondaire FundBoard et mécanisme de chargement de modales dynamiques.

Certaines capacités sont cassées ou incomplètes, mais leur intention fonctionnelle doit être conservée par les nouvelles implémentations.

### 3.2 Schéma actuel

| Modèle | Propriétaire actuel | Limites principales |
|---|---|---|
| `Account` | `user` direct | pas d'institution/connexion, type limité, pas d'identifiant externe, IBAN, statut ni horodatage ; précision à 2 décimales |
| `Asset` | global | ticker mondialement unique, pas d'ISIN/MIC/devise/pays/chaîne/identifiants fournisseur |
| `PriceHistory` | via `Asset` global | date seulement, 2 décimales, pas de devise/source/fraîcheur/horodatage de collecte |
| `Transaction` | `user` direct et `account` | les deux propriétaires peuvent diverger ; pas d'identifiant externe, clé d'idempotence, devise, frais, taxes, brut/net, statut, source ou date de valeur |
| `Watchlist` | `user` direct | pas de contrainte d'unicité par utilisateur |
| `WatchAsset` | via `Watchlist` | doublons possibles |
| `Subscription` | `user` direct | pas de devise, compte, statut ou bornes de récurrence |
| `Income` | `user` direct | interface de lecture obsolète, aucun CRUD actif |
| `BalanceHistory` | via `Account` | date seulement, aucune unicité ni source |
| `Notification` | `user` direct | modèle minimal mais correctement rattaché |
| `Dividend` | `user` direct | pas de compte, devise, source, fiscalité ni identifiant externe |

Le modèle ne contient encore ni institution, connexion, position, taux de change, snapshot patrimonial, immobilier, prêt, private equity, import/synchronisation ou portefeuille virtuel.

### 3.3 Invariants manquants

- Une `Transaction` peut être créée avec `transaction.user != transaction.account.user` ; aucun `clean()`, service ou contrainte applicative ne l'empêche.
- Les accès lecture principaux filtrent bien sur l'utilisateur et l'édition inter-utilisateur d'un compte retourne `404` dans le smoke test.
- Les vues `AccountSourceModal`, `AddAccountModal`, `EditAccountModal`, `DeleteAccountModal`, `AddSubscriptionModal`, `EditSubscriptionModal` et `DeleteSubscriptionModal` n'héritent toutefois pas de `LoginRequiredMixin`.
- Les objets globaux `Asset` et `PriceHistory` peuvent rester partagés si leur contenu est strictement public ; toutes les positions, transactions, valorisations privées et métadonnées utilisateur devront être rattachées et filtrées.
- Les modèles importent directement `django.contrib.auth.models.User` au lieu de `settings.AUTH_USER_MODEL`.

## 4. Problèmes bloquants classés par priorité

### P0 — avant toute migration ou mise en production

#### P0.1 — Migration `FundBoard.0005` destructive et incorrecte

La migration `0005_account_balancehistory_dividend_income_subscription_and_more.py` :

- crée de nouvelles tables `Account`, `Income`, `Subscription`, `Dividend` et `BalanceHistory` sans `RunPython` de copie ;
- supprime ensuite `CompteBancaire`, `InvestmentAccount`, `Revenu`, `Abonnement`, `Dividende` et `HistoriqueSolde` ;
- retire les deux anciens rattachements de `Transaction`, puis ajoute `account_id` avec la valeur ponctuelle `0` ;
- renomme `valeur_basse` en `high_price` et `valeur_haute` en `low_price`, donc inverse sémantiquement les valeurs hautes et basses.

Deux scénarios ont été reproduits sur des bases temporaires :

- base `0004` peuplée sans transaction : migration réussie, puis `Account=0`, `Income=0`, `Subscription=0`, `Dividend=0`, `BalanceHistory=0`; un cours haut `20.00` et bas `10.00` devient `high_price=10.00`, `low_price=20.00` ;
- même base avec une transaction : échec `IntegrityError`, car `account_id=0` ne référence aucun compte.

Cette migration ne doit pas être modifiée tant que son état d'application réel n'est pas connu. Une base arrêtée à `0004` ne doit surtout pas exécuter `0005` avant export vérifié des données historiques.

#### P0.2 — Base et sauvegardes réelles inconnues

Le clone ne contient aucune base. Il faut obtenir avant toute migration sensible :

- le moteur et l'emplacement de la base réellement utilisée ;
- la sortie de `showmigrations FundBoard` sur cet environnement ;
- un dénombrement des lignes par table sans exposer les données ;
- une sauvegarde cohérente, chiffrée si elle quitte la machine, son SHA-256 et un test de restauration.

Sans ces éléments, les données éventuellement perdues lors d'une application passée de `0005` ne sont récupérables que depuis une sauvegarde antérieure.

#### P0.3 — Authentification inutilisable

- `common/login.html` et `common/signup.html` étendent `base.html`, absent : les deux routes lèvent `TemplateDoesNotExist`.
- toutes les vues FundBoard protégées utilisent `reverse_lazy('fundboard:login')`, route inexistante : une visite anonyme lève `NoReverseMatch` au lieu de rediriger vers `dashboard:login`.
- les vues modales listées en 3.3 sont accessibles anonymement ; les écritures finissent généralement en erreur en raison de `AnonymousUser`, mais la protection doit être explicite et testée.

#### P0.4 — Socle de dépendances non supporté

Le projet épingle Django 4.2.3. Au 3 septembre 2026, Django 4.2 est hors support depuis avril 2026. Django 5.2.17 est la version corrective courante de la LTS 5.2, maintenue en sécurité jusqu'en avril 2028. Le passage vers 5.2.17 a réussi pour `check` et `makemigrations --check` dans un environnement temporaire, mais ce signal reste insuffisant sans tests.

Sources officielles :

- <https://www.djangoproject.com/download/>
- <https://docs.djangoproject.com/en/5.2/faq/install/>
- <https://docs.djangoproject.com/en/5.2/releases/>

### P1 — stabilisation fonctionnelle et sécurité immédiate

| Problème | Preuve/impact | Correction proposée en Phase 1 |
|---|---|---|
| Aucun test | `manage.py test` trouve 0 test | installer et configurer pytest, puis caractériser routes, modèles et permissions |
| `.gitignore` masque le futur travail | `**/tests/*` et tous les `management/commands/*` sont ignorés | remplacer par un `.gitignore` Python/Django ciblé et vérifier `git check-ignore` |
| Portefeuille cassé | route présente, `fundboard/portfolio.html` absent | rétablir une page de compatibilité minimale testée |
| Abonnements personnalisés cassés | `Decimal * float` lève `TypeError` | service de normalisation annuel entièrement en `Decimal`, avec tests |
| Graphique abonnements invalide | HTML produit `JSON.parse('[\u0027Monthly\u0027]')` et `JSON.parse('[Decimal(...)]')` | sérialiser avec `json_script` ou données JSON dédiées |
| Revenus obsolètes | template demande `nom`, `montant`, `frequence`, `date_prochain_paiement` au modèle anglais | adapter le template et caractériser la capacité conservée ; CRUD en phase ultérieure |
| Montants/devise mal affichés | comptes et transactions affichent toujours `€` ; formulaire compte n'expose pas la devise | afficher la devise du modèle et tester les cas non EUR |
| Propriété non garantie | `Transaction.user` peut diverger de `Account.user` | validation de domaine + tests à deux utilisateurs ; migration corrective additive plus tard |
| Réglages de déploiement faibles | `DEBUG=True`, `ALLOWED_HOSTS=[]`, cookies/HSTS/SSL non configurés ; 7 avertissements `check --deploy` | configuration typée par environnement et `.env.example` sans secrets |
| Langue/fuseau incohérents | `en-us`, `UTC` | `fr-fr`, stockage UTC via `USE_TZ`, affichage initial `Europe/Paris` |
| Assets absents | `css/styles.css`, JS de dashboard et trois SVG FundBoard introuvables ; chemin GameBoard avec `\` | corriger les chemins et ajouter des tests de collecte/rendu |
| Dépendances CDN | Bootstrap 5.1.3 via CDN ; Chart.js non versionné et chargé à deux endroits | conserver temporairement le minimum, puis migrer vers Tabler local en Phase 2 |
| Appel réseau dans une vue | convertisseur ToolBoard : `requests.get` sans timeout/cache | déplacer vers un service, timeout explicite, mock dans les tests |

### P2 — dette à traiter pendant les phases suivantes

- aucun modèle FundBoard n'est enregistré dans l'admin ;
- aucun index métier ou contrainte d'idempotence, hormis l'unicité `(asset, date)` ;
- plusieurs formulaires ont des widgets/classes et retours d'erreurs incohérents ;
- le JavaScript modal ne vérifie pas le statut HTTP et injecte toute réponse reçue ;
- le dashboard référence des graphiques sans données ni script présent ;
- le logger maison écrit des messages non structurés dans des fichiers locaux ignorés, sans redaction ;
- plusieurs imports et classes sont inutilisés ou dupliqués ;
- les templates GameBoard `naval_battle.html`, `tic_tac_toe.html`, `chess.html` et `pages/error.html` sont référencés mais absents ;
- la couverture fonctionnelle des imports/exports SkyJo n'est pas testée et `openpyxl` n'est pas déclaré alors que `pandas.read_excel()` peut en avoir besoin.

## 5. Matrice de risques

| Risque | Probabilité | Impact | Niveau | Mesure immédiate |
|---|---:|---:|---:|---|
| perte/échec de migration depuis `0004` | élevée si une ancienne base existe | critique | P0 | geler les migrations, inventorier et sauvegarder la base réelle |
| données déjà perdues après `0005` | inconnue | critique | P0 | rechercher une sauvegarde antérieure et comparer les dénombrements |
| accès ou mutation non autorisée | moyenne | critique | P0/P1 | authentifier toutes les vues et ajouter des tests croisés à deux utilisateurs |
| régression masquée par absence de tests | élevée | élevée | P1 | suite de caractérisation avant refactorisation |
| calcul financier erroné par `float`/arrondi | élevée | élevée | P1/P3 | services purs en `Decimal`, règles d'arrondi documentées |
| dépendance/framework vulnérable | élevée | élevée | P0/P1 | montée contrôlée vers Django 5.2.17 et versions verrouillées |
| fournisseur externe indisponible | élevée à terme | moyenne/élevée | P5/P6 | adaptateurs, cache, timeouts, dernières données connues |
| fuite de secret connecteur | moyenne à terme | critique | P6 | coffre/chiffrement externe, redaction, lecture seule et tests |
| double import/synchronisation | élevée sans clé | élevée | P3/P4/P6 | empreintes, clés d'idempotence et transactions atomiques |

## 6. Audit séparé des archives de référence

### 6.1 Prototype Binance de `dev-gamebord_fundboard.zip`

Le fichier n'a pas été copié. Constats :

- il ne compile pas : `first_retrieve()` n'a aucun corps ;
- `first_retrieve` ne reçoit pas `self` et `get_timestamp()` retourne deux variables non définies ;
- une grande table d'endpoints mélange endpoints utiles, inutiles et doublons ;
- `binance_request()` exécute toujours `requests.get()`, même pour les endpoints déclarés `POST` ;
- aucun timeout, validation de statut, retry borné, jitter, pagination, synchronisation incrémentale ou idempotence ;
- gestion des limites par `sleep` bloquant et en-têtes partiels ;
- absence de DTO, mapper, état de connexion et vérification des restrictions lecture seule.

Seul l'inventaire fonctionnel (soldes, dépôts, retraits, trades, conversions, rewards) est réutilisable comme aide à la conception. Les endpoints devront être revérifiés dans la documentation Binance au moment de la Phase 6.

### 6.2 Prototype Trade Republic de `dev-gamebord_fundboard.zip`

Le fichier sans extension compile, mais n'est pas intégrable :

- import direct de `FundBoard.models.Transaction` et écriture de champs inexistants `transaction_id` et `data` ;
- méthodes définies sans `self` ni `@staticmethod`, puis appelées comme méthodes liées ;
- PIN et jeton de session détenus par l'objet sans stratégie de chiffrement/révocation ;
- endpoints HTTP/WebSocket privés, aucun timeout, retry, backoff ou contrôle de protocole ;
- payloads fournisseur mélangés au stockage ORM ;
- aucune normalisation financière, devise, `Decimal`, clé d'idempotence ou journal redacted.

### 6.3 `trade_republic_scraper-main.zip`

Le script séparé compile et sa licence MIT a été identifiée. Il fournit une référence utile pour le flux de login, la pagination par curseur, `timelineTransactions` et `timelineDetailV2`. Il ne doit pas être transplanté :

- numéro et PIN sont lus depuis un fichier INI en clair ;
- jeton placé dans les messages WebSocket ;
- données brutes écrites en JSON/CSV sans politique de sensibilité/rétention ;
- aucun timeout/retry/backoff, peu de validation et dépendance à des libellés localisés ;
- variables globales de sortie et mélange collecte/transformation/persistance.

Toute réutilisation substantielle devra conserver l'avis de licence MIT. L'automatisation Trade Republic restera expérimentale, derrière feature flag et validation explicite ; l'import manuel est prioritaire.

## 7. Schéma cible ajusté

Le schéma cible du plan est retenu, avec les conventions suivantes :

| Actuel | Cible | Stratégie |
|---|---|---|
| `Account` | compte canonique + institution + connexion | enrichissement additif ; préserver les PK |
| `Asset` | `Instrument` canonique | ajout des identifiants et de la devise avant éventuel renommage contrôlé |
| aucun modèle | `Position` | nouveau modèle entre compte et instrument |
| `Transaction` minimale | transaction canonique | champs ajoutés d'abord nullables, backfill, validation, puis contraintes |
| `PriceHistory` | cours horodaté et sourcé | réparer haut/bas, augmenter la précision, ajouter devise/source/qualité/fraîcheur |
| `BalanceHistory` | snapshots compte/position/patrimoine | conserver les lignes et migrer vers un snapshot générique ou une façade claire |
| `Dividend`/`Income` | cashflows typés et sourcés | préserver la sémantique ; ne fusionner qu'après tests et migration explicite |
| `Watchlist`/`WatchAsset` | watchlists canoniques | conserver, ajouter unicité et ownership indirect vérifié |
| aucun modèle | FX, immobilier, prêts, private equity | ajouts spécialisés après le socle canonique |
| aucun modèle | imports, sync jobs, audit | modèles techniques séparés, sans secret ni payload sensible non filtré |
| aucun modèle | paper portfolios/orders | agrégat totalement séparé des comptes réels |

Les instruments et cours publics peuvent être globaux. Toute donnée patrimoniale est propriétaire directement ou via un compte/portefeuille dont l'appartenance est vérifiée.

## 8. Stratégie de migration sans perte

### 8.1 Préflight obligatoire

1. Identifier la base réelle et son état de migration.
2. Passer l'application en maintenance pour une migration sensible.
3. Effectuer une sauvegarde cohérente (`sqlite3 .backup` pour SQLite, `pg_dump --format=custom` pour PostgreSQL), chiffrer si nécessaire, calculer son SHA-256.
4. Restaurer la sauvegarde dans un environnement isolé et comparer schéma, dénombrements et sommes de contrôle métier.
5. Exécuter les migrations et validations sur la copie restaurée avant la base réelle.

### 8.2 Traitement spécial de `0005`

- **Base neuve ou absente** : la chaîne actuelle peut être appliquée, car il n'existe aucune donnée historique à perdre ; les défauts haut/bas restent à corriger par une nouvelle migration.
- **Base déjà en `0005`** : ne pas réécrire `0005`. Préserver les tables actuelles ; récupérer les anciennes données uniquement depuis une sauvegarde pré-`0005`, via un import de récupération contrôlé et idempotent.
- **Base en `0001`–`0004` avec données** : ne pas lancer `migrate`. Construire d'abord un exporteur historique en lecture seule utilisant l'état de migration, produire un manifeste de comptes/lignes/checksums, puis valider un import dans le schéma courant sur une copie.

### 8.3 Ordre proposé des futures migrations métier

Les numéros exacts seront générés par Django après inventaire de la base réelle ; l'ordre logique est :

1. migration corrective non destructive pour OHLC et invariants constatés ;
2. ajout des institutions, connexions et métadonnées de compte, nullable au départ ;
3. enrichissement de l'instrument et ajout des positions ;
4. enrichissement de transaction, génération déterministe des clés d'idempotence et backfill des devises/sources ;
5. validation de cohérence `Transaction`/`Account`, puis suppression éventuelle du propriétaire redondant ;
6. ajout des contraintes uniques et champs non nuls seulement après rapport de validation ;
7. snapshots, change, imports/synchronisations et audit ;
8. modèles spécialisés, puis paper trading dans des migrations distinctes.

Chaque retrait de modèle ou champ sera une migration ultérieure, après une version de coexistence et une vérification de parité. Les migrations de données seront réversibles lorsque la sémantique le permet et testées sur des données représentatives.

## 9. Arborescence cible proposée

```text
Mizzac/
├── Core/
│   ├── context_processors.py
│   ├── navigation.py
│   ├── templates/
│   │   ├── layouts/base.html
│   │   └── partials/{navbar,sidebar,footer,messages}.html
│   └── static/core/
│       ├── css/app.css
│       ├── js/app.js
│       └── vendor/tabler/
├── FundBoard/
│   ├── domain/
│   │   ├── money.py
│   │   ├── transactions.py
│   │   ├── valuations.py
│   │   ├── loans.py
│   │   ├── simulations.py
│   │   └── paper_trading.py
│   ├── models/                 # justifié lorsque le modèle canonique sera introduit
│   │   ├── accounts.py
│   │   ├── instruments.py
│   │   ├── transactions.py
│   │   ├── valuations.py
│   │   ├── assets_liabilities.py
│   │   └── operations.py
│   ├── services/
│   │   ├── net_worth.py
│   │   ├── performance.py
│   │   ├── pricing.py
│   │   ├── fx.py
│   │   ├── reconciliation.py
│   │   ├── loan_calculator.py
│   │   ├── compound_interest.py
│   │   └── paper_execution.py
│   ├── integrations/
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── binance/{client,mappers,sync}.py
│   │   ├── ledger/{addresses,mappers,sync}.py
│   │   ├── trade_republic/{client,mappers,sync}.py
│   │   ├── market_data/{base,yahoo,ecb,crypto}.py
│   │   └── open_banking/{base,provider}.py
│   ├── imports/{schemas,json_importer,excel_importer,templates}.py
│   ├── exports/{json_exporter,excel_exporter,csv_exporter}.py
│   ├── view_modules/           # transition depuis views.py sans rupture de routes
│   ├── management/commands/
│   ├── templates/fundboard/
│   ├── static/fundboard/
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   ├── migrations/
│   │   └── contracts/
│   ├── tasks.py
│   ├── urls.py
│   └── views.py                # façade temporaire pendant la transition
├── tests/                      # smoke tests transverses Core/apps
└── docs/
    ├── architecture/
    ├── operations/
    └── imports/
```

Les dossiers ne seront créés qu'au moment où une responsabilité réelle y sera déplacée. La Phase 1 restera volontairement proche de l'arborescence actuelle.

## 10. Dépendances : conserver, remplacer ou ajouter

### Phase 1

| Dépendance actuelle | Décision |
|---|---|
| `django==4.2.3` | passer brièvement au dernier 4.2 correctif pour caractériser les dépréciations, puis verrouiller `Django==5.2.17` |
| `jsonfield==3.1.0` en double | supprimer : aucun import et les modèles utilisent déjà `models.JSONField` |
| `python-dotenv==1.0.0` | conserver temporairement, mettre à jour et centraliser le parsing d'environnement |
| `requests==2.31.0` | conserver pour ToolBoard, mettre à jour et isoler derrière un service avec timeout |
| `Pillow==11.0.0` | conserver pour `Game.cover`, sous version compatible/supportée |
| `pandas==2.2.2` | conserver pour l'import Excel SkyJo tant que cette capacité est maintenue |
| `numpy==2.1.2` | retirer des dépendances directes si aucun usage direct n'apparaît ; laisser pandas résoudre sa dépendance |

Ajouter un outillage de développement verrouillé : `pytest`, `pytest-django`, `pytest-cov` et `ruff`. Ajouter une configuration dans `pyproject.toml` et séparer clairement dépendances d'exécution et de développement.

### Phases ultérieures

- Phase 2 : `@tabler/core@1.4.0` via npm avec lockfile, assets générés/copiés localement et licence. Cette version est la stable officielle vérifiée au jour de l'audit : <https://github.com/tabler/tabler/releases> et <https://www.npmjs.com/package/@tabler/core>.
- Phase 2/5 : retenir une seule bibliothèque de graphiques, probablement ApexCharts, avec version verrouillée.
- Phase 4 : `openpyxl` pour les modèles, validations et imports/exports Excel.
- Préparation production : `psycopg` dans un groupe/déploiement PostgreSQL distinct ; SQLite reste le défaut de développement.
- Phase 5 : fournisseurs de marché ajoutés uniquement derrière les interfaces et après validation des conditions d'utilisation.
- Phase 6 : bibliothèque de chiffrement ou gestionnaire de secrets choisi avant toute persistance de jeton.
- Phase 10 : Celery/Redis/beat seulement après décision sur l'environnement de déploiement ; une commande planifiée avec verrou en base est l'alternative initiale plus simple.

## 11. Plan de tests

### Socle Phase 1

1. Tests de routes anonymes/authentifiées pour chaque application.
2. Tests de rendu des templates login, signup, accueil et pages FundBoard.
3. Tests de toutes les modales : en-tête AJAX, authentification, CSRF, succès/erreurs de formulaire.
4. Tests avec deux utilisateurs : liste, détail, édition, suppression et objets liés ; l'accès croisé doit retourner `404` ou `403` sans révéler l'existence.
5. Tests modèles : fréquences, montants négatifs/positifs, cohérence transaction-compte, devise et `full_clean()`.
6. Tests `Decimal` avec cas mensuel, annuel, quotidien, hebdomadaire et personnalisé, sans conversion en `float`.
7. Tests de sérialisation sûre des données graphiques.
8. Tests de migration sur copies temporaires : base neuve, état `0004` peuplé, état `0005` et récupération depuis sauvegarde.
9. Smoke tests des assets statiques et du layout commun.
10. `check`, `check --deploy`, `makemigrations --check --dry-run`, Ruff et couverture à chaque jalon.

### Phases métier

- services financiers purs avec cas connus, arrondis et propriétés invariantes ;
- imports JSON/XLSX valides, invalides, partiels, dupliqués, formules et tailles limites ;
- exports sans secrets et protection contre l'injection de formules CSV/XLSX ;
- contrats de connecteurs avec clients simulés, pagination, timeout, retry, erreurs et redaction ;
- synchronisations répétées prouvant l'idempotence ;
- paper trading sans look-ahead et séparation stricte des comptes réels.

La suite standard ne fera aucun appel réseau réel et ne dépendra d'aucun secret.

## 12. Découpage détaillé proposé pour la Phase 1

Chaque tâche forme un petit jalon validable :

1. **Hygiène du dépôt** : corriger `.gitignore`, ajouter `pyproject.toml`, dépendances dev, configuration pytest/Ruff ; prouver que les tests et commandes sont suivis par Git.
2. **Caractérisation transversale** : ajouter les smoke tests des cinq applications et les tests des routes/noms existants.
3. **Authentification** : réparer les templates login/signup, centraliser `LOGIN_URL`, corriger les redirections FundBoard et tester anonyme/authentifié.
4. **Permissions FundBoard** : protéger toutes les modales, factoriser les querysets propriétaires, tester lecture/édition/suppression entre deux utilisateurs.
5. **Régressions visibles** : restaurer le template portefeuille minimal, corriger revenus, assets manquants et chemins statiques sans refondre l'UI.
6. **Calculs et JSON** : extraire le calcul annuel des abonnements en service pur `Decimal`, utiliser une sérialisation sûre et ajouter les cas limites.
7. **Configuration** : variables d'environnement typées pour `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, CSRF/cookies/proxy/SSL ; `fr-fr`, affichage initial Europe/Paris, `.env.example` non sensible.
8. **Base de données** : configuration SQLite développement/PostgreSQL production, documentation de sauvegarde/restauration et commande de diagnostic non sensible de l'état de migration.
9. **Montée de dépendances** : baseline au dernier correctif 4.2, résolution des dépréciations, puis Django 5.2.17 ; versions nettoyées et verrouillées.
10. **Validation finale Phase 1** : compileall, suite complète, couverture, Ruff, `check`, `check --deploy`, migrations sèches et smoke test manuel documenté.

Aucune nouvelle migration métier n'est nécessaire pour les tâches 1 à 10. La correction de données `0005` attend l'inventaire de la base réelle et fera l'objet d'un plan validé séparément avant exécution.

## 13. Commandes exécutées et résultats

| Commande/contrôle | Résultat |
|---|---|
| `git status --short --branch` | branche correcte, worktree propre au départ |
| `python -...` | commande absente (`127`) ; documentation à corriger |
| `python3 --version` | Python 3.12.3 |
| `python3 -m compileall -q Mizzac` | succès |
| installation `requirements.txt` sous `/tmp` | succès après autorisation réseau ; aucun paquet installé dans le dépôt |
| `manage.py check` sous Django 4.2.3 | succès, 0 problème |
| `manage.py check --deploy` | 7 avertissements : HSTS, redirection SSL, clé d'audit faible, cookies session/CSRF, DEBUG, ALLOWED_HOSTS |
| `manage.py makemigrations --check --dry-run` | aucune modification détectée |
| `manage.py showmigrations --plan` | migrations présentes mais non appliquées, faute de base fournie |
| `manage.py test --verbosity 2` | succès technique, **0 test exécuté** |
| migration complète d'une base temporaire vide | succès |
| smoke tests FundBoard | erreurs confirmées login, portefeuille, abonnements personnalisés ; pages restantes rendues comme détaillé |
| smoke tests autres applications | Dashboard, DrunkBoard, GameBoard et ToolBoard : HTTP 200 authentifié ; login/signup en erreur |
| scénarios de migration `0004 → 0005` peuplés | perte de lignes et inversion OHLC ; `IntegrityError` avec transaction |
| syntaxe prototype Binance | échec `IndentationError` autour de `first_retrieve()` |
| syntaxe prototype Trade Republic et scraper séparé | succès, incompatibilités fonctionnelles confirmées |
| `manage.py check` sous Django 5.2.17 isolé | succès |
| `manage.py makemigrations --check --dry-run` sous Django 5.2.17 | aucune modification détectée |
| `manage.py test` sous Django 5.2.17 | 0 test, donc compatibilité non encore démontrée |
| `findstatic` ciblé | quatre références statiques importantes introuvables |

Le contrôle `showmigrations` a créé un fichier SQLite vide ignoré de 0 octet ; il a été déplacé vers `/tmp/mizzac-phase0-empty-db.sqlite3`. Le dépôt ne contient toujours aucune base locale. Les autres bases, dépendances et données factices de l'audit sont uniquement sous `/tmp`.

## 14. Fichiers et migrations modifiés

- Créé : `AUDIT_PHASE_0_FUNDBOARD.md`.
- Aucun fichier applicatif modifié.
- Aucune migration créée, réécrite ou appliquée à une base utilisateur.
- Aucune donnée utilisateur consultée ou modifiée.

## 15. Écrans concernés

Aucune refonte ni capture n'a été produite en Phase 0. Les rendus ont été vérifiés via le client de test Django avec des données factices :

- pages principales des cinq applications rendues pour un utilisateur authentifié ;
- login/signup en erreur de template ;
- dashboard FundBoard, transactions, revenus et comptes rendus ;
- portefeuille et abonnements personnalisés en erreur ;
- accès inter-utilisateur à l'édition d'un compte refusé en `404` ;
- modales compte accessibles anonymement, défaut à corriger.

## 16. Limites et décisions requises

1. Indiquer où se trouve la base réellement utilisée et si une sauvegarde antérieure à `FundBoard.0005` existe.
2. Confirmer si `FundBoard.0005` a déjà été appliquée sur cette base.
3. Confirmer que l'inscription doit rester publique ; sinon la Phase 1 la désactivera au profit de comptes créés par l'administrateur.
4. Valider le périmètre de Phase 1 décrit en section 12 avant toute implémentation.

Les choix de fournisseur de marché, d'open banking, de chiffrement de secrets et d'orchestrateur de tâches sont volontairement différés aux phases où leurs coûts et contraintes pourront être comparés.
