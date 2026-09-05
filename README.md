# Mizzac / FundBoard

Mizzac est un projet Django composé de `DashBoard`, `FundBoard`, `GameBoard`,
`DrunkBoard` et `ToolBoard`. La version de référence est Python 3.12 avec Django
6.1.1.

## Installation locale

Depuis la racine du dépôt :

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements-dev.txt
cp .env.example .env
```

Remplacez `DJANGO_SECRET_KEY` dans `.env` par une valeur aléatoire et privée. Le
fichier `.env` ne doit jamais être versionné.

Pour une base neuve uniquement :

```bash
cd Mizzac
python3 manage.py migrate
python3 manage.py loaddata ToolBoard/fixtures/tools.json  # facultatif
python3 manage.py createsuperuser                         # facultatif
python3 manage.py runserver
```

La phase 3 a remplacé le prototype FundBoard par une migration canonique
initiale. Seule une base neuve est prise en charge sur cette branche. Ne pointez
pas cette version vers une ancienne base FundBoard ; consultez
[OPERATIONS_DATABASE.md](OPERATIONS_DATABASE.md).

## Validation locale

La commande suivante ne requiert ni secret ni accès réseau :

```bash
make ci
```

Elle lance Ruff, la compilation Python, `manage.py check`, la vérification des
migrations et les tests avec couverture. Les commandes peuvent aussi être
lancées séparément avec `make lint`, `make check`, `make migrations` et
`make test`.

## Interface Tabler

Les distributions utilisées par Django sont déjà présentes sous
`Mizzac/Core/static/core/vendor/`. Pour les reconstruire exactement depuis le
lockfile, utilisez Node.js 20.19, 22.12 ou 24 et plus récent :

```bash
make frontend
```

Cette commande exécute `npm ci`, puis copie uniquement Tabler 1.4.0, les icônes
Tabler sélectionnées et ApexCharts 7.1.0 avec leurs licences. Aucun CDN n'est
nécessaire au navigateur ni au déploiement Python.

ApexCharts est chargé une seule fois par le layout `Core` et utilisable dans
toutes les applications via `window.MizzacCharts`. Les conventions, l'exemple
d'utilisation et la contrainte de licence personnelle sont documentés dans
[Mizzac/Core/CHARTS.md](Mizzac/Core/CHARTS.md).

## Dépendances et déploiement

- `requirements.txt` : exécution locale, Django 6.1.1 verrouillé ;
- `requirements-dev.txt` : tests, couverture et Ruff ;
- `requirements-production.txt` : pilote PostgreSQL ;
- `.env.example` : variables de configuration sans secret réel.

SQLite reste le choix par défaut en développement. PostgreSQL et les sauvegardes
sont documentés dans [OPERATIONS_DATABASE.md](OPERATIONS_DATABASE.md). Le
choix de version Django est consigné dans [DJANGO_VERSION.md](DJANGO_VERSION.md).

Le schéma financier, ses règles de signe, sa précision et son idempotence sont
décrits dans
[Mizzac/FundBoard/MODELE_CANONIQUE.md](Mizzac/FundBoard/MODELE_CANONIQUE.md).

## Saisie, imports et exports

Une fois connecté, FundBoard permet de créer, modifier et archiver manuellement
les comptes, instruments, positions, transactions, biens immobiliers et prêts.
La page **Imports / exports** fournit les modèles JSON et Excel 1.0, un dry-run,
un historique et des exports JSON, Excel ou CSV.

L'import applique une stratégie de succès partiel par ligne : chaque ligne
valide est enregistrée dans sa propre transaction et chaque ligne invalide est
entièrement ignorée puis ajoutée au rapport d'erreurs. Le schéma, les références
et les règles d'annulation sont documentés dans
[Mizzac/FundBoard/IMPORT_EXPORT_V1.md](Mizzac/FundBoard/IMPORT_EXPORT_V1.md).

## Cours, change et dashboard patrimonial

La phase 5 ajoute une valorisation consolidée reproductible, l'historique des
cours, les snapshots quotidiens, la performance Modified Dietz et les pages de
détail par compte et instrument. Les actions sont affichées en EUR et les
cryptomonnaies en USD par défaut ; un bouton commun permet de basculer rapidement
les positions entre EUR et USD sans nouvel appel réseau.

Les cours actions/ETF/indices proviennent de Yahoo via `yfinance`, les cryptos
de CoinGecko et le change EUR/USD de Frankfurter filtré sur les données BCE.
Toutes les collectes sont déclenchées explicitement, datées puis mises en cache.
Les sources, devises, dates, retards et états de fraîcheur sont visibles dans
l'interface. La configuration, les limites et la commande de snapshots sont
documentées dans
[Mizzac/FundBoard/MARKET_DATA.md](Mizzac/FundBoard/MARKET_DATA.md).

## Connexions financières en lecture seule

La phase 6 ajoute une interface commune pour Enable Banking, Binance Spot et
les imports locaux Ledger Live / Trade Republic. Le compte espèces Trade
Republic peut aussi être connecté automatiquement par son accès PSD2 via Enable
Banking ; les positions CTO/PEA restent hors de cette API. Enable Banking est le
choix par défaut pour un usage personnel restreint à ses propres comptes ;
Powens reste interchangeable mais n'est pas activé, car sa production exige un
contrat et aucun tarif public adapté à ce projet n'a été trouvé.

Aucun mot de passe bancaire, PIN, code 2FA, cookie, seed ou clé privée n'est
stocké en base. Les synchronisations sont explicites, incrémentales,
idempotentes et journalisées sans payload brut. Configuration, comparaison des
agrégateurs, limites et commande de planification sont documentées dans
[Mizzac/FundBoard/CONNECTORS.md](Mizzac/FundBoard/CONNECTORS.md).

## Immobilier, prêts et private equity

La phase 7 fournit des listes synthétiques et des pages de détail pour les biens
immobiliers, prêts et participations non cotées. Les valorisations manuelles et
capitaux restants sont datés, sourcés et tracés dans des historiques ApexCharts.
Les calculs séparent les devises et exposent valeur nette, rendement brut/net,
progression du prêt, engagement non appelé, DPI, RVPI et TVPI. Les conventions
et formules sont détaillées dans
[Mizzac/FundBoard/ASSETS_PHASE_7.md](Mizzac/FundBoard/ASSETS_PHASE_7.md).

## Simulations financières

La phase 8 ajoute des scénarios privés totalement séparés du patrimoine réel.
Le simulateur de prêt calcule mensualité ou durée, différés, assurance, frais,
remboursements anticipés et tableau d'amortissement. Le simulateur d'intérêts
composés prend en compte versements, rendement nominal, frais, inflation et
fiscalité finale simplifiée. Deux à quatre scénarios de même type et devise
peuvent être comparés puis exportés en JSON ou Excel. Les hypothèses, règles
d'arrondi et limites sont documentées dans
[Mizzac/FundBoard/SIMULATIONS_PHASE_8.md](Mizzac/FundBoard/SIMULATIONS_PHASE_8.md).

## Portefeuilles virtuels

La phase 9 ajoute un registre de paper trading entièrement distinct des comptes
réels : capital et cash fictifs, watchlist, ordres au marché ou à cours limité,
quantités entières ou fractionnaires, frais, spread et slippage. Une exécution
utilise exclusivement un cours horodaté déjà stocké, respecte un état de marché
simplifié et conserve la source ainsi que le signal de retard du cours.

La section suit positions, PRU, gains réalisés et latents, dividendes, splits,
performance et benchmark. Elle permet d'annuler les ordres ouverts, de cloner
ou remettre à zéro un portefeuille, puis d'exporter le registre en JSON ou
Excel. Aucun modèle virtuel ne référence un compte ou une transaction réelle et
le moteur ne possède aucun accès à un connecteur. Les conventions et limites
sont détaillées dans
[Mizzac/FundBoard/PAPER_TRADING_PHASE_9.md](Mizzac/FundBoard/PAPER_TRADING_PHASE_9.md).

## Automatisation et exploitation

La phase 10 fournit une maintenance planifiable qui crée les snapshots, traite
les ordres virtuels ouverts et, seulement avec une option explicite, actualise
change, cours suivis et connecteurs en lecture seule. Un verrou par utilisateur,
des compteurs, des identifiants de corrélation, une page **Exploitation** et un
healthcheck rendent chaque passage observable sans enregistrer de secret.

Les commandes de sauvegarde créent des archives privées accompagnées d'un
manifeste SHA-256. SQLite peut être vérifié puis restauré uniquement vers un
nouveau fichier ; PostgreSQL utilise les outils officiels `pg_dump` et
`pg_restore`. Les réglages web, en-têtes de sécurité et logs expurgés ont été
durcis. Consultez [INSTALLATION.md](INSTALLATION.md),
[OPERATIONS.md](OPERATIONS.md),
[SECURITY_AUDIT_PHASE_10.md](SECURITY_AUDIT_PHASE_10.md) et
[ADDING_CONNECTOR.md](ADDING_CONNECTOR.md).

Documentation Django : <https://docs.djangoproject.com/en/6.1/>
