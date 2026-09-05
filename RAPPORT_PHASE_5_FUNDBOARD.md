# Rapport de phase 5 — Cours, valorisation et dashboard patrimonial

Date de validation : 5 septembre 2026  
Branche de travail : `mizeos-FundBoard-test`  
Version unique : Python 3.12 / Django 6.1.1

## 1. Résumé du résultat fonctionnel

La phase 5 est terminée. FundBoard dispose maintenant d'une interface commune
de données de marché, d'adaptateurs Yahoo/yfinance, CoinGecko et Frankfurter
v2/ECB, d'un cache historique, d'une valorisation multi-actifs et de snapshots
quotidiens reproductibles.

Le dashboard consolide trésorerie, titres, cryptomonnaies, immobilier, private
equity et prêts dans la devise patrimoniale choisie. Il montre les actifs,
passifs, patrimoine net, allocation, historique, performance Modified Dietz,
benchmark et anomalies de données. Une valeur sans cours ou taux n'est jamais
mélangée au total : elle est exclue et signalée comme valorisation partielle.

Les actions, ETF, fonds et indices sont affichés en EUR par défaut ; les
cryptomonnaies le sont en USD. Les boutons **Défaut / EUR / USD** convertissent
immédiatement l'affichage des positions à partir du taux en cache, sans
rafraîchissement de page ni nouvel appel réseau.

## 2. Constats et décisions prises

- Frankfurter v2 est le fournisseur de change retenu. Chaque requête EUR/USD
  force `providers=ECB`, puis le taux direct et son inverse sont enregistrés
  atomiquement avec date et source `frankfurter-ecb`.
- Yahoo via `yfinance==1.7.0` fournit les cours quotidiens et historiques des
  actions, ETF, fonds, indices et le benchmark. Son usage est documenté comme
  personnel, différé et non garanti, jamais comme temps réel.
- CoinGecko fournit les cryptomonnaies en USD. L'identifiant CoinGecko exact,
  par exemple `bitcoin`, est explicite afin de ne pas confondre un ticker avec
  l'identité du cryptoactif. Une clé Demo reste facultative et configurable.
- Les appels HTTP sont confinés dans `integrations/market_data/`. Une vue `GET`
  n'effectue aucun appel externe ; seules les actions `POST` authentifiées et
  protégées par CSRF déclenchent une collecte.
- Les valeurs fournisseur deviennent des `Decimal` à la frontière de
  l'adaptateur. Les calculs financiers ne manipulent pas de `float` binaire.
- Un cours est unique par instrument, instant observé et source. Un taux est
  unique par paire, date et source. Un rejeu met à jour ou retrouve la même
  donnée au lieu de la dupliquer.
- Une panne place le statut en erreur sans effacer le dernier cours ni le
  dernier taux valide. L'interface affiche alors le cache et avertit qu'il est
  ancien ou que l'actualisation a échoué.
- La fraîcheur effective vaut deux heures pour une crypto et quatre jours pour
  les autres instruments et le change. Source, devise, date, fuseau, état du
  marché, retard et fraîcheur sont visibles dans le détail.
- Les snapshots sont créés uniquement à partir d'une valorisation complète,
  sont idempotents pour une même journée et ne déclenchent aucun appel réseau.
- ApexCharts, déjà centralisé dans `Core`, affiche désormais l'allocation, le
  patrimoine historique et les historiques de compte/instrument.

## 3. Fichiers créés ou modifiés

Créations principales :

- `Mizzac/FundBoard/integrations/market_data/base.py`, `registry.py`,
  `frankfurter.py`, `yahoo.py` et `coingecko.py` : contrats, registre et
  adaptateurs ;
- `Mizzac/FundBoard/services/fx.py`, `display_currency.py`, `pricing.py`,
  `net_worth.py`, `snapshots.py` et `dashboard.py` : cache, conversions,
  valorisation, snapshots et performance ;
- `Mizzac/FundBoard/view_modules/market_data.py` : préférences, actions de
  collecte et détails protégés ;
- `Mizzac/FundBoard/management/commands/create_portfolio_snapshots.py` :
  snapshots locaux idempotents ;
- templates `market_settings.html`, `instrument_detail.html`,
  `account_detail.html`, `_currency_controls.html` et `_currency_value.html` ;
- `Mizzac/Core/static/core/js/currency.js` : bascule EUR/USD commune à toutes
  les applications ;
- `Mizzac/FundBoard/tests/test_market_data.py` ;
- `Mizzac/FundBoard/MARKET_DATA.md` et présent rapport.

Modifications principales :

- `Mizzac/FundBoard/models.py`, `admin.py`, `forms.py`, `urls.py` et `views.py` :
  préférences, états de collecte, identifiant CoinGecko, routes, dashboard et
  administration ;
- templates du dashboard, du portefeuille, des comptes, des instruments et de
  la navigation ;
- `Mizzac/Core/templates/core/base.html` et tests du layout : chargement global
  du module de conversion ;
- `Mizzac/ToolBoard/services/currency.py` et ses tests : même adaptateur
  Frankfurter/ECB au lieu d'une seconde implémentation du change ;
- `requirements-base.txt` : ajout de `yfinance==1.7.0` ;
- `.env.example` et `Mizzac/Mizzac/settings.py` : sélection des fournisseurs et
  clé CoinGecko facultative ;
- `README.md` et `Mizzac/FundBoard/MODELE_CANONIQUE.md` : exploitation et
  responsabilités des services.

## 4. Migrations et impact sur les données

La migration
`FundBoard.0003_price_market_state_price_market_timezone_and_more` :

- ajoute l'état et le fuseau du marché à `Price` ;
- ajoute le type d'instrument `INDEX` ;
- crée `MarketDataPreference`, une configuration par utilisateur avec les
  valeurs initiales EUR pour le patrimoine/actions et USD pour les cryptos ;
- crée `MarketDataStatus`, unique par utilisateur, instrument et fournisseur ;
- étend les types d'événement d'audit aux collectes, snapshots et préférences.

Elle a été générée sous Django 6.1.1 puis appliquée avec succès sur la base
SQLite vierge `/tmp/mizzac-phase5-mYax4P/phase5.sqlite3`. La base du dépôt n'a
pas été modifiée. Comme validé lors des phases précédentes, cette branche reste
destinée à une base neuve et ne contient aucune reprise d'une base historique.

## 5. Commandes de validation exécutées

| Commande | Résultat |
|---|---|
| `make ci` sous Django 6.1.1 | chaîne complète réussie |
| `python3 -m ruff check .` | aucun problème |
| `python3 -m compileall -q Mizzac` | succès |
| `manage.py check --settings=Mizzac.settings_test` | aucun problème |
| `manage.py makemigrations --check --dry-run` | aucun changement détecté |
| `pytest --cov --cov-report=term-missing` | 98 tests et 86 sous-tests réussis ; couverture 82,21 % |
| `python3 -Wd -m pytest -q` | 98 tests et 86 sous-tests réussis, sans avertissement |
| `manage.py migrate --noinput` sur SQLite vierge | toutes les migrations appliquées, dont `FundBoard.0003` |
| `manage.py check --deploy` avec réglages HTTPS | aucun problème |
| `node --check` sur `charts.js` et `currency.js` | syntaxe valide |
| import de `django`, `yfinance` et `pandas` | versions 6.1.1, 1.7.0 et 2.3.3 compatibles |
| `git diff --check` | aucune erreur d'espace ou marqueur de conflit |

Les tests fournisseurs sont entièrement mockés et ne nécessitent aucun accès
réseau. Ils couvrent notamment les réponses décimales, l'idempotence, la panne
avec conservation du cache, le refus d'un snapshot partiel, les valeurs EUR/USD,
le POST/CSRF, l'absence de collecte en `GET` et l'isolation entre utilisateurs.

## 6. Description des écrans concernés

- **Vue d'ensemble** : patrimoine net, date de dernière donnée, taux
  Frankfurter/ECB, actifs/passifs, allocation ApexCharts, historique, performance
  et état des collectes.
- **Marché et devises** : devise patrimoniale, devises par défaut des actions et
  cryptos, ticker du benchmark et rappel des trois fournisseurs actifs.
- **Portefeuille** : valeurs sources datées, bouton immédiat Défaut/EUR/USD et
  liens vers les détails d'instrument.
- **Détail instrument** : dernier cours, devise, instant, source, fraîcheur,
  retard, état/fuseau du marché, change disponible, historique ApexCharts et
  positions détenues.
- **Détail compte** : trésorerie, quote-part, positions sourcées et datées,
  conversion rapide et historique des snapshots par ApexCharts.

Aucune capture automatisée n'a été produite. Les rendus, routes, contenus et
permissions ont été validés avec le client de test Django.

## 7. Risques, limites et dette technique restante

- Yahoo/yfinance, CoinGecko et Frankfurter n'offrent ici ni SLA ni garantie de
  temps réel. Ce socle convient à l'usage patrimonial personnel, pas au passage
  d'ordres ni au calcul fiscal officiel.
- Les collectes restent manuelles. La planification, les reprises exponentielles
  et l'observabilité opérationnelle appartiennent aux phases 6 et 10.
- CoinGecko peut imposer un quota ou nécessiter une clé Demo selon les limites
  courantes de son offre.
- La conversion rapide couvre EUR et USD uniquement. Une troisième devise
  nécessiterait un élargissement explicite du modèle de préférences et de l'UI.
- Les opérations sur titres Yahoo peuvent être lues par l'adaptateur, mais ne
  modifient pas automatiquement les positions ou transactions.
- Une performance multi-devise ancienne exige des taux conservés aux dates des
  flux ; sans eux, le calcul signale l'impossibilité au lieu d'inventer un taux.
- Le snapshot enregistre les comptes, positions et patrimoine net. Le détail
  temporel spécialisé des biens, prêts et private equity reste prévu en phase 7.
- Les contrats réels des fournisseurs n'ont volontairement pas été appelés par
  la suite de tests ; leurs changements futurs devront être surveillés.

## 8. Proposition exacte pour la phase suivante

Exécuter la phase 6 connecteur par connecteur, en commençant par Binance :

1. définir un contrat de connexion et de synchronisation strictement en lecture ;
2. stocker seulement une référence vers les secrets, jamais les clés en base ;
3. importer comptes, positions et transactions avec curseur et idempotence ;
4. fournir une synchronisation initiale puis incrémentale, avec statut et erreurs
   expurgées dans l'interface ;
5. conserver l'import manuel de phase 4 comme solution de secours ;
6. ajouter des tests mockés de pagination, quota, reprise, doublon et permission ;
7. appliquer ensuite la même méthode à Ledger, puis au scraper Trade Republic
   expérimental ; différer l'open banking jusqu'au choix de son fournisseur.

## 9. Questions nécessitant validation

Aucune question ne bloque l'utilisation de la phase 5 avec les choix déjà
validés : Frankfurter/ECB, actions en EUR, cryptos en USD et conversion rapide.

Avant la phase 6, il faudra confirmer le premier connecteur à activer (Binance
reste l'ordre recommandé) et la méthode locale de stockage des références de
secrets en lecture seule.
